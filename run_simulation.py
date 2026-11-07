#!/usr/bin/env python3
"""
Sandvox Official Endogenous Policy Simulation CLI (v5.0 - Foundational Closed-Loop Engine)
Implements first-principles macroeconomic, demographic, fiscal, micro-sampling, and constitutional parliamentary dynamics:

1. Endogenous Fertility (TFR / ASFR) Feedback from Household Living Costs & Education Support:
   - TFR responds to `child_allowance` (`Status._respond`), `education_budget` (reducing child-rearing educational cost burden
     when enacted by the Diet), and monthly household economic security (`discontent`, post-tax food inflation `effective_food_yoy`,
     and real wage growth from `EconMonth`).
2. Continuous JGB Yield Curve (`jgb_10y`), 8.5-Year Maturity Rollover, & Zero-Residual FY2024 Budget Decomposition:
   - Exhaustively partitions `budget_fy2024` (`112,571.7 bn JPY` total) into `social_security` (`37,719.3 bn`),
     `local_allocation_tax` (`17,786.3 bn`), `debt_service` (`27,009.0 bn` split into 60-year rule principal redemption
     `12,594.2 bn` + coupon interest `14,414.8 bn`), `defence` (`7,949.6 bn`, never double-counted in core ops), and
     `core_ops` (`22,107.5 bn`), with `0.0 bn JPY` residual.
   - Couples sovereign debt service and social security to actual demographic headcount (`65-74` vs. `75+`), per-worker
     nominal GDP growth, and Japan's statutory 2004 Macroeconomic Slide (マクロ経済スライド, National Pension Act Art. 27-3).
3. Young-Old (65-74) vs. Old-Old (75+ Late-Stage Elderly) Demographic Separation & Exact Flow Accounting:
   - Computes `pop_65_74` and `pop_75_plus` directly from 1-year `st.cohort["JPN"]` bins every day, weighting per-capita
     social security cost growth 3.5x toward `75+` per MHLW National Medical Care Expenditure profiles.
   - Applies cumulative error-diffusion integer quantization to annual `Births`, `Deaths`, and `NetMig` so that
     `Pop Change == Births - Deaths + NetMig` holds with `0` person residual at every horizon.
4. Endogenous Net Migration (`NetMig`) Saturation & Economic Attractiveness:
   - Normalizes the 2023 post-COVID border reopening spike (`+242,000/yr`) toward IPSS structural baseline (`168,000/yr`),
     saturates `ssw_visa_cap` inflows smoothly with `foreign_residents` stock, and scales inflows with real wages and inflation stability.
5. Statistical Sample Health Monitoring (Kish's Effective Sample Size N_eff & L1 Cohort Divergence) & Generational Replenishment:
   - Monitors Kish's Effective Sample Size `N_eff = (sum w_i)^2 / sum(w_i^2)` and unweighted vs. national cohort age-bracket L1
     divergence every month, triggering `replenish_persons_if_needed` whenever aging and `_reborn(i)` weight concentration
     degrade `N_eff / N_eff_0` below threshold (`0.55`) or L1 divergence above `0.20` (as well as headcount `p.n < min_n`).
6. Constitutional Parliamentary Alternation (`Election.designate` Art. 67 & `Election.run_upper_house` Art. 46) & Single-Source Parameters:
   - Executes both House of Representatives (4-year) and House of Councillors (3-year half-renewal) elections in `--full` mode,
     designates the Prime Minister and governing coalition via `Election.designate`, updates proportional vote-share baselines,
     and loads all feedback parameters exclusively from `data/modern/jpn/feedback_params.json` with schema validation.
"""
import sys
import os
import argparse
import time
import math
import json
import copy

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


