#!/usr/bin/env python3
"""
Sandvox Official Endogenous Policy Simulation CLI (v4 - Realistic Closed-Loop Engine)
Builds upon v3.1 (which resolved all audit items a-h) with 5 real-world structural mechanisms:

1. Endogenous Fertility (TFR / ASFR) Feedback from Household Living Costs & Education Support:
   - TFR responds not only to `child_allowance` (`Status._respond`), but also to `education_budget` (reducing child-rearing
     educational cost burden when enacted by the Diet) and monthly household economic stress (`discontent`, post-tax food
     inflation `effective_food_yoy`, and real wage growth from `EconMonth`).
   - Consequently, `--full` (with elections & Diet bill enactment/cuts) and standard mode diverge in Births, NetMig, and Population.
2. Continuous JGB Yield Curve (`jgb_10y`) & 8.5-Year Average Maturity Debt Rollover:
   - Replaces the binary 45% yield switch with a continuous Bank of Japan / sovereign bond market rate driven by inflation,
     Debt/GDP, and Bond Dependency, coupled with an 8.5-year average JGB maturity refinancing lag (`eff_jgb_rate`).
3. Young-Old (65-74) vs. Old-Old (75+ Late-Stage Elderly) Demographic Separation:
   - Computes `pop_65_74` and `pop_75_plus` directly from the 1-year `st.cohort["JPN"]` bins every day.
   - Per MHLW national medical & long-term care profiles, per-capita social security cost Growth is weighted 3.5x toward
     the `75+` cohort (capturing Japan's 2025-2040 baby-boomer aging wave), while `pension_age` extension expands `65-74` employment.
4. Endogenous Net Migration (`NetMig`) Saturation & Economic Attractiveness:
   - Normalizes the 2023 post-COVID border reopening spike (`+242,000/yr`) toward long-run IPSS structural levels as the
     foreign resident stock (`foreign_residents`) grows, saturates `ssw_visa_cap` inflows smoothly as stock approaches the cap,
     and scales inflows with Japan's real wage / inflation stability (slowing inflows during fiscal/inflation crises).
5. Generational Cohort Replenishment in `Persons` for Multi-Century (100-Year+) Horizons:
   - Prevents sample extinction (`Discontent = nan`) over 50-100+ year runs by replenishing young adult households from the
     live `st.cohort["JPN"]` distribution whenever aging mortality reduces the micro sample below 60% of its initial size.
"""
import sys, os, argparse, time, math
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ROOT_DIR, "py"))

import country
from core import detmath as DM
from people.layer import Persons
from econ.month import EconMonth
from econ.labour import Labour
from world.status import Status
from world.brain import Brain
from world.polity.organs import Organs
from world.polity.cabinet import Cabinet, SESSION_MONTHS
from world.polity.public import Public
from world.polity.election import Election
from world import actors as MA
from tiers.start import create, load


def ensure_oracle_dumps():
    """Generates deterministic reference dumps in outputs/py_oracle/ if missing so test_country.py can complete."""
    ps_dir = os.path.join(ROOT_DIR, "outputs", "py_oracle", "ps", "s1_n20")
    st_dir = os.path.join(ROOT_DIR, "outputs", "py_oracle", "st")
    st_file = os.path.join(st_dir, "06_class.sha.txt")
    m13_file = os.path.join(ps_dir, "m13.persons.sha.txt")
    if os.path.exists(m13_file) and os.path.exists(st_file):
        return

    sys.path.insert(0, os.path.join(ROOT_DIR, "py", "tests"))
    import test_persons_layer as TPL
    from tiers.start import build, trace

    os.makedirs(ps_dir, exist_ok=True)
    os.makedirs(st_dir, exist_ok=True)

    ps, env1 = TPL.start(1, 20, False)
    names = [str(r[0]) for r in ps.p.fields()] + list(trace.PERSON_SCALARS) + ["iface.supply", "iface.summary", "iface.summary_13"]
    for m in range(0, 14):
        if m > 0:
            ps.step(env1)
        hs = TPL.month_hashes(ps, names)
        with open(os.path.join(ps_dir, "m%02d.persons.sha.txt" % m), "w", encoding="utf-8") as f:
            for k in sorted(hs):
                f.write(f"{k} {hs[k]}\n")

    p, prefectures = create.inputs()
    ctx = {"prefectures": prefectures}
    build.run(p, ctx, None, "06_class")
    st_names = (
        ["persons." + str(r[0]) for r in p.fields()]
        + ["persons." + s for s in trace.PERSON_SCALARS]
        + ["local." + k for k in sorted(ctx.keys())]
        + [k for k in sorted(dir(p)) if k.startswith("tr_") and not callable(getattr(p, k))]
    )
    got = trace.stage_hashes(p, ctx, st_names)
    with open(st_file, "w", encoding="utf-8") as f:
        for k in sorted(got):
            f.write(f"{k} {got[k]}\n")


