# Stage group C of TR.build_start (tiers.gd at cd165891): the top tier's individuals, the emptied units dropped, the class residual
# and the sample points (START_PORT_PLAN §7)
import bisect
import math

from core import detmath as DM
from core import gdsort, keyed
from core.gd import clampf, clampi, idiv, imod, maxf, maxi, minf, mini
from tiers.start import b_class as B
from tiers.start import persons as PS
from tiers.start import tconst as T
from tiers.start.common import _largest, _v
from tiers.start.p import PArr

INF = math.inf
KEY_STRIDE = T.KEY_STRIDE
AGE_SLOTS = T.AGE_SLOTS
NTYPE = T.NTYPE
NEMP = T.NEMP
NCLASS = T.NCLASS
CLASS_NONE = T.CLASS_NONE
PEN_NONE = T.PEN_NONE
POINT_PID = T.POINT_PID
_POINT_SKIP = set(T.POINT_SKIP)


# tiers.gd 330
def _drop_empty(p):
    remap = PArr("i32")
    remap.resize(p.tr_units)
    key = PArr("i32")
    count = PArr("i64")
    ages = PArr("i64")
    size = PArr("i32")
    moff = PArr("i64")
    mcode = PArr("i32")
    mn = PArr("i64")
    kept = 0
    for u in range(p.tr_units):
        if p.tr_count[u] <= 0:
            remap[u] = -1
            continue
        remap[u] = kept
        kept += 1
        for f in range(KEY_STRIDE):
            key.append(p.tr_key[u * KEY_STRIDE + f])
        count.append(p.tr_count[u])
        for y in range(AGE_SLOTS):
            ages.append(p.tr_age_counts[u * AGE_SLOTS + y])
        size.append(p.tr_tier_size[u])
        moff.append(len(mcode))
        for m in range(p.tr_mix_off[u], p.tr_mix_off[u + 1]):
            if p.tr_mix_n[m] > 0:
                mcode.append(p.tr_mix_code[m])
                mn.append(p.tr_mix_n[m])
    moff.append(len(mcode))
    p.tr_margins["dropped_units"] = p.tr_units - kept
    p.tr_units = kept
    p.tr_key = key
    p.tr_count = count
    p.tr_age_counts = ages
    p.tr_tier_size = size
    p.tr_mix_off = moff
    p.tr_mix_code = mcode
    p.tr_mix_n = mn
    for i in range(len(p.tr_indiv_unit)):
        p.tr_indiv_unit[i] = remap[p.tr_indiv_unit[i]]


# tiers.gd 373
def mix_draw(p, u, x):
    acc = 0
    for m in range(p.tr_mix_off[u], p.tr_mix_off[u + 1]):
        acc += p.tr_mix_n[m]
        if x < acc:
            return m
    return p.tr_mix_off[u + 1] - 1


# tiers.gd 384
def _class_residual(p, adult_shares):
    by = [0.0] * NCLASS
    for m in range(len(p.tr_mix_code)):
        by[idiv(p.tr_mix_code[m], NTYPE * NEMP)] += float(p.tr_mix_n[m])
    by[0] += float(p.n)
    adults = 0.0
    for k in range(NCLASS - 1):
        adults += by[k]
    worst = 0.0
    for k2 in range(NCLASS - 1):
        want = adults * float(adult_shares[k2])
        worst = maxf(worst, abs(by[k2] - want) / maxf(1.0, want))
    return worst


