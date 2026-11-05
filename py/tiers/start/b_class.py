# The start's class stage group (tiers.gd at cd165891): the class lines from the generator's income law, the cells split over
# employment x class, the top tier held, and the units built from the cells (build_start's stages 06_class, 07_cells, 08_units)
import math

from core import detmath as DM
from core import gdsort, keyed
from core.gd import clampf, clampi, idiv, maxf, maxi, minf, mini, roundf
from core.prims import systematic
from tiers.start import a_fit as A
from tiers.start import tconst as T
from tiers.start.common import _v
from tiers.start.p import PArr

_CELL0 = [0, 0, 0, 0, 0, 0, 0.0]


def _cell_key(c, b, s, k, t, e):
    return "%02d|%02d|%d|%d|%d|%d" % (c, b, s, k, t, e)


# tiers.gd 301
def _hold_top(p, cells, top_real, cand):
    want = int(math.floor(top_real + 0.5))
    have = 0
    for c in cand:
        have += int(cells.get(_cell_key(c[1], c[2], c[3], 0, c[4], c[5]), _CELL0)[6])
    order = list(range(len(cand)))
    # Why the raw draws taken once and not in the comparator: they are pure functions of the index, so the comparisons are the same
    rw = [keyed.raw(p.seed_v, "tier_hold", i, 0, 0) for i in range(len(cand))]
    gdsort.sort_custom(order, lambda i, j: rw[i] < rw[j])
    for i2 in order:
        if have == want:
            break
        c2 = cand[i2]
        k0 = _cell_key(c2[1], c2[2], c2[3], 0, c2[4], c2[5])
        k5 = _cell_key(c2[1], c2[2], c2[3], 5, c2[4], c2[5])
        n0 = int(cells.get(k0, _CELL0)[6])
        x = float(c2[0])
        if have > want and n0 > int(math.floor(x)):
            cells[k0][6] = float(n0 - 1)
            _cell_add(cells, int(c2[1]), int(c2[2]), int(c2[3]), 5, int(c2[4]), int(c2[5]), 1.0)
            have -= 1
        elif have < want and n0 < int(math.ceil(x)) and k5 in cells and int(cells[k5][6]) > 0:
            cells[k5][6] = float(int(cells[k5][6]) - 1)
            _cell_add(cells, int(c2[1]), int(c2[2]), int(c2[3]), 0, int(c2[4]), int(c2[5]), 1.0)
            have += 1
    p.tr_residual.append(float(have - want))


# tiers.gd 400
def _cell_add(cells, c, b, s, k, t, e, x):
    ks = _cell_key(c, b, s, k, t, e)
    if ks in cells:
        cells[ks][6] += x
    else:
        cells[ks] = [c, b, s, k, t, e, x]


# tiers.gd 1840
def _phi_table():
    n = int(roundf(-T.PHI_ZMIN / T.PHI_STEP)) + 1
    out = PArr("f64")
    out.resize(n)
    for i in range(n):
        z = T.PHI_ZMIN + float(i) * T.PHI_STEP
        lo = -700.0
        hi = DM.log(0.5)
        for it in range(64):
            mid = 0.5 * (lo + hi)
            if DM.inv_normal(DM.exp(mid)) < z:
                lo = mid
            else:
                hi = mid
        out[i] = 0.5 * (lo + hi)
    return out


# tiers.gd 1858
def _log_phi(tab, z):
    if z <= T.PHI_ZMIN:
        return -800.0
    x = (minf(z, 0.0) - T.PHI_ZMIN) / T.PHI_STEP
    i = mini(int(math.floor(x)), len(tab) - 2)
    return tab[i] + (tab[i + 1] - tab[i]) * (x - float(i))


# tiers.gd 1867
def _phi(tab, z):
    if z <= 0.0:
        return DM.exp(_log_phi(tab, z))
    return 1.0 - DM.exp(_log_phi(tab, -z))


# tiers.gd 1873
def _q(tab, z):
    return _phi(tab, -z)