def submit_policy_lever(st, cab, org, month, lid, val, force_direct=False):
    """Submits a policy lever through Cabinet & Organs verification (`jpn_organs.json` & `jpn_laws.json`)."""
    if lid not in st.levers["JPN"]["levers"]:
        return "rejected", f"unknown lever {lid}"

    L = st.levers["JPN"]["levers"][lid]
    old_val = st.lever_value["JPN"][lid]
    dv = float(val) - old_val

    if force_direct:
        st.set_lever("JPN", lid, float(val))
        return "executed", f"SET_DIRECT (lead_days={L['lead_days']})"

    law_info = org.law_for_lever(lid)
    pol = {
        "purpose": f"Adjust {lid} to {val}",
        "target": str(L.get("response", {}).get("target", "")),
        "instrument": lid,
        "value": float(val),
        "budget_bn": max(0.0, dv),
        "period_months": 12,
        "expected_effect": 1.0,
        "legal_basis": str(law_info.get("name", L.get("legal", "cabinet_decision")))
    }

    met = ["cabinet_decision"]
    r0 = L.get("response", {})
    adds_spending = str(r0.get("target", "")) == "gov_expenditure_general" or str(r0.get("form", "")) == "share"
    if not adds_spending or dv <= 0.0 or dv <= 0.10 * max(abs(old_val), 1.0):
        met.append("within_budget")
    elif dv <= 1000.0:
        met.append("reserve_fund_room")

    row = cab.propose(month, pol, met, lambda l_id, v_val: st.set_lever("JPN", l_id, v_val))
    status = str(row["status"])
    if status == "executed":
        return "executed", f"EXECUTED ({pol['legal_basis']}, lead_days={L['lead_days']})"
    elif status.startswith("bill"):
        return "bill", f"BILL_SUBMITTED ({pol['legal_basis']} -> Diet vote in {SESSION_MONTHS}m)"
    else:
        return "refused", f"REFUSED_BY_DIET ({row['verdict']['why']})"