# tiers.gd 1569
def _individuals(p, lines, tab):
    cls = _v(p, "classes")
    want = int(cls["individuals_top"])
    top = []
    tot = 0
    p.tr_indiv_code = PArr("i32")
    for u in range(p.tr_units):
        if p.tr_key[u * KEY_STRIDE + 3] == 0 and p.tr_count[u] > 0:
            top.append(u)
            tot += p.tr_count[u]
    free4 = {}
    for u0 in range(p.tr_units):
        for m0 in range(p.tr_mix_off[u0], p.tr_mix_off[u0 + 1]):
            if imod(idiv(p.tr_mix_code[m0], NEMP), NTYPE) == 4:
                k0 = "%d|%d|%d" % (p.tr_key[u0 * KEY_STRIDE], p.tr_key[u0 * KEY_STRIDE + 1], p.tr_key[u0 * KEY_STRIDE + 2])
                free4[k0] = int(free4.get(k0, 0)) + p.tr_mix_n[m0]
    for src in [p.tr_couples, p.tr_nh_couples]:
        # Why the comparison once per source and not per key as GDScript writes it: it is the same for every key of the source
        is_cp = src == p.tr_couples
        for kc in src:
            f = kc.split("|")
            if is_cp and int(f[3]) != 4:
                continue
            for side in [[int(f[1]) + 3, 0], [int(f[2]) + 3, 1]]:
                k1 = "%s|%d|%d" % (f[0], int(side[0]), int(side[1]))
                free4[k1] = int(free4.get(k1, 0)) - int(src[kc])
    draws = []
    dcodes = []
    redrawn = 0
    for q in range(want):
        if tot <= 0:
            break
        for attempt in range(64):
            x = keyed.below(tot, p.seed_v, "tier_indiv", q, attempt, 0)
            acc = 0
            done = False
            for u2 in top:
                acc += p.tr_count[u2]
                if x < acc:
                    if p.tr_count[u2] > 0:
                        m = mix_draw(p, u2, keyed.below(p.tr_count[u2], p.seed_v, "tier_indiv_mix", q, attempt, 0))
                        k2 = "%d|%d|%d" % (p.tr_key[u2 * KEY_STRIDE], p.tr_key[u2 * KEY_STRIDE + 1], p.tr_key[u2 * KEY_STRIDE + 2])
                        t4 = imod(idiv(p.tr_mix_code[m], NEMP), NTYPE) == 4
                        if t4 and int(free4.get(k2, 0)) <= 0:
                            redrawn += 1
                            break
                        if t4:
                            free4[k2] = int(free4[k2]) - 1
                        draws.append(u2)
                        dcodes.append(p.tr_mix_code[m])
                        p.tr_mix_n[m] -= 1
                        p.tr_count[u2] -= 1
                        tot -= 1
                    done = True
                    break
            if done:
                break
    p.tr_margins["indiv_redrawn"] = redrawn
    p.place_persons(len(draws))
    for i in range(len(draws)):
        u3 = draws[i]
        b = p.tr_key[u3 * KEY_STRIDE + 1]
        na = 0
        for y0 in range(AGE_SLOTS):
            na += p.tr_age_counts[u3 * AGE_SLOTS + y0]
        y = age_draw(p, u3, keyed.below(na, p.seed_v, "tier_age", i, 0, 0))
        p.tr_age_counts[u3 * AGE_SLOTS + y] -= 1
        a = b * 5 + y
        p.place_person(i, p.tr_key[u3 * KEY_STRIDE], 3000000 + i, a, p.tr_key[u3 * KEY_STRIDE + 2])
    for i2 in range(p.n):
        p.draw_person(i2)
        p.finish_person(i2)
        u4 = draws[i2]
        dc = dcodes[i2]
        p.tier_person(i2, imod(dc, NEMP), mini(imod(idiv(dc, NEMP), NTYPE), 4), -1.0, -1.0)
        _class_draw(p, i2, idiv(dc, NTYPE * NEMP), lines, tab, "tier_inc_i", i2)
        p.tr_indiv_unit.append(u4)
        p.tr_indiv_code.append(dc)


# tiers.gd 1654
def age_draw(p, u, x):
    acc = 0
    for y in range(AGE_SLOTS):
        acc += p.tr_age_counts[u * AGE_SLOTS + y]
        if x < acc:
            return y
    return AGE_SLOTS - 1