# tiers.gd 1901
def _income_law(p, b, s, e, age_in_band):
    sp = p.spec
    out = []
    if e == p.EMP_NONE and b * 5 < p.PENSION_AGE:
        return [[1.0, 2, 0.0, 0.0]]
    if e == p.EMP_STUDENT:
        return [[1.0, 2, float(sp["student_income_man_yen"]["value"]), 0.0]]
    sigma = float(sp["wage_sigma"]["value"])
    pr = sp["pension_rule"]["value"]
    top = p.AGES if b == T.BANDS - 1 else b * 5 + 5
    wsum = 0.0
    for a0 in range(b * 5, top):
        wsum += age_in_band[a0 * 2 + s]
    for a in range(b * 5, top):
        wa = age_in_band[a * 2 + s] / wsum if wsum > 0.0 else 1.0 / float(top - b * 5)
        if wa <= 0.0:
            continue
        if a >= p.PENSION_AGE and (e == p.EMP_RETIRED or e == p.EMP_NONE):
            for r in _pension_law(p, a, s):
                out.append([wa * float(r[0]), 2, 0.0, 0.0] if int(r[3]) == T.PEN_NONE else [wa * float(r[0]), 1, float(r[1]), float(r[2])])
            continue
        if e == p.EMP_RETIRED:
            idx = float(p.pension["new"]) if a <= int(pr["new_until_age"]) else float(p.pension["old"])
            p0 = float(sp["pension_man_yen"]["value"]) * idx
            out.append([wa, 1, 0.7 * p0, 1.3 * p0])
            continue
        for d in range(len(p.EDUCATION)):
            sh = _edu_share(p, a, d)
            if sh <= 0.0:
                continue
            lm = DM.log(_component_m(p, a, s, e, d))
            if a < p.PENSION_AGE:
                out.append([wa * sh, 0, lm, sigma])
                continue
            for r2 in _pension_law(p, a, s):
                out.append([wa * sh * float(r2[0]), 3, lm, sigma, 0.5 * (float(r2[1]) + float(r2[2]))])
    return out


# tiers.gd 1942
def _pension_law(p, a, s):
    pe = _v(p, "pension_entitlement")
    sx = "male" if s == p.MALE else "female"
    bi = clampi(idiv(a - p.PENSION_AGE, 5), 0, 3)
    none = float(pe["none_share"][sx][bi])
    basic = float(pe["basic_only_share"][sx][bi])
    sb = float(pe["short_record_share"][sx]["basic_only"])
    se = float(pe["short_record_share"][sx]["employee"])
    idx = p.pension_index_at(a)
    out = [[none, 0.0, 0.0, T.PEN_NONE]]
    for row in [[T.PEN_BASIC, "basic_only_classes", basic * (1.0 - sb)], [T.PEN_BASIC_SHORT, "basic_only_short_classes", basic * sb],
                [T.PEN_EMPLOYEE, "employee_classes", (1.0 - basic) * (1.0 - se)], [T.PEN_EMPLOYEE_SHORT, "employee_short_classes", (1.0 - basic) * se]]:
        t = pe[str(row[1])][sx]
        c = t["counts"]
        n = 0.0
        for x in c:
            n += float(x)
        for k in range(len(c)):
            hi = float(k + 1) if k < len(c) - 1 else float(k) + float(t["top_width"])
            out.append([(1.0 - none) * float(row[2]) * float(c[k]) / n, float(k) * idx, hi * idx, int(row[0])])
    return out


# tiers.gd 1966
def _edu_share(p, a, d):
    if a < 22:
        return 1.0 if d == 0 else 0.0
    eb = "22_34" if a < 35 else ("35_54" if a < 55 else "55_plus")
    return float(p.spec["education_shares_by_age"][eb][p.EDUCATION[d]])