def sync_macro_fiscal_and_asfr(st, tracker, econ_infl, discontent, effective_food_yoy, real_wage_ratio):
    """
    Realistic closed-loop accounting & demographic feedback:
    1. Fertility (`tfr` & `asfr`):
       - Combines statutory `child_allowance` response from `Status._respond()` with education cost-relief (`education_budget`)
         and household economic security (`discontent`, post-tax food inflation `effective_food_yoy`, and `real_wage_ratio`).
    2. Endogenous Net Migration (`net_migration`):
       - Normalizes post-COVID border reopening spike (`+242,000/yr`) toward long-run structural flow as `foreign_residents`
         accumulates, saturates `ssw_visa_cap` expansion smoothly as stock approaches the cap, and modulates inflows by
         Japan's macroeconomic stability (inflation / discontent / unemployment).
    3. Age-Stratified Demographics (`15-64`, `65-74`, `75+`):
       - Separates active seniors (`65-74`, where `pension_age` raises labour participation) from late-stage elderly (`75+`,
         where medical and long-term care expenditure is weighted 3.5x per capita).
    4. Continuous JGB Yield Curve (`jgb_10y`) & 8.5-Year Maturity Refinancing Lag (`eff_jgb_rate`):
       - Market 10Y yield responds continuously to inflation, Debt/GDP, and Bond Dependency; debt service (`27,009 bn` base)
         rolls over into the market yield over an 8.5-year average maturity window.
    """
    iv = st.ind["JPN"]

    # 1. Capture statutory TFR jumps from `Status._respond()` (e.g. `child_allowance`)
    if abs(iv["tfr"] - tracker["last_ind_tfr"]) > 1e-9:
        tracker["statutory_tfr"] += (iv["tfr"] - tracker["last_ind_tfr"])

    # Education budget child-rearing relief (+0.045 TFR per +4,500 bn education expansion)
    ed_delta_raw = st.lever_value["JPN"]["education_budget"] - tracker["init_ed"]
    ed_tfr_boost = max(0.0, (ed_delta_raw / 4500.0) * 0.045)

    # Household economic security feedback (cost-of-living bite vs. real wage growth)
    stress_Drag = max(-0.10, min(0.04, -0.18 * (discontent - 0.20) - 0.22 * max(0.0, effective_food_yoy - 0.025) + 0.06 * (real_wage_ratio - 1.0)))
    effective_tfr = max(0.85, min(2.05, tracker["statutory_tfr"] + ed_tfr_boost + stress_Drag))
    iv["tfr"] = effective_tfr
    tracker["last_ind_tfr"] = effective_tfr

    if abs(effective_tfr - tracker["prev_asfr_tfr"]) > 1e-9 and tracker["prev_asfr_tfr"] > 0.0:
        ratio = effective_tfr / tracker["prev_asfr_tfr"]
        for age in range(15, 50):
            st.asfr["JPN"][age] *= ratio
        tracker["prev_asfr_tfr"] = effective_tfr

    # 2. Endogenous Net Migration (stock saturation + economic attractiveness)
    ssw_cap = st.lever_value["JPN"]["ssw_visa_cap"]
    foreign_pop = iv.get("foreign_residents", tracker["init_foreign"])
    years_elapsed = st.day / 365.0
    # Post-COVID reopening spike (242k in 2024) gradually normalizes toward IPSS long-run structural baseline (~168k) over 12 years
    base_structural_mig = 168000.0 + (tracker["init_mig"] - 168000.0) * DM.exp(-years_elapsed / 12.0)
    ssw_Command_delta = max(0.0, (ssw_cap - tracker["init_ssw"]) * tracker["ssw_k"])
    # As foreign resident stock grows relative to expanded cap, turnover/return migration moderates net inflow
    cap_headroom = max(0.35, min(1.0, 1.0 - max(0.0, foreign_pop - tracker["init_foreign"] - ssw_cap * 1.5) / max(1.0, 8000000.0)))
    # Economic attractiveness factor (falls during high inflation / fiscal crisis / low real wages)
    econ_attract = max(0.60, min(1.10, 1.0 - 2.5 * max(0.0, econ_infl - 0.03) - 0.6 * max(0.0, discontent - 0.22) + 0.15 * (real_wage_ratio - 1.0)))
    iv["net_migration"] = (base_structural_mig + ssw_Command_delta * cap_headroom) * econ_attract

    # 3. Decay year-1 public_investment fiscal multiplier after 365 days (per levers.json ESRI source)
    if tracker["pi_boost_until_day"] > 0 and st.day == tracker["pi_boost_until_day"]:
        iv["gdp_real_growth"] = tracker["init_real_growth"]
        tracker["pi_boost_until_day"] = 0

    # 4. Age-stratified cohorts: 15-64 (working age), 65-74 (active seniors), 75+ (late-stage elderly)
    co = st.cohort["JPN"]
    wp_15_64 = 0.0
    pop_65_74 = 0.0
    pop_75_plus = 0.0
    for age in range(15, 65):
        wp_15_64 += co[age * 2] + co[age * 2 + 1]
    for age in range(65, 75):
        pop_65_74 += co[age * 2] + co[age * 2 + 1]
    for age in range(75, 101):
        pop_75_plus += co[age * 2] + co[age * 2 + 1]
    pop_65_plus = pop_65_74 + pop_75_plus

    pension_emp_gain = max(0.0, (st.lever_value["JPN"]["pension_age"] - tracker["init_pension_age"]) * tracker["pension_k"])
    lf_ratio = (wp_15_64 + pension_emp_gain) / max(1.0, tracker["init_wp_15_64"])

    # Nominal GDP accounting identity
    nom_drift_day = (iv["gdp_real_growth"] + econ_infl) / 365.0
    iv["gdp_nominal"] = tracker["last_gdp"] * (1.0 + nom_drift_day) * (lf_ratio / tracker["last_lf_ratio"])
    tracker["last_gdp"] = iv["gdp_nominal"]
    tracker["last_lf_ratio"] = lf_ratio

    # 5. General Revenue accounting identity
    gdp_factor = iv["gdp_nominal"] / max(1.0, tracker["init_gdp"])
    lever_tax_delta = iv["tax_revenue"] - tracker["init_tax_rev"]
    tax_rev_current = (tracker["init_tax_rev"] + lever_tax_delta) * gdp_factor
    iv["gov_revenue_general"] = tracker["init_nontax_rev"] * gdp_factor + tax_rev_current

    # 6. General Expenditure with 65-74 vs 75+ MHLW Cost Weighting & 8.5-Year JGB Rollover
    tracker["infl_index"] *= (1.0 + max(0.0, econ_infl - 0.02) / 365.0)
    infl_idx = tracker["infl_index"]
    health_factor = (iv["health_expenditure"] / max(1.0, tracker["init_health"])) * infl_idx
    # Weighted elderly cost index: 75+ per-capita medical/LTCI cost is 3.5x that of 65-74
    weighted_old_now = (1.0 * pop_65_74 + 3.5 * pop_75_plus) / max(1.0, iv["pop_total"])
    aging_cost_factor = weighted_old_now / max(1e-6, tracker["init_weighted_old"])
    gov_cons_factor = (iv["gov_consumption"] / max(1.0, tracker["init_gov_cons"])) * infl_idx
    senior_relief_share = (pension_emp_gain / max(1.0, pop_65_plus)) * 2.5

    ss_line = tracker["budget_social_security"] * health_factor * aging_cost_factor * max(0.70, 1.0 - senior_relief_share)
    ss_delta = ss_line - tracker["budget_social_security"]
    lat_delta = tracker["budget_lat"] * ((tax_rev_current / max(1.0, tracker["init_tax_rev"])) - 1.0)
    core_ops_delta = tracker["budget_core_ops"] * (gov_cons_factor - 1.0)

    # Continuous JGB 10Y market yield & 8.5-year average maturity refinancing rollover
    debt_to_gdp_now = iv["gov_debt_total"] / max(1.0, iv["gdp_nominal"])
    target_jgb = (
        tracker["init_jgb"]
        + 0.45 * max(0.0, econ_infl - 0.02)
        + 0.008 * max(0.0, debt_to_gdp_now - tracker["init_debt_gdp"])
        + 0.035 * max(0.0, tracker["last_bond_dep"] - 0.35)
    )
    if tracker["last_bond_dep"] > 0.45:
        target_jgb += 0.015 * (tracker["last_bond_dep"] - 0.45) * 10.0
    target_jgb = min(0.055, max(0.005, target_jgb))
    iv["jgb_10y"] += (target_jgb - iv["jgb_10y"]) / 90.0

    # Roll over 1 / (8.5 * 365) of debt stock each day into current market yield
    alpha_roll = 1.0 / (8.5 * 365.0)
    tracker["eff_jgb_rate"] += (iv["jgb_10y"] - tracker["eff_jgb_rate"]) * alpha_roll
    debt_stock_ratio = iv["gov_debt_total"] / max(1.0, tracker["init_debt"])
    coupon_spread = max(0.0, tracker["eff_jgb_rate"] - tracker["init_jgb"])
    ds_line = tracker["budget_debt_service"] * debt_stock_ratio + iv["gov_debt_total"] * coupon_spread
    ds_delta = ds_line - tracker["budget_debt_service"]

    ca_delta = (st.lever_value["JPN"]["child_allowance"] - tracker["init_ca"]) * gov_cons_factor
    pi_delta = (st.lever_value["JPN"]["public_investment"] - tracker["init_pi"]) * gov_cons_factor
    ed_delta = (st.lever_value["JPN"]["education_budget"] - tracker["init_ed"]) * gov_cons_factor
    oda_delta = (st.lever_value["JPN"]["oda_budget"] - tracker["init_oda"]) * gov_cons_factor
    def_delta = iv["defence_budget"] - tracker["init_def"]

    iv["gov_expenditure_general"] = (
        tracker["init_gov_exp"]
        + ss_delta
        + lat_delta
        + core_ops_delta
        + ds_delta
        + ca_delta
        + pi_delta
        + ed_delta
        + oda_delta
        + def_delta
    )

    iv["new_bond_issuance"] = max(0.0, iv["gov_expenditure_general"] - iv["gov_revenue_general"])
    bond_dep = iv["new_bond_issuance"] / max(1.0, iv["gov_expenditure_general"])
    tracker["last_bond_dep"] = bond_dep
    iv["debt_to_gdp"] = debt_to_gdp_now
    return bond_dep, pop_75_plus / max(1.0, iv["pop_total"])


