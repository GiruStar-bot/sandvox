# Stage group A of TR.build_start (tiers.gd at cd165891): the base, the couples, the fit, type 2's cap and the size floor, and the
# integer rounding (start_trace.gd's _build_start through 05_round)
import math

from core import gdsort
from core.gd import clampf, idiv, maxf, maxi, minf, mini, roundf
from core.prims import systematic as _systematic
from tiers.start import tconst as T
from tiers.start.common import _largest, _v, band_of
from tiers.start.p import PArr

BANDS = T.BANDS
NTYPE = T.NTYPE
NEMP = T.NEMP


def _f64(n):
    return PArr("f64", [0.0] * n)


def _i64(n):
    return PArr("i64", [0] * n)


def _floor(x):
    return float(math.floor(x))


def _ceil(x):
    return float(math.ceil(x))


# tiers.gd 653
def _base(p, codes, prefectures, band_share):
    pop22 = _v(p, "population_2022_by_pref_sex_band")["by_pref"]
    nc = len(codes)
    nbs = BANDS * 2
    x = _f64(nc * nbs)
    rows = _f64(nc)
    total = 0.0
    for ci in range(nc):
        code = "%02d" % codes[ci]
        # Why pop_persons when given (step (c), AMENDED): rule (D)'s totals are persons, and pop_thousand * 1000 is inexact there
        rows[ci] = float(prefectures[code]["pop_persons"]) if "pop_persons" in prefectures[code] else float(prefectures[code]["pop_thousand"]) * 1000.0
        total += rows[ci]
        est = pop22[str(codes[ci])]
        est_tot = 0.0
        for s0 in range(2):
            for b0 in range(BANDS):
                est_tot += float(est[s0][b0])
        for bs2 in range(nbs):
            x[ci * nbs + bs2] = rows[ci] * float(est[bs2 % 2][idiv(bs2, 2)]) / est_tot
    cols = _f64(nbs)
    for bs3 in range(nbs):
        cols[bs3] = total * band_share[bs3]
    fit = _v(p, "fit")
    _rake2(x, rows, cols, nc, nbs, int(fit["max_rounds"]), float(fit["tol"]))
    return x


# tiers.gd 689
def _employment(p, base, codes, emp_bs):
    lab = _v(p, "labour_by_prefecture")
    pl = lab["prefectures"]
    nbs = BANDS * 2
    out = []
    for ci in range(len(codes)):
        code = "%02d" % codes[ci]
        lf_n = 0.0
        u_n = 0.0
        pop15 = 0.0
        for bs in range(nbs):
            if idiv(bs, 2) < 3:
                continue
            r = emp_bs[bs % 2][idiv(bs, 2)]
            w = base[ci * nbs + bs]
            pop15 += w
            lf_n += w * (float(r[1]) + float(r[2]) + float(r[3]))
            u_n += w * float(r[3])
        f_lf = 1.0
        f_u = 1.0
        if code in pl and lf_n > 0.0 and u_n > 0.0:
            f_lf = float(pl[code]["labour force rate"]) / (lf_n / pop15)
            f_u = float(pl[code]["unemployment rate"]) / (u_n / lf_n)
        by_sex = []
        for s in range(2):
            by_band = []
            for b in range(BANDS):
                r2 = emp_bs[s][b]
                v = _f64(NEMP)
                for e in range(NEMP):
                    v[e] = float(r2[e])
                lf = v[1] + v[2] + v[3]
                if b >= 3 and lf > 0.0:
                    lf2 = minf(lf * f_lf, 1.0 - v[4])
                    un2 = minf(lf2, lf2 * v[3] / lf * f_u)
                    em = v[1] + v[2]
                    em2 = lf2 - un2
                    out_lf = v[0] + v[4] + v[5]
                    out2 = 1.0 - lf2
                    v[1] = v[1] / em * em2 if em > 0.0 else 0.0
                    v[2] = v[2] / em * em2 if em > 0.0 else 0.0
                    v[3] = un2
                    for e2 in [0, 4, 5]:
                        v[e2] = v[e2] / out_lf * out2 if out_lf > 0.0 else 0.0
                by_band.append(v)
            by_sex.append(by_band)
        out.append(by_sex)
    return out


# tiers.gd 748
def _seed(nc, base, fixed, five):
    nbs = BANDS * 2
    y = _f64(nc * nbs * NTYPE)
    floor_excess = 0.0
    for ci in range(nc):
        for bs in range(nbs):
            row = five[bs % 2][idiv(bs, 2)]
            tot = 0.0
            for t in range(NTYPE):
                tot += maxf(0.0, float(row[t]))
            if tot <= 0.0:
                continue
            fsum = 0.0
            v = _f64(NTYPE)
            vt = 0.0
            for t2 in range(NTYPE):
                f = float(fixed[(ci * nbs + bs) * NTYPE + t2])
                fsum += f
                want = base[ci * nbs + bs] * maxf(0.0, float(row[t2])) / tot
                v[t2] = 0.0 if t2 == 1 else maxf(0.0, want - f)
                floor_excess += maxf(0.0, f - want)
                vt += v[t2]
            nnc = maxf(0.0, base[ci * nbs + bs] - fsum)
            for t3 in range(NTYPE):
                if vt > 0.0:
                    y[(ci * nbs + bs) * NTYPE + t3] = v[t3] / vt * nnc
    return [y, floor_excess]


# tiers.gd 785
def _size_floor(p, codes, y, fixed):
    tgt = _v(p, "household_target")["by_pref"]
    heads = _head_targets(p)
    nbs = BANDS * 2
    moved = {}
    for ci in range(len(codes)):
        tc = tgt[str(codes[ci])]
        have = _f64(NTYPE)
        h2 = 0.0
        f4 = 0.0
        for bs in range(nbs):
            for t in range(NTYPE):
                have[t] += y[(ci * nbs + bs) * NTYPE + t]
            if bs % 2 == 0:
                h2 += float(fixed[(ci * nbs + bs) * NTYPE + 2])
            f4 += float(fixed[(ci * nbs + bs) * NTYPE + 4])
        need = PArr("f64", [0.0, 0.0, h2, 2.0 * float(tc[3]), maxf(0.0, 2.0 * float(heads["%02d|4" % codes[ci]]) - f4), 0.0])
        short = _f64(NTYPE)
        for t2 in [2, 3, 4]:
            short[t2] = maxf(0.0, need[t2] - have[t2])
        for t3 in [2, 3, 4]:
            if short[t3] <= 0.0 or have[t3] <= 0.0:
                continue
            for bs2 in range(nbs):
                at = (ci * nbs + bs2) * NTYPE
                want = short[t3] * y[at + t3] / have[t3]
                pool = 0.0
                for u in range(2, NTYPE):
                    if short[u] <= 0.0 and u != t3:
                        pool += y[at + u]
                take = minf(want, pool)
                if take <= 0.0:
                    continue
                for u2 in range(2, NTYPE):
                    if short[u2] <= 0.0 and u2 != t3:
                        y[at + u2] -= take * y[at + u2] / pool
                y[at + t3] += take
                mk = "%d|%d" % (t3, idiv(bs2, 2))
                moved[mk] = float(moved.get(mk, 0.0)) + take
    return moved