# tiers.gd 1975
def _component_m(p, a, s, e, d):
    sp = p.spec
    w = sp["wage_regular_man_yen"]
    base = float(w["male"]) if s == p.MALE else float(w["female"])
    base *= float(sp["wage_age_curve"][str(clampi(idiv(a, 10) * 10, 20, 70))])
    base *= p.wage_index
    if e == p.EMP_NONREGULAR:
        base *= float(sp["non_regular_wage_factor"]["value"])
    elif e == p.EMP_UNEMPLOYED:
        base *= float(sp["unemployment_benefit_factor"]["value"])
    if e == p.EMP_REGULAR or e == p.EMP_NONREGULAR:
        cr = _v(p, "wage_cash_ratio")
        base *= float(cr["regular" if e == p.EMP_REGULAR else "non_regular"]["male" if s == p.MALE else "female"][0 if a < 20 else mini(11, idiv(a - 20, 5) + 1)])
    skill = clampf(20.0 + 15.0 * d + 0.8 * float(maxf(0.0, a - 22)), 0.0, 100.0)
    return base * float(sp["wage_education_factor"][p.EDUCATION[d]]) * (1.0 + 0.004 * (skill - 50.0))


# tiers.gd 2024
def _above(tab, law, line):
    # Why the logs cached within the call and not taken per component: DM.log is a pure function, so the cached value is the same
    # bits, and the class lines' and the tail's bisections read this about 2 x 10^7 times
    lg = {}
    s = 0.0
    for c in law:
        w = float(c[0])
        kind = int(c[1])
        if kind == 0:
            ll = lg.get(line)
            if ll is None:
                ll = lg[line] = DM.log(line)
            s += w * _q(tab, (ll - float(c[2])) / float(c[3]))
        elif kind == 1:
            s += w * clampf((float(c[3]) - line) / (float(c[3]) - float(c[2])), 0.0, 1.0)
        elif kind == 3:
            t = line - float(c[4])
            if t > 0.0:
                lt = lg.get(t)
                if lt is None:
                    lt = lg[t] = DM.log(t)
                s += w * _q(tab, (lt - float(c[2])) / float(c[3]))
            else:
                s += w * 1.0
        else:
            s += w * (1.0 if float(c[2]) > line else 0.0)
    return s


# tiers.gd 2043
def _class_lines(tab, laws, mass, adult_shares):
    adults = 0.0
    for k in mass:
        adults += float(mass[k])
    lines = PArr("f64")
    cum = 0.0
    for c in range(len(adult_shares) - 1):
        cum += float(adult_shares[c])
        lo = DM.log(1e-3)
        hi = DM.log(1e7)
        for it in range(80):
            mid = 0.5 * (lo + hi)
            g = 0.0
            for k2 in mass:
                g += float(mass[k2]) * _above(tab, laws[k2], DM.exp(mid))
            if g > cum * adults:
                lo = mid
            else:
                hi = mid
        lines.append(DM.exp(0.5 * (lo + hi)))
    return lines


# tiers.gd 2067
def _class_probs(tab, law, lines):
    out = PArr("f64")
    prev = 0.0
    for c in range(len(lines)):
        a = _above(tab, law, lines[c])
        out.append(maxf(0.0, a - prev))
        prev = a
    out.append(maxf(0.0, 1.0 - prev))
    return out


# tiers.gd 2178
def _tail_map(p, tab, laws, mass, lines, adult_shares):
    tl = _v(p, "income_tail")
    adults = 0.0
    for k in mass:
        adults += float(mass[k])
    med = lines[len(lines) - 1]
    knots = []
    cum = 0.0
    for c in range(len(lines)):
        cum += float(adult_shares[c])
        knots.append([DM.log(lines[c]), DM.log(cum)])
    lo = DM.log(med)
    hi = DM.log(1e5)
    for i in range(T.TAIL_GRID):
        ly = lo + (hi - lo) * float(i) / float(T.TAIL_GRID - 1)
        g = 0.0
        for k2 in mass:
            g += float(mass[k2]) * _above(tab, laws[k2], DM.exp(ly))
        if i > 0 and g > 0.0:
            knots.append([ly, DM.log(g / adults)])
    gdsort.sort_custom(knots, lambda a, b: float(a[0]) < float(b[0]))
    gy = PArr("f64")
    gs = PArr("f64")
    for q in knots:
        if float(q[0]) >= lo - 1e-12:
            gy.append(float(q[0]))
            gs.append(float(q[1]))
    gpi = _gpi_fit(med, _below_mean(tab, laws, mass, med), tl)
    ty = PArr("f64", [lo])
    for p0 in [0.9, 0.99, 0.999, 0.9999]:
        ty.append(DM.log(_gpi_q(gpi, p0)))
    return {"gy": gy, "gs": gs, "gpi": gpi, "ty": ty, "median": med}


