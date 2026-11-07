# Roadmap P1: the eleven levers no scenario used must actually move the
# world. Status-level responses are checked against each lever's declared
# spec in data/modern/jpn/levers.json (k, form, source); CLI-level checks
# cover the levers whose effects the CLI consumes (defence share flows into
# the fiscal path, call_election forces an out-of-cycle election, and a
# corporate tax act faces a real Diet vote).
#   python py/tests/test_dormant_levers.py
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import Kit  # noqa: E402  (puts py/ on the path)

import agent_env  # noqa: E402
from world.status import Status  # noqa: E402

REN = ("solar", "wind", "hydro", "bioenergy", "other_renewable")


def fresh():
    st = Status()
    err = st.load(2024, ["JPN"])
    assert not err, err
    return st


def apply(st, lid, val):
    lead = int(st.levers["JPN"]["levers"][lid]["lead_days"])
    st.set_lever("JPN", lid, val)
    for _ in range(lead + 30):
        st.step()


def ren_share(st):
    mix = st.aux["JPN"]["electricity_by_source"]
    return sum(mix[s] for s in REN)


def main():
    k = Kit("py/tests/test_dormant_levers.py")

    st = fresh()
    apply(st, "corporate_tax_rate", 0.30)
    k.check(abs(st.ind["JPN"]["tax_revenue"] - (69608.0 + 4080.0)) < 1.0,
            "P1 corporate_tax_rate 0.232->0.30 raises tax_revenue by the declared 600bn/pt (now %.0f)" % st.ind["JPN"]["tax_revenue"])

    st = fresh()
    apply(st, "defence_budget_share", 0.02)
    want = 0.02 * st.ind["JPN"]["gdp_nominal"]
    k.check(abs(st.ind["JPN"]["defence_budget"] - want) < 0.01 * want,
            "P1 defence_budget_share 0.02 sets defence_budget to 2%% of GDP (%.1f)" % st.ind["JPN"]["defence_budget"])

    st = fresh()
    apply(st, "energy_mix_target_renewables", 0.40)
    mix = st.aux["JPN"]["electricity_by_source"]
    k.check(abs(ren_share(st) - 0.40) < 1e-9 and abs(sum(mix.values()) - 1.0) < 1e-9,
            "P1 renewables target 0.40 reached exactly, mix still sums to 1 (ren=%.3f)" % ren_share(st))

    st = fresh()
    n0 = st.aux["JPN"]["electricity_by_source"]["nuclear"]
    apply(st, "nuclear_restart", 3.0)
    mix = st.aux["JPN"]["electricity_by_source"]
    k.check(abs(mix["nuclear"] - (n0 + 0.018)) < 1e-9 and abs(sum(mix.values()) - 1.0) < 1e-9,
            "P1 nuclear_restart +3 reactors adds 3x the declared 0.6pt share (%.3f)" % mix["nuclear"])

    st = fresh()
    apply(st, "semiconductor_subsidy", 3000.0)
    k.check(abs(st.ind["JPN"]["fab_capacity_share"] - 0.174) < 1e-9,
            "P1 semiconductor_subsidy 1000->3000bn raises fab share by the declared rate (%.3f)" % st.ind["JPN"]["fab_capacity_share"])

    st = fresh()
    apply(st, "fuel_subsidy", 3000.0)
    k.check(abs(st.ind["JPN"]["cpi_inflation"] - 0.023) < 1e-9,
            "P1 fuel_subsidy 3000bn lowers CPI by the declared 0.6pt (%.3f)" % st.ind["JPN"]["cpi_inflation"])

    st = fresh()
    apply(st, "oil_stock_release", 10.0)
    k.check(st.ind["JPN"]["oil_stock_days"] == 150.0,
            "P1 oil_stock_release 10 days draws the stockpile down 160->150")

    st = fresh()
    before = st.ind["JPN"]["imports_customs"]
    apply(st, "tariff_rate_general", 0.08)
    want = before * (0.08 / 0.037) ** -1.5
    k.check(abs(st.ind["JPN"]["imports_customs"] - want) < 1.0,
            "P1 tariff 3.7->8%% cuts imports by the sourced -1.5 elasticity (%.0f -> %.0f)" % (before, st.ind["JPN"]["imports_customs"]))

    st = fresh()
    apply(st, "rice_stock_release", 200.0)
    k.check(st.ind["JPN"]["rice_stockpile"] == 800.0,
            "P1 rice_stock_release 200kt draws the stockpile 1000->800")

    # CLI level: the defence share's delta is consumed by the fiscal sync,
    # so a year-end act must move the debt path against the null episode.
    def defence(obs):
        if obs["phase"] == "year_end" and obs["year"] == 2025:
            return [("defence_budget_share", 0.02)]
        return []

    base = agent_env.run_episode(agent_env.null_policy, years=10, scenario="baseline")
    def_ep = agent_env.run_episode(defence, years=10, scenario="baseline")
    # Per-year assertion (strengthened in the D-6 fix round: this
    # comment used to claim "at every year" while the code checked
    # only the endpoint). Measured cadence: the act is submitted at
    # YE2025, the share reaches 0.02 during 2026, bond dependence is
    # higher from 2026 on, and the debt STOCK is higher from 2027 on
    # (the defence delta enters the fiscal sync with a lag). The
    # Debt/GDP RATIO is still not asserted: since track G carried the
    # full FY2024 spend, the defence run's higher bond dependence
    # crosses the 45% CRISIS threshold inside this horizon (2033:
    # 45.3% vs the null run's 44.6% in 2034), the crisis inflation
    # premium inflates nominal GDP, and the ratio inverts at the
    # endpoint (254.0 -> 252.7) while the debt stock is higher
    # (1,823.5 -> 1,869.1 tn). The ratio assertion held at P1-J
    # states only because neither run crossed CRISIS within 10 years.
    b_yrs = {s["year"]: s["obs"] for s in base["steps"] if s["phase"] == "year_end"}
    d_yrs = {s["year"]: s["obs"] for s in def_ep["steps"] if s["phase"] == "year_end"}
    k.check(all(d_yrs[y]["row"]["bond_dep"] > b_yrs[y]["row"]["bond_dep"] for y in b_yrs if y >= 2026)
            and all(d_yrs[y]["indicators"]["gov_debt_total"] > b_yrs[y]["indicators"]["gov_debt_total"] for y in b_yrs if y >= 2027),
            "P1 defence act raises bond dependence every year from 2026 and the debt stock every year from 2027 (final debt %.1f -> %.1f tn)"
            % (b_yrs[2034]["indicators"]["gov_debt_total"] / 1000.0, d_yrs[2034]["indicators"]["gov_debt_total"] / 1000.0))

    # CLI level: a corporate tax act goes to a Diet vote and the outcome is
    # recorded (this engine's minority Diet rejects it; the chain is what
    # P1 wires, the politics is the engine's).
    def corp(obs):
        if obs["phase"] == "year_end" and obs["year"] == 2025:
            return [("corporate_tax_rate", 0.30)]
        return []

    corp_ep = agent_env.run_episode(corp, years=6, scenario="baseline")
    notes = " ".join(r["notes"] for r in corp_ep["history"])
    status = [r["status"] for s in corp_ep["steps"] for r in s["results"]]
    k.check(status == ["bill"] and "corporate_tax_rate" in notes,
            "P1 corporate tax act becomes a bill and the Diet's verdict is recorded")

    # CLI level: call_election forces an out-of-cycle election in full mode.
    def caller(obs):
        if obs["phase"] == "initial":
            return [("call_election", 1.0)]
        return []

    cal = agent_env.run_episode(caller, years=6, scenario="baseline", full_mode=True)
    k.check("Election Called" in cal["history"][0]["notes"] and cal["history"][0]["gov_seats"] != 215,
            "P1 call_election triggers a 2025 election (seats 215 -> %d)" % cal["history"][0]["gov_seats"])

    k.finish()


if __name__ == "__main__":
    main()
