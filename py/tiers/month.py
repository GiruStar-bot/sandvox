# The tiers' T2.2 month: the twin of sim/modern/people/tiers.gd's step and everything under it, with life_course.gd's rate functions,
# in the oracle's names, loops and operation order (PY_TRIAL_PLAN §1, §2). The state is a St of Python lists during the month.
import math
from array import array

import numpy as np

from core import detmath, keyed, prims
from core.gd import idiv, maxi, mini, maxf, minf, clampi, clampf
from core.digest import Packed, PackedStr

BANDS = 18
NTYPE = 6
NEMP = 6
CLASS_NONE = 6
EMP_KEY_UNTIL_BAND = 14
CLASS_REST = 4
ADULT_FROM = 20
KEY_STRIDE = 6
AGE_SLOTS = 16
NG = 5
NK = 2
NS = NG * NK
AGES = 101
MALE = 0
EMP_REGULAR = 1
EMP_NONREGULAR = 2
INF = float("inf")

binomial = prims.binomial
hypergeometric = prims.hypergeometric
hypergeometric_split = prims.hypergeometric_split
largest_keyed = prims.largest_keyed
split_holds = prims.split_holds
cap_to = prims.cap_to


class St:
    # The tiers' state: each packed array as a Python list, its Godot kind in kinds (for the digest and the packing back)
    def __init__(self, tree):
        # Why each field is popped from tree as it is converted: holding the NumPy copies beside the lists doubles the peak memory
        self.kinds = {}
        self.pt_kinds = {}
        self.extra = {}
        for k in list(tree.keys()):
            v = tree.pop(k)
            if k == "tr_points":
                self.tr_points = {}
                for n in list(v.keys()):
                    arr = v.pop(n)
                    self.tr_points[n] = arr.a if isinstance(arr.a, array) else array(TYPECODE[arr.kind], _as_list(arr.a))
                    self.pt_kinds[n] = arr.kind
            elif k == "tr_instruments":
                self.tr_instruments = {}
                for n in list(v.keys()):
                    self.tr_instruments[n] = _as_list(v.pop(n).a)
            elif isinstance(v, Packed):
                setattr(self, k, _as_list(v.a))
                self.kinds[k] = v.kind
            elif k == "tr_pt_rem":
                self.tr_pt_rem = {rk: _as_list(rv.a) for rk, rv in v.items()}
            else:
                setattr(self, k, v)
            del v
        self.tr_margins = {}

    def field(self, k):
        # One tr_* field in the digest's form, built alone (the digest takes them one at a time)
        if k in self.kinds:
            return Packed(self.kinds[k], np.array(getattr(self, k), dtype=_np(self.kinds[k])))
        if k == "tr_points":
            return {n: Packed(self.pt_kinds[n], np.array(v, dtype=_np(self.pt_kinds[n]))) for n, v in self.tr_points.items()}
        if k == "tr_instruments":
            return {n: Packed("i64", np.array(v, dtype=np.int64)) for n, v in self.tr_instruments.items()}
        if k == "tr_pt_rem":
            return {rk: Packed("i64", np.array(rv, dtype=np.int64)) for rk, rv in self.tr_pt_rem.items()}
        return getattr(self, k)

    def fields(self):
        return sorted(k for k in self.__dict__ if k.startswith("tr_") and k != "tr_margins")

    def tree(self):
        out = {}
        for k in self.kinds:
            out[k] = Packed(self.kinds[k], np.array(getattr(self, k), dtype=_np(self.kinds[k])))
        out["tr_points"] = {n: Packed(self.pt_kinds[n], np.array(v, dtype=_np(self.pt_kinds[n]))) for n, v in self.tr_points.items()}
        out["tr_instruments"] = {n: Packed("i64", np.array(v, dtype=np.int64)) for n, v in self.tr_instruments.items()}
        out["tr_pt_rem"] = {rk: Packed("i64", np.array(rv, dtype=np.int64)) for rk, rv in self.tr_pt_rem.items()}
        for k, v in self.__dict__.items():
            if k.startswith("tr_") and k not in out and k != "tr_margins":
                out[k] = v
        return out


# Why typed arrays for tr_points and not lists: its fields are floats, and a list of floats holds a 24-byte object per value (598 MB
# of the S0's 2.2 GB); 'f' also rounds a write to float32 as Godot's PackedFloat32Array does
TYPECODE = {"i64": "q", "i32": "i", "f64": "d", "f32": "f", "u8": "B"}


def _as_list(a):
    return a if isinstance(a, (list, array)) else a.tolist()


def _np(kind):
    return {"i64": np.int64, "i32": np.int32, "f64": np.float64, "f32": np.float32, "u8": np.uint8}[kind]


def _zi(n):
    return [0] * n


def _zf(n):
    return [0.0] * n


def _v(p, k):
    return p.tr_spec[k]["value"]


def _lc(p, k):
    return p.hh_spec["life_course"]["value"][k]["value"]


def _b10(a):
    return mini(idiv(a, 10), 8)


def _slots_in(b):
    return AGE_SLOTS if b == BANDS - 1 else 5


def _top_slot(b):
    return AGE_SLOTS - 1 if b == BANDS - 1 else 4


# ---- life_course.gd's rate functions ----

def lc_shares(p, a, s):
    sa = _lc(p, "prevalence_single_age")
    sx = "men" if s == 0 else "women"
    a1 = clampi(a, 0, 100)
    s2 = float(sa["g2plus"][sx][a1])
    med = float(_lc(p, "medical_level"))
    g4 = float(sa["g4"][sx][a1]) / med
    g3 = maxf(0.0, s2 - g4) * float(_lc(p, "poor_share_of_rest")) / med
    g2 = maxf(0.0, maxf(s2, g4) - g4 - g3)
    g1 = maxf(0.0, 1.0 - g2 - g3 - g4)
    b4 = lc_ltci_share(p, a, s)
    if b4 > g4:
        sc = (1.0 - b4) / (1.0 - g4)
        g1 *= sc
        g2 *= sc
        g3 *= sc
        g4 = b4
    return [g1, g2, g3, g4 - b4, b4]


def lc_ltci_share(p, a, s):
    return float(_lc(p, "prevalence_single_age")["b4"]["men" if s == 0 else "women"][clampi(a, 0, 100)])

def lc_income_factor(p, a, k):
    f = _lc(p, "death_income_factor")
    x = clampf(float(a), float(f["range"][0]), float(f["range"][1])) - float(f["a0"])
    return detmath.exp(0.5 * float(k) * (float(f["b0"]) + float(f["b1"]) * x))


def lc_death_q(p, c, a, g, k, mu, per):
    return 1.0 - detmath.exp(-c * float(_lc(p, "death_multiplier")[g]) * lc_income_factor(p, a, k) * mu / per)


def lc_h_regrade(p):
    return 1.0 - float(_lc(p, "grade_kernel")["within_stay"])


def lc_grade_kernel(p, c, pi0):
    kp = _lc(p, "grade_kernel")
    cl = kp["stable" if c == 0 else "mobile"]
    a = float(cl["good_stay"])
    b = float(cl["bad_stay"])
    r = lc_h_regrade(p)
    p4 = [pi0[0], pi0[1], pi0[2], pi0[3] + pi0[4]]
    tot = [p4[0] + p4[1], p4[2] + p4[3]]
    k4 = _zf(16)
    for g in range(4):
        side_g = g // 2
        p_good = a if side_g == 0 else 1.0 - b
        for side in range(2):
            p_side = p_good if side == 0 else 1.0 - p_good
            if tot[side] <= 0.0:
                continue
            for h in (side * 2, side * 2 + 1):
                share = p4[h] / tot[side]
                if side == side_g:
                    share = (1.0 - r) * (1.0 if h == g else 0.0) + r * p4[h] / tot[side]
                k4[g * 4 + h] += p_side * share
    bad_stay = k4[14] + k4[15]
    k4[15] = minf(float(kp["adl_stay"]) * b / float(kp["bad_stay_one_year"]), bad_stay)
    k4[14] = bad_stay - k4[15]
    k = _zf(NG * NG)
    for g2 in range(4):
        for h2 in range(3):
            k[g2 * NG + h2] = k4[g2 * 4 + h2]
        if p4[3] > 0.0:
            k[g2 * NG + 3] = k4[g2 * 4 + 3] * pi0[3] / p4[3]
            k[g2 * NG + 4] = k4[g2 * 4 + 3] * pi0[4] / p4[3]
    eb = float(kp["care_exit"])
    k[4 * NG + 4] = 1.0 - eb
    k[4 * NG + 3] = eb
    return k

