# Roadmap P5 (blueprint stage S3): China and EU counterparts, the export-
# control licence, and migration by origin.
#   python py/tests/test_counterparts_chn_eu.py
# - CHN and EU profiles load alongside JPN/USA; their tariffs move the
#   matching customs lane by the same -1.5 elasticity as the USA lane,
#   with the mirror identity exact, and foreign acts work for any
#   counterpart via the CODE: prefix.
# - export_control (the licence form deferred in P1) now bites: full
#   denial removes the declared controlled share (12%) of exports to
#   China, and releasing it restores the lane exactly.
# - Net migration is decomposed by origin: the structural part follows
#   the ISA resident-stock shares, the SSW-driven part is attributed to
#   the SSW-sending origins, so the visa lever moves the composition.
#   The parts sum exactly to net_migration.
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import Kit  # noqa: E402  (puts py/ on the path)

import agent_env  # noqa: E402
from world.status import Status  # noqa: E402


def main():
    k = Kit("py/tests/test_counterparts_chn_eu.py")

    st = Status()
    err = st.load(2024, ["JPN", "USA", "CHN", "EU"])
    k.check(not err and st.ind["CHN"]["pop_total"] == 1408280000.0 and st.ind["EU"]["pop_total"] == 450400000.0,
            "P5 CHN (NBS 1,408.28M) and EU (Eurostat ~450.4M) profiles load")

    lane0 = st.aux["JPN"]["trade_by_partner"]["CHINA"]["exports_bn_jpy"]
    st.set_lever("JPN", "export_control", 1.0)
    for _ in range(5):
        st.step()
    lane1 = st.aux["JPN"]["trade_by_partner"]["CHINA"]["exports_bn_jpy"]
    st.set_lever("JPN", "export_control", 0.0)
    for _ in range(5):
        st.step()
    lane2 = st.aux["JPN"]["trade_by_partner"]["CHINA"]["exports_bn_jpy"]
    k.check(abs(lane1 - lane0 * 0.88) < 0.5 and abs(lane2 - lane0) < 0.5,
            "P5 export_control: full denial cuts the CHINA lane 12%% (%.0f -> %.0f) and release restores it" % (lane0, lane1))

    c = agent_env.run_episode(agent_env.null_policy, years=6, scenario="baseline", chn_tariff=0.25)
    obs = c["steps"][-1]["obs"]
    lane = obs["trade_by_partner"]["CHINA"]["exports_bn_jpy"]
    mir = obs["counterpart"]["CHN"]["trade_by_partner"]["JPN"]["imports_bn_jpy"]
    k.check(abs(lane - 17763.9 * (1.25 ** -1.5)) < 2.0 and lane == mir,
            "P5 CHN tariff 25%%: lane exports fall to %.0f bn, mirror identity holds" % lane)

    e = agent_env.run_episode(agent_env.null_policy, years=6, scenario="baseline", eu_tariff=0.25)
    obse = e["steps"][-1]["obs"]
    lane_e = obse["trade_by_partner"]["EU"]["exports_bn_jpy"]
    mir_e = obse["counterpart"]["EU"]["trade_by_partner"]["JPN"]["imports_bn_jpy"]
    k.check(abs(lane_e - 11900.0 * (1.25 ** -1.5)) < 2.0 and lane_e == mir_e and "EU" in obse["counterpart"],
            "P5 EU tariff 25%%: the runtime EU lane falls to %.0f bn, mirror identity holds" % lane_e)

    def foreign_policy(obs):
        if obs["phase"] == "initial":
            return [("CHN:tariff_on_jpn", 0.10), ("EU:tariff_on_jpn", 0.10)]
        return []

    fp = agent_env.run_episode(foreign_policy, years=4, scenario="baseline")
    res = fp["steps"][0]["results"]
    k.check(all(r["status"] == "executed" for r in res)
            and fp["steps"][-1]["obs"]["trade_by_partner"]["CHINA"]["exports_bn_jpy"] < 17763.9,
            "P5 foreign acts CHN:/EU: execute directly and move their lanes")

    n = agent_env.run_episode(agent_env.null_policy, years=6, scenario="baseline")
    obn = n["steps"][-1]["obs"]
    mo = obn["migration_by_origin"]
    tot = sum(v["annual_flow"] for v in mo.values())
    k.check(abs(tot - obn["indicators"]["net_migration"]) < 1.0 and abs(mo["VNM"]["annual_flow"] / tot - 0.167) < 0.01,
            "P5 origin flows sum to net migration (%.0f); VNM follows its resident share at rest" % tot)

    s = agent_env.run_episode(agent_env.null_policy, years=6, scenario="synergy")
    mos = s["steps"][-1]["obs"]["migration_by_origin"]
    tots = sum(v["annual_flow"] for v in mos.values())
    ssw = lambda m, t: sum(m[o]["annual_flow"] for o in ("VNM", "PHL", "IDN", "NPL")) / t  # noqa: E731
    k.check(ssw(mos, tots) > ssw(mo, tot) + 0.15,
            "P5 the SSW visa expansion shifts the origin composition (SSW share %.3f -> %.3f)" % (ssw(mo, tot), ssw(mos, tots)))

    r = agent_env.run_episode(agent_env.null_policy, years=6, scenario="baseline",
                              shocks=[{"kind": "foreign_recession", "partner": "CHN", "start": [2026, 7], "months": 12, "mag": 25.0}])
    k.check(abs(r["steps"][2]["obs"]["trade_by_partner"]["CHINA"]["exports_bn_jpy"] - 17763.9 * 0.75) < 1.0,
            "P5 foreign_recession now takes a partner: the CHINA lane falls 25% in a Chinese recession")

    k.finish()


if __name__ == "__main__":
    main()