# tiers.gd 2227
def _below_mean(tab, laws, mass, med):
    tot = 0.0
    adults = 0.0
    for k in mass:
        adults += float(mass[k])
        s = 0.0
        for c in laws[k]:
            w = float(c[0])
            kind = int(c[1])
            if kind == 0:
                mu = float(c[2])
                sg = float(c[3])
                s += w * DM.exp(mu + 0.5 * sg * sg) * _phi(tab, (DM.log(med) - mu - sg * sg) / sg)
            elif kind == 1:
                a = float(c[2])
                b = float(c[3])
                if med >= b:
                    s += w * 0.5 * (a + b)
                elif med > a:
                    s += w * (med * med - a * a) / (2.0 * (b - a))
            elif kind == 3:
                mu3 = float(c[2])
                sg3 = float(c[3])
                t3 = med - float(c[4])
                if t3 > 0.0:
                    s += w * (DM.exp(mu3 + 0.5 * sg3 * sg3) * _phi(tab, (DM.log(t3) - mu3 - sg3 * sg3) / sg3) + float(c[4]) * _phi(tab, (DM.log(t3) - mu3) / sg3))
            else:
                if float(c[2]) <= med:
                    s += w * float(c[2])
        tot += float(mass[k]) * s
    return tot / adults


# tiers.gd 2261
def _quintic(h, f0, f1, d0, d1, s0, s1):
    c2 = 0.5 * s0
    a = f1 - (f0 + d0 * h + c2 * h * h)
    bd = d1 - (d0 + 2.0 * c2 * h)
    cc = s1 - 2.0 * c2
    return PArr("f64", [f0, d0, c2, (10.0 * a - 4.0 * bd * h + 0.5 * cc * h * h) / (h * h * h),
                        (-15.0 * a + 7.0 * bd * h - cc * h * h) / (h * h * h * h), (6.0 * a - 3.0 * bd * h + 0.5 * cc * h * h) / (h * h * h * h * h)])


# tiers.gd 2270
def _third(c, u):
    return 6.0 * c[3] + 24.0 * c[4] * u + 60.0 * c[5] * u * u


# tiers.gd 2277
def _gpi_spline(kn):
    n = len(kn)
    m = []
    r = PArr("f64")
    for i in range(n):
        row = PArr("f64")
        row.resize(n)
        m.append(row)
        r.append(0.0)

    def lin(i, at_end):
        h = float(kn[i + 1][0]) - float(kn[i][0])
        u = h if at_end else 0.0
        base = _third(_quintic(h, kn[i][1], kn[i + 1][1], kn[i][2], kn[i + 1][2], 0.0, 0.0), u)
        a = _third(_quintic(h, kn[i][1], kn[i + 1][1], kn[i][2], kn[i + 1][2], 1.0, 0.0), u) - base
        b = _third(_quintic(h, kn[i][1], kn[i + 1][1], kn[i][2], kn[i + 1][2], 0.0, 1.0), u) - base
        return [a, b, base]

    e0 = lin(0, False)
    m[0][0] = e0[0]
    m[0][1] = e0[1]
    r[0] = -e0[2]
    for k in range(1, n - 1):
        l1 = lin(k - 1, True)
        l2 = lin(k, False)
        m[k][k - 1] += l1[0]
        m[k][k] += l1[1] - l2[0]
        m[k][k + 1] -= l2[1]
        r[k] = l2[2] - l1[2]
    en = lin(n - 2, True)
    m[n - 1][n - 2] = en[0]
    m[n - 1][n - 1] = en[1]
    r[n - 1] = -en[2]
    s = _solve(m, r)
    out = []
    for i2 in range(n - 1):
        out.append(_quintic(float(kn[i2 + 1][0]) - float(kn[i2][0]), kn[i2][1], kn[i2 + 1][1], kn[i2][2], kn[i2 + 1][2], s[i2], s[i2 + 1]))
    return out


