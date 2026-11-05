# Group E of the tiers start (tiers.gd at cd165891): T2.1 at month 0 (build_t21 and everything under it) and the month-0 state of
# the T2.2 month (_t22_start), with life_course.gd's functions they read as lc_<name>
import math

from core import detmath, keyed, prims
from core.gd import idiv, maxf, maxi, mini, minf, clampi, clampf
from tiers.start import tconst as T
from tiers.start.common import _v, _slots_in, _zeros_i, _largest
from tiers.start.p import PArr, PStr

AGE_SLOTS = T.AGE_SLOTS
KEY_STRIDE = T.KEY_STRIDE
NG = T.NG
NK = T.NK
NS = T.NS


def _systematic(v, total, seed_v, tag, key):
    return PArr("i64", prims.systematic(v, total, seed_v, tag, key))


def dep_round(x, nr, nc, seed_v, tag, key):
    return PArr("i64", prims.dep_round(x, nr, nc, seed_v, tag, key))


# ---- life_course.gd ----

# life_course.gd 14
def lc__lc(p, k):
    return p.hh_spec["life_course"]["value"][k]["value"]


# life_course.gd 18
def lc__b10(a):
    return mini(idiv(a, 10), 8)


# life_course.gd 27
def lc_shares(p, a, s):
    sa = lc__lc(p, "prevalence_single_age")
    sx = "men" if s == 0 else "women"
    a1 = clampi(a, 0, 100)
    s2 = float(sa["g2plus"][sx][a1])
    med = float(lc__lc(p, "medical_level"))
    g4 = float(sa["g4"][sx][a1]) / med
    g3 = maxf(0.0, s2 - g4) * float(lc__lc(p, "poor_share_of_rest")) / med
    g2 = maxf(0.0, maxf(s2, g4) - g4 - g3)
    g1 = maxf(0.0, 1.0 - g2 - g3 - g4)
    b4 = lc_ltci_share(p, a, s)
    if b4 > g4:
        sc = (1.0 - b4) / (1.0 - g4)
        g1 *= sc
        g2 *= sc
        g3 *= sc
        g4 = b4
    return PArr("f64", [g1, g2, g3, g4 - b4, b4])


# life_course.gd 48
def lc_ltci_share(p, a, s):
    return float(lc__lc(p, "prevalence_single_age")["b4"]["men" if s == 0 else "women"][clampi(a, 0, 100)])


# life_course.gd 269
def lc_income_factor(p, a, k):
    f = lc__lc(p, "death_income_factor")
    x = clampf(float(a), float(f["range"][0]), float(f["range"][1])) - float(f["a0"])
    return detmath.exp(0.5 * float(k) * (float(f["b0"]) + float(f["b1"]) * x))


# ---- tiers.gd ----

# tiers.gd 3600
def _table_round(p, x, rows, cols, nr, nk, tag, key):
    from tiers.start import a_fit as A
    z = PArr("i64")
    z.resize(nr * nk)
    for r in range(nr):
        rv = PArr("f64")
        rv.resize(nk)
        for k in range(nk):
            rv[k] = x[r * nk + k]
        ri = _systematic(rv, rows[r], p.seed_v, tag, key * 64 + r)
        for k2 in range(nk):
            z[r * nk + k2] = ri[k2]
    A._repair(z, x, cols, nr, nk)
    return z


# tiers.gd 4561
def build_t21(p):
    # Why sorted and not gdsort: the keys are distinct strings, so the order is total and any sort agrees with Godot's
    p.tr_hh_keys = PStr(sorted(p.tr_hh.keys()))
    _age_layout(p)
    _role_layout(p)
    _couples(p)
    _nh_couple_points(p)
    _marital(p)
    _t22_start(p)


# tiers.gd 4573
def _point_order(p, u, tag):
    rows = []
    off = p.tr_pt_off[u]
    hd = keyed.head(p.seed_v, tag)
    for j in range(off, p.tr_pt_off[u + 1]):
        rows.append((float(keyed.h64(hd, u, j - off, 0) >> 11) / keyed.TWO53, j))
    # Why not gdsort: the second element j is distinct per row, so the order is total and any sort agrees with Godot's
    rows.sort()
    out = []
    for r in rows:
        out.append(int(r[1]))
    return out


# tiers.gd 4586
def _overlap(a, b):
    out = []
    i = 0
    j = 0
    na = len(a)
    nb = len(b)
    ra = int(a[0]) if na > 0 else 0
    rb = int(b[0]) if nb > 0 else 0
    while i < na and j < nb:
        if ra == 0:
            i += 1
            ra = int(a[i]) if i < na else 0
            continue
        if rb == 0:
            j += 1
            rb = int(b[j]) if j < nb else 0
            continue
        n = mini(ra, rb)
        out.append([i, j, n])
        ra -= n
        rb -= n
    return out