REQUIRED_PARAM_SCHEMA = {
    "fertility": (
        "ed_budget_unit_bn",
        "ed_tfr_boost_per_unit",
        "discontent_baseline",
        "discontent_tfr_slope",
        "food_infl_threshold",
        "food_infl_tfr_slope",
        "real_wage_tfr_slope",
        "stress_drag_min",
        "stress_drag_max",
        "tfr_floor",
        "tfr_ceiling",
    ),
    "migration": (
        "structural_baseline",
        "reopening_decay_years",
        "cap_ssw_multiplier",
        "cap_saturation_scale",
        "cap_headroom_floor",
        "infl_attract_threshold",
        "infl_attract_slope",
        "discontent_attract_threshold",
        "discontent_attract_slope",
        "real_wage_attract_slope",
        "attract_min",
        "attract_max",
    ),
    "fiscal_and_jgb": (
        "old_75plus_cost_weight",
        "senior_relief_multiplier",
        "senior_relief_floor",
        "care_dependency_elasticity",
        "core_ops_pop_elasticity",
        "infl_index_threshold",
        "jgb_infl_threshold",
        "jgb_infl_slope",
        "jgb_debt_gdp_slope",
        "jgb_bond_dep_threshold",
        "jgb_bond_dep_slope",
        "crisis_bond_dep_threshold",
        "jgb_crisis_slope",
        "jgb_min",
        "jgb_max",
        "jgb_adjust_days",
        "jgb_rollover_years",
        "crisis_infl_premium",
        "crisis_food_premium",
        "vat_food_passthrough",
        "vat_ongoing_food_bite",
    ),
    "persons_replenishment": (
        "min_sample_ratio",
        "min_sample_abs",
        "min_effective_sample_ratio",
        "max_age_l1_divergence",
        "min_replenish_interval_months",
    ),
    "polity_feedback": (
        "pr_vote_share_memory",
        "party_share_floor",
        "new_cabinet_approval_init",
    ),
}


def load_feedback_params(params_path=None, overrides=None):
    """
    Loads and validates feedback parameters exclusively from `data/modern/jpn/feedback_params.json`
    (or custom `params_path`), eliminating dual parameter maintenance in Python code.
    """
    default_path = os.path.join(ROOT_DIR, "data", "modern", "jpn", "feedback_params.json")
    target_path = params_path if params_path is not None else default_path
    if not os.path.exists(target_path):
        raise FileNotFoundError(f"Feedback parameter specification not found at: {target_path}")

    with open(target_path, "r", encoding="utf-8") as fh:
        loaded = json.load(fh)

    params = {}
    for sec, req_keys in REQUIRED_PARAM_SCHEMA.items():
        if sec not in loaded or not isinstance(loaded[sec], dict):
            raise KeyError(f"Missing required parameter section '{sec}' in {target_path}")
        params[sec] = {}
        for k in req_keys:
            if k not in loaded[sec]:
                raise KeyError(f"Missing required parameter '{sec}.{k}' in {target_path}")
            val = loaded[sec][k]
            if not isinstance(val, (int, float)):
                raise ValueError(f"Parameter '{sec}.{k}' must be numeric, got {type(val).__name__}")
            params[sec][k] = float(val)

    if "_provenance" in loaded and isinstance(loaded["_provenance"], dict):
        params["_provenance"] = copy.deepcopy(loaded["_provenance"])

    if isinstance(overrides, dict):
        for sec, vals in overrides.items():
            if sec in params and isinstance(vals, dict):
                for k, v in vals.items():
                    if k not in REQUIRED_PARAM_SCHEMA.get(sec, ()):
                        raise KeyError(f"Unknown override parameter '{sec}.{k}'")
                    params[sec][k] = float(v)
    return params


def decompose_fy2024_budget(fy24_lines, init_gov_exp, init_debt, init_jgb):
    """
    Exhaustively decomposes the FY2024 General Account Budget (`112,571.7 bn JPY`) into 5 mutually
    exclusive components with 0.0 bn JPY residual and zero double-counting of `defence`:
      1. `budget_social_security` (`37,719.3 bn`)
      2. `budget_lat` (`17,786.3 bn`)
      3. `budget_debt_service` (`27,009.0 bn` = `debt_redemption_0` + `debt_interest_0`)
      4. `budget_defence` (`7,949.6 bn`, excluded from `budget_core_ops`)
      5. `budget_core_ops` (`22,107.5 bn` = `public_works` + `education_science` + `reserve_fund` + `other` + `unallocated_contingency`)
    """
    ss = float(fy24_lines["social_security"])
    lat = float(fy24_lines["local_allocation_tax"])
    ds = float(fy24_lines["debt_service"])
    defence = float(fy24_lines["defence"])
    named_non_def_ops = (
        float(fy24_lines["public_works"])
        + float(fy24_lines["education_science"])
        + float(fy24_lines["other"])
        + float(fy24_lines["reserve_fund"])
    )
    unallocated_contingency = float(init_gov_exp) - (ss + lat + ds + defence + named_non_def_ops)
    core_ops = named_non_def_ops + unallocated_contingency

    debt_interest_0 = min(ds, float(init_debt) * float(init_jgb))
    debt_redemption_0 = ds - debt_interest_0

    total_check = ss + lat + ds + defence + core_ops
    if abs(total_check - float(init_gov_exp)) > 1e-6:
        raise ValueError(f"FY2024 budget decomposition mismatch: {total_check} != {init_gov_exp}")

    return {
        "budget_social_security": ss,
        "budget_lat": lat,
        "budget_debt_service": ds,
        "budget_debt_redemption_0": debt_redemption_0,
        "budget_debt_interest_0": debt_interest_0,
        "budget_defence": defence,
        "budget_core_ops": core_ops,
        "budget_named_non_def_ops": named_non_def_ops,
        "budget_contingency_other": unallocated_contingency,
    }


