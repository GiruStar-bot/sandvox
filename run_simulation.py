#!/usr/bin/env python3
"""
Sandvox Official Endogenous Policy Simulation CLI (v4.1 - Realistic Closed-Loop Engine)
Builds upon v3.1 (which resolved all audit items a-h) and incorporates the 5 v4 closed-loop mechanisms
plus all 3 v4 technical audit enhancements (Issues A, B, and C):

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
   - Per MHLW national medical & long-term care profiles, per-capita social security cost growth is weighted 3.5x toward
     the `75+` cohort (capturing Japan's 2025-2040 baby-boomer aging wave), while `pension_age` extension expands `65-74` employment.
4. Endogenous Net Migration (`NetMig`) Saturation & Economic Attractiveness:
   - Normalizes the 2023 post-COVID border reopening spike (`+242,000/yr`) toward long-run IPSS structural levels as the
     foreign resident stock (`foreign_residents`) grows, saturates `ssw_visa_cap` inflows smoothly as stock approaches the cap,
     and scales inflows with Japan's real wage / inflation stability (slowing inflows during fiscal/inflation crises).
5. Generational Cohort Replenishment in `Persons` for Multi-Century (100-Year+) Horizons (Audit Issue C Enhanced):
   - Prevents sample extinction (`Discontent = nan`) over 50-100+ year runs by replenishing households from the live
     `st.cohort["JPN"]` distribution whenever aging mortality reduces the micro sample below 60% of its initial size,
     while preserving wage/price indices, employment rates, income expectations, age-stratified assets/debt, food price beliefs,
     and accumulated macroeconomic emotion shifts (`emo - emo_base`).
6. Externalized Feedback Parameters (`data/modern/jpn/feedback_params.json`, Audit Issue B) & 2025-01-01 Initial State Alignment (Audit Issue A).
"""
import sys, os, argparse, time, math, json, copy
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ROOT_DIR, "py"))

import country
from core import detmath as DM
from people.layer import Persons
from people import rel as REL
from people.sections import _ranks
from tiers.start.p import P
from tiers.start.persons import age_band
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


DEFAULT_FEEDBACK_PARAMS = {
    "fertility": {
        "ed_budget_unit_bn": 4500.0,
        "ed_tfr_boost_per_unit": 0.045,
        "discontent_baseline": 0.20,
        "discontent_tfr_slope": -0.18,
        "food_infl_threshold": 0.025,
        "food_infl_tfr_slope": -0.22,
        "real_wage_tfr_slope": 0.06,
        "stress_drag_min": -0.10,
        "stress_drag_max": 0.04,
        "tfr_floor": 0.85,
        "tfr_ceiling": 2.05,
    },
    "migration": {
        "structural_baseline": 168000.0,
        "reopening_decay_years": 12.0,
        "cap_ssw_multiplier": 1.5,
        "cap_saturation_scale": 8000000.0,
        "cap_headroom_floor": 0.35,
        "infl_attract_threshold": 0.03,
        "infl_attract_slope": -2.5,
        "discontent_attract_threshold": 0.22,
        "discontent_attract_slope": -0.6,
        "real_wage_attract_slope": 0.15,
        "attract_min": 0.60,
        "attract_max": 1.10,
    },
    "fiscal_and_jgb": {
        "old_75plus_cost_weight": 3.5,
        "senior_relief_multiplier": 2.5,
        "senior_relief_floor": 0.70,
        "infl_index_threshold": 0.02,
        "jgb_infl_threshold": 0.02,
        "jgb_infl_slope": 0.45,
        "jgb_debt_gdp_slope": 0.008,
        "jgb_bond_dep_threshold": 0.35,
        "jgb_bond_dep_slope": 0.035,
        "crisis_bond_dep_threshold": 0.45,
        "jgb_crisis_slope": 0.15,
        "jgb_min": 0.005,
        "jgb_max": 0.055,
        "jgb_adjust_days": 90.0,
        "jgb_rollover_years": 8.5,
        "crisis_infl_premium": 0.030,
        "crisis_food_premium": 0.040,
        "vat_food_passthrough": 0.80,
        "vat_ongoing_food_bite": 0.35,
    },
    "persons_replenishment": {
        "min_sample_ratio": 0.60,
        "min_sample_abs": 20,
    },
}


def load_feedback_params(params_path=None, overrides=None):
    """Loads feedback parameters from `data/modern/jpn/feedback_params.json` (or custom path) merged over `DEFAULT_FEEDBACK_PARAMS`."""
    params = copy.deepcopy(DEFAULT_FEEDBACK_PARAMS)
    default_path = os.path.join(ROOT_DIR, "data", "modern", "jpn", "feedback_params.json")
    target_path = params_path if params_path is not None else (default_path if os.path.exists(default_path) else None)
    if target_path and os.path.exists(target_path):
        with open(target_path, "r", encoding="utf-8") as fh:
            loaded = json.load(fh)
        for sec, vals in loaded.items():
            if sec in params and isinstance(vals, dict):
                for k, v in vals.items():
                    params[sec][k] = float(v) if isinstance(v, (int, float)) else v
    if isinstance(overrides, dict):
        for sec, vals in overrides.items():
            if sec in params and isinstance(vals, dict):
                for k, v in vals.items():
                    params[sec][k] = float(v) if isinstance(v, (int, float)) else v
    return params


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