# tiers.gd 4611
def _age_layout(p):
    p.tr_pt_age = PArr("i64")
    p.tr_pt_age.resize(p.tr_pt_off[p.tr_units] * AGE_SLOTS)
    pa = p.tr_pt_age
    mismatch = 0
    for u in range(p.tr_units):
        order = _point_order(p, u, "t21_age_order")
        a = []
        for j in order:
            a.append(p.tr_pt_mass[j])
        b = []
        sb = 0
        for s in range(AGE_SLOTS):
            b.append(p.tr_age_counts[u * AGE_SLOTS + s])
            sb += p.tr_age_counts[u * AGE_SLOTS + s]
        if sb != p.tr_count[u]:
            mismatch += 1
        for r in _overlap(a, b):
            pa[int(order[int(r[0])]) * AGE_SLOTS + int(r[1])] += int(r[2])
    p.tr_margins["t21_age_mismatch"] = mismatch


# tiers.gd 4634
def _role_layout(p):
    ents = [None] * p.tr_units
    for u0 in range(p.tr_units):
        ents[u0] = []
    for h in range(len(p.tr_hh_keys)):
        mem = p.tr_hh[p.tr_hh_keys[h]]["members"]
        # Why sorted and not gdsort: the unit keys are distinct ints, so the order is total
        uk = sorted(mem.keys())
        for u1 in uk:
            m1 = mem[u1]
            for r in range(5):
                n = int(m1.get(r, 0))
                if n > 0:
                    ents[int(u1)].append([h, r, n])
    rows = [None] * len(p.tr_hh_keys)
    for h1 in range(len(p.tr_hh_keys)):
        rows[h1] = []
    rest = 0
    for u in range(p.tr_units):
        order = _point_order(p, u, "t21_role_order")
        a = []
        for j in order:
            a.append(p.tr_pt_mass[j])
        b = []
        held = 0
        for e in ents[u]:
            b.append(int(e[2]))
            held += int(e[2])
        rest += maxi(0, p.tr_count[u] - held)
        b.append(maxi(0, p.tr_count[u] - held))
        for o in _overlap(a, b):
            if int(o[1]) < len(ents[u]):
                e2 = ents[u][int(o[1])]
                rows[int(e2[0])].append([int(order[int(o[0])]), int(e2[1]), int(o[2])])
    p.tr_hm_off = PArr("i64")
    p.tr_hm_pt = PArr("i32")
    p.tr_hm_role = PArr("i32")
    p.tr_hm_n = PArr("i64")
    for h2 in range(len(p.tr_hh_keys)):
        p.tr_hm_off.append(len(p.tr_hm_pt))
        for r2 in rows[h2]:
            p.tr_hm_pt.append(int(r2[0]))
            p.tr_hm_role.append(int(r2[1]))
            p.tr_hm_n.append(int(r2[2]))
    p.tr_hm_off.append(len(p.tr_hm_pt))
    p.tr_margins["t21_role_rest"] = rest


# tiers.gd 4683
def _r70_band(a):
    return 0 if a < 30 else mini(5, idiv(a - 20, 10))


# tiers.gd 4687
def _at_work(p, j):
    e = p.tr_points["employment"][j]
    return e == p.EMP_REGULAR or e == p.EMP_NONREGULAR


# tiers.gd 4694
def _r70_class(p, j, edges):
    if not _at_work(p, j):
        return 0
    y = float(p.tr_points["income"][j]) * 12.0
    c = 0
    for k in range(len(edges)):
        if y >= float(edges[k]):
            c = k
    return c


# tiers.gd 4706
def _couple_ranks(p, pairs):
    by = {}
    for pr in pairs:
        j = int(pr[0])
        if not _at_work(p, j):
            continue
        g = int(p.tr_points["sex"][j]) * 6 + _r70_band(int(p.tr_points["age"][j]))
        if g not in by:
            by[g] = {}
        by[g][j] = int(by[g].get(j, 0)) + int(pr[1])
    out = {}
    inc = p.tr_points["income"]
    for g2 in by:
        rows = []
        tot = 0.0
        for j2 in by[g2]:
            rows.append((float(inc[j2]), int(j2), float(by[g2][j2])))
            tot += float(by[g2][j2])
        # Why not gdsort: the second element j is distinct per row, so the order is total and any sort agrees with Godot's
        rows.sort()
        k = 0
        acc = 0.0
        while k < len(rows):
            k2 = k
            tie = 0.0
            while k2 < len(rows) and float(rows[k2][0]) == float(rows[k][0]):
                tie += float(rows[k2][2])
                k2 += 1
            for k3 in range(k, k2):
                out[int(rows[k3][1])] = (acc + 0.5 * tie) / tot
            acc += tie
            k = k2
    return out


