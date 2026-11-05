# The persons layer's functions the tiers start calls (people.gd at cd165891; START_PORT_PLAN §1), bound onto P as its methods so
# the ported code reads p.u(...), p.place_person(...) as GDScript does. finish_person's draws (traits, dream, drives, states) are
# ported too: _points copies every registry row of the scratch slot into tr_points, so they reach a tr_* field
import math

from core import detmath as DM
from core import keyed
from core.gd import clampf, clampi, fdiv, idiv, maxf, minf, mini
from tiers.start.p import P

PID_MASK = 0x7FFFFFFFFFFF
REL_C = 12
REL_NF = 2
GRP_M = 3
GRP_G_MOVEMENT = 5
ACT_NA = 14
ACT_A_KEEP = 0

_FIELDS = None


def u(p, tag, i, b=0, c=0):
    return keyed.u(p.seed_v, tag, int(p.pid[i] & PID_MASK), b, c)


def normal(p, tag, i, b=0, c=0):
    return keyed.normal(p.seed_v, tag, int(p.pid[i] & PID_MASK), b, c)


# people.gd 524
def tier_person(p, i, emp, kind, inc, ass):
    p.employment[i] = emp
    p.hh_kind[i] = kind
    p.income[i] = float(inc) if inc >= 0.0 else p.wage(i)
    if ass >= 0.0:
        p.assets[i] = float(ass)


# people.gd 534
def tier_education(p, i, d):
    a = p.age[i]
    p.education[i] = d
    p.skill[i] = float(clampf(20.0 + 15.0 * p.education[i] + 0.8 * maxf(0.0, float(a - 22)) + 10.0 * p.normal("skill", i), 0.0, 100.0))
    p.income[i] = p.wage(i)


# people.gd 544
def tier_income(p, i, inc, ass):
    inc = float(inc)
    p.income[i] = inc
    p.q_income[i] = inc
    e = p.employment[i]
    if e == P.EMP_RETIRED or (e == P.EMP_NONE and p.tiers and p.age[i] >= p.PENSION_AGE):
        if inc > 0.0:
            p.tr_pension[p.pid[i]] = inc / p.pension_index(i)
        else:
            p.tr_pension.pop(p.pid[i], None)
    elif e == P.EMP_REGULAR or e == P.EMP_NONREGULAR or e == P.EMP_UNEMPLOYED:
        p.tr_phi.pop(p.pid[i], None)
        pen = p.entitled(i)
        w = p.wage(i) - pen
        if w > 0.0:
            p.tr_phi[p.pid[i]] = (inc - pen) / w
    if ass >= 0.0:
        p.assets[i] = float(ass)


# people.gd 564
def tier_pension(p, i, amount, kind):
    p.tr_pension_kind[p.pid[i]] = int(kind)
    if amount > 0.0:
        p.tr_pension[p.pid[i]] = float(amount) / p.pension_index(i)
    else:
        p.tr_pension.pop(p.pid[i], None)


# people.gd 573
def tier_wealth(p, i, ass, dbt):
    p.assets[i] = float(ass)
    p.debt[i] = float(dbt)


