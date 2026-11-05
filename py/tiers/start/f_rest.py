# Group F of the tiers start (tiers.gd at cd165891): the never-married and married-apart shares, the transfers and the instruments
import math

from core import detmath as DM
from core import gdsort, keyed
from core.gd import clampf, clampi, idiv, imod, maxf, minf, mini, roundf
from tiers.start import tconst as T
from tiers.start.common import _v
from tiers.start.p import PArr

BANDS = T.BANDS
KEY_STRIDE = T.KEY_STRIDE
AGE_SLOTS = T.AGE_SLOTS
ADULT_FROM = T.ADULT_FROM
NEMP = T.NEMP
NTYPE = T.NTYPE
CLASS_NONE = T.CLASS_NONE


def _fdiv(a, b):
    # Why not a / b: GDScript's float division by zero gives inf or nan, where Python raises
    if b == 0.0:
        if a == 0.0 or a != a:
            return math.nan
        return math.copysign(math.inf, a) * math.copysign(1.0, b)
    return a / b


# tiers.gd 419
def _never_married(p):
    cm = _v(p, "coresident_marital")
    nu = PArr("f64")
    nu.resize(BANDS * 2)
    for bs in range(BANDS * 2):
        b = idiv(bs, 2)
        if b < 3:
            nu[bs] = 1.0
            continue
        rows = cm["men" if imod(bs, 2) == 0 else "women"][mini(b - 3, 14)]
        nv = float(rows[0][0]) + float(rows[0][1])
        other = float(rows[2][0]) + float(rows[2][1]) + float(rows[3][0]) + float(rows[3][1])
        nu[bs] = nv / (nv + other) if nv + other > 0.0 else 1.0
    married_child = PArr("f64")
    married_child.resize(p.tr_units)
    for rk in p.tr_nh_hh:
        for rec in p.tr_nh_hh[rk]:
            if int(rec[2]) == 0:
                married_child[int(rec[0])] += float(rec[3])
                married_child[int(rec[1])] += float(rec[3])
    fixed = PArr("f64")
    fixed.resize(p.tr_units)
    free = PArr("f64")
    free.resize(p.tr_units)
    for hk in p.tr_hh:
        t = int(hk.split("|")[1])
        mem = p.tr_hh[hk]["members"]
        for u in mem:
            bs2 = p.tr_key[int(u) * KEY_STRIDE + 1] * 2 + p.tr_key[int(u) * KEY_STRIDE + 2]
            for r in mem[u]:
                x = float(mem[u][r])
                if int(r) == 2:
                    mc = minf(x, married_child[int(u)])
                    married_child[int(u)] -= mc
                    fixed[int(u)] += (x - mc) * nu[bs2]
                    continue
                f = _role_never_married(t, int(r))
                if f < 0.0:
                    free[int(u)] += x
                else:
                    fixed[int(u)] += x * f
    cells = {}
    for u2 in range(p.tr_units):
        b2 = p.tr_key[u2 * KEY_STRIDE + 1]
        if b2 < 3:
            continue
        c = p.tr_key[u2 * KEY_STRIDE]
        s = p.tr_key[u2 * KEY_STRIDE + 2]
        ck = "%d|%d|%d" % (c, b2, s)
        if ck not in cells:
            cells[ck] = [0.0, 0.0, 0.0, 0.0]
        e = cells[ck]
        e[0] = float(e[0]) + float(p.tr_count[u2])
        e[2] = float(e[2]) + fixed[u2]
        e[3] = float(e[3]) + free[u2]
    persons = {}
    for ck0 in cells:
        persons[ck0] = float(cells[ck0][0])
    m21 = _marital_cells(p, persons)
    for ck1 in cells:
        cells[ck1][1] = float(m21[ck1][3])
    share = {}
    p.tr_margins["nm"] = []
    keys = list(cells.keys())
    gdsort.sort(keys)
    for ck2 in keys:
        e2 = cells[ck2]
        sh = clampf((float(e2[1]) - float(e2[2])) / float(e2[3]), 0.0, 1.0) if float(e2[3]) > 0.0 else 1.0
        share[ck2] = sh
        kk = ck2.split("|")
        p.tr_margins["nm"].append([int(kk[0]), int(kk[1]), int(kk[2]), _fdiv(float(e2[1]), float(e2[0])), sh,
                                   _fdiv(float(e2[2]) + sh * float(e2[3]) - float(e2[1]), float(e2[0]))])
    p.tr_never_married = PArr("f64")
    p.tr_never_married.resize(p.tr_units)
    for u3 in range(p.tr_units):
        b3 = p.tr_key[u3 * KEY_STRIDE + 1]
        if b3 < 3 or p.tr_count[u3] <= 0:
            p.tr_never_married[u3] = 1.0
            continue
        ck3 = "%d|%d|%d" % (p.tr_key[u3 * KEY_STRIDE], b3, p.tr_key[u3 * KEY_STRIDE + 2])
        p.tr_never_married[u3] = minf(1.0, (fixed[u3] + float(share.get(ck3, 1.0)) * free[u3]) / float(p.tr_count[u3]))