# tiers.gd 4741
def couple_seed(p, w, h, ranks):
    ce = _v(p, "couple_wife_employment")
    wb = _r70_band(int(p.tr_points["age"][w]))
    if not _at_work(p, w):
        return 1.0
    cs = ce["couples"][wb]
    es = ce["wife_employed"][wb]
    tc = 0.0
    te = 0.0
    for k in range(len(cs)):
        tc += float(cs[k])
        te += float(es[k])
    s = 1.0
    if _at_work(p, h):
        c = _r70_class(p, h, ce["class_from_man_yen_year"])
        rate = float(es[c]) / float(cs[c])
        all_ = te / tc
        s = (rate / (1.0 - rate)) / (all_ / (1.0 - all_))
    else:
        lf = _v(p, "couple_wife_work_husband_not_at_work")
        k = 0
        for i in range(len(lf["wife_band_from"])):
            if int(p.tr_points["age"][w]) >= int(lf["wife_band_from"][i]):
                k = i
        s = float(lf["odds_ratio"][k])
    if _at_work(p, h) and w in ranks and h in ranks:
        rho_s = float(_v(p, "couple_spearman_both_earn")["rho_s"][wb])
        r = 2.0 * detmath.sin(math.pi * rho_s / 6.0)
        z1 = detmath.inv_normal(float(ranks[w]))
        z2 = detmath.inv_normal(float(ranks[h]))
        s *= detmath.exp(-(r * r * (z1 * z1 + z2 * z2) - 2.0 * r * z1 * z2) / (2.0 * (1.0 - r * r))) / math.sqrt(1.0 - r * r)
    return s


# tiers.gd 4776
def ipf2(seed, rr, cc):
    nr = len(rr)
    nc = len(cc)
    x = PArr("f64", seed)
    for it in range(2000):
        for i in range(nr):
            s = 0.0
            for j in range(nc):
                s += x[i * nc + j]
            if s > 0.0:
                for j2 in range(nc):
                    x[i * nc + j2] *= float(rr[i]) / s
        worst = 0.0
        for j3 in range(nc):
            s2 = 0.0
            for i2 in range(nr):
                s2 += x[i2 * nc + j3]
            if s2 > 0.0:
                for i3 in range(nr):
                    x[i3 * nc + j3] *= float(cc[j3]) / s2
        for i4 in range(nr):
            s3 = 0.0
            for j4 in range(nc):
                s3 += x[i4 * nc + j4]
            worst = maxf(worst, abs(s3 - float(rr[i4])) / maxf(1.0, float(rr[i4])))
        if worst < 1e-12:
            break
    return x