# people.gd 608
def fields(p=None):
    global _FIELDS
    if _FIELDS is None:
        K_MEM, NT, ND, NE = P.K_MEM, P.NT, P.ND, P.NE
        _FIELDS = [["pid", "i64", 1, 0, None],
                   ["pref", "i32", 1, 0, None], ["k_in_pref", "i32", 1, 0, None], ["age", "i32", 1, 0, None], ["sex", "i32", 1, 0, None], ["hh_kind", "i32", 1, 0, None],
                   ["education", "i32", 1, 0, None], ["employment", "i32", 1, 0, None], ["health", "i32", 1, 0, None], ["dream_kind", "i32", 1, 0, None],
                   ["dream_status", "i32", 1, 0, None], ["dream_blocked", "i32", 1, 0, None], ["mem_month", "i32", K_MEM, 0, None], ["mem_kind", "i32", K_MEM, 0, None],
                   ["mem_head", "i32", 1, 0, None], ["plan", "i32", 1, 0, None], ["search", "i32", 1, 0, None], ["flags", "i32", 1, 0, None],
                   ["last_action", "i32", 1, 0, None], ["contact_idx", "i32", REL_C, -1, None], ["contact_kind", "i32", REL_C, 0, None],
                   ["contact_last", "i32", REL_C, 0, None], ["met", "i32", 1, 0, None], ["belief_known", "i32", REL_NF, 0, None], ["belief_source", "i32", REL_NF, 0, None],
                   ["belief_month", "i32", REL_NF, 0, None], ["member_of", "i32", GRP_M, -1, None], ["union_cover", "i32", 1, 0, 0],
                   ["weight", "f64", 1, 0, None], ["hh_size", "f64", 1, 0, None], ["income", "f64", 1, 0, None], ["pay_factor", "f64", 1, 0, 1.0],
                   ["assets", "f64", 1, 0, None], ["debt", "f64", 1, 0, None], ["skill", "f64", 1, 0, None], ["rank", "f64", 1, 0, None], ["traits", "f64", NT, 0, None],
                   ["lam", "f64", 1, 0, None], ["dw", "f64", ND, 0, None], ["emo", "f64", NE, 0, None], ["emo_base", "f64", NE, 0, None], ["dd", "f64", ND, 0, None],
                   ["basket", "f64", 4, 0, None], ["pref_leisure", "f64", 1, 0, None], ["pref_social", "f64", 1, 0, None], ["pol_interest", "f64", 1, 0, None],
                   ["dream_importance", "f64", 1, 0, None], ["dream_progress", "f64", 1, 0, None], ["q_income", "f64", 1, 0, None], ["q_price", "f64", 1, 0, None],
                   ["q_job", "f64", 1, 0, None], ["mem_val", "f64", K_MEM, 0, None], ["cohort", "f64", 0, 0, None], ["qx", "f64", 0, 0, None],
                   ["q_act", "f64", ACT_NA, 0, None], ["pressure_prev", "f64", 1, 0, None], ["contact_trust", "f64", REL_C, 0, None], ["belief", "f64", REL_NF, 0, None]]
    return _FIELDS


# people.gd 652
def _resize(p, m):
    for f in p.fields():
        if int(f[2]) > 0:
            arr = getattr(p, f[0])
            arr.resize(m * int(f[2]))
            if int(f[3]) != 0:
                # Why the whole array and not the new slots: Godot's fill() writes every element, as _resize does
                arr[:] = [int(f[3])] * len(arr)


def get(p, name):
    return getattr(p, name)


# people.gd 684
def pick(shares, keys, x):
    acc = 0.0
    for j in range(len(keys)):
        acc += float(shares[keys[j]])
        if x < acc:
            return j
    return len(keys) - 1


# people.gd 693
def age_band(a):
    return "under_30" if a < 30 else ("30_59" if a < 60 else "60_plus")