# tiers.gd 507
def _married_apart(p):
    mar = _v(p, "marital_by_pref_sex_band")["by_pref"]
    pop20 = _v(p, "population_2020_by_pref_sex_band")["by_pref"]
    cba = _v(p, "couples_by_age")["by_pref"]
    cells = {}
    for u in range(p.tr_units):
        b = p.tr_key[u * KEY_STRIDE + 1]
        if b * 5 < 15:
            continue
        c = p.tr_key[u * KEY_STRIDE]
        sx = p.tr_key[u * KEY_STRIDE + 2]
        ck = "%d|%d|%d" % (c, b, sx)
        if ck not in cells:
            cells[ck] = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
        row = mar[str(c)][sx]
        e = cells[ck]
        e[0] = float(e[0]) + float(p.tr_count[u])
        e[2] = float(e[2]) + p.tr_never_married[u] * float(p.tr_count[u])
        for y in range(AGE_SLOTS):
            n = p.tr_age_counts[u * AGE_SLOTS + y]
            if n == 0:
                continue
            mb = mini(idiv(b * 5 + y - 15, 5), len(row) - 1)
            e[1] = float(e[1]) + float(n) * float(row[mb][1])
            if b == BANDS - 1:
                e[3 + mini(idiv(y, 5), 3)] = float(e[3 + mini(idiv(y, 5), 3)]) + float(n)
    m21 = p.tr_margins["m21"]
    ma = {}
    nat = PArr("f64")
    nat.resize(BANDS * 2 * 4)
    over1 = 0
    keys = list(cells.keys())
    gdsort.sort(keys)
    for ck2 in keys:
        e2 = cells[ck2]
        kk = ck2.split("|")
        b2 = int(kk[1])
        s2 = int(kk[2])
        x = float(m21[ck2][1]) - float(m21[ck2][2]) if ck2 in m21 else 0.0
        e2[1] = float(m21[ck2][1]) if ck2 in m21 else 0.0
        ma[ck2] = x
        if b2 * 5 >= ADULT_FROM and float(e2[1]) + float(e2[2]) > float(e2[0]) + 1e-6:
            over1 += 1
        row2 = mar[kk[0]][s2]
        n20 = float(pop20[kk[0]][s2][b2 - 3])
        m20 = n20 * float(row2[b2 - 3][1])
        if b2 == BANDS - 1:
            wt = float(e2[3]) + float(e2[4]) + float(e2[5]) + float(e2[6])
            m20 = 0.0
            for j in range(4):
                m20 += n20 * (float(e2[3 + j]) / wt if wt > 0.0 else 0.25) * float(row2[mini(b2 - 3 + j, len(row2) - 1)][1])
        c20 = 0.0
        tab = cba[kk[0]]
        for o in range(len(tab)):
            c20 += float(tab[b2 - 3][o]) if s2 == 0 else float(tab[o][b2 - 3])
        at = (b2 * 2 + s2) * 4
        nat[at] += x
        nat[at + 1] += float(e2[1])
        nat[at + 2] += m20 - c20
        nat[at + 3] += m20
    p.tr_married_apart = PArr("f64")
    p.tr_married_apart.resize(p.tr_units)
    for u2 in range(p.tr_units):
        ck3 = "%d|%d|%d" % (p.tr_key[u2 * KEY_STRIDE], p.tr_key[u2 * KEY_STRIDE + 1], p.tr_key[u2 * KEY_STRIDE + 2])
        if ck3 in ma and float(cells[ck3][0]) > 0.0:
            p.tr_married_apart[u2] = float(ma[ck3]) / float(cells[ck3][0])
    p.tr_margins["ma"] = {"cells": ma, "national": nat, "over1": over1}


