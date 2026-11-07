# Roadmap P2 (blueprint stage S3, first counterpart): the USA profile and
# the two-way JPN-USA trade lane.
#   python py/tests/test_bilateral_usa.py
# The cross-border identity is exact: Japan's exports to the U.S. are the
# U.S.'s imports from Japan in the mirror record, before and after pulses.
# Tariff propagation follows the sourced -1.5 import demand elasticity
# (Kee, Nicita & Olarreaga 2008) on both sides.
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import Kit  # noqa: E402  (puts py/ on the path)

import agent_env  # noqa: E402
import run_simulation as RS  # noqa: E402
from world.status import Status  # noqa: E402


def fresh():
    st = Status()
    err = st.load(2024, ["JPN", "USA"])
    assert not err, err
    return st


def main():
    k = Kit("py/tests/test_bilateral_usa.py")

    st = fresh()
    lane = st.aux["JPN"]["trade_by_partner"]["USA"]
    mir = st.aux["USA"]["trade_by_partner"]["JPN"]
    k.check(st.ind["USA"]["pop_total"] > 300_000_000 and st.lever_value["USA"]["tariff_on_jpn"] == 0.0,
            "P2 USA profile loads (pop %.0f, tariff lever at baseline 0)" % st.ind["USA"]["pop_total"])
    k.check(lane["exports_bn_jpy"] == mir["imports_bn_jpy"] and lane["imports_bn_jpy"] == mir["exports_bn_jpy"],
            "P2 cross-border identity holds at load (JPN->USA %.1f bn = USA imports from JPN)" % lane["exports_bn_jpy"])

    # U.S. tariff pulse: exports fall by (1+t)^-1.5, the mirror follows,
    # exports_customs and the GDP level take the net-export impulse.
    tr = {"us_tariff_prev": 0.0, "jp_tariff_prev": 0.037,
          "last_gdp": st.ind["JPN"]["gdp_nominal"], "init_gdp": st.ind["JPN"]["gdp_nominal"]}
    exp0 = st.ind["JPN"]["exports_customs"]
    st.set_lever("USA", "tariff_on_jpn", 0.25)
    for _ in range(120):
        st.step()
    RS.sync_bilateral_trade(st, tr)
    lane = st.aux["JPN"]["trade_by_partner"]["USA"]
    mir = st.aux["USA"]["trade_by_partner"]["JPN"]
    want = 20260.2 * 1.25 ** -1.5
    k.check(abs(lane["exports_bn_jpy"] - want) < 0.5 and lane["exports_bn_jpy"] == mir["imports_bn_jpy"],
            "P2 U.S. tariff 25%% cuts JPN exports to the U.S. to %.1f bn, mirror intact" % want)
    k.check(abs((st.ind["JPN"]["exports_customs"] - exp0) - (want - 20260.2)) < 0.5 and tr["last_gdp"] < tr["init_gdp"],
            "P2 exports_customs and the GDP level absorb the impulse (GDP %.2f%%)" % ((tr["last_gdp"] / tr["init_gdp"] - 1) * 100))

    # Japanese tariff pulse: the lane follows the same elasticity form as
    # the total-imports response, and the sync does not double-count the
    # total (Status._respond already moved imports_customs).
    st2 = fresh()
    tr2 = {"us_tariff_prev": 0.0, "jp_tariff_prev": 0.037,
           "last_gdp": st2.ind["JPN"]["gdp_nominal"], "init_gdp": st2.ind["JPN"]["gdp_nominal"]}
    st2.set_lever("JPN", "tariff_rate_general", 0.08)
    for _ in range(200):
        st2.step()
    total_after_respond = st2.ind["JPN"]["imports_customs"]
    RS.sync_bilateral_trade(st2, tr2)
    lane2 = st2.aux["JPN"]["trade_by_partner"]["USA"]
    want2 = 11555.4 * (0.08 / 0.037) ** -1.5
    k.check(abs(lane2["imports_bn_jpy"] - want2) < 0.5 and st2.ind["JPN"]["imports_customs"] == total_after_respond,
            "P2 JPN tariff 8%% cuts imports from the U.S. to %.1f bn, no double count in the total" % want2)

    # CLI level: a U.S. tariff shock (set by the policy as a foreign act)
    # raises Japan's debt ratio against the null episode, through the
    # export -> GDP level -> fiscal path.
    def shock(obs):
        if obs["phase"] == "initial":
            return [("USA:tariff_on_jpn", 0.25)]
        return []

    base = agent_env.run_episode(agent_env.null_policy, years=10, scenario="baseline")
    ep = agent_env.run_episode(shock, years=10, scenario="baseline")
    res = [r for s in ep["steps"] for r in s["results"]]
    k.check(bool(res) and res[0]["status"] == "executed"
            and ep["final"]["debt_gdp"] > base["final"]["debt_gdp"]
            and "counterpart" in ep["steps"][0]["obs"],
            "P2 agent-set U.S. tariff raises final Debt/GDP (%.1f -> %.1f) and the counterpart is observable"
            % (base["final"]["debt_gdp"], ep["final"]["debt_gdp"]))

    k.finish()


if __name__ == "__main__":
    main()