# people.gd 697
def _draw_attributes(p, i):
    spec = p.spec
    a = p.age[i]
    if p.households:
        pass
    elif a < 18:
        p.hh_kind[i] = P.HK_COUPLE_CHILDREN if p.u("hh", i) < float(spec["household_kind_child"]["couple_children"]) else P.HK_SINGLE_PARENT
    else:
        p.hh_kind[i] = pick(spec["household_kind_shares_adult"], P.HOUSEHOLD, p.u("hh", i))
    p.hh_size[i] = float(spec["household_size"][P.HOUSEHOLD[p.hh_kind[i]]])
    eb = "22_34" if a < 35 else ("35_54" if a < 55 else "55_plus")
    p.education[i] = pick(spec["education_shares_by_age"][eb], P.EDUCATION, p.u("edu", i)) if a >= 22 else 0
    pa = spec["participation"]
    ur = float(spec["unemployment_rate_start"]["value"])
    if a < 15:
        p.employment[i] = P.EMP_NONE
    elif a < 18:
        p.employment[i] = P.EMP_STUDENT if p.u("stu", i) < float(spec["student_share_by_age"]["15_17"]) else p._labour(i, ur)
    elif a < 22:
        sk = "18_19" if a < 20 else "20_21"
        p.employment[i] = P.EMP_STUDENT if p.u("stu", i) < float(spec["student_share_by_age"][sk]) else p._labour(i, ur)
    elif a < 65:
        part = float(pa["male_15_64"]) if p.sex[i] == P.MALE else float(pa["female_15_64"])
        p.employment[i] = p._labour(i, ur) if p.u("part", i) < part else 0
    else:
        p.employment[i] = p._labour(i, ur) if p.u("part", i) < float(pa["age_65_plus"]) else 5
    p.pay_factor[i] = 1.0
    p.income[i] = p.wage(i)
    ab = "under_30" if a < 30 else ("30_39" if a < 40 else ("40_49" if a < 50 else ("50_59" if a < 60 else "60_plus")))
    p.assets[i] = float(spec["assets_median_man_yen_by_age"][ab]) * DM.exp(0.8 * p.normal("assets", i)) if a >= 18 else 0.0
    hl = spec["housing_loan"]
    p.debt[i] = float(hl["size_man_yen"]) * (0.5 + p.u("debtsz", i)) if (a >= 30 and a <= 55 and p.hh_kind[i] >= P.HK_COUPLE and p.hh_kind[i] <= P.HK_COUPLE_CHILDREN and p.u("debt", i) < float(hl["p_by_kind_30_55"])) else 0.0
    hp = spec["health_poor_share_by_age"]
    ppoor = float(hp["base"]) + float(hp["slope_per_year"]) * float(a)
    hu = p.u("health", i)
    p.health[i] = P.GRADE_POOR if hu < ppoor else (P.GRADE_FAIR if hu < ppoor * 2.5 else P.GRADE_GOOD)
    p.skill[i] = float(clampf(20.0 + 15.0 * p.education[i] + 0.8 * maxf(0.0, float(a - 22)) + 10.0 * p.normal("skill", i), 0.0, 100.0)) if a >= 15 else 0.0


# people.gd 739
def _labour(p, i, ur):
    if p.u("unemp", i) < ur:
        return P.EMP_UNEMPLOYED
    nr = float(p.spec["non_regular_share"]["male"]) if p.sex[i] == P.MALE else float(p.spec["non_regular_share"]["female"])
    return P.EMP_NONREGULAR if p.u("nonreg", i) < nr else P.EMP_REGULAR


# people.gd 747
def pension_index(p, i):
    return p.pension_index_at(p.age[i])


# people.gd 751
def pension_index_at(p, a):
    pr = p.spec["pension_rule"]["value"]
    return float(p.pension["new"]) if a <= int(pr["new_until_age"]) else float(p.pension["old"])


# people.gd 758
def wage(p, i):
    spec = p.spec
    e = p.employment[i]
    if e == P.EMP_NONE:
        return p.entitled(i)
    if e == P.EMP_STUDENT:
        return float(spec["student_income_man_yen"]["value"])
    if e == P.EMP_RETIRED:
        if p.tiers and p.pid[i] in p.tr_pension:
            return float(p.tr_pension[p.pid[i]]) * p.pension_index(i)
        return float(spec["pension_man_yen"]["value"]) * (0.7 + 0.6 * p.u("pension", i)) * p.pension_index(i)
    w = spec["wage_regular_man_yen"]
    base = float(w["male"]) if p.sex[i] == P.MALE else float(w["female"])
    curve = spec["wage_age_curve"]
    a = p.age[i]
    dec = str(clampi(idiv(a, 10) * 10, 20, 70))
    base *= float(curve[dec])
    base *= float(spec["wage_education_factor"][P.EDUCATION[p.education[i]]])
    base *= DM.exp(float(spec["wage_sigma"]["value"]) * p.normal("wage", i))
    base *= (1.0 + 0.004 * (p.skill[i] - 50.0)) * p.wage_index
    if e == P.EMP_REGULAR or e == P.EMP_NONREGULAR:
        base *= p.pay_factor[i]
        if p.tiers:
            base *= p.cash_ratio(i)
    if p.tiers:
        base *= float(p.tr_phi.get(p.pid[i], 1.0))
    if e == P.EMP_NONREGULAR:
        base *= float(spec["non_regular_wage_factor"]["value"])
    elif e == P.EMP_UNEMPLOYED:
        base *= float(spec["unemployment_benefit_factor"]["value"])
    return base + p.entitled(i)


