# Roadmap P4 (blueprint stage S4): the deterministic shock library.
#   python py/tests/test_shocks.py
# A schedule is data; the same schedule reproduces the same episode
# exactly. Transmissions are checked for sign and size against the
# declared constants, and the no-shock baseline is untouched (its
# invariance is pinned by test_agent_env's printed-table check).
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import Kit  # noqa: E402  (puts py/ on the path)

import agent_env  # noqa: E402


def ep(schedule=None, years=6):
    return agent_env.run_episode(agent_env.null_policy, years=years, scenario="baseline", shocks=schedule)


def main():
    k = Kit("py/tests/test_shocks.py")
    null = ep()

    sched = [{"kind": "energy_price", "start": [2026, 3], "months": 12, "mag": 50.0}]
    e1, e2 = ep(sched), ep(sched)
    k.check(e1["history"] == e2["history"],
            "P4 the same schedule reproduces the identical episode")
    obs = e1["steps"][2]["obs"]  # year-end 2026, inside the window
    k.check("Shock energy_price" in e1["history"][1]["notes"]
            and abs(obs["indicators"]["cpi_inflation"] - (null["steps"][2]["obs"]["indicators"]["cpi_inflation"] + 0.0075)) < 0.002
            and obs["indicators"]["imports_customs"] > null["steps"][2]["obs"]["indicators"]["imports_customs"] + 10000.0
            and obs["shocks_active"] and obs["shocks_active"][0]["kind"] == "energy_price",
            "P4 energy +50%%: CPI +0.75pt and the import bill up while active (CPI %.4f, imports %.0f)"
            % (obs["indicators"]["cpi_inflation"], obs["indicators"]["imports_customs"]))

    f = ep([{"kind": "food_price", "start": [2026, 1], "months": 12, "mag": 30.0}])
    k.check(f["history"][1]["discontent"] > null["history"][1]["discontent"] + 0.2
            and f["history"][1]["approval"] < null["history"][1]["approval"],
            "P4 food +30%%: discontent jumps (%.3f -> %.3f) and approval falls"
            % (null["history"][1]["discontent"], f["history"][1]["discontent"]))

    d = ep([{"kind": "disaster", "start": [2027, 6], "months": 12, "mag": 2.0}])
    k.check("Shock disaster" in d["history"][2]["notes"] and d["final"]["debt_gdp"] > null["final"]["debt_gdp"] + 2.0,
            "P4 disaster 2%% of GDP: final Debt/GDP rises (%.1f -> %.1f)"
            % (null["final"]["debt_gdp"], d["final"]["debt_gdp"]))

    r = ep([{"kind": "foreign_recession", "start": [2026, 7], "months": 12, "mag": 25.0}])
    lane = r["steps"][2]["obs"]["trade_by_partner"]["USA"]
    mir = r["steps"][2]["obs"]["counterpart"]["USA"]["trade_by_partner"]["JPN"]
    k.check(abs(lane["exports_bn_jpy"] - 20260.2 * 0.75) < 1.0 and lane["exports_bn_jpy"] == mir["imports_bn_jpy"],
            "P4 foreign recession: exports to the U.S. fall 25%% to %.0f bn, mirror identity holds" % lane["exports_bn_jpy"])

    p = ep([{"kind": "pandemic", "start": [2026, 1], "months": 12, "mag": 3.0, "hazard_x": 0.5, "mig_scale": 0.2}])
    k.check(p["history"][1]["deaths"] > null["history"][1]["deaths"] * 1.3
            and p["history"][1]["net_mig"] < null["history"][1]["net_mig"] * 0.4,
            "P4 pandemic: deaths rise (%d -> %d) and net migration collapses under border closure"
            % (null["history"][1]["deaths"], p["history"][1]["deaths"]))

    s1 = agent_env.random_shock_schedule(7, years=10)
    s2 = agent_env.random_shock_schedule(7, years=10)
    s3 = agent_env.random_shock_schedule(8, years=10)
    k.check(s1 == s2 and s1 != s3 and all(x["kind"] in ("energy_price", "food_price", "disaster", "foreign_recession", "pandemic") for x in s1),
            "P4 seeded library: same seed, same schedule; different seed, different schedule (%d events)" % len(s1))

    k.finish()


if __name__ == "__main__":
    main()