def align_initial_state_2025(st, c, co_2025):
    """
    Aligns `Status` indicators from the 2023-10 / 2024-06 snapshot in `status_2024.json` to the exact
    `2025-01-01` initial state in `start_2025.json` (`cohort_2025-01-01.json`) (Audit Issue A).
    """
    wp_2024 = sum(st.cohort["JPN"][a * 2] + st.cohort["JPN"][a * 2 + 1] for a in range(15, 65))
    for idx in range(len(co_2025)):
        st.cohort["JPN"][idx] = float(co_2025[idx])

    pop_2025 = st.population_of("JPN")
    wp_2025 = sum(st.cohort["JPN"][a * 2] + st.cohort["JPN"][a * 2 + 1] for a in range(15, 65))
    old_65_2025 = sum(st.cohort["JPN"][a * 2] + st.cohort["JPN"][a * 2 + 1] for a in range(65, 101))
    old_75_2025 = sum(st.cohort["JPN"][a * 2] + st.cohort["JPN"][a * 2 + 1] for a in range(75, 101))

    iv = st.ind["JPN"]
    iv["pop_total"] = pop_2025
    iv["working_age_pop"] = wp_2025
    iv["aged_pop"] = old_65_2025
    iv["share_65plus"] = old_65_2025 / max(1.0, pop_2025)
    iv["share_75plus"] = old_75_2025 / max(1.0, pop_2025)

    d_2025 = load.load_json(c.path("start_2025"))
    flows = d_2025.get("flows", {})
    births_2024 = sum(float(flows[ym]["births"]) for ym in flows if ym.startswith("2024-"))
    deaths_2024 = sum(float(flows[ym]["deaths"]) for ym in flows if ym.startswith("2024-"))
    intl_h2_2024 = sum(
        float(flows[ym]["intl_net"])
        for ym in ("2024-07", "2024-08", "2024-09", "2024-10", "2024-11", "2024-12")
        if ym in flows
    )
    if births_2024 > 0.0 and deaths_2024 > 0.0:
        iv["births"] = births_2024
        iv["deaths"] = deaths_2024
        iv["natural_change"] = births_2024 - deaths_2024
    if "foreign_residents" in iv:
        iv["foreign_residents"] += intl_h2_2024

    if wp_2024 > 0.0 and "employed" in iv and "unemployed" in iv:
        wp_scale = wp_2025 / wp_2024
        iv["employed"] *= wp_scale
        iv["unemployed"] *= wp_scale

    st.ind0["JPN"] = dict(iv)
    return old_65_2025, old_75_2025


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


COUNTERPARTS = ("USA", "CHN", "EU")
# The JPN-side customs lane key for each counterpart entity (the sourced
# trade_by_partner dict uses customs names; the EU lane is created at
# runtime from the EU profile's mirror lane - see run_simulation).
LANE_KEYS = {"USA": "USA", "CHN": "CHINA", "EU": "EU"}


def sync_bilateral_trade(st, tracker):
    """Two-way trade on every loaded counterpart lane (Roadmap P2/P5,
    blueprint stage S3).

    A counterpart's tariff on Japan (its own lever, set directly on its
    entity) scales Japan's exports to it by the sourced -1.5 import
    demand elasticity (Kee, Nicita & Olarreaga 2008, the same source as
    JPN's tariff spec), applied to the (1 + t) factor because the
    counterpart lever is a delta over a zero additional-tariff baseline.
    The export delta moves exports_customs and shifts the nominal GDP
    level by the net-export impulse (delta / initial GDP), which the
    fiscal sync then carries forward. Japan's general tariff moves each
    lane's imports with the same (v/old) elasticity form Status._respond
    applies to total imports; imports_customs is NOT adjusted here,
    because that response already moved the total. Each mirror lane is
    rewritten from the JPN lane every call: Japan's exports to X are
    X's imports from Japan, exactly (cross-border identity). With no
    tariff changes the factors are 1 and nothing moves.
    """
    jp_aux = st.aux.get("JPN", {}).get("trade_by_partner")
    if not jp_aux:
        return
    el = -1.5
    t_jp = float(st.lever_value["JPN"]["tariff_rate_general"])
    prev_jp = float(tracker.get("jp_tariff_prev", t_jp))
    jp_changed = t_jp != prev_jp and prev_jp > 0.0 and t_jp > 0.0
    for code in COUNTERPARTS:
        if not st.has(code):
            continue
        cp_aux = st.aux.get(code, {}).get("trade_by_partner")
        lane = jp_aux.get(LANE_KEYS[code])
        if not cp_aux or "JPN" not in cp_aux or lane is None:
            continue
        mirror = cp_aux["JPN"]
        t_cp = float(st.lever_value.get(code, {}).get("tariff_on_jpn", 0.0))
        prev_cp = float(tracker.get(f"cp_tariff_prev_{code}", 0.0))
        if t_cp != prev_cp:
            f = ((1.0 + t_cp) / (1.0 + prev_cp)) ** el
            old_exp = float(lane["exports_bn_jpy"])
            lane["exports_bn_jpy"] = old_exp * f
            d_net = float(lane["exports_bn_jpy"]) - old_exp
            st.ind["JPN"]["exports_customs"] += d_net
            tracker["last_gdp"] *= (1.0 + d_net / max(1.0, tracker["init_gdp"]))
            tracker[f"cp_tariff_prev_{code}"] = t_cp
        if jp_changed:
            lane["imports_bn_jpy"] = float(lane["imports_bn_jpy"]) * ((t_jp / prev_jp) ** el)
        mirror["imports_bn_jpy"] = lane["exports_bn_jpy"]
        mirror["exports_bn_jpy"] = lane["imports_bn_jpy"]
    if jp_changed:
        tracker["jp_tariff_prev"] = t_jp