def lc_grade_flows(p, n, pi0):
    ng = len(pi0)
    nr = 2 * ng
    pt = 0.0
    for g0 in range(ng):
        pt += pi0[g0]
    nt = 0.0
    for x in range(nr):
        nt += n[x]
    f = _zf(nr * ng)
    for c in range(2):
        k = lc_grade_kernel(p, c, pi0)
        for g in range(ng):
            for h in range(ng):
                f[(c * ng + g) * ng + h] = n[c * ng + g] * k[g * ng + h]
    res = 0.0
    for _it in range(1000):
        for h2 in range(ng):
            col = 0.0
            for rw in range(nr):
                col += f[rw * ng + h2]
            if col > 0.0:
                sc = pi0[h2] / pt * nt / col
                for rw2 in range(nr):
                    f[rw2 * ng + h2] *= sc
        for rw3 in range(nr):
            row = 0.0
            for h6 in range(ng):
                row += f[rw3 * ng + h6]
            if row > 0.0:
                sr = n[rw3] / row
                for h3 in range(ng):
                    f[rw3 * ng + h3] *= sr
        res = 0.0
        for h4 in range(ng):
            col2 = 0.0
            for rw4 in range(nr):
                col2 += f[rw4 * ng + h4]
            res = maxf(res, abs(col2 - pi0[h4] / pt * nt))
        if res <= 1e-12 * nt:
            break
    pm = _zf(nr * ng)
    for rw5 in range(nr):
        for h5 in range(ng):
            pm[rw5 * ng + h5] = f[rw5 * ng + h5] / n[rw5] if n[rw5] > 0.0 else (1.0 if h5 == rw5 % ng else 0.0)
    return [pm, res / nt if nt > 0.0 else 0.0]

def step(p):
    w = _t22_work(p)
    tl = w["tally"]
    if p.month % 12 == 0:
        p.tr_pt_jan = list(p.tr_pt_age)
        p.tr_pt_old = list(p.tr_pt_age)
        p.tr_pt_jg = list(p.tr_pt_ag)
        p.tr_pt_og = list(p.tr_pt_ag)
        p.tr_pt_rem = {}
    g0 = grade_table(p, [])
    _t22_age(p, w)
    g1 = grade_table(p, w["lists"])
    _t22_deaths(p, w)
    g2 = grade_table(p, w["lists"])
    if p.month % 12 == 0:
        p.tr_kb = _targets(p)
    _t22_quartiles_w(p, w)
    _t22_compress(p, w)
    _t22_rebuild(p, w)
    g3 = grade_table(p, [])
    _t22_c5(p, w)
    g4 = grade_table(p, [])
    led_none = _zi(len(g0))
    gxs = {"ageing and the re-grade": _gx_off(g0, g1, w["led_age"]), "deaths and widowing": _gx_off(g1, g2, w["led_death"]),
           "C1, C2 and the rebuild": _gx_off(g2, g3, led_none), "C5": _gx_off(g3, g4, led_none)}
    tl["gx_by_stage"] = gxs
    tl["gx"] = int(gxs["ageing and the re-grade"]) + int(gxs["deaths and widowing"]) + int(gxs["C1, C2 and the rebuild"]) + int(gxs["C5"])
    p.tr_margins["t22"] = tl

def _gx_off(before, after, led):
    off = 0
    for x in range(len(before)):
        off += 0 if after[x] - before[x] == led[x] else 1
    return off