# tiers.gd 832
def _type2_cap(p, codes, y, fixed):
    nbs = BANDS * 2
    by_c = {}
    keys = list(p.tr_couples.keys())
    gdsort.sort(keys)
    for k in keys:
        if k.endswith("|2"):
            c = int(k.split("|")[0])
            if c not in by_c:
                by_c[c] = []
            by_c[c].append(k)
    moved = {}
    for ci in range(len(codes)):
        c2 = codes[ci]
        if c2 not in by_c:
            continue
        kids = 0.0
        for bs in range(nbs):
            kids += y[(ci * nbs + bs) * NTYPE + 2]
        h = 0
        w = PArr("f64")
        for k2 in by_c[c2]:
            h += int(p.tr_couples[k2])
            w.append(float(p.tr_couples[k2]))
        ex = h - int(math.floor(kids))
        if ex <= 0:
            continue
        mv = _systematic(w, ex, p.seed_v, "tier_cap2", c2)
        for q in range(len(mv)):
            if mv[q] <= 0:
                continue
            k3 = by_c[c2][q]
            hb = int(k3.split("|")[1])
            wb = int(k3.split("|")[2])
            n = mini(mv[q], int(p.tr_couples[k3]))
            p.tr_couples[k3] = int(p.tr_couples[k3]) - n
            k4 = "%d|%d|%d|4" % (c2, hb, wb)
            p.tr_couples[k4] = int(p.tr_couples.get(k4, 0)) + n
            if int(p.tr_couples[k3]) == 0:
                del p.tr_couples[k3]
            for side in [[(hb + 3) * 2], [(wb + 3) * 2 + 1]]:
                at = (ci * nbs + int(side[0])) * NTYPE
                fixed[at + 2] -= n
                fixed[at + 4] += n
            moved[c2] = int(moved.get(c2, 0)) + n
    return moved


# tiers.gd 881
def _ten_band(b):
    return 0 if b < 3 else mini(idiv(b - 3, 2) + 1, 8)


# tiers.gd 886
def _ten_shares(p):
    labels = ["<15", "15-24", "25-34", "35-44", "45-54", "55-64", "65-74", "75-84", "85+"]
    out = []
    for s in range(2):
        rows = []
        for g in range(9):
            rows.append([0.0, 0.0, 0.0, 0.0, 0.0, 0.0])
        out.append(rows)
    for c in p.tr_spec["type_by_band_sex"]["s_cells"]:
        out[int(c[0])][labels.index(str(c[1]))][int(c[2])] = float(c[3])
    return out


# tiers.gd 902
def _five_shares(p):
    ten = _ten_shares(p)
    cr = _v(p, "child_role")["by_pref"]["0"]
    pop = _v(p, "population_2020_by_pref_sex_band")["by_pref"]["0"]
    kind = [2, 0, 0, 0, 1, 3]
    out = []
    for s in range(2):
        q = _f64(BANDS * 5)
        for b in range(BANDS):
            e = cr["m" if s == 0 else "f"][b]
            den = float(e[2]) if b < 3 else float(pop[s][b - 3])
            q[b * 5] = float(e[3])
            q[b * 5 + 1] = float(e[4])
            q[b * 5 + 2] = float(e[2]) - float(e[3]) - float(e[4])
            q[b * 5 + 3] = maxf(0.0, den - float(e[2])) if b >= 3 else 0.0
            q[b * 5 + 4] = den
        rows = []
        for b2 in range(BANDS):
            g = _ten_band(b2)
            qg = PArr("f64", [0.0, 0.0, 0.0, 0.0, 0.0])
            for b3 in range(BANDS):
                if _ten_band(b3) == g:
                    for k in range(5):
                        qg[k] += q[b3 * 5 + k]
            v = []
            vt = 0.0
            for t in range(NTYPE):
                k2 = kind[t]
                qb = q[b2 * 5 + k2] / q[b2 * 5 + 4] if q[b2 * 5 + 4] > 0.0 else 0.0
                qgk = qg[k2] / qg[4] if qg[4] > 0.0 else 0.0
                r = qb / qgk if qgk > 0.0 and not (k2 == 3 and b2 < 3) else 1.0
                v.append(float(ten[s][g][t]) * r)
                vt += float(v[t])
            for t2 in range(NTYPE):
                v[t2] = float(v[t2]) / vt if vt > 0.0 else 0.0
            rows.append(v)
        out.append(rows)
    return out


# tiers.gd 948
def _age_unknown(p):
    au = _v(p, "age_unknown")["by_pref"]
    cr = _v(p, "child_role")["by_pref"]["0"]
    out = []
    for s in range(2):
        sk = "m" if s == 0 else "f"
        shape = _f64(BANDS)
        for b in range(BANDS):
            e = cr[sk][b]
            shape[b] = maxf(0.0, float(e[2]) - float(e[3]) - float(e[4]))
        nat = _f64(3 * BANDS)
        for c in au:
            if c == "0":
                continue
            a = au[c][sk]
            rows = PArr("f64", [float(a["rows"][0]), float(a["rows"][1]), float(a["rows"][2])])
            cols = _f64(BANDS)
            ct = 0.0
            for b2 in range(BANDS):
                cols[b2] = maxf(0.0, float(a["imputed"][b2]) - float(a["raw"][b2]))
                ct += cols[b2]
            rt = rows[0] + rows[1] + rows[2]
            if ct <= 0.0 or rt <= 0.0:
                continue
            for b3 in range(BANDS):
                cols[b3] *= rt / ct
            x = _f64(3 * BANDS)
            for b4 in range(BANDS):
                x[b4] = shape[b4] if b4 >= 3 else 0.0
                x[BANDS + b4] = shape[b4]
                x[2 * BANDS + b4] = 1.0
            _rake2(x, rows, cols, 3, BANDS, 500, 1e-12)
            for q in range(3 * BANDS):
                nat[q] += x[q]
        out.append(nat)
    return out