# people.gd 793
def entitled(p, i):
    if not p.tiers or p.age[i] < p.PENSION_AGE:
        return 0.0
    return float(p.tr_pension.get(p.pid[i], 0.0)) * p.pension_index(i)


# people.gd 800
def cash_ratio(p, i):
    cr = p.tr_spec["wage_cash_ratio"]["value"]
    a = p.age[i]
    k = 0 if a < 20 else mini(11, idiv(a - 20, 5) + 1)
    return float(cr["regular" if p.employment[i] == P.EMP_REGULAR else "non_regular"]["male" if p.sex[i] == P.MALE else "female"][k])


# people.gd 861
def place_persons(p, m):
    p.n = m
    p._resize(p.n)


# people.gd 866
def place_person(p, i, code, kk, a, s):
    p.pref[i] = code
    p.k_in_pref[i] = kk
    p.age[i] = a
    p.sex[i] = s
    p.pid[i] = keyed.pid(p.seed_v, code, p.base_year - a, s, kk)


# people.gd 889
def draw_person(p, i):
    p._draw_attributes(i)


# people.gd 893
def finish_person(p, i):
    p._draw_traits(i)
    p._draw_dream(i)
    p._compose_drives(i)
    p._init_states(i)


# people.gd 948
def _draw_traits(p, i):
    spec = p.spec
    NT = P.NT
    sd = float(spec["trait_sd"]["value"])
    for t in range(NT):
        p.traits[i * NT + t] = float(clampf(0.5 + sd * p.normal("trait", i, t), 0.02, 0.98))
    la = spec["loss_aversion"]
    p.lam[i] = float(clampf(float(la["mean"]) + (0.5 - p.trait_of(i, "risk_tolerance")) * 1.6, float(la["range"][0]), float(la["range"][1])))
    p.pref_leisure[i] = float(clampf(0.3 + 0.3 * p.trait_of(i, "openness") + 0.2 * (1.0 - p.trait_of(i, "competitiveness")) + 0.05 * p.normal("pl", i), 0.05, 0.95))
    p.pref_social[i] = float(clampf(p.trait_of(i, "sociability") + 0.05 * p.normal("ps", i), 0.05, 0.95))
    p.pol_interest[i] = float(clampf(0.15 + 0.4 * p.trait_of(i, "fairness") * p.trait_of(i, "openness") + 0.004 * maxf(0.0, float(p.age[i] - 30)) + 0.08 * p.normal("pi", i), 0.02, 0.98))
    food = 0.26
    housing = 0.18 if p.hh_kind[i] == P.HK_SINGLE else 0.12
    leisure = 0.08 + 0.08 * p.pref_leisure[i]
    p.basket[i * 4] = food
    p.basket[i * 4 + 1] = housing
    p.basket[i * 4 + 2] = leisure
    p.basket[i * 4 + 3] = maxf(0.0, 1.0 - food - housing - leisure)


# people.gd 969
def trait_of(p, i, name):
    return p.traits[i * P.NT + P.TRAITS.index(name)]


# people.gd 985
def _draw_dream(p, i):
    spec = p.spec
    p.dream_kind[i] = -1
    p.dream_status[i] = 0
    if p.age[i] < 18 or p.u("dream", i) >= float(spec["dream_share_adult"]["value"]):
        return
    wts = spec["dream_kind_weights_by_age"][age_band(p.age[i])]
    x = p.u("dreamkind", i)
    acc = 0.0
    for j in range(len(P.DREAMS)):
        acc += float(wts[j])
        if x < acc:
            p.dream_kind[i] = j
            break
    if p.dream_kind[i] < 0:
        p.dream_kind[i] = len(P.DREAMS) - 1
    p.dream_importance[i] = float(clampf(0.4 + 0.4 * p.trait_of(i, "future_orientation") + 0.1 * p.normal("dreamimp", i), 0.1, 1.0))
    p.dream_progress[i] = float(clampf(0.3 * p.u("dreamprog", i), 0.0, 0.9))