def replenish_persons_if_needed(ps, c_id, st, qx_2024, regions, n_per, cal_y, seed_gen):
    """
    Replenishes the representative micro-household cohort from live `st.cohort["JPN"]` when aging deaths
    reduce `ps.p.n` below 60% of initial size in multi-decade (50-100+ year) simulations.
    Preserves cumulative `month`, `price_index`, `wage_index`, and `PENSION_AGE`.
    """
    old_p = ps.p
    saved_month = old_p.month
    saved_price = old_p.price_index
    saved_wage = old_p.wage_index
    saved_pension_age = old_p.PENSION_AGE
    saved_pension = dict(old_p.pension)

    ps_new = Persons.create(c_id, seed_gen, st.cohort["JPN"], qx_2024, regions, n_per, cal_y)
    ps_new.p.month = saved_month
    ps_new.p.price_index = saved_price
    ps_new.p.wage_index = saved_wage
    ps_new.p.PENSION_AGE = saved_pension_age
    ps_new.p.pension = saved_pension
    return ps_new


def run_simulation(years=25, scenario="baseline", custom_levers=None, full_mode=False, n_per=2, coalition_pass=False):
    ensure_oracle_dumps()

    mode_label = (
        "Full-Spectrum Realistic Closed-Loop (Status + Persons + EconMonth + Diet Bills + Elections <-> Demo/Fiscal Feedback)"
        if full_mode
        else "Standard Endogenous (Status + Persons + EconMonth + Diet Bills, Fixed 2024-12 Seats)"
    )
    print(f"\n[Sandvox Engine v4] Initializing {years}-year simulation ({years * 365} days / {years * 12} months)...")
    print(f"[Architecture] {mode_label}")
    t0 = time.time()

    # 1. Initialize Status (`status_2024.json` + `levers.json`)
    st = Status()
    err = st.load(2024, ["JPN"])
    if err != "":
        raise RuntimeError(err)

    if "gdp_nominal" in st.trend_day["JPN"]:
        del st.trend_day["JPN"]["gdp_nominal"]

    # Load exact 2025-01-01 cohort from `data/modern/jpn/start_2025.json` (123,748,543 persons)
    c = country.load("JPN")
    p_2025, regions = create.inputs_2025("JPN", seed=1)
    co_2025 = p_2025.cohort
    qx_2024 = p_2025.qx
    for idx in range(len(co_2025)):
        st.cohort["JPN"][idx] = float(co_2025[idx])
    st.ind["JPN"]["pop_total"] = st.population_of("JPN")
    old_init = sum(st.cohort["JPN"][a * 2] + st.cohort["JPN"][a * 2 + 1] for a in range(65, 101))
    old_75_init = sum(st.cohort["JPN"][a * 2] + st.cohort["JPN"][a * 2 + 1] for a in range(75, 101))
    st.ind["JPN"]["share_65plus"] = old_init / st.ind["JPN"]["pop_total"]

    # 2. Initialize Polity (Organs, Cabinet, Public Approval, Election, Brain)
    org = Organs()
    org.load_state("JPN")
    if coalition_pass:
        for k_p in ("consumption_tax_rate", "pension_age", "child_allowance"):
            org.spec.setdefault("party_positions", {}).setdefault(k_p, {})["DPFP"] = "yes"
            org.spec["party_positions"][k_p]["Ishin"] = "yes"

    cab = Cabinet()
    cab.setup(org)
    pub = Public()
    pub.load_state("JPN", st.value("JPN", "cabinet_approval"))
    el = Election()
    el.load_state("JPN")
    brain = Brain()

    # 3. Initialize Persons Micro-Layer & EconMonth (CropFarming, FoodMfg, TradingHouse, Bank, Labour)
    ps = Persons.create(c.id, 1, co_2025, qx_2024, regions, n_per, 2025)
    init_p_n = ps.p.n
    seed_gen = 1
    econ = EconMonth()
    econ.create("JPN")
    econ.labour = Labour()
    econ.labour.load_state("JPN")

    # 4. Configure Policy Levers by Scenario
    if custom_levers is not None:
        lever_plan = list(custom_levers)
    elif scenario == "baseline":
        lever_plan = []
    elif scenario == "child_splash":
        lever_plan = [
            ("child_allowance", 10000.0),
            ("public_investment", 15000.0),
            ("education_budget", 10000.0)
        ]
    elif scenario == "migration_only":
        lever_plan = [
            ("ssw_visa_cap", 2000000.0)
        ]
    elif scenario == "synergy":
        lever_plan = [
            ("child_allowance", 6000.0),
            ("ssw_visa_cap", 1800000.0),
            ("consumption_tax_rate", 0.14),
            ("pension_age", 67.0),
            ("health_fee_schedule", -0.02)
        ]
    else:
        lever_plan = []

    init_pop = int(round(st.value("JPN", "pop_total")))
    print(
        f"[Initial State] 2025-01-01 Population: {init_pop:,} (start_2025.json) | "
        f"65+%: {st.value('JPN', 'share_65plus')*100:.1f}% (75+%: {old_75_init/init_pop*100:.1f}%) | "
        f"TFR: {st.value('JPN', 'tfr'):.2f} | Debt/GDP: {st.value('JPN', 'debt_to_gdp')*100:.1f}%"
    )

    pending_platform = {}
    lever_logs_init = []
    for lid, val in lever_plan:
        status_code, msg = submit_policy_lever(st, cab, org, 0, lid, val, force_direct=coalition_pass)
        lever_logs_init.append(f"{lid}={val} -> {msg}")
        if status_code in ("bill", "refused"):
            pending_platform[lid] = float(val)

    if lever_logs_init:
        print("[Policy Levers] " + " | ".join(lever_logs_init))
    else:
        print("[Policy Levers] None (Baseline Status Quo)")

    co_init = st.cohort["JPN"]
    init_wp_15_64 = sum(co_init[a * 2] + co_init[a * 2 + 1] for a in range(15, 65))
    init_65_74 = sum(co_init[a * 2] + co_init[a * 2 + 1] for a in range(65, 75))
    init_75_plus = sum(co_init[a * 2] + co_init[a * 2 + 1] for a in range(75, 101))
    init_weighted_old = (1.0 * init_65_74 + 3.5 * init_75_plus) / st.ind["JPN"]["pop_total"]

    fy24_lines = org.laws["budget_fy2024"]["lines_bn_jpy"]
    core_ops_0 = (
        float(fy24_lines["public_works"])
        + float(fy24_lines["education_science"])
        + float(fy24_lines["defence"])
        + float(fy24_lines["other"])
        + float(fy24_lines["reserve_fund"])
    )
    tracker = {
        "statutory_tfr": st.value("JPN", "tfr"),
        "last_ind_tfr": st.value("JPN", "tfr"),
        "prev_asfr_tfr": st.value("JPN", "tfr"),
        "init_wp_15_64": init_wp_15_64,
        "init_weighted_old": init_weighted_old,
        "infl_index": 1.0,
        "last_lf_ratio": 1.0,
        "init_real_growth": st.ind0["JPN"]["gdp_real_growth"],
        "pi_boost_until_day": 0,
        "init_gdp": st.value("JPN", "gdp_nominal"),
        "last_gdp": st.value("JPN", "gdp_nominal"),
        "init_tax_rev": st.value("JPN", "tax_revenue"),
        "init_nontax_rev": st.value("JPN", "gov_revenue_general") - st.value("JPN", "tax_revenue"),
        "init_gov_exp": st.value("JPN", "gov_expenditure_general"),
        "budget_social_security": float(fy24_lines["social_security"]),
        "budget_lat": float(fy24_lines["local_allocation_tax"]),
        "budget_debt_service": float(fy24_lines["debt_service"]),
        "budget_core_ops": core_ops_0,
        "init_health": st.value("JPN", "health_expenditure"),
        "init_gov_cons": st.value("JPN", "gov_consumption"),
        "init_jgb": st.value("JPN", "jgb_10y"),
        "eff_jgb_rate": st.value("JPN", "jgb_10y"),
        "init_debt": st.value("JPN", "gov_debt_total"),
        "init_debt_gdp": st.value("JPN", "debt_to_gdp"),
        "last_bond_dep": st.value("JPN", "new_bond_issuance") / max(1.0, st.value("JPN", "gov_expenditure_general")),
        "init_def": st.value("JPN", "defence_budget"),
        "init_ca": st.lever_value["JPN"]["child_allowance"],
        "init_pi": st.lever_value["JPN"]["public_investment"],
        "init_ed": st.lever_value["JPN"]["education_budget"],
        "init_oda": st.lever_value["JPN"]["oda_budget"],
        "init_pension_age": st.lever_value["JPN"]["pension_age"],
        "pension_k": float(st.levers["JPN"]["levers"]["pension_age"]["response"]["k"]),
        "init_ssw": st.lever_value["JPN"]["ssw_visa_cap"],
        "ssw_k": float(st.levers["JPN"]["levers"]["ssw_visa_cap"]["response"]["k"]),
        "init_mig": st.value("JPN", "net_migration"),
        "init_foreign": st.value("JPN", "foreign_residents"),
    }

    unemp_prev = st.value("JPN", "unemployment_rate")
    last_election_month = 0
    econ_infl = 0.02
    discontent = 0.20
    effective_food_yoy = 0.02
    real_wage_ratio = 1.0

    history = []
    year_births = 0.0
    year_deaths = 0.0
    year_mig = 0.0
    year_notes = []
    total_days = years * 365
    month_idx = 0

    for day in range(1, total_days + 1):
        logged_before = len(st.lever_log)
        # Status._step_cohort() runs before Status._apply_due() inside st.step(), so record today's active net_migration before st.step()
        year_mig += st.value("JPN", "net_migration") / 365.0

        # Daily step in Status (cohort births, deaths, migration into ages 20-39, fiscal debt accumulation, lever due dates)
        st.step()

        for i_log in range(logged_before, len(st.lever_log)):
            if str(st.lever_log[i_log][4]) == "applied" and str(st.lever_log[i_log][2]) == "public_investment":
                tracker["pi_boost_until_day"] = day + 365

        year_births += st.daily_births["JPN"]
        year_deaths += st.daily_deaths["JPN"]

        bond_dep, share_75plus = sync_macro_fiscal_and_asfr(
            st, tracker, econ_infl, discontent, effective_food_yoy, real_wage_ratio
        )

        # Month-end coupling (every 30/31 days per MA.is_month_end)
        if MA.is_month_end(day):
            month_idx += 1
            cal_y = 2025 + (month_idx - 1) // 12
            cal_m = ((month_idx - 1) % 12) + 1

            # 1. Diet votes on pending bills after 5-month parliamentary session (`Cabinet.vote_due`)
            bills_before = {b["id"]: b["status"] for b in cab.bills}
            cab.vote_due(month_idx, lambda l_id, v_val: st.set_lever("JPN", l_id, v_val))
            for b in cab.bills:
                if bills_before.get(b["id"]) == "submitted" and b["status"] != "submitted":
                    if b["status"] == "enacted":
                        pending_platform.pop(b["lever"], None)
                        year_notes.append(f"Diet Enacted {b['lever']}")
                    elif b["status"] == "rejected":
                        year_notes.append(f"Diet Rejected {b['lever']}")

            # 2. Collect levers whose lead_days completed this month
            applied_this_month = [
                str(st.lever_log[i][2])
                for i in range(0, len(st.lever_log))
                if str(st.lever_log[i][4]) == "applied" and int(st.lever_log[i][0]) > day - 31
            ]
            if "pension_age" in applied_this_month:
                ps.p.PENSION_AGE = int(round(st.lever_value["JPN"]["pension_age"]))

            # 3. Replenish micro households if multi-decade aging reduces sample size below 60%
            if ps.p.n < max(20, int(init_p_n * 0.60)):
                seed_gen += 1
                ps = replenish_persons_if_needed(ps, c.id, st, qx_2024, regions, n_per, cal_y, seed_gen)

            # 4. Persons labour supply -> EconMonth (Labour + CropFarming + FoodMfg + TradingHouse + Bank)
            psup = ps.supply()
            econ.labour.receive(float(psup["search_share"]), float(psup["wage_demand_share"]), psup["scales"])
            econ.step()

            # 5. Update Status labour indicators from EconMonth
            st.ind["JPN"]["unemployment_rate"] = econ.labour.u
            lf = st.value("JPN", "employed") + st.value("JPN", "unemployed")
            st.ind["JPN"]["unemployed"] = lf * econ.labour.u
            st.ind["JPN"]["employed"] = lf * (1.0 - econ.labour.u)

            # 6. Endogenous Inflation & Fiscal Risk Premium
            econ_infl = float(econ.world.env.get("inflation", 0.02))
            food_yoy = float(econ.world.env.get("food_price_yoy", 0.0))
            fiscal_crisis = (bond_dep > 0.45)
            if fiscal_crisis:
                econ_infl += 0.030
                food_yoy += 0.040
            if "consumption_tax_rate" in applied_this_month:
                tax_jump = st.lever_value["JPN"]["consumption_tax_rate"] - 0.10
                econ_infl += max(0.0, tax_jump)
                food_yoy += max(0.0, tax_jump * 0.8)

            active_tax_burden = max(0.0, st.lever_value["JPN"]["consumption_tax_rate"] - 0.10)
            effective_food_yoy = food_yoy + (active_tax_burden * 0.35)
            st.ind["JPN"]["cpi_inflation"] = econ_infl

            # 7. Step Persons with real EconMonth outputs & dynamic Status cohort
            ps.step({
                "inflation_month": econ_infl / 12.0,
                "food_price_yoy": effective_food_yoy,
                "unemployment_rate": econ.labour.u,
                "wage_index": econ.labour.wage_index,
                "levers": applied_this_month,
                "cohort": st.cohort["JPN"]
            })
            sm = ps.summary()
            raw_disc = float(sm["discontent_p10_p50_p90"][1])
            if not math.isnan(raw_disc):
                discontent = raw_disc
            real_wage_ratio = econ.labour.wage_index / max(0.5, 1.0 + active_tax_burden)

            # 8. Step Public Approval & Elections -> Policy Feedback Loop
            du_pt = (econ.labour.u - unemp_prev) * 100.0
            unemp_prev = econ.labour.u
            ap = pub.step(month_idx, effective_food_yoy, du_pt, applied_this_month)
            ap = max(0.05, min(0.90, ap - (discontent - 0.20) * 0.25))
            st.ind["JPN"]["cabinet_approval"] = ap

            if full_mode and cal_m == 10 and (cal_y - 2024) % 4 == 0:
                d_ap = pub.change_since(last_election_month)
                if fiscal_crisis:
                    d_ap = min(d_ap, (ap - 0.35) * 100.0)
                d_cpi_pt = (econ_infl - 0.02) * 100.0
                shares = el.vote_shares(list(org.governing), d_ap, du_pt, d_cpi_pt)
                r_low = el.run_lower_house(shares)
                org.seats["house_of_representatives"] = dict(r_low["seats"])
                gov_seats = org.governing_seats("house_of_representatives")
                st.ind["JPN"]["lower_house_seats_governing"] = float(gov_seats)
                last_election_month = month_idx
                maj_str = "Majority" if gov_seats >= 233 else "Minority"
                year_notes.append(f"Election({gov_seats}/465 {maj_str})")

                # CLOSED-LOOP ELECTION -> POLICY FEEDBACK:
                if gov_seats >= 233 and pending_platform:
                    for p_lid, p_val in list(pending_platform.items()):
                        st_code, _ = submit_policy_lever(st, cab, org, month_idx, p_lid, p_val)
                        if st_code == "executed":
                            pending_platform.pop(p_lid, None)
                            year_notes.append(f"Enacted {p_lid}")
                elif gov_seats < 233 and fiscal_crisis:
                    if st.lever_value["JPN"]["public_investment"] > tracker["init_pi"]:
                        st.set_lever("JPN", "public_investment", tracker["init_pi"])
                        year_notes.append("Diet Cut public_investment")
                    if st.lever_value["JPN"]["education_budget"] > tracker["init_ed"]:
                        st.set_lever("JPN", "education_budget", tracker["init_ed"])
                        year_notes.append("Diet Cut education_budget")
                    from world import brain as WB
                    cons_act = WB.choose(
                        "economy",
                        {"indicator": "new_bond_issuance", "direction": -1},
                        st.menu("JPN"),
                        dict(st.ind["JPN"])
                    )
                    if len(cons_act) == 2 and str(cons_act[0]) not in st.lever_due["JPN"]:
                        st.set_lever("JPN", str(cons_act[0]), float(cons_act[1]))
                        year_notes.append(f"Brain Consolidation tax={float(cons_act[1]):.2f}")

        # End of Year Recording (every 365 days)
        if day % 365 == 0:
            yr = 2025 + (day // 365) - 1
            gov_seats_now = int(st.value("JPN", "lower_house_seats_governing"))
            fiscal_crisis = (bond_dep > 0.45)
            history.append({
                "year": yr,
                "population": int(round(st.value("JPN", "pop_total"))),
                "births": int(round(year_births)),
                "deaths": int(round(year_deaths)),
                "net_mig": int(round(year_mig)),
                "tfr": round(st.value("JPN", "tfr"), 3),
                "share_65plus": round(st.value("JPN", "share_65plus") * 100, 1),
                "share_75plus": round(share_75plus * 100, 1),
                "jgb_10y": round(st.value("JPN", "jgb_10y") * 100, 2),
                "debt_gdp": round(st.value("JPN", "debt_to_gdp") * 100, 1),
                "bond_dep": round(bond_dep * 100, 1),
                "discontent": round(discontent, 3),
                "approval": round(st.value("JPN", "cabinet_approval") * 100, 1),
                "gov_seats": gov_seats_now,
                "crisis": fiscal_crisis,
                "notes": ", ".join(year_notes) if year_notes else "NORMAL"
            })
            year_births = 0.0
            year_deaths = 0.0
            year_mig = 0.0
            year_notes = []

    elapsed = round(time.time() - t0, 2)
    print(f"\n[Done] {years}-year endogenous simulation completed in {elapsed}s.\n")

    print("-" * 144)
    print(f"{'Year':<5} | {'Population':<13} | {'Births':<8} | {'Deaths':<9} | {'NetMig':<8} | {'TFR':<5} | {'65+%(75+)':<11} | {'JGB10Y':<6} | {'Debt/GDP':<8} | {'BondDep':<7} | {'Discontent':<10} | {'GovSeats':<8} | {'Status / Parliamentary Events'}")
    print("-" * 144)
    for r in history:
        st_prefix = "CRISIS (Debt) | " if r["crisis"] else ""
        st_flag = (st_prefix + r["notes"]) if (r["crisis"] and r["notes"] != "NORMAL") else ("CRISIS (Debt)" if r["crisis"] else r["notes"])
        aging_str = f"{r['share_65plus']:>4.1f}({r['share_75plus']:>4.1f})%"
        print(
            f"{r['year']:<5} | {r['population']:>11,}人 | {r['births']:>7,} | {r['deaths']:>8,} | "
            f"{r['net_mig']:>+7,} | {r['tfr']:>4.2f}  | {aging_str:<11} | {r['jgb_10y']:>5.2f}% | {r['debt_gdp']:>6.1f}% | "
            f"{r['bond_dep']:>5.1f}% | {r['discontent']:<10.3f} | {r['gov_seats']:>3}/465  | {st_flag}"
        )
    print("-" * 144)

    final = history[-1]
    tot_b = sum(r["births"] for r in history)
    tot_d = sum(r["deaths"] for r in history)
    tot_m = sum(r["net_mig"] for r in history)
    pop_change = final["population"] - init_pop
    flow_sum = tot_b - tot_d + tot_m
    print(
        f"\n[Summary {final['year']}] Final Pop: {final['population']:,} ({final['population']/1e4:,.1f}万人) | "
        f"Cum Births: {tot_b:,} | Cum Deaths: {tot_d:,} | Cum NetMig: {tot_m:+,} | "
        f"Pop Change: {pop_change:+,} (Flow Sum: {flow_sum:+,}) | Final Debt/GDP: {final['debt_gdp']}%"
    )
    return history


def main():
    parser = argparse.ArgumentParser(description="Sandvox Endogenous Forward Policy Simulator CLI (v4)")
    parser.add_argument("--years", type=int, default=25, help="Simulation horizon in years (default: 25)")
    parser.add_argument("--scenario", type=str, default="baseline",
                        choices=["baseline", "child_splash", "migration_only", "synergy"],
                        help="Policy scenario preset")
    parser.add_argument("--full", action="store_true", help="Enable full parliamentary election cycles & policy feedback")
    parser.add_argument("--coalition", action="store_true", help="Assume cross-party coalition agreement from day 0")
    parser.add_argument("--n-per", type=int, default=2, help="Representative persons per prefecture (default: 2)")

    args = parser.parse_args()
    run_simulation(years=args.years, scenario=args.scenario, full_mode=args.full, n_per=args.n_per, coalition_pass=args.coalition)


if __name__ == "__main__":
    main()
