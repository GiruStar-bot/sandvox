# Parallel episode runner, seeded domain randomization and curriculum
# stages for the Sandvox training harness (Roadmap v3, phase B).
#
#   python3 py/episode_runner.py --episodes 8 --seed 1 --stage train \
#       --randomize --workers 4 --out runs/batch.jsonl
#
# Three pieces:
#
# 1. Batch runner. Episodes are independent processes (multiprocessing,
#    fork) and results are collected as JSONL records in configuration
#    order - never completion order - so a batch file is itself
#    reproducible. Each record carries the full configuration, every
#    randomized draw (below), the final row, the per-year headline
#    series, and a sha256 over the canonical result: rerunning the same
#    batch configuration must reproduce the same hashes exactly.
#    Workers are REUSED, never spawned per episode: measured on the
#    merged main (evaluability report, 2026-11-07), a fresh process
#    pays ~10-13 s of import/initialization before its first episode -
#    the same order as a whole 25y episode (15.0 s warm) - which capped
#    a spawn-per-batch harness at 0.44 parallel efficiency and
#    236 episodes/hour. WorkerPool keeps fork-initialized workers alive
#    across batches so that cost is paid once per worker, not once per
#    batch or episode; run_batch reuses a caller-supplied pool, and
#    only creates (and closes) a temporary one when none is given.
#
# 2. Domain randomization. A policy trained at one calibrated point can
#    overfit that point's elasticities (Goodhart). The T-labelled
#    response parameters of data/modern/jpn/feedback_params.json (the
#    parameters whose _provenance label is "T": calibrated tuning
#    constants, no external source) are therefore drawn per episode
#    from declared multiplicative bands around their calibrated values,
#    seeded by (seed, episode index). Bands multiply the SIGNED value,
#    so a slope keeps its sign - a flipped slope would be a different
#    mechanism, not a calibration draw. Every draw is recorded in the
#    episode record (base, factor, value), so any episode can be
#    replayed exactly from its record alone.
#    Scope boundary: plausibility bounds and clamps (tfr_floor /
#    tfr_ceiling, attract_min/max, jgb_min/max, the drag/relief
#    clamps and floors) are NOT randomized - they are the model's
#    guardrails, not response strengths. Definitional constants are
#    not randomized either: ed_budget_unit_bn (the unit the education
#    elasticity is quoted per; the elasticity itself is in the spec)
#    and jgb_adjust_days (a cadence). Module-level T constants in
#    run_simulation.py (the central-bank passes, LAT pass, ...) have
#    no override surface and are out of scope here; the labelled
#    group in feedback_params.json is the randomization surface.
#    The bands themselves are declared T choices of this harness.
#
# 3. Curriculum stages. Training runs cheap (small n_per, short
#    horizon), evaluation runs dear (large n_per, long horizon) - the
#    v2 roadmap's measured scaling (25y synergy --full: n_per 2 ->
#    13.2 s, 10 -> 47.7 s, 20 -> 101.0 s) is what the stage sizes rest
#    on. STAGES below is the standard; callers may override any field
#    per episode.
#
# Reward: there is none, by design (user decision 2026-11-07). The
# design is examination-style: challenges and proposals flow through
# py/eval_interface.py, evaluation happens outside the environment,
# and these records are the evidence the external evaluator reads.
import argparse
import hashlib
import json
import os
import random  # lint-ok: keyed Random(seed) draws only - sample_overrides seeds every draw from (seed, index)
import sys
import time
from functools import partial

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import agent_env  # noqa: E402