# tiers.gd 4812
def _couples(p):
    keys = p.tr_hh_keys
    pairs = []
    for h0 in range(len(keys)):
        t0 = int(keys[h0].split("|")[1])
        if t0 != 1 and t0 != 2 and t0 != 4:
            continue
        for k0 in range(p.tr_hm_off[h0], p.tr_hm_off[h0 + 1]):
            if p.tr_hm_role[k0] <= 1:
                pairs.append([p.tr_hm_pt[k0], p.tr_hm_n[k0]])
    ranks = _couple_ranks(p, pairs)
    p.tr_cp_hh = PArr("i32")
    p.tr_cp_w = PArr("i32")
    p.tr_cp_h = PArr("i32")
    p.tr_cp_n = PArr("i64")
    cross = 0
    nopart = 0
    extra = {}
    grp = {}
    for h0 in range(len(keys)):
        f0 = keys[h0].split("|")
        t0 = int(f0[1])
        if t0 != 1 and t0 != 2 and t0 != 4:
            continue
        gk = "%s|%s|%s|%s" % (f0[0], f0[1], f0[2], f0[4])
        if gk not in grp:
            grp[gk] = []
        grp[gk].append(h0)
    # Why sorted and not gdsort: the keys are distinct strings, so the order is total
    gkeys = sorted(grp.keys())
    sex = p.tr_points["sex"]
    for gi in range(len(gkeys)):
        hs = grp[gkeys[gi]]
        h = int(hs[0])
        t = int(keys[h].split("|")[1])
        wd = {}
        hd = {}
        wb = {}
        for hh in hs:
            for k in range(p.tr_hm_off[hh], p.tr_hm_off[hh + 1]):
                j = p.tr_hm_pt[k]
                fem = int(sex[j]) == p.FEMALE
                if fem and p.tr_hm_role[k] == 1:
                    if p.tr_hm_n[k] > int(wd.get(j, 0)):
                        wb[j] = hh
                    wd[j] = int(wd.get(j, 0)) + p.tr_hm_n[k]
                elif not fem and p.tr_hm_role[k] == 0:
                    hd[j] = int(hd.get(j, 0)) + p.tr_hm_n[k]
        # Why sorted and not gdsort: the point keys are distinct ints, so the order is total
        w = sorted(wd.keys())
        hu = sorted(hd.keys())
        wn = []
        for j1 in w:
            wn.append(int(wd[j1]))
        hn = []
        for j2 in hu:
            hn.append(int(hd[j2]))
        sw = 0
        sh = 0
        for x in wn:
            sw += x
        for y in hn:
            sh += y
        wn0 = list(wn)
        hn0 = list(hn)
        if sw > sh:
            cross += sw - sh
            cx = p.tr_margins.get("cp_cross_by", {})
            ckx = "type %d, householder %s" % (t, keys[h].split("|")[2])
            cx[ckx] = int(cx.get(ckx, 0)) + sw - sh
            p.tr_margins["cp_cross_by"] = cx
            wn = list(_systematic(_scaled(wn, sh, sw), sh, p.seed_v, "t21_cp_cut", gi * 2)) if sh > 0 else _zeros(len(wn))
        elif sh > sw:
            nopart += (sh - sw) if t != 4 else 0
            hn = list(_systematic(_scaled(hn, sw, sh), sw, p.seed_v, "t21_cp_cut", gi * 2 + 1)) if sw > 0 else _zeros(len(hn))
        for a0 in range(len(w)):
            if int(wn0[a0]) > int(wn[a0]):
                extra[int(w[a0])] = int(extra.get(int(w[a0]), 0)) + int(wn0[a0]) - int(wn[a0])
        if t != 4:
            for b0 in range(len(hu)):
                if int(hn0[b0]) > int(hn[b0]):
                    extra[int(hu[b0])] = int(extra.get(int(hu[b0]), 0)) + int(hn0[b0]) - int(hn[b0])
        if mini(sw, sh) <= 0:
            continue
        nw = len(w)
        nh = len(hu)
        seed = PArr("f64")
        seed.resize(nw * nh)
        for a in range(nw):
            for b in range(nh):
                seed[a * nh + b] = couple_seed(p, int(w[a]), int(hu[b]), ranks) if int(wn[a]) > 0 and int(hn[b]) > 0 else 0.0
        xt = ipf2(seed, wn, hn)
        it = dep_round(xt, nw, nh, p.seed_v, "t21_cp_round", gi)
        for a2 in range(nw):
            for b2 in range(nh):
                m = it[a2 * nh + b2]
                if m > 0:
                    p.tr_cp_hh.append(int(wb[int(w[a2])]))
                    p.tr_cp_w.append(int(w[a2]))
                    p.tr_cp_h.append(int(hu[b2]))
                    p.tr_cp_n.append(m)
    p.tr_margins["cp_cross"] = cross
    p.tr_margins["cp_nopartner"] = nopart
    p.tr_margins["cp_extra"] = extra
    p.tr_margins["cp_ranks"] = ranks