def sync_macro_fiscal_and_asfr(st, tracker, econ_infl, discontent, effective_food_yoy, real_wage_ratio, params=None):
    """
    Realistic closed-loop accounting & demographic feedback parameterized via `feedback_params.json`:
    1. Fertility (`tfr` & `asfr`)
    2. Endogenous Net Migration (`net_migration`)
    3. Age-Stratified Demographics (`15-64`, `65-74`, `75+`)
    4. Continuous JGB Yield Curve (`jgb_10y`) & 8.5-Year Maturity Refinancing Lag (`eff_jgb_rate`)
    """
    if params is None:
        params = DEFAULT_FEEDBACK_PARAMS
    fp = params["fertility"]
    mp = params["migration"]
    jp = params["fiscal_and_jgb"]
    iv = st.ind["JPN"]

    # 1. Capture statutory TFR jumps from `Status._respond()` (e.g. `child_allowance`)
    if abs(iv["tfr"] - tracker["last_ind_tfr"]) > 1e-9:
        tracker["statutory_tfr"] += (iv["tfr"] - tracker["last_ind_tfr"])

    # Education budget child-rearing relief
    ed_delta_raw = st.lever_value["JPN"]["education_budget"] - tracker["init_ed"]
    ed_tfr_boost = max(0.0, (ed_delta_raw / fp["ed_budget_unit_bn"]) * fp["ed_tfr_boost_per_unit"])

    # Household economic security feedback (cost-of-living bite vs. real wage growth)
    stress_drag = max(
        fp["stress_drag_min"],
        min(
            fp["stress_drag_max"],
            fp["discontent_tfr_slope"] * (discontent - fp["discontent_baseline"])
            + fp["food_infl_tfr_slope"] * max(0.0, effective_food_yoy - fp["food_infl_threshold"])
            + fp["real_wage_tfr_slope"] * (real_wage_ratio - 1.0),
        ),
    )
    effective_tfr = max(fp["tfr_floor"], min(fp["tfr_ceiling"], tracker["statutory_tfr"] + ed_tfr_boost + stress_drag))
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
    base_structural_mig = mp["structural_baseline"] + (tracker["init_mig"] - mp["structural_baseline"]) * DM.exp(
        -years_elapsed / mp["reopening_decay_years"]
    )
    ssw_command_delta = max(0.0, (ssw_cap - tracker["init_ssw"]) * tracker["ssw_k"])
    cap_headroom = max(
        mp["cap_headroom_floor"],
        min(
            1.0,
            1.0 - max(0.0, foreign_pop - tracker["init_foreign"] - ssw_cap * mp["cap_ssw_multiplier"]) / max(1.0, mp["cap_saturation_scale"]),
        ),
    )
    econ_attract = max(
        mp["attract_min"],
        min(
            mp["attract_max"],
            1.0
            + mp["infl_attract_slope"] * max(0.0, econ_infl - mp["infl_attract_threshold"])
            + mp["discontent_attract_slope"] * max(0.0, discontent - mp["discontent_attract_threshold"])
            + mp["real_wage_attract_slope"] * (real_wage_ratio - 1.0),
        ),
    )
    iv["net_migration"] = (base_structural_mig + ssw_command_delta * cap_headroom) * econ_attract
    if tracker.get("mig_scale", 1.0) != 1.0:
        iv["net_migration"] *= tracker["mig_scale"]

    # Origin composition of the flow (Roadmap P5): residents shares are
    # the Immigration Services Agency's 2024-06 stock (links_2024 people
    # block, rounded). The structural part of the flow follows the stock
    # shares; the SSW-driven part is attributed to the SSW-sending
    # origins (VNM/PHL/IDN/NPL), so the visa lever moves the composition,
    # not only the total. The parts sum exactly to net_migration.
    _scale = float(tracker.get("mig_scale", 1.0))
    _ssw_flow = ssw_command_delta * cap_headroom * econ_attract * _scale
    _struct_flow = base_structural_mig * econ_attract * _scale
    _ssw_group = sum(ORIGIN_SHARES[o] for o in SSW_ORIGINS)
    _origins = {}
    for _o, _s in ORIGIN_SHARES.items():
        _f = _struct_flow * _s
        if _o in SSW_ORIGINS:
            _f += _ssw_flow * (_s / _ssw_group)
        _origins[_o] = {"residents_share": _s, "annual_flow": _f}
    st.aux.setdefault("JPN", {})["migration_by_origin"] = _origins

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
    iv["working_age_pop"] = wp_15_64
    iv["aged_pop"] = pop_65_plus
    iv["share_75plus"] = pop_75_plus / max(1.0, iv["pop_total"])

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
    tracker["infl_index"] *= (1.0 + max(0.0, econ_infl - jp["infl_index_threshold"]) / 365.0)
    infl_idx = tracker["infl_index"]
    health_factor = (iv["health_expenditure"] / max(1.0, tracker["init_health"])) * infl_idx
    weighted_old_now = (1.0 * pop_65_74 + jp["old_75plus_cost_weight"] * pop_75_plus) / max(1.0, iv["pop_total"])
    aging_cost_factor = weighted_old_now / max(1e-6, tracker["init_weighted_old"])
    gov_cons_factor = (iv["gov_consumption"] / max(1.0, tracker["init_gov_cons"])) * infl_idx
    senior_relief_share = (pension_emp_gain / max(1.0, pop_65_plus)) * jp["senior_relief_multiplier"]

    ss_line = tracker["budget_social_security"] * health_factor * aging_cost_factor * max(jp["senior_relief_floor"], 1.0 - senior_relief_share)
    ss_delta = ss_line - tracker["budget_social_security"]
    lat_delta = tracker["budget_lat"] * ((tax_rev_current / max(1.0, tracker["init_tax_rev"])) - 1.0)
    core_ops_delta = tracker["budget_core_ops"] * (gov_cons_factor - 1.0)

    # Continuous JGB 10Y market yield & 8.5-year average maturity refinancing rollover
    debt_to_gdp_now = iv["gov_debt_total"] / max(1.0, iv["gdp_nominal"])
    target_jgb = (
        tracker["init_jgb"]
        + jp["jgb_infl_slope"] * max(0.0, econ_infl - jp["jgb_infl_threshold"])
        + jp["jgb_debt_gdp_slope"] * max(0.0, debt_to_gdp_now - tracker["init_debt_gdp"])
        + jp["jgb_bond_dep_slope"] * max(0.0, tracker["last_bond_dep"] - jp["jgb_bond_dep_threshold"])
    )
    if tracker["last_bond_dep"] > jp["crisis_bond_dep_threshold"]:
        target_jgb += jp["jgb_crisis_slope"] * (tracker["last_bond_dep"] - jp["crisis_bond_dep_threshold"])
    target_jgb = min(jp["jgb_max"], max(jp["jgb_min"], target_jgb))
    iv["jgb_10y"] += (target_jgb - iv["jgb_10y"]) / jp["jgb_adjust_days"]

    # Roll over 1 / (jgb_rollover_years * 365) of debt stock each day into current market yield
    alpha_roll = 1.0 / (jp["jgb_rollover_years"] * 365.0)
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
    return bond_dep, iv["share_75plus"]