# (section, key) -> (low, high) multiplicative band on the signed value.
DR_SPEC = {
    # fertility responses
    ("fertility", "ed_tfr_boost_per_unit"): (0.75, 1.33),
    ("fertility", "discontent_tfr_slope"): (0.75, 1.33),
    ("fertility", "food_infl_threshold"): (0.80, 1.25),
    ("fertility", "food_infl_tfr_slope"): (0.75, 1.33),
    ("fertility", "real_wage_tfr_slope"): (0.75, 1.33),
    # migration responses
    ("migration", "structural_baseline"): (0.85, 1.18),
    ("migration", "reopening_decay_years"): (0.75, 1.33),
    ("migration", "cap_ssw_multiplier"): (0.75, 1.33),
    ("migration", "cap_saturation_scale"): (0.75, 1.33),
    ("migration", "infl_attract_threshold"): (0.80, 1.25),
    ("migration", "infl_attract_slope"): (0.75, 1.33),
    ("migration", "discontent_attract_threshold"): (0.80, 1.25),
    ("migration", "discontent_attract_slope"): (0.75, 1.33),
    ("migration", "real_wage_attract_slope"): (0.75, 1.33),
    # fiscal / JGB responses
    ("fiscal_and_jgb", "senior_relief_multiplier"): (0.75, 1.33),
    ("fiscal_and_jgb", "jgb_infl_slope"): (0.75, 1.33),
    ("fiscal_and_jgb", "jgb_debt_gdp_slope"): (0.75, 1.33),
    ("fiscal_and_jgb", "jgb_bond_dep_threshold"): (0.80, 1.25),
    ("fiscal_and_jgb", "jgb_bond_dep_slope"): (0.75, 1.33),
    ("fiscal_and_jgb", "jgb_crisis_slope"): (0.75, 1.33),
    ("fiscal_and_jgb", "crisis_infl_premium"): (0.75, 1.33),
    ("fiscal_and_jgb", "crisis_food_premium"): (0.75, 1.33),
    ("fiscal_and_jgb", "vat_food_passthrough"): (0.80, 1.25),
    ("fiscal_and_jgb", "vat_ongoing_food_bite"): (0.75, 1.33),
}

STAGES = {
    "train": {"years": 10, "n_per": 2},
    "eval": {"years": 25, "n_per": 10},
    "final": {"years": 100, "n_per": 20},
}

_YEAR_FIELDS = ("year", "population", "births", "deaths", "net_mig", "tfr",
                "debt_gdp", "bond_dep", "jgb_10y", "discontent", "approval")


def sample_overrides(seed, index):
    """Seeded parameter draws for one episode. Returns (overrides,
    draws): overrides in the {section: {key: value}} shape the engine's
    load_feedback_params accepts, draws the full record of what was
    drawn (base, factor, value per parameter). Deterministic in
    (seed, index) across runs and platforms."""
    rng = random.Random("sandvox-dr:%s:%s" % (seed, index))
    base = agent_env.RS.load_feedback_params()
    overrides, draws = {}, {}
    for (sec, key), (lo, hi) in sorted(DR_SPEC.items()):
        v0 = float(base[sec][key])
        f = rng.uniform(lo, hi)
        v = v0 * f
        overrides.setdefault(sec, {})[key] = v
        draws["%s.%s" % (sec, key)] = {"base": v0, "factor": f, "value": v}
    return overrides, draws


