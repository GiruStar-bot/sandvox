# Roadmap P6: distribution channels and a replenishment that fires.
#   python py/tests/test_distribution_replenish.py
# The Issue-C replenishment was dead code in every default run: its
# trigger (panel n below 60% of initial) can never fire because the
# household layer is self-renewing and n is structurally constant
# (n=94 measured over 100 years). The redesigned trigger fires on the
# n condition OR a 10-year re-anchoring cadence, and the distribution
# channel connects the household layer to approval: the worst-decile
# economic-security deficit, re-anchored at each panel refresh so the
# channel measures within-panel deterioration, not resample jumps.
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import Kit  # noqa: E402  (puts py/ on the path)

import agent_env  # noqa: E402


def main():
    k = Kit("py/tests/test_distribution_replenish.py")

    ep = agent_env.run_episode(agent_env.null_policy, years=25, scenario="baseline")
    ye = {s["year"]: s for s in ep["steps"] if s["phase"] == "year_end"}
    k.check(ye[2034]["obs"]["row"]["replenishments"] == 0 and ye[2035]["obs"]["row"]["replenishments"] == 1
            and ye[2049]["obs"]["row"]["replenishments"] == 2,
            "P6 replenishment fires on the 10y cadence (2035, 2045); counter reaches 2 by 2049")
    k.check(ye[2035]["obs"]["row"]["approval"] > 30.0,
            "P6 the resample does not crater approval (re-anchored reference): 2035 approval %.1f"
            % ye[2035]["obs"]["row"]["approval"])
    d = ye[2049]["obs"]["distribution"]
    k.check(0.0 <= d["deficit_p90"] <= 1.0 and d["discontent_p90"] > d["discontent_p10"],
            "P6 the distribution surface is observable (deficit p90 %.3f, discontent spread %.3f)"
            % (d["deficit_p90"], d["discontent_p90"] - d["discontent_p10"]))

    n = agent_env.run_episode(agent_env.null_policy, years=6, scenario="baseline")
    f = agent_env.run_episode(agent_env.null_policy, years=6, scenario="baseline",
                              shocks=[{"kind": "food_price", "start": [2026, 1], "months": 12, "mag": 30.0}])
    dn, df = n["steps"][2]["obs"]["distribution"], f["steps"][2]["obs"]["distribution"]
    k.check(df["deficit_p90"] > dn["deficit_p90"] and f["history"][1]["approval"] < n["history"][1]["approval"],
            "P6 distribution worsens -> approval falls: deficit p90 %.3f -> %.3f, approval %.1f -> %.1f"
            % (dn["deficit_p90"], df["deficit_p90"], n["history"][1]["approval"], f["history"][1]["approval"]))

    k.finish()


if __name__ == "__main__":
    main()