# tiers.gd 2316
def _solve(m, r):
    n = len(r)
    a = []
    for i in range(n):
        a.append(PArr("f64", m[i]))
    b = PArr("f64", r)
    for c in range(n):
        piv = c
        for i2 in range(c + 1, n):
            if abs(a[i2][c]) > abs(a[piv][c]):
                piv = i2
        t = a[c]
        a[c] = a[piv]
        a[piv] = t
        tb = b[c]
        b[c] = b[piv]
        b[piv] = tb
        for i3 in range(c + 1, n):
            f = a[i3][c] / a[c][c]
            for j in range(c, n):
                a[i3][j] -= f * a[c][j]
            b[i3] -= f * b[c]
    x = PArr("f64")
    x.resize(n)
    for i4 in range(n - 1, -1, -1):
        acc = b[i4]
        for j2 in range(i4 + 1, n):
            acc -= a[i4][j2] * x[j2]
        x[i4] = acc / a[i4][i4]
    return x


# tiers.gd 2349
def _gpi_q(g, p):
    kn = g["knots"]
    last = kn[len(kn) - 1]
    x = -DM.log(1.0 - p)
    if x >= float(last[0]):
        b = 1.0 / float(last[2])
        alpha = b / (b - 1.0)
        q_last = float(last[2]) * DM.exp(-float(last[1])) * DM.exp(float(last[0]))
        return q_last * DM.exp((x - float(last[0])) / alpha)
    seg = g["segments"]
    i = 0
    while i < len(kn) - 2 and x > float(kn[i + 1][0]):
        i += 1
    c = seg[i]
    u = x - float(kn[i][0])
    f = c[0] + u * (c[1] + u * (c[2] + u * (c[3] + u * (c[4] + u * c[5]))))
    d = c[1] + u * (2.0 * c[2] + u * (3.0 * c[3] + u * (4.0 * c[4] + u * 5.0 * c[5])))
    return d * DM.exp(x - f)


# tiers.gd 2371
def _gpi_knots(med, b_half, mu, q1, s1, q01, s01):
    out = []
    for row in [[0.5, med, mu - b_half], [0.99, q1, s1 * mu], [0.999, q01, s01 * mu]]:
        p = float(row[0])
        i = float(row[2])
        out.append([-DM.log(1.0 - p), -DM.log(i), (1.0 - p) * float(row[1]) / i])
    return out


# tiers.gd 2381
def _gpi_fit(med, b_half, tl):
    lines = tl["lines_yen_year"]
    sh = tl["cash_income_shares_pct"]
    q10 = float(lines[0]) / 12.0 / 1e4
    q1 = float(lines[1]) / 12.0 / 1e4
    q01 = float(lines[2]) / 12.0 / 1e4
    s1 = float(sh["top1"]) / 100.0
    s01 = float(sh["top0_1"]) / 100.0
    lo = 0.009 * q1 / (s1 - s01)
    hi = 0.009 * q01 / (s1 - s01)
    g = {}
    for it in range(100):
        mid = 0.5 * (lo + hi)
        kn = _gpi_knots(med, b_half, mid, q1, s1, q01, s01)
        g = {"knots": kn, "segments": _gpi_spline(kn), "mu": mid}
        if _gpi_q(g, 0.9) < q10:
            lo = mid
        else:
            hi = mid
    return g