# people.gd 1024
def _compose_drives(p, i):
    ND = P.ND
    D = P.DRIVES
    base = p.spec["drive_base_by_age"][age_band(p.age[i])]
    w = [0.0] * ND
    for d in range(ND):
        w[d] = float(base[d]) + 0.02 * p.normal("drivew", i, d)
    w[D.index("recognition")] += 0.06 * (p.trait_of(i, "competitiveness") - 0.5)
    w[D.index("growth")] += 0.06 * (p.trait_of(i, "openness") - 0.5)
    w[D.index("change")] += 0.06 * (p.trait_of(i, "openness") - 0.5) + 0.04 * (p.trait_of(i, "fairness") - 0.5)
    w[D.index("contribution")] += 0.06 * (p.trait_of(i, "cooperativeness") - 0.5)
    w[D.index("belonging")] += 0.06 * (p.trait_of(i, "sociability") - 0.5)
    w[D.index("autonomy")] += 0.06 * (p.trait_of(i, "risk_tolerance") - 0.5) - 0.04 * (p.trait_of(i, "authority_attitude") - 0.5)
    w[D.index("economic_security")] += 0.06 * (0.5 - p.trait_of(i, "risk_tolerance")) + 0.04 * (p.trait_of(i, "future_orientation") - 0.5)
    tot = 0.0
    for d in range(ND):
        w[d] = maxf(0.005, w[d])
        tot += w[d]
    for d in range(ND):
        p.dw[i * ND + d] = w[d] / tot


# people.gd 1046
def _init_states(p, i):
    NE = P.NE
    E = P.EMOTIONS
    to = p.trait_of
    b = [0.0] * NE
    b[E.index("joy")] = clampf(0.4 + 0.2 * (to(i, "sociability") - 0.5) + 0.2 * (to(i, "openness") - 0.5), 0.05, 0.95)
    b[E.index("sadness")] = clampf(0.15 + 0.2 * (0.5 - to(i, "patience")), 0.02, 0.9)
    b[E.index("anger")] = clampf(0.1 + 0.2 * (to(i, "competitiveness") - 0.5) + 0.1 * (0.5 - to(i, "patience")), 0.02, 0.9)
    b[E.index("anxiety")] = clampf(0.25 + 0.3 * (0.5 - to(i, "risk_tolerance")) + 0.1 * (0.5 - to(i, "trust_in_others")) + 0.1 * float(p.health[i]), 0.02, 0.95)
    b[E.index("fear")] = clampf(0.1 + 0.2 * (0.5 - to(i, "risk_tolerance")), 0.02, 0.9)
    b[E.index("relief")] = 0.2
    b[E.index("hope")] = clampf(0.4 + 0.3 * (to(i, "openness") - 0.5) + 0.2 * (to(i, "future_orientation") - 0.5) - 0.003 * maxf(0.0, float(p.age[i] - 40)), 0.05, 0.95)
    b[E.index("loneliness")] = clampf(0.25 + 0.3 * (0.5 - to(i, "sociability")) + (0.15 if p.hh_kind[i] == P.HK_SINGLE else 0.0), 0.02, 0.95)
    b[E.index("discontent")] = clampf(0.2 + 0.2 * (to(i, "competitiveness") - 0.5) + 0.2 * (to(i, "fairness") - 0.5) * (1.0 - p.rank[i]), 0.02, 0.95)
    b[E.index("trust")] = to(i, "trust_in_others")
    for e in range(NE):
        p.emo_base[i * NE + e] = float(b[e])
        p.emo[i * NE + e] = float(b[e])
    p.q_income[i] = p.income[i]
    p.q_price[i] = 0.02
    p.q_job[i] = 1.0 if (p.employment[i] == P.EMP_REGULAR or p.employment[i] == P.EMP_NONREGULAR) else 0.0
    p.mem_head[i] = 0
    for k in range(P.K_MEM):
        p.mem_kind[i * P.K_MEM + k] = -1
    p.plan[i] = 1
    p.search[i] = 0
    p.flags[i] = 0
    p.last_action[i] = ACT_A_KEEP
    for a in range(ACT_NA):
        p.q_act[i * ACT_NA + a] = 0.0
    p._deficits(i)
    p.pressure_prev[i] = p.pressure(i)