# tiers.gd 578
def _couple_cells(p):
    cpc = {}
    for src in (p.tr_couples, p.tr_nh_couples):
        for key in src:
            k = key.split("|")
            n2 = float(src[key])
            cpc["%s|%d|0" % (k[0], int(k[1]) + 3)] = float(cpc.get("%s|%d|0" % (k[0], int(k[1]) + 3), 0.0)) + n2
            cpc["%s|%d|1" % (k[0], int(k[2]) + 3)] = float(cpc.get("%s|%d|1" % (k[0], int(k[2]) + 3), 0.0)) + n2
    cross = p.tr_margins.get("r77_cross_cells", {})
    for ck0 in cross:
        cpc[ck0] = float(cpc.get(ck0, 0.0)) - float(cross[ck0])
    return cpc


# tiers.gd 598
def _marital_cells(p, persons):
    m24 = _v(p, "marital_2024")["by_pref"]
    imm = _v(p, "immigration_2020_2023")
    cpc = _couple_cells(p)
    out = {}
    for ck in persons:
        kk = ck.split("|")
        b = int(kk[1])
        row = m24[kk[0]][int(kk[2])][mini(b - 3, 14)]
        n = float(persons[ck])
        c = maxf(0.0, float(cpc.get(ck, 0.0)))
        mar = minf(n, c * (1.0 + float(row[1])))
        w = float(row[3])
        d = float(row[4])
        nv = maxf(0.0, n - mar - w - d) if float(row[2]) < 0.0 else float(row[2])
        res = n - mar - nv - w - d
        sx = int(kk[2])
        iv = minf(maxf(0.0, float(imm["by_pref"][kk[0]][sx][mini(b - 3, 14)])), maxf(0.0, res))
        ish = imm["marital_shares"][sx][mini(b - 3, 14)]
        res2 = res - iv
        nonm = nv + w + d
        short = 0.0
        if nonm > 0.0:
            f = maxf(0.0, 1.0 + res2 / nonm)
            short = maxf(0.0, -(res2 + nonm))
            nv *= f
            w *= f
            d *= f
        else:
            nv = maxf(0.0, res2)
        out[ck] = [n, mar + iv * float(ish[1]), c, nv + iv * float(ish[0]), w + iv * float(ish[2]), d + iv * float(ish[3]), res,
                   short, iv]
    p.tr_margins["m21"] = out
    return out


# tiers.gd 634
def _role_never_married(t, r):
    if r == 2:
        return 1.0
    if r == 1 or r == 3:
        return 0.0
    if r == 0 and (t == 1 or t == 2):
        return 0.0
    if r == 0 and t == 3:
        return 0.1
    return -1.0