def replenish_persons_if_needed(ps, c_id, st, qx_2024, regions, n_per, cal_y, seed_gen, current_u=None):
    """
    Replenishes the representative micro-household cohort from live `st.cohort["JPN"]` when aging deaths
    reduce `ps.p.n` below 60% of initial size in multi-decade (50-100+ year) simulations.
    Audit Issue C Fix: Preserves not only `month`, `price_index`, `wage_index`, `PENSION_AGE`, and `pension`,
    but also recomputes individual wages (`repay`) at `saved_wage`, preserves income expectations (`q_income`),
    inflation expectations (`q_price`), food price beliefs (`belief`), age-stratified household `assets` and `debt`,
    employment rate (`current_u`), accumulated emotion shifts (`emo - emo_base`), and `food_plan_start`.
    """
    old_p = ps.p
    saved_month = old_p.month
    saved_price = old_p.price_index
    saved_wage = old_p.wage_index
    saved_pension_age = old_p.PENSION_AGE
    saved_pension = copy.deepcopy(old_p.pension)

    NE = P.NE
    NF = REL.NF
    tot_w = 0.0
    emo_shift = [0.0] * NE
    mean_q_price = 0.02
    q_inc_num = 0.0
    q_inc_den = 0.0
    pf_num = 0.0
    pf_den = 0.0
    bel_num = 0.0
    bel_den = 0.0
    old_assets_sum = {"under_30": 0.0, "30_59": 0.0, "60_plus": 0.0}
    old_debt_sum = {"under_30": 0.0, "30_59": 0.0, "60_plus": 0.0}
    old_band_w = {"under_30": 0.0, "30_59": 0.0, "60_plus": 0.0}

    for i in range(old_p.n):
        w = float(old_p.weight[i])
        tot_w += w
        for e in range(NE):
            emo_shift[e] += w * (float(old_p.emo[i * NE + e]) - float(old_p.emo_base[i * NE + e]))
        mean_q_price += w * float(old_p.q_price[i])
        if old_p.age[i] >= 18 and old_p.income[i] > 1.0:
            q_inc_num += w * (float(old_p.q_income[i]) / float(old_p.income[i]))
            q_inc_den += w
        if old_p.employment[i] in (P.EMP_REGULAR, P.EMP_NONREGULAR):
            pf_num += w * float(old_p.pay_factor[i])
            pf_den += w
        if old_p.belief_known[i * NF] == 1:
            bel_num += w * float(old_p.belief[i * NF])
            bel_den += w
        ab = age_band(old_p.age[i])
        old_assets_sum[ab] += w * float(old_p.assets[i])
        old_debt_sum[ab] += w * float(old_p.debt[i])
        old_band_w[ab] += w

    if tot_w > 0.0:
        for e in range(NE):
            emo_shift[e] /= tot_w
        mean_q_price /= tot_w
    q_inc_ratio = (q_inc_num / q_inc_den) if q_inc_den > 0.0 else 1.0
    mean_pay_factor = (pf_num / pf_den) if pf_den > 0.0 else 1.0
    mean_food_belief = (bel_num / bel_den) if bel_den > 0.0 else 0.0
    known_share = (bel_den / tot_w) if tot_w > 0.0 else 0.0
    old_food_scale = (
        old_p.food_plan() / max(1e-9, old_p.food_plan_start)
        if (not math.isnan(old_p.food_plan_start) and old_p.food_plan_start > 0.0)
        else 1.0
    )

    ps_new = Persons.create(c_id, seed_gen, st.cohort["JPN"], qx_2024, regions, n_per, cal_y)
    new_p = ps_new.p
    new_p.month = saved_month
    new_p.price_index = saved_price
    new_p.wage_index = saved_wage
    new_p.PENSION_AGE = saved_pension_age
    new_p.pension = saved_pension

    new_assets_sum = {"under_30": 0.0, "30_59": 0.0, "60_plus": 0.0}
    new_debt_sum = {"under_30": 0.0, "30_59": 0.0, "60_plus": 0.0}
    new_band_w = {"under_30": 0.0, "30_59": 0.0, "60_plus": 0.0}
    for i in range(new_p.n):
        w = float(new_p.weight[i])
        ab = age_band(new_p.age[i])
        new_assets_sum[ab] += w * float(new_p.assets[i])
        new_debt_sum[ab] += w * float(new_p.debt[i])
        new_band_w[ab] += w

    asset_scale = {}
    debt_scale = {}
    for ab in ("under_30", "30_59", "60_plus"):
        if old_band_w[ab] > 0.0 and new_band_w[ab] > 0.0 and new_assets_sum[ab] > 0.0:
            old_mean_a = old_assets_sum[ab] / old_band_w[ab]
            new_mean_a = new_assets_sum[ab] / new_band_w[ab]
            asset_scale[ab] = max(0.25, min(4.0 * saved_wage, old_mean_a / max(1.0, new_mean_a)))
        else:
            asset_scale[ab] = saved_wage
        if old_band_w[ab] > 0.0 and new_band_w[ab] > 0.0 and new_debt_sum[ab] > 0.0:
            old_mean_d = old_debt_sum[ab] / old_band_w[ab]
            new_mean_d = new_debt_sum[ab] / new_band_w[ab]
            debt_scale[ab] = max(0.25, min(4.0 * saved_price, old_mean_d / max(1.0, new_mean_d)))
        else:
            debt_scale[ab] = saved_wage

    ur_target = float(current_u) if current_u is not None else float(new_p.spec["unemployment_rate_start"]["value"])
    for i in range(new_p.n):
        a = new_p.age[i]
        ab = age_band(a)
        if a >= 65 and a < saved_pension_age and new_p.employment[i] == P.EMP_RETIRED:
            pa = new_p.spec["participation"]
            part = float(pa["male_15_64"]) if new_p.sex[i] == P.MALE else float(pa["female_15_64"])
            if new_p.u("part_pen", i) < part * 0.65:
                new_p.employment[i] = new_p._labour(i, ur_target)
        elif new_p.employment[i] in (P.EMP_REGULAR, P.EMP_NONREGULAR, P.EMP_UNEMPLOYED):
            new_p.employment[i] = new_p._labour(i, ur_target)
        if new_p.employment[i] in (P.EMP_REGULAR, P.EMP_NONREGULAR):
            new_p.pay_factor[i] = mean_pay_factor

        new_p.repay(i)
        new_p.q_income[i] = new_p.income[i] * q_inc_ratio
        new_p.q_price[i] = mean_q_price
        new_p.q_job[i] = 1.0 if new_p.employment[i] in (P.EMP_REGULAR, P.EMP_NONREGULAR) else 0.0
        new_p.assets[i] = float(new_p.assets[i]) * asset_scale[ab]
        new_p.debt[i] = float(new_p.debt[i]) * debt_scale[ab]

        if new_p.u("repl_bel", i) < known_share:
            new_p.belief_known[i * NF] = 1
            new_p.belief[i * NF] = mean_food_belief

    _ranks(new_p)
    for i in range(new_p.n):
        for e in range(NE):
            new_p.emo[i * NE + e] = min(0.98, max(0.02, float(new_p.emo_base[i * NE + e]) + emo_shift[e]))
        new_p._deficits(i)
        new_p.pressure_prev[i] = new_p.pressure(i)

    new_p.food_plan_start = new_p.food_plan() / max(1e-9, old_food_scale)
    return ps_new


