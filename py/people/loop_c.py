# The persons' month, sections c1, c4 and c5 of people.step (people.gd 1240-1307 at cd165891; tools/py/persons_trace.gd _step), with
# what they call that the start's persons functions (py/tiers/start/persons.py) do not hold: people.gd's pension month, finding rate,
# year, rebirth, month values and person-level rake, labour.gd's per-person half (lab_*), state_view.gd (SV) and life_course.gd's
# calls of both modes (lc_*), with households on py/lchh's life course (LC) and households (HH). Bound onto P as its methods, as
# persons.py's are
from core import detmath as DM
from core import keyed
from core.gd import clampf, fdiv, maxf, minf, mini
from lchh import households as HH
from lchh import life_course as LC
from people import act as ACT
from people import grp as GRP
from people import rel as REL
from tiers.start.p import P, PArr

_MEM_KINDS = ["job_loss", "job_found", "entered_work", "retired", "dream_achieved", "dream_abandoned", "changed_job"]


# state_view.gd
class SV:
    _strides = {}

    @staticmethod
    def strides_of(o):
        if not SV._strides:
            for fl in o.fields():
                SV._strides[str(fl[0])] = int(fl[2])
        return SV._strides

    def of_person(self, o, i):
        self.p = o
        self.idx = i
        self.is_point = False
        self.stride = SV.strides_of(o)
        return self

    def f(self, name, k=0):
        if self.is_point:
            raise NotImplementedError("a point's view (of_point) is the tiers' month's")
        return float(getattr(self.p, name)[self.idx * int(self.stride[name]) + k])

    def n(self, name, k=0):
        if self.is_point:
            raise NotImplementedError("a point's view (of_point) is the tiers' month's")
        return int(getattr(self.p, name)[self.idx * int(self.stride[name]) + k])

    def contacts(self):
        return self.p.contact_count(self.idx)

    def memberships(self):
        return GRP.memberships(self.p, self.idx)

    def in_movement(self):
        return self.p.in_movement(self.idx)


# people.gd 662
def below(p, tag, i, b, c, h):
    x = p.u(tag, i, b, c)
    if p.rone_on:
        p.rone_log.append(["draw", tag, i, h])
    return x < h


# people.gd 670
def rone_out(p, name, v):
    if p.rone_on:
        p.rone_log.append(["out", name, v])
    return v


# people.gd 847
def repay(p, i):
    p.income[i] = p.wage(i)


# people.gd 391
def reweight(p, cohort_now, start_types=False):
    for i0 in range(p.n):
        if p.pref[i0] not in p.pref_pop:
            p.error = "people: prefecture %d has no population; the rake cannot scale it" % p.pref[i0]
            break
    c_now = cohort_now if len(cohort_now) == P.AGES * P.SEXES else p.cohort
    tot_start = 0.0
    tot_now = 0.0
    for k in range(P.AGES * P.SEXES):
        tot_start += p.cohort[k]
        tot_now += c_now[k]
    cell_target = PArr("f64")
    cell_target.resize((len(P.AGE_BANDS) + 1) * P.SEXES)
    for a in range(P.AGES):
        for s in range(P.SEXES):
            cell_target[band_of(a) * P.SEXES + s] += fdiv(c_now[a * P.SEXES + s], tot_now)
    if p.households:
        HH.rake(p, cell_target, fdiv(tot_now, tot_start), start_types)
        return
    pop_total = 0.0
    for code in p.pref_pop:
        pop_total += float(p.pref_pop[code])
    for r in range(6):
        csum = PArr("f64")
        csum.resize(len(cell_target))
        all_ = 0.0
        for i in range(p.n):
            csum[band_of(p.age[i]) * P.SEXES + p.sex[i]] += p.weight[i]
            all_ += p.weight[i]
        for i2 in range(p.n):
            cc = band_of(p.age[i2]) * P.SEXES + p.sex[i2]
            if csum[cc] > 0.0:
                p.weight[i2] *= cell_target[cc] * all_ / csum[cc]
        now = {}
        for i3 in range(p.n):
            now[p.pref[i3]] = float(now.get(p.pref[i3], 0.0)) + p.weight[i3]
        for i4 in range(p.n):
            w0 = float(now.get(p.pref[i4], 0.0))
            if w0 > 0.0 and p.pref[i4] in p.pref_pop:
                p.weight[i4] *= float(p.pref_pop[p.pref[i4]]) * fdiv(tot_now, tot_start) / w0