# tiers.gd 994
def _completed_shares(p, five, base, nc):
    au = _v(p, "age_unknown")["by_pref"]["0"]
    alloc = _age_unknown(p)
    nbs = BANDS * 2
    out = []
    for s in range(2):
        a = au["m" if s == 0 else "f"]
        rows = []
        for b in range(BANDS):
            raw = float(a["raw"][b])
            imp = float(a["imputed"][b])
            cnt = _f64(NTYPE)
            rel = 0.0
            for t in range(NTYPE):
                cnt[t] = float(five[s][b][t]) * raw
                rel += cnt[t] if t < 5 else 0.0
            unk = alloc[s][BANDS + b]
            for t2 in range(5):
                cnt[t2] += unk * cnt[t2] / rel if rel > 0.0 else 0.0
            cnt[0] += alloc[s][b]
            cnt[5] += alloc[s][2 * BANDS + b]
            v = []
            for t3 in range(NTYPE):
                v.append(cnt[t3] / imp if imp > 0.0 else float(five[s][b][t3]))
            rows.append(v)
        out.append(rows)
    want = float(_v(p, "household_target")["by_pref"]["0"][0])
    have = 0.0
    for ci in range(nc):
        for bs in range(nbs):
            have += float(out[bs % 2][idiv(bs, 2)][0]) * base[ci * nbs + bs]
    f = want / have if have > 0.0 else 1.0
    p.tr_margins["one_rake"] = [have, want, f]
    for s2 in range(2):
        for b2 in range(BANDS):
            r = out[s2][b2]
            s0 = float(r[0])
            n0 = minf(1.0, s0 * f)
            for t4 in range(NTYPE):
                r[t4] = n0 if t4 == 0 else (float(r[t4]) * (1.0 - n0) / (1.0 - s0) if s0 < 1.0 else 0.0)
    return out


# tiers.gd 1040
def _type_targets(y, nc, pop_bs, fixed, five):
    nbs = BANDS * 2
    n = _f64(nbs)
    f = _f64(nbs * NTYPE)
    yc = _f64(nbs)
    for ci in range(nc):
        for bs in range(nbs):
            n[bs] += pop_bs[ci * nbs + bs]
            for t in range(NTYPE):
                f[bs * NTYPE + t] += float(fixed[(ci * nbs + bs) * NTYPE + t])
                yc[bs] += y[(ci * nbs + bs) * NTYPE + t]
    tg = _f64(nbs * NTYPE)
    shift = 0.0
    for g2 in range(nbs):
        raw = _f64(NTYPE)
        rt = 0.0
        for t2 in range(NTYPE):
            raw[t2] = 0.0 if t2 == 1 else maxf(0.0, float(five[g2 % 2][idiv(g2, 2)][t2]) * n[g2] - f[g2 * NTYPE + t2])
            rt += raw[t2]
        r0 = minf(raw[0], yc[g2])
        for t3 in range(NTYPE):
            if t3 == 0:
                tg[g2 * NTYPE] = r0
            else:
                tg[g2 * NTYPE + t3] = raw[t3] / (rt - raw[0]) * (yc[g2] - r0) if rt - raw[0] > 0.0 else 0.0
            shift += abs(tg[g2 * NTYPE + t3] + f[g2 * NTYPE + t3] - float(five[g2 % 2][idiv(g2, 2)][t3]) * n[g2]) * 0.5
    return [tg, shift]


