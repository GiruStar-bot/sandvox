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

    def semi_policy(obs):
        if obs["phase"] == "initial":
            return [("semiconductor_subsidy", 5000.0)]
        return []

    # The subsidy costs ~4 tn JPY/yr up front; its growth dividend
    # compounds and overtakes the cost only over long horizons (at
    # 12y debt is still higher: 262.3 vs 258.9 - measured, kept as
    # the honest short-run sign in this comment).
    sp = agent_env.run_episode(semi_policy, years=25, scenario="baseline")
    bn = agent_env.run_episode(agent_env.null_policy, years=12, scenario="baseline")
    k.check(sp["steps"][-1]["obs"]["row"]["capital_tn"] > ye[2049]["obs"]["row"]["capital_tn"]
            and sp["final"]["debt_gdp"] < b["final"]["debt_gdp"],
            "I semiconductor subsidy builds capital and, by 2049, pays for part of itself (debt %.1f vs %.1f)"
            % (sp["final"]["debt_gdp"], b["final"]["debt_gdp"]))

    saved = RS.GROWTH_ENGINE
    RS.GROWTH_ENGINE = False
    try:
        ab = agent_env.run_episode(agent_env.null_policy, years=12, scenario="baseline")
    finally:
        RS.GROWTH_ENGINE = saved
    ab_g = [x for x in ab["steps"] if x["phase"] == "year_end"][-1]["obs"]["row"]["real_growth"]
    k.check(ab_g == 1.7 and ab["final"]["debt_gdp"] < bn["final"]["debt_gdp"],
            "I ablation: engine off restores the frozen 1.7%% print and the pre-axis-I trajectory (debt %.1f < %.1f)"
            % (ab["final"]["debt_gdp"], bn["final"]["debt_gdp"]))

    k.finish()


if __name__ == "__main__":
    main()