# people.gd 1082
def _cost(p, hk, hs):
    c = p.spec["consumption_man_yen_month"]
    hh = float(c["single"]) if hk == P.HK_SINGLE else float(c["two_plus"]) + float(c["per_extra_member"]) * maxf(0.0, hs - 2.0)
    return hh * p.price_index


# people.gd 1105
def _deficits(p, i):
    NE, ND = P.NE, P.ND
    ev = [p.emo[i * NE + e0] for e0 in range(NE)]
    d = p.deficit_values(i, ev, p.skill[i], p.debt[i])
    for k in range(ND):
        p.dd[i * ND + k] = d[k]


# people.gd 1117, with the state view of person i (state_view.gd of_person): f and n read the persons' arrays at i x the field's stride
def deficit_values(p, i, ev, sk, dbt):
    E = P.EMOTIONS
    to = p.trait_of
    e = p.employment[i]
    cost = p._cost(p.hh_kind[i], p.hh_size[i])
    food_rise = float(p.belief[i * REL_NF]) if p.belief_known[i * REL_NF] == 1 else 0.0
    cost *= 1.0 + p.basket[i * 4] * food_rise
    hk = p.hh_kind[i]
    hh_income = p.income[i] * (1.0 if hk == P.HK_SINGLE else minf(p.hh_size[i], 2.0)) if p.age[i] >= 22 else cost * 0.9
    cover = hh_income / maxf(1e-6, cost)
    fl = p.flags[i]
    d = [0.0] * P.ND
    d[P.D_SURVIVAL] = clampf(0.15 * float(p.health[i]) + 0.4 * maxf(0.0, 1.0 - cover), 0.0, 1.0)
    d[P.D_SECURITY] = clampf(0.5 * maxf(0.0, 1.2 - cover) + (0.5 if e == P.EMP_UNEMPLOYED else 0.0) + (0.15 if e == P.EMP_NONREGULAR else 0.0) + 0.1 * minf(1.0, dbt / maxf(1.0, 24.0 * p.income[i] + 1.0)), 0.0, 1.0)
    d[P.D_BELONGING] = clampf((0.5 if hk == P.HK_SINGLE else 0.2) + 0.2 * (0.5 - p.pref_social[i]) + (0.2 if e == P.EMP_UNEMPLOYED else 0.0) - 0.04 * float(p.contact_count(i)), 0.0, 1.0)
    d[P.D_RECOGNITION] = clampf(1.0 - p.rank[i], 0.0, 1.0) * (0.6 + 0.4 * to(i, "competitiveness"))
    d[P.D_AUTONOMY] = [0.3, 0.5, 0.6, 0.8, 0.5, 0.3][e]
    d[P.D_GROWTH] = clampf(1.0 - sk / 100.0, 0.0, 1.0) * (0.5 + to(i, "openness"))
    pl = p.plan[i]
    d[P.D_ENJOYMENT] = clampf(0.7 - p.basket[i * 4 + 2] * 3.0 - 0.2 * ev[E.index("joy")] - (0.2 if fl & P.F_REST else 0.0) - (0.25 if pl == 2 else 0.0) + (0.1 if pl == 0 else 0.0), 0.0, 1.0)
    ag = p.age[i]
    d[P.D_FAMILY] = clampf((0.7 if (ag >= 25 and ag <= 45 and hk <= P.HK_COUPLE) else 0.2) + (0.2 if hk == P.HK_SINGLE_PARENT else 0.0) - (0.3 if fl & P.F_SUPPORTED else 0.0), 0.0, 1.0)
    if fl & P.F_SOCIALISED:
        d[P.D_BELONGING] = maxf(0.0, d[P.D_BELONGING] - 0.2)
    mem = p.memberships(i)
    d[P.D_BELONGING] = maxf(0.0, d[P.D_BELONGING] - 0.1 * float(mem))
    d[P.D_CONTRIBUTION] = maxf(0.0, 0.3 + 0.2 * (to(i, "cooperativeness") - 0.5) - 0.08 * float(mem))
    d[P.D_CHANGE] = clampf(0.3 * ev[E.index("discontent")] + 0.3 * ev[E.index("anger")] + 0.2 * (1.0 - to(i, "authority_attitude")) - (0.1 if p.in_movement(i) else 0.0), 0.0, 1.0)
    for k in range(P.ND):
        d[k] = float(clampf(d[k], 0.0, 1.0))
    return d