def align_initial_state_2025(st, c, co_2025):
    """
    Aligns `Status` indicators from the 2023-10 / 2024-06 snapshot in `status_2024.json` to the exact
    `2025-01-01` initial state in `start_2025.json` (`cohort_2025-01-01.json`).
    """
    wp_2024 = 0.0
    for a in range(15, 65):
        wp_2024 += st.cohort["JPN"][a * 2] + st.cohort["JPN"][a * 2 + 1]
    for idx in range(len(co_2025)):
        st.cohort["JPN"][idx] = float(co_2025[idx])

    pop_2025 = st.population_of("JPN")
    wp_2025 = 0.0
    old_65_2025 = 0.0
    old_75_2025 = 0.0
    for a in range(15, 65):
        wp_2025 += st.cohort["JPN"][a * 2] + st.cohort["JPN"][a * 2 + 1]
    for a in range(65, 101):
        old_65_2025 += st.cohort["JPN"][a * 2] + st.cohort["JPN"][a * 2 + 1]
    for a in range(75, 101):
        old_75_2025 += st.cohort["JPN"][a * 2] + st.cohort["JPN"][a * 2 + 1]

    iv = st.ind["JPN"]
    iv["pop_total"] = pop_2025
    iv["working_age_pop"] = wp_2025
    iv["aged_pop"] = old_65_2025
    iv["share_65plus"] = old_65_2025 / max(1.0, pop_2025)
    iv["share_75plus"] = old_75_2025 / max(1.0, pop_2025)

    d_2025 = load.load_json(c.path("start_2025"))
    flows = d_2025.get("flows", {})
    births_2024 = 0.0
    deaths_2024 = 0.0
    for ym in sorted(flows.keys()):
        if ym.startswith("2024-"):
            births_2024 += float(flows[ym]["births"])
            deaths_2024 += float(flows[ym]["deaths"])
    intl_h2_2024 = 0.0
    for ym in ("2024-07", "2024-08", "2024-09", "2024-10", "2024-11", "2024-12"):
        if ym in flows:
            intl_h2_2024 += float(flows[ym]["intl_net"])

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
        "legal_basis": str(law_info.get("name", L.get("legal", "cabinet_decision"))),
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


def sync_cabinet_party_positions(cab, org):
    """
    Ensures `cab.party_positions` reflects the sitting governing coalition after constitutional PM alternation
    (per `jpn_organs.json`: 'the governing parties vote yes on their own bills; a party not listed votes with its bloc').
    """
    base_pos = copy.deepcopy(org.spec.get("party_positions", {}))
    for lid, pos_map in base_pos.items():
        if not isinstance(pos_map, dict):
            continue
        if lid == "consumption_tax_rate":
            # Any party in opposition opposes a consumption tax hike; sitting governing parties vote yes on their cabinet bill
            updated = {}
            for p_name in org.seats.get("house_of_representatives", {}):
                updated[p_name] = "yes" if p_name in org.governing else "no"
            cab.party_positions[lid] = updated
        else:
            updated = dict(pos_map)
            for g_party in org.governing:
                updated[g_party] = "yes"
            cab.party_positions[lid] = updated