# Declared (T) shock transmission constants (Roadmap P4, blueprint S4).
ENERGY_IMPORT_SHARE = 0.22         # mineral fuels' share of imports (MOF 2023, rounded)
ENERGY_CPI_PASS_PER_PCT = 0.00015  # +50% energy import prices ~ +0.75pt CPI while active (partial pass-through)


# Foreign-resident stock shares by origin (Immigration Services Agency,
# 在留外国人統計 2024-06, via links_2024 people block; rounded, sums to 1)
# and the SSW-sending origins among them.
ORIGIN_SHARES = {"CHN": 0.229, "VNM": 0.167, "KOR": 0.114, "PHL": 0.090,
                 "NPL": 0.065, "BRA": 0.059, "IDN": 0.042, "OTHER": 0.234}
SSW_ORIGINS = ("VNM", "PHL", "IDN", "NPL")


class ShockEngine:
    """Deterministic scheduled shocks (blueprint stage S4).

    A schedule is data: a list of {"kind", "start": [year, month],
    "months": duration, "mag": magnitude} specs, with kind-specific
    fields ("hazard_x", "mig_scale" for pandemics). The same schedule
    always produces the same episode - reproducibility is a property of
    the schedule, so seeded libraries sample schedules (see
    agent_env.random_shock_schedule) rather than sampling inside the
    engine. Kinds and transmissions (all magnitudes in percent):

    - energy_price: import prices +mag%. CPI pass-through premium while
      active; the energy import bill rises at activation and the GDP
      level takes the terms-of-trade loss; both reverse at expiry.
    - food_price: food prices +mag%. A food-inflation premium while
      active (flows into discontent, approval, Persons' food demand).
    - disaster: a one-off GDP level loss of mag% (capital destruction,
      NOT reversed) plus a discontent premium while active.
    - foreign_recession: exports to the USA fall mag% (via the P2 lane;
      activation/expiry symmetric, GDP follows the net-export impulse).
    - pandemic: GDP level -mag% (reversed at expiry in this version),
      mortality hazard x (1 + hazard_x) while active, net migration
      scaled by mig_scale while active, discontent premium.
    """

    def __init__(self, schedule):
        self.specs = []
        for i, s in enumerate(schedule or []):
            y, m = s["start"]
            self.specs.append({
                "id": i, "kind": str(s["kind"]),
                "start_mi": (int(y) - 2025) * 12 + int(m),
                "months": int(s.get("months", 12)),
                "mag": float(s.get("mag", 0.0)),
                "hazard_x": float(s.get("hazard_x", 0.0)),
                "mig_scale": float(s.get("mig_scale", 1.0)),
                "partner": str(s.get("partner", "USA")),
            })
        self.applied = {}
        self._hazard_saved = None

    def _active(self, month_idx):
        return [s for s in self.specs if s["start_mi"] <= month_idx < s["start_mi"] + s["months"]]

    def on_month(self, month_idx, st, tracker, year_notes):
        prem = {"cpi": 0.0, "food": 0.0, "discontent": 0.0}
        active = self._active(month_idx)
        active_ids = {s["id"] for s in active}
        for sid in list(self.applied.keys()):
            if sid not in active_ids:
                self._reverse(st, tracker, self.applied.pop(sid))
        for s in active:
            if s["id"] not in self.applied:
                self.applied[s["id"]] = self._activate(st, tracker, s, year_notes)
        mig = 1.0
        for s in active:
            if s["kind"] == "energy_price":
                prem["cpi"] += ENERGY_CPI_PASS_PER_PCT * s["mag"]
            elif s["kind"] == "food_price":
                prem["food"] += s["mag"] / 100.0
            elif s["kind"] == "disaster":
                prem["discontent"] += 0.03
            elif s["kind"] == "pandemic":
                prem["discontent"] += 0.05
                mig *= s["mig_scale"]
        tracker["mig_scale"] = mig
        st.shock_active = [
            {"kind": s["kind"], "mag": s["mag"],
             "until_year": 2025 + (s["start_mi"] + s["months"] - 2) // 12,
             "until_month": (s["start_mi"] + s["months"] - 2) % 12 + 1}
            for s in active
        ]
        return prem

    def _activate(self, st, tracker, s, year_notes):
        iv = st.ind["JPN"]
        note = {"kind": s["kind"], "gdp_frac": 0.0, "lane_delta": 0.0, "imp_delta": 0.0}
        year_notes.append(f"Shock {s['kind']}")
        if s["kind"] == "energy_price":
            d_imp = iv["imports_customs"] * ENERGY_IMPORT_SHARE * s["mag"] / 100.0
            iv["imports_customs"] += d_imp
            frac = -d_imp / max(1.0, tracker["init_gdp"])
            tracker["last_gdp"] *= (1.0 + frac)
            note.update({"imp_delta": d_imp, "gdp_frac": frac})
        elif s["kind"] == "disaster":
            frac = -s["mag"] / 100.0
            tracker["last_gdp"] *= (1.0 + frac)
            note.update({"gdp_frac": frac, "permanent": True})
        elif s["kind"] == "foreign_recession":
            partner = s.get("partner", "USA")
            lane_key = LANE_KEYS.get(partner)
            if lane_key and st.has(partner):
                lane = st.aux["JPN"]["trade_by_partner"][lane_key]
                d = -float(lane["exports_bn_jpy"]) * s["mag"] / 100.0
                lane["exports_bn_jpy"] += d
                iv["exports_customs"] += d
                frac = d / max(1.0, tracker["init_gdp"])
                tracker["last_gdp"] *= (1.0 + frac)
                note.update({"lane_delta": d, "gdp_frac": frac, "lane_key": lane_key, "partner": partner})
        elif s["kind"] == "pandemic":
            frac = -s["mag"] / 100.0
            tracker["last_gdp"] *= (1.0 + frac)
            note["gdp_frac"] = frac
            if s["hazard_x"] > 0.0 and self._hazard_saved is None:
                self._hazard_saved = list(st.hazard["JPN"])
                hz = st.hazard["JPN"]
                for i in range(len(hz)):
                    hz[i] = hz[i] * (1.0 + s["hazard_x"])
                note["hazard"] = True
        return note

    def _reverse(self, st, tracker, note):
        if note.get("permanent"):
            return
        iv = st.ind["JPN"]
        if note.get("imp_delta"):
            iv["imports_customs"] -= note["imp_delta"]
        if note.get("lane_delta"):
            st.aux["JPN"]["trade_by_partner"][note.get("lane_key", "USA")]["exports_bn_jpy"] -= note["lane_delta"]
            iv["exports_customs"] -= note["lane_delta"]
        if note.get("gdp_frac"):
            tracker["last_gdp"] /= (1.0 + note["gdp_frac"])
        if note.get("hazard") and self._hazard_saved is not None:
            hz = st.hazard["JPN"]
            for i in range(len(hz)):
                hz[i] = self._hazard_saved[i]
            self._hazard_saved = None