# tiers.gd 1666
def _points(p, lines, tab, tm):
    _point_counts(p)
    n_pts = p.tr_pt_off[p.tr_units]
    n_ind = p.n
    p.place_persons(n_ind + 1)
    scratch = n_ind
    p.tr_points = {}
    rows = point_rows(p)
    for r in rows:
        arr = PArr("i32") if r[1] == "i32" else PArr("f64")
        arr.resize(n_pts * int(r[2]))
        p.tr_points[r[0]] = arr
    phi = PArr("f64")
    phi.resize(n_pts)
    pen = PArr("f64")
    pen.resize(n_pts)
    kind = PArr("i32")
    kind.resize(n_pts)
    p.tr_pt_code = PArr("i32")
    p.tr_pt_code.resize(n_pts)
    copies = [(getattr(p, r[0]), p.tr_points[r[0]], int(r[2])) for r in rows]
    health = p.tr_points["health"]
    for u in range(p.tr_units):
        c = p.tr_key[u * KEY_STRIDE]
        b = p.tr_key[u * KEY_STRIDE + 1]
        s = p.tr_key[u * KEY_STRIDE + 2]
        stt = _point_states(p, u)
        off = p.tr_pt_off[u]
        for g in range(off, p.tr_pt_off[u + 1]):
            code = stt[0][g - off]
            p.tr_pt_code[g] = code
            a = b * 5 + int(stt[1][g - off])
            p.place_person(scratch, c, POINT_PID + g, a, s)
            p.draw_person(scratch)
            p.finish_person(scratch)
            p.tier_person(scratch, imod(code, NEMP), mini(imod(idiv(code, NEMP), NTYPE), 4), -1.0, -1.0)
            if idiv(code, NTYPE * NEMP) < CLASS_NONE:
                _class_draw(p, scratch, idiv(code, NTYPE * NEMP), lines, tab, "tier_inc", g)
            else:
                p.tier_income(scratch, p.income[scratch], -1.0)
            # Why slices and not GDScript's element loop: the same elements copied, without a Python loop per stride element
            for src, dst, st in copies:
                dst[g * st:(g + 1) * st] = src[scratch * st:(scratch + 1) * st]
            health[g] = PS.draw_grade(p, scratch, "grade0")
            pd = p.pid[scratch]
            phi[g] = float(p.tr_phi.get(pd, 1.0))
            pen[g] = float(p.tr_pension.get(pd, 0.0))
            kind[g] = int(p.tr_pension_kind.get(pd, -1))
            p.tr_phi.pop(pd, None)
            p.tr_pension.pop(pd, None)
            p.tr_pension_kind.pop(pd, None)
    p.tr_points["phi"] = phi
    p.tr_points["pension_own"] = pen
    p.tr_points["pension_kind"] = kind
    p.place_persons(n_ind)
    _class_factors(p, tm)


# tiers.gd 1728 (the start's own, on P; py/tiers/month.py's reads an St)
def _targets(p):
    U = p.tr_units
    by_pref = {}
    for u in range(U):
        c = p.tr_key[u * KEY_STRIDE]
        if c not in by_pref:
            by_pref[c] = []
        by_pref[c].append(u)
    kb = PArr("i64")
    kb.resize(U)
    for c2 in by_pref:
        us = by_pref[c2]
        total_n = 0
        for u2 in us:
            total_n += p.tr_count[u2]
        Pc = p.tr_k * len(us)
        worth = float(total_n) / float(maxi(1, Pc))
        n_one = 0
        rest_n = 0
        for u3 in us:
            if p.tr_count[u3] <= 0:
                kb[u3] = 0
            elif float(p.tr_count[u3]) < worth:
                kb[u3] = 1
                n_one += 1
            else:
                kb[u3] = -1
                rest_n += p.tr_count[u3]
        share = PArr("f64")
        share.resize(len(us))
        p_rest = maxi(0, Pc - n_one)
        for j in range(len(us)):
            if kb[us[j]] < 0:
                share[j] = float(p_rest) * float(p.tr_count[us[j]]) / float(maxi(1, rest_n))
        ints = _largest(share, p_rest)
        for j2 in range(len(us)):
            if kb[us[j2]] < 0:
                kb[us[j2]] = maxi(2, ints[j2])
    return kb