def result_digest(final, years):
    canon = json.dumps({"final": final, "years": years},
                       sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()


def run_one(cfg, policy=None):
    """Run one episode from a plain-dict configuration and return its
    record. cfg keys: index, seed, years, scenario, full_mode, n_per,
    shocks (list or None), randomize (bool). The policy defaults to
    agent_env.null_policy; a supplied policy must be a module-level
    callable (it is pickled to worker processes)."""
    overrides, draws = (sample_overrides(cfg["seed"], cfg["index"])
                        if cfg.get("randomize") else (None, {}))
    env = agent_env.SandvoxEnv(
        years=cfg.get("years", 25),
        scenario=cfg.get("scenario", "baseline"),
        full_mode=cfg.get("full_mode", False),
        n_per=cfg.get("n_per", 2),
        shocks=cfg.get("shocks"),
        feedback_params=overrides,
    )
    ep = env.run(policy or agent_env.null_policy)
    years = [{k: row.get(k) for k in _YEAR_FIELDS} for row in ep["history"]]
    rec = {
        "index": cfg["index"],
        "seed": cfg["seed"],
        "config": {k: cfg.get(k) for k in
                   ("years", "scenario", "full_mode", "n_per", "randomize")},
        "draws": draws,
        "final": ep["final"],
        "years": years,
        "sha256": result_digest(ep["final"], years),
    }
    return rec


class WorkerPool:
    """A reusable pool of initialized episode workers (fork start
    method: workers inherit this process's imported engine, so no
    per-worker import cost; the pool then persists across batches
    until close()). Pass one pool to successive run_batch calls to
    amortize worker initialization over a whole training session."""

    def __init__(self, workers):
        import multiprocessing as mp
        self.workers = workers
        self._pool = mp.get_context("fork").Pool(workers)

    def map(self, configs, policy=None):
        return self._pool.map(partial(run_one, policy=policy), configs)

    def close(self):
        self._pool.close()
        self._pool.join()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
        return False


def run_batch(configs, workers=1, policy=None, pool=None):
    """Run a batch of episode configurations. Records come back sorted
    by configuration index regardless of worker completion order.
    With pool= (a WorkerPool) the initialized workers are reused;
    with workers>1 and no pool, a temporary pool is created for this
    batch and closed at the end."""
    if pool is not None:
        records = pool.map(configs, policy=policy)
    elif workers and workers > 1:
        with WorkerPool(workers) as p:
            records = p.map(configs, policy=policy)
    else:
        records = [run_one(c, policy=policy) for c in configs]
    return sorted(records, key=lambda r: r["index"])


def stage_configs(stage, episodes, seed, **over):
    """Build `episodes` configurations for a curriculum stage."""
    base = dict(STAGES[stage])
    base.update(over)
    return [dict(base, index=i, seed=seed) for i in range(episodes)]


def main():
    ap = argparse.ArgumentParser(description="Parallel Sandvox episode runner")
    ap.add_argument("--episodes", type=int, default=4)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--stage", choices=sorted(STAGES), default=None)
    ap.add_argument("--years", type=int, default=None)
    ap.add_argument("--n-per", type=int, default=None)
    ap.add_argument("--scenario", default="baseline")
    ap.add_argument("--full", action="store_true")
    ap.add_argument("--randomize", action="store_true",
                    help="draw T-labelled feedback parameters per episode (seeded)")
    ap.add_argument("--shock-seed", type=int, default=None,
                    help="sample each episode's shock schedule from this seed (P4 library)")
    ap.add_argument("--workers", type=int, default=1)
    ap.add_argument("--out", default=None, help="JSONL output path (default: stdout summary only)")
    a = ap.parse_args()

    if a.stage:
        cfgs = stage_configs(a.stage, a.episodes, a.seed,
                             scenario=a.scenario, full_mode=a.full,
                             randomize=a.randomize)
    else:
        cfgs = [dict(index=i, seed=a.seed, years=a.years or 25, n_per=a.n_per or 2,
                     scenario=a.scenario, full_mode=a.full, randomize=a.randomize)
                for i in range(a.episodes)]
    if a.shock_seed is not None:
        for c in cfgs:
            c["shocks"] = agent_env.random_shock_schedule(
                a.shock_seed * 100003 + c["index"], years=c.get("years", 25))

    t0 = time.time()  # lint-ok: CLI wall-clock reporting only - never feeds the simulation
    records = run_batch(cfgs, workers=a.workers)
    wall = time.time() - t0  # lint-ok: CLI wall-clock reporting only
    if a.out:
        with open(a.out, "w", encoding="utf-8") as fh:
            for r in records:
                fh.write(json.dumps(r, ensure_ascii=True, sort_keys=True) + "\n")
    print("episodes: %d | workers: %d | wall: %.1fs | per-episode: %.1fs"
          % (len(records), a.workers, wall, wall / max(1, len(records))))
    for r in records:
        print("  #%d final pop %d debt/gdp %.1f sha %s"
              % (r["index"], r["final"]["population"], r["final"]["debt_gdp"], r["sha256"][:12]))


if __name__ == "__main__":
    main()