def _policy_obs(st, year, phase, row):
    """Observation for an external policy (agent) hook: the full indicator
    state, current lever values and bounds, and the last yearly summary row.
    Plain data only (dicts/lists/numbers), safe to serialise."""
    levers_def = st.levers["JPN"]["levers"]
    obs = {
        "year": year,
        "phase": phase,
        "indicators": dict(st.ind["JPN"]),
        "levers": dict(st.lever_value["JPN"]),
        "lever_bounds": {
            lid: {"min": L.get("min"), "max": L.get("max"), "unit": L.get("unit"), "status": L.get("status")}
            for lid, L in levers_def.items()
        },
        "trade_by_partner": {p: dict(v) for p, v in st.aux.get("JPN", {}).get("trade_by_partner", {}).items()},
        "shocks_active": list(getattr(st, "shock_active", [])),
        "row": row,
    }
    obs["migration_by_origin"] = {o: dict(v) for o, v in st.aux.get("JPN", {}).get("migration_by_origin", {}).items()}
    cps = {}
    for _code in COUNTERPARTS:
        if st.has(_code):
            cps[_code] = {
                "indicators": dict(st.ind[_code]),
                "levers": dict(st.lever_value[_code]),
                "trade_by_partner": {p: dict(v) for p, v in st.aux.get(_code, {}).get("trade_by_partner", {}).items()},
            }
    if cps:
        obs["counterpart"] = cps
    return obs