# tiers.gd 129-153 (build_start)
def st06_class(p, ctx):
    A.st05_margins(p, ctx)
    nc = ctx["nc"]
    nbs = ctx["nbs"]
    yi = ctx["yi"]
    emp_c = ctx["emp_c"]
    age_in_band = ctx["age_in_band"]
    adult_shares = ctx["adult_shares"]
    tab = _phi_table()
    mass = {}
    for ci7 in range(nc):
        for bs7 in range(nbs):
            if idiv(bs7, 2) * 5 < T.ADULT_FROM:
                continue
            n7 = 0.0
            for t7 in range(T.NTYPE):
                n7 += float(yi[(ci7 * nbs + bs7) * T.NTYPE + t7])
            er7 = emp_c[ci7][bs7 % 2][idiv(bs7, 2)]
            et7 = 0.0
            for e7 in range(T.NEMP):
                et7 += maxf(0.0, er7[e7])
            for e8 in range(T.NEMP):
                if et7 > 0.0 and er7[e8] > 0.0:
                    mass[bs7 * T.NEMP + e8] = float(mass.get(bs7 * T.NEMP + e8, 0.0)) + n7 * er7[e8] / et7
    laws = {}
    for kl in mass:
        laws[kl] = _income_law(p, idiv(idiv(kl, T.NEMP), 2), idiv(kl, T.NEMP) % 2, kl % T.NEMP, age_in_band)
    lines = _class_lines(tab, laws, mass, adult_shares)
    pk = {}
    for kl2 in laws:
        pk[kl2] = _class_probs(tab, laws[kl2], lines)
    p.tr_margins["class_lines"] = lines
    tm = _tail_map(p, tab, laws, mass, lines, adult_shares)
    ctx["tab"] = tab
    ctx["mass"] = mass
    ctx["laws"] = laws
    ctx["lines"] = lines
    ctx["pk"] = pk
    ctx["tm"] = tm


# tiers.gd 154-191 (build_start)
def st07_cells(p, ctx):
    nc = ctx["nc"]
    nbs = ctx["nbs"]
    yi = ctx["yi"]
    emp_c = ctx["emp_c"]
    codes = ctx["codes"]
    pk = ctx["pk"]
    cells = {}
    top_real = 0.0
    top_cand = []
    for ci2 in range(nc):
        for bs2 in range(nbs):
            b = idiv(bs2, 2)
            s3 = bs2 % 2
            adult = b * 5 + 4 >= T.ADULT_FROM
            for t3 in range(T.NTYPE):
                n0 = yi[(ci2 * nbs + bs2) * T.NTYPE + t3]
                if n0 <= 0:
                    continue
                sub = PArr("f64")
                tags = []
                erow = emp_c[ci2][s3][b]
                etot = 0.0
                for e in range(T.NEMP):
                    etot += maxf(0.0, erow[e])
                for e2 in range(T.NEMP):
                    pe = maxf(0.0, erow[e2]) / etot if etot > 0.0 else (1.0 if e2 == 0 else 0.0)
                    if pe <= 0.0:
                        continue
                    if not adult:
                        sub.append(float(n0) * pe)
                        tags.append([T.CLASS_NONE, e2])
                    else:
                        for k in range(T.NCLASS - 1):
                            sub.append(float(n0) * pe * float(pk.get(bs2 * T.NEMP + e2, _PK0)[k]))
                            tags.append([k, e2])
                ints = systematic(sub, n0, p.seed_v, "tier_cell", (ci2 * nbs + bs2) * T.NTYPE + t3)
                for q in range(len(ints)):
                    if ints[q] > 0:
                        _cell_add(cells, codes[ci2], b, s3, int(tags[q][0]), t3, int(tags[q][1]), float(ints[q]))
                    if adult and int(tags[q][0]) == 0:
                        top_real += sub[q]
                        top_cand.append([sub[q], codes[ci2], b, s3, t3, int(tags[q][1])])
    _hold_top(p, cells, top_real, top_cand)
    ctx["cells"] = cells
    ctx["top_real"] = top_real
    ctx["top_cand"] = top_cand


