# Roadmap P2.5 (axis H): the central bank, connected.
#   python py/tests/test_central_bank.py
# EconMonth's Bank always had a policy rate (a published path, then a
# Taylor-type rule) - but it reached nothing outside EconMonth: the
# Status policy_rate indicator sat at its 2024 value forever, JGB
# yields were priced off fiscal variables only, and the yen never
# moved. The bridges added here publish the Bank's rate monthly and
# transmit it: into the JGB target (pass 0.6), into the inflation the
# demographic/fiscal layer sees (stance above a 1% neutral trims CPI),
# and into USD/JPY via the rate differential. This is a deliberate
# model change - the ablation at the end pins it: with both
# pass-throughs zeroed the run reproduces the pre-P2.5 trajectory.
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import Kit  # noqa: E402  (puts py/ on the path)

import agent_env  # noqa: E402
import run_simulation as RS  # noqa: E402


def main():
    k = Kit("py/tests/test_central_bank.py")

    ep = agent_env.run_episode(agent_env.null_policy, years=10, scenario="baseline")
    ye = {s["year"]: s for s in ep["steps"] if s["phase"] == "year_end"}
    r25 = ye[2025]["obs"]["indicators"]["policy_rate"]
    r27 = ye[2027]["obs"]["indicators"]["policy_rate"]
    r28 = ye[2028]["obs"]["indicators"]["policy_rate"]
    k.check(0.008 < r25 < 0.013 and r27 > 0.018,
            "H the Bank's rate is published and climbs the Taylor path (2025 %.3f -> 2027 %.3f)" % (r25, r27))
    k.check(r28 < r27,
            "H the rule reacts, not ratchets: the rate eases when its inflation cools (2028 %.3f)" % r28)
    fx25 = ye[2025]["obs"]["indicators"]["fx_jpy_usd"]
    fx27 = ye[2027]["obs"]["indicators"]["fx_jpy_usd"]
    k.check(fx27 < fx25 < 151.61,
            "H the yen strengthens as the differential narrows (%.1f -> %.1f)" % (fx25, fx27))
    k.check(abs(ye[2030]["obs"]["row"]["policy_rate"] - ye[2030]["obs"]["indicators"]["policy_rate"] * 100) < 0.01,
            "H the year row carries the same policy rate as the indicator")

    saved = (RS.JGB_POLICY_PASS, RS.MONETARY_CPI_PASS)
    RS.JGB_POLICY_PASS = 0.0
    RS.MONETARY_CPI_PASS = 0.0
    try:
        ab = agent_env.run_episode(agent_env.null_policy, years=10, scenario="baseline")
    finally:
        RS.JGB_POLICY_PASS, RS.MONETARY_CPI_PASS = saved
    k.check(ep["final"]["debt_gdp"] > ab["final"]["debt_gdp"] + 1.0,
            "H transmission bites: live monetary bridges raise 10y Debt/GDP (%.1f vs ablated %.1f)"
            % (ep["final"]["debt_gdp"], ab["final"]["debt_gdp"]))
    k.check(ab["final"]["population"] > ep["final"]["population"],
            "H ablation sanity: with the bridges off, the pre-P2.5 trajectory returns (pop %d > %d)"
            % (ab["final"]["population"], ep["final"]["population"]))

    k.finish()


if __name__ == "__main__":
    main()