def _submit_policy_acts(st, cab, org, month, acts, pending_platform):
    """Submit agent lever acts through the same Cabinet/Diet path as the
    scenario lever plan. Bill/refused acts join pending_platform, so a later
    election majority can enact them exactly as with scenario levers."""
    results = []
    for lid, val in acts:
        _head = lid.split(":", 1)[0]
        if ":" in lid and _head in COUNTERPARTS:
            if st.has(_head):
                st.set_lever(_head, lid[len(_head) + 1:], float(val))
                results.append({"lever": lid, "value": float(val), "status": "executed",
                                "message": "FOREIGN_ACT (counterpart decision, no Diet path)"})
            else:
                results.append({"lever": lid, "value": float(val), "status": "rejected",
                                "message": f"counterpart {_head} not loaded"})
            continue
        code, msg = submit_policy_lever(st, cab, org, month, lid, float(val))
        if code in ("bill", "refused"):
            pending_platform[lid] = float(val)
        results.append({"lever": lid, "value": float(val), "status": code, "message": msg})
    return results


def _policy_call(policy_fn, st, cab, org, month, year, phase, row, pending_platform):
    obs = _policy_obs(st, year, phase, row)
    acts = policy_fn(obs) or []
    if isinstance(acts, dict):
        acts = list(acts.items())
    acts = [(str(lid), float(val)) for lid, val in acts]
    if not acts:
        return
    results = _submit_policy_acts(st, cab, org, month, acts, pending_platform)
    print("[Agent Policy %s] %s" % (year, " | ".join(
        "%s=%s -> %s" % (r["lever"], r["value"], r["status"].upper()) for r in results)))
    report = getattr(policy_fn, "report", None)
    if callable(report):
        report(year, phase, results)