# tiers.gd 1075
def _fit(p, y, codes, prefectures, fixed, pop_bs, five):
    by_pref = _v(p, "type_by_prefecture")
    fit = _v(p, "fit")
    max_rounds = int(fit["max_rounds"])
    tol = float(fit["tol"])
    mean_size = PArr("f64", [1.0, 2.0, 3.6, 2.5, 4.2, 1.0])
    nc = len(codes)
    nbs = BANDS * 2
    base = _f64(nc * nbs)
    m = _f64(nc * NTYPE)
    for ci in range(nc):
        for bs in range(nbs):
            for t in range(NTYPE):
                v = y[(ci * nbs + bs) * NTYPE + t]
                base[ci * nbs + bs] += v
                m[ci * NTYPE + t] += v
    rows = _f64(nc)
    r64 = _f64(nc * NTYPE)
    for ci2 in range(nc):
        for t2 in range(NTYPE):
            rows[ci2] += m[ci2 * NTYPE + t2]
        code = "%02d" % codes[ci2]
        if code in by_pref:
            hs = by_pref[code]
            tot_w = 0.0
            for t3 in range(5):
                tot_w += float(hs[t3]) * mean_size[t3]
            fpt = _f64(NTYPE)
            for bs8 in range(nbs):
                for t8 in range(NTYPE):
                    fpt[t8] += float(fixed[(ci2 * nbs + bs8) * NTYPE + t8])
            priv = rows[ci2] - m[ci2 * NTYPE + 5]
            priv_all = priv + fpt[0] + fpt[1] + fpt[2] + fpt[3] + fpt[4]
            mt = _f64(5)
            mtot = 0.0
            for t4 in range(5):
                room = t4 != 1 and m[ci2 * NTYPE + t4] > 0.0
                mt[t4] = maxf(0.0, float(hs[t4]) * mean_size[t4] / tot_w * priv_all - fpt[t4]) if room else 0.0
                mtot += mt[t4]
            for t9 in range(5):
                m[ci2 * NTYPE + t9] = mt[t9] / mtot * priv if mtot > 0.0 else 0.0
        for t5 in range(NTYPE):
            r64[ci2 * NTYPE + t5] = m[ci2 * NTYPE + t5] / rows[ci2]
    tt = _type_targets(y, nc, pop_bs, fixed, five)
    tg = tt[0]
    p.tr_margins["ten_shift"] = tt[1]
    t0 = _v(p, "household_target")["by_pref"]
    m2 = _f64(nc * 2)
    n0 = 0.0
    for g0 in range(nbs):
        n0 += tg[g0 * NTYPE]
    s0 = 0.0
    for ci4 in range(nc):
        s0 += float(t0[str(codes[ci4])][0])
    for ci5 in range(nc):
        m2[ci5 * 2] = float(t0[str(codes[ci5])][0]) * n0 / s0
        m2[ci5 * 2 + 1] = rows[ci5] - m2[ci5 * 2]
    err = 0.0
    used = 0
    ny = len(y)
    span = nbs * NTYPE
    mix = [(i // span) * 2 + (0 if i % NTYPE == 0 else 1) for i in range(ny)]
    for r in range(max_rounds):
        used = r + 1
        sm = [0.0] * (nc * 2)
        for i in range(ny):
            sm[mix[i]] += y[i]
        for i2 in range(ny):
            mi = mix[i2]
            if sm[mi] > 0.0:
                y[i2] *= m2[mi] / sm[mi]
        sg = [0.0] * span
        for i3 in range(ny):
            sg[i3 % span] += y[i3]
        for i4 in range(ny):
            gi = i4 % span
            if sg[gi] > 0.0:
                y[i4] *= tg[gi] / sg[gi]
        sb = [0.0] * (nc * nbs)
        for i5 in range(ny):
            sb[i5 // NTYPE] += y[i5]
        for i6 in range(ny):
            if sb[i6 // NTYPE] > 0.0:
                y[i6] *= base[i6 // NTYPE] / sb[i6 // NTYPE]
        err = 0.0
        sm = [0.0] * (nc * 2)
        for i7 in range(ny):
            sm[mix[i7]] += y[i7]
        for j in range(len(sm)):
            if m2[j] > 0.0:
                err = maxf(err, abs(sm[j] - m2[j]) / m2[j])
        sg = [0.0] * span
        for i8 in range(ny):
            sg[i8 % span] += y[i8]
        for j2 in range(len(sg)):
            if tg[j2] > 0.0:
                err = maxf(err, abs(sg[j2] - tg[j2]) / tg[j2])
        if err < tol:
            break
    gap = 0.0
    sf = _f64(nc * NTYPE)
    for i9 in range(ny):
        sf[(i9 // span) * NTYPE + i9 % NTYPE] += y[i9]
    for ci3 in range(nc):
        for t7 in range(NTYPE):
            gap = maxf(gap, abs(sf[ci3 * NTYPE + t7] / rows[ci3] - r64[ci3 * NTYPE + t7]))
    return PArr("f64", [gap, err, float(used)])


# tiers.gd 1206
def _rake2(x, rows, cols, nr, nk, rounds, tol):
    for r in range(rounds):
        for i in range(nr):
            s = 0.0
            for k in range(nk):
                s += x[i * nk + k]
            if s > 0.0:
                for k2 in range(nk):
                    x[i * nk + k2] *= rows[i] / s
        worst = 0.0
        for k3 in range(nk):
            s2 = 0.0
            for i2 in range(nr):
                s2 += x[i2 * nk + k3]
            if s2 > 0.0:
                worst = maxf(worst, abs(s2 - cols[k3]) / maxf(1.0, cols[k3]))
                for i3 in range(nr):
                    x[i3 * nk + k3] *= cols[k3] / s2
        if worst < tol:
            break


# tiers.gd 1232
def _round(p, y, codes, prefectures, base, fixed):
    nc = len(codes)
    nbs = BANDS * 2
    R = _i64(nc * nbs)
    for ci in range(nc):
        # Why pop_persons when given (step (c), AMENDED): tiers.gd truncates to whole thousands, which held while the inputs were in
        # thousands; rule (D)'s are persons, and the truncation lost 27,543 of them (S0-c-pop)
        pr = prefectures["%02d" % codes[ci]]
        pop = int(pr["pop_persons"]) if "pop_persons" in pr else int(pr["pop_thousand"]) * 1000
        v = _f64(nbs)
        for bs in range(nbs):
            v[bs] = base[ci * nbs + bs]
        ints = _largest(v, pop)
        for bs2 in range(nbs):
            R[ci * nbs + bs2] = ints[bs2]
    p.tr_margins = {"pbs": {}, "bst": {}, "bs_real": {}, "bst_real": {}}
    for ci6 in range(nc):
        for bs6 in range(nbs):
            p.tr_margins["pbs"]["%d|%d|%d" % (codes[ci6], idiv(bs6, 2), bs6 % 2)] = R[ci6 * nbs + bs6]
            kr = "%d|%d" % (idiv(bs6, 2), bs6 % 2)
            p.tr_margins["bs_real"][kr] = float(p.tr_margins["bs_real"].get(kr, 0.0)) + base[ci6 * nbs + bs6]
    out = _i64(len(y))
    moves = 0
    oob = 0
    over = 0
    for bs3 in range(nbs):
        ntot = 0
        rows = _f64(nc)
        Rn = _i64(nc)
        fcol = _i64(NTYPE)
        for ci2 in range(nc):
            fs = 0
            for t0 in range(NTYPE):
                fs += fixed[(ci2 * nbs + bs3) * NTYPE + t0]
                fcol[t0] += fixed[(ci2 * nbs + bs3) * NTYPE + t0]
            over += maxi(0, fs - R[ci2 * nbs + bs3])
            Rn[ci2] = maxi(0, R[ci2 * nbs + bs3] - fs)
            ntot += Rn[ci2]
            rows[ci2] = float(Rn[ci2])
        ct = _f64(NTYPE)
        x = _f64(nc * NTYPE)
        for ci3 in range(nc):
            for t in range(NTYPE):
                x[ci3 * NTYPE + t] = y[(ci3 * nbs + bs3) * NTYPE + t]
                ct[t] += x[ci3 * NTYPE + t]
        C = _largest(ct, ntot)
        for t6 in range(NTYPE):
            p.tr_margins["bst"]["%d|%d|%d" % (idiv(bs3, 2), bs3 % 2, t6)] = C[t6] + fcol[t6]
            p.tr_margins["bst_real"]["%d|%d|%d" % (idiv(bs3, 2), bs3 % 2, t6)] = ct[t6] + float(fcol[t6])
        cf = _f64(NTYPE)
        for t2 in range(NTYPE):
            cf[t2] = float(C[t2])
        _rake2(x, rows, cf, nc, NTYPE, 500, 1e-13)
        z = _i64(nc * NTYPE)
        for ci4 in range(nc):
            rv = _f64(NTYPE)
            for t3 in range(NTYPE):
                rv[t3] = x[ci4 * NTYPE + t3]
            ri = _systematic(rv, Rn[ci4], p.seed_v, "tier_row", ci4 * nbs + bs3)
            for t4 in range(NTYPE):
                z[ci4 * NTYPE + t4] = ri[t4]
        mv = _repair(z, x, C, nc)
        moves += int(mv[0])
        oob += int(mv[1])
        to4 = 0
        for ci9 in range(nc):
            to4 += z[ci9 * NTYPE + 1]
            z[ci9 * NTYPE + 4] += z[ci9 * NTYPE + 1]
            z[ci9 * NTYPE + 1] = 0
        k1 = "%d|%d|1" % (idiv(bs3, 2), bs3 % 2)
        p.tr_margins["bst"][k1] = int(p.tr_margins["bst"][k1]) - to4
        k4 = "%d|%d|4" % (idiv(bs3, 2), bs3 % 2)
        p.tr_margins["bst"][k4] = int(p.tr_margins["bst"][k4]) + to4
        p.tr_margins["r77_type1_to4"] = int(p.tr_margins.get("r77_type1_to4", 0)) + to4
        for ci5 in range(nc):
            for t5 in range(NTYPE):
                out[(ci5 * nbs + bs3) * NTYPE + t5] = z[ci5 * NTYPE + t5] + fixed[(ci5 * nbs + bs3) * NTYPE + t5]
    p.tr_residual.append(float(moves))
    p.tr_residual.append(float(oob))
    p.tr_margins["r77_over"] = over
    return out


# tiers.gd 1507
def _repair(z, x, C, nc, nk=NTYPE):
    moves = 0
    oob = 0
    for guard in range(100000):
        d = [0] * nk
        for t in range(nk):
            d[t] = -C[t]
        for ci in range(nc):
            for t2 in range(nk):
                d[t2] += z[ci * nk + t2]
        src = -1
        for t3 in range(nk):
            if d[t3] > 0:
                src = t3
                break
        if src < 0:
            break
        prev = {src: [-1, -1]}
        queue = [src]
        dst = -1
        while queue and dst < 0:
            a = queue.pop(0)
            for ci2 in range(nc):
                if float(z[ci2 * nk + a]) <= _floor(x[ci2 * nk + a]) + 1e-9:
                    continue
                for b in range(nk):
                    if b in prev or float(z[ci2 * nk + b]) >= _ceil(x[ci2 * nk + b] - 1e-9):
                        continue
                    prev[b] = [a, ci2]
                    queue.append(b)
                    if d[b] < 0:
                        dst = b
                        break
                if dst >= 0:
                    break
        if dst >= 0:
            at = dst
            while at != src:
                pv = prev[at]
                z[int(pv[1]) * nk + int(pv[0])] -= 1
                z[int(pv[1]) * nk + at] += 1
                moves += 1
                at = int(pv[0])
        else:
            dn = -1
            for t4 in range(nk):
                if d[t4] < 0:
                    dn = t4
                    break
            for ci3 in range(nc):
                if z[ci3 * nk + src] > 0:
                    z[ci3 * nk + src] -= 1
                    z[ci3 * nk + dn] += 1
                    oob += 1
                    break
    return [moves, oob]


# tiers.gd 3410
def _head_targets(p):
    tgt = _v(p, "household_target")["by_pref"]
    out = {}
    for c in tgt:
        if c == "0":
            continue
        for t2 in range(5):
            out["%02d|%d" % (int(c), t2)] = int(roundf(float(tgt[c][t2])))
        for t3 in [1, 2, 4]:
            out["%02d|%d" % (int(c), t3)] = 0
    h4s = p.tr_margins["h4s"]
    for c2 in h4s:
        out["%02d|4" % int(c2)] = int(roundf(float(h4s[c2])))
    for key in p.tr_couples:
        k = key.split("|")
        if int(k[3]) == 1 or int(k[3]) == 2 or int(k[3]) == 4:
            out["%02d|%s" % (int(k[0]), k[3])] = int(out["%02d|%s" % (int(k[0]), k[3])]) + int(p.tr_couples[key])
    return out


# tiers.gd 3914
def _child_targets(p, codes, base):
    cr = _v(p, "child_role")["by_pref"]
    au = _v(p, "age_unknown")["by_pref"]
    nbs = BANDS * 2
    out = _f64(len(codes) * nbs * 2)
    for ci in range(len(codes)):
        key = str(codes[ci])
        for bs in range(nbs):
            b = idiv(bs, 2)
            e = cr[key]["m" if bs % 2 == 0 else "f"][b]
            den = float(au[key]["m" if bs % 2 == 0 else "f"]["imputed"][b])
            if den <= 0.0:
                continue
            out[(ci * nbs + bs) * 2] = float(e[1]) / den * base[ci * nbs + bs]
            out[(ci * nbs + bs) * 2 + 1] = float(int(e[0]) - int(e[1])) / den * base[ci * nbs + bs]
    return out


# tiers.gd 3942
def _r77_couples(p, codes, base):
    cba = _v(p, "couples_by_age")
    cob = _v(p, "couple_only_by_age")
    c24 = _v(p, "couples_2024")["by_pref"]
    nc = len(codes)
    nbs = BANDS * 2
    fixed = _i64(nc * nbs * NTYPE)
    out = {}
    nh = {}
    total = 0
    cpl = _f64(nc * 225)
    co_x = _f64(nc * 225)
    nhf = _f64(nc * 450)
    call_c = _f64(nc * 225)
    nh_clip = 0.0
    c24_clip = 0.0
    for ci in range(nc):
        key = str(codes[ci])
        tab = cba["by_pref"][key]
        cot = cob["by_pref"][key]
        t24 = c24[key]
        nh_clip += _r77_nonhead(p, key, tab, nhf, ci)
        coarse_n = _f64(49)
        for h0 in range(15):
            for w0 in range(15):
                coarse_n[_coarse(h0) * 7 + _coarse(w0)] += float(tab[h0][w0]) * (1.0 - nhf[ci * 450 + h0 * 15 + w0] - nhf[ci * 450 + 225 + h0 * 15 + w0])
        rw = _f64(15)
        cw = _f64(15)
        for h1 in range(15):
            for w1 in range(15):
                rw[h1] += float(t24[h1][w1])
                cw[w1] += float(t24[h1][w1])
        for hb in range(15):
            if rw[hb] <= 0.0:
                continue
            fm = minf(1.0, base[ci * nbs + (hb + 3) * 2] / rw[hb])
            for wb2 in range(15):
                cv = float(t24[hb][wb2])
                if cv <= 0.0:
                    continue
                fc = minf(fm, base[ci * nbs + (wb2 + 3) * 2 + 1] / cw[wb2])
                c24_clip += cv * (1.0 - fc)
                cc = _coarse(hb) * 7 + _coarse(wb2)
                call_c[ci * 225 + hb * 15 + wb2] = cv * fc
                cpl[ci * 225 + hb * 15 + wb2] = call_c[ci * 225 + hb * 15 + wb2] * (1.0 - nhf[ci * 450 + hb * 15 + wb2] - nhf[ci * 450 + 225 + hb * 15 + wb2])
                co_x[ci * 225 + hb * 15 + wb2] = cpl[ci * 225 + hb * 15 + wb2] * (minf(1.0, float(cot[_coarse(hb)][_coarse(wb2)]) / coarse_n[cc]) if coarse_n[cc] > 0.0 else 0.0)
    co_x = _r77_rake(p, codes, base, cpl, co_x)
    five0 = _five_shares(p)
    ct = _child_targets(p, codes, base)
    role_tbs = _v(p, "role_by_type_band_sex")
    crp = _v(p, "child_role")["by_pref"]
    aup = _v(p, "age_unknown")["by_pref"]
    n4 = _f64(BANDS * 7)
    for ci in range(nc):
        key0 = str(codes[ci])
        for q0 in range(225):
            g0 = idiv(q0, 15) + 3
            n4[g0 * 7] += call_c[ci * 225 + q0]
            n4[g0 * 7 + 1] += call_c[ci * 225 + q0] * (nhf[ci * 450 + q0] + nhf[ci * 450 + 225 + q0])
            n4[g0 * 7 + 2] += co_x[ci * 225 + q0]
            n4[g0 * 7 + 3] += cpl[ci * 225 + q0] - co_x[ci * 225 + q0]
        for b0 in range(3, BANDS):
            nm = base[ci * nbs + b0 * 2]
            imp = float(aup[key0]["m"]["imputed"][b0])
            n4[b0 * 7 + 4] += float(crp[key0]["m"][b0][3]) / imp * nm if imp > 0.0 else 0.0
            n4[b0 * 7 + 5] += ct[(ci * nbs + b0 * 2) * 2]
            sh = role_tbs.get("3,%d,0" % b0, [0.0, 0.0, 0.0, 0.0, 0.0])
            st = 0.0
            for r0 in range(5):
                st += maxf(0.0, float(sh[r0]))
            n4[b0 * 7 + 6] += float(five0[0][b0][3]) * nm * (maxf(0.0, float(sh[0])) / st if st > 0.0 else 0.0)
    s4 = _f64(BANDS)
    n4_rep = {}
    for g2 in range(3, BANDS):
        e = g2 * 7
        raw = n4[e] - (n4[e + 4] - n4[e + 5] - n4[e + 6])
        t4 = clampf(raw, n4[e + 1], n4[e + 1] + n4[e + 3])
        s4[g2] = (t4 - n4[e + 1]) / n4[e + 3] if n4[e + 3] > 0.0 else 0.0
        n4_rep[g2] = [n4[e], n4[e + 1], raw, t4, n4[e + 4], n4[e + 5], n4[e + 6]]
    m22 = _v(p, "m022_within_couple")
    cen = _v(p, "household_target")["census_2020"]
    t2_clip = 0.0
    h4s = {}
    for ci in range(nc):
        key2 = str(codes[ci])
        tab2 = cba["by_pref"][key2]
        d1 = 0.0
        d2 = 0.0
        c20t = 0.0
        nh20 = 0.0
        for h3 in range(15):
            for w3 in range(15):
                x3 = float(tab2[h3][w3])
                d1 += float(m22["s1"][h3]) * x3
                d2 += float(m22["s2"][h3]) * x3
                c20t += x3
                nh20 += x3 * (nhf[ci * 450 + h3 * 15 + w3] + nhf[ci * 450 + 225 + h3 * 15 + w3])
        f1 = float(cen[key2][1]) / d1 if d1 > 0.0 else 0.0
        f2 = float(cen[key2][2]) / d2 if d2 > 0.0 else 0.0
        s4p = _f64(15)
        for h4 in range(15):
            s4p[h4] = maxf(0.0, 1.0 - f1 * float(m22["s1"][h4]) - f2 * float(m22["s2"][h4]))
        h4s[codes[ci]] = maxf(0.0, (float(cen[key2][4]) - (c20t - float(cen[key2][1]) - float(cen[key2][2]) - nh20)) * float(m22["other_ratio"]))
        v = PArr("f64")
        keys = []
        for hb in range(15):
            for wb2 in range(15):
                c = cpl[ci * 225 + hb * 15 + wb2]
                call = call_c[ci * 225 + hb * 15 + wb2]
                if call <= 0.0:
                    continue
                co = minf(co_x[ci * 225 + hb * 15 + wb2], c)
                r2 = call - co - maxf(s4p[hb] * call, call - c)
                c2 = maxf(0.0, r2)
                t2_clip += c2 - r2
                for tt in [[1, co], [2, c2], [4, maxf(0.0, c - co - c2)], [T.NH_CHILD, call * nhf[ci * 450 + hb * 15 + wb2]], [T.NH_PARENT, call * nhf[ci * 450 + 225 + hb * 15 + wb2]]]:
                    v.append(float(tt[1]))
                    keys.append([hb, wb2, int(tt[0])])
        tot = 0.0
        for x in v:
            tot += x
        ints = _systematic(v, int(math.floor(tot + 0.5)), p.seed_v, "tier_r77", ci)
        for q in range(len(ints)):
            if ints[q] <= 0:
                continue
            k = keys[q]
            t5 = int(k[2])
            if t5 >= T.NH_CHILD:
                nh["%d|%d|%d|%d" % (codes[ci], int(k[0]), int(k[1]), t5 - T.NH_CHILD)] = ints[q]
                t5 = 4
            else:
                out["%d|%d|%d|%d" % (codes[ci], int(k[0]), int(k[1]), t5)] = ints[q]
            fixed[(ci * nbs + (int(k[0]) + 3) * 2) * NTYPE + t5] += ints[q]
            fixed[(ci * nbs + (int(k[1]) + 3) * 2 + 1) * NTYPE + t5] += ints[q]
            total += ints[q]
    return {"fixed": fixed, "couples": out, "nonhead": nh, "nh_clip": nh_clip, "total": total, "rake": p.tr_margins.get("r77_rake", {}), "n4": n4_rep, "t2_clip": t2_clip, "c24_clip": c24_clip, "h4s": h4s}


# tiers.gd 4110
def _r77_nonhead(p, key, tab, nhf, ci):
    nh = _v(p, "nonhead_couples")["by_pref"][key]
    cc = _f64(225)
    pc = _f64(225)
    rowt = _f64(15)
    colt = _f64(15)
    all_ = 0.0
    for h in range(15):
        for w in range(15):
            rowt[h] += float(tab[h][w])
            colt[w] += float(tab[h][w])
            all_ += float(tab[h][w])
    nch = 0.0
    for b in range(15):
        fw = float(nh["child_spouse_f"][b])
        mh = float(nh["child_spouse_m"][b])
        nch += fw + mh
        for o in range(15):
            if colt[b] > 0.0:
                cc[o * 15 + b] += fw * float(tab[o][b]) / colt[b]
            if rowt[b] > 0.0:
                cc[b * 15 + o] += mh * float(tab[b][o]) / rowt[b]
    npc = all_ - float(nh["head_spouses"]) - nch
    clip = maxf(0.0, -npc)
    npc = maxf(0.0, npc)
    pt = 0.0
    for b2 in range(15):
        pt += float(nh["parents_m"][b2])
    for h2 in range(15):
        nhh = npc * float(nh["parents_m"][h2]) / pt if pt > 0.0 else 0.0
        for w2 in range(15):
            if rowt[h2] > 0.0:
                pc[h2 * 15 + w2] = nhh * float(tab[h2][w2]) / rowt[h2]
    for q in range(225):
        n = float(tab[idiv(q, 15)][q % 15])
        if n <= 0.0:
            clip += cc[q] + pc[q]
            continue
        s = (cc[q] + pc[q]) / n
        f = 1.0 / s if s > 1.0 else 1.0
        clip += (cc[q] + pc[q]) * (1.0 - f)
        nhf[ci * 450 + q] = cc[q] * f / n
        nhf[ci * 450 + 225 + q] = pc[q] * f / n
    return clip


# tiers.gd 4166
def _r77_rake(p, codes, base, cpl, x0):
    nc = len(codes)
    nbs = BANDS * 2
    tbs = _v(p, "type_by_band_sex")
    x = x0.duplicate()
    a = _f64(nc * 49)
    for ci in range(nc):
        for q in range(225):
            a[ci * 49 + _coarse(idiv(q, 15)) * 7 + _coarse(q % 15)] += x0[ci * 225 + q]
    tab = _f64(30)
    for b in range(15):
        for s in range(2):
            n = 0.0
            for ci2 in range(nc):
                n += base[ci2 * nbs + (b + 3) * 2 + s]
            tab[s * 15 + b] = float(tbs[s][b + 3][1]) * n
    tgt = _f64(30)
    for s2 in range(2):
        g = 0.0
        tb = 0.0
        for b2 in range(1, 9):
            tb += tab[s2 * 15 + b2]
            for ci3 in range(nc):
                for o in range(15):
                    g += x0[ci3 * 225 + (b2 * 15 + o if s2 == 0 else o * 15 + b2)]
        for b3 in range(1, 9):
            tgt[s2 * 15 + b3] = g * tab[s2 * 15 + b3] / tb if tb > 0.0 else 0.0
    err = PArr("f64", [0.0, 0.0, 0.0])
    worst_a = []
    # Why the index lists built once and not each round as tiers.gd does: they depend on the indices only, so the cells raked and
    # their order are the same
    coarse_cells = []
    for ci4 in range(nc):
        cells = []
        for k in range(49):
            cells.append([])
        for q2 in range(225):
            k2 = _coarse(idiv(q2, 15)) * 7 + _coarse(q2 % 15)
            cells[k2].append(ci4 * 225 + q2)
        coarse_cells.append(cells)
    band_idx = []
    for s3 in range(2):
        for b4 in range(1, 9):
            idx = []
            for ci5 in range(nc):
                for o2 in range(15):
                    idx.append(ci5 * 225 + (b4 * 15 + o2 if s3 == 0 else o2 * 15 + b4))
            band_idx.append((idx, s3 * 15 + b4))
    for it in range(200):
        for ci4 in range(nc):
            cells = coarse_cells[ci4]
            for k3 in range(49):
                _rake_group(x, cpl, cells[k3], a[ci4 * 49 + k3])
        for idx, ti in band_idx:
            _rake_group(x, cpl, idx, tgt[ti])
    for ci6 in range(nc):
        sa = _f64(49)
        for q3 in range(225):
            sa[_coarse(idiv(q3, 15)) * 7 + _coarse(q3 % 15)] += x[ci6 * 225 + q3]
        for k4 in range(49):
            if a[ci6 * 49 + k4] > 0.0 and abs(sa[k4] / a[ci6 * 49 + k4] - 1.0) > err[0]:
                err[0] = abs(sa[k4] / a[ci6 * 49 + k4] - 1.0)
                worst_a = [codes[ci6], idiv(k4, 7), k4 % 7, a[ci6 * 49 + k4], sa[k4]]
    before = _f64(30)
    after = _f64(30)
    for ci7 in range(nc):
        for q4 in range(225):
            before[idiv(q4, 15)] += x0[ci7 * 225 + q4]
            before[15 + q4 % 15] += x0[ci7 * 225 + q4]
            after[idiv(q4, 15)] += x[ci7 * 225 + q4]
            after[15 + q4 % 15] += x[ci7 * 225 + q4]
    worst_b = [[], []]
    for s4 in range(2):
        for b5 in range(9):
            if tgt[s4 * 15 + b5] > 0.0 and abs(after[s4 * 15 + b5] / tgt[s4 * 15 + b5] - 1.0) > err[1 + s4]:
                err[1 + s4] = abs(after[s4 * 15 + b5] / tgt[s4 * 15 + b5] - 1.0)
                worst_b[s4] = [b5, tgt[s4 * 15 + b5], after[s4 * 15 + b5]]
    p.tr_margins["r77_rake"] = {"err": err, "before": before, "after": after, "table": tab, "worst": [worst_a, worst_b]}
    return x


# tiers.gd 4245
def _rake_group(x, cap, idx, t):
    for rep_i in range(8):
        held = 0.0
        free = 0.0
        for i in idx:
            if x[i] >= cap[i]:
                held += x[i]
            else:
                free += x[i]
        if free <= 0.0:
            return
        f = (t - held) / free
        if abs(f - 1.0) < 1e-12:
            return
        hit = False
        for i2 in idx:
            if x[i2] < cap[i2]:
                x[i2] = x[i2] * maxf(0.0, f)
                if x[i2] > cap[i2]:
                    x[i2] = cap[i2]
                    hit = True
        if not hit:
            return


# tiers.gd 4271
def _coarse(b):
    return 0 if b < 9 else b - 8


def _realias(p, ctx):
    # The oracle's locals share objects (fixed is cp["fixed"], y is sd[0], tr_couples is cp["couples"]) and later stages write
    # through them; a state read back from a dump holds copies, so the links are restored before a stage writes
    # Why not compare-and-skip: the copies are equal by construction at every checkpoint, so relinking never changes a value
    cp = ctx.get("cp")
    if cp is not None:
        if "fixed" in ctx:
            cp["fixed"] = ctx["fixed"]
        cp["couples"] = p.tr_couples
        cp["nonhead"] = p.tr_nh_couples
    if "sd" in ctx and "y" in ctx:
        ctx["sd"][0] = ctx["y"]


# start_trace.gd 59-88 (tiers.gd 61-88)
def st01_base(p, ctx):
    prefectures = ctx["prefectures"]
    K = p.tier_k if p.tier_k > 0 else int(_v(p, "k_points"))
    p.tr_k = K
    cls = _v(p, "classes")
    emp_bs = _v(p, "employment_by_band_sex")
    adult_shares = cls["adult_shares"]
    ctot = 0.0
    for a0 in range(len(p.cohort)):
        ctot += p.cohort[a0]
    band_share = _f64(BANDS * 2)
    for a in range(p.AGES):
        for s in range(2):
            band_share[band_of(a) * 2 + s] += p.cohort[a * p.SEXES + s] / ctot
    age_in_band = _f64(p.AGES * 2)
    for a2 in range(p.AGES):
        for s2 in range(2):
            bs = band_share[band_of(a2) * 2 + s2]
            age_in_band[a2 * 2 + s2] = (p.cohort[a2 * p.SEXES + s2] / ctot) / bs if bs > 0.0 else 0.0
    codes = []
    for code in prefectures:
        codes.append(int(code))
    gdsort.sort(codes)
    nc = len(codes)
    nbs = BANDS * 2
    base = _base(p, codes, prefectures, band_share)
    emp_c = _employment(p, base, codes, emp_bs)
    ctx.update({"K": K, "cls": cls, "emp_bs": emp_bs, "adult_shares": adult_shares, "ctot": ctot, "band_share": band_share,
                "age_in_band": age_in_band, "codes": codes, "nc": nc, "nbs": nbs, "base": base, "emp_c": emp_c})


# start_trace.gd 93-97
def st02_couples(p, ctx):
    cp = _r77_couples(p, ctx["codes"], ctx["base"])
    fixed = cp["fixed"]
    p.tr_couples = cp["couples"]
    p.tr_nh_couples = cp["nonhead"]
    p.tr_margins["h4s"] = cp["h4s"]
    ctx["cp"] = cp
    ctx["fixed"] = fixed


# start_trace.gd 99-102
def st03_fit(p, ctx):
    _realias(p, ctx)
    codes, base, nc, fixed = ctx["codes"], ctx["base"], ctx["nc"], ctx["fixed"]
    five = _completed_shares(p, _five_shares(p), base, nc)
    sd = _seed(nc, base, fixed, five)
    y = sd[0]
    p.tr_residual = _fit(p, y, codes, ctx["prefectures"], fixed, base, five)
    ctx["five"] = five
    ctx["sd"] = sd
    ctx["y"] = y


# start_trace.gd 106-112
def st04_cap_floor(p, ctx):
    _realias(p, ctx)
    codes, base, nc, fixed, five = ctx["codes"], ctx["base"], ctx["nc"], ctx["fixed"], ctx["five"]
    sd = ctx["sd"]
    y = ctx["y"]
    moved = _type2_cap(p, codes, y, fixed)
    if moved:
        sd = _seed(nc, base, fixed, five)
        y = sd[0]
        p.tr_residual = _fit(p, y, codes, ctx["prefectures"], fixed, base, five)
    floor_moved = _size_floor(p, codes, y, fixed)
    floor_excess = sd[1]
    ctx.update({"sd": sd, "y": y, "moved": moved, "floor_moved": floor_moved, "floor_excess": floor_excess})


# start_trace.gd 114-116
def st05_round(p, ctx):
    _realias(p, ctx)
    ten_shift = float(p.tr_margins.get("ten_shift", 0.0))
    one_rake = p.tr_margins.get("one_rake", [])
    yi = _round(p, ctx["y"], ctx["codes"], ctx["prefectures"], ctx["base"], ctx["fixed"])
    ctx.update({"ten_shift": ten_shift, "one_rake": one_rake, "yi": yi})


# start_trace.gd 118-129: the margins _round's reset dropped, put back. Why not inside st05_round: the oracle's 05_round check is
# taken before these lines, so the stage after it runs them first
def st05_margins(p, ctx):
    cp = ctx["cp"]
    p.tr_margins["ten_shift"] = ctx["ten_shift"]
    p.tr_margins["one_rake"] = ctx["one_rake"]
    p.tr_margins["t2_clip"] = cp["t2_clip"]
    p.tr_margins["c24_clip"] = cp["c24_clip"]
    p.tr_margins["h4s"] = cp["h4s"]
    p.tr_margins["floor_moved"] = ctx["floor_moved"]
    p.tr_margins["r77_floor_excess"] = ctx["floor_excess"]
    p.tr_margins["r77_couples"] = cp["total"]
    p.tr_margins["r77_rake"] = cp["rake"]
    p.tr_margins["n4"] = cp["n4"]
    p.tr_margins["n4_cap"] = ctx["moved"]
    p.tr_margins["nh_clip"] = cp["nh_clip"]