# people.gd 438
def band_of(a):
    for b in range(len(P.AGE_BANDS)):
        if a < P.AGE_BANDS[b]:
            return b
    return len(P.AGE_BANDS)


# people.gd 1090
def _cost_v(p, v):
    return p._cost(v.n("hh_kind"), v.f("hh_size"))


# people.gd 1094
def _trait_v(p, v, name):
    return v.f("traits", P.TRAITS.index(name))


# people.gd 1098
def _food_rise_v(p, v):
    return v.f("belief", 0) if v.n("belief_known", 0) == 1 else 0.0


# people.gd 1160
def _pension_month(p):
    pr = p.spec["pension_rule"]["value"]
    if p.month % 12 == 0:
        insured = 0.0
        for i in range(p.n):
            if p.age[i] >= 20 and p.age[i] < 60:
                insured += p.weight[i]
        p.pension["jan_prev"] = list(p.pension["jan"])
        p.pension["jan"] = [p.price_index, p.wage_index, insured]
    if p.month % 12 != int(pr["revision_month_index"]):
        return
    prev = p.pension["jan_prev"]
    now = p.pension["jan"]
    if len(prev) == 0 or len(now) == 0:
        first = float(pr["first_revision"])
        r = [first, first, float(p.pension["carry"]), 0.0, 0.0, 0.0]
    else:
        cpi = fdiv(float(now[0]), float(prev[0])) - 1.0
        wg = fdiv(float(now[1]), float(prev[1])) - 1.0
        slide = (float(now[2]) / float(prev[2]) - 1.0 if float(prev[2]) > 0.0 else 0.0) + float(pr["life_expectancy_slide"])
        r = pension_revision(cpi, wg, minf(0.0, slide), float(p.pension["carry"]))
        r.extend([cpi, wg, slide])
    p.pension["new"] = float(p.pension["new"]) * (1.0 + float(r[0]))
    p.pension["old"] = float(p.pension["old"]) * (1.0 + float(r[1]))
    p.pension["carry"] = float(r[2])
    p.pension["log"].append([p.month, r[0], r[1], r[2]])
    for i2 in range(p.n):
        if p.employment[i2] == P.EMP_RETIRED:
            p.repay(i2)


# people.gd 1196
def pension_revision(cpi, wage, slide, carry):
    total = slide + carry
    base_new = wage
    base_old = minf(cpi, wage)
    rate_new = maxf(0.0, base_new + total) if base_new > 0.0 else base_new
    rate_old = maxf(0.0, base_old + total) if base_old > 0.0 else base_old
    used = rate_new - base_new if base_new > 0.0 else 0.0
    return [rate_new, rate_old, minf(0.0, total - used)]


# people.gd 1209
def _mean_finding(p, f):
    wu = 0.0
    wf = 0.0
    for i in range(p.n):
        if p.employment[i] == P.EMP_UNEMPLOYED:
            wu += p.weight[i]
            wf += p.weight[i] * (ACT.SEARCH_BOOST if p.search[i] == 1 else ACT.NO_SEARCH)
    return f * wf / wu if wu > 0.0 else f


# people.gd 1229
def saving_values(a0, d0, save):
    a = a0 + save
    d = d0
    if a < 0.0:
        d -= a
        a = 0.0
    return PArr("f64", [a, d])