# tiers.gd 1775
def _point_counts(p):
    U = p.tr_units
    kb = _targets(p)
    p.tr_kb = kb.duplicate()
    p.tr_pt_off = PArr("i64")
    p.tr_pt_off.resize(U + 1)
    p.tr_pt_mass = PArr("i64")
    at = 0
    for u4 in range(U):
        p.tr_pt_off[u4] = at
        k = kb[u4]
        if k > 0:
            base = idiv(p.tr_count[u4], k)
            extra = imod(p.tr_count[u4], k)
            first = keyed.below(k, p.seed_v, "tier_pt_mass", u4, 0, 0)
            for j3 in range(k):
                p.tr_pt_mass.append(base + (1 if imod(j3 - first + k, k) < extra else 0))
        at += k
    p.tr_pt_off[U] = at


# tiers.gd 1797
def _at_cum(arr, off, n, x):
    acc = 0
    for m in range(n):
        acc += arr[off + m]
        if x < float(acc):
            return m
    return n - 1


# tiers.gd 1813
def _point_states(p, u):
    codes = PArr("i32")
    slots = PArr("i32")
    uc = keyed.u(p.seed_v, "tier_pt_mix", u, 0, 0)
    ua = keyed.u(p.seed_v, "tier_pt_age", u, 0, 0)
    off = p.tr_mix_off[u]
    nm = p.tr_mix_off[u + 1] - off
    g0 = p.tr_pt_off[u]
    k = p.tr_pt_off[u + 1] - g0
    slots.resize(k)
    acc = 0.0
    for g in range(g0, g0 + k):
        m = float(p.tr_pt_mass[g])
        codes.append(p.tr_mix_code[off + _at_cum(p.tr_mix_n, off, nm, acc + uc * m)])
        acc += m
    order = list(range(k))
    # Why the keys drawn once and not in the comparator: KEYED.raw is pure, so the comparisons and Godot's order are the same
    hd = keyed.head(p.seed_v, "tier_pt_perm")
    rk = [keyed.h64(hd, g0 + i, 0, 0) >> 11 for i in range(k)]
    gdsort.sort_custom(order, lambda i, j: rk[i] < rk[j])
    acc2 = 0.0
    for j2 in order:
        m2 = float(p.tr_pt_mass[g0 + j2])
        slots[j2] = _at_cum(p.tr_age_counts, u * AGE_SLOTS, AGE_SLOTS, acc2 + ua * m2)
        acc2 += m2
    return [codes, slots]


# tiers.gd 1878
def _trunc_normal(tab, zl, zh, u):
    if zl >= 0.0:
        ql = B._q(tab, zl)
        qh = B._q(tab, zh) if zh < INF else 0.0
        t = qh + (1.0 - u) * (ql - qh)
        z = -DM.inv_normal(t) if t > 0.0 else zl
    else:
        pl = B._phi(tab, zl) if zl > -INF else 0.0
        ph = B._phi(tab, zh) if zh < INF else 1.0
        t2 = pl + u * (ph - pl)
        if t2 <= 0.0:
            z = zl
        elif t2 <= 0.5:
            z = DM.inv_normal(t2)
        else:
            z = -DM.inv_normal(1.0 - t2)
    return clampf(z, zl, zh)


# tiers.gd 1996
def _edu_given_class(p, i, lo, hi, tab, tag, key):
    a = p.age[i]
    if a < 22:
        return
    sigma = float(p.spec["wage_sigma"]["value"])
    wts = []
    tot = 0.0
    rows = B._pension_law(p, a, p.sex[i]) if a >= p.PENSION_AGE else [[1.0, 0.0, 0.0, PEN_NONE]]
    for d in range(len(p.EDUCATION)):
        lm = DM.log(B._component_m(p, a, p.sex[i], p.employment[i], d))
        m = 0.0
        for r in rows:
            cm = 0.5 * (float(r[1]) + float(r[2]))
            m += float(r[0]) * _shifted_mass(tab, lm, sigma, lo - cm, hi - cm)
        wts.append(B._edu_share(p, a, d) * m)
        tot += wts[d]
    if tot <= 0.0:
        return
    x = keyed.u(p.seed_v, tag, key, 1, 0) * tot
    acc = 0.0
    for d2 in range(len(wts)):
        acc += wts[d2]
        if x < acc or d2 == len(wts) - 1:
            p.tier_education(i, d2)
            return