# tiers.gd 4923
def _nh_couple_points(p):
    unit_of = PArr("i32")
    unit_of.resize(p.tr_pt_off[p.tr_units])
    for u in range(p.tr_units):
        for j in range(p.tr_pt_off[u], p.tr_pt_off[u + 1]):
            unit_of[j] = u
    keys = p.tr_hh_keys
    grp = {}
    for h in range(len(keys)):
        f0 = keys[h].split("|")
        if int(f0[1]) != 4:
            continue
        gk = "%s|%s|%s" % (f0[0], f0[2], f0[4])
        if gk not in grp:
            grp[gk] = []
        grp[gk].append(h)
    p.tr_margins["cp_nh_from"] = len(p.tr_cp_n)
    ranks = p.tr_margins.get("cp_ranks", {})
    short = 0
    made = 0
    # Why sorted and not gdsort: the keys are distinct strings, so the order is total
    rks = sorted(p.tr_nh_hh.keys())
    for gi in range(len(rks)):
        rk = rks[gi]
        if rk not in grp:
            short += 1
            continue
        left = {}
        bun = {}
        for h2 in grp[rk]:
            for k in range(p.tr_hm_off[h2], p.tr_hm_off[h2 + 1]):
                if p.tr_hm_role[k] == 2 or p.tr_hm_role[k] == 3:
                    key = "%d|%d" % (p.tr_hm_pt[k], p.tr_hm_role[k])
                    left[key] = int(left.get(key, 0)) + p.tr_hm_n[k]
                    bun[p.tr_hm_pt[k]] = h2
        recs = p.tr_nh_hh[rk]
        for ri in range(len(recs)):
            rec = recs[ri]
            role = 2 if int(rec[2]) == 0 else 3
            n = int(rec[3])
            sides = []
            for side in range(2):
                uu = int(rec[side])
                pts = []
                ms = []
                tot = 0
                for j3 in range(p.tr_pt_off[uu], p.tr_pt_off[uu + 1]):
                    m = int(left.get("%d|%d" % (j3, role), 0))
                    if m > 0:
                        pts.append(j3)
                        ms.append(m)
                        tot += m
                take = mini(n, tot)
                cut = list(_systematic(_scaled(ms, take, maxi(1, tot)), take, p.seed_v, "t21_nh_cut", (gi * 64 + ri) * 2 + side)) if take > 0 else []
                sides.append([pts, cut, take])
            nn = mini(int(sides[0][2]), int(sides[1][2]))
            short += n - nn
            if nn <= 0:
                continue
            for side2 in range(2):
                if int(sides[side2][2]) > nn:
                    sides[side2][1] = list(_systematic(_scaled(sides[side2][1], nn, int(sides[side2][2])), nn, p.seed_v, "t21_nh_cut2", (gi * 64 + ri) * 2 + side2))
            hp = sides[0][0]
            hn = sides[0][1]
            wp = sides[1][0]
            wn = sides[1][1]
            seed = PArr("f64")
            seed.resize(len(wp) * len(hp))
            for a in range(len(wp)):
                for b in range(len(hp)):
                    seed[a * len(hp) + b] = couple_seed(p, int(wp[a]), int(hp[b]), ranks) if int(wn[a]) > 0 and int(hn[b]) > 0 else 0.0
            it = dep_round(ipf2(seed, wn, hn), len(wp), len(hp), p.seed_v, "t21_nh_round", gi * 64 + ri)
            for a2 in range(len(wp)):
                for b2 in range(len(hp)):
                    m2 = it[a2 * len(hp) + b2]
                    if m2 <= 0:
                        continue
                    p.tr_cp_hh.append(int(bun[int(wp[a2])]))
                    p.tr_cp_w.append(int(wp[a2]))
                    p.tr_cp_h.append(int(hp[b2]))
                    p.tr_cp_n.append(m2)
                    made += m2
                    kw = "%d|%d" % (int(wp[a2]), role)
                    kh2 = "%d|%d" % (int(hp[b2]), role)
                    left[kw] = int(left[kw]) - m2
                    left[kh2] = int(left[kh2]) - m2
    p.tr_margins["cp_nh"] = made
    p.tr_margins["cp_nh_short"] = short


# tiers.gd 5012
def _zeros(n):
    return [0] * n


# tiers.gd 5019
def _scaled(v, num, den):
    out = PArr("f64")
    for x in v:
        out.append(float(x) * float(num) / float(den))
    return out


# tiers.gd 5032
def _marital(p):
    m21 = p.tr_margins["m21"]
    cpm = dict(p.tr_margins["cp_extra"])
    for c in range(len(p.tr_cp_n)):
        cpm[p.tr_cp_w[c]] = int(cpm.get(p.tr_cp_w[c], 0)) + p.tr_cp_n[c]
        cpm[p.tr_cp_h[c]] = int(cpm.get(p.tr_cp_h[c], 0)) + p.tr_cp_n[c]
    cells = {}
    key = p.tr_key
    for u in range(p.tr_units):
        b = key[u * KEY_STRIDE + 1]
        if b * 5 < 15:
            continue
        c2 = key[u * KEY_STRIDE]
        sx = key[u * KEY_STRIDE + 2]
        ck = "%d|%d|%d" % (c2, b, sx)
        if ck not in cells:
            cells[ck] = [0.0, 0.0, 0.0, 0.0, 0.0]
        e = cells[ck]
        cm = 0
        for j in range(p.tr_pt_off[u], p.tr_pt_off[u + 1]):
            cm += int(cpm.get(j, 0))
        e[0] = float(e[0]) + float(p.tr_count[u] - cm)
        e[1] = float(e[1]) + p.tr_married_apart[u] * float(p.tr_count[u])
        e[2] = float(e[2]) + p.tr_never_married[u] * float(p.tr_count[u])
        if ck in m21:
            e[3] = float(m21[ck][4])
            e[4] = float(m21[ck][5])
    capped = 0
    ma_over = 0
    for ck2 in cells:
        e2 = cells[ck2]
        nc = float(e2[0])
        ma = minf(float(e2[1]), nc)
        ma_over += 1 if float(e2[1]) > nc + 1e-6 else 0
        nm = minf(float(e2[2]), nc - ma)
        capped += 1 if float(e2[2]) > nc - ma + 1e-6 else 0
        rest = maxf(0.0, nc - ma - nm)
        wd = float(e2[3]) + float(e2[4])
        wi = rest * float(e2[3]) / wd if wd > 0.0 else rest * 0.5
        cells[ck2] = [nc, ma, nm, wi, rest - wi]
    p.tr_pt_ms = PArr("i64")
    p.tr_pt_ms.resize(p.tr_pt_off[p.tr_units] * 4)
    ms = p.tr_pt_ms
    for u2 in range(p.tr_units):
        b2 = key[u2 * KEY_STRIDE + 1]
        ck3 = "%d|%d|%d" % (key[u2 * KEY_STRIDE], b2, key[u2 * KEY_STRIDE + 2])
        for j2 in range(p.tr_pt_off[u2], p.tr_pt_off[u2 + 1]):
            cmj = int(cpm.get(j2, 0))
            free = p.tr_pt_mass[j2] - cmj
            if b2 * 5 < 15 or ck3 not in cells:
                ms[j2 * 4] = free
                ms[j2 * 4 + 1] = cmj
                continue
            e3 = cells[ck3]
            v = PArr("f64")
            for k in [2, 1, 3, 4]:
                v.append(float(free) * float(e3[k]) / float(e3[0]) if float(e3[0]) > 0.0 else (float(free) if k == 2 else 0.0))
            q = _largest(v, free)
            ms[j2 * 4] = q[0]
            ms[j2 * 4 + 1] = cmj + q[1]
            ms[j2 * 4 + 2] = q[2]
            ms[j2 * 4 + 3] = q[3]
    p.tr_margins["ms"] = {"capped": capped, "ma_over": ma_over, "cells": len(cells)}


