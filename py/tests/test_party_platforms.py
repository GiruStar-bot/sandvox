# Roadmap axis K: party platform differentiation.
#   python py/tests/test_party_platforms.py
# Parties had sourced vote shares and a seat engine but no platforms,
# and org.governing never changed hands - an election could not
# change what the government does. Now each governing-capable party
# carries a declared platform (data/modern/polity/jpn_platforms.json),
# the election winner forms a government by the declared coalition
# order, and its merged platform enters the existing enactment loop
# (majority: full; minority: halfway compromise). Vote shares also
# answer to electorate composition (aging / Kanto-share tilts).
# Found and fixed on the way: the first election ignored approval
# entirely - pub.change_since(0) always returned 0.0 because the
# approval history starts at month 1, so a popularity collapse and a
# popular government produced identical seats.
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import Kit  # noqa: E402  (puts py/ on the path)

import agent_env  # noqa: E402
import run_simulation as RS  # noqa: E402


def main():
    k = Kit("py/tests/test_party_platforms.py")

    plat = RS._load_platforms()
    bloc, agenda = RS._form_government(
        {"LDP": 200, "Komeito": 30, "CDP": 150, "Ishin": 40, "DPFP": 30, "Reiwa": 15}, plat)
    k.check(bloc == ["LDP", "Komeito"] and agenda["child_allowance"] == 2500.0,
            "K formation: largest party leads, junior joins, senior partner wins lever conflicts (%s)" % "+".join(bloc))
    bloc2, agenda2 = RS._form_government(
        {"LDP": 120, "Komeito": 20, "CDP": 170, "Ishin": 40, "DPFP": 60, "Reiwa": 55}, plat)
    k.check(bloc2 == ["CDP", "DPFP", "Reiwa"] and agenda2["consumption_tax_rate"] == 0.05,
            "K formation: an opposition plurality builds its declared coalition (%s)" % "+".join(bloc2))

    b = agent_env.run_episode(agent_env.null_policy, years=7, scenario="baseline", full_mode=True)
    el = b["steps"][-1]["obs"]["election"]
    lv = b["steps"][-1]["obs"]["levers"]
    k.check(el.get("government") == "LDP+Komeito" and el.get("majority") is True
            and abs(lv["defence_budget_share"] - 0.02) < 1e-6 and lv["semiconductor_subsidy"] == 3000.0,
            "K incumbents re-elected: their platform is enacted (defence share %.3f, semiconductor subsidy %.0f)"
            % (lv["defence_budget_share"], lv["semiconductor_subsidy"]))

    shock = [{"kind": "food_price", "start": [2026, 3], "months": 30, "mag": 30.0}]
    s = agent_env.run_episode(agent_env.null_policy, years=7, scenario="baseline", full_mode=True, shocks=shock)
    el2 = s["steps"][-1]["obs"]["election"]
    lv2 = s["steps"][-1]["obs"]["levers"]
    # Note: the new government's consumption-tax cut was REJECTED by
    # the Diet's fiscal procedure in the stressed post-shock state,
    # while its spending and regulatory items passed - platforms
    # propose, the existing bill path disposes.
    k.check(el2.get("government") == "CDP+DPFP+Reiwa"
            and abs(lv2["energy_mix_target_renewables"] - 0.40) < 1e-6 and lv2["child_allowance"] == 6000.0,
            "K a popularity collapse changes the government AND its policies (gov %s, renewables %.2f, child allowance %.0f)"
            % (el2.get("government"), lv2["energy_mix_target_renewables"], lv2["child_allowance"]))

    std = agent_env.run_episode(agent_env.null_policy, years=3, scenario="baseline")
    k.check(std["steps"][-1]["obs"]["election"] == {},
            "K standard mode runs no elections (platforms stay inert data)")

    k.finish()


if __name__ == "__main__":
    main()