# tiers.gd 2083
def _class_draw(p, i, k, lines, tab, tag, key):
    hi = INF if k == 0 else lines[k - 1]
    lo = lines[k] if k < len(lines) else 0.0
    e = p.employment[i]
    a = p.age[i]
    if a >= p.PENSION_AGE and (e == p.EMP_RETIRED or e == p.EMP_NONE):
        _pension_draw(p, i, lo, hi, tag, key)
        return
    if (e == p.EMP_REGULAR or e == p.EMP_NONREGULAR or e == p.EMP_UNEMPLOYED) and p.income[i] > 0.0:
        _edu_given_class(p, i, lo, hi, tab, tag, key)
    w = p.income[i]
    u = keyed.u(p.seed_v, tag, key, 0, 0)
    if (e == p.EMP_REGULAR or e == p.EMP_NONREGULAR or e == p.EMP_UNEMPLOYED) and w > 0.0:
        sigma = float(p.spec["wage_sigma"]["value"])
        z0 = p.normal("wage", i)
        c = 0.0
        if a >= p.PENSION_AGE:
            rows = B._pension_law(p, a, p.sex[i])
            wts = []
            tot = 0.0
            for r in rows:
                cm = 0.5 * (float(r[1]) + float(r[2]))
                wts.append(float(r[0]) * _shifted_mass(tab, DM.log(w) - sigma * z0, sigma, lo - cm, hi - cm))
                tot += wts[len(wts) - 1]
            if tot > 0.0:
                x = keyed.u(p.seed_v, tag, key, 2, 0) * tot
                acc = 0.0
                for j in range(len(rows)):
                    acc += wts[j]
                    if x < acc or j == len(rows) - 1:
                        c = 0.5 * (float(rows[j][1]) + float(rows[j][2]))
                        p.tier_pension(i, c, int(rows[j][3]))
                        break
        lo2 = lo - c
        hi2 = hi - c
        zl = z0 + DM.log(lo2 / w) / sigma if lo2 > 0.0 else -INF
        zh = z0 + DM.log(hi2 / w) / sigma if hi2 < INF else INF
        f = DM.exp(sigma * (_trunc_normal(tab, zl, zh, u) - z0))
        p.tier_income(i, w * f + c, -1.0)
    elif e == p.EMP_RETIRED and w > 0.0:
        p0 = w / (0.7 + 0.6 * p.u("pension", i))
        ul = clampf((lo / p0 - 0.7) / 0.6, 0.0, 1.0)
        uh = clampf((hi / p0 - 0.7) / 0.6, 0.0, 1.0) if hi < INF else 1.0
        p.tier_income(i, p0 * (0.7 + 0.6 * (ul + u * (uh - ul))), -1.0)
    else:
        p.tier_income(i, w, -1.0)


# tiers.gd 2134
def _shifted_mass(tab, lm, sigma, lo, hi):
    if hi <= 0.0:
        return 0.0
    ql = B._q(tab, (DM.log(lo) - lm) / sigma) if lo > 0.0 else 1.0
    qh = B._q(tab, (DM.log(hi) - lm) / sigma) if hi < INF else 0.0
    return maxf(0.0, ql - qh)