# tiers.gd 5126
def _t22_start(p):
    n_pts = p.tr_pt_off[p.tr_units]
    p.tr_pt_id = PArr("i64", range(n_pts))
    p.tr_pt_next = n_pts
    p.tr_pt_jan = p.tr_pt_age.duplicate()
    p.tr_pt_old = p.tr_pt_age.duplicate()
    p.tr_class_lines = p.tr_margins["class_lines"]
    p.tr_pt_rem = {}
    p.tr_pt_muq = PArr("f64")
    p.tr_pt_muq.resize(n_pts)
    p.tr_pt_mug = PArr("f64")
    p.tr_pt_mug.resize(n_pts)
    p.tr_cp_cap = {}
    for c in range(len(p.tr_cp_n)):
        p.tr_cp_cap[p.tr_cp_hh[c]] = int(p.tr_cp_cap.get(p.tr_cp_hh[c], 0)) + 1
    p.tr_pt_ag = _zeros_i(n_pts * AGE_SLOTS * NS)
    p.tr_pt_jg = _zeros_i(n_pts * AGE_SLOTS * NS)
    p.tr_pt_og = _zeros_i(n_pts * AGE_SLOTS * NS)
    p.tr_pt_T = _zeros_i(n_pts * 4 * NG)
    ag = p.tr_pt_ag
    jg = p.tr_pt_jg
    og = p.tr_pt_og
    pT = p.tr_pt_T
    pa = p.tr_pt_age
    pid = p.tr_pt_id
    pms = p.tr_pt_ms
    pst = lc__lc(p, "grade_kernel")["p_stable_given_side"]
    ps_good = float(pst["good"])
    ps_bad = float(pst["bad"])
    hd = keyed.head(p.seed_v, "t22b_class0")
    sh_cache = {}
    for u in range(p.tr_units):
        b = p.tr_key[u * KEY_STRIDE + 1]
        s = p.tr_key[u * KEY_STRIDE + 2]
        for g2 in range(p.tr_pt_off[u], p.tr_pt_off[u + 1]):
            colm = PArr("i64")
            colm.resize(NG)
            for sl in range(_slots_in(b)):
                m0 = pa[g2 * AGE_SLOTS + sl]
                if m0 <= 0:
                    continue
                ka = (b * 5 + sl, s)
                sh = sh_cache.get(ka)
                if sh is None:
                    sh = lc_shares(p, b * 5 + sl, s)
                    sh_cache[ka] = sh
                z = _start_split(p, m0, sh, pid[g2] * AGE_SLOTS + sl)
                for gr in range(NG):
                    if z[gr] <= 0:
                        continue
                    colm[gr] += z[gr]
                    ps = ps_good if gr < 2 else ps_bad
                    xs = prims.binomial(z[gr], ps, float(keyed.h64(hd, pid[g2] * NG + gr, sl, 0) >> 11) / keyed.TWO53)
                    cx = (g2 * AGE_SLOTS + sl) * NS + gr * NK
                    ag[cx] = xs
                    ag[cx + 1] = z[gr] - xs
                    jg[cx] = xs
                    jg[cx + 1] = z[gr] - xs
                    og[cx] = xs
                    og[cx + 1] = z[gr] - xs
            rows = PArr("i64")
            rows.resize(4)
            mt = 0
            for k in range(4):
                rows[k] = pms[g2 * 4 + k]
                mt += rows[k]
            if mt <= 0:
                continue
            x = PArr("f64")
            x.resize(4 * NG)
            for k2 in range(4):
                for gr2 in range(NG):
                    x[k2 * NG + gr2] = float(rows[k2]) * float(colm[gr2]) / float(mt)
            tz = _table_round(p, x, rows, colm, 4, NG, "m036_T", pid[g2])
            for k3 in range(4):
                for gr3 in range(NG):
                    pT[g2 * 4 * NG + k3 * NG + gr3] = tz[k3 * NG + gr3]
    _t22_quartiles(p)
    _t22_solve_c(p, True)