# tiers.gd 2455
def _transfers(p):
    inc = p.tr_points["income"]
    qi = p.tr_points["q_income"]
    ages = p.tr_points["age"]
    sexes = p.tr_points["sex"]
    pen = p.tr_points["pension_own"]
    kind = p.tr_points["pension_kind"]
    n_pts = p.tr_pt_code.size()
    med = DM.exp(float(p.tr_margins["tail_lines"][0]))
    sv = _v(p, "survivors")
    surv = PArr("f64")
    surv.resize(n_pts)
    elig = PArr("f64", [0.0, 0.0, 0.0, 0.0])
    recip = PArr("f64", [0.0, 0.0, 0.0, 0.0])
    ok = PArr("u8")
    ok.resize(n_pts)
    for g in range(n_pts):
        if sexes[g] == p.MALE or ages[g] < p.PENSION_AGE:
            continue
        bi = clampi(idiv(ages[g] - p.PENSION_AGE, 5), 0, 3)
        if kind[g] != T.PEN_NONE:
            recip[bi] += float(p.tr_pt_mass[g])
        t = imod(idiv(p.tr_pt_code[g], NEMP), NTYPE)
        k = idiv(p.tr_pt_code[g], NTYPE * NEMP)
        if t != 1 and t != 2 and k == CLASS_NONE - 1 and (kind[g] == T.PEN_BASIC or kind[g] == T.PEN_BASIC_SHORT or kind[g] == T.PEN_EMPLOYEE_SHORT):
            ok[g] = 1
            elig[bi] += float(p.tr_pt_mass[g])
    q = PArr("f64", [0.0, 0.0, 0.0, 0.0])
    want = PArr("f64", [0.0, 0.0, 0.0, 0.0])
    for bi2 in range(4):
        want[bi2] = maxf(0.0, float(sv["right_holders"][bi2]) * float(sv["recipient_ratio"]) - recip[bi2] * float(sv["women_kosei_only_share"][bi2]))
        q[bi2] = clampf(want[bi2] / elig[bi2], 0.0, 1.0) if elig[bi2] > 0.0 else 0.0
    drawn = PArr("f64", [0.0, 0.0, 0.0, 0.0])
    skipped = 0.0
    for g2 in range(n_pts):
        if ok[g2] == 0:
            continue
        bi3 = clampi(idiv(ages[g2] - p.PENSION_AGE, 5), 0, 3)
        if keyed.u(p.seed_v, "tier_surv", g2, 0, 0) >= q[bi3]:
            continue
        idx = p.pension_index_at(ages[g2])
        amt = float(sv["mean_yen"]) / 1e4 * idx
        if inc[g2] + amt >= med:
            skipped += float(p.tr_pt_mass[g2])
            continue
        surv[g2] = amt / idx
        pen[g2] += amt / idx
        inc[g2] += amt
        qi[g2] = inc[g2]
        drawn[bi3] += float(p.tr_pt_mass[g2])
    p.tr_points["survivor"] = surv
    pr = _v(p, "protection")
    floor_m = float(pr["minimum_yen"]) / 1e4
    cand = []
    for g3 in range(n_pts):
        if ages[g3] >= p.PENSION_AGE and imod(idiv(p.tr_pt_code[g3], NEMP), NTYPE) == 0 and inc[g3] < floor_m:
            cand.append([inc[g3], g3])
    gdsort.sort_custom(cand, lambda x, y: float(x[0]) < float(y[0]) if float(x[0]) != float(y[0]) else int(x[1]) < int(y[1]))
    prot = PArr("f64")
    prot.resize(n_pts)
    taken = 0.0
    for c in cand:
        if taken >= float(pr["elderly_households"]):
            break
        g4 = int(c[1])
        prot[g4] = floor_m - inc[g4]
        inc[g4] = floor_m
        qi[g4] = inc[g4]
        taken += float(p.tr_pt_mass[g4])
    p.tr_points["protection"] = prot
    p.tr_margins["survivors"] = {"want": want, "drawn": drawn, "skipped": skipped}
    p.tr_margins["protection"] = {"want": float(pr["elderly_households"]), "taken": taken, "below": len(cand)}


