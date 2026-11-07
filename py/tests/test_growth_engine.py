# Roadmap axis I: the long-run growth engine.
#   python py/tests/test_growth_engine.py
# Real growth used to be the initial print - 2023's +1.7%, one strong
# year - frozen for every horizon. The engine replaces it with
# potential growth from capital accumulation and TFP: investment is
# deflated to constant prices, the capital stock accumulates, and the
# Solow term is capital deepening per worker (the labour-force level
# still scales GDP separately). Public investment keeps its sourced
# first-year demand multiplier and now also builds capital; the
# semiconductor subsidy invests and lifts TFP through fab share.
# GROWTH_ENGINE=False restores the legacy frozen print exactly.
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import Kit  # noqa: E402  (puts py/ on the path)

import agent_env  # noqa: E402
import run_simulation as RS  # noqa: E402


def main():
    k = Kit("py/tests/test_growth_engine.py")

    b = agent_env.run_episode(agent_env.null_policy, years=25, scenario="baseline")
    ye = {s["year"]: s for s in b["steps"] if s["phase"] == "year_end"}
    g25, g49 = ye[2025]["obs"]["row"]["real_growth"], ye[2049]["obs"]["row"]["real_growth"]
    k.check(0.5 < g25 < 1.2 and 0.4 < g49 < 1.2,
            "I potential growth is endogenous and plausible (2025 %.2f%%, 2049 %.2f%%, not the frozen 1.7%%)" % (g25, g49))
    k.check(ye[2049]["obs"]["row"]["capital_tn"] > ye[2025]["obs"]["row"]["capital_tn"] + 150.0,
            "I the capital stock accumulates in constant prices (%.0f -> %.0f tn JPY)"
            % (ye[2025]["obs"]["row"]["capital_tn"], ye[2049]["obs"]["row"]["capital_tn"]))

    s = agent_env.run_episode(agent_env.null_policy, years=25, scenario="child_splash")
    yes = {x["year"]: x for x in s["steps"] if x["phase"] == "year_end"}
    k.check(yes[2025]["obs"]["row"]["real_growth"] > g25 + 1.0
            and yes[2049]["obs"]["row"]["capital_tn"] > ye[2049]["obs"]["row"]["capital_tn"],
            "I public investment: year-1 demand boost (%.2f%%) and a larger capital stock by 2049 (%.0f tn)"
            % (yes[2025]["obs"]["row"]["real_growth"], yes[2049]["obs"]["row"]["capital_tn"]))

    # The subsidy as a preset condition (+4 tn JPY/yr from 2025).
    # CORRECTED CLAIM (independent review D-1, fix round): the
    # axis-I-era text here said the subsidy "costs ~4 tn up front"
    # and cited 262.3 vs 258.9 at 12y as the honest short-run sign.
    # Both were wrong - the subsidy's delta never entered government
    # expenditure (it was fiscally free), and the 12y ratio gap was a
    # crisis-threshold denominator artifact (the subsidy run's debt
    # STOCK was the lower one). With the cost wired into expenditure,
    # the measured truth at this calibration is the sterner one:
    # bond dependence is higher at both horizons, capital is higher
    # by 2049 (2,261 vs 2,216 tn), and the Debt/GDP ratio is HIGHER
    # by 2049 (341.8 vs 334.0) - the growth dividend does not pay for
    # the subsidy inside 25 years. (The 12y ratio reads lower, 254.8
    # vs 260.4, only because the subsidy run crosses the 45% CRISIS
    # threshold in 2033 instead of 2035 and the crisis inflation
    # premium inflates its denominator; its bond dependence, 50.1 vs
    # 47.8, shows the real pressure.)
    import contextlib
    import io
    with contextlib.redirect_stdout(io.StringIO()):
        sp = RS.run_simulation(years=25, custom_levers=[("semiconductor_subsidy", 5000.0)])
        sp12 = RS.run_simulation(years=12, custom_levers=[("semiconductor_subsidy", 5000.0)])
        bn12 = RS.run_simulation(years=12, scenario="baseline")
    bn = agent_env.run_episode(agent_env.null_policy, years=12, scenario="baseline")
    k.check(sp[-1]["capital_tn"] > ye[2049]["obs"]["row"]["capital_tn"]
            and sp[-1]["bond_dep"] > b["final"]["bond_dep"]
            and sp[-1]["debt_gdp"] > b["final"]["debt_gdp"],
            "I semiconductor subsidy (cost wired): builds capital (%.0f tn) but raises bond dependence and the 2049 Debt/GDP ratio (%.1f vs %.1f)"
            % (sp[-1]["capital_tn"], sp[-1]["debt_gdp"], b["final"]["debt_gdp"]))
    k.check(sp12[-1]["bond_dep"] > bn12[-1]["bond_dep"],
            "I subsidy at 12y: bond dependence is higher (%.1f vs %.1f) even though the ratio reads lower on crisis timing"
            % (sp12[-1]["bond_dep"], bn12[-1]["bond_dep"]))

    saved = RS.GROWTH_ENGINE
    saved_lat = RS.LAT_STRESS_PASS
    RS.GROWTH_ENGINE = False
    try:
        ab = agent_env.run_episode(agent_env.null_policy, years=12, scenario="baseline")
    finally:
        RS.GROWTH_ENGINE = saved
    ab_g = [x for x in ab["steps"] if x["phase"] == "year_end"][-1]["obs"]["row"]["real_growth"]
    k.check(ab_g == 1.7 and ab["final"]["debt_gdp"] < bn["final"]["debt_gdp"],
            "I ablation: engine off restores the frozen 1.7%% print and the pre-axis-I trajectory (debt %.1f < %.1f)"
            % (ab["final"]["debt_gdp"], bn["final"]["debt_gdp"]))
    # Snapshot assertion (strengthened in the D-6 fix round: composed
    # ablations used to be checked by inequality only). Engine off +
    # LAT pass 0 reproduces the composed snapshot at the current head
    # exactly. The remaining +0.2pt against the pre-track-G 256.0 is
    # track G's unitemized budget line - a data change no switch
    # reverses (verified digit-for-digit by the independent review).
    RS.GROWTH_ENGINE = False
    RS.LAT_STRESS_PASS = 0.0
    try:
        ab25 = agent_env.run_episode(agent_env.null_policy, years=25, scenario="baseline")
    finally:
        RS.GROWTH_ENGINE = saved
        RS.LAT_STRESS_PASS = saved_lat
    k.check(ab25["final"]["population"] == 100762891 and abs(ab25["final"]["debt_gdp"] - 256.2) < 0.05,
            "I ablation chain snapshot: engine off + LAT 0 reproduces the composed state exactly (pop %d, debt %.1f)"
            % (ab25["final"]["population"], ab25["final"]["debt_gdp"]))

    k.finish()


if __name__ == "__main__":
    main()