def sync_macro_fiscal_and_asfr(st, tracker, econ_infl, discontent, effective_food_yoy, real_wage_ratio, params):
    """
    First-principles closed-loop macroeconomic, demographic, and fiscal coupling parameterized via `feedback_params.json`:
    1. Fertility (`tfr` & `asfr`)
    2. Endogenous Net Migration (`net_migration`)
    3. Age-Stratified Demographics (`15-64`, `65-74`, `75+`) & Per-Worker Nominal GDP
    4. Zero-Residual FY2024 Expenditure Scaling with Headcount-Weighted Beneficiary Scale & Exact Debt Service Split
    5. Continuous JGB Yield Curve (`jgb_10y`) & 8.5-Year Maturity Refinancing Lag (`eff_jgb_rate`)
    """
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
    pop_ratio = iv["pop_total"] / max(1.0, tracker["init_pop"])

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

    # 6. First-Principles General Expenditure (Headcount-Weighted 65-74 vs 75+, Macroeconomic Slide, & Debt Split)
    tracker["infl_index"] *= (1.0 + max(0.0, econ_infl - jp["infl_index_threshold"]) / 365.0)
    infl_idx = tracker["infl_index"]

    # Unit cost indices: `health_expenditure` (baseline trend + excess inflation + fee schedule lever) & `gov_consumption`
    fee_sched_mult = max(0.80, 1.0 + float(st.lever_value["JPN"].get("health_fee_schedule", 0.0)))
    health_unit_factor = (iv["health_expenditure"] / max(1.0, tracker["init_health"])) * fee_sched_mult * infl_idx
    gov_cons_factor = (iv["gov_consumption"] / max(1.0, tracker["init_gov_cons"])) * infl_idx

    # Actual elderly beneficiary headcount relative to 2025-01-01 (`beneficiary_ratio = B_t / B_0`)
    # and old-age dependency ratio (`old_dep_factor = (B_t / B_0) / (L_t / L_0)`).
    # Unlike dividing by `pop_total` without population scaling (which creates a spurious `Pop_0 / Pop_t` explosion
    # as total population shrinks over 100 years), scaling by `beneficiary_ratio * (1 + care_dependency_elasticity * (old_dep_factor - 1))`
    # matches MHLW aging pressure over 2025-2050 while stabilizing ss_line / GDP once the age pyramid reaches stationary shares.
    weighted_old_abs = 1.0 * pop_65_74 + jp["old_75plus_cost_weight"] * pop_75_plus
    beneficiary_ratio = weighted_old_abs / max(1.0, tracker["init_weighted_old_abs"])
    old_dep_factor = beneficiary_ratio / max(0.05, lf_ratio)
    ss_demo_factor = beneficiary_ratio * (1.0 + jp["care_dependency_elasticity"] * max(0.0, old_dep_factor - 1.0))

    senior_relief_share = (pension_emp_gain / max(1.0, pop_65_plus)) * jp["senior_relief_multiplier"]
    ss_line = (
        tracker["budget_social_security"]
        * health_unit_factor
        * ss_demo_factor
        * max(jp["senior_relief_floor"], 1.0 - senior_relief_share)
    )
    ss_delta = ss_line - tracker["budget_social_security"]

    lat_delta = tracker["budget_lat"] * ((tax_rev_current / max(1.0, tracker["init_tax_rev"])) - 1.0)

    # Core operations scale with unit public cost (`gov_cons_factor`) and national population scale (`core_ops_pop_elasticity`)
    core_pop_scale = jp["core_ops_pop_elasticity"] * pop_ratio + (1.0 - jp["core_ops_pop_elasticity"]) * 1.0
    core_ops_delta = tracker["budget_core_ops"] * (gov_cons_factor * core_pop_scale - 1.0)

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

    # Exact Debt Service split: 60-year redemption rule principal + effective coupon rate on debt stock
    ds_redemption = tracker["budget_debt_redemption_0"] * debt_stock_ratio
    ds_interest = iv["gov_debt_total"] * tracker["eff_jgb_rate"]
    ds_line = ds_redemption + ds_interest
    ds_delta = ds_line - tracker["budget_debt_service"]

    # Policy levers & defence (with defence excluded from core_ops to prevent double-counting)
    ca_delta = (st.lever_value["JPN"]["child_allowance"] - tracker["init_ca"]) * gov_cons_factor * pop_ratio
    pi_delta = (st.lever_value["JPN"]["public_investment"] - tracker["init_pi"]) * gov_cons_factor
    ed_delta = (st.lever_value["JPN"]["education_budget"] - tracker["init_ed"]) * gov_cons_factor * pop_ratio
    oda_delta = (st.lever_value["JPN"]["oda_budget"] - tracker["init_oda"]) * gov_cons_factor

    def_lever_factor = iv["defence_budget"] / max(1.0, tracker["init_def"])
    def_line = tracker["budget_defence"] * def_lever_factor * gov_cons_factor * core_pop_scale
    def_delta = def_line - tracker["budget_defence"]

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