# people.gd 1313
def month_values(p, v, infl, levers):
    NE, ND = P.NE, P.ND
    ev = PArr("f64")
    ev.resize(NE)
    for e in range(NE):
        ev[e] = v.f("emo", e)
    rec = []
    qi = v.f("q_income") * (1.0 + v.f("q_price") / 12.0)
    surprise = (v.f("income") - qi) / maxf(1.0, qi) if v.n("age") >= 22 else 0.0
    if surprise < -0.02:
        p._move_v(ev, rec, "sadness", 0.6 * v.f("lam") * -surprise, "income_below_expectation", "loss_aversion")
        p._move_v(ev, rec, "anxiety", 0.4 * v.f("lam") * -surprise * (1.5 - p._trait_v(v, "risk_tolerance")), "income_below_expectation", "risk_tolerance")
    elif surprise > 0.02:
        p._move_v(ev, rec, "joy", 0.4 * surprise, "income_above_expectation", "")
        p._move_v(ev, rec, "hope", 0.2 * surprise * (0.5 + p._trait_v(v, "openness")), "income_above_expectation", "openness")
    yoy = p._food_rise_v(v)
    if yoy > 0.03:
        bite = (yoy - 0.03) * v.f("basket", 0) / 0.26 * minf(2.0, p._cost_v(v) / maxf(1.0, v.f("income") + 1.0))
        p._move_v(ev, rec, "anxiety", 0.5 * bite * (1.5 - p._trait_v(v, "risk_tolerance")), "food_price_rise", "risk_tolerance")
        p._move_v(ev, rec, "discontent", 0.4 * bite, "food_price_rise", "")
        p._move_v(ev, rec, "anger", 0.3 * bite * p._trait_v(v, "fairness"), "food_price_rise", "fairness")
    for lid in levers:
        if lid == "consumption_tax_rate":
            p._move_v(ev, rec, "anger", 0.12 * (1.5 - p._trait_v(v, "authority_attitude")), "tax_rise", "authority_attitude")
            p._move_v(ev, rec, "discontent", 0.1, "tax_rise", "")
        elif lid == "child_allowance":
            if v.n("hh_kind") == P.HK_COUPLE_CHILDREN or v.n("hh_kind") == P.HK_SINGLE_PARENT:
                p._move_v(ev, rec, "joy", 0.1, "child_allowance", "")
                p._move_v(ev, rec, "trust", 0.05, "child_allowance", "")
        elif lid == "fuel_subsidy" or lid == "rice_stock_release":
            p._move_v(ev, rec, "relief", 0.05, lid, "")
    sk = maxf(0.0, v.f("skill") - 0.5) if v.n("employment") == P.EMP_UNEMPLOYED else v.f("skill")
    factor = [0.85, 1.0, 1.2][v.n("plan")]
    save = v.f("income") - p._cost_v(v) / maxf(1.0, v.f("hh_size")) * factor
    ad = saving_values(v.f("assets"), v.f("debt"), save)
    a = ad[0]
    dbt = ad[1]
    dream = p._dream_values(v, save, a, ev, rec)
    if v.n("hh_kind") == P.HK_SINGLE and v.n("met") == 0:
        p._move_v(ev, rec, "loneliness", 0.02 * v.f("pref_social"), "living_alone", "sociability")
    lr = float(p.spec["expectation_learning_rate"]["value"])
    di = v.f("income") - v.f("q_income")
    jobnow = 1.0 if (v.n("employment") == P.EMP_REGULAR or v.n("employment") == P.EMP_NONREGULAR) else 0.0
    dec = p.spec["emotion_decay_month"]
    for e2 in range(NE):
        ev[e2] = clampf(ev[e2] + float(dec[P.EMOTIONS[e2]]) * (v.f("emo_base", e2) - ev[e2]), 0.0, 1.0)
    # Why persons.py's deficit_values at the view's index and not a second copy over the view: a person's view reads the persons'
    # arrays at its index (state_view.gd f, n), which that function reads directly; a point's view is the tiers' month's
    d = p.deficit_values(v.idx, ev, sk, dbt)
    pr = 0.0
    for k in range(ND):
        pr += v.f("dw", k) * d[k]
    r = v.f("pressure_prev") - pr
    la = v.n("last_action")
    qa = v.f("q_act", la)
    return {"emo": ev, "rec": rec, "skill": sk, "assets": a, "debt": dbt, "dream": dream,
            "q_income": v.f("q_income") + lr * di * (v.f("lam") if di < 0.0 else 1.0), "q_price": v.f("q_price") + lr * (infl * 12.0 - v.f("q_price")),
            "q_job": v.f("q_job") + lr * (jobnow - v.f("q_job")) * (v.f("lam") if jobnow < v.f("q_job") else 1.0), "dd": d,
            "q_act": qa + 0.3 * (r - qa) * (v.f("lam") if r < qa else 1.0), "pressure": pr}