def _t22_work(p):
    n_pts = p.tr_pt_off[p.tr_units]
    lists = [list(range(p.tr_pt_off[u], p.tr_pt_off[u + 1])) for u in range(p.tr_units)]
    cp_of = [[] for _ in range(n_pts)]
    hm_of = [[] for _ in range(n_pts)]
    for c in range(len(p.tr_cp_n)):
        cp_of[p.tr_cp_w[c]].append(c)
        cp_of[p.tr_cp_h[c]].append(c)
    hm_h = [0] * len(p.tr_hm_pt)
    for h in range(len(p.tr_hh_keys)):
        for k in range(p.tr_hm_off[h], p.tr_hm_off[h + 1]):
            hm_h[k] = h
            hm_of[p.tr_hm_pt[k]].append(k)
    ins_pt = {}
    ins_ind = {}
    for name in p.tr_instruments:
        arr = p.tr_instruments[name]
        ins_pt[name] = arr[0:n_pts]
        ins_ind[name] = arr[n_pts:]
    stride = {}
    for name2 in p.tr_points:
        stride[name2] = (len(p.tr_points[name2]) // n_pts) if n_pts > 0 else 1
    by_key = {}
    for u2 in range(p.tr_units):
        ks = _key_str(p.tr_key, u2)
        if ks not in by_key:
            by_key[ks] = []
        by_key[ks].append(u2)
    htype = [int(hk.split("|")[1]) for hk in p.tr_hh_keys]
    unit_of = [0] * n_pts
    for u3 in range(p.tr_units):
        for g3 in range(p.tr_pt_off[u3], p.tr_pt_off[u3 + 1]):
            unit_of[g3] = u3
    led_n = 2 * 9 * 4 * NG + AGES * 2 * NG
    return {"htype": htype, "lists": lists, "unit_of": unit_of, "led_age": _zi(led_n), "led_death": _zi(led_n),
            "cp_of": cp_of, "hm_of": hm_of, "hm_h": hm_h, "ins": ins_pt, "ins_ind": ins_ind, "stride": stride, "by_key": by_key,
            "tally": {"moved": 0, "due": 0, "splits": 0, "new_units": 0, "clamped": 0, "merges": 0, "dropped": 0, "class_entered": 0,
                      "split_src": [], "c1": 0, "c2": 0, "cx_bad": 0, "cb_mr": _zf(36), "cb_mv": _zf(36), "cb_cr": _zf(36), "cb_cv": _zf(36),
                      "c1_q_moved": 0, "cb_mm": _zf(36), "cb_cm": _zf(36), "cbg_m": _zf(36), "cbq": 0, "cbq_mass": 0, "c5_moves": 0, "c5_x": 0,
                      "c5_over": 0, "c5_r": _zf(153), "c5_v": _zf(153), "cp_blocks_capped": 0,
                      "deaths": 0, "widowed": 0, "couples_lost": 0, "d_as": _zi(AGES * 2), "d_old": _zi(AGES * 2), "x_as": _zf(AGES * 2),
                      "e_as": _zf(AGES * 2), "v_as": _zf(AGES * 2), "d_g": _zi(AGES * 2 * NG), "x_g": _zf(AGES * 2 * NG), "d_k": _zi(AGES * 8),
                      "x_k": _zf(AGES * 8), "wg_n": _zf(2 * 9 * NG * NG), "wg_x": _zf(2 * 9 * NG), "wg_e": _zf(2 * 9 * NG),
                      "wg_v": _zf(2 * 9 * NG), "gx": 0}}


def grade_table(p, lists):
    base = 2 * 9 * 4 * NG
    out = _zi(base + AGES * 2 * NG)
    key = p.tr_key
    T = p.tr_pt_T
    ag = p.tr_pt_ag
    for u in range(p.tr_units):
        b = key[u * KEY_STRIDE + 1]
        s = key[u * KEY_STRIDE + 2]
        row = (s * 9 + _b10(b * 5)) * 4 * NG
        pts = lists[u] if len(lists) > 0 else range(p.tr_pt_off[u], p.tr_pt_off[u + 1])
        for g in pts:
            for x in range(4 * NG):
                out[row + x] += T[g * 4 * NG + x]
            for sl in range(_slots_in(b)):
                for sb in range(NS):
                    out[base + ((b * 5 + sl) * 2 + s) * NG + sb // NK] += ag[(g * AGE_SLOTS + sl) * NS + sb]
    return out


def _key_str(key, u):
    return "%d|%d|%d|%d|%d|%d" % tuple(key[u * KEY_STRIDE:u * KEY_STRIDE + 6])


def key_of(c, b, s, code):
    k = code // (NTYPE * NEMP)
    gk = k
    gt = (code // NEMP) % NTYPE
    ge = code % NEMP
    if k < CLASS_REST:
        gt = -1
        ge = -1
    elif k < CLASS_NONE:
        gk = CLASS_REST
        if b >= EMP_KEY_UNTIL_BAND:
            ge = -1
    else:
        ge = -1
    return [c, b, s, gk, gt, ge]


def class_of_income(lines, y):
    k = 0
    while k < len(lines) and y < lines[k]:
        k += 1
    return k


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
    out = _zi(12)
    left = m
    rows = []
    o = keyed.below(12, p.seed_v, "t21_birth_month", j, age, 0)
    for k in range(12):
        x = float(m) * float(sh[k])
        out[k] = int(math.floor(x))
        left -= out[k]
        rows.append((-(x - float(out[k])), (k - o + 12) % 12, k))
    rows.sort()
    for r in range(left):
        out[rows[r % 12][2]] += 1
    return out


def _t22_age(p, w):
    mc = p.month % 12
    lists = w["lists"]
    tl = w["tally"]
    U0 = p.tr_units
    nc = AGES * 2 * 4
    nn = _zf(nc * NK * NG)
    mv = []
    key = p.tr_key
    og = p.tr_pt_og
    jg = p.tr_pt_jg
    rem = p.tr_pt_rem
    hd_age = keyed.head(p.seed_v, "t22_age")
    for u in range(U0):
        b = key[u * KEY_STRIDE + 1]
        s = key[u * KEY_STRIDE + 2]
        for g in lists[u]:
            id_ = p.tr_pt_id[g]
            k = p.tr_pt_q[g]
            for sl in range(_slots_in(b)):
                a = b * 5 + sl
                a2 = mini(a + 1, AGES - 1)
                for sb in range(NS):
                    cx = (g * AGE_SLOTS + sl) * NS + sb
                    o = og[cx]
                    if o <= 0:
                        continue
                    gk = id_ * NS + sb
                    rk = (id_ * AGE_SLOTS + sl) * NS + sb
                    has_r = rk in rem
                    S = rem[rk] if has_r else birth_months(p, gk, a, jg[cx])
                    nr = 0
                    for k2 in range(mc, 12):
                        nr += S[k2]
                    tl["due"] = int(tl["due"]) + S[mc]
                    x = o
                    if mc < 11:
                        if nr < o:
                            nr = o
                            tl["clamped"] = int(tl["clamped"]) + 1
                        x = hypergeometric(nr, mini(S[mc], nr), o, float(keyed.h64(hd_age, gk, a, p.month) >> 11) / keyed.TWO53)
                    if has_r:
                        rem[rk][mc] = 0
                    if x <= 0:
                        continue
                    mv.append((u, g, sl, sb, x))
                    nn[((a2 * 2 + s) * 4 + k) * (NK * NG) + (sb % NK) * NG + sb // NK] += float(x)
    W = NK * NG
    pm = _zf(nc * W * NG)
    gp = {"res": 0.0}
    for k0 in ("before", "target", "after", "var", "stay", "stay_seed"):
        gp[k0] = _zf(2 * 9 * NG)
    gp["stay_c"] = _zf(2 * 2 * 9 * NG)
    gp["n_c"] = _zf(2 * 2 * 9 * NG)
    for k6 in ("b4_target", "b4_after", "b4_var", "b4_n", "b4_exit"):
        gp[k6] = _zf(14)
    for cell in range(nc):
        n8 = nn[cell * W:cell * W + W]
        nt = 0.0
        for x0 in range(W):
            nt += n8[x0]
        if nt <= 0.0:
            continue
        a3 = cell // 8
        s2 = (cell // 4) % 2
        pi0 = lc_shares(p, a3, s2)
        pt = 0.0
        for g8 in range(NG):
            pt += pi0[g8]
        out = lc_grade_flows(p, n8, pi0)
        pr = out[0]
        for x1 in range(W * NG):
            pm[cell * W * NG + x1] = pr[x1]
        gp["res"] = maxf(float(gp["res"]), float(out[1]))
        row = (s2 * 9 + _b10(a3)) * NG
        for g1 in range(NG):
            gp["target"][row + g1] += pi0[g1] / pt * nt
        if a3 >= 65:
            gp["b4_target"][s2 * 7 + mini((a3 - 65) // 5, 6)] += pi0[4] / pt * nt
        for c in range(NK):
            kc = lc_grade_kernel(p, c, pi0)
            for g5 in range(NG):
                gp["before"][row + g5] += n8[c * NG + g5]
                gp["stay_seed"][row + g5] += n8[c * NG + g5] * kc[g5 * NG + g5]
    lb = 2 * 9 * 4 * NG
    ups = {}
    moved = 0
    led = w["led_age"]
    T = p.tr_pt_T
    ag = p.tr_pt_ag
    hd_grade = keyed.head(p.seed_v, "t22b_grade")
    for (u2, g2, sl2, sb2, m) in mv:
        b2 = key[u2 * KEY_STRIDE + 1]
        s3 = key[u2 * KEY_STRIDE + 2]
        top = _top_slot(b2)
        a4 = b2 * 5 + sl2
        a5 = mini(a4 + 1, AGES - 1)
        id2 = p.tr_pt_id[g2]
        gr2 = sb2 // NK
        cl = sb2 % NK
        cell2 = (a5 * 2 + s3) * 4 + p.tr_pt_q[g2]
        rw = cl * NG + gr2
        cx2 = (g2 * AGE_SLOTS + sl2) * NS + sb2
        b10s = _b10(b2 * 5)
        row2 = (s3 * 9 + _b10(a5)) * NG
        xs = _zi(NG)
        rmass = m
        rp = 1.0
        for g3 in range(NG):
            pg = pm[cell2 * W * NG + rw * NG + g3]
            gp["var"][row2 + g3] += float(m) * pg * (1.0 - pg)
            x2 = rmass
            if g3 < NG - 1:
                x2 = binomial(rmass, clampf(pg / rp, 0.0, 1.0), float(keyed.h64(hd_grade, id2 * NS + sb2, a5, p.month * NG + g3) >> 11) / keyed.TWO53) if rp > 0.0 and rmass > 0 else 0
            rp -= pg
            rmass -= x2
            xs[g3] = x2
            gp["after"][row2 + g3] += float(x2)
        gp["stay"][row2 + gr2] += float(xs[gr2])
        gp["stay_c"][cl * 18 * NG + row2 + gr2] += float(xs[gr2])
        gp["n_c"][cl * 18 * NG + row2 + gr2] += float(m)
        if a5 >= 65:
            r5 = s3 * 7 + mini((a5 - 65) // 5, 6)
            gp["b4_var"][r5] += float(m) * pm[cell2 * W * NG + rw * NG + 4] * (1.0 - pm[cell2 * W * NG + rw * NG + 4])
            gp["b4_after"][r5] += float(xs[4])
            if gr2 == 4:
                gp["b4_n"][r5] += float(m)
                gp["b4_exit"][r5] += float(xs[3])
        tl["moved"] = int(tl["moved"]) + m
        p.tr_pt_og[cx2] -= m
        ag[cx2] -= m
        p.tr_pt_old[g2 * AGE_SLOTS + sl2] -= m
        p.tr_pt_age[g2 * AGE_SLOTS + sl2] -= m
        p.tr_age_counts[u2 * AGE_SLOTS + sl2] -= m
        for g4 in range(NG):
            x3 = xs[g4]
            if x3 <= 0:
                continue
            led[lb + (a4 * 2 + s3) * NG + gr2] -= x3
            led[lb + (a5 * 2 + s3) * NG + g4] += x3
            if g4 != gr2:
                moved += x3
                col = [T[g2 * 4 * NG + k3 * NG + gr2] for k3 in range(4)]
                md = hypergeometric_split(col, x3, p.seed_v, "t22b_ms", (((id2 * NS + sb2) * NG + g4) * 128 + a5) * 256 + p.month % 256)
                for k4 in range(4):
                    T[g2 * 4 * NG + k4 * NG + gr2] -= md[k4]
                    T[g2 * 4 * NG + k4 * NG + g4] += md[k4]
                    led[(s3 * 9 + b10s) * 4 * NG + k4 * NG + gr2] -= md[k4]
                    led[(s3 * 9 + b10s) * 4 * NG + k4 * NG + g4] += md[k4]
            dsb = g4 * NK + cl
            if a4 >= AGES - 1:
                ag[(g2 * AGE_SLOTS + sl2) * NS + dsb] += x3
                p.tr_pt_age[g2 * AGE_SLOTS + sl2] += x3
                p.tr_age_counts[u2 * AGE_SLOTS + sl2] += x3
            elif sl2 < top:
                ag[(g2 * AGE_SLOTS + sl2 + 1) * NS + dsb] += x3
                p.tr_pt_age[g2 * AGE_SLOTS + sl2 + 1] += x3
                p.tr_age_counts[u2 * AGE_SLOTS + sl2 + 1] += x3
            else:
                if g2 not in ups:
                    ups[g2] = [u2, _zi(NS), a5]
                ups[g2][1][dsb] += x3
    for g6 in ups:
        up = ups[g6]
        _t22_split(p, w, int(up[0]), int(g6), up[1], int(up[2]))
    gp["moved"] = moved
    gp["nn"] = nn
    gp["pm"] = pm
    tl["t22b"] = gp

def _pt_set(p, name, i, v):
    kind = p.pt_kinds[name]
    if kind == "f64":
        p.tr_points[name][i] = float(v)
    elif kind == "f32":
        p.tr_points[name][i] = float(np.float32(v))
    else:
        p.tr_points[name][i] = int(v)


def _t22_split(p, w, u, g, xc, a):
    tl = w["tally"]
    xs = _zi(NG)
    x = 0
    for sb in range(NS):
        xs[sb // NK] += xc[sb]
        x += xc[sb]
    b = a // 5
    code = p.tr_pt_code[g]
    if code // (NTYPE * NEMP) == CLASS_NONE and a >= ADULT_FROM:
        k = class_of_income(p.tr_class_lines, float(p.tr_points["income"][g]))
        code = (k * NTYPE + (code // NEMP) % NTYPE) * NEMP + code % NEMP
        tl["class_entered"] = int(tl["class_entered"]) + x
    key = key_of(p.tr_key[u * KEY_STRIDE], b, p.tr_key[u * KEY_STRIDE + 2], code)
    ks = "%d|%d|%d|%d|%d|%d" % tuple(key)
    id_ = p.tr_pt_id[g]
    if ks in w["by_key"]:
        us = w["by_key"][ks]
        v = int(us[0]) if len(us) == 1 else int(us[keyed.below(len(us), p.seed_v, "t22_part", id_, p.month, 0)])
    else:
        v = _t22_new_unit(p, w, u, key, ks)
    m = p.tr_pt_mass[g]
    h = _t22_new_point(p, w, g, v, code)
    _pt_set(p, "age", h, a)
    p.tr_pt_age[h * AGE_SLOTS] = x
    for sb3 in range(NS):
        p.tr_pt_ag[h * AGE_SLOTS * NS + sb3] = xc[sb3]
    p.tr_pt_mass[h] = x
    p.tr_pt_mass[g] = m - x
    fr = float(x) / float(m)
    p.tr_pt_muq[h] = p.tr_pt_muq[g] * fr
    p.tr_pt_muq[g] -= p.tr_pt_muq[h]
    p.tr_pt_mug[h] = p.tr_pt_mug[g] * fr
    p.tr_pt_mug[g] -= p.tr_pt_mug[h]
    p.tr_count[u] -= x
    p.tr_count[v] += x
    p.tr_age_counts[v * AGE_SLOTS] += x
    tl["splits"] = int(tl["splits"]) + 1
    tl["split_src"].append([p.tr_pt_id[h], id_])
    T = p.tr_pt_T
    q = [0, 0, 0, 0]
    led = w["led_age"]
    for gr2 in range(NG):
        if xs[gr2] <= 0:
            continue
        held_ms = []
        col = 0
        for k4 in range(4):
            held_ms.append(T[g * 4 * NG + k4 * NG + gr2])
            col += held_ms[k4]
        ms = [float(xs[gr2]) * float(held_ms[k2]) / float(col) if col > 0 else 0.0 for k2 in range(4)]
        qg = cap_to(largest_keyed(ms, xs[gr2], p.seed_v, "t22_split_ms", id_ * NG + gr2, p.month), held_ms)
        sx = p.tr_key[u * KEY_STRIDE + 2]
        for k5 in range(4):
            led[(sx * 9 + _b10(p.tr_key[u * KEY_STRIDE + 1] * 5)) * 4 * NG + k5 * NG + gr2] -= qg[k5]
            led[(sx * 9 + _b10(b * 5)) * 4 * NG + k5 * NG + gr2] += qg[k5]
        for k3 in range(4):
            T[g * 4 * NG + k3 * NG + gr2] -= qg[k3]
            T[h * 4 * NG + k3 * NG + gr2] = qg[k3]
            p.tr_pt_ms[g * 4 + k3] -= qg[k3]
            p.tr_pt_ms[h * 4 + k3] += qg[k3]
            q[k3] += qg[k3]
    cps = w["cp_of"][g]
    holds = []
    cm = 0
    for c in cps:
        holds.append(p.tr_cp_n[c])
        cm += p.tr_cp_n[c]
    holds.append(maxi(0, p.tr_pt_ms[g * 4 + 1] + q[1] - cm))
    y = split_holds(holds, q[1], p.seed_v, "t22_split_cp", id_, p.month)
    for i in range(len(cps)):
        if y[i] <= 0:
            continue
        c2 = cps[i]
        p.tr_cp_n[c2] -= y[i]
        fem = p.tr_cp_w[c2] == g
        p.tr_cp_hh.append(p.tr_cp_hh[c2])
        p.tr_cp_w.append(h if fem else p.tr_cp_w[c2])
        p.tr_cp_h.append(p.tr_cp_h[c2] if fem else h)
        p.tr_cp_n.append(y[i])
        nc = len(p.tr_cp_n) - 1
        w["cp_of"][h].append(nc)
        w["cp_of"][p.tr_cp_h[c2] if fem else p.tr_cp_w[c2]].append(nc)
    hms = w["hm_of"][g]
    hh = []
    held = 0
    for e in hms:
        hh.append(p.tr_hm_n[e])
        held += p.tr_hm_n[e]
    hh.append(maxi(0, m - held))
    z = split_holds(hh, x, p.seed_v, "t22_split_hm", id_, p.month)
    for i2 in range(len(hms)):
        if z[i2] <= 0:
            continue
        e2 = hms[i2]
        p.tr_hm_n[e2] -= z[i2]
        p.tr_hm_pt.append(h)
        p.tr_hm_role.append(p.tr_hm_role[e2])
        p.tr_hm_n.append(z[i2])
        w["hm_h"].append(w["hm_h"][e2])
        w["hm_of"][h].append(len(p.tr_hm_n) - 1)
    for name in w["ins"]:
        amt = w["ins"][name][g]
        mv = idiv(amt * x, m)
        w["ins"][name][g] = amt - mv
        w["ins"][name][h] = mv


def _t22_new_point(p, w, g, v, code):
    h = len(p.tr_pt_mass)
    p.tr_pt_mass.append(0)
    p.tr_pt_code.append(code)
    p.tr_pt_q.append(p.tr_pt_q[g])
    p.tr_pt_muq.append(0.0)
    p.tr_pt_mug.append(0.0)
    p.tr_pt_id.append(p.tr_pt_next)
    p.tr_pt_next += 1
    p.tr_pt_age.extend([0] * AGE_SLOTS)
    p.tr_pt_jan.extend([0] * AGE_SLOTS)
    p.tr_pt_old.extend([0] * AGE_SLOTS)
    p.tr_pt_ms.extend([0] * 4)
    p.tr_pt_ag.extend([0] * (AGE_SLOTS * NS))
    p.tr_pt_jg.extend([0] * (AGE_SLOTS * NS))
    p.tr_pt_og.extend([0] * (AGE_SLOTS * NS))
    p.tr_pt_T.extend([0] * (4 * NG))
    w["unit_of"].append(v)
    for name in p.tr_points:
        st = w["stride"][name]
        arr = p.tr_points[name]
        arr.extend(arr[g * st:g * st + st])
    for name2 in w["ins"]:
        w["ins"][name2].append(0)
    w["cp_of"].append([])
    w["hm_of"].append([])
    w["lists"][v].append(h)
    return h


def _t22_new_unit(p, w, u, key, ks):
    v = p.tr_units
    p.tr_key.extend(key)
    p.tr_count.append(0)
    p.tr_age_counts.extend([0] * AGE_SLOTS)
    p.tr_never_married.append(p.tr_never_married[u])
    p.tr_married_apart.append(p.tr_married_apart[u])
    p.tr_tier_size.append(p.tr_tier_size[u])
    p.tr_mix_off.append(len(p.tr_mix_code))
    p.tr_kb.append(p.tr_kb[u])
    p.tr_units += 1
    w["lists"].append([])
    w["by_key"][ks] = [v]
    w["tally"]["new_units"] = int(w["tally"]["new_units"]) + 1
    return v


def mu_path(p, variant="medium"):
    lt = _lc(p, "qx_2022")
    r = _v(p, "mortality_ratio_ipss_2023")
    years = r["years"]
    yi = clampi(p.base_year + idiv(p.month, 12) - int(years[0]), -1, len(years) - 1)
    out = _zf(AGES * 2)
    for s in range(2):
        tab = lt["men" if s == MALE else "women"]
        for a in range(AGES):
            q = float(tab[mini(a, len(tab) - 1)])
            if yi >= 0:
                q = minf(1.0, q * float(r["by_variant"][variant]["M" if s == MALE else "F"][yi][mini(a, int(r["ages"]) - 1)]))
            out[a * 2 + s] = INF if q >= 1.0 else -detmath.log(1.0 - q)
    return out


def _t22_deaths(p, w):
    tl = w["tally"]
    mu = mu_path(p)
    lists = w["lists"]
    unit_of = w["unit_of"]
    key = p.tr_key
    ag = p.tr_pt_ag
    og = p.tr_pt_og
    T = p.tr_pt_T
    ms = p.tr_pt_ms
    hd_d = keyed.head(p.seed_v, "t22_death")
    hd_o = keyed.head(p.seed_v, "t22_death_old")
    led = w["led_death"]
    x_as, e_as, v_as, x_g, x_k = tl["x_as"], tl["e_as"], tl["v_as"], tl["x_g"], tl["x_k"]
    for u in range(p.tr_units):
        b = key[u * KEY_STRIDE + 1]
        s = key[u * KEY_STRIDE + 2]
        for g in lists[u]:
            if p.tr_pt_mass[g] <= 0:
                continue
            id_ = p.tr_pt_id[g]
            k = p.tr_pt_q[g]
            dead = 0
            dead_g = _zi(NG)
            for sl in range(_slots_in(b)):
                a = b * 5 + sl
                ix = a * 2 + s
                for sb in range(NS):
                    gr = sb // NK
                    cx = (g * AGE_SLOTS + sl) * NS + sb
                    m = ag[cx]
                    if m <= 0:
                        continue
                    gk = id_ * NS + sb
                    qm = 1.0 if mu[ix] == INF else lc_death_q(p, p.tr_c[ix], a, gr, k, mu[ix], 12.0)
                    x_as[ix] += float(m) / 12.0
                    e_as[ix] += float(m) * qm
                    v_as[ix] += float(m) * qm * (1.0 - qm)
                    x_g[ix * NG + gr] += float(m) / 12.0
                    x_k[ix * 4 + k] += float(m) / 12.0
                    d = binomial(m, qm, float(keyed.h64(hd_d, gk, a, p.month) >> 11) / keyed.TWO53)
                    if d <= 0:
                        continue
                    o = og[cx]
                    od = hypergeometric(m, o, d, float(keyed.h64(hd_o, gk, a, p.month) >> 11) / keyed.TWO53)
                    led[2 * 9 * 4 * NG + ix * NG + gr] -= d
                    og[cx] -= od
                    ag[cx] -= d
                    p.tr_pt_old[g * AGE_SLOTS + sl] -= od
                    p.tr_pt_age[g * AGE_SLOTS + sl] -= d
                    p.tr_age_counts[u * AGE_SLOTS + sl] -= d
                    tl["d_as"][ix] += d
                    tl["d_old"][ix] += od
                    tl["d_g"][ix * NG + gr] += d
                    tl["d_k"][ix * 4 + k] += d
                    dead_g[gr] += d
                    dead += d
            if dead <= 0:
                continue
            tl["deaths"] = int(tl["deaths"]) + dead
            keep_fr = float(p.tr_pt_mass[g] - dead) / float(p.tr_pt_mass[g])
            p.tr_pt_muq[g] *= keep_fr
            p.tr_pt_mug[g] *= keep_fr
            p.tr_pt_mass[g] -= dead
            p.tr_count[u] -= dead
            married0 = ms[g * 4 + 1]
            md1 = _zi(NG)
            for gr2 in range(NG):
                if dead_g[gr2] <= 0:
                    continue
                col = [T[g * 4 * NG + k2 * NG + gr2] for k2 in range(4)]
                md = hypergeometric_split(col, dead_g[gr2], p.seed_v, "t22_death_ms", (id_ * NG + gr2) * 1200 + p.month)
                for k3 in range(4):
                    led[(s * 9 + _b10(b * 5)) * 4 * NG + k3 * NG + gr2] -= md[k3]
                    T[g * 4 * NG + k3 * NG + gr2] -= md[k3]
                    ms[g * 4 + k3] -= md[k3]
                md1[gr2] = md[1]
            mdt = 0
            for g6 in range(NG):
                mdt += md1[g6]
            if mdt <= 0:
                continue
            cps = w["cp_of"][g]
            holds = []
            cm = 0
            for c in cps:
                holds.append(p.tr_cp_n[c])
                cm += p.tr_cp_n[c]
            holds.append(maxi(0, married0 - cm))
            y = hypergeometric_split(holds, mdt, p.seed_v, "t22_death_cp", id_ * 1200 + p.month)
            for i in range(len(cps)):
                if y[i] <= 0:
                    continue
                c2 = cps[i]
                p.tr_cp_n[c2] -= y[i]
                other = p.tr_cp_h[c2] if p.tr_cp_w[c2] == g else p.tr_cp_w[c2]
                wv = mini(y[i], ms[other * 4 + 1])
                tl["couples_lost"] = int(tl["couples_lost"]) + y[i]
                if wv <= 0:
                    continue
                row1 = []
                n1 = 0
                for g3 in range(NG):
                    row1.append(T[other * 4 * NG + NG + g3])
                    n1 += row1[g3]
                wg = hypergeometric_split(row1, wv, p.seed_v, "t22_widow", (p.tr_pt_id[other] * 1200 + p.month) * 64 + c2 % 64)
                uo = unit_of[other]
                wx = (key[uo * KEY_STRIDE + 2] * 9 + _b10(key[uo * KEY_STRIDE + 1] * 5)) * NG
                lw = (key[uo * KEY_STRIDE + 2] * 9 + _b10(key[uo * KEY_STRIDE + 1] * 5)) * 4 * NG
                for g4 in range(NG):
                    led[lw + NG + g4] -= wg[g4]
                    led[lw + 2 * NG + g4] += wg[g4]
                    T[other * 4 * NG + NG + g4] -= wg[g4]
                    T[other * 4 * NG + 2 * NG + g4] += wg[g4]
                    pr = float(row1[g4]) / float(n1)
                    tl["wg_x"][wx + g4] += float(wg[g4])
                    tl["wg_e"][wx + g4] += float(wv) * pr
                    tl["wg_v"][wx + g4] += float(wv) * pr * (1.0 - pr) * float(n1 - wv) / float(maxi(1, n1 - 1))
                    for dg in range(NG):
                        tl["wg_n"][(wx + dg) * NG + g4] += float(wg[g4]) * float(md1[dg]) / float(mdt)
                ms[other * 4 + 1] -= wv
                ms[other * 4 + 2] += wv
                tl["widowed"] = int(tl["widowed"]) + wv


def _t22_quartiles_w(p, w):
    n_pts = len(p.tr_pt_mass)
    inc = p.tr_points["income"]
    hm_h = w["hm_h"]
    nh = len(p.tr_hh_keys)
    tot = _zf(nh)
    pers = _zf(nh)
    hmn = p.tr_hm_n
    hmp = p.tr_hm_pt
    for e in range(len(hmn)):
        if hmn[e] <= 0:
            continue
        tot[hm_h[e]] += float(hmn[e]) * inc[hmp[e]]
        pers[hm_h[e]] += float(hmn[e])
    eq = _zf(nh)
    for h in range(nh):
        hc = float(int(p.tr_hh[p.tr_hh_keys[h]]["count"]))
        eq[h] = (tot[h] / hc) / math.sqrt(pers[h] / hc) if hc > 0.0 and pers[h] > 0.0 else 0.0
    held = _zi(n_pts)
    sum_e = _zf(n_pts)
    for e2 in range(len(hmn)):
        if hmn[e2] <= 0:
            continue
        held[hmp[e2]] += hmn[e2]
        sum_e[hmp[e2]] += float(hmn[e2]) * eq[hm_h[e2]]
    by = [[] for _ in range(9)]
    lists = w["lists"]
    for u in range(p.tr_units):
        b10b = _b10(p.tr_key[u * KEY_STRIDE + 1] * 5)
        for g in lists[u]:
            m = p.tr_pt_mass[g]
            if m <= 0:
                continue
            rest = maxi(0, m - held[g])
            den = float(held[g] + rest)
            e3 = (sum_e[g] + float(rest) * inc[g]) / den if den > 0.0 else inc[g]
            by[b10b].append((e3, g, m))
    qm = _zf(8)
    for b2 in range(9):
        rows = by[b2]
        # Why not a port of Godot's sort: the second key g is distinct per row, so the order is total and any sort agrees
        rows.sort()
        tot2 = 0.0
        for r in rows:
            tot2 += float(r[2])
        acc = 0.0
        for r2 in rows:
            pos = (acc + 0.5 * float(r2[2])) / tot2 if tot2 > 0.0 else 0.0
            kq = 3 if pos < 0.25 else (2 if pos < 0.5 else (1 if pos < 0.75 else 0))
            p.tr_pt_q[r2[1]] = kq
            qm[kq] += float(r2[0]) * float(r2[2])
            qm[4 + kq] += float(r2[2])
            acc += float(r2[2])
    p.tr_margins["t22_q_means"] = qm


def _largest(v, total):
    n = len(v)
    out = _zi(n)
    used = 0
    for i in range(n):
        out[i] = int(math.floor(v[i]))
        used += out[i]
    order = sorted(range(n), key=lambda i: (-(v[i] - math.floor(v[i])), i))
    q = 0
    while used < total:
        out[order[q % n]] += 1
        used += 1
        q += 1
    while used > total:
        i2 = order[n - 1 - (q % n)]
        if out[i2] > 0:
            out[i2] -= 1
            used -= 1
        q += 1
    return out


def _targets(p):
    U = p.tr_units
    by_pref = {}
    for u in range(U):
        c = p.tr_key[u * KEY_STRIDE]
        if c not in by_pref:
            by_pref[c] = []
        by_pref[c].append(u)
    kb = _zi(U)
    for c2 in by_pref:
        us = by_pref[c2]
        total_n = 0
        for u2 in us:
            total_n += p.tr_count[u2]
        P = p.tr_k * len(us)
        worth = float(total_n) / float(maxi(1, P))
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
        share = _zf(len(us))
        p_rest = maxi(0, P - n_one)
        for j in range(len(us)):
            if kb[us[j]] < 0:
                share[j] = float(p_rest) * float(p.tr_count[us[j]]) / float(maxi(1, rest_n))
        ints = _largest(share, p_rest)
        for j2 in range(len(us)):
            if kb[us[j2]] < 0:
                kb[us[j2]] = maxi(2, ints[j2])
    return kb


def _t22_compress(p, w):
    lists = w["lists"]
    tl = w["tally"]
    for u in range(p.tr_units):
        l = []
        for g in lists[u]:
            if p.tr_pt_mass[g] > 0:
                l.append(g)
            else:
                tl["dropped"] = int(tl["dropped"]) + 1
        if len(l) <= 1:
            lists[u] = l
            continue
        before = _t22_totals(p, w, l)
        l = _t22_coalesce(p, w, u, l)
        kb = cap_target(p, u, l)
        if len(l) > int(math.ceil(1.5 * float(kb))):
            l = _t22_cap(p, w, u, l, kb)
        after = _t22_totals(p, w, l)
        for x in range(len(before)):
            if before[x] != after[x]:
                tl["cx_bad"] = int(tl["cx_bad"]) + 1
                break
        lists[u] = l


def cap_target(p, u, l):
    seen = {}
    for g in l:
        seen[p.tr_pt_q[g]] = True
    return maxi(maxi(1, p.tr_kb[u]), len(seen))


def _t22_totals(p, w, l):
    gb = AGE_SLOTS * 3 + 6 + len(w["ins"])
    out = _zf(gb + AGE_SLOTS * NS * 3 + 4 * NG)
    S2 = AGE_SLOTS * NS
    for g in l:
        for x2 in range(S2):
            out[gb + x2] += float(p.tr_pt_ag[g * S2 + x2])
            out[gb + S2 + x2] += float(p.tr_pt_jg[g * S2 + x2])
            out[gb + 2 * S2 + x2] += float(p.tr_pt_og[g * S2 + x2])
        for x3 in range(4 * NG):
            out[gb + 3 * S2 + x3] += float(p.tr_pt_T[g * 4 * NG + x3])
        for s in range(AGE_SLOTS):
            out[s] += float(p.tr_pt_age[g * AGE_SLOTS + s])
            out[AGE_SLOTS + s] += float(p.tr_pt_jan[g * AGE_SLOTS + s])
            out[2 * AGE_SLOTS + s] += float(p.tr_pt_old[g * AGE_SLOTS + s])
        for k in range(4):
            out[3 * AGE_SLOTS + k] += float(p.tr_pt_ms[g * 4 + k])
        for c in w["cp_of"][g]:
            out[3 * AGE_SLOTS + 4] += float(p.tr_cp_n[c])
        for e in w["hm_of"][g]:
            out[3 * AGE_SLOTS + 5] += float(p.tr_hm_n[e])
        x = 3 * AGE_SLOTS + 6
        for name in w["ins"]:
            out[x] += float(w["ins"][name][g])
            x += 1
    return out


def _t22_same(p, w, a, b):
    if p.tr_pt_code[a] != p.tr_pt_code[b]:
        return False
    for name in p.tr_points:
        if name == "health":
            continue
        st = w["stride"][name]
        arr = p.tr_points[name]
        for k in range(st):
            if arr[a * st + k] != arr[b * st + k]:
                return False
    return True


def _gd_num14(x):
    # Godot's String.num(x, 14): "%.14f" with the trailing zeros and then a trailing point stripped
    if x != x:
        return "nan"
    if x in (INF, -INF):
        return "inf" if x > 0 else "-inf"
    s = "%.14f" % x
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    return s


def _t22_coalesce(p, w, u, l):
    tl = w["tally"]
    grp = {}
    inc = p.tr_points["income"]
    phi = p.tr_points["phi"]
    for g in l:
        key = "%d|%s|%s" % (p.tr_pt_code[g], _gd_num14(float(inc[g])), _gd_num14(float(phi[g])))
        if key not in grp:
            grp[key] = []
        grp[key].append(g)
    gone = {}
    for key2 in grp:
        gs = grp[key2]
        if len(gs) < 2:
            continue
        reps = []
        for g2 in gs:
            hit = -1
            for r in range(len(reps)):
                if _t22_same(p, w, int(reps[r]), g2):
                    hit = r
                    break
            if hit < 0:
                reps.append(g2)
                continue
            a = int(reps[hit])
            kept = a if p.tr_pt_id[a] < p.tr_pt_id[g2] else g2
            drop = g2 if kept == a else a
            if p.tr_pt_q[kept] != p.tr_pt_q[drop]:
                tl["c1_q_moved"] = int(tl["c1_q_moved"]) + p.tr_pt_mass[drop]
            _t22_merge(p, w, kept, drop, u)
            gone[drop] = True
            reps[hit] = kept
            tl["c1"] = int(tl["c1"]) + 1
    return [g3 for g3 in l if g3 not in gone]


def _t22_cap(p, w, u, l, kb):
    tl = w["tally"]
    n = len(l)
    num = []
    for name in ("income", "assets"):
        arr = p.tr_points[name]
        idx = sorted(range(n), key=lambda i: (float(arr[l[i]]), i))
        r = _zf(n)
        for k in range(n):
            r[idx[k]] = float(k) / float(maxi(1, n - 1))
        num.append(r)
    nsc = []
    for v in num:
        mean = 0.0
        for x in v:
            mean += x
        mean /= float(n)
        var_v = 0.0
        for x2 in v:
            var_v += (x2 - mean) * (x2 - mean)
        var_v /= float(n)
        nsc.append(1.0 / var_v if var_v > 0.0 else 0.0)
    cat = []
    csc = []
    for name2 in ("employment", "education", "dream_kind"):
        arr2 = p.tr_points[name2]
        v2 = []
        cnt = {}
        for g2 in l:
            v2.append(int(arr2[g2]))
            cnt[v2[-1]] = int(cnt.get(v2[-1], 0)) + 1
        gini = 1.0
        for c in cnt:
            fq = float(cnt[c]) / float(n)
            gini -= fq * fq
        cat.append(v2)
        csc.append(2.0 / gini if gini > 1e-12 else 0.0)
    zrow = list(range(n))
    comp = [_t22_comp(p, w, int(l[i2])) for i2 in range(n)]
    alive = [int(l[i2]) for i2 in range(n)]
    left = n
    b10 = _b10(p.tr_key[u * KEY_STRIDE + 1] * 5)
    hd_m = keyed.head(p.seed_v, "t22_merge")
    pq = p.tr_pt_q
    mass = p.tr_pt_mass
    while left > kb:
        bi = -1
        bj = -1
        best = INF
        per_q = [0, 0, 0, 0]
        for g5 in alive:
            if g5 >= 0:
                per_q[pq[g5]] += 1
        cross_ok = per_q[0] <= 1 and per_q[1] <= 1 and per_q[2] <= 1 and per_q[3] <= 1
        for i3 in range(n):
            ai = alive[i3]
            if ai < 0:
                continue
            ca = comp[i3]
            a = zrow[i3]
            for j3 in range(i3 + 1, n):
                aj = alive[j3]
                if aj < 0:
                    continue
                if not cross_ok and pq[ai] != pq[aj]:
                    continue
                d = 0.0
                b = zrow[j3]
                for q in range(len(num)):
                    dz = float(num[q][a]) - float(num[q][b])
                    d += dz * dz * nsc[q]
                for q2 in range(len(cat)):
                    if cat[q2][a] != cat[q2][b]:
                        d += csc[q2]
                cb = comp[j3]
                for q3 in range(len(ca)):
                    d += (ca[q3] - cb[q3]) * (ca[q3] - cb[q3])
                cost = float(mass[ai]) * float(mass[aj]) * d
                if cost < best:
                    best = cost
                    bi = i3
                    bj = j3
        gi = alive[bi]
        gj = alive[bj]
        lo = bi if p.tr_pt_id[gi] < p.tr_pt_id[gj] else bj
        hi = bj if lo == bi else bi
        glo = alive[lo]
        ghi = alive[hi]
        wl = float(mass[glo])
        wh = float(mass[ghi])
        ku = float(keyed.h64(hd_m, u, p.month, p.tr_pt_id[glo] * 100000000 + p.tr_pt_id[ghi]) >> 11) / keyed.TWO53
        keep = lo if ku * (wl + wh) < wl else hi
        drop = hi if keep == lo else lo
        if pq[alive[keep]] != pq[alive[drop]]:
            tl["cbq"] = int(tl["cbq"]) + 1
            tl["cbq_mass"] = int(tl["cbq_mass"]) + mass[alive[keep]] + mass[alive[drop]]
        _t22_cb(p, w, alive[keep], alive[drop], b10, wl, wh)
        _t22_book_mu(p, alive[keep], alive[drop], wl, wh, keep == lo)
        _t22_merge(p, w, alive[keep], alive[drop], u)
        comp[keep] = _t22_comp(p, w, int(alive[keep]))
        alive[drop] = -1
        left -= 1
        tl["c2"] = int(tl["c2"]) + 1
    return [g4 for g4 in alive if g4 >= 0]


def _t22_comp(p, w, g):
    out = _zf(12 + NG)
    m = float(p.tr_pt_mass[g])
    if m <= 0.0:
        return out
    for k in range(4):
        out[k] = float(p.tr_pt_ms[g * 4 + k]) / m
    cm = 0.0
    for c in w["cp_of"][g]:
        cm += float(p.tr_cp_n[c])
    out[4] = cm / m
    held = 0.0
    for e in w["hm_of"][g]:
        out[5 + int(w["htype"][w["hm_h"][e]])] += float(p.tr_hm_n[e]) / m
        held += float(p.tr_hm_n[e])
    out[11] = maxf(0.0, m - held) / m
    for gr in range(NG):
        gm = 0
        for k2 in range(4):
            gm += p.tr_pt_T[g * 4 * NG + k2 * NG + gr]
        out[12 + gr] = float(gm) / m
    return out


def _t22_cb(p, w, keep, drop, b10, wl, wh):
    qk = p.tr_pt_q[keep]
    qd = p.tr_pt_q[drop]
    tl = w["tally"]
    pp = wl * wh / ((wl + wh) * (wl + wh))
    mk = float(p.tr_pt_ms[keep * 4 + 1])
    md = float(p.tr_pt_ms[drop * 4 + 1])
    wk = float(p.tr_pt_mass[keep])
    wd = float(p.tr_pt_mass[drop])
    pk = wk / (wk + wd)
    if qk == qd:
        return
    ck = 0.0
    cd = 0.0
    for c in w["cp_of"][keep]:
        ck += float(p.tr_cp_n[c])
    for c2 in w["cp_of"][drop]:
        cd += float(p.tr_cp_n[c2])
    xk = qk * 9 + b10
    xd = qd * 9 + b10
    tl["cb_mr"][xk] += md
    tl["cb_mr"][xd] -= md
    tl["cb_cr"][xk] += cd
    tl["cb_cr"][xd] -= cd
    for x in (xk, xd):
        tl["cb_mv"][x] += pp * (mk + md) * (mk + md)
        tl["cb_cv"][x] += pp * (ck + cd) * (ck + cd)
    mu_m = pk * md - (1.0 - pk) * mk
    mu_c = pk * cd - (1.0 - pk) * ck
    tl["cb_mm"][xk] += mu_m
    tl["cb_mm"][xd] -= mu_m
    tl["cb_cm"][xk] += mu_c
    tl["cb_cm"][xd] -= mu_c


def _t22_rem(p, g, sl, sb, a, mc):
    rk = (p.tr_pt_id[g] * AGE_SLOTS + sl) * NS + sb
    if rk in p.tr_pt_rem:
        return list(p.tr_pt_rem[rk])
    j = p.tr_pt_jg[(g * AGE_SLOTS + sl) * NS + sb]
    out = _zi(12)
    if j > 0:
        out = birth_months(p, p.tr_pt_id[g] * NS + sb, a, j)
        for k in range(mini(12, mc + 1)):
            out[k] = 0
    return out


def _t22_book_mu(p, keep, drop, wl, wh, keep_is_lo):
    wk = wl if keep_is_lo else wh
    wd = wh if keep_is_lo else wl
    pk = wk / (wk + wd)
    mu = pk * float(p.tr_pt_ms[drop * 4 + 1]) - (1.0 - pk) * float(p.tr_pt_ms[keep * 4 + 1])
    if p.tr_pt_q[keep] != p.tr_pt_q[drop]:
        p.tr_pt_muq[keep] += mu


def _t22_merge(p, w, i, k, u):
    mc = p.month % 12
    b = p.tr_key[u * KEY_STRIDE + 1]
    og = p.tr_pt_og
    S2 = AGE_SLOTS * NS
    for s0 in range(AGE_SLOTS):
        for sb in range(NS):
            cx = s0 * NS + sb
            rd = (p.tr_pt_id[k] * AGE_SLOTS + s0) * NS + sb
            if mc < 11 and og[i * S2 + cx] + og[k * S2 + cx] > 0:
                ri = _t22_rem(p, i, s0, sb, b * 5 + s0, mc)
                rk2 = _t22_rem(p, k, s0, sb, b * 5 + s0, mc)
                for m2 in range(12):
                    ri[m2] += rk2[m2]
                p.tr_pt_rem[(p.tr_pt_id[i] * AGE_SLOTS + s0) * NS + sb] = ri
            p.tr_pt_rem.pop(rd, None)
    p.tr_pt_muq[i] += p.tr_pt_muq[k]
    p.tr_pt_muq[k] = 0.0
    p.tr_pt_mug[i] += p.tr_pt_mug[k]
    p.tr_pt_mug[k] = 0.0
    p.tr_pt_mass[i] += p.tr_pt_mass[k]
    p.tr_pt_mass[k] = 0
    for s in range(AGE_SLOTS):
        p.tr_pt_age[i * AGE_SLOTS + s] += p.tr_pt_age[k * AGE_SLOTS + s]
        p.tr_pt_jan[i * AGE_SLOTS + s] += p.tr_pt_jan[k * AGE_SLOTS + s]
        p.tr_pt_old[i * AGE_SLOTS + s] += p.tr_pt_old[k * AGE_SLOTS + s]
    for s2 in range(4):
        p.tr_pt_ms[i * 4 + s2] += p.tr_pt_ms[k * 4 + s2]
    ag = p.tr_pt_ag
    jg = p.tr_pt_jg
    for x in range(S2):
        ag[i * S2 + x] += ag[k * S2 + x]
        jg[i * S2 + x] += jg[k * S2 + x]
        og[i * S2 + x] += og[k * S2 + x]
        ag[k * S2 + x] = 0
        jg[k * S2 + x] = 0
        og[k * S2 + x] = 0
    T = p.tr_pt_T
    for x2 in range(4 * NG):
        T[i * 4 * NG + x2] += T[k * 4 * NG + x2]
        T[k * 4 * NG + x2] = 0
    for name in w["ins"]:
        w["ins"][name][i] += w["ins"][name][k]
        w["ins"][name][k] = 0
    for c in w["cp_of"][k]:
        if p.tr_cp_w[c] == k:
            p.tr_cp_w[c] = i
        if p.tr_cp_h[c] == k:
            p.tr_cp_h[c] = i
        w["cp_of"][i].append(c)
    for e in w["hm_of"][k]:
        p.tr_hm_pt[e] = i
        w["hm_of"][i].append(e)
    w["cp_of"][k] = []
    w["hm_of"][k] = []


def _perm(src, order, st):
    out = array(src.typecode) if isinstance(src, array) else []
    for g in order:
        out.extend(src[g * st:g * st + st])
    return out


def _t22_rebuild(p, w):
    lists = w["lists"]
    order = []
    off = []
    for u in range(p.tr_units):
        off.append(len(order))
        for g in lists[u]:
            if p.tr_pt_mass[g] > 0:
                order.append(g)
    off.append(len(order))
    n_old = len(p.tr_pt_mass)
    nid = [-1] * n_old
    for i in range(len(order)):
        nid[order[i]] = i
    p.tr_pt_off = off
    p.tr_pt_mass = _perm(p.tr_pt_mass, order, 1)
    p.tr_pt_id = _perm(p.tr_pt_id, order, 1)
    p.tr_pt_age = _perm(p.tr_pt_age, order, AGE_SLOTS)
    p.tr_pt_jan = _perm(p.tr_pt_jan, order, AGE_SLOTS)
    p.tr_pt_old = _perm(p.tr_pt_old, order, AGE_SLOTS)
    p.tr_pt_ms = _perm(p.tr_pt_ms, order, 4)
    p.tr_pt_ag = _perm(p.tr_pt_ag, order, AGE_SLOTS * NS)
    p.tr_pt_jg = _perm(p.tr_pt_jg, order, AGE_SLOTS * NS)
    p.tr_pt_og = _perm(p.tr_pt_og, order, AGE_SLOTS * NS)
    p.tr_pt_T = _perm(p.tr_pt_T, order, 4 * NG)
    p.tr_pt_code = [p.tr_pt_code[g] for g in order]
    p.tr_pt_q = [p.tr_pt_q[g] for g in order]
    p.tr_pt_muq = [p.tr_pt_muq[g] for g in order]
    p.tr_pt_mug = [p.tr_pt_mug[g] for g in order]
    for name in p.tr_points:
        p.tr_points[name] = _perm(p.tr_points[name], order, w["stride"][name])
    for name2 in w["ins"]:
        pts = _perm(w["ins"][name2], order, 1)
        pts.extend(w["ins_ind"][name2])
        p.tr_instruments[name2] = pts
    seen = {}
    cw = []
    chh = []
    chu = []
    cn = []
    lost = 0
    lost_hm = 0
    no = len(order)
    nkeys1 = len(p.tr_hh_keys) + 1
    for c in range(len(p.tr_cp_n)):
        if p.tr_cp_n[c] <= 0:
            continue
        a = nid[p.tr_cp_w[c]]
        b = nid[p.tr_cp_h[c]]
        if a < 0 or b < 0:
            lost += p.tr_cp_n[c]
            continue
        ck = (a * no + b) * nkeys1 + p.tr_cp_hh[c]
        if ck in seen:
            cn[seen[ck]] += p.tr_cp_n[c]
            continue
        seen[ck] = len(cn)
        chh.append(p.tr_cp_hh[c])
        cw.append(a)
        chu.append(b)
        cn.append(p.tr_cp_n[c])
    p.tr_cp_hh = chh
    p.tr_cp_w = cw
    p.tr_cp_h = chu
    p.tr_cp_n = cn
    hm_h = w["hm_h"]
    rows = []
    for e in range(len(p.tr_hm_n)):
        if p.tr_hm_n[e] <= 0:
            continue
        if nid[p.tr_hm_pt[e]] < 0:
            lost_hm += p.tr_hm_n[e]
            continue
        rows.append((hm_h[e], e))
    rows.sort()
    seen2 = {}
    hpt = []
    hro = []
    hn = []
    nk = len(p.tr_hh_keys)
    hoff = [0] * (nk + 1)
    at = 0
    for r in rows:
        e2 = r[1]
        hk = (r[0] * no + nid[p.tr_hm_pt[e2]]) * 8 + p.tr_hm_role[e2]
        if hk in seen2:
            hn[seen2[hk]] += p.tr_hm_n[e2]
            continue
        while at <= r[0]:
            hoff[at] = len(hpt)
            at += 1
        seen2[hk] = len(hn)
        hpt.append(nid[p.tr_hm_pt[e2]])
        hro.append(p.tr_hm_role[e2])
        hn.append(p.tr_hm_n[e2])
    while at <= nk:
        hoff[at] = len(hpt)
        at += 1
    p.tr_hm_off = hoff
    p.tr_hm_pt = hpt
    p.tr_hm_role = hro
    p.tr_hm_n = hn
    w["tally"]["lost"] = lost
    ids = set(p.tr_pt_id)
    for rk3 in list(p.tr_pt_rem.keys()):
        if idiv(int(rk3), AGE_SLOTS * NS) not in ids:
            del p.tr_pt_rem[rk3]
    w["tally"]["lost_hm"] = lost_hm
    _point_wealth(p)


def _point_wealth(p):
    by = _v(p, "instrument_age_profiles")["by_instrument"]
    fin = sorted(name for name in p.tr_instruments if str(by.get(name, "")) == "financial")
    n_pts = p.tr_pt_off[p.tr_units]
    ins = p.tr_instruments
    for g in range(n_pts):
        a = 0
        for name2 in fin:
            a += ins[name2][g]
        m = float(p.tr_pt_mass[g])
        _pt_set(p, "assets", g, float(a) / m / 1e4 if m > 0.0 else 0.0)
        _pt_set(p, "debt", g, float(ins["borrowing"][g]) / m / 1e4 if m > 0.0 else 0.0)


def _at_work(p, j):
    e = p.tr_points["employment"][j]
    return e == EMP_REGULAR or e == EMP_NONREGULAR


def _t22_c5(p, w):
    tl = w["tally"]
    unit_of = [0] * p.tr_pt_off[p.tr_units]
    for u in range(p.tr_units):
        for g in range(p.tr_pt_off[u], p.tr_pt_off[u + 1]):
            unit_of[g] = u
    blocks = {}
    for c in range(len(p.tr_cp_n)):
        hb0 = p.tr_cp_hh[c]
        if hb0 not in blocks:
            blocks[hb0] = []
        blocks[hb0].append(c)
    for hb in sorted(blocks.keys()):
        cells = blocks[hb]
        pw = {}
        ph = {}
        for c2 in cells:
            pw[p.tr_cp_w[c2]] = True
            ph[p.tr_cp_h[c2]] = True
        cap = maxi(int(p.tr_cp_cap.get(int(hb), 0)), int(math.ceil(1.5 * float(len(pw) + len(ph) - 1))))
        if len(cells) <= cap:
            continue
        tl["cp_blocks_capped"] = int(tl["cp_blocks_capped"]) + 1
        before = _t22_c5_marg(p, cells)
        _t22_c5_block(p, tl, cells, cap, int(hb), unit_of)
        kept = [c3 for c3 in cells if p.tr_cp_n[c3] > 0]
        if len(kept) > cap:
            tl["c5_over"] = int(tl["c5_over"]) + 1
        after = _t22_c5_marg(p, kept)
        # Why not Godot's Dictionary.hash(): it is the engine's 32-bit hash; ordered equality is the same test barring its collisions (PY_TRIAL_PLAN §2)
        if list(before.items()) != list(after.items()) or len(before) != len(after):
            tl["c5_x"] = int(tl["c5_x"]) + 1
    hh = []
    cw = []
    ch = []
    cn = []
    for c4 in range(len(p.tr_cp_n)):
        if p.tr_cp_n[c4] > 0:
            hh.append(p.tr_cp_hh[c4])
            cw.append(p.tr_cp_w[c4])
            ch.append(p.tr_cp_h[c4])
            cn.append(p.tr_cp_n[c4])
    p.tr_cp_hh = hh
    p.tr_cp_w = cw
    p.tr_cp_h = ch
    p.tr_cp_n = cn


def _t22_c5_marg(p, cells):
    m = {}
    tot = 0
    for c in cells:
        kw = p.tr_cp_w[c] * 2
        kh = p.tr_cp_h[c] * 2 + 1
        m[kw] = int(m.get(kw, 0)) + p.tr_cp_n[c]
        m[kh] = int(m.get(kh, 0)) + p.tr_cp_n[c]
        tot += p.tr_cp_n[c]
    out = {"total": tot}
    for k in sorted(m.keys()):
        if int(m[k]) > 0:
            out[k] = m[k]
    return out


def _t22_c5_block(p, tl, cells, cap, hb, unit_of):
    rows = []
    for c in cells:
        rows.append((-p.tr_cp_n[c], p.tr_pt_id[p.tr_cp_w[c]], p.tr_pt_id[p.tr_cp_h[c]], c))
    rows.sort()
    parent = {}
    adj = {}
    off = []
    for r in rows:
        c2 = r[3]
        a = p.tr_cp_w[c2] * 2
        b = p.tr_cp_h[c2] * 2 + 1
        ra = _uf_find(parent, a)
        rb = _uf_find(parent, b)
        if ra != rb:
            parent[ra] = rb
            _c5_link(adj, a, b, c2)
        else:
            off.append((p.tr_cp_n[c2], r[1], r[2], c2))
    off.sort()
    live = len(cells)
    hd5 = keyed.head(p.seed_v, "t22_c5")
    for o in off:
        if live <= cap:
            break
        c3 = o[3]
        if p.tr_cp_n[c3] <= 0:
            continue
        start = p.tr_cp_h[c3] * 2 + 1
        goal = p.tr_cp_w[c3] * 2
        path = _c5_path(adj, start, goal)
        if not path:
            _c5_link(adj, goal, start, c3)
            continue
        cyc = [c3] + path
        d1 = 1 << 60
        d2 = 1 << 60
        for i in range(len(cyc)):
            if i % 2 == 1:
                d1 = mini(d1, p.tr_cp_n[cyc[i]])
            else:
                d2 = mini(d2, p.tr_cp_n[cyc[i]])
        uu = float(keyed.h64(hd5, p.month, hb, p.tr_pt_id[p.tr_cp_w[c3]] * 100000000 + p.tr_pt_id[p.tr_cp_h[c3]]) >> 11) / keyed.TWO53
        dv = d1 if uu * float(d1 + d2) < float(d2) else -d2
        fsum = {}
        for i2 in range(len(cyc)):
            sg = 1 if i2 % 2 == 0 else -1
            c5 = cyc[i2]
            p.tr_cp_n[c5] += sg * dv
            for f in _t22_c5_keys(p, c5, unit_of):
                fsum[f] = int(fsum.get(f, 0)) + sg
        for f2 in fsum:
            tl["c5_r"][int(f2)] += float(int(fsum[f2]) * dv)
            tl["c5_v"][int(f2)] += float(d1) * float(d2) * float(int(fsum[f2]) * int(fsum[f2]))
        tl["c5_moves"] = int(tl["c5_moves"]) + 1
        lost_edge = False
        for i3 in range(1, len(cyc)):
            e = cyc[i3]
            if p.tr_cp_n[e] <= 0:
                _c5_unlink(adj, p.tr_cp_w[e] * 2, p.tr_cp_h[e] * 2 + 1, e)
                lost_edge = True
                live -= 1
        if p.tr_cp_n[c3] <= 0:
            live -= 1
        elif lost_edge:
            _c5_link(adj, goal, start, c3)


def _c5_link(adj, a, b, c):
    if a not in adj:
        adj[a] = {}
    if b not in adj:
        adj[b] = {}
    adj[a][c] = b
    adj[b][c] = a


def _c5_unlink(adj, a, b, c):
    if a in adj:
        adj[a].pop(c, None)
    if b in adj:
        adj[b].pop(c, None)


def _c5_path(adj, start, goal):
    prev = {start: (-1, -1)}
    queue = [start]
    qi = 0
    while qi < len(queue) and goal not in prev:
        x = queue[qi]
        qi += 1
        nb = adj.get(x, {})
        for c in nb:
            y = int(nb[c])
            if y not in prev:
                prev[y] = (x, c)
                queue.append(y)
    if goal not in prev:
        return []
    path = []
    at = goal
    while at != start:
        path.append(int(prev[at][1]))
        at = int(prev[at][0])
    path.reverse()
    return path


def _uf_find(parent, x):
    r = x
    while r in parent and int(parent[r]) != r:
        r = int(parent[r])
    y = x
    while y in parent and int(parent[y]) != r:
        nx = int(parent[y])
        parent[y] = r
        y = nx
    if r not in parent:
        parent[r] = r
    return r


def _t22_c5_keys(p, c, unit_of):
    wq = p.tr_pt_q[p.tr_cp_w[c]]
    hq = p.tr_pt_q[p.tr_cp_h[c]]
    b10 = _b10(p.tr_key[unit_of[p.tr_cp_h[c]] * KEY_STRIDE + 1] * 5)
    out = [(wq * 4 + hq) * 9 + b10]
    if _at_work(p, p.tr_cp_w[c]) and _at_work(p, p.tr_cp_h[c]):
        out.append(144 + b10)
    return out