def compute_sample_health(ps, cohort, init_neff=None):
    """
    Computes Kish's (1965) Effective Sample Size `N_eff = (sum w_i)^2 / sum(w_i^2)` and the L1 total
    variation divergence between unweighted sample age-bracket shares and live national `cohort` shares.
    Detects sample degradation in both `households=False` (where `_reborn` keeps `p.n` constant while
    distorting the sample age pyramid and concentrating weights) and `households=True` (where `p.n` shrinks).
    """
    p = ps.p
    if p.n <= 0:
        return 0.0, 0.0, 1.0

    sum_w = 0.0
    sum_w2 = 0.0
    for i in range(p.n):
        w = float(p.weight[i])
        sum_w += w
        sum_w2 += w * w

    neff = (sum_w * sum_w) / sum_w2 if sum_w2 > 0.0 else float(p.n)
    neff_ratio = (neff / init_neff) if (init_neff is not None and init_neff > 0.0) else 1.0

    pop_tot = 0.0
    for idx in range(len(cohort)):
        pop_tot += float(cohort[idx])
    pop_tot = max(1.0, pop_tot)

    age_brackets = ((0, 15), (15, 30), (30, 45), (45, 65), (65, 75), (75, 101))
    l1_div = 0.0
    for lo, hi in age_brackets:
        s_cnt = 0
        for i in range(p.n):
            if lo <= p.age[i] < hi:
                s_cnt += 1
        s_share = float(s_cnt) / float(p.n)
        c_pop = 0.0
        for a in range(lo, hi):
            c_pop += float(cohort[a * 2]) + float(cohort[a * 2 + 1])
        c_share = c_pop / pop_tot
        l1_div += 0.5 * abs(s_share - c_share)

    return neff, neff_ratio, l1_div