_PK0 = [0.0, 0.0, 0.0, 0.0, 0.0, 1.0]


# tiers.gd 192-286 (build_start)
def st08_units(p, ctx):
    cells = ctx["cells"]
    cls = ctx["cls"]
    age_in_band = ctx["age_in_band"]
    groups = {}
    for ks in cells:
        cell = cells[ks]
        n = int(cell[6])
        if n <= 0:
            continue
        k = int(cell[3])
        t = int(cell[4])
        e = int(cell[5])
        gk = k
        gt = t
        ge = e
        if k < T.CLASS_REST:
            gt = -1
            ge = -1
        elif k < T.CLASS_NONE:
            gk = T.CLASS_REST
            if int(cell[1]) >= T.EMP_KEY_UNTIL_BAND:
                ge = -1
        else:
            ge = -1
        gs = "%02d|%02d|%d|%d|%d|%d" % (int(cell[0]), int(cell[1]), int(cell[2]), gk, gt + 1, ge + 1)
        if gs not in groups:
            groups[gs] = [int(cell[0]), int(cell[1]), int(cell[2]), gk, gt, ge, {}]
        mix = groups[gs][6]
        code = (k * T.NTYPE + t) * T.NEMP + e
        mix[code] = int(mix.get(code, 0)) + n
    keys = list(groups.keys())
    gdsort.sort(keys)
    p.tr_units = 0
    p.tr_key = PArr("i32")
    p.tr_count = PArr("i64")
    p.tr_age_counts = PArr("i64")
    p.tr_never_married = PArr("f64")
    p.tr_married_apart = PArr("f64")
    p.tr_tier_size = PArr("i32")
    p.tr_mix_off = PArr("i64")
    p.tr_mix_code = PArr("i32")
    p.tr_mix_n = PArr("i64")
    unit_size = cls["unit_size"]
    for gi in range(len(keys)):
        g = groups[keys[gi]]
        mixg = g[6]
        mcodes = list(mixg.keys())
        gdsort.sort(mcodes)
        n2 = 0
        for mc in mcodes:
            n2 += int(mixg[mc])
        us = int(unit_size[int(g[3])])
        parts = 1 if us <= 0 else maxi(1, int(roundf(float(n2) / float(us))))
        split = []
        for q in range(parts):
            split.append({})
        off = keyed.below(parts, p.seed_v, "tier_part", gi, 0, 0)
        for mc2 in mcodes:
            nc2 = int(mixg[mc2])
            r = nc2 % parts
            for q2 in range(parts):
                add = idiv(nc2, parts) + (1 if (q2 - off + parts) % parts < r else 0)
                if add > 0:
                    split[q2][mc2] = add
            off = (off + r) % parts
        for q3 in range(parts):
            sm = split[q3]
            share = 0
            for mc3 in sm:
                share += int(sm[mc3])
            if share <= 0:
                continue
            for f in range(T.KEY_STRIDE):
                p.tr_key.append(int(g[f]))
            p.tr_count.append(share)
            p.tr_tier_size.append(us)
            p.tr_mix_off.append(len(p.tr_mix_code))
            sk = list(sm.keys())
            gdsort.sort(sk)
            for mc4 in sk:
                p.tr_mix_code.append(mc4)
                p.tr_mix_n.append(int(sm[mc4]))
            b2 = int(g[1])
            s4 = int(g[2])
            av = PArr("f64")
            av.resize(T.AGE_SLOTS)
            for a3 in range(b2 * 5, p.AGES if b2 == T.BANDS - 1 else b2 * 5 + 5):
                av[a3 - b2 * 5] += float(share) * age_in_band[a3 * 2 + s4]
            p.tr_age_counts.append_array(systematic(av, share, p.seed_v, "tier_age_split", p.tr_units))
            p.tr_units += 1
    p.tr_mix_off.append(len(p.tr_mix_code))
    ctx["groups"] = groups
    ctx["keys"] = keys
    ctx["unit_size"] = unit_size