# tiers.gd 3786
def _instruments(p):
    ins = _v(p, "instruments_hh_trillion_yen")
    prof = _v(p, "instrument_age_profiles")
    n_pts = p.tr_pt_off[p.tr_units]
    n_all = n_pts + p.n
    inc = p.tr_points["income"]
    ages = p.tr_points["age"]
    mass = PArr("f64")
    mass.resize(n_all)
    income = PArr("f64")
    income.resize(n_all)
    grp = PArr("i32")
    grp.resize(n_all)
    g_inc = PArr("f64")
    g_inc.resize(7)
    g_n = PArr("f64")
    g_n.resize(7)
    for g in range(n_all):
        a = ages[g] if g < n_pts else p.age[g - n_pts]
        grp[g] = clampi(idiv(a, 10) - 2, 0, 6) if a >= ADULT_FROM else -1
        if grp[g] < 0:
            continue
        mass[g] = float(p.tr_pt_mass[g]) if g < n_pts else 1.0
        income[g] = float(inc[g] if g < n_pts else p.income[g - n_pts])
        g_inc[grp[g]] += income[g] * mass[g]
        g_n[grp[g]] += mass[g]
    p.tr_instruments = {}
    p.tr_instrument_factor = {}
    names = list(ins.keys())
    gdsort.sort(names)
    for name in names:
        if name == "net_worth":
            continue
        curve = prof[str(prof["by_instrument"][name])]
        w = PArr("f64")
        w.resize(n_all)
        tot = 0.0
        for g2 in range(n_all):
            if grp[g2] < 0 or g_inc[grp[g2]] <= 0.0:
                continue
            w[g2] = mass[g2] * float(curve[grp[g2]]) * income[g2] / (g_inc[grp[g2]] / g_n[grp[g2]])
            tot += w[g2]
        total_yen = int(roundf(float(ins[name]) * 10.0)) * 100000000000
        p.tr_instruments[name] = _keyed_largest(w, tot, total_yen, p.seed_v, "tier_ins_" + name)
        p.tr_instrument_factor[name] = tot
    _wealth_from_instruments(p, prof, n_pts)


# tiers.gd 3840
def _wealth_from_instruments(p, prof, n_pts):
    by = prof["by_instrument"]
    fin = []
    for name in p.tr_instruments:
        if str(by.get(name, "")) == "financial":
            fin.append(name)
    gdsort.sort(fin)
    assets = p.tr_points["assets"]
    debt = p.tr_points["debt"]
    bor = p.tr_instruments["borrowing"]
    for g in range(n_pts):
        a = 0
        for name2 in fin:
            a += p.tr_instruments[name2][g]
        m = float(p.tr_pt_mass[g])
        assets[g] = float(a) / m / 1e4 if m > 0.0 else 0.0
        debt[g] = float(bor[g]) / m / 1e4 if m > 0.0 else 0.0
    for i in range(p.n):
        a2 = 0
        for name3 in fin:
            a2 += p.tr_instruments[name3][n_pts + i]
        p.tier_wealth(i, float(a2) / 1e4, float(bor[n_pts + i]) / 1e4)


# tiers.gd 3866
def _keyed_largest(w, tot, total, seed_v, tag):
    out = PArr("i64")
    out.resize(w.size())
    fr = []
    used = 0
    hd = keyed.head(seed_v, tag)
    for i in range(w.size()):
        if w[i] <= 0.0:
            continue
        x = float(total) * (w[i] / tot)
        out[i] = int(math.floor(x))
        used += out[i]
        fr.append([x - float(math.floor(x)), keyed.h64(hd, i, 0, 0) >> 11, i])
    gdsort.sort_custom(fr, lambda a, b: float(a[0]) > float(b[0]) if a[0] != b[0] else int(a[1]) < int(b[1]))
    left = total - used
    q = 0
    while left > 0 and fr:
        out[int(fr[q % len(fr)][2])] += 1
        left -= 1
        q += 1
    while left < 0 and fr:
        i2 = int(fr[len(fr) - 1 - (q % len(fr))][2])
        if out[i2] > 0:
            out[i2] -= 1
            left += 1
        q += 1
    return out


def st13_transfers(p, ctx):
    _transfers(p)


def st15_never_married(p, ctx):
    _never_married(p)


def st16_married_apart(p, ctx):
    _married_apart(p)


def st17_instruments(p, ctx):
    _instruments(p)