# people.gd 1386
def apply_month_values(p, i, v, counts):
    NE, ND = P.NE, P.ND
    ev = v["emo"]
    for e in range(NE):
        p.emo[i * NE + e] = ev[e]
    for r in v["rec"]:
        if str(r[0]) == "move":
            p._count(counts, str(r[1]) + ":" + str(r[2]), i, float(r[3]), "scaled by " + str(r[4]) if str(r[4]) != "" else "flat")
            if p.pid[i] in p.trace_pids:
                p.trace.append([p.month, p.pid[i], str(r[1]), str(r[2]), float(r[3]), str(r[4])])
        else:
            p._count(counts, str(r[1]), i, 0.0, str(r[2]))
    p.skill[i] = float(v["skill"])
    p.assets[i] = float(v["assets"])
    p.debt[i] = float(v["debt"])
    dr = v["dream"]
    p.dream_progress[i] = float(dr["progress"])
    p.dream_blocked[i] = int(dr["blocked"])
    p.dream_importance[i] = float(dr["importance"])
    p.dream_status[i] = int(dr["status"])
    for m in dr["remember"]:
        p._remember(i, str(m[0]), float(m[1]))
    p.q_income[i] = float(v["q_income"])
    p.q_price[i] = float(v["q_price"])
    p.q_job[i] = float(v["q_job"])
    REL.clear_met(p, i)
    d = v["dd"]
    for k in range(ND):
        p.dd[i * ND + k] = d[k]
    p.q_act[i * ACT.NA + p.last_action[i]] = float(v["q_act"])
    p.pressure_prev[i] = float(v["pressure"])


# people.gd 1419
def _move_v(p, ev, rec, emotion_name, amount, why, scaled_by):
    if abs(amount) < 1e-9:
        return
    k = P.EMOTIONS.index(emotion_name)
    before = ev[k]
    ev[k] = clampf(before + amount, 0.0, 1.0)
    rec.append(["move", why, emotion_name, ev[k] - before, scaled_by])


# people.gd 1428
def labour_from_rates(p, i):
    return P.EMP_NONREGULAR if p.below("nonreg2", i, p.month, 0, p.h_nonregular(p.sex[i])) else P.EMP_REGULAR


# people.gd 1433
def h_nonregular(p, s):
    return p.rone_out("h_nonregular", float(p.spec["non_regular_share"]["male"]) if s == P.MALE else float(p.spec["non_regular_share"]["female"]))


# people.gd 1440
def _year(p, i, counts):
    a = p.age[i]
    if p.households:
        if LC.dies(p, i):
            return
    q = p.h_death_off(a, p.sex[i])
    if not p.households and p.below("death", i, p.month, 0, q):
        p._count(counts, "death", i, 0.0, "the cohort's qx (S)")
        p._reborn(i)
        return
    p.age[i] = a + 1
    if p.households:
        LC.year_turn(p, i)
    if p.age[i] == 22 and p.employment[i] == P.EMP_STUDENT:
        p._draw_attributes_education(i)
        lab_enter_work(p, i, counts)
    elif p.age[i] == 15 and p.employment[i] == P.EMP_NONE:
        lc_enter_school(p, i)
    elif p.age[i] == 65 and (p.employment[i] == P.EMP_REGULAR or p.employment[i] == P.EMP_NONREGULAR or p.employment[i] == P.EMP_UNEMPLOYED):
        lc_retire(p, i, counts)
    elif p.employment[i] == P.EMP_REGULAR or p.employment[i] == P.EMP_NONREGULAR:
        p.income[i] = p.wage(i)
    p.skill[i] = minf(100.0, p.skill[i] + (0.8 if p.employment[i] <= P.EMP_NONREGULAR and p.employment[i] >= P.EMP_REGULAR else 0.2))
    p._compose_drives(i)


# people.gd 1467
def h_death_off(p, a, s):
    return p.rone_out("h_death_off", p.qx[mini(a, P.AGES - 1) * P.SEXES + s] if len(p.qx) > 0 else 0.0)


# people.gd 1471
def _draw_attributes_education(p, i):
    p.education[i] = P.pick(p.spec["education_shares_by_age"]["22_34"], P.EDUCATION, p.u("edu22", i))
    p.skill[i] = float(clampf(20.0 + 15.0 * p.education[i] + 10.0 * p.normal("skill22", i), 0.0, 100.0))


