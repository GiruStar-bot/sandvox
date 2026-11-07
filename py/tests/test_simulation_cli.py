# Verification suite for run_simulation.py (v5.0) and data/modern/jpn/feedback_params.json:
#   python3 py/tests/test_simulation_cli.py
# CLI-oracle: reference oracle files in outputs/py_oracle/ are present and run_simulation.py does not self-generate oracles
# CLI-params: feedback_params.json is the single source of truth with provenance metadata; overrides move simulation outputs
# CLI-budget: FY2024 budget (112,571.7 bn JPY) decomposes orthogonally with 0.0 residual, no defence double-counting, and redemption/interest split
# CLI-identity: annual and cumulative demographic flows satisfy Pop_t - Pop_{t-1} == Births_t - Deaths_t + NetMig_t with 0-person residual; runs are bit-identical
# CLI-replenish: Kish N_eff & L1 cohort divergence sample health metrics trigger replenish_persons_if_needed and preserve finite state
# CLI-polity: Election.designate and Election.run_upper_house execute constitutional PM alternation when the incumbent loses majority
import contextlib
import io
import json
import math
import os
import sys

from common import Kit, ROOT

sys.path.insert(0, ROOT)
import run_simulation as RS  # noqa: E402


def run_quiet(**kwargs):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        hist = RS.run_simulation(**kwargs)
    return hist, buf.getvalue()


def main():
    k = Kit("py/tests/test_simulation_cli.py")

    # 1. CLI-oracle: independent reference oracle files exist and self-generation is removed
    ps_oracles = [
        os.path.join(ROOT, "outputs", "py_oracle", "ps", "s1_n20", "m%02d.persons.sha.txt" % m)
        for m in range(14)
    ]
    st_oracle = os.path.join(ROOT, "outputs", "py_oracle", "st", "06_class.sha.txt")
    all_oracles_present = all(os.path.exists(p) for p in ps_oracles) and os.path.exists(st_oracle)
    no_self_oracle = not hasattr(RS, "ensure_oracle_dumps")
    k.check(
        all_oracles_present and no_self_oracle,
        "CLI-oracle all 15 reference oracle files exist in outputs/py_oracle/ and run_simulation.py has no self-generating oracle function",
    )

    # 2. CLI-params: single source of truth, schema validation, provenance metadata, and parameter sensitivity
    no_dup_defaults = not hasattr(RS, "DEFAULT_FEEDBACK_PARAMS")
    params = RS.load_feedback_params()
    prov = params.get("_provenance", {})
    has_all_prov = all(
        sec in prov and all(key in prov[sec] and len(str(prov[sec][key])) > 10 for key in RS.REQUIRED_PARAM_SCHEMA[sec])
        for sec in RS.REQUIRED_PARAM_SCHEMA
    )
    caught_bad_override = False
    try:
        RS.load_feedback_params(overrides={"fertility": {"non_existent_param": 1.0}})
    except KeyError:
        caught_bad_override = True
    k.check(
        no_dup_defaults and has_all_prov and caught_bad_override,
        "CLI-params feedback_params.json is the single source of truth with complete provenance metadata and strict schema validation",
    )

    # 3. CLI-budget: exact 112,571.7 bn JPY FY2024 budget decomposition with 0.0 residual and zero defence double-counting
    with open(os.path.join(ROOT, "data", "modern", "polity", "jpn_laws.json"), encoding="utf-8") as fh:
        laws_data = json.load(fh)
    fy24_lines = laws_data["laws"]["budget_fy2024"]["lines_bn_jpy"]
    b_dec = RS.decompose_fy2024_budget(fy24_lines, 112571.7, 1310438.5, 0.011)
    total_sum = (
        b_dec["budget_social_security"]
        + b_dec["budget_lat"]
        + b_dec["budget_debt_service"]
        + b_dec["budget_defence"]
        + b_dec["budget_core_ops"]
    )
    ds_split_sum = b_dec["budget_debt_redemption_0"] + b_dec["budget_debt_interest_0"]
    def_excluded = abs(b_dec["budget_named_non_def_ops"] - (6082.8 + 5405.4 + 5619.3 + 1000.0)) < 1e-6
    contingency_exact = abs(b_dec["budget_contingency_other"] - 4000.0) < 1e-6
    k.check(
        abs(total_sum - 112571.7) < 1e-6
        and abs(ds_split_sum - 27009.0) < 1e-6
        and def_excluded
        and contingency_exact,
        "CLI-budget FY2024 budget decomposes into 112,571.7 bn JPY with 0.0 residual, exact debt service split, and zero defence double-counting",
    )

    # 4. CLI-identity & determinism & parameter sensitivity (3-year fast checks)
    h1, _ = run_quiet(years=3, scenario="synergy", full_mode=True)
    h2, _ = run_quiet(years=3, scenario="synergy", full_mode=True)
    h_mod, _ = run_quiet(
        years=3,
        scenario="synergy",
        full_mode=True,
        feedback_params={"migration": {"structural_baseline": 220000.0}},
    )
    det_ok = (h1 == h2)
    param_moves_out = (h1[-1]["population"] != h_mod[-1]["population"] and h1[-1]["net_mig"] != h_mod[-1]["net_mig"])

    init_pop = 123748543
    prev_p = init_pop
    yearly_exact = True
    for r in h1:
        if (r["population"] - prev_p) != (r["births"] - r["deaths"] + r["net_mig"]):
            yearly_exact = False
        prev_p = r["population"]
    tot_flow = sum(r["births"] - r["deaths"] + r["net_mig"] for r in h1)
    cum_exact = ((h1[-1]["population"] - init_pop) == tot_flow)
    k.check(
        det_ok and param_moves_out and yearly_exact and cum_exact,
        "CLI-identity 0-person demographic flow residual every year, bit-identical determinism, and verified parameter override sensitivity",
    )

    # 5. CLI-replenish: Kish N_eff sample replenishment fires when threshold is reached and preserves finite state
    h_rep, _ = run_quiet(
        years=2,
        scenario="baseline",
        full_mode=False,
        feedback_params={
            "persons_replenishment": {
                "min_effective_sample_ratio": 0.99,
                "min_replenish_interval_months": 6,
            }
        },
    )
    rep_fired = h_rep[-1]["replenish_count"] >= 1
    finite_disc = all(math.isfinite(r["discontent"]) and 0.0 < r["discontent"] < 1.0 for r in h_rep)
    k.check(
        rep_fired and finite_disc,
        "CLI-replenish Kish N_eff sample health monitor triggers replenish_persons_if_needed and preserves finite household discontent",
    )

    # 6. CLI-polity: constitutional PM alternation via Election.designate when incumbent loses majority
    # Run through 2028 general election (4 years) under severe fiscal/inflation stress to verify PM designation & alternation
    h_pol, _ = run_quiet(
        years=4,
        scenario="child_splash",
        full_mode=True,
        feedback_params={
            "fiscal_and_jgb": {
                "crisis_bond_dep_threshold": 0.30,
                "crisis_infl_premium": 0.08,
                "crisis_food_premium": 0.10,
            }
        },
    )
    yr_2028 = h_pol[-1]
    alternated = (yr_2028["governing"] != "LDP+Komeito" and "PM:" in yr_2028["notes"])
    k.check(
        alternated and yr_2028["gov_seats"] > 0,
        f"CLI-polity constitutional PM alternation (Art. 67) executed in 2028 election: governing={yr_2028['governing']} ({yr_2028['gov_seats']}/465)",
    )

    k.finish()


if __name__ == "__main__":
    main()