def run_simulation(
    years=25,
    scenario="baseline",
    custom_levers=None,
    full_mode=False,
    n_per=2,
    coalition_pass=False,
    params_path=None,
    feedback_params=None,
    policy_fn=None,
    usa_tariff=None,
    chn_tariff=None,
    eu_tariff=None,
    shocks=None,
):
    ensure_oracle_dumps()
    params = load_feedback_params(params_path=params_path, overrides=feedback_params)
    shock_engine = ShockEngine(shocks) if shocks else None
    jp = params["fiscal_and_jgb"]
    rp = params["persons_replenishment"]

    mode_label = (
        "Full-Spectrum Realistic Closed-Loop (Status + Persons + EconMonth + Diet Bills + Elections <-> Demo/Fiscal Feedback)"
        if full_mode
        else "Standard Endogenous (Status + Persons + EconMonth + Diet Bills, Fixed 2024-12 Seats)"
    )
    print(f"\n[Sandvox Engine v4] Initializing {years}-year simulation ({years * 365} days / {years * 12} months)...")
    print(f"[Architecture] {mode_label}")
    t0 = time.time()

    # 1. Initialize Status (`status_2024.json` + `levers.json`) and align to `2025-01-01` (`start_2025.json`)
    st = Status()
    err = st.load(2024, ["JPN", "USA", "CHN", "EU"])
    # The sourced JPN customs surface lists EU member states individually,
    # so the bloc lane on the JPN side is created here from the EU
    # profile's (declared-estimate) mirror lane; the bilateral sync then
    # maintains it like every other lane.
    if st.has("EU"):
        _jp_lanes = st.aux.get("JPN", {}).get("trade_by_partner", {})
        _eu_mirror = st.aux.get("EU", {}).get("trade_by_partner", {}).get("JPN")
        if _eu_mirror is not None and "EU" not in _jp_lanes:
            _jp_lanes["EU"] = {"exports_bn_jpy": float(_eu_mirror["imports_bn_jpy"]),
                               "imports_bn_jpy": float(_eu_mirror["exports_bn_jpy"])}
    if err != "":
        raise RuntimeError(err)

    if "gdp_nominal" in st.trend_day["JPN"]:
        del st.trend_day["JPN"]["gdp_nominal"]

    c = country.load("JPN")
    p_2025, regions = create.inputs_2025("JPN", seed=1)
    co_2025 = p_2025.cohort
    qx_2024 = p_2025.qx
    _, old_75_init = align_initial_state_2025(st, c, co_2025)

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
    init_foreign_disp = int(round(st.value("JPN", "foreign_residents")))
    print(
        f"[Initial State] 2025-01-01 Population: {init_pop:,} (start_2025.json, ForeignRes: {init_foreign_disp:,}) | "
        f"65+%: {st.value('JPN', 'share_65plus')*100:.1f}% (75+%: {old_75_init/init_pop*100:.1f}%) | "
        f"TFR: {st.value('JPN', 'tfr'):.2f} | Debt/GDP: {st.value('JPN', 'debt_to_gdp')*100:.1f}%"
    )

    pending_platform = {}
    lever_logs_init = []
    for lid, val in lever_plan:
        if lid.startswith("USA:"):
            if st.has("USA"):
                st.set_lever("USA", lid[4:], float(val))
                lever_logs_init.append(f"{lid}={val} -> FOREIGN_ACT (counterpart decision)")
            continue
        status_code, msg = submit_policy_lever(st, cab, org, 0, lid, val, force_direct=coalition_pass)
        lever_logs_init.append(f"{lid}={val} -> {msg}")
        if status_code in ("bill", "refused"):
            pending_platform[lid] = float(val)

    if lever_logs_init:
        print("[Policy Levers] " + " | ".join(lever_logs_init))
    else:
        print("[Policy Levers] None (Baseline Status Quo)")

    for _code, _tv in (("USA", usa_tariff), ("CHN", chn_tariff), ("EU", eu_tariff)):
        if _tv is not None and st.has(_code):
            st.set_lever(_code, "tariff_on_jpn", float(_tv))
            print(f"[Counterpart] {_code} tariff_on_jpn={float(_tv)} (additional, over the 2024 baseline)")

    if policy_fn is not None:
        _policy_call(policy_fn, st, cab, org, 0, 2025, "initial", None, pending_platform)

    co_init = st.cohort["JPN"]
    init_wp_15_64 = sum(co_init[a * 2] + co_init[a * 2 + 1] for a in range(15, 65))
    init_65_74 = sum(co_init[a * 2] + co_init[a * 2 + 1] for a in range(65, 75))
    init_75_plus = sum(co_init[a * 2] + co_init[a * 2 + 1] for a in range(75, 101))
    init_weighted_old = (1.0 * init_65_74 + jp["old_75plus_cost_weight"] * init_75_plus) / st.ind["JPN"]["pop_total"]

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
        "us_tariff_prev": 0.0,
        "jp_tariff_prev": float(st.lever_value["JPN"]["tariff_rate_general"]),
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

        sync_bilateral_trade(st, tracker)

        bond_dep, share_75plus = sync_macro_fiscal_and_asfr(
            st, tracker, econ_infl, discontent, effective_food_yoy, real_wage_ratio, params=params
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

            # 3. Replenish micro households if multi-decade aging reduces sample size below min_sample_ratio
            min_n = max(int(rp["min_sample_abs"]), int(init_p_n * float(rp["min_sample_ratio"])))
            if ps.p.n < min_n:
                seed_gen += 1
                ps = replenish_persons_if_needed(
                    ps, c.id, st, qx_2024, regions, n_per, cal_y, seed_gen, current_u=econ.labour.u
                )

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
            fiscal_crisis = (bond_dep > jp["crisis_bond_dep_threshold"])
            if fiscal_crisis:
                econ_infl += jp["crisis_infl_premium"]
                food_yoy += jp["crisis_food_premium"]
            if "consumption_tax_rate" in applied_this_month:
                tax_jump = st.lever_value["JPN"]["consumption_tax_rate"] - 0.10
                econ_infl += max(0.0, tax_jump)
                food_yoy += max(0.0, tax_jump * jp["vat_food_passthrough"])

            fuel_sub_val = st.lever_value["JPN"].get("fuel_subsidy", 0.0)
            if fuel_sub_val > 0.0:
                fuel_k = float(st.levers["JPN"]["levers"]["fuel_subsidy"]["response"].get("k", 0.0))
                econ_infl += fuel_k * fuel_sub_val / 100.0

            shock_prem = None
            if shock_engine is not None:
                shock_prem = shock_engine.on_month(month_idx, st, tracker, year_notes)
                econ_infl += shock_prem["cpi"]
                food_yoy += shock_prem["food"]

            active_tax_burden = max(0.0, st.lever_value["JPN"]["consumption_tax_rate"] - 0.10)
            effective_food_yoy = food_yoy + (active_tax_burden * jp["vat_ongoing_food_bite"])
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
            if shock_prem is not None and shock_prem["discontent"]:
                discontent = min(1.0, discontent + shock_prem["discontent"])
            real_wage_ratio = econ.labour.wage_index / max(0.5, 1.0 + active_tax_burden)

            # 8. Step Public Approval & Elections -> Policy Feedback Loop
            du_pt = (econ.labour.u - unemp_prev) * 100.0
            unemp_prev = econ.labour.u
            ap = pub.step(month_idx, effective_food_yoy, du_pt, applied_this_month)
            ap = max(0.05, min(0.90, ap - (discontent - 0.20) * 0.25))
            st.ind["JPN"]["cabinet_approval"] = ap

            call_due = st.lever_value["JPN"].get("call_election", 0.0) >= 0.5
            if full_mode and ((cal_m == 10 and (cal_y - 2024) % 4 == 0) or call_due):
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
                if call_due:
                    st.lever_value["JPN"]["call_election"] = 0.0
                    year_notes.append("Election Called")
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
            fiscal_crisis = (bond_dep > jp["crisis_bond_dep_threshold"])
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
            if policy_fn is not None:
                _policy_call(policy_fn, st, cab, org, month_idx, cal_y, "year_end", history[-1], pending_platform)

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
    parser = argparse.ArgumentParser(description="Sandvox Endogenous Forward Policy Simulator CLI (v4.1)")
    parser.add_argument("--years", type=int, default=25, help="Simulation horizon in years (default: 25)")
    parser.add_argument("--scenario", type=str, default="baseline",
                        choices=["baseline", "child_splash", "migration_only", "synergy"],
                        help="Policy scenario preset")
    parser.add_argument("--full", action="store_true", help="Enable full parliamentary election cycles & policy feedback")
    parser.add_argument("--coalition", action="store_true", help="Assume cross-party coalition agreement from day 0")
    parser.add_argument("--n-per", type=int, default=2, help="Representative persons per prefecture (default: 2)")
    parser.add_argument("--params-file", type=str, default=None, help="Path to custom feedback_params.json override")
    parser.add_argument("--usa-tariff", type=float, default=None, help="Additional U.S. tariff on Japan (share, over the 2024 baseline)")
    parser.add_argument("--chn-tariff", type=float, default=None, help="Additional Chinese tariff on Japan (share, over the 2024 baseline)")
    parser.add_argument("--eu-tariff", type=float, default=None, help="Additional EU tariff on Japan (share, over the 2024 baseline)")
    parser.add_argument("--shocks-file", type=str, default=None, help="JSON file with a shock schedule (list of {kind, start [year, month], months, mag, ...})")

    args = parser.parse_args()
    run_simulation(
        years=args.years,
        scenario=args.scenario,
        full_mode=args.full,
        n_per=args.n_per,
        coalition_pass=args.coalition,
        params_path=args.params_file,
        usa_tariff=args.usa_tariff,
        chn_tariff=args.chn_tariff,
        eu_tariff=args.eu_tariff,
        shocks=(json.load(open(args.shocks_file)) if args.shocks_file else None),
    )


if __name__ == "__main__":
    main()
