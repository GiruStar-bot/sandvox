# tiers.gd's households at cd165891 (stage 14_households): _households and the functions it reaches, in file order, line by line
import math

from core import detmath as DM
from core import gdsort, keyed
from core.gd import clampi, maxf, maxi, minf, mini, roundf
from core.prims import dep_round, systematic as _systematic
from tiers.start import a_fit as A
from tiers.start import e_t21 as E
from tiers.start import tconst as T
from tiers.start.common import _largest, _v
from tiers.start.p import PArr

BANDS = T.BANDS
NTYPE = T.NTYPE
NEMP = T.NEMP
NCLASS = T.NCLASS
CLASS_REST = T.CLASS_REST
ADULT_FROM = T.ADULT_FROM
KEY_STRIDE = T.KEY_STRIDE
SIZE_MIN = T.SIZE_MIN
SIZE_MAX = T.SIZE_MAX

_ROLE_DEF = [1.0, 0.0, 0.0, 0.0, 0.0]


def st14_households(p, ctx):
    _households(p)


# tiers.gd 2548
def _households(p):
    role_tbs = _v(p, "role_by_type_band_sex")
    size_th = _v(p, "size_by_type_hband")
    p.tr_hh = {}
    p.tr_nh_hh = {}
    p.tr_margins["hh_unfilled"] = 0
    p.tr_margins["hh_unfilled_t"] = {}
    p.tr_margins["hh_childless"] = 0
    p.tr_margins["hh_partner_short"] = 0
    p.tr_margins["head_gap"] = {}
    targets = A._head_targets(p)
    lt = _l_other(p)
    p.tr_margins["lc_clip"] = {}
    groups = {}
    tr_key = p.tr_key
    for u in range(p.tr_units):
        c = tr_key[u * KEY_STRIDE]
        for mi in range(p.tr_mix_off[u], p.tr_mix_off[u + 1]):
            n = p.tr_mix_n[mi]
            if n <= 0:
                continue
            code = p.tr_mix_code[mi]
            t = (code // NEMP) % NTYPE
            gk = "%02d|%d" % (c, t)
            if gk not in groups:
                groups[gk] = []
            groups[gk].append([u, tr_key[u * KEY_STRIDE + 1], tr_key[u * KEY_STRIDE + 2], code // (NTYPE * NEMP), n, mi])
    gkeys = list(groups.keys())
    gdsort.sort(gkeys)
    for gk2 in gkeys:
        parts = gk2.split("|")
        _household_group(p, int(parts[0]), int(parts[1]), groups[gk2], role_tbs, size_th, int(targets.get(gk2, -1)), lt)


# tiers.gd 2581
def _household_group(p, c, t, ents, role_tbs, size_th, want_h, lt):
    ne = len(ents)
    roles = []
    nhr = []
    for j0 in range(ne):
        nhr.append([0, 0])
    heads = 0
    partners = 0
    for j in range(ne):
        e = ents[j]
        sh = role_tbs.get("%d,%d,%d" % (t, int(e[1]), int(e[2])), _ROLE_DEF)
        v = []
        for r in range(5):
            v.append(float(e[4]) * maxf(0.0, float(sh[r])))
        tot = 0.0
        for r2 in range(5):
            tot += v[r2]
        if tot <= 0.0:
            v[0] = float(e[4])
        rc = _systematic(v, int(e[4]), p.seed_v, "tier_role", int(e[5]))
        roles.append(rc)
        heads += rc[0]
        partners += rc[1]
    gap = p.tr_margins["head_gap"]
    if t == 1 or t == 2 or t == 4:
        roles = _r77_roles(p, c, t, ents, role_tbs, want_h, nhr, lt)
        heads = 0
        partners = 0
        for j7 in range(ne):
            heads += roles[j7][0]
            partners += roles[j7][1]
        if want_h >= 0:
            gap[t] = int(gap.get(t, 0)) + heads - want_h
    elif want_h >= 0 and t == 3:
        gap[t] = int(gap.get(t, 0)) + _set_heads(p, ents, roles, heads, want_h, role_tbs, t, c * NTYPE + t)
        heads = 0
        partners = 0
        for j9 in range(ne):
            heads += roles[j9][0]
            partners += roles[j9][1]
    elif want_h >= 0 and t == 0:
        gap[t] = int(gap.get(t, 0)) + heads - want_h
    hh_heads = {}
    hh_men = {}
    by_hb = PArr("i64")
    by_hb.resize(BANDS)
    for j2 in range(ne):
        h = roles[j2][0]
        if h > 0:
            kh = int(ents[j2][1]) * NCLASS + int(ents[j2][3])
            hh_heads[kh] = int(hh_heads.get(kh, 0)) + h
            if int(ents[j2][2]) == 0:
                hh_men[kh] = int(hh_men.get(kh, 0)) + h
            by_hb[int(ents[j2][1])] += h
    if not hh_heads:
        hh_heads[mini(BANDS - 1, ADULT_FROM // 5) * NCLASS + CLASS_REST] = 0
    members = {}
    for kh2 in hh_heads:
        members[kh2] = {}
    for j3 in range(ne):
        if roles[j3][0] > 0:
            _member_add(members, int(ents[j3][1]) * NCLASS + int(ents[j3][3]), int(ents[j3][0]), 0, roles[j3][0])
    if t == 1 or t == 2 or t == 4:
        _place_partners(p, ents, roles, by_hb, hh_men, members, c * NTYPE + t, _r77_z(p, c, t, ents, roles))
    if t == 4:
        filled = _place_nonhead(p, c, ents, nhr, hh_heads, members)
        for j6 in range(ne):
            roles[j6][2] += int(nhr[j6][0])
            roles[j6][3] += int(nhr[j6][1])
        _one_member_each(p, c, ents, roles, hh_heads, members, filled)
    kids = PArr("i64")
    kids.resize(ne)
    for j5 in range(ne):
        kids[j5] = roles[j5][2]
    if t == 2 or t == 3:
        _one_child_each(p, t, ents, kids, hh_heads, members)
    dens = _child_dens(p) if t == 4 else PArr("f64")
    for j4 in range(ne):
        for r3 in (1, 2, 3, 4):
            m = kids[j4] if r3 == 2 else roles[j4][r3]
            if m <= 0 or ((t == 1 or t == 2 or t == 4) and r3 == 1):
                continue
            if t == 4 and r3 == 3:
                _parent_window(p, by_hb, members, hh_heads, ents[j4], m, dens)
                continue
            want = clampi(int(ents[j4][1]) + (6 if r3 == 2 else (-6 if r3 == 3 else 0)), 0, BANDS - 1)
            hb = _nearest_hb(by_hb, want)
            _member_by_class(p, members, hh_heads, hb, int(ents[j4][0]), r3, m, "tier_mem", (int(ents[j4][5]) * 8 + r3))
    mk = list(members.keys())
    gdsort.sort(mk)
    for kh3 in mk:
        absent = 0
        if t == 1 or t == 2 or t == 4:
            pt3 = 0
            for u3 in members[kh3]:
                pt3 += int(members[kh3][u3].get(1, 0))
            absent = maxi(0, pt3 - int(hh_heads.get(kh3, 0)))
        _household_sizes(p, c, t, kh3 // NCLASS, kh3 % NCLASS, int(hh_heads.get(kh3, 0)), members[kh3], size_th, absent)


# tiers.gd 2696
def _one_child_each(p, t, ents, kids, hh_heads, members):
    gap = _child_gaps(p)
    dens = _child_dens(p)
    by_band = []
    sup = PArr("i64")
    sup.resize(BANDS)
    for b2 in range(BANDS):
        by_band.append([])
    for j in range(len(ents)):
        if kids[j] > 0:
            by_band[int(ents[j][1])].append(j)
            sup[int(ents[j][1])] += kids[j]
    rows = {}
    keys = list(hh_heads.keys())
    gdsort.sort(keys)
    for kh in keys:
        need = int(hh_heads[kh])
        if need <= 0:
            continue
        mem = members.get(kh, {})
        us = list(mem.keys())
        gdsort.sort(us)
        held = 0
        for u in us:
            r = 1 if t == 2 else 0
            n = int(mem[u].get(r, 0))
            if n <= 0:
                continue
            fem = p.tr_key[int(u) * KEY_STRIDE + 2] == 1
            rk = p.tr_key[int(u) * KEY_STRIDE + 1] * 2 + (0 if fem else 1)
            if rk not in rows:
                rows[rk] = []
            rows[rk].append([kh, n])
            held += n
        if need > held:
            rk2 = (kh // NCLASS) * 2 + 1
            if rk2 not in rows:
                rows[rk2] = []
            rows[rk2].append([kh, need - held])
    rks = list(rows.keys())
    gdsort.sort(rks)
    cols = []
    for b3 in range(BANDS):
        if sup[b3] > 0:
            cols.append(b3)
    if not rks or not cols:
        return
    rr = []
    tot_need = 0
    for rk3 in rks:
        sn = 0
        for e in rows[rk3]:
            sn += int(e[1])
        rr.append(sn)
        tot_need += sn
    cc = []
    tot_sup = 0
    for b4 in cols:
        cc.append(sup[b4])
        tot_sup += sup[b4]
    rr.append(maxi(0, tot_sup - tot_need))
    short = maxi(0, tot_need - tot_sup)
    if short > 0:
        cc.append(short)
    nr = len(rr)
    ncol = len(cc)
    seed = PArr("f64")
    seed.resize(nr * ncol)
    for ri in range(len(rks)):
        m = int(rks[ri]) // 2
        fa = int(rks[ri]) % 2
        for ci in range(len(cols)):
            b5 = int(cols[ci])
            g = m - b5
            if g <= 0 or g >= 13:
                continue
            lo5 = gap[b5 * 4 + fa * 2]
            hi5 = gap[b5 * 4 + fa * 2 + 1]
            d5 = lo5 - g if g < lo5 else (g - hi5 if g > hi5 else 0)
            seed[ri * ncol + ci] = dens[(b5 * 2 + fa) * 13 + g] if d5 == 0 else -float(d5)
        if short > 0:
            seed[ri * ncol + ncol - 1] = 1.0
    for ci2 in range(len(cols)):
        seed[(nr - 1) * ncol + ci2] = 1.0
    _decay_eps(seed)
    x = E.ipf2(seed, rr, cc)
    it = dep_round(x, nr, ncol, p.seed_v, "tier_child_round", c_key(ents) * NTYPE + t)
    tm = p.tr_margins
    for ri2 in range(len(rks)):
        m2 = int(rks[ri2]) // 2
        fa2 = int(rks[ri2]) % 2
        hh = rows[rks[ri2]]
        hi_at = 0
        for ci3 in range(len(cols)):
            n2 = it[ri2 * ncol + ci3]
            b6 = int(cols[ci3])
            g2 = m2 - b6
            inside = g2 >= gap[b6 * 4 + fa2 * 2] and g2 <= gap[b6 * 4 + fa2 * 2 + 1]
            while n2 > 0 and hi_at < len(hh):
                e2 = hh[hi_at]
                take = mini(n2, int(e2[1]))
                left = take
                for j2 in by_band[b6]:
                    if left <= 0:
                        break
                    tk = mini(left, kids[int(j2)])
                    if tk <= 0:
                        continue
                    _member_add(members, int(e2[0]), int(ents[int(j2)][0]), 2, tk)
                    kids[int(j2)] -= tk
                    left -= tk
                e2[1] = int(e2[1]) - take
                n2 -= take
                if int(e2[1]) <= 0:
                    hi_at += 1
                g2k = "gap2_father" if fa2 == 1 else "gap2"
                tm[g2k] = _gap_add(tm.get(g2k, {}), b6, g2, take)
                if fa2 == 0:
                    mc = tm.get("gap2_mc", {})
                    mck = "%d|%d" % (m2, b6)
                    mc[mck] = int(mc.get(mck, 0)) + take
                    tm["gap2_mc"] = mc
                if inside:
                    tm["gap_child"] = _gap_add(tm.get("gap_child", {}), b6, g2, take)
                else:
                    sk = "t%d %s %d-%d" % (t, "father" if fa2 == 1 else "mother", 5 * m2, 5 * m2 + 4)
                    ob = tm.get("hh_outside_by", {})
                    ob[sk] = int(ob.get(sk, 0)) + take
                    tm["hh_outside_by"] = ob
    tm["hh_childless"] = int(tm.get("hh_childless", 0)) + short


# tiers.gd 2829
def _child_dens(p):
    win = _v(p, "child_window")
    out = PArr("f64")
    out.resize(BANDS * 2 * 13)
    for b in range(BANDS):
        y = 2024 - (5 * b + 2)
        best = 0
        bd = 1 << 30
        for i in range(len(win["mother"])):
            d = abs(int(win["mother"][i][0]) - maxi(y, 1950))
            if d < bd:
                bd = d
                best = i
        for fa in range(2):
            rows = win["mother_shares"][best] if fa == 0 else win["father_shares"]
            for r in rows:
                mid = (float(r[0]) + float(r[1])) * 0.5 / 5.0
                g0 = int(math.floor(mid))
                fr = mid - float(g0)
                if g0 >= 0 and g0 < 13:
                    out[(b * 2 + fa) * 13 + g0] += float(r[2]) * (1.0 - fr)
                if g0 + 1 >= 0 and g0 + 1 < 13:
                    out[(b * 2 + fa) * 13 + g0 + 1] += float(r[2]) * fr
    return out


# tiers.gd 2947
def _decay_eps(seed):
    lo = 1e300
    for v in seed:
        if v > 0.0 and v < lo:
            lo = v
    e0 = 1e-6 * (lo if lo < 1e300 else 1.0)
    for i in range(len(seed)):
        if seed[i] < 0.0:
            seed[i] = e0 * DM.pow(0.01, -seed[i] - 1.0)


# tiers.gd 2960
def _no_pair(g, b1, b2):
    return g < 0 or (g == 0 and not (b1 == BANDS - 1 and b2 == BANDS - 1))


# tiers.gd 2965
def c_key(ents):
    return int(ents[0][0]) if ents else 0


# tiers.gd 2970
def _gap_add(d, b, g, n):
    y = 2024 - (5 * b + 2)
    grp = 0 if y < 1970 else (1 if y < 1990 else (2 if y < 2010 else 3))
    k = "%d|%d" % (grp, g)
    d[k] = int(d.get(k, 0)) + n
    return d


# tiers.gd 2979
def _child_gaps(p):
    win = _v(p, "child_window")
    gap = PArr("i64")
    gap.resize(BANDS * 4)
    for b in range(BANDS):
        y = 2024 - (5 * b + 2)
        best = []
        bd = 1 << 30
        for row in win["mother"]:
            d = abs(int(row[0]) - maxi(y, 1950))
            if d < bd:
                bd = d
                best = row
        gap[b * 4] = int(math.floor(float(best[2]) / 5.0))
        gap[b * 4 + 1] = int(math.ceil(float(best[3]) / 5.0))
        gap[b * 4 + 2] = int(math.floor(float(win["father"][0]) / 5.0))
        gap[b * 4 + 3] = int(math.ceil(float(win["father"][1]) / 5.0))
    return gap


# tiers.gd 3009
def _place_nonhead(p, c, ents, nhr, hh_heads, members):
    gap = _child_gaps(p)
    dens = _child_dens(p)
    tm = p.tr_margins
    slots = []
    keys = list(hh_heads.keys())
    gdsort.sort(keys)
    for kh in keys:
        heads = int(hh_heads[kh])
        if heads <= 0:
            continue
        mem = members.get(kh, {})
        us = list(mem.keys())
        gdsort.sort(us)
        wives = 0
        fheads = 0
        for u in us:
            fem = p.tr_key[int(u) * KEY_STRIDE + 2] == 1
            b = p.tr_key[int(u) * KEY_STRIDE + 1]
            nw = int(mem[u].get(1, 0)) if fem else 0
            nf = int(mem[u].get(0, 0)) if fem else 0
            if nw > 0:
                slots.append([b, 0, kh, nw, 0])
                wives += nw
            if nf > 0:
                slots.append([b, 0, kh, nf, 1])
                fheads += nf
        rest = heads - fheads - wives
        if rest > 0:
            slots.append([kh // NCLASS, 1, kh, rest, 1])
    gdsort.sort(slots)
    dem = []
    for key in p.tr_nh_couples:
        k = key.split("|")
        if int(k[0]) == c:
            dem.append([int(k[3]), int(k[2]) + 3, int(k[1]) + 3, int(p.tr_nh_couples[key])])
    for d5 in dem:
        if int(d5[0]) != 1:
            continue
        ok = False
        for sl5 in slots:
            if int(sl5[4]) == 0 and int(sl5[3]) > 0 and not _no_pair(int(d5[1]) - int(sl5[0]), int(d5[1]), int(sl5[0])):
                ok = True
                break
        if ok:
            continue
        nm = int(d5[3])
        for side in ([int(d5[1]), 1], [int(d5[2]), 0]):
            left = nm
            for j5 in range(len(ents)):
                if left <= 0:
                    break
                if int(ents[j5][1]) == int(side[0]) and int(ents[j5][2]) == int(side[1]) and int(nhr[j5][1]) > 0:
                    mv = mini(left, int(nhr[j5][1]))
                    nhr[j5][1] = int(nhr[j5][1]) - mv
                    nhr[j5][0] = int(nhr[j5][0]) + mv
                    left -= mv
        k1 = "%d|%d|%d|1" % (c, int(d5[2]) - 3, int(d5[1]) - 3)
        k0 = "%d|%d|%d|0" % (c, int(d5[2]) - 3, int(d5[1]) - 3)
        p.tr_nh_couples[k1] = int(p.tr_nh_couples[k1]) - nm
        if int(p.tr_nh_couples[k1]) == 0:
            del p.tr_nh_couples[k1]
        p.tr_nh_couples[k0] = int(p.tr_nh_couples.get(k0, 0)) + nm
        d5[0] = 0
        tm["nh_kind_moved"] = int(tm.get("nh_kind_moved", 0)) + nm
    gdsort.sort(dem)

    def pick(d, sl):
        w = int(d[1])
        r = int(sl[0])
        fa = int(sl[1])
        g = r - w if int(d[0]) == 0 else w - r
        cb = w if int(d[0]) == 0 else r
        lo = gap[cb * 4 + fa * 2]
        hi = gap[cb * 4 + fa * 2 + 1]
        return lo - g if g < lo else (g - hi if g > hi else 0)

    placed = []
    nhp = _v(p, "nonhead_couples")["by_pref"][str(c)]
    ccn = 0
    pcn = 0
    for d0 in dem:
        ccn += int(d0[3]) if int(d0[0]) == 0 else 0
        pcn += int(d0[3]) if int(d0[0]) == 1 else 0
    ht = _v(p, "household_target")
    o20 = float(ht["census_2020"][str(c)][4])
    low_s = int(roundf(float(nhp["two_couple_low"]) * float(A._head_targets(p)["%02d|4" % c]) / o20)) if o20 > 0.0 else 0
    cap0 = maxi(0, ccn - maxi(0, low_s - pcn))
    for rnd in range(2):
        groups = {}
        for si in range(len(slots)):
            if int(slots[si][4]) == 1 - rnd and int(slots[si][3]) > 0:
                gk2 = int(slots[si][0]) * 2 + int(slots[si][1])
                if gk2 not in groups:
                    groups[gk2] = []
                groups[gk2].append(si)
        cgr = {}
        for di in range(len(dem)):
            if int(dem[di][3]) > 0 and (rnd == 1 or int(dem[di][0]) == 0):
                ck2 = int(dem[di][0]) * BANDS + int(dem[di][1])
                if ck2 not in cgr:
                    cgr[ck2] = []
                cgr[ck2].append(di)
        cdx = list(cgr.keys())
        gdsort.sort(cdx)
        gks = list(groups.keys())
        gdsort.sort(gks)
        if not gks or not cdx:
            continue
        rr = []
        ss = 0
        for gk3 in gks:
            sn = 0
            for si2 in groups[gk3]:
                sn += int(slots[si2][3])
            rr.append(sn)
            ss += sn
        cc = []
        sd = 0
        for ck3 in cdx:
            cn = 0
            for di2 in cgr[ck3]:
                cn += int(dem[di2][3])
            cc.append(cn)
            sd += cn
        k = mini(ss, sd) if rnd == 1 else mini(cap0, mini(ss, sd))
        rr.append(sd - k)
        cc.append(ss - k)
        nr = len(rr)
        ncol = len(cc)
        seed = PArr("f64")
        seed.resize(nr * ncol)
        for ri in range(len(gks)):
            r2 = int(gks[ri]) // 2
            fa2 = int(gks[ri]) % 2
            probe = [r2, fa2, 0, 0, 0]
            for ci in range(len(cdx)):
                d4 = dem[int(cgr[cdx[ci]][0])]
                w2 = int(d4[1])
                g4 = r2 - w2 if int(d4[0]) == 0 else w2 - r2
                dist = pick(d4, probe)
                if _no_pair(g4, r2, w2):
                    continue
                if g4 <= 0 or g4 >= 13:
                    seed[ri * ncol + ci] = -float(maxi(1, dist))
                    continue
                seed[ri * ncol + ci] = (dens[(w2 * 2 + fa2) * 13 + g4] if int(d4[0]) == 0 else dens[(r2 * 2) * 13 + g4]) if dist == 0 else -float(dist)
            seed[ri * ncol + ncol - 1] = 1.0
        for ci2 in range(len(cdx)):
            seed[(nr - 1) * ncol + ci2] = 1.0
        _decay_eps(seed)
        xt = E.ipf2(seed, rr, cc)
        it = dep_round(xt, nr, ncol, p.seed_v, "tier_nh_round", c * 2 + rnd)
        for ri2 in range(len(gks)):
            sl_list = groups[gks[ri2]]
            at2 = 0
            for ci3 in range(len(cdx)):
                n4 = it[ri2 * ncol + ci3]
                for di3 in cgr[cdx[ci3]]:
                    while n4 > 0 and at2 < len(sl_list) and int(dem[di3][3]) > 0:
                        si3 = int(sl_list[at2])
                        take = mini(n4, mini(int(slots[si3][3]), int(dem[di3][3])))
                        if take > 0:
                            placed.append([di3, si3, take, 0 if pick(dem[di3], slots[si3]) == 0 else 1])
                            slots[si3][3] = int(slots[si3][3]) - take
                            dem[di3][3] = int(dem[di3][3]) - take
                            n4 -= take
                        if int(slots[si3][3]) <= 0:
                            at2 += 1
    for di4 in range(len(dem)):
        if int(dem[di4][3]) > 0:
            tm["nh_unplaced"] = int(tm.get("nh_unplaced", 0)) + int(dem[di4][3])
            uk = tm.get("nh_unplaced_kind", {})
            ukk = "%d|%d" % (int(dem[di4][0]), int(dem[di4][1]))
            uk[ukk] = int(uk.get(ukk, 0)) + int(dem[di4][3])
            tm["nh_unplaced_kind"] = uk
            ub = tm.get("nh_unplaced_by", {})
            ub[c] = int(ub.get(c, 0)) + int(dem[di4][3])
            tm["nh_unplaced_by"] = ub
    gaps = tm.get("nh_gaps", {})
    filled = {}
    for pl in placed:
        d3 = dem[int(pl[0])]
        sl3 = slots[int(pl[1])]
        n3 = int(pl[2])
        kind = int(d3[0])
        g3 = int(sl3[0]) - int(d3[1]) if kind == 0 else int(d3[1]) - int(sl3[0])
        gk = "%s %s%d" % ("child" if kind == 0 else "parent", "out " if int(pl[3]) == 1 else "", g3)
        gaps[gk] = int(gaps.get(gk, 0)) + n3
        if int(pl[3]) == 0:
            tm["gap_nh"] = _gap_add(tm.get("gap_nh", {}), int(d3[1]) if kind == 0 else int(sl3[0]), g3, n3)
        if int(pl[3]) == 1:
            tm["nh_outside"] = int(tm.get("nh_outside", 0)) + n3
        if int(sl3[4]) == 1:
            filled[int(sl3[2])] = int(filled.get(int(sl3[2]), 0)) + n3
        if int(sl3[4]) == 0:
            tm["nh_two_couple"] = int(tm.get("nh_two_couple", 0)) + n3
            tc = tm.get("nh_two_couple_by", {})
            tc[c] = int(tc.get(c, 0)) + n3
            tm["nh_two_couple_by"] = tc
        left = n3
        while left > 0:
            jh = _nh_entry(ents, nhr, int(d3[2]), 0, kind)
            jw = _nh_entry(ents, nhr, int(d3[1]), 1, kind)
            if jh < 0 or jw < 0:
                tm["nh_unplaced"] = int(tm.get("nh_unplaced", 0)) + left
                ub2 = tm.get("nh_unplaced_by", {})
                ub2[c] = int(ub2.get(c, 0)) + left
                tm["nh_unplaced_by"] = ub2
                if int(sl3[4]) == 0:
                    tm["nh_two_couple"] = int(tm.get("nh_two_couple", 0)) - left
                    tc2 = tm.get("nh_two_couple_by", {})
                    tc2[c] = int(tc2.get(c, 0)) - left
                    tm["nh_two_couple_by"] = tc2
                break
            m = mini(left, mini(int(nhr[jh][kind]), int(nhr[jw][kind])))
            kh3 = int(sl3[2])
            _member_add(members, kh3, int(ents[jh][0]), 2 if kind == 0 else 3, m)
            _member_add(members, kh3, int(ents[jw][0]), 2 if kind == 0 else 3, m)
            nhr[jh][kind] = int(nhr[jh][kind]) - m
            nhr[jw][kind] = int(nhr[jw][kind]) - m
            rk = "%02d|%02d|%d" % (c, kh3 // NCLASS, kh3 % NCLASS)
            if rk not in p.tr_nh_hh:
                p.tr_nh_hh[rk] = []
            p.tr_nh_hh[rk].append([int(ents[jh][0]), int(ents[jw][0]), kind, m])
            left -= m
    tm["nh_gaps"] = gaps
    return filled


# tiers.gd 3251
def _one_member_each(p, c, ents, roles, hh_heads, members, filled):
    gap = _child_gaps(p)
    dens = _child_dens(p)
    rows = {}
    keys = list(hh_heads.keys())
    gdsort.sort(keys)
    for kh in keys:
        mem = members.get(kh, {})
        wives = 0
        for u in mem:
            if p.tr_key[int(u) * KEY_STRIDE + 2] == 1:
                wives += int(mem[u].get(1, 0))
        need = int(hh_heads[kh]) - wives - int(filled.get(kh, 0))
        if need <= 0:
            continue
        hb = kh // NCLASS
        if hb not in rows:
            rows[hb] = []
        rows[hb].append([kh, need])
    if not rows:
        return
    cols = []
    csup = []
    for r in (2, 3, 4):
        for b in range(BANDS):
            sn = 0
            for j in range(len(ents)):
                if int(ents[j][1]) == b:
                    sn += roles[j][r]
            if sn > 0:
                cols.append([r, b])
                csup.append(sn)
    if not cols:
        p.tr_margins["t4_unfilled"] = int(p.tr_margins.get("t4_unfilled", 0)) + 1
        return
    hbs = list(rows.keys())
    gdsort.sort(hbs)
    rr = []
    need_t = 0
    for hb2 in hbs:
        sn2 = 0
        for e in rows[hb2]:
            sn2 += int(e[1])
        rr.append(sn2)
        need_t += sn2
    cc = list(csup)
    sup_t = 0
    for x0 in csup:
        sup_t += x0
    rr.append(maxi(0, sup_t - need_t))
    short = maxi(0, need_t - sup_t)
    if short > 0:
        cc.append(short)
    nr = len(rr)
    ncol = len(cc)
    seed = PArr("f64")
    seed.resize(nr * ncol)
    for ri in range(len(hbs)):
        hb3 = int(hbs[ri])
        for ci in range(len(cols)):
            r3 = int(cols[ci][0])
            b3 = int(cols[ci][1])
            v = 0.0
            if r3 == 2 or r3 == 3:
                cb = b3 if r3 == 2 else hb3
                g = hb3 - b3 if r3 == 2 else b3 - hb3
                lo = gap[cb * 4]
                hi = gap[cb * 4 + 1]
                d = lo - g if g < lo else (g - hi if g > hi else 0)
                if _no_pair(g, hb3, b3):
                    v = 0.0
                else:
                    v = dens[(cb * 2) * 13 + g] if d == 0 and g < 13 else -float(maxi(1, d))
            else:
                d4 = abs(b3 - hb3)
                v = 1.0 if d4 <= 2 else -float(d4 - 2)
            seed[ri * ncol + ci] = v
        if short > 0:
            seed[ri * ncol + ncol - 1] = 1.0
    for ci2 in range(len(cols)):
        seed[(nr - 1) * ncol + ci2] = 1.0
    _decay_eps(seed)
    x = E.ipf2(seed, rr, cc)
    it = dep_round(x, nr, ncol, p.seed_v, "tier_t4_round", c)
    for ri2 in range(len(hbs)):
        hh = rows[hbs[ri2]]
        at = 0
        for ci3 in range(len(cols)):
            n = it[ri2 * ncol + ci3]
            r4 = int(cols[ci3][0])
            b4 = int(cols[ci3][1])
            while n > 0 and at < len(hh):
                take = mini(n, int(hh[at][1]))
                left = take
                for j2 in range(len(ents)):
                    if left <= 0:
                        break
                    if int(ents[j2][1]) != b4 or roles[j2][r4] <= 0:
                        continue
                    tk = mini(left, roles[j2][r4])
                    _member_add(members, int(hh[at][0]), int(ents[j2][0]), r4, tk)
                    roles[j2][r4] -= tk
                    left -= tk
                hh[at][1] = int(hh[at][1]) - take
                n -= take
                if int(hh[at][1]) <= 0:
                    at += 1
    p.tr_margins["t4_unfilled"] = int(p.tr_margins.get("t4_unfilled", 0)) + short


# tiers.gd 3362
def _nh_entry(ents, nhr, b, s, kind):
    for j in range(len(ents)):
        if int(ents[j][1]) == b and int(ents[j][2]) == s and int(nhr[j][kind]) > 0:
            return j
    return -1


# tiers.gd 3369
def _member_add(members, kh, u, r, n):
    if n <= 0:
        return
    if kh not in members:
        members[kh] = {}
    m = members[kh]
    if u not in m:
        m[u] = {}
    m[u][r] = int(m[u].get(r, 0)) + n


# tiers.gd 3380
def _nearest_hb(by_hb, want):
    for d in range(BANDS):
        if want - d >= 0 and by_hb[want - d] > 0:
            return want - d
        if want + d < BANDS and by_hb[want + d] > 0:
            return want + d
    return want


# tiers.gd 3390
def _member_by_class(p, members, hh_heads, hb, u, r, m, tag, key):
    v = []
    tot = 0.0
    for k in range(NCLASS):
        v.append(float(hh_heads.get(hb * NCLASS + k, 0)))
        tot += v[k]
    if tot <= 0.0:
        _member_add(members, hb * NCLASS + CLASS_REST, u, r, m)
        return
    for k2 in range(NCLASS):
        v[k2] *= float(m) / tot
    ints = _systematic(v, m, p.seed_v, tag, key)
    for k3 in range(NCLASS):
        _member_add(members, hb * NCLASS + k3, u, r, ints[k3])


# tiers.gd 3433
def _set_heads(p, ents, roles, heads, want, role_tbs, t, key):
    ne = len(ents)
    up = want > heads
    cap = [0] * ne
    v = [0.0] * ne
    tot = 0.0
    cap_tot = 0
    for j in range(ne):
        rc = roles[j]
        sh = role_tbs.get("%d,%d,%d" % (t, int(ents[j][1]), int(ents[j][2])), _ROLE_DEF)
        if up:
            cap[j] = (rc[1] + rc[2] + rc[3] + rc[4]) if int(ents[j][1]) * 5 >= 15 else 0
            v[j] = float(cap[j]) * maxf(0.0, float(sh[0]))
        else:
            cap[j] = rc[0]
            v[j] = float(cap[j])
        tot += v[j]
        cap_tot += cap[j]
    move = mini(abs(want - heads), cap_tot)
    if move <= 0:
        return heads - want
    for j2 in range(ne):
        v[j2] = (v[j2] / tot if tot > 0.0 else float(cap[j2]) / float(maxi(1, cap_tot))) * float(move)
    q = _capped(v, cap, move, p.seed_v, "tier_heads", key)
    for j3 in range(ne):
        if q[j3] <= 0:
            continue
        rc2 = roles[j3]
        sh2 = role_tbs.get("%d,%d,%d" % (t, int(ents[j3][1]), int(ents[j3][2])), _ROLE_DEF)
        if up:
            o = [0.0, float(rc2[1]), float(rc2[2]), float(rc2[3]), float(rc2[4])]
            take = _systematic(o, q[j3], p.seed_v, "tier_heads_take", key * 4096 + j3)
            for r in (1, 2, 3, 4):
                rc2[r] -= take[r]
            rc2[0] += q[j3]
        else:
            o2 = [0.0, maxf(0.0, float(sh2[1])), maxf(0.0, float(sh2[2])), maxf(0.0, float(sh2[3])), maxf(0.0, float(sh2[4]))]
            ot = o2[1] + o2[2] + o2[3] + o2[4]
            if ot <= 0.0:
                o2[4] = 1.0
                ot = 1.0
            for r2 in range(5):
                o2[r2] *= float(q[j3]) / ot
            give = _systematic(o2, q[j3], p.seed_v, "tier_heads_give", key * 4096 + j3)
            for r3 in (1, 2, 3, 4):
                rc2[r3] += give[r3]
            rc2[0] -= q[j3]
        roles[j3] = rc2
    return (heads + (move if up else -move)) - want


# tiers.gd 3487
def _capped(v, cap, total, seed_v, tag, key):
    out = _systematic(v, total, seed_v, tag, key)
    over = 0
    for i in range(len(out)):
        if out[i] > cap[i]:
            over += out[i] - cap[i]
            out[i] = cap[i]
    for i2 in range(len(out)):
        while over > 0 and out[i2] < cap[i2]:
            out[i2] += 1
            over -= 1
    return out


# tiers.gd 3505
def _place_partners(p, ents, roles, by_hb, hh_men, members, key, zfix):
    rows_n = [0] * (BANDS * 2)
    row_ents = {}
    for j in range(len(ents)):
        q = roles[j][1]
        if q <= 0:
            continue
        rb = int(ents[j][1]) * 2 + int(ents[j][2])
        rows_n[rb] += q
        if rb not in row_ents:
            row_ents[rb] = []
        row_ents[rb].append([int(ents[j][0]), q])
    z = zfix
    at_hb = {}
    for rb3 in range(BANDS * 2):
        if rb3 not in row_ents:
            continue
        ent = row_ents[rb3]
        ei = 0
        left = int(ent[0][1])
        for hb3 in range(BANDS):
            cnt = z[rb3 * BANDS + hb3]
            while cnt > 0:
                take = mini(cnt, left)
                if hb3 not in at_hb:
                    at_hb[hb3] = []
                at_hb[hb3].append([int(ent[ei][0]), take])
                cnt -= take
                left -= take
                if left == 0 and ei + 1 < len(ent):
                    ei += 1
                    left = int(ent[ei][1])
    hbs = list(at_hb.keys())
    gdsort.sort(hbs)
    for hb4 in hbs:
        es = at_hb[hb4]
        rws = PArr("i64")
        tot = 0
        for e in es:
            rws.append(int(e[1]))
            tot += int(e[1])
        hk = PArr("f64")
        htot = 0
        for k in range(NCLASS):
            hk.append(float(hh_men.get(hb4 * NCLASS + k, 0)))
            htot += int(hh_men.get(hb4 * NCLASS + k, 0))
        for k2 in range(NCLASS):
            hk[k2] *= float(tot) / float(maxi(1, htot))
        if htot == 0:
            hk[CLASS_REST] = float(tot)
        kcols = _largest(hk, tot)
        spill = 0
        for k5 in range(NCLASS):
            cap = int(hh_men.get(hb4 * NCLASS + k5, 0))
            if htot > 0 and kcols[k5] > cap:
                spill += kcols[k5] - cap
                kcols[k5] = cap
        for k6 in range(NCLASS):
            room = int(hh_men.get(hb4 * NCLASS + k6, 0)) - kcols[k6]
            if spill > 0 and room > 0:
                mv = mini(spill, room)
                kcols[k6] += mv
                spill -= mv
        if spill > 0:
            kcols[CLASS_REST if htot == 0 else _largest_key(hh_men, hb4)] += spill
        x2 = PArr("f64")
        x2.resize(len(es) * NCLASS)
        for q in range(len(es)):
            for k3 in range(NCLASS):
                x2[q * NCLASS + k3] = float(rws[q]) * float(kcols[k3]) / float(maxi(1, tot))
        z2 = E._table_round(p, x2, rws, kcols, len(es), NCLASS, "tier_pcls", key * BANDS + hb4)
        for q2 in range(len(es)):
            for k4 in range(NCLASS):
                _member_add(members, hb4 * NCLASS + k4, int(es[q2][0]), 1, z2[q2 * NCLASS + k4])


# tiers.gd 3587
def _largest_key(hh_men, hb):
    best = CLASS_REST
    most = -1
    for k in range(NCLASS):
        n = int(hh_men.get(hb * NCLASS + k, 0))
        if n > most:
            most = n
            best = k
    return best


# tiers.gd 3619
def _household_sizes(p, c, t, hb, k, H0, mem, size_th, absent=0):
    H = H0 + absent
    persons = absent
    for u in mem:
        for r in mem[u]:
            persons += int(mem[u][r])
    lo = SIZE_MIN[t]
    hi = SIZE_MAX[t]
    sh = size_th.get("%d,%d" % (t, hb), _ROLE_DEF)
    v = [0.0] * 5
    tot = 0.0
    for z in range(lo, hi + 1):
        v[z] = maxf(0.0, float(sh[z]))
        tot += v[z]
    for z2 in range(lo, hi + 1):
        v[z2] = float(H) * (v[z2] / tot if tot > 0.0 else (1.0 if z2 == lo else 0.0))
    hz = _systematic(v, H, p.seed_v, "tier_size", ((c * NTYPE + t) * BANDS + hb) * NCLASS + k)
    cap = [0] * 5
    used = 0
    for z3 in range(5):
        cap[z3] = hz[z3] * (z3 + 1)
        used += cap[z3]
    guard = 0
    while used < persons and guard < 10000000:
        guard += 1
        moved = False
        for z4 in range(lo, hi):
            if hz[z4] > 0:
                hz[z4] -= 1
                hz[z4 + 1] += 1
                used += 1
                moved = True
                break
        if not moved:
            break
    while used > persons:
        moved2 = False
        for z5 in range(hi, lo, -1):
            if hz[z5] > 0:
                hz[z5] -= 1
                hz[z5 - 1] += 1
                used -= 1
                moved2 = True
                break
        if not moved2:
            break
    tm = p.tr_margins
    if used > persons:
        tm["hh_unfilled"] = int(tm["hh_unfilled"]) + (used - persons)
        tm["hh_unfilled_t"][t] = int(tm["hh_unfilled_t"].get(t, 0)) + (used - persons)
    for z6 in range(5):
        cap[z6] = hz[z6] * (z6 + 1)
    cap[4] += maxi(0, persons - used)
    us = list(mem.keys())
    gdsort.sort(us)
    head_cols = PArr("i64", [0] * 5)
    part_cols = PArr("i64", [0] * 5)
    rest_cols = PArr("i64", [0] * 5)
    couple_t = t == 1 or t == 2 or t == 4
    n_part = 0
    for u2 in us:
        n_part += int(mem[u2].get(1, 0)) if couple_t else 0
    for z7 in range(5):
        head_cols[z7] = mini(hz[z7], cap[z7])
    out = {}
    _fill_sizes(p, mem, us, [0], head_cols, out, c, t, hb, k, 0)
    left = n_part
    tr_key = p.tr_key
    for z8 in range(5):
        mh = 0
        oz = out.get(z8, {})
        for u4 in oz:
            if tr_key[int(u4) * KEY_STRIDE + 2] == 0:
                mh += int(out[z8][u4].get(0, 0))
        part_cols[z8] = mini(left, mini(mh, maxi(0, cap[z8] - head_cols[z8])))
        left -= part_cols[z8]
    for z9 in range(4, -1, -1):
        room = maxi(0, cap[z9] - head_cols[z9] - part_cols[z9])
        add = mini(left, room)
        part_cols[z9] += add
        left -= add
    for z10 in range(5):
        rest_cols[z10] = maxi(0, cap[z10] - head_cols[z10] - part_cols[z10])
    _fill_sizes(p, mem, us, [1] if couple_t else [], part_cols, out, c, t, hb, k, 1)
    _fill_sizes(p, mem, us, [1, 2, 3, 4] if not couple_t else [2, 3, 4], rest_cols, out, c, t, hb, k, 2)
    for z9 in range(5):
        if hz[z9] <= 0 and z9 not in out:
            continue
        hk = "%02d|%d|%02d|%d|%d" % (c, t, hb, z9, k)
        p.tr_hh[hk] = {"count": hz[z9], "members": out.get(z9, {})}
        if absent > 0:
            hd9 = 0
            for u9 in out.get(z9, {}):
                hd9 += int(out[z9][u9].get(0, 0))
            p.tr_hh[hk]["cross"] = maxi(0, hz[z9] - hd9)


# tiers.gd 3724
def _fill_sizes(p, mem, us, rset, cols, out, c, t, hb, k, pass_i):
    rk = []
    rows = PArr("i64")
    for u in us:
        for r in rset:
            n = int(mem[u].get(r, 0))
            if n > 0:
                rk.append([u, r])
                rows.append(n)
    if not rk:
        return
    nr = len(rk)
    tot_r = 0
    for q in range(nr):
        tot_r += rows[q]
    tot_c = 0
    for z in range(5):
        tot_c += cols[z]
    cf = cols.duplicate()
    if tot_c != tot_r:
        cf[4] = maxi(0, cf[4] + tot_r - tot_c)
        tot_c = 0
        for z2 in range(5):
            tot_c += cf[z2]
        zi = 0
        while tot_c > tot_r and zi < 5:
            cut = mini(cf[zi], tot_c - tot_r)
            cf[zi] -= cut
            tot_c -= cut
            zi += 1
    x = PArr("f64")
    x.resize(nr * 5)
    rf = PArr("f64")
    rf.resize(nr)
    for q2 in range(nr):
        rf[q2] = float(rows[q2])
        for z3 in range(5):
            x[q2 * 5 + z3] = float(rows[q2]) * float(cf[z3]) / float(maxi(1, tot_r))
    z4 = E._table_round(p, x, rows, cf, nr, 5, "tier_fill%d" % pass_i, ((c * NTYPE + t) * BANDS + hb) * NCLASS + k)
    for q3 in range(nr):
        for z5 in range(5):
            n2 = z4[q3 * 5 + z5]
            if n2 <= 0:
                continue
            if z5 not in out:
                out[z5] = {}
            m = out[z5]
            u2 = rk[q3][0]
            if u2 not in m:
                m[u2] = {}
            m[u2][int(rk[q3][1])] = int(m[u2].get(int(rk[q3][1]), 0)) + n2


# tiers.gd 4280
def _r77_roles(p, c, t, ents, role_tbs, want_h, nhr, lt):
    ne = len(ents)
    hw = [0] * BANDS
    ww = [0] * BANDS
    for key in p.tr_couples:
        k = key.split("|")
        if int(k[0]) != c or int(k[3]) != t:
            continue
        hw[int(k[1]) + 3] += int(p.tr_couples[key])
        ww[int(k[2]) + 3] += int(p.tr_couples[key])
    roles = []
    for j in range(ne):
        roles.append(PArr("i64", [0, 0, 0, 0, 0]))
    cross = [0, 0]
    for b in range(BANDS):
        for s in range(2):
            want = hw[b] if s == 0 else ww[b]
            idx = []
            avail = 0
            for j2 in range(ne):
                if int(ents[j2][1]) == b and int(ents[j2][2]) == s:
                    idx.append(j2)
                    avail += int(ents[j2][4])
            take = mini(want, avail)
            cross[s] += want - take
            if want > take:
                cc = p.tr_margins.get("r77_cross_cells", {})
                cck = "%d|%d|%d" % (c, b, s)
                cc[cck] = int(cc.get(cck, 0)) + want - take
                p.tr_margins["r77_cross_cells"] = cc
            if take <= 0:
                continue
            cap = []
            v = []
            for j3 in idx:
                cap.append(int(ents[j3][4]))
                v.append(float(ents[j3][4]) * float(take) / float(avail))
            q = _capped(v, cap, take, p.seed_v, "tier_r77_role", (c * NTYPE + t) * BANDS * 2 + b * 2 + s)
            for i in range(len(idx)):
                roles[int(idx[i])][s] = q[i]
    rest1 = 0
    if t == 4:
        _r77_nh_roles(p, c, ents, roles, nhr)
        _r77_other_heads(p, c, ents, roles, role_tbs, want_h, nhr)
        _l_children(p, c, ents, roles, nhr, lt)
    for j4 in range(ne):
        rc = roles[j4]
        rest = int(ents[j4][4]) - rc[0] - rc[1] - rc[2] - rc[3] - rc[4] - (int(nhr[j4][0]) + int(nhr[j4][1]) if t == 4 else 0)
        if rest <= 0:
            continue
        if t == 1:
            rc[4] += rest
            rest1 += rest
        elif t == 2:
            rc[2] += rest
        else:
            sh = role_tbs.get("%d,%d,%d" % (t, int(ents[j4][1]), int(ents[j4][2])), _ROLE_DEF)
            v2 = [0.0, 0.0, 0.0 if t == 4 else maxf(0.0, float(sh[2])), maxf(0.0, float(sh[3])), maxf(0.0, float(sh[4]))]
            if v2[2] + v2[3] + v2[4] <= 0.0:
                v2[4] = 1.0
            vt = v2[2] + v2[3] + v2[4]
            for r in range(5):
                v2[r] *= float(rest) / vt
            add = _systematic(v2, rest, p.seed_v, "tier_r77_rest", int(ents[j4][5]))
            for r2 in range(5):
                rc[r2] += add[r2]
        roles[j4] = rc
    tm = p.tr_margins
    tm["r77_cross_husband"] = int(tm.get("r77_cross_husband", 0)) + cross[0]
    tm["r77_cross_wife"] = int(tm.get("r77_cross_wife", 0)) + cross[1]
    tm["r77_type1_rest"] = int(tm.get("r77_type1_rest", 0)) + rest1
    return roles


# tiers.gd 4360
def _parent_window(p, by_hb, members, hh_heads, ent, m, dens):
    pb = int(ent[1])
    w = [0.0] * BANDS
    lo = 1e300
    for hb in range(BANDS):
        g = pb - hb
        if by_hb[hb] > 0 and g >= 1 and g <= 12 and dens[(hb * 2) * 13 + g] > 0.0:
            w[hb] = float(by_hb[hb]) * dens[(hb * 2) * 13 + g]
            lo = minf(lo, dens[(hb * 2) * 13 + g])
    e0 = 1e-6 * (lo if lo < 1e300 else 1.0)
    for hb2 in range(BANDS):
        if by_hb[hb2] <= 0 or w[hb2] > 0.0 or _no_pair(pb - hb2, pb, hb2):
            continue
        d = 13
        for hb3 in range(BANDS):
            g3 = pb - hb3
            if g3 >= 1 and g3 <= 12 and dens[(hb3 * 2) * 13 + g3] > 0.0:
                d = mini(d, abs(hb3 - hb2))
        w[hb2] = float(by_hb[hb2]) * e0 * DM.pow(0.01, float(maxi(1, d)) - 1.0)
    tot = 0.0
    for x in w:
        tot += x
    if tot <= 0.0:
        hb0 = _nearest_hb(by_hb, pb)
        _member_by_class(p, members, hh_heads, hb0, int(ent[0]), 4, m, "tier_mem", int(ent[5]) * 8 + 3)
        p.tr_margins["parent_none"] = int(p.tr_margins.get("parent_none", 0)) + m
        return
    for hb4 in range(BANDS):
        w[hb4] *= float(m) / tot
    ints = _systematic(w, m, p.seed_v, "tier_parent", int(ent[5]))
    for hb5 in range(BANDS):
        if ints[hb5] > 0:
            _member_by_class(p, members, hh_heads, hb5, int(ent[0]), 3, ints[hb5], "tier_mem", int(ent[5]) * 8 + 3)
            gk = "%d|%d" % (pb, hb5)
            pw = p.tr_margins.get("parent_window", {})
            pw[gk] = int(pw.get(gk, 0)) + ints[hb5]
            p.tr_margins["parent_window"] = pw


# tiers.gd 4407
def _l_other(p, kind=1):
    cr = _v(p, "child_role")["by_pref"]
    out = {}
    for key in cr:
        if key == "0":
            continue
        for s in range(2):
            for b in range(BANDS):
                e = cr[key]["m" if s == 0 else "f"][b]
                den = float(e[4]) if kind == 1 else float(e[3])
                num = float(int(e[0]) - int(e[1])) if kind == 1 else float(e[1])
                out["%d|%d|%d" % (int(key), b, s)] = num / den if den > 0.0 else 0.0
    return out


# tiers.gd 4425
def _l_children(p, c, ents, roles, nhr, lt):
    clip = p.tr_margins["lc_clip"]
    for b in range(BANDS):
        for s in range(2):
            persons = 0
            for j0 in range(len(ents)):
                if int(ents[j0][1]) == b and int(ents[j0][2]) == s:
                    persons += int(ents[j0][4])
            want = int(roundf(float(lt.get("%d|%d|%d" % (c, b, s), 0.0)) * float(persons)))
            if want <= 0:
                continue
            idx = []
            cap = []
            v = []
            room = 0
            for j in range(len(ents)):
                if int(ents[j][1]) == b and int(ents[j][2]) == s:
                    rc = roles[j]
                    r = maxi(0, int(ents[j][4]) - rc[0] - rc[1] - rc[2] - rc[3] - rc[4] - int(nhr[j][0]) - int(nhr[j][1]))
                    idx.append(j)
                    cap.append(r)
                    room += r
            take = mini(want, room)
            if take < want:
                ck = "%d|%d" % (b, s)
                clip[ck] = int(clip.get(ck, 0)) + want - take
            if take <= 0:
                continue
            for q in range(len(idx)):
                v.append(float(cap[q]) * float(take) / float(room))
            ints = _capped(v, cap, take, p.seed_v, "tier_lchild", (c * BANDS + b) * 2 + s)
            for q2 in range(len(idx)):
                rc2 = roles[int(idx[q2])]
                rc2[2] += ints[q2]
                roles[int(idx[q2])] = rc2


# tiers.gd 4463
def _r77_z(p, c, t, ents, roles):
    z = PArr("i64")
    z.resize(BANDS * 2 * BANDS)
    for key in p.tr_couples:
        k = key.split("|")
        if int(k[0]) != c or int(k[3]) != t:
            continue
        z[((int(k[2]) + 3) * 2 + 1) * BANDS + int(k[1]) + 3] += int(p.tr_couples[key])
    have = [0] * (BANDS * 2)
    for j in range(len(ents)):
        have[int(ents[j][1]) * 2 + int(ents[j][2])] += roles[j][1]
    for rb in range(BANDS * 2):
        row = PArr("f64")
        rt = 0
        for hb in range(BANDS):
            row.append(float(z[rb * BANDS + hb]))
            rt += z[rb * BANDS + hb]
        if rt == have[rb]:
            continue
        cut = _largest(row, have[rb]) if rt > 0 else PArr("i64")
        for hb2 in range(BANDS):
            z[rb * BANDS + hb2] = cut[hb2] if rt > 0 else 0
    return z


# tiers.gd 4493
def _r77_nh_roles(p, c, ents, roles, nhr):
    want = [0] * (BANDS * 2 * 2)
    for key in p.tr_nh_couples:
        k = key.split("|")
        if int(k[0]) != c:
            continue
        n = int(p.tr_nh_couples[key])
        kind = int(k[3])
        want[((int(k[1]) + 3) * 2) * 2 + kind] += n
        want[((int(k[2]) + 3) * 2 + 1) * 2 + kind] += n
    for bs in range(BANDS * 2):
        for kind2 in range(2):
            w = want[bs * 2 + kind2]
            if w <= 0:
                continue
            idx = []
            cap = []
            v = []
            avail = 0
            for j in range(len(ents)):
                if int(ents[j][1]) * 2 + int(ents[j][2]) == bs:
                    room = maxi(0, int(ents[j][4]) - roles[j][0] - roles[j][1] - int(nhr[j][0]) - int(nhr[j][1]))
                    idx.append(j)
                    cap.append(room)
                    avail += room
            take = mini(w, avail)
            if take < w:
                p.tr_margins["nh_short"] = int(p.tr_margins.get("nh_short", 0)) + w - take
            if take <= 0:
                continue
            for q in range(len(idx)):
                v.append(float(cap[q]) * float(take) / float(avail))
            ints = _capped(v, cap, take, p.seed_v, "tier_nh_role", (c * BANDS * 2 + bs) * 2 + kind2)
            for q2 in range(len(idx)):
                nhr[int(idx[q2])][kind2] = int(nhr[int(idx[q2])][kind2]) + ints[q2]


# tiers.gd 4534
def _r77_other_heads(p, c, ents, roles, role_tbs, want_h, nhr):
    ch = 0
    cap = []
    v = []
    avail = 0
    for j in range(len(ents)):
        ch += roles[j][0]
        rest = maxi(0, int(ents[j][4]) - roles[j][0] - roles[j][1] - int(nhr[j][0]) - int(nhr[j][1]))
        sh = role_tbs.get("4,%d,%d" % (int(ents[j][1]), int(ents[j][2])), _ROLE_DEF)
        cap.append(rest if int(ents[j][1]) * 5 >= ADULT_FROM else 0)
        v.append(float(cap[j]) * maxf(0.0, float(sh[0])))
        avail += cap[j]
    want = mini(avail, maxi(0, want_h - ch)) if want_h >= 0 else 0
    vt = 0.0
    for x in v:
        vt += x
    if want <= 0:
        return
    for j2 in range(len(v)):
        v[j2] = v[j2] * float(want) / vt if vt > 0.0 else float(cap[j2]) * float(want) / float(maxi(1, avail))
    q = _capped(v, cap, want, p.seed_v, "tier_r77_heads", c)
    for j3 in range(len(ents)):
        roles[j3][0] += q[j3]


# tiers.gd 5098
def birth_months(p, j, age, m):
    bm = _v(p, "birth_month_shares")
    y = maxi(1947, 2023 - age)
    best = 0
    bd = 1 << 30
    for i in range(len(bm["years"])):
        d = abs(int(bm["years"][i]) - y)
        if d < bd:
            bd = d
            best = i
    sh = bm["shares"][best]
    out = PArr("i64")
    out.resize(12)
    left = m
    rows = []
    o = keyed.below(12, p.seed_v, "t21_birth_month", j, age, 0)
    for k in range(12):
        x = float(m) * float(sh[k])
        out[k] = int(math.floor(x))
        left -= out[k]
        rows.append([-(x - float(out[k])), (k - o + 12) % 12, k])
    gdsort.sort(rows)
    for r in range(left):
        out[int(rows[r % 12][2])] += 1
    return out