# people.gd 1476
def _reborn(p, i):
    code = p.pref[i]
    k = p.k_in_pref[i]
    p.age[i] = 0
    p.sex[i] = keyed.below(2, p.seed_v, "rebornsex", code, k, p.month)
    p.pid[i] = keyed.pid(p.seed_v, code, p.base_year + p.month // 12, p.sex[i], 100000 + k * 64 + p.month % 64)
    p._draw_attributes(i)
    p._draw_traits(i)
    p._draw_dream(i)
    p._compose_drives(i)
    p._init_states(i)
    REL.drop_all(p, i)
    REL.forget(p, i)
    for m in range(GRP.M):
        if p.member_of[i * GRP.M + m] >= 0:
            GRP.leave(p, i, p.member_of[i * GRP.M + m])
    GRP.clear_cover(p, i)


# people.gd 1496
def event(p, i, kind, counts):
    to = p.trait_of
    if kind == "job_loss":
        p._move(i, "anxiety", 0.35 * p.lam[i] / 2.0 * (1.5 - to(i, "risk_tolerance")), kind, "risk_tolerance x loss_aversion", counts)
        p._move(i, "sadness", 0.25 * p.lam[i] / 2.0, kind, "loss_aversion", counts)
        p._move(i, "anger", 0.15 * to(i, "fairness"), kind, "fairness", counts)
        p._move(i, "discontent", 0.2, kind, "", counts)
        p._move(i, "hope", -0.15 * (1.5 - to(i, "openness")), kind, "openness", counts)
    elif kind == "job_found":
        p._move(i, "relief", 0.4, kind, "", counts)
        p._move(i, "joy", 0.3 * (0.5 + to(i, "sociability")), kind, "sociability", counts)
        p._move(i, "hope", 0.2, kind, "", counts)
        p._move(i, "anxiety", -0.25, kind, "", counts)
    elif kind == "entered_work":
        p._move(i, "hope", 0.2, kind, "", counts)
        p._move(i, "anxiety", 0.1 * (1.5 - to(i, "risk_tolerance")), kind, "risk_tolerance", counts)
    elif kind == "retired":
        p._move(i, "relief", 0.2, kind, "", counts)
        p._move(i, "anxiety", 0.1 * (1.5 - to(i, "future_orientation")), kind, "future_orientation", counts)
    p._remember(i, kind, -1.0 if kind == "job_loss" else 1.0)


# people.gd 1575
def _remember(p, i, kind, valence):
    h = p.mem_head[i]
    k = i * P.K_MEM + h
    p.mem_month[k] = p.month
    p.mem_kind[k] = _MEM_KINDS.index(kind) if kind in _MEM_KINDS else -1
    p.mem_val[k] = valence
    p.mem_head[i] = (h + 1) % P.K_MEM


# people.gd 1587
def _dream_values(p, v, save, a_new, ev, rec):
    out = {"progress": v.f("dream_progress"), "blocked": v.n("dream_blocked"), "importance": v.f("dream_importance"), "status": v.n("dream_status"), "remember": []}
    dk = v.n("dream_kind")
    if dk < 0 or v.n("dream_status") != 0:
        return out
    cost = float(p.spec["dream_cost_man_yen"][P.DREAMS[dk]])
    if save > 0.0:
        out["progress"] = minf(1.0, v.f("dream_progress") + fdiv((1.0 if v.n("flags") & P.F_DREAM else 0.5) * save, cost) * (0.5 + p._trait_v(v, "patience")))
        out["blocked"] = 0
    elif a_new > 6.0 * p._cost_v(v):
        out["blocked"] = 0
    else:
        out["blocked"] = v.n("dream_blocked") + 1
        if int(out["blocked"]) >= 12:
            out["importance"] = maxf(0.0, v.f("dream_importance") - 0.05 * (1.5 - p._trait_v(v, "patience")))
    if float(out["progress"]) >= 1.0:
        out["status"] = 1
        p._move_v(ev, rec, "joy", 0.5, "dream_achieved", "")
        p._move_v(ev, rec, "hope", 0.3, "dream_achieved", "")
        out["remember"].append(["dream_achieved", 2.0])
    elif float(out["importance"]) < 0.2:
        out["status"] = 2
        p._move_v(ev, rec, "sadness", 0.3 * v.f("lam") / 2.0, "dream_abandoned", "loss_aversion")
        p._move_v(ev, rec, "discontent", 0.2, "dream_abandoned", "")
        rec.append(["count", "dream_abandoned:" + P.DREAMS[dk], "no savings for %d months, patience %.2f" % (int(out["blocked"]), p._trait_v(v, "patience"))])
        out["remember"].append(["dream_abandoned", -2.0])
    return out


# labour.gd person_month
def lab_person_month(p, i, s, f, counts):
    h = lab_rates(p, i, s, f)
    m = p.month
    if h[0] > 0.0 and p.below("sep", i, m, 0, h[0]):
        e0 = lab_effect_loss(p)
        lab_apply(p, i, int(e0[0]), float(e0[1]), "job_loss", counts)
    elif h[1] > 0.0 and p.below("find", i, m, 0, h[1]):
        e1 = lab_effect_find(p, i)
        lab_apply(p, i, int(e1[0]), float(e1[1]), "job_found", counts)
    elif h[2] > 0.0 and p.below("change", i, m, 0, h[2]):
        before = p.income[i]
        e2 = lab_effect_change(p, i, m)
        lab_apply(p, i, int(e2[0]), float(e2[1]), "changed_job", counts)
        p.count_kind(counts, "changed_job:income_change", i, p.income[i] - before, "the economy's wage table redrawn (T)")


# labour.gd rates
def lab_rates(p, i, s, f):
    e = p.employment[i]
    at_work = e == P.EMP_REGULAR or e == P.EMP_NONREGULAR
    return p.rone_out("rates", PArr("f64", [float(s) if at_work else 0.0,
                                            f * (ACT.SEARCH_BOOST if p.search[i] == 1 else ACT.NO_SEARCH) if e == P.EMP_UNEMPLOYED else 0.0,
                                            ACT.CHANGE_P if at_work and p.search[i] == 2 else 0.0]))


# labour.gd h_to_regular
def lab_h_to_regular(p, i):
    return p.rone_out("h_to_regular", 0.3 if p.employment[i] == P.EMP_NONREGULAR else 0.0)


# labour.gd effect_loss
def lab_effect_loss(p):
    return [P.EMP_UNEMPLOYED, 1.0]


# labour.gd effect_find
def lab_effect_find(p, i):
    return [p.labour_from_rates(i), 1.0]


# labour.gd effect_change
def lab_effect_change(p, i, m):
    e = p.employment[i]
    hr = lab_h_to_regular(p, i)
    if hr > 0.0 and p.below("toregular", i, m, 0, hr):
        e = P.EMP_REGULAR
    return [e, DM.exp(0.15 * p.normal("newwage", i, m))]


# labour.gd apply
def lab_apply(p, i, emp, pf, kind, counts):
    p.employment[i] = emp
    p.pay_factor[i] = pf
    p.repay(i)
    GRP.new_job(p, i)
    p.event(i, kind, counts)


# labour.gd enter_work
def lab_enter_work(p, i, counts):
    p.employment[i] = p.labour_from_rates(i)
    p.repay(i)
    GRP.new_job(p, i)
    p.event(i, "entered_work", counts)


# life_course.gd 365
def lc_enter_school(p, i):
    p.employment[i] = P.EMP_STUDENT
    p.repay(i)


# life_course.gd 371
def lc_h_retire(p):
    return p.rone_out("h_retire", 0.74)


# life_course.gd 376
def lc_retire(p, i, counts):
    if p.below("retire", i, p.month, 0, lc_h_retire(p)):
        p.employment[i] = P.EMP_RETIRED
        p.repay(i)
        p.event(i, "retired", counts)


def _env_locals(p, ctx, env):
    # people.gd 1241-1248's locals, re-read from env and the spec when a section starts from a dump that does not hold them (the
    # oracle writes each check's own locals only); they are pure reads, so the values are step's
    if "infl" not in ctx:
        ctx["infl"] = float(env.get("inflation_month", 0.02 / 12.0))
    if "ur" not in ctx:
        ctx["ur"] = float(env.get("unemployment_rate", float(p.spec["unemployment_rate_start"]["value"])))
    if "f" not in ctx:
        ctx["f"] = float(p.spec["job_finding_rate_month"]["value"])
    if "yoy_true" not in ctx:
        ctx["yoy_true"] = float(env.get("food_price_yoy", 0.0))
    if "levers" not in ctx:
        ctx["levers"] = env.get("levers", [])


# people.gd 1241-1251
def sec_c1(p, ctx, env):
    infl = float(env.get("inflation_month", 0.02 / 12.0))
    p.price_index *= 1.0 + infl
    p.wage_index = float(env.get("wage_index", p.wage_index))
    p._pension_month()
    ctx["infl"] = infl
    ctx["ur"] = float(env.get("unemployment_rate", float(p.spec["unemployment_rate_start"]["value"])))
    ctx["f"] = float(p.spec["job_finding_rate_month"]["value"])
    ctx["yoy_true"] = float(env.get("food_price_yoy", 0.0))
    ctx["levers"] = env.get("levers", [])
    ctx["counts"] = {}
    ctx["dec_counts"] = {}
    ctx["ref_counts"] = {}


# people.gd 1273-1287
def sec_c4(p, ctx, env):
    _env_locals(p, ctx, env)
    s, f, infl, levers, counts = ctx["s"], ctx["f"], ctx["infl"], ctx["levers"], ctx["counts"]
    pools = {}
    for i0 in range(p.n):
        if p.pref[i0] not in pools:
            pools[p.pref[i0]] = []
        pools[p.pref[i0]].append(i0)
    for i in range(p.n):
        if p.month % 12 == int(p.pid[i] % 12):
            p._year(i, counts)
            if p.contact_renewal:
                REL.replenish(p, i, pools[p.pref[i]])
        lab_person_month(p, i, s, f, counts)
        p.apply_month_values(i, p.month_values(SV().of_person(p, i), infl, levers), counts)


# life_course.gd 674
def lc_deaths(p, counts):
    dead = PArr("u8")
    dead.resize(p.n)
    for i in p.lc_dying:
        if dead[i] == 1:
            continue
        dead[i] = 1
        p.lc_deaths[LC._dband(p.age[i]) * 2 + p.sex[i]] += 1
        p.count_kind(counts, "death", i, 0.0, "the life table's qx x the grade multiplier (S/T)")
        LC._log(p, i, "death", p.partner[i], {"age": p.age[i], "grade": p.health[i] + 1})
        pt = p.partner[i]
        if pt >= 0:
            p.partner[pt] = -1
            LC._draw_intention(p, pt, p.month + 1)
            LC._log(p, pt, "widowed", i, {"age": p.age[pt]})
        p.partner[i] = -1
        REL.drop_all(p, i)
        for m in range(GRP.M):
            if p.member_of[i * GRP.M + m] >= 0:
                GRP.leave(p, i, p.member_of[i * GRP.M + m])
        LC._hh_remove(p, i)
    p.lc_dying = PArr("i32")
    return dead


# life_course.gd 700. Why not py/lchh's LC.month: it takes no counts (its cut L reads no records), and the month's events are
# people.step's records. Each effect below is py/lchh's, with the count after it: life_course.gd's count_kind is each effect's last
# line and reads only the actor's weight, which no effect writes
def lc_month(p, counts):
    dead = lc_deaths(p, counts)
    n0 = p.n
    acted = PArr("u8")
    acted.resize(n0)
    for i0 in range(n0):
        acted[i0] = dead[i0]
    fam = P.D_FAMILY
    aut = P.D_AUTONOMY
    dws = 0.0
    dwa = 0.0
    na = 0.0
    for i in range(n0):
        if dead[i] == 1 or p.age[i] < 18:
            continue
        dws += p.dw[i * P.ND + fam]
        dwa += p.dw[i * P.ND + aut]
        na += 1.0
    fam_mean = dws / maxf(1.0, na)
    aut_mean = dwa / maxf(1.0, na)
    pa = LC._lc(p, "partnering")
    births = []
    bi = LC._lc(p, "birth")
    lh = LC._lc(p, "leaving_home")
    dv = LC._lc(p, "divorce_choice")
    mi = LC._lc(p, "moving_in")
    ins = LC._lc(p, "institution")
    for i in range(n0):
        if acted[i] == 1:
            continue
        a = p.age[i]
        h = p.hh_id[i]
        if p.hh_type[h] == LC.INSTITUTION:
            continue
        size = len(p.hh_members[h])
        hi = LC.h_institution(ins, p, i, a, size)
        if hi > 0.0 and p.below("lc_inst", i, p.month, 0, hi):
            LC.e_institution(p, i, h)
            p.count_kind(counts, "institution", i, 0.0, "grade 4 at 75+ (T)")
            acted[i] = 1
            continue
        hm = LC.h_move_in(mi, p, i, a, size)
        if hm > 0.0 and p.below("lc_movein", i, p.month, 0, hm):
            to = LC._move_in_to(mi, p, i, a)
            if to >= 0:
                LC.e_move_in(p, i, to)
                p.count_kind(counts, "moved_in", i, 0.0, "65+ at grade 3-4 with a child's household (T)")
                acted[i] = 1
                continue
        pt = p.partner[i]
        if pt >= 0 and p.sex[i] == P.FEMALE and p.hh_id[pt] == h and acted[pt] == 0:
            if p.below("lc_divorce", i, p.month, 0, LC.h_divorce(dv, p, i, pt, h)):
                LC.e_divorce(p, i, pt, h)
                p.count_kind(counts, "divorce", i, 0.0, "the partners' discontent, money and a young child (T)")
                acted[i] = 1
                acted[pt] = 1
                continue
            hb = LC.h_birth(bi, p, i, pt, a)
            if hb > 0.0 and p.below("lc_birth", i, p.month, 0, hb):
                births.append(i)
                acted[i] = 1
                continue
        hl = LC.h_leave(lh, p, i, a, pt, aut_mean)
        if hl > 0.0 and p.below("lc_leave", i, p.month, 0, hl):
            LC.e_leave(p, i, h)
            p.count_kind(counts, "left_home", i, 0.0, "the autonomy drive x earning (T)")
            acted[i] = 1
            continue
        hp = LC.h_look(pa, p, i, a, pt)
        if hp > 0.0 and p.below("lc_partner", i, p.month, 0, hp):
            pool = LC._met(p, i, dead)
            found = -1
            if len(pool) > 0:
                j2 = pool[keyed.below(len(pool), p.seed_v, "lc_partnerpick", int(p.pid[i] & 0x7FFFFFFFFFFF), p.month * 32, 0)]
                if acted[j2] == 0 and LC._can_pair(pa, p, i, j2, a, h):
                    c = LC._compat(p, i, j2, float(pa["trait_compat"]))
                    if p.below("lc_accept", i, p.month * 32, 0, LC.h_accept(p, i, c, fam_mean, 1.0)) and \
                            p.below("lc_agree", j2, p.month * 32, 0, LC.h_accept(p, j2, c, fam_mean, LC._window(pa["window"], p.age[j2]))):
                        found = j2
            if found >= 0 and not p.below("lc_econ", i, p.month, 0, LC.h_carry(p, i, found)):
                found = -1
            if found >= 0:
                LC._partner(p, i, found)
                acted[i] = 1
                acted[found] = 1
                p.count_kind(counts, "partnered", i, 0.0, "two independent decisions (drive, security, traits), both intending to marry, the pair's income (P/T)")
    for m2 in births:
        LC._birth(p, m2)
        p.count_kind(counts, "birth", m2, 0.0, "a couple's family drive x fecundity x budget (T)")
    p.remove_persons(dead)
    for h2 in range(p.hh_n):
        LC._classify(p, h2)
    for i3 in range(p.n):
        h3 = p.hh_id[i3]
        p.hh_kind[i3] = P.HK_SINGLE if p.hh_type[h3] == LC.INSTITUTION else p.hh_type[h3]
        p.hh_size[i3] = float(len(p.hh_members[h3]))


# people.gd 1288-1293
def sec_c5(p, ctx, env):
    if p.households:
        LC.grade_birthday(p)
        lc_month(p, ctx.setdefault("counts", {}))
    p.reweight(env.get("cohort", PArr("f64")))
    if p.households:
        LC.quartile_cuts(p)


for _f in (below, rone_out, repay, reweight, _cost_v, _trait_v, _food_rise_v, _pension_month, _mean_finding, month_values,
           apply_month_values, _move_v, labour_from_rates, h_nonregular, _year, h_death_off, _draw_attributes_education, _reborn,
           event, _remember, _dream_values):
    setattr(P, _f.__name__, _f)
P.band_of = staticmethod(band_of)
P.pension_revision = staticmethod(pension_revision)
P.saving_values = staticmethod(saving_values)