# tiers.gd 2144
def _pension_draw(p, i, lo, hi, tag, key):
    rows = B._pension_law(p, p.age[i], p.sex[i])
    wts = []
    tot = 0.0
    for r in rows:
        m = 0.0
        if int(r[3]) == PEN_NONE:
            m = float(r[0]) if lo <= 0.0 else 0.0
        else:
            m = float(r[0]) * maxf(0.0, minf(hi, float(r[2])) - maxf(lo, float(r[1]))) / (float(r[2]) - float(r[1]))
        wts.append(m)
        tot += m
    if tot <= 0.0:
        p.tier_income(i, p.income[i], -1.0)
        return
    x = keyed.u(p.seed_v, tag, key, 0, 0) * tot
    acc = 0.0
    for j in range(len(rows)):
        acc += wts[j]
        if x < acc or j == len(rows) - 1:
            amount = 0.0
            if int(rows[j][3]) != PEN_NONE:
                a0 = maxf(lo, float(rows[j][1]))
                amount = a0 + keyed.u(p.seed_v, tag, key, 3, 0) * (minf(hi, float(rows[j][2])) - a0)
            p.tier_pension(i, amount, int(rows[j][3]))
            p.tier_income(i, amount, -1.0)
            return


# tiers.gd 2214
def _tail_of(tm, y):
    if y <= float(tm["median"]):
        return y
    gy = tm["gy"]
    gs = tm["gs"]
    ly = DM.log(y)
    at = clampi(bisect.bisect_left(gy, ly) - 1, 0, len(gy) - 2)
    ls = gs[at] + (gs[at + 1] - gs[at]) * (ly - gy[at]) / (gy[at + 1] - gy[at])
    return maxf(float(tm["median"]), B._gpi_q(tm["gpi"], maxf(0.5, 1.0 - DM.exp(ls))))


# tiers.gd 2409
def _class_factors(p, tm):
    pub = _v(p, "classes")["mean_income_yen_year"]
    inc = p.tr_points["income"]
    phi = p.tr_points["phi"]
    pen = p.tr_points["pension_own"]
    qi = p.tr_points["q_income"]
    emp = p.tr_points["employment"]
    ages = p.tr_points["age"]
    s = [0.0] * CLASS_NONE
    m = [0.0] * CLASS_NONE
    for g in range(len(p.tr_pt_code)):
        k = idiv(p.tr_pt_code[g], NTYPE * NEMP)
        if k < CLASS_NONE:
            y = _tail_of(tm, inc[g])
            pg = pen[g] * p.pension_index_at(ages[g]) if ages[g] >= p.PENSION_AGE else 0.0
            if (emp[g] == p.EMP_REGULAR or emp[g] == p.EMP_NONREGULAR or emp[g] == p.EMP_UNEMPLOYED) and inc[g] > pg:
                phi[g] *= (y - pg) / (inc[g] - pg)
            elif (emp[g] == p.EMP_RETIRED or (emp[g] == p.EMP_NONE and ages[g] >= p.PENSION_AGE)) and inc[g] > 0.0:
                pen[g] *= y / inc[g]
            inc[g] = y
            s[k] += inc[g] * float(p.tr_pt_mass[g])
            m[k] += float(p.tr_pt_mass[g])
        qi[g] = inc[g]
    for i in range(p.n):
        k2 = idiv(p.tr_indiv_code[i], NTYPE * NEMP)
        x = _tail_of(tm, p.income[i])
        p.tier_income(i, x, x * 120.0)
        s[k2] += x
        m[k2] += 1.0
    c = PArr("f64")
    c.resize(CLASS_NONE)
    for k3 in range(CLASS_NONE):
        c[k3] = float(pub[k3]) / 12.0 / 1e4 / (s[k3] / m[k3]) if s[k3] > 0.0 else 1.0
    p.tr_margins["class_factor"] = c
    p.tr_margins["tail_lines"] = tm["ty"]
    p.tr_margins["gpi"] = tm["gpi"]


# tiers.gd 2530
def point_rows(p):
    out = []
    for f in p.fields():
        if int(f[2]) > 0 and f[0] not in _POINT_SKIP and f[1] != "i64":
            out.append([f[0], f[1], int(f[2])])
    return out


def st09_individuals(p, ctx):
    _individuals(p, ctx["lines"], ctx["tab"])


def st10_drop_empty(p, ctx):
    _drop_empty(p)


def st11_class_residual(p, ctx):
    p.tr_residual.append(_class_residual(p, ctx["adult_shares"]))


def st12_points(p, ctx):
    _points(p, ctx["lines"], ctx["tab"], ctx["tm"])
