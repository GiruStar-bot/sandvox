# Roadmap v3 phase B: the training harness - parallel episode runner,
# seeded domain randomization, curriculum stages, reward socket.
#   python py/tests/test_episode_runner.py
# Pass conditions (roadmap v3): the same (seed, configuration) batch
# reproduces its result hashes exactly, randomized episodes keep the
# accounting identities, and the default configuration reproduces the
# merged baseline digit-for-digit.
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import Kit  # noqa: E402  (puts py/ on the path)

import agent_env  # noqa: E402
import episode_runner as ER  # noqa: E402


def main():
    k = Kit("py/tests/test_episode_runner.py")

    # --- domain randomization: spec discipline -----------------------
    params = json.load(open(os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..", "..",
        "data", "modern", "jpn", "feedback_params.json"), encoding="utf-8"))
    prov = params["_provenance"]
    k.check(all(prov[sec][key]["label"] == "T" for (sec, key) in ER.DR_SPEC),
            "B every randomized parameter is T-labelled in feedback_params provenance (%d params)" % len(ER.DR_SPEC))
    clamps = [("fertility", "tfr_floor"), ("fertility", "tfr_ceiling"),
              ("migration", "attract_min"), ("migration", "attract_max"),
              ("fiscal_and_jgb", "jgb_min"), ("fiscal_and_jgb", "jgb_max"),
              ("fertility", "ed_budget_unit_bn"), ("fiscal_and_jgb", "jgb_adjust_days")]
    k.check(all(c not in ER.DR_SPEC for c in clamps),
            "B plausibility bounds, clamps and definitional constants are NOT randomized (guardrails stay fixed)")

    o1, d1 = ER.sample_overrides(7, 0)
    o2, d2 = ER.sample_overrides(7, 0)
    o3, _ = ER.sample_overrides(7, 1)
    k.check(o1 == o2 and d1 == d2 and o1 != o3,
            "B draws are deterministic in (seed, index) and differ across indices")
    base = agent_env.RS.load_feedback_params()
    in_band = True
    for (sec, key), (lo, hi) in ER.DR_SPEC.items():
        v0 = float(base[sec][key])
        for draws in (d1,):
            f = draws["%s.%s" % (sec, key)]["factor"]
            v = draws["%s.%s" % (sec, key)]["value"]
            in_band &= lo <= f <= hi and v == v0 * f and (v0 == 0.0 or (v > 0) == (v0 > 0))
    k.check(in_band, "B every draw lies in its declared band, equals base x factor, and preserves the parameter's sign")

    # --- no reward, by design (user decision 2026-11-07) ---------------
    import inspect
    ep_plain = agent_env.SandvoxEnv(years=3, scenario="baseline").run(agent_env.null_policy)
    k.check("reward_fn" not in inspect.signature(agent_env.SandvoxEnv.__init__).parameters
            and "rewards" not in ep_plain and "reward_total" not in ep_plain,
            "B the environment exposes no reward hook and records no rewards (examination-style design: evaluation is external, via py/eval_interface.py)")

    # --- batch reproducibility (the phase pass condition) -------------
    cfgs = [dict(index=i, seed=3, years=5, scenario="baseline", n_per=2, randomize=True)
            for i in range(2)]
    r_par = ER.run_batch(cfgs, workers=2)
    r_ser = [ER.run_one(cfgs[0]), ER.run_one(cfgs[1])]
    k.check([r["sha256"] for r in r_par] == [r["sha256"] for r in r_ser]
            and r_par[0]["sha256"] != r_par[1]["sha256"],
            "B same-seed batch reproduces identical result hashes in parallel and serial; randomized indices differ")
    k.check(all(len(r["draws"]) == len(ER.DR_SPEC) for r in r_par),
            "B every episode record carries its full draw record (replayable from the record alone)")
    with ER.WorkerPool(2) as pool:
        rp1 = ER.run_batch(cfgs, pool=pool)
        rp2 = ER.run_batch(cfgs, pool=pool)
    k.check([r["sha256"] for r in rp1] == [r["sha256"] for r in rp2]
            == [r["sha256"] for r in r_ser],
            "B a reused WorkerPool (initialized workers kept across batches) reproduces the same hashes on every batch")

    # --- identities under randomization -------------------------------
    rec = r_par[0]
    ys = rec["years"]
    flow_ok = all(abs((ys[i]["population"] - ys[i - 1]["population"])
                      - (ys[i]["births"] - ys[i]["deaths"] + ys[i]["net_mig"])) <= 2
                  for i in range(1, len(ys)))
    finite = all(math.isfinite(v) for v in rec["final"].values() if isinstance(v, (int, float)))
    k.check(flow_ok and finite,
            "B randomized episode keeps the population flow identity every year and ends finite")

    # --- curriculum stages --------------------------------------------
    k.check(ER.STAGES["train"]["n_per"] < ER.STAGES["eval"]["n_per"] < ER.STAGES["final"]["n_per"]
            and ER.STAGES["train"]["years"] < ER.STAGES["eval"]["years"] < ER.STAGES["final"]["years"],
            "B curriculum stages are ordered: train cheap, eval dearer, final dearest (n_per and horizon)")

    # --- baseline invariance through the runner ------------------------
    b = ER.run_one(dict(index=0, seed=1, years=25, scenario="baseline", n_per=2, randomize=False))
    k.check(b["final"]["population"] == 100644584 and abs(b["final"]["debt_gdp"] - 334.0) < 0.05,
            "B default configuration through the runner reproduces the merged baseline exactly (pop %d, debt %.1f)"
            % (b["final"]["population"], b["final"]["debt_gdp"]))

    k.finish()


if __name__ == "__main__":
    main()