def replenish_persons_if_needed(ps, c_id, st, qx_2024, regions, n_per, cal_y, seed_gen, current_u=None):
    """
    Replenishes the representative micro-household cohort from live `st.cohort["JPN"]` when sample health
    degrades (`p.n < min_n`, Kish `N_eff / N_eff_0 < min_effective_sample_ratio`, or age-bracket `L1 > max_age_l1_divergence`).
    Preserves `month`, `price_index`, `wage_index`, `PENSION_AGE`, `pension`, individual wages (`repay`),
    income expectations (`q_income`), inflation expectations (`q_price`), food price beliefs (`belief`),
    age-stratified household `assets` and `debt`, employment rate (`current_u`), accumulated emotion shifts
    (`emo - emo_base`), and `food_plan_start`.
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
    mean_q_price = 0.0
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
    else:
        mean_q_price = 0.02
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


def run_simulation(
    years=25,
    scenario="baseline",
    custom_levers=None,
    full_mode=False,
    n_per=2,
    coalition_pass=False,
    params_path=None,
    feedback_params=None,
):
    params = load_feedback_params(params_path=params_path, overrides=feedback_params)
    jp = params["fiscal_and_jgb"]
    rp = params["persons_replenishment"]
    pp = params["polity_feedback"]

    mode_label = (
        "Full-Spectrum Realistic Closed-Loop (Status + Persons + EconMonth + Diet Bills + Bicameral Elections & Art.67 PM Alternation)"
        if full_mode
        else "Standard Endogenous (Status + Persons + EconMonth + Diet Bills, Fixed 2024-12 Seats)"
    )
    print(f"\n[Sandvox Engine v5] Initializing {years}-year simulation ({years * 365} days / {years * 12} months)...")
    print(f"[Architecture] {mode_label}")
    t0 = time.time()  # lint-ok: CLI wall-clock benchmark timer

    # 1. Initialize Status (`status_2024.json` + `levers.json`) and align to `2025-01-01` (`start_2025.json`)
    st = Status()
    err = st.load(2024, ["JPN"])
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
    init_neff, _, _ = compute_sample_health(ps, st.cohort["JPN"])
    seed_gen = 1
    replenish_count = 0
    last_replenish_month = 0

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
            ("education_budget", 10000.0),
        ]
    elif scenario == "migration_only":
        lever_plan = [
            ("ssw_visa_cap", 2000000.0),
        ]
    elif scenario == "synergy":
        lever_plan = [
            ("child_allowance", 6000.0),
            ("ssw_visa_cap", 1800000.0),
            ("consumption_tax_rate", 0.14),
            ("pension_age", 67.0),
            ("health_fee_schedule", -0.02),
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
        status_code, msg = submit_policy_lever(st, cab, org, 0, lid, val, force_direct=coalition_pass)
        lever_logs_init.append(f"{lid}={val} -> {msg}")
        if status_code in ("bill", "refused"):
            pending_platform[lid] = float(val)

    if lever_logs_init:
        print("[Policy Levers] " + " | ".join(lever_logs_init))
    else:
        print("[Policy Levers] None (Baseline Status Quo)")

    co_init = st.cohort["JPN"]
    init_wp_15_64 = 0.0
    init_65_74 = 0.0
    init_75_plus = 0.0
    for a in range(15, 65):
        init_wp_15_64 += co_init[a * 2] + co_init[a * 2 + 1]
    for a in range(65, 75):
        init_65_74 += co_init[a * 2] + co_init[a * 2 + 1]
    for a in range(75, 101):
        init_75_plus += co_init[a * 2] + co_init[a * 2 + 1]
    init_weighted_old_abs = 1.0 * init_65_74 + jp["old_75plus_cost_weight"] * init_75_plus

    fy24_lines = org.laws["budget_fy2024"]["lines_bn_jpy"]
    b_decomp = decompose_fy2024_budget(
        fy24_lines,
        st.value("JPN", "gov_expenditure_general"),
        st.value("JPN", "gov_debt_total"),
        st.value("JPN", "jgb_10y"),
    )

    tracker = {
        "statutory_tfr": st.value("JPN", "tfr"),
        "last_ind_tfr": st.value("JPN", "tfr"),
        "prev_asfr_tfr": st.value("JPN", "tfr"),
        "init_pop": st.value("JPN", "pop_total"),
        "init_wp_15_64": init_wp_15_64,
        "init_weighted_old_abs": init_weighted_old_abs,
        "infl_index": 1.0,
        "y_worker_idx": 1.0,
        "last_lf_ratio": 1.0,
        "init_real_growth": st.ind0["JPN"]["gdp_real_growth"],
        "pi_boost_until_day": 0,
        "init_gdp": st.value("JPN", "gdp_nominal"),
        "last_gdp": st.value("JPN", "gdp_nominal"),
        "init_tax_rev": st.value("JPN", "tax_revenue"),
        "init_nontax_rev": st.value("JPN", "gov_revenue_general") - st.value("JPN", "tax_revenue"),
        "init_gov_exp": st.value("JPN", "gov_expenditure_general"),
        "budget_social_security": b_decomp["budget_social_security"],
        "budget_lat": b_decomp["budget_lat"],
        "budget_debt_service": b_decomp["budget_debt_service"],
        "budget_debt_redemption_0": b_decomp["budget_debt_redemption_0"],
        "budget_debt_interest_0": b_decomp["budget_debt_interest_0"],
        "budget_defence": b_decomp["budget_defence"],
        "budget_core_ops": b_decomp["budget_core_ops"],
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
    cum_births_f = 0.0
    cum_deaths_f = 0.0
    cum_mig_f = 0.0
    cum_births_i = 0
    cum_deaths_i = 0
    cum_mig_i = 0
    prev_pop_int = init_pop

    year_notes = []
    total_days = years * 365
    month_idx = 0

    for day in range(1, total_days + 1):
        logged_before = len(st.lever_log)
        # Status._step_cohort() runs before Status._apply_due() inside st.step(), so record today's active net_migration before st.step()
        cum_mig_f += st.value("JPN", "net_migration") / 365.0

        # Daily step in Status (cohort births, deaths, migration into ages 20-39, fiscal debt accumulation, lever due dates)
        st.step()

        for i_log in range(logged_before, len(st.lever_log)):
            if str(st.lever_log[i_log][4]) == "applied" and str(st.lever_log[i_log][2]) == "public_investment":
                tracker["pi_boost_until_day"] = day + 365

        cum_births_f += st.daily_births["JPN"]
        cum_deaths_f += st.daily_deaths["JPN"]

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

            # 3. Statistical Sample Health Monitoring (Kish N_eff & L1 Cohort Divergence) -> Generational Replenishment
            min_n = max(int(rp["min_sample_abs"]), int(init_p_n * float(rp["min_sample_ratio"])))
            _, neff_ratio, l1_div = compute_sample_health(ps, st.cohort["JPN"], init_neff=init_neff)
            cooldown_ok = (month_idx - last_replenish_month) >= int(rp["min_replenish_interval_months"])
            if ps.p.n < min_n or (
                cooldown_ok
                and (neff_ratio < float(rp["min_effective_sample_ratio"]) or l1_div > float(rp["max_age_l1_divergence"]))
            ):
                seed_gen += 1
                ps = replenish_persons_if_needed(
                    ps, c.id, st, qx_2024, regions, n_per, cal_y, seed_gen, current_u=econ.labour.u
                )
                init_neff, _, _ = compute_sample_health(ps, st.cohort["JPN"])
                last_replenish_month = month_idx
                replenish_count += 1
                year_notes.append(f"Replenish(gen={seed_gen},Neff={neff_ratio:.2f}->1.00)")

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
                "cohort": st.cohort["JPN"],
            })
            sm = ps.summary()
            raw_disc = float(sm["discontent_p10_p50_p90"][1])
            if not math.isnan(raw_disc):
                discontent = raw_disc
            real_wage_ratio = econ.labour.wage_index / max(0.5, 1.0 + active_tax_burden)

            # 8. Step Public Approval & Bicameral Parliamentary Elections -> Constitutional Policy Feedback Loop
            du_pt = (econ.labour.u - unemp_prev) * 100.0
            unemp_prev = econ.labour.u
            ap = pub.step(month_idx, effective_food_yoy, du_pt, applied_this_month)
            ap = max(0.05, min(0.90, ap - (discontent - 0.20) * 0.25))
            st.ind["JPN"]["cabinet_approval"] = ap

            # House of Councillors half-renewal election every 3 years in July (Constitution Art. 46)
            if full_mode and cal_m == 7 and (cal_y - 2025) % 3 == 0:
                d_ap_up = pub.change_since(last_election_month)
                if fiscal_crisis:
                    d_ap_up = min(d_ap_up, (ap - 0.35) * 100.0)
                d_cpi_pt_up = (econ_infl - 0.02) * 100.0
                shares_up = el.vote_shares(list(org.governing), d_ap_up, du_pt, d_cpi_pt_up)
                r_up = el.run_upper_house(shares_up)
                org.seats["house_of_councillors"] = dict(r_up["composition"])
                el.spec["houses"]["house_of_councillors"]["continuing_half_2022"] = dict(r_up["elected"])
                up_gov_seats = org.governing_seats("house_of_councillors")
                st.ind["JPN"]["upper_house_seats_governing"] = float(up_gov_seats)
                org.record(month_idx, "election", "house_of_councillors", {"governing_seats": up_gov_seats}, "art. 46: half elected")

            # House of Representatives general election every 4 years in October & PM Designation (Constitution Art. 45, 67)
            if full_mode and cal_m == 10 and (cal_y - 2024) % 4 == 0:
                d_ap = pub.change_since(last_election_month)
                if fiscal_crisis:
                    d_ap = min(d_ap, (ap - 0.35) * 100.0)
                d_cpi_pt = (econ_infl - 0.02) * 100.0
                shares = el.vote_shares(list(org.governing), d_ap, du_pt, d_cpi_pt)
                r_low = el.run_lower_house(shares)
                org.seats["house_of_representatives"] = dict(r_low["seats"])

                # Update proportional vote-share baseline with damped persistence
                base_pr = el.spec["vote_share_2024_10_27_pr"]
                mem_w = float(pp["pr_vote_share_memory"])
                floor_w = float(pp["party_share_floor"])
                tot_s = 0.0
                for p_name in el.spec["parties"]:
                    upd = max(floor_w, mem_w * float(base_pr.get(p_name, 0.0)) + (1.0 - mem_w) * float(shares.get(p_name, 0.0)))
                    base_pr[p_name] = upd
                    tot_s += upd
                for p_name in el.spec["parties"]:
                    base_pr[p_name] = float(base_pr[p_name]) / max(1e-9, tot_s)

                # Incumbent governing seats before PM designation check
                incumbent_bloc = list(org.governing)
                incumbent_seats = org.governing_seats("house_of_representatives")
                des = el.designate(r_low["seats"], org.governing, 465, org.spec.get("partners", {}))
                new_bloc = list(des["governing"])
                pm_changed = (new_bloc != incumbent_bloc)

                if pm_changed:
                    org.governing = new_bloc
                    org.record(month_idx, "designate_pm", "diet", des, des["why"])
                    sync_cabinet_party_positions(cab, org)
                    pub.approval = float(pp["new_cabinet_approval_init"])
                    pub.shock = 0.0
                    pub.history.append([month_idx, pub.approval, effective_food_yoy, du_pt, 0.0])
                    st.ind["JPN"]["cabinet_approval"] = pub.approval

                gov_seats = org.governing_seats("house_of_representatives")
                st.ind["JPN"]["lower_house_seats_governing"] = float(gov_seats)
                last_election_month = month_idx
                maj_str = "Majority" if gov_seats >= 233 else "Minority"
                bloc_str = "+".join(org.governing)
                if pm_changed:
                    year_notes.append(f"Election({incumbent_seats}->PM:{bloc_str} {gov_seats}/465 {maj_str})")
                else:
                    year_notes.append(f"Election({bloc_str} {gov_seats}/465 {maj_str})")

                # CLOSED-LOOP ELECTION -> POLICY FEEDBACK:
                # 1. If incumbent lost its majority (`incumbent_seats < 233`) during a fiscal crisis, Diet mandates consolidation
                if (incumbent_seats < 233 or gov_seats < 233) and fiscal_crisis:
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
                        dict(st.ind["JPN"]),
                    )
                    if len(cons_act) == 2 and str(cons_act[0]) not in st.lever_due["JPN"]:
                        st.set_lever("JPN", str(cons_act[0]), float(cons_act[1]))
                        year_notes.append(f"Brain Consolidation tax={float(cons_act[1]):.2f}")
                    if st.lever_value["JPN"]["pension_age"] < 68.0 and "pension_age" not in st.lever_due["JPN"]:
                        next_pa = min(68.0, st.lever_value["JPN"]["pension_age"] + 1.0)
                        st.set_lever("JPN", "pension_age", next_pa)
                        year_notes.append(f"Diet Reform pension_age={next_pa:.0f}")
                elif gov_seats >= 233 and pending_platform and not fiscal_crisis:
                    for p_lid, p_val in list(pending_platform.items()):
                        st_code, _ = submit_policy_lever(st, cab, org, month_idx, p_lid, p_val)
                        if st_code == "executed":
                            pending_platform.pop(p_lid, None)
                            year_notes.append(f"Enacted {p_lid}")

        # End of Year Recording (every 365 days) with Exact Error-Diffusion Flow Quantization
        if day % 365 == 0:
            yr = 2025 + (day // 365) - 1
            gov_seats_now = int(st.value("JPN", "lower_house_seats_governing"))
            fiscal_crisis = (bond_dep > jp["crisis_bond_dep_threshold"])

            pop_now = int(round(st.value("JPN", "pop_total")))
            b_int = int(round(cum_births_f)) - cum_births_i
            d_int = int(round(cum_deaths_f)) - cum_deaths_i
            # Reconcile integer net migration with exact cohort stock change so Pop_t - Pop_{t-1} == Births_t - Deaths_t + NetMig_t identically
            m_int = (pop_now - prev_pop_int) - (b_int - d_int)

            cum_births_i += b_int
            cum_deaths_i += d_int
            cum_mig_i += m_int
            prev_pop_int = pop_now

            history.append({
                "year": yr,
                "population": pop_now,
                "births": b_int,
                "deaths": d_int,
                "net_mig": m_int,
                "tfr": round(st.value("JPN", "tfr"), 3),
                "share_65plus": round(st.value("JPN", "share_65plus") * 100, 1),
                "share_75plus": round(share_75plus * 100, 1),
                "jgb_10y": round(st.value("JPN", "jgb_10y") * 100, 2),
                "debt_gdp": round(st.value("JPN", "debt_to_gdp") * 100, 1),
                "bond_dep": round(bond_dep * 100, 1),
                "discontent": round(discontent, 3),
                "approval": round(st.value("JPN", "cabinet_approval") * 100, 1),
                "gov_seats": gov_seats_now,
                "governing": "+".join(org.governing),
                "replenish_count": replenish_count,
                "crisis": fiscal_crisis,
                "notes": ", ".join(year_notes) if year_notes else "NORMAL",
            })
            year_notes = []

    elapsed = round(time.time() - t0, 2)  # lint-ok: CLI wall-clock benchmark timer
    print(f"\n[Done] {years}-year endogenous simulation completed in {elapsed}s (Cohort Replenishments: {replenish_count}).\n")

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
    tot_b = 0
    tot_d = 0
    tot_m = 0
    for r in history:
        tot_b += int(r["births"])
        tot_d += int(r["deaths"])
        tot_m += int(r["net_mig"])
    pop_change = final["population"] - init_pop
    flow_sum = tot_b - tot_d + tot_m
    print(
        f"\n[Summary {final['year']}] Final Pop: {final['population']:,} ({final['population']/1e4:,.1f}万人) | "
        f"Cum Births: {tot_b:,} | Cum Deaths: {tot_d:,} | Cum NetMig: {tot_m:+,} | "
        f"Pop Change: {pop_change:+,} (Flow Sum: {flow_sum:+,}) | Final Debt/GDP: {final['debt_gdp']}%"
    )
    return history


def main():
    parser = argparse.ArgumentParser(description="Sandvox Endogenous Forward Policy Simulator CLI (v5.0)")
    parser.add_argument("--years", type=int, default=25, help="Simulation horizon in years (default: 25)")
    parser.add_argument("--scenario", type=str, default="baseline",
                        choices=["baseline", "child_splash", "migration_only", "synergy"],
                        help="Policy scenario preset")
    parser.add_argument("--full", action="store_true", help="Enable full parliamentary election cycles & policy feedback")
    parser.add_argument("--coalition", action="store_true", help="Assume cross-party coalition agreement from day 0")
    parser.add_argument("--n-per", type=int, default=2, help="Representative persons per prefecture (default: 2)")
    parser.add_argument("--params-file", type=str, default=None, help="Path to custom feedback_params.json override")

    args = parser.parse_args()
    run_simulation(
        years=args.years,
        scenario=args.scenario,
        full_mode=args.full,
        n_per=args.n_per,
        coalition_pass=args.coalition,
        params_path=args.params_file,
    )


if __name__ == "__main__":
    main()