# tiers.gd 5198
def _start_split(p, m, sh, key):
    out = PArr("i64")
    out.resize(NG)
    tot = 0.0
    for g in range(NG):
        tot += sh[g]
    fr = []
    used = 0
    hd = keyed.head(p.seed_v, "m036_start")
    for g2 in range(NG):
        x = float(m) * sh[g2] / tot
        out[g2] = int(math.floor(x))
        used += out[g2]
        fr.append((x - float(math.floor(x)), keyed.h64(hd, key, g2, 0) >> 11, g2))
    # Why not gdsort.sort_custom: the comparator orders by the fraction, descending, then by the keyed raw value, which is distinct
    # per state, so the order is total and any sort agrees with Godot's
    fr.sort(key=lambda r: (-r[0], r[1]))
    for q in range(m - used):
        out[int(fr[q % NG][2])] += 1
    return out


# tiers.gd 6512
def _t22_quartiles(p, w=None):
    if w:
        _t22_quartiles_w(p, w)
        return
    n_pts = p.tr_pt_off[p.tr_units]
    inc = p.tr_points["income"]
    nh = len(p.tr_hh_keys)
    eq = PArr("f64")
    eq.resize(nh)
    held = PArr("i64")
    held.resize(n_pts)
    sum_e = PArr("f64")
    sum_e.resize(n_pts)
    hmn = p.tr_hm_n
    hmp = p.tr_hm_pt
    for h in range(nh):
        hc = float(int(p.tr_hh[p.tr_hh_keys[h]]["count"]))
        tot = 0.0
        pers = 0.0
        for e in range(p.tr_hm_off[h], p.tr_hm_off[h + 1]):
            tot += float(hmn[e]) * inc[hmp[e]]
            pers += float(hmn[e])
        eq[h] = (tot / hc) / math.sqrt(pers / hc) if hc > 0.0 and pers > 0.0 else 0.0
        for e2 in range(p.tr_hm_off[h], p.tr_hm_off[h + 1]):
            held[hmp[e2]] += hmn[e2]
            sum_e[hmp[e2]] += float(hmn[e2]) * eq[h]
    by = []
    for b10 in range(9):
        by.append([])
    for u in range(p.tr_units):
        b10b = lc__b10(p.tr_key[u * KEY_STRIDE + 1] * 5)
        for g in range(p.tr_pt_off[u], p.tr_pt_off[u + 1]):
            m = p.tr_pt_mass[g]
            rest = maxi(0, m - held[g])
            den = float(held[g] + rest)
            e3 = (sum_e[g] + float(rest) * inc[g]) / den if den > 0.0 else float(inc[g])
            by[b10b].append((e3, g, m))
    p.tr_pt_q = PArr("i32")
    p.tr_pt_q.resize(n_pts)
    qm = PArr("f64", [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0])
    for b2 in range(9):
        rows = by[b2]
        # Why not gdsort: the second element g is distinct per row, so the order is total and any sort agrees with Godot's
        rows.sort()
        tot2 = 0.0
        for r in rows:
            tot2 += float(r[2])
        acc = 0.0
        for r2 in rows:
            pos = (acc + 0.5 * float(r2[2])) / tot2 if tot2 > 0.0 else 0.0
            kq = 3 if pos < 0.25 else (2 if pos < 0.5 else (1 if pos < 0.75 else 0))
            p.tr_pt_q[int(r2[1])] = kq
            qm[kq] += float(r2[0]) * float(r2[2])
            qm[4 + kq] += float(r2[2])
            acc += float(r2[2])
    p.tr_margins["t22_q_means"] = qm


