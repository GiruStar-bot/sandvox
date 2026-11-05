# The twin of sim/modern/people/life_course.gd (LC_HH_PORT_PLAN §1): the persons' life course with households on, in the GDScript's
# loop orders. The rate functions the tiers share are the tiers' twins, imported (one source, row L0-t)
import math

from core import detmath, keyed
from core.gd import clampf, clampi, gd_round, maxf, maxi, minf, mini
from tiers.month import (lc_death_q as death_q, lc_grade_flows as grade_flows, lc_grade_kernel as grade_kernel,
                         lc_h_regrade as h_regrade, lc_income_factor as income_factor, lc_ltci_share as ltci_share,
                         lc_shares as shares)
from core.digest import Packed

from . import gdsort, households as HH
from . import pstate as ps

INSTITUTION = 5
NG = 5
INF = float("inf")


def _lc(p, k):
    return p.hh_spec["life_course"]["value"][k]["value"]


def _b10(a):
    return mini(a // 10, 8)


def draw_grade(p, i, tag):
    sh = shares(p, p.age[i], p.sex[i])
    return _grade_of(sh, p.u(tag, i, p.month))


def _grade_of(sh, x):
    acc = 0.0
    for g in range(NG):
        acc += sh[g]
        if x < acc:
            return g
    return NG - 1


def start(p):
    nm = _lc(p, "never_married")
    u0 = float(_lc(p, "union_start_age"))
    free = {}
    _resize_keep(p.health_class, p.n, 0)
    for i in range(p.n):
        p.health[i] = draw_grade(p, i, "grade0")
        draw_class(p, i, False)
        r = p.hh_role[i]
        single_adult = r == ps.R_HEAD and p.partner[i] < 0 and len(p.hh_members[p.hh_id[i]]) == 1
        if p.partner[i] >= 0 or r == ps.R_PARENT or (r == ps.R_HEAD and p.hh_type[p.hh_id[i]] == ps.HK_SINGLE_PARENT):
            p.ever_married[i] = 1
        elif single_adult and HH._nm_band(p.age[i], nm["ages"]) >= 0:
            key = HH._nm_band(p.age[i], nm["ages"]) * 2 + p.sex[i]
            free[key] = list(free.get(key, [])) + [i]
        elif single_adult and p.age[i] >= 25:
            k = 0
            for t in range(len(nm["ages"])):
                if p.age[i] >= int(nm["ages"][t]):
                    k = t
            p.ever_married[i] = 1 if p.u("evermar0", i) >= float(nm["men" if p.sex[i] == ps.MALE else "women"][k]) else 0
        p.ever_left[i] = 0 if r == ps.R_CHILD else 1
        p.last_birth[i] = -999
        if p.sex[i] == ps.FEMALE and p.partner[i] >= 0:
            p.union_month[i] = -12 * maxi(0, p.age[i] - int(gd_round(u0)))
            p.union_month[p.partner[i]] = p.union_month[i]
    for h in range(p.hh_n):
        ms = p.hh_members[h]
        mother = -1
        kids = 0
        for i2 in ms:
            if p.hh_role[i2] == ps.R_CHILD:
                kids += 1
            elif p.hh_role[i2] <= ps.R_PARTNER and (p.sex[i2] == ps.FEMALE or p.hh_type[h] == ps.HK_SINGLE_PARENT):
                mother = i2
        if mother >= 0 and p.sex[mother] == ps.FEMALE:
            p.births_n[mother] = kids
    _never_married_start(p, nm, free)
    cp = _lc(p, "completed_parity")
    for i3 in range(p.n):
        if p.sex[i3] == ps.FEMALE and p.age[i3] >= 35 and (p.partner[i3] >= 0 or (p.hh_role[i3] == ps.R_HEAD and p.hh_type[p.hh_id[i3]] == ps.HK_SINGLE_PARENT)):
            x = p.u("parity0", i3)
            acc = 0.0
            drawn = 4
            for k3 in range(5):
                acc += float(cp[str(k3)])
                if x < acc:
                    drawn = k3
                    break
            p.births_n[i3] = maxi(p.births_n[i3], drawn)
    _resize_keep(p.intends_marry, p.n, 0)
    p.intends_marry[:] = [-1] * p.n
    _resize_keep(p.intended_kids, p.n, 0)
    p.intended_kids[:] = [-1] * p.n
    for i4 in range(p.n):
        if p.ever_married[i4] == 1:
            if p.partner[i4] >= 0:
                p.intends_marry[i4] = 1
            else:
                _draw_intention(p, i4, 0)
        elif p.age[i4] >= 18:
            _draw_intention(p, i4)
        if p.sex[i4] == ps.FEMALE and p.age[i4] >= 15:
            _draw_kids(p, i4, p.births_n[i4])


def _resize_keep(arr, m, z):
    # Godot's resize: the held values kept, the rest zero
    arr.extend([z] * max(0, m - len(arr)))
    del arr[m:]


def year_turn(p, i):
    if p.age[i] >= 18 and p.intends_marry[i] < 0:
        _draw_intention(p, i)
    if p.sex[i] == ps.FEMALE and p.age[i] >= 15 and p.intended_kids[i] < 0:
        _draw_kids(p, i, p.births_n[i])


def _draw_intention(p, i, ended=-1):
    hi = h_intend(p, p.age[i], p.sex[i])
    p.intends_marry[i] = 1 if (p.below("lc_intend", i, 0, 0, hi) if ended < 0 else p.below("lc_reintend", i, ended, 0, hi)) else 0


def h_intend(p, a, s):
    im = _lc(p, "intend_to_marry")
    k = 0
    for b in range(len(im["bands"])):
        if a >= int(str(im["bands"][b]).split("-")[0]):
            k = b
    return float(im["men" if s == ps.MALE else "women"][k])


def _draw_kids(p, i, born):
    ik = law_kids(p, p.age[i])
    got = born
    for r in range(16):
        x = p.u("lc_kids", i, r)
        acc = 0.0
        k = 5
        for c in range(6):
            acc += float(ik[str(c)])
            if x < acc:
                k = c
                break
        if k >= born:
            got = k
            break
    p.intended_kids[i] = got


def law_kids(p, a):
    ikd = _lc(p, "intended_children")
    bands = ikd["bands"]
    b = 0
    for k0 in range(len(bands)):
        if a >= int(str(bands[k0]).split("-")[0]):
            b = k0
    return ikd["by_age"][b]


def _never_married_start(p, nm, free):
    lo = nm["ages"]
    tot = [0] * (len(lo) * 2)
    fixed_nm = [0] * (len(lo) * 2)
    is_free = {}
    for key in free:
        for i0 in free[key]:
            is_free[i0] = True
    for i in range(p.n):
        b = HH._nm_band(p.age[i], lo)
        if b < 0:
            continue
        tot[b * 2 + p.sex[i]] += 1
        if i not in is_free and p.ever_married[i] == 0:
            fixed_nm[b * 2 + p.sex[i]] += 1
    p.lc_nm_short = [0.0] * (len(lo) * 2)
    for c in range(len(lo) * 2):
        ms = free.get(c, [])
        need = float(nm["men" if c % 2 == 0 else "women"][c // 2]) * float(tot[c]) - float(fixed_nm[c])
        q = clampf(need / float(len(ms)), 0.0, 1.0) if len(ms) > 0 else 0.0
        p.lc_nm_short[c] = need - q * float(len(ms))
        for i2 in ms:
            p.ever_married[i2] = 0 if p.u("evermar0", i2) < q else 1


def equivalized(p, i):
    mem = p.hh_members[p.hh_id[i]]
    s = 0.0
    for j in mem:
        s += p.income[j]
    return s / math.sqrt(float(len(mem)))


def _row_less(x, y):
    return float(x[0]) < float(y[0])


def quartile_rows(p):
    by = [[] for _ in range(9)]
    for i in range(p.n):
        by[_b10(p.age[i])].append([equivalized(p, i), p.weight[i], i])
    for rows in by:
        gdsort.sort_custom(rows, _row_less)
    return by


def quartile_cuts(p):
    by = quartile_rows(p)
    _resize_keep(p.lc_qcut, 27, 0.0)
    for b2 in range(9):
        rows = by[b2]
        tot = 0.0
        for r in rows:
            tot += float(r[1])
        acc = 0.0
        q = 0
        for r2 in rows:
            acc += float(r2[1])
            while q < 3 and acc >= tot * float(q + 1) / 4.0:
                p.lc_qcut[b2 * 3 + q] = float(r2[0])
                q += 1
        while q < 3:
            p.lc_qcut[b2 * 3 + q] = INF
            q += 1


def quartile_of(p, e, a):
    c = _b10(a) * 3
    if e < p.lc_qcut[c]:
        return 3
    if e < p.lc_qcut[c + 1]:
        return 2
    if e < p.lc_qcut[c + 2]:
        return 1
    return 0


def quartile(p, i):
    return quartile_of(p, equivalized(p, i), p.age[i])


def _mu(p, a, s):
    lt = _lc(p, "qx_2022")["men" if s == ps.MALE else "women"]
    q = float(lt[mini(a, len(lt) - 1)])
    return INF if q >= 1.0 else -detmath.log(1.0 - q)


def solve_c(p):
    quartile_cuts(p)
    m = _lc(p, "death_multiplier")
    ages = len(_lc(p, "qx_2022")["men"])
    w = [0.0] * (18 * NG * 4)
    ws = [0.0] * (ages * 2 * NG * 4)
    for i in range(p.n):
        gk = p.health[i] * 4 + quartile(p, i)
        w[(_b10(p.age[i]) * 2 + p.sex[i]) * NG * 4 + gk] += p.weight[i]
        ws[(mini(p.age[i], ages - 1) * 2 + p.sex[i]) * NG * 4 + gk] += p.weight[i]
    _resize_keep(p.lc_c, ages * 2, 0.0)
    p.lc_c_band = 0
    for a in range(ages):
        for s in range(2):
            src = ws
            cell = (a * 2 + s) * NG * 4
            tot = 0.0
            for x0 in range(NG * 4):
                tot += ws[cell + x0]
            if tot <= 0.0:
                src = w
                cell = (_b10(a) * 2 + s) * NG * 4
                p.lc_c_band += 1
                for x in range(NG * 4):
                    tot += w[cell + x]
            mu = _mu(p, a, s)
            if tot <= 0.0 or mu == INF:
                p.lc_c[a * 2 + s] = 1.0
                continue
            target = detmath.exp(-mu)
            lo = 0.0
            hi = 16.0
            for _it in range(60):
                c = 0.5 * (lo + hi)
                surv = 0.0
                for g in range(NG):
                    for k in range(4):
                        surv += src[cell + g * 4 + k] / tot * detmath.exp(-c * float(m[g]) * income_factor(p, a, k) * mu)
                if surv > target:
                    lo = c
                else:
                    hi = c
            p.lc_c[a * 2 + s] = 0.5 * (lo + hi)


def h_death(p, a, s, g, k):
    mu = _mu(p, a, s)
    if mu == INF:
        return 1.0
    ac = mini(a, len(p.lc_c) // 2 - 1)
    return death_q(p, p.lc_c[ac * 2 + s], a, g, k, mu, 1.0)


def _dband(a):
    return 0 if a < 65 else (1 if a < 75 else (2 if a < 85 else 3))


def dies(p, i):
    q = h_death(p, p.age[i], p.sex[i], p.health[i], quartile(p, i))
    p.lc_expected[_dband(p.age[i]) * 2 + p.sex[i]] += q
    if p.below("death", i, p.month, 0, q):
        p.lc_dying.append(i)
        return True
    return False


def h_retire(p):
    return 0.74


def grade_birthday(p):
    nn = {}
    key_of = [0] * p.n
    dying = {}
    for d0 in p.lc_dying:
        dying[d0] = True
    turning = []
    for i0 in range(p.n):
        if p.month % 12 == int(p.pid[i0] % 12) and i0 not in dying:
            turning.append(i0)
    for i in turning:
        key = (p.age[i] * 2 + p.sex[i]) * 4 + quartile(p, i)
        key_of[i] = key
        if key not in nn:
            nn[key] = [0.0] * (2 * NG)
        nn[key][p.health_class[i] * NG + p.health[i]] += p.weight[i]
    tl = {"res": 0.0}
    for k0 in ("before", "target", "after", "var", "stay", "stay_seed"):
        tl[k0] = [0.0] * (18 * NG)
    tl["stay_c"] = [0.0] * (36 * NG)
    tl["n_c"] = [0.0] * (36 * NG)
    for k5 in ("b4_target", "b4_after", "b4_var", "b4_n", "b4_exit"):
        tl[k5] = [0.0] * 14
    pm = {}
    for key2 in nn:
        a = key2 // 8
        s = (key2 // 4) % 2
        pi0 = shares(p, a, s)
        pt = 0.0
        for g7 in range(NG):
            pt += pi0[g7]
        n8 = nn[key2]
        out = grade_flows(p, n8, pi0)
        pm[key2] = out[0]
        tl["res"] = maxf(float(tl["res"]), float(out[1]))
        row = (s * 9 + _b10(a)) * NG
        nt = 0.0
        for x in range(2 * NG):
            nt += n8[x]
        for g in range(NG):
            tl["target"][row + g] += pi0[g] / pt * nt
        if a >= 65:
            tl["b4_target"][s * 7 + mini((a - 65) // 5, 6)] += pi0[4] / pt * nt
        for c in range(2):
            k = grade_kernel(p, c, pi0)
            for g2 in range(NG):
                tl["before"][row + g2] += n8[c * NG + g2]
                tl["stay_seed"][row + g2] += n8[c * NG + g2] * k[g2 * NG + g2]
    for i2 in turning:
        pr = pm[key_of[i2]]
        rw = p.health_class[i2] * NG + p.health[i2]
        x2 = p.u("t22b_grade", i2, p.month)
        acc = 0.0
        g3 = NG - 1
        for h in range(NG):
            acc += pr[rw * NG + h]
            if x2 < acc:
                g3 = h
                break
        row2 = (p.sex[i2] * 9 + _b10(p.age[i2])) * NG
        wi = p.weight[i2]
        for h2 in range(NG):
            q = pr[rw * NG + h2]
            tl["var"][row2 + h2] += wi * wi * q * (1.0 - q)
        tl["after"][row2 + g3] += wi
        if p.age[i2] >= 65:
            r5 = p.sex[i2] * 7 + mini((p.age[i2] - 65) // 5, 6)
            q4 = pr[rw * NG + 4]
            tl["b4_var"][r5] += wi * wi * q4 * (1.0 - q4)
            tl["b4_after"][r5] += wi if g3 == 4 else 0.0
            if p.health[i2] == 4:
                tl["b4_n"][r5] += wi
                tl["b4_exit"][r5] += wi if g3 == 3 else 0.0
        rc = p.health_class[i2] * 18 * NG + row2 + p.health[i2]
        tl["n_c"][rc] += wi
        if g3 == p.health[i2]:
            tl["stay"][row2 + g3] += wi
            tl["stay_c"][rc] += wi
        p.health[i2] = g3
    p.lc_t22b = {k: (Packed("f64", v) if isinstance(v, list) else v) for k, v in tl.items()}


def draw_class(p, i, at_birth):
    kp = _lc(p, "grade_kernel")
    pst = float(kp["stable_share"]) if at_birth else float(kp["p_stable_given_side"]["good" if p.health[i] < 2 else "bad"])
    p.health_class[i] = 0 if p.u("grade_class0", i) < pst else 1


def _log(p, i, kind, j, detail):
    p.life_log.append([p.month, p.pid[i], kind, p.pid[j] if j >= 0 else -1, detail, p.weight[i], p.sex[i]])


def _hh_remove(p, i):
    h = p.hh_id[i]
    ms = p.hh_members[h]
    if i in ms:
        ms.remove(i)
    if p.hh_role[i] == ps.R_HEAD and ms:
        nh = -1
        for j in ms:
            if p.hh_role[j] == ps.R_PARTNER:
                nh = j
        if nh < 0:
            nh = ms[0]
            for j2 in ms:
                if p.age[j2] > p.age[nh]:
                    nh = j2
        p.hh_role[nh] = ps.R_HEAD
    _classify(p, h)


def _hh_add(p, i, h, role):
    p.hh_members[h].append(i)
    p.hh_id[i] = h
    p.hh_role[i] = role
    p.set_pref(i, p.hh_pref[h])


def _new_household(p, pref, w, kind=0):
    p.hh_type.append(kind)
    p.hh_pref.append(pref)
    HH.add_household_weight(p, w)
    p.hh_members.append([])
    p.hh_n += 1
    return p.hh_n - 1


def _classify(p, h):
    if p.hh_type[h] == INSTITUTION:
        return
    ms = p.hh_members[h]
    if len(ms) <= 1:
        p.hh_type[h] = ps.HK_SINGLE
        return
    cnt = [0, 0, 0, 0, 0]
    for i in ms:
        cnt[p.hh_role[i]] += 1
    if cnt[ps.R_PARENT] + cnt[ps.R_OTHER] > 0:
        p.hh_type[h] = ps.HK_OTHER
    elif cnt[ps.R_CHILD] == 0:
        p.hh_type[h] = ps.HK_COUPLE if cnt[ps.R_PARTNER] == 1 else ps.HK_OTHER
    else:
        p.hh_type[h] = ps.HK_COUPLE_CHILDREN if cnt[ps.R_PARTNER] == 1 else ps.HK_SINGLE_PARENT


def _move_out(p, i, h_new, role):
    _hh_remove(p, i)
    _hh_add(p, i, h_new, role)


def _children_of(p, i):
    out = []
    if p.hh_role[i] > ps.R_PARTNER:
        return out
    for j in p.hh_members[p.hh_id[i]]:
        if p.hh_role[j] == ps.R_CHILD:
            out.append(j)
    return out


def _window(w, a):
    v = 0.0
    for k in w:
        if a >= int(k):
            v = float(w[k])
    return v


def _deaths(p):
    dead = [0] * p.n
    for i in p.lc_dying:
        if dead[i] == 1:
            continue
        dead[i] = 1
        p.lc_deaths[_dband(p.age[i]) * 2 + p.sex[i]] += 1
        _log(p, i, "death", p.partner[i], {"age": p.age[i], "grade": p.health[i] + 1})
        pt = p.partner[i]
        if pt >= 0:
            p.partner[pt] = -1
            _draw_intention(p, pt, p.month + 1)
            _log(p, pt, "widowed", i, {"age": p.age[pt]})
        p.partner[i] = -1
        ps.rel_drop_all(p, i)
        for m in range(ps.M):
            if p.member_of[i * ps.M + m] >= 0:
                ps.grp_leave(p, i, p.member_of[i * ps.M + m])
        _hh_remove(p, i)
    p.lc_dying = []
    return dead


def month(p):
    dead = _deaths(p)
    n0 = p.n
    acted = list(dead)
    fam = ps.D_FAMILY
    aut = ps.D_AUTONOMY
    dws = 0.0
    dwa = 0.0
    na = 0.0
    for i in range(n0):
        if dead[i] == 1 or p.age[i] < 18:
            continue
        dws += p.dw[i * ps.ND + fam]
        dwa += p.dw[i * ps.ND + aut]
        na += 1.0
    fam_mean = dws / maxf(1.0, na)
    aut_mean = dwa / maxf(1.0, na)
    pa = _lc(p, "partnering")
    births = []
    bi = _lc(p, "birth")
    lh = _lc(p, "leaving_home")
    dv = _lc(p, "divorce_choice")
    mi = _lc(p, "moving_in")
    ins = _lc(p, "institution")
    for i in range(n0):
        if acted[i] == 1:
            continue
        a = p.age[i]
        h = p.hh_id[i]
        if p.hh_type[h] == INSTITUTION:
            continue
        size = len(p.hh_members[h])
        hi = h_institution(ins, p, i, a, size)
        if hi > 0.0 and p.below("lc_inst", i, p.month, 0, hi):
            e_institution(p, i, h)
            acted[i] = 1
            continue
        hm = h_move_in(mi, p, i, a, size)
        if hm > 0.0 and p.below("lc_movein", i, p.month, 0, hm):
            to = _move_in_to(mi, p, i, a)
            if to >= 0:
                e_move_in(p, i, to)
                acted[i] = 1
                continue
        pt = p.partner[i]
        if pt >= 0 and p.sex[i] == ps.FEMALE and p.hh_id[pt] == h and acted[pt] == 0:
            if p.below("lc_divorce", i, p.month, 0, h_divorce(dv, p, i, pt, h)):
                e_divorce(p, i, pt, h)
                acted[i] = 1
                acted[pt] = 1
                continue
            hb = h_birth(bi, p, i, pt, a)
            if hb > 0.0 and p.below("lc_birth", i, p.month, 0, hb):
                births.append(i)
                acted[i] = 1
                continue
        hl = h_leave(lh, p, i, a, pt, aut_mean)
        if hl > 0.0 and p.below("lc_leave", i, p.month, 0, hl):
            e_leave(p, i, h)
            acted[i] = 1
            continue
        hp = h_look(pa, p, i, a, pt)
        if hp > 0.0 and p.below(TAG_PARTNER[0], i, p.month, 0, hp):
            pool = _met(p, i, dead)
            found = -1
            if pool:
                j2 = pool[keyed.below(len(pool), p.seed_v, "lc_partnerpick", int(p.pid[i] & ps.PID_LOW), p.month * 32, 0)]
                if acted[j2] == 0 and _can_pair(pa, p, i, j2, a, h):
                    c = _compat(p, i, j2, float(pa["trait_compat"]))
                    if p.below("lc_accept", i, p.month * 32, 0, h_accept(p, i, c, fam_mean, 1.0)) and \
                            p.below("lc_agree", j2, p.month * 32, 0, h_accept(p, j2, c, fam_mean, _window(pa["window"], p.age[j2]))):
                        found = j2
            if found >= 0 and not p.below("lc_econ", i, p.month, 0, h_carry(p, i, found)):
                found = -1
            if found >= 0:
                _partner(p, i, found)
                acted[i] = 1
                acted[found] = 1
    for m2 in births:
        _birth(p, m2)
    p.remove_persons(dead)
    for h2 in range(p.hh_n):
        _classify(p, h2)
    for i3 in range(p.n):
        h3 = p.hh_id[i3]
        p.hh_kind[i3] = ps.HK_SINGLE if p.hh_type[h3] == INSTITUTION else p.hh_type[h3]
        p.hh_size[i3] = float(len(p.hh_members[h3]))


# The partnering draw's tag, held in a list so row L-mf2 can change it by one character
TAG_PARTNER = ["lc_partner"]


def h_institution(ins, p, i, a, size):
    if a < int(ins["from_age"]) or p.health[i] < ps.GRADE_LIMITED:
        return 0.0
    return float(ins["kappa"]) * (float(ins["alone"]) if size == 1 else float(ins["with_others"]))


def h_move_in(mi, p, i, a, size):
    if a < 65 or size != 1 or p.health[i] < ps.GRADE_POOR:
        return 0.0
    return float(mi["kappa"]) * (float(mi["grade4"]) if p.health[i] >= ps.GRADE_LIMITED else 1.0)


def h_divorce(dv, p, i, pt, h):
    dmax = maxf(p.emotion(i, "discontent"), p.emotion(pt, "discontent"))
    pd = float(dv["kappa"]) * dmax * dmax
    pd *= 1.0 + float(dv["early_m0"]) * detmath.exp(-float(p.month - p.union_month[i]) / 12.0 / float(dv["early_tau_years"]))
    if 0.5 * (p.dd[i * ps.ND + ps.D_SECURITY] + p.dd[pt * ps.ND + ps.D_SECURITY]) > float(dv["money_line"]):
        pd *= float(dv["money"])
    for y in p.hh_members[h]:
        if p.age[y] < int(dv["young_child_age"]):
            pd *= float(dv["young_child"])
            break
    return pd


def h_birth(bi, p, i, pt, a):
    if a < 15 or a > 49 or p.month - p.last_birth[i] < int(bi["gap_months"]) or p.births_n[i] >= p.intended_kids[i]:
        return 0.0
    pw = float(bi["kappa"]) * _window(bi["fecundity"], a)
    pw *= 1.0 - 0.25 * (p.dd[i * ps.ND + ps.D_SECURITY] + p.dd[pt * ps.ND + ps.D_SECURITY])
    return pw


def h_leave(lh, p, i, a, pt, aut_mean):
    if p.hh_role[i] != ps.R_CHILD or a < 18 or pt >= 0:
        return 0.0
    pl = float(lh["kappa"]) * p.dw[i * ps.ND + ps.D_AUTONOMY] / maxf(1e-9, aut_mean)
    pl *= float(lh["earner"]) if p.income[i] >= float(lh["earner_man_yen"]) else float(lh["not_earner"])
    if a == 18 and p.employment[i] == ps.EMP_STUDENT and p.month % 12 == int(p.pid[i] % 12):
        pl *= float(lh["student_at_18"])
    return pl


def h_look(pa, p, i, a, pt):
    if pt >= 0 or a < 18 or a >= 75 or p.intends_marry[i] != 1:
        return 0.0
    return float(pa["kappa"]) * _window(pa["window"], a)


def h_accept(p, x, c, fam_mean, w):
    return minf(1.0, p.dw[x * ps.ND + ps.D_FAMILY] / maxf(1e-9, fam_mean) * (1.0 - 0.5 * p.dd[x * ps.ND + ps.D_SECURITY]) * w * c)


def h_carry(p, i, j):
    return minf(1.0, (p.income[i] + p.income[j]) / float(p.spec["consumption_man_yen_month"]["two_plus"]))


def _can_pair(pa, p, i, j, a, h):
    gap = (a - p.age[j]) if p.sex[i] == ps.MALE else (p.age[j] - a)
    return not (p.partner[j] >= 0 or p.hh_id[j] == h or gap < int(pa["gap"][0]) or gap > int(pa["gap"][1]) or p.age[j] < 18
                or p.age[j] >= 75 or p.intends_marry[j] != 1)


def _move_in_to(mi, p, i, a):
    for c in range(ps.C):
        j = p.contact_idx[i * ps.C + c]
        if j >= 0 and p.contact_kind[i * ps.C + c] == ps.K_FAMILY:
            gap = a - p.age[j]
            hj = p.hh_id[j]
            if gap >= int(mi["gap"][0]) and gap <= int(mi["gap"][1]) and p.hh_role[j] <= ps.R_PARTNER and p.pref[j] == p.pref[i] \
                    and p.hh_type[hj] != INSTITUTION and len(p.hh_members[hj]) >= 2:
                return j
    return -1


def e_institution(p, i, h):
    pt0 = p.partner[i]
    if pt0 >= 0:
        p.partner[pt0] = -1
        _draw_intention(p, pt0, p.month + 1)
        p.partner[i] = -1
    _move_out(p, i, _new_household(p, p.pref[i], p.hh_weight[h], INSTITUTION), 0)
    _log(p, i, "institution", pt0, {"age": p.age[i]})


def e_move_in(p, i, to):
    _move_out(p, i, p.hh_id[to], ps.R_PARENT)
    _classify(p, p.hh_id[to])
    _log(p, i, "moved_in", to, {"age": p.age[i]})


def h_custody(p):
    return float(_lc(p, "divorce_children_with_mother"))


def e_divorce(p, i, pt, h):
    kids = _children_of(p, i)
    with_mother = p.below("lc_custody", i, p.month, 0, h_custody(p))
    leaver = pt if with_mother else i
    p.partner[i] = -1
    p.partner[pt] = -1
    _draw_intention(p, i, p.month + 1)
    _draw_intention(p, pt, p.month + 1)
    _move_out(p, leaver, _new_household(p, p.pref[leaver], p.hh_weight[h]), 0)
    _classify(p, h)
    _log(p, i, "divorce", pt, {"years": float(p.month - p.union_month[i]) / 12.0, "children": len(kids), "with_mother": with_mother,
                                "wife_age": p.age[i]})


def e_leave(p, i, h):
    _move_out(p, i, _new_household(p, p.pref[i], p.hh_weight[h]), 0)
    p.ever_left[i] = 1
    _log(p, i, "left_home", -1, {"age": p.age[i]})


def move_household(p, i, dest, reason=""):
    h = p.hh_id[i]
    if p.hh_type[h] == INSTITUTION:
        return []
    if p.hh_role[i] <= ps.R_PARTNER:
        ms = list(p.hh_members[h])
        p.hh_pref[h] = dest
        for j in ms:
            p.set_pref(j, dest)
        _log(p, i, "moved", -1, {"to": dest, "members": len(ms), "reason": reason})
        return ms
    pt = p.partner[i]
    hn = _new_household(p, dest, p.hh_weight[h])
    if pt >= 0 and p.hh_id[pt] == h:
        man = i if p.sex[i] == ps.MALE else pt
        _move_out(p, man, hn, ps.R_HEAD)
        _move_out(p, pt if man == i else i, hn, ps.R_PARTNER)
        _classify(p, hn)
        _log(p, i, "moved", pt, {"to": dest, "members": 2, "reason": reason})
        return [i, pt]
    _move_out(p, i, hn, ps.R_HEAD)
    p.ever_left[i] = 1
    _log(p, i, "moved", -1, {"to": dest, "members": 1, "reason": reason})
    return [i]


def _compat(p, i, j, k):
    d = 0.0
    for t in range(ps.NT):
        d += abs(p.traits[i * ps.NT + t] - p.traits[j * ps.NT + t])
    return 1.0 - k * d / float(ps.NT)


def _met(p, i, dead):
    out = []
    seen = {i: True}
    front = []
    for c in range(ps.C):
        j = p.contact_idx[i * ps.C + c]
        if j >= 0 and j not in seen:
            seen[j] = True
            front.append(j)
    second = []
    for j2 in front:
        for c2 in range(ps.C):
            k = p.contact_idx[j2 * ps.C + c2]
            if k >= 0 and k not in seen:
                seen[k] = True
                second.append(k)
    for x in front + second:
        if (x >= len(dead) or dead[x] == 0) and p.sex[x] != p.sex[i] and p.partner[x] < 0 and p.hh_type[p.hh_id[x]] != INSTITUTION:
            out.append(x)
    return out


def _partner(p, i, j):
    man = i if p.sex[i] == ps.MALE else j
    woman = j if man == i else i
    hn = _new_household(p, p.pref[man], 0.5 * (p.hh_weight[p.hh_id[man]] + p.hh_weight[p.hh_id[woman]]))
    kids = []
    for x in (man, woman):
        if p.hh_role[x] == ps.R_HEAD and p.hh_type[p.hh_id[x]] == ps.HK_SINGLE_PARENT:
            kids.extend(_children_of(p, x))
    _move_out(p, man, hn, ps.R_HEAD)
    _move_out(p, woman, hn, ps.R_PARTNER)
    for k in kids:
        _move_out(p, k, hn, ps.R_CHILD)
    _classify(p, hn)
    p.partner[man] = woman
    p.partner[woman] = man
    for x2 in (man, woman):
        _log(p, x2, "partnered", man if x2 == woman else woman, {"age": p.age[x2], "first": p.ever_married[x2] == 0})
        p.ever_married[x2] = 1
        p.ever_left[x2] = 1
        p.union_month[x2] = p.month
    if not ps.rel_has_contact(p, man, woman) and ps.rel_add(p, man, woman, ps.K_FAMILY):
        if not ps.rel_add(p, woman, man, ps.K_FAMILY):
            ps.rel_unlink(p, man, woman)


def _birth(p, mother):
    h = p.hh_id[mother]
    code = p.pref[mother]
    k = int(p.next_k.get(code, 0))
    p.next_k[code] = k + 1
    j = p.new_person(code, k)
    p.partner[j] = -1
    p.intends_marry[j] = -1
    p.intended_kids[j] = -1
    p.last_birth[j] = -999
    p.union_month[j] = 0
    _hh_add(p, j, h, ps.R_CHILD)
    HH.set_member_weight(p, j)
    p.hh_kind[j] = p.hh_type[h]
    p.hh_size[j] = float(len(p.hh_members[h]))
    p.draw_person(j)
    p.health[j] = draw_grade(p, j, "grade0")
    draw_class(p, j, True)
    p.finish_person(j)
    for x in p.hh_members[h]:
        if x != j and p.contact_count(x) < ps.C and ps.rel_add(p, j, x, ps.K_FAMILY):
            if not ps.rel_add(p, x, j, ps.K_FAMILY):
                ps.rel_unlink(p, j, x)
    p.births_n[mother] += 1
    p.last_birth[mother] = p.month
    p.lc_births.append([p.month, p.age[mother], p.weight[mother]])
    _classify(p, h)
    _log(p, j, "birth", mother, {"mother_age": p.age[mother], "order": p.births_n[mother]})


def stage(p, cohort_now=None, before_cuts=None):
    # The cut L of LC_HH_PORT_PLAN §2: people.step's lines 1289-1294; before_cuts(p) reads the state between the rake and the cuts
    grade_birthday(p)
    month(p)
    p.reweight(cohort_now)
    if before_cuts is not None:
        before_cuts(p)
    quartile_cuts(p)