# people.gd 1159
def pressure(p, i):
    s = 0.0
    for k in range(P.ND):
        s += p.dw[i * P.ND + k] * p.dd[i * P.ND + k]
    return s


# people.gd 1537
def in_movement(p, i):
    for m in range(GRP_M):
        gid = p.member_of[i * GRP_M + m]
        if gid >= 0 and int(p.groups[gid]["kind"]) == GRP_G_MOVEMENT:
            return True
    return False


# people.gd 1545
def contact_count(p, i):
    k = 0
    for c in range(REL_C):
        if p.contact_idx[i * REL_C + c] >= 0:
            k += 1
    return k


# groups.gd 122
def memberships(p, i):
    k = 0
    for m in range(GRP_M):
        if p.member_of[i * GRP_M + m] >= 0:
            k += 1
    return k


# life_course.gd 13
def _lc(p, k):
    return p.hh_spec["life_course"]["value"][k]["value"]


# life_course.gd 27
def lc_shares(p, a, s):
    sa = _lc(p, "prevalence_single_age")
    sx = "men" if s == 0 else "women"
    a1 = clampi(a, 0, 100)
    s2 = float(sa["g2plus"][sx][a1])
    med = float(_lc(p, "medical_level"))
    g4 = fdiv(float(sa["g4"][sx][a1]), med)
    g3 = fdiv(maxf(0.0, s2 - g4) * float(_lc(p, "poor_share_of_rest")), med)
    g2 = maxf(0.0, maxf(s2, g4) - g4 - g3)
    g1 = maxf(0.0, 1.0 - g2 - g3 - g4)
    b4 = lc_ltci_share(p, a, s)
    if b4 > g4:
        sc = fdiv(1.0 - b4, 1.0 - g4)
        g1 *= sc
        g2 *= sc
        g3 *= sc
        g4 = b4
    return [g1, g2, g3, g4 - b4, b4]


# life_course.gd 48
def lc_ltci_share(p, a, s):
    return float(_lc(p, "prevalence_single_age")["b4"]["men" if s == 0 else "women"][clampi(a, 0, 100)])


LC_NG = 5


# life_course.gd 52 (LC.draw_grade)
def draw_grade(p, i, tag):
    sh = lc_shares(p, p.age[i], p.sex[i])
    x = p.u(tag, i, p.month)
    acc = 0.0
    for g in range(LC_NG):
        acc += sh[g]
        if x < acc:
            return g
    return LC_NG - 1


for _f in (u, normal, tier_person, tier_education, tier_income, tier_pension, tier_wealth, fields, _resize, get, _draw_attributes,
           _labour, pension_index, pension_index_at, wage, entitled, cash_ratio, place_persons, place_person, draw_person,
           finish_person, _draw_traits, trait_of, _draw_dream, _compose_drives, _init_states, _cost, _deficits, deficit_values,
           pressure, in_movement, contact_count, memberships):
    setattr(P, _f.__name__, _f)
P.pick = staticmethod(pick)
P.age_band = staticmethod(age_band)