# tiers.gd 6569
def _t22_quartiles_w(p, w):
    n_pts = len(p.tr_pt_mass)
    inc = p.tr_points["income"]
    hm_h = w["hm_h"]
    nh = len(p.tr_hh_keys)
    tot = PArr("f64")
    tot.resize(nh)
    pers = PArr("f64")
    pers.resize(nh)
    for e in range(len(p.tr_hm_n)):
        if p.tr_hm_n[e] <= 0:
            continue
        tot[hm_h[e]] += float(p.tr_hm_n[e]) * inc[p.tr_hm_pt[e]]
        pers[hm_h[e]] += float(p.tr_hm_n[e])
    eq = PArr("f64")
    eq.resize(nh)
    for h in range(nh):
        hc = float(int(p.tr_hh[p.tr_hh_keys[h]]["count"]))
        eq[h] = (tot[h] / hc) / math.sqrt(pers[h] / hc) if hc > 0.0 and pers[h] > 0.0 else 0.0
    held = PArr("i64")
    held.resize(n_pts)
    sum_e = PArr("f64")
    sum_e.resize(n_pts)
    for e2 in range(len(p.tr_hm_n)):
        if p.tr_hm_n[e2] <= 0:
            continue
        held[p.tr_hm_pt[e2]] += p.tr_hm_n[e2]
        sum_e[p.tr_hm_pt[e2]] += float(p.tr_hm_n[e2]) * eq[hm_h[e2]]
    by = []
    for b10 in range(9):
        by.append([])
    lists = w["lists"]
    for u in range(p.tr_units):
        b10b = lc__b10(p.tr_key[u * KEY_STRIDE + 1] * 5)
        for g in lists[u]:
            m = p.tr_pt_mass[g]
            if m <= 0:
                continue
            rest = maxi(0, m - held[g])
            den = float(held[g] + rest)
            e3 = (sum_e[g] + float(rest) * inc[g]) / den if den > 0.0 else float(inc[g])
            by[b10b].append((e3, g, m))
    qm = PArr("f64", [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0])
    for b2 in range(9):
        rows = by[b2]
        # Why not gdsort: the second element g is distinct per row, so the order is total and any sort agrees with Godot's
        rows.sort()
        tot2 = 0.0
        for r in rows:
            tot2 += float(r[2])
        acc = 0.0
        for r2 in rows:
            pos = (acc + 0.5 * float(r2[2])) / tot2 if tot2 > 0.0 else 0.0
            kq = 3 if pos < 0.25 else (2 if pos < 0.5 else (1 if pos < 0.75 else 0))
            p.tr_pt_q[int(r2[1])] = kq
            qm[kq] += float(r2[0]) * float(r2[2])
            qm[4 + kq] += float(r2[2])
            acc += float(r2[2])
    p.tr_margins["t22_q_means"] = qm


# tiers.gd 6633
def _t22_solve_c(p, from_cells):
    m = lc__lc(p, "death_multiplier")
    lt = lc__lc(p, "qx_2022")
    ws = PArr("f64")
    ws.resize(p.AGES * 2 * NG * 4)
    wb = PArr("f64")
    wb.resize(9 * 2 * NG * 4)
    health = p.tr_points["health"]
    ag = p.tr_pt_ag
    pa = p.tr_pt_age
    ptq = p.tr_pt_q
    for u in range(p.tr_units):
        b = p.tr_key[u * KEY_STRIDE + 1]
        s = p.tr_key[u * KEY_STRIDE + 2]
        for g in range(p.tr_pt_off[u], p.tr_pt_off[u + 1]):
            for sl in range(_slots_in(b)):
                for sb in range(NS):
                    gr = idiv(sb, NK)
                    if not from_cells and sb != int(health[g]) * NK:
                        continue
                    x = float(ag[(g * AGE_SLOTS + sl) * NS + sb] if from_cells else pa[g * AGE_SLOTS + sl])
                    if x <= 0.0:
                        continue
                    a = b * 5 + sl
                    gk = gr * 4 + ptq[g]
                    ws[(a * 2 + s) * NG * 4 + gk] += x
                    wb[(lc__b10(a) * 2 + s) * NG * 4 + gk] += x
    p.tr_c = PArr("f64")
    p.tr_c.resize(p.AGES * 2)
    band = 0
    for a2 in range(p.AGES):
        ifs = [lc_income_factor(p, a2, k) for k in range(4)]
        for s2 in range(2):
            src = ws
            cell = (a2 * 2 + s2) * NG * 4
            tot = 0.0
            for x0 in range(NG * 4):
                tot += ws[cell + x0]
            if tot <= 0.0:
                src = wb
                cell = (lc__b10(a2) * 2 + s2) * NG * 4
                band += 1
                for x1 in range(NG * 4):
                    tot += wb[cell + x1]
            tab = lt["men" if s2 == p.MALE else "women"]
            q = float(tab[mini(a2, len(tab) - 1)])
            if tot <= 0.0 or q >= 1.0:
                p.tr_c[a2 * 2 + s2] = 1.0
                continue
            mu = -detmath.log(1.0 - q)
            target = detmath.exp(-mu)
            lo = 0.0
            hi = 16.0
            for it in range(60):
                c = 0.5 * (lo + hi)
                surv = 0.0
                for gg in range(NG):
                    for k in range(4):
                        surv += src[cell + gg * 4 + k] / tot * detmath.exp(-c * float(m[gg]) * ifs[k] * mu)
                if surv > target:
                    lo = c
                else:
                    hi = c
            p.tr_c[a2 * 2 + s2] = 0.5 * (lo + hi)
    p.tr_margins["t22_c_band"] = band


def st18_t21(p, ctx):
    build_t21(p)
