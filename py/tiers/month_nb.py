# The T2.2 month with the Numba kernels (nbk.py) and the cell arrays in NumPy: a private copy of month.py with its hot functions
# replaced; every other function is month.py's own code (PY_TRIAL_PLAN §2, Numba where measured)
# Why a private copy and not patching month.py: the pure month stays importable in the same process, as the trial's baseline
import importlib.util
import os

import numpy as np

from core import keyed
from tiers import nbk
from core.digest import Packed

_spec = importlib.util.spec_from_file_location("tiers._month_nbbase", os.path.join(os.path.dirname(__file__), "month.py"),
                                               submodule_search_locations=None)
M = importlib.util.module_from_spec(_spec)
M.__package__ = "tiers"
_spec.loader.exec_module(M)

AGE_SLOTS = M.AGE_SLOTS
NS = M.NS
NG = M.NG
KEY_STRIDE = M.KEY_STRIDE
CELL = {"tr_pt_ag": AGE_SLOTS * NS, "tr_pt_jg": AGE_SLOTS * NS, "tr_pt_og": AGE_SLOTS * NS, "tr_pt_age": AGE_SLOTS, "tr_pt_jan": AGE_SLOTS,
        "tr_pt_old": AGE_SLOTS, "tr_pt_T": 4 * NG, "tr_pt_ms": 4}
HEAD = 0.5


# CORE_LAYOUT_PLAN §2: the counts, indices and ids held as int32 (each bound by the national population or the points held, 2^31 - 1
# far above either); array('i') raises on an overflow instead of wrapping
NARROW = ("tr_cp_hh", "tr_cp_w", "tr_cp_h", "tr_cp_n", "tr_hm_pt", "tr_hm_role", "tr_hm_n", "tr_pt_mass", "tr_pt_id", "tr_pt_code",
          "tr_pt_q", "tr_count", "tr_key")
I32 = (1 << 31) - 1


def _arr(tc, a):
    # A typed array from a NumPy array or a sequence, checked to fit when narrowed
    # Why not array(tc, list): a list of the values is the copy this layout avoids
    a = np.asarray(a)
    if tc == "i":
        if a.size and int(np.abs(a).max()) > I32:
            raise OverflowError("an int32 field holds %d" % int(np.abs(a).max()))
        a = a.astype(np.int32, copy=False)
    else:
        a = a.astype({"q": np.int64, "d": np.float64, "f": np.float32}[tc], copy=False)
    out = M.array(tc)
    out.frombytes(np.ascontiguousarray(a).tobytes())
    return out


class St(M.St):
    # The Numba path's state (CORE_LAYOUT_PLAN options 1-3): the point cells as int64 NumPy buffers sized to the points held, every
    # other packed field a typed array (int32 where §2 proves it fits), tr_pt_rem's vectors as lists
    def __init__(self, tree):
        self.kinds = {}
        self.pt_kinds = {}
        self.extra = {}
        for k in list(tree.keys()):
            v = tree.pop(k)
            if k == "tr_points":
                self.tr_points = {}
                for n in list(v.keys()):
                    arr = v.pop(n)
                    self.tr_points[n] = _arr(M.TYPECODE[arr.kind], arr.a)
                    self.pt_kinds[n] = arr.kind
            elif k == "tr_instruments":
                self.tr_instruments = {n: _arr("q", v.pop(n).a) for n in list(v.keys())}
            elif isinstance(v, Packed):
                self.kinds[k] = v.kind
                if k in CELL:
                    a = np.asarray(v.a)
                    if a.size and int(np.abs(a).max()) > I32:
                        raise OverflowError("%s holds %d" % (k, int(np.abs(a).max())))
                    setattr(self, k, np.ascontiguousarray(a.astype(np.int32)))
                elif k == "tr_age_counts":
                    setattr(self, k, np.ascontiguousarray(np.asarray(v.a, dtype=np.int64)))
                else:
                    setattr(self, k, _arr("i" if k in NARROW else M.TYPECODE[v.kind], v.a))
            elif k == "tr_pt_rem":
                self.tr_pt_rem = {rk: M._as_list(rv.a) for rk, rv in v.items()}
            else:
                setattr(self, k, v)
            del v
        self.tr_margins = {}
        self.cap = len(self.tr_pt_mass)
        bm = M._v(self, "birth_month_shares")
        self.bm_sh = np.array([[float(x) for x in row] for row in bm["shares"]], dtype=np.float64)
        best = np.zeros(M.AGES + 1, dtype=np.int64)
        for age in range(M.AGES + 1):
            y = max(1947, 2023 - age)
            bd = 1 << 30
            for i in range(len(bm["years"])):
                d = abs(int(bm["years"][i]) - y)
                if d < bd:
                    bd = d
                    best[age] = i
        self.bm_best = best

    def tree(self):
        n = len(self.tr_pt_mass)
        saved = {}
        for name, st in CELL.items():
            saved[name] = getattr(self, name)
            setattr(self, name, saved[name][:n * st].tolist())
        ac = self.tr_age_counts
        self.tr_age_counts = ac.tolist()
        try:
            return super().tree()
        finally:
            for name in CELL:
                setattr(self, name, saved[name])
            self.tr_age_counts = ac

    def field(self, k):
        # The field as it is held; core.digest._hash_values widens it to the oracle's kind chunk by chunk
        if k in CELL:
            return Packed("i64", getattr(self, k)[:len(self.tr_pt_mass) * CELL[k]])
        if k in self.kinds:
            return Packed(self.kinds[k], getattr(self, k))
        if k == "tr_points":
            return {n: Packed(self.pt_kinds[n], a) for n, a in self.tr_points.items()}
        if k == "tr_instruments":
            return {n: Packed("i64", a) for n, a in self.tr_instruments.items()}
        return super().field(k)

    def grow(self, need=0):
        # Why an exact size (CORE_LAYOUT_PLAN option 1): the ageing kernel counts the month's splits before any is applied, and each
        # adds one point, so the buffers grow once to n + that count; the 1.5x headroom held half the cells idle all month
        n = len(self.tr_pt_mass)
        cap2 = max(n + need, n + 1)
        for name, st in CELL.items():
            a = np.zeros(cap2 * st, dtype=np.int32)
            a[:n * st] = getattr(self, name)[:n * st]
            setattr(self, name, a)
        self.cap = cap2


def _flat(lists, U):
    off = np.zeros(U + 1, dtype=np.int64)
    for u in range(U):
        off[u + 1] = off[u] + len(lists[u])
    idx = np.fromiter((g for u in range(U) for g in lists[u]), dtype=np.int64, count=int(off[U]))
    return off, idx


def _unit_bs(p):
    key = np.array(p.tr_key, dtype=np.int64).reshape(-1, KEY_STRIDE)
    return key[:, 1].copy(), key[:, 2].copy()


def grade_table(p, lists):
    ub, us = _unit_bs(p)
    if len(lists) > 0:
        off, idx = _flat(lists, p.tr_units)
    else:
        off = np.array(p.tr_pt_off, dtype=np.int64)
        idx = np.arange(off[-1], dtype=np.int64)
    return nbk.grade_table(p.tr_pt_T, p.tr_pt_ag, ub, us, off, idx).tolist()


def _t22_age(p, w):
    # month.py's _t22_age (M035) with its two loops in nbk.age_collect and nbk.age_apply and the pooled cells' flows here
    lists = w["lists"]
    tl = w["tally"]
    U0 = p.tr_units
    ub, us = _unit_bs(p)
    off, idx = _flat(lists, U0)
    rk = sorted(p.tr_pt_rem.keys())
    rem_keys = np.array(rk, dtype=np.int64)
    rem_vals = np.array([p.tr_pt_rem[k] for k in rk], dtype=np.int64).reshape(len(rk), 12)
    ids = np.array(p.tr_pt_id, dtype=np.int64)
    pq = np.array(p.tr_pt_q, dtype=np.int64)
    nc = M.AGES * 2 * 4
    W = M.NK * NG
    nn = np.zeros(nc * W, dtype=np.float64)
    cnt = np.zeros(3, dtype=np.int64)
    # Why the arrivals' buffers are sized by a counting pass: a point can bring up to every one of its cells, and a full-size buffer is
    # 16 x 10 int64 per point five times over
    nmv = _count_arrivals(p, off, idx)
    mv = [np.zeros(max(1, nmv), dtype=np.int64) for _ in range(5)]
    nbk.age_collect(p.month, ub, us, U0, off, idx, ids, pq, p.tr_pt_og, p.tr_pt_jg, rem_keys, rem_vals, p.bm_best, p.bm_sh,
                    np.uint64(keyed.head(p.seed_v, "t21_birth_month")), np.uint64(keyed.head(p.seed_v, "t22_age")), nn,
                    mv[0], mv[1], mv[2], mv[3], mv[4], cnt)
    for i, k in enumerate(rk):
        p.tr_pt_rem[k] = rem_vals[i].tolist()
    tl["due"] = int(tl["due"]) + int(cnt[0])
    tl["clamped"] = int(tl["clamped"]) + int(cnt[1])
    nn_l = nn.tolist()
    pm = M._zf(nc * W * NG)
    gp = {"res": 0.0}
    for k0 in ("before", "target", "after", "var", "stay", "stay_seed"):
        gp[k0] = M._zf(2 * 9 * NG)
    gp["stay_c"] = M._zf(2 * 2 * 9 * NG)
    gp["n_c"] = M._zf(2 * 2 * 9 * NG)
    for k6 in ("b4_target", "b4_after", "b4_var", "b4_n", "b4_exit"):
        gp[k6] = M._zf(14)
    for cell in range(nc):
        n8 = nn_l[cell * W:cell * W + W]
        nt = 0.0
        for x0 in range(W):
            nt += n8[x0]
        if nt <= 0.0:
            continue
        a3 = cell // 8
        s2 = (cell // 4) % 2
        pi0 = M.lc_shares(p, a3, s2)
        pt = 0.0
        for g8 in range(NG):
            pt += pi0[g8]
        out = M.lc_grade_flows(p, n8, pi0)
        pr = out[0]
        for x1 in range(W * NG):
            pm[cell * W * NG + x1] = pr[x1]
        gp["res"] = M.maxf(float(gp["res"]), float(out[1]))
        row = (s2 * 9 + M._b10(a3)) * NG
        for g1 in range(NG):
            gp["target"][row + g1] += pi0[g1] / pt * nt
        if a3 >= 65:
            gp["b4_target"][s2 * 7 + min((a3 - 65) // 5, 6)] += pi0[4] / pt * nt
        for c in range(M.NK):
            kc = M.lc_grade_kernel(p, c, pi0)
            for g5 in range(NG):
                gp["before"][row + g5] += n8[c * NG + g5]
                gp["stay_seed"][row + g5] += n8[c * NG + g5] * kc[g5 * NG + g5]
    fa = {k: np.array(gp[k], dtype=np.float64) for k in ("var", "after", "stay", "stay_c", "n_c", "b4_var", "b4_after", "b4_n", "b4_exit")}
    led = np.array(w["led_age"], dtype=np.int64)
    n_pts = len(p.tr_pt_mass)
    up_of = np.full(n_pts, -1, dtype=np.int64)
    up_g = np.zeros(n_pts, dtype=np.int64)
    up_u = np.zeros(n_pts, dtype=np.int64)
    up_a = np.zeros(n_pts, dtype=np.int64)
    up_x = np.zeros((n_pts, NS), dtype=np.int64)
    c2 = np.zeros(3, dtype=np.int64)
    nbk.age_apply(p.month, int(cnt[2]), mv[0], mv[1], mv[2], mv[3], mv[4], ub, us, ids, pq, p.tr_pt_og, p.tr_pt_ag, p.tr_pt_old,
                  p.tr_pt_age, p.tr_age_counts, p.tr_pt_T, np.array(pm, dtype=np.float64), np.uint64(keyed.head(p.seed_v, "t22b_grade")),
                  np.uint64(keyed.head(p.seed_v, "t22b_ms")), led, fa["var"], fa["after"], fa["stay"], fa["stay_c"], fa["n_c"],
                  fa["b4_var"], fa["b4_after"], fa["b4_n"], fa["b4_exit"], up_g, up_u, up_a, up_x, up_of, c2)
    for k, a in fa.items():
        gp[k] = a.tolist()
    w["led_age"] = led.tolist()
    tl["moved"] = int(tl["moved"]) + int(c2[0])
    if len(p.tr_pt_mass) + int(c2[2]) > p.cap:
        p.grow(int(c2[2]))
    for i in range(int(c2[2])):
        M._t22_split(p, w, int(up_u[i]), int(up_g[i]), up_x[i].tolist(), int(up_a[i]))
    gp["moved"] = int(c2[1])
    gp["nn"] = nn_l
    gp["pm"] = pm
    tl["t22b"] = gp


def _count_arrivals(p, off, idx):
    # An upper bound of the month's arrivals: the cells with an unaged mass (each brings at most one arrival)
    n = len(p.tr_pt_mass)
    og = p.tr_pt_og[:n * AGE_SLOTS * NS]
    return int(np.count_nonzero(og > 0))


def _t22_new_point(p, w, g, v, code):
    h = len(p.tr_pt_mass)
    if h + 1 > p.cap:
        p.grow(1)
    p.tr_pt_mass.append(0)
    p.tr_pt_code.append(code)
    p.tr_pt_q.append(p.tr_pt_q[g])
    p.tr_pt_muq.append(0.0)
    p.tr_pt_mug.append(0.0)
    p.tr_pt_id.append(p.tr_pt_next)
    p.tr_pt_next += 1
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
    p.tr_age_counts = np.concatenate([p.tr_age_counts, np.zeros(AGE_SLOTS, dtype=np.int64)])
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


def _qtab(p, mu):
    out = np.zeros(M.AGES * 2 * NG * 4, dtype=np.float64)
    inf = np.zeros(M.AGES * 2, dtype=np.bool_)
    for ix in range(M.AGES * 2):
        if mu[ix] == M.INF:
            inf[ix] = True
            continue
        a = ix // 2
        for gr in range(NG):
            for k in range(4):
                out[(ix * NG + gr) * 4 + k] = M.lc_death_q(p, p.tr_c[ix], a, gr, k, mu[ix], 12.0)
    return out, inf


def _t22_deaths(p, w):
    tl = w["tally"]
    mu = M.mu_path(p)
    lists = w["lists"]
    U = p.tr_units
    ub, us = _unit_bs(p)
    off, idx = _flat(lists, U)
    qtab, mu_inf = _qtab(p, mu)
    led = np.array(w["led_death"], dtype=np.int64)
    arrs = {k: np.array(tl[k], dtype=np.float64) for k in ("x_as", "e_as", "v_as", "x_g", "x_k")}
    iarrs = {k: np.array(tl[k], dtype=np.int64) for k in ("d_as", "d_old", "d_g", "d_k")}
    dead = np.zeros(len(idx), dtype=np.int64)
    dead_g = np.zeros((len(idx), NG), dtype=np.int64)
    nbk.death_cells(p.month, ub, us, U, off, idx, np.array(p.tr_pt_mass, dtype=np.int64), np.array(p.tr_pt_id, dtype=np.int64),
                    np.array(p.tr_pt_q, dtype=np.int64), p.tr_pt_ag, p.tr_pt_og, p.tr_pt_old, p.tr_pt_age, p.tr_age_counts, qtab, mu_inf,
                    np.uint64(keyed.head(p.seed_v, "t22_death")), np.uint64(keyed.head(p.seed_v, "t22_death_old")), led,
                    arrs["x_as"], arrs["e_as"], arrs["v_as"], arrs["x_g"], arrs["x_k"], iarrs["d_as"], iarrs["d_old"], iarrs["d_g"], iarrs["d_k"],
                    dead, dead_g)
    for k, a in arrs.items():
        tl[k] = a.tolist()
    for k, a in iarrs.items():
        tl[k] = a.tolist()
    w["led_death"] = led.tolist()
    _marital(p, w, ub, us, off, idx, dead, dead_g)


def _marital(p, w, ub, us, off, idx, dead_a, dead_g_a):
    # _t22_deaths' per-point part after its cells, in the same point order (month.py's code from "if dead <= 0")
    tl = w["tally"]
    unit_of = w["unit_of"]
    key = p.tr_key
    T = p.tr_pt_T
    ms = p.tr_pt_ms
    led = w["led_death"]
    hsp = M.hypergeometric_split
    for u in range(p.tr_units):
        b = int(ub[u])
        s = int(us[u])
        for j in range(int(off[u]), int(off[u + 1])):
            dead = int(dead_a[j])
            if dead <= 0:
                continue
            g = int(idx[j])
            id_ = p.tr_pt_id[g]
            dead_g = dead_g_a[j].tolist()
            tl["deaths"] = int(tl["deaths"]) + dead
            keep_fr = float(p.tr_pt_mass[g] - dead) / float(p.tr_pt_mass[g])
            p.tr_pt_muq[g] *= keep_fr
            p.tr_pt_mug[g] *= keep_fr
            p.tr_pt_mass[g] -= dead
            p.tr_count[u] -= dead
            married0 = int(ms[g * 4 + 1])
            md1 = [0] * NG
            for gr2 in range(NG):
                if dead_g[gr2] <= 0:
                    continue
                col = [int(T[g * 4 * NG + k2 * NG + gr2]) for k2 in range(4)]
                md = hsp(col, dead_g[gr2], p.seed_v, "t22_death_ms", (id_ * NG + gr2) * 1200 + p.month)
                for k3 in range(4):
                    led[(s * 9 + M._b10(b * 5)) * 4 * NG + k3 * NG + gr2] -= md[k3]
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
            holds.append(max(0, married0 - cm))
            y = hsp(holds, mdt, p.seed_v, "t22_death_cp", id_ * 1200 + p.month)
            for i in range(len(cps)):
                if y[i] <= 0:
                    continue
                c2 = cps[i]
                p.tr_cp_n[c2] -= y[i]
                other = p.tr_cp_h[c2] if p.tr_cp_w[c2] == g else p.tr_cp_w[c2]
                wv = min(y[i], int(ms[other * 4 + 1]))
                tl["couples_lost"] = int(tl["couples_lost"]) + y[i]
                if wv <= 0:
                    continue
                row1 = []
                n1 = 0
                for g3 in range(NG):
                    row1.append(int(T[other * 4 * NG + NG + g3]))
                    n1 += row1[g3]
                wg = hsp(row1, wv, p.seed_v, "t22_widow", (p.tr_pt_id[other] * 1200 + p.month) * 64 + c2 % 64)
                uo = unit_of[other]
                wx = (key[uo * KEY_STRIDE + 2] * 9 + M._b10(key[uo * KEY_STRIDE + 1] * 5)) * NG
                lw = (key[uo * KEY_STRIDE + 2] * 9 + M._b10(key[uo * KEY_STRIDE + 1] * 5)) * 4 * NG
                for g4 in range(NG):
                    led[lw + NG + g4] -= wg[g4]
                    led[lw + 2 * NG + g4] += wg[g4]
                    T[other * 4 * NG + NG + g4] -= wg[g4]
                    T[other * 4 * NG + 2 * NG + g4] += wg[g4]
                    pr = float(row1[g4]) / float(n1)
                    tl["wg_x"][wx + g4] += float(wg[g4])
                    tl["wg_e"][wx + g4] += float(wv) * pr
                    tl["wg_v"][wx + g4] += float(wv) * pr * (1.0 - pr) * float(n1 - wv) / float(max(1, n1 - 1))
                    for dg in range(NG):
                        tl["wg_n"][(wx + dg) * NG + g4] += float(wg[g4]) * float(md1[dg]) / float(mdt)
                ms[other * 4 + 1] -= wv
                ms[other * 4 + 2] += wv
                tl["widowed"] = int(tl["widowed"]) + wv


def _t22_totals(p, w, l):
    # Why int64 sums and not month.py's float loop: the terms are integers and their sums stay below 2^53, so the float sums are
    # exact and equal to these in any order (the bound asserted)
    gi = np.array(l, dtype=np.int64)
    S2 = AGE_SLOTS * NS
    parts = []
    parts.append(p.tr_pt_age.reshape(-1, AGE_SLOTS)[gi].sum(axis=0))
    parts.append(p.tr_pt_jan.reshape(-1, AGE_SLOTS)[gi].sum(axis=0))
    parts.append(p.tr_pt_old.reshape(-1, AGE_SLOTS)[gi].sum(axis=0))
    parts.append(p.tr_pt_ms.reshape(-1, 4)[gi].sum(axis=0))
    cp = 0
    hm = 0
    for g in l:
        for c in w["cp_of"][g]:
            cp += p.tr_cp_n[c]
        for e in w["hm_of"][g]:
            hm += p.tr_hm_n[e]
    ins = [sum(w["ins"][name][g] for g in l) for name in w["ins"]]
    parts.append(np.array([cp, hm] + ins, dtype=np.int64))
    parts.append(p.tr_pt_ag.reshape(-1, S2)[gi].sum(axis=0))
    parts.append(p.tr_pt_jg.reshape(-1, S2)[gi].sum(axis=0))
    parts.append(p.tr_pt_og.reshape(-1, S2)[gi].sum(axis=0))
    parts.append(p.tr_pt_T.reshape(-1, 4 * NG)[gi].sum(axis=0))
    out = np.concatenate(parts)
    assert all(abs(x) < (1 << 53) for x in ins) and int(np.abs(out).max(initial=0)) < (1 << 53)
    return out.tolist()


def _t22_merge(p, w, i, k, u):
    mc = p.month % 12
    b = p.tr_key[u * KEY_STRIDE + 1]
    og = p.tr_pt_og
    S2 = AGE_SLOTS * NS
    idk = p.tr_pt_id[k]
    idi = p.tr_pt_id[i]
    if mc < 11:
        both = np.nonzero(og[i * S2:(i + 1) * S2] + og[k * S2:(k + 1) * S2] > 0)[0]
    else:
        both = np.zeros(0, dtype=np.int64)
    bset = set(int(x) for x in both)
    for s0 in range(AGE_SLOTS):
        for sb in range(NS):
            cx = s0 * NS + sb
            rd = (idk * AGE_SLOTS + s0) * NS + sb
            if cx in bset:
                ri = M._t22_rem(p, i, s0, sb, b * 5 + s0, mc)
                rk2 = M._t22_rem(p, k, s0, sb, b * 5 + s0, mc)
                for m2 in range(12):
                    ri[m2] += rk2[m2]
                p.tr_pt_rem[(idi * AGE_SLOTS + s0) * NS + sb] = ri
            p.tr_pt_rem.pop(rd, None)
    p.tr_pt_muq[i] += p.tr_pt_muq[k]
    p.tr_pt_muq[k] = 0.0
    p.tr_pt_mug[i] += p.tr_pt_mug[k]
    p.tr_pt_mug[k] = 0.0
    p.tr_pt_mass[i] += p.tr_pt_mass[k]
    p.tr_pt_mass[k] = 0
    for name, st in CELL.items():
        a = getattr(p, name)
        if name in ("tr_pt_age", "tr_pt_jan", "tr_pt_old", "tr_pt_ms"):
            a[i * st:(i + 1) * st] += a[k * st:(k + 1) * st]
        else:
            a[i * st:(i + 1) * st] += a[k * st:(k + 1) * st]
            a[k * st:(k + 1) * st] = 0
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


for _name in ("grade_table", "_t22_age", "_t22_new_point", "_t22_new_unit", "_t22_deaths", "_t22_totals", "_t22_merge"):
    setattr(M, _name, globals()[_name])
_rebuild_base = M._t22_rebuild
M._t22_rebuild = lambda p, w: _rebuild_nb(p, w)


def _rebuild_nb(p, w):
    lists = w["lists"]
    order = []
    for u in range(p.tr_units):
        for g in lists[u]:
            if p.tr_pt_mass[g] > 0:
                order.append(g)
    oi = np.array(order, dtype=np.int64)
    no = len(order)
    cap = no
    newa = {}
    for name, st in CELL.items():
        src = getattr(p, name).reshape(-1, st)
        a = np.zeros(cap * st, dtype=np.int32)
        a[:no * st] = src[oi].reshape(-1)
        newa[name] = a
    for name in CELL:
        setattr(p, name, [])
    _rebuild_base(p, w)
    for name in CELL:
        setattr(p, name, newa[name])
    p.cap = cap


def step(p):
    if p.month % 12 == 0:
        p.tr_pt_jan = p.tr_pt_age.copy()
        p.tr_pt_old = p.tr_pt_age.copy()
        p.tr_pt_jg = p.tr_pt_ag.copy()
        p.tr_pt_og = p.tr_pt_ag.copy()
        p.tr_pt_rem = {}
        # Why not month.py's step: its January block copies with list(), which would turn these buffers into lists
    _step_rest(p)


def _step_rest(p):
    import time
    st = {}
    t = [time.perf_counter()]  # lint-ok: per-stage seconds into p.timing, never digested

    def lap(name):
        now = time.perf_counter()  # lint-ok: per-stage seconds into p.timing, never digested
        st[name] = st.get(name, 0.0) + now - t[0]
        t[0] = now
    w = M._t22_work(p)
    tl = w["tally"]
    lap("work")
    g0 = M.grade_table(p, [])
    lap("tables")
    M._t22_age(p, w)
    lap("ageing")
    g1 = M.grade_table(p, w["lists"])
    lap("tables")
    M._t22_deaths(p, w)
    lap("deaths and widowing")
    g2 = M.grade_table(p, w["lists"])
    lap("tables")
    if p.month % 12 == 0:
        p.tr_kb = M._targets(p)
    M._t22_quartiles_w(p, w)
    lap("quartiles")
    M._t22_compress(p, w)
    lap("C1 and C2")
    M._t22_rebuild(p, w)
    lap("rebuild")
    g3 = M.grade_table(p, [])
    lap("tables")
    M._t22_c5(p, w)
    lap("C5")
    g4 = M.grade_table(p, [])
    led_none = M._zi(len(g0))
    gxs = {"ageing and the re-grade": M._gx_off(g0, g1, w["led_age"]), "deaths and widowing": M._gx_off(g1, g2, w["led_death"]),
           "C1, C2 and the rebuild": M._gx_off(g2, g3, led_none), "C5": M._gx_off(g3, g4, led_none)}
    tl["gx_by_stage"] = gxs
    tl["gx"] = int(gxs["ageing and the re-grade"]) + int(gxs["deaths and widowing"]) + int(gxs["C1, C2 and the rebuild"]) + int(gxs["C5"])
    lap("tables")
    p.timing = st
    p.tr_margins["t22"] = tl


_c5_base = M._t22_c5
_keys_base = M._t22_c5_keys
_kcache = {}


def _c5_keys_cached(p, c, unit_of):
    # Why a cache is exact: a couple cell's keys read its points' quartile, employment and unit band, which C5 never writes
    k = _kcache.get(c)
    if k is None:
        k = _keys_base(p, c, unit_of)
        _kcache[c] = k
    return k


def _t22_c5_nb(p, w):
    _kcache.clear()
    try:
        _c5_base(p, w)
    finally:
        _kcache.clear()


def _perm_np(src, order, st):
    if len(src) == 0:
        return []
    a = np.asarray(src)
    o = np.asarray(order, dtype=np.int64)
    idx = (o[:, None] * st + np.arange(st, dtype=np.int64)[None, :]).reshape(-1)
    out = a[idx]
    return M.array(src.typecode, out.tobytes()) if isinstance(src, M.array) else out.tolist()


M._t22_c5_keys = _c5_keys_cached
M._t22_c5 = _t22_c5_nb
M._perm = _perm_np


def _t22_c5_kernel(p, w):
    import math
    tl = w["tally"]
    n_pts = p.tr_pt_off[p.tr_units]
    unit_of = np.zeros(n_pts, dtype=np.int64)
    poff = np.array(p.tr_pt_off, dtype=np.int64)
    unit_of[:] = np.repeat(np.arange(p.tr_units), np.diff(poff))
    cw = np.array(p.tr_cp_w, dtype=np.int64)
    ch = np.array(p.tr_cp_h, dtype=np.int64)
    cn = np.array(p.tr_cp_n, dtype=np.int64)
    chh = np.array(p.tr_cp_hh, dtype=np.int64)
    ids = np.array(p.tr_pt_id, dtype=np.int64)
    q = np.array(p.tr_pt_q, dtype=np.int64)
    emp = np.asarray(p.tr_points["employment"]).astype(np.int64)
    work = (emp == M.EMP_REGULAR) | (emp == M.EMP_NONREGULAR)
    ub = np.array(p.tr_key, dtype=np.int64).reshape(-1, KEY_STRIDE)[:, 1]
    hb10 = np.minimum((ub[unit_of[ch]] * 5) // 10, 8)
    key1 = (q[cw] * 4 + q[ch]) * 9 + hb10
    key2 = np.where(work[cw] & work[ch], 144 + hb10, -1)
    order = np.argsort(chh, kind="stable")
    hbs, starts = np.unique(chh[order], return_index=True)
    boff = np.append(starts, len(order)).astype(np.int64)
    caps = np.zeros(len(hbs), dtype=np.int64)
    for i, hb in enumerate(hbs.tolist()):
        cells = order[boff[i]:boff[i + 1]]
        npw = len(set(cw[cells].tolist()))
        nph = len(set(ch[cells].tolist()))
        caps[i] = max(int(p.tr_cp_cap.get(int(hb), 0)), int(math.ceil(1.5 * float(npw + nph - 1))))
    # Why the two orders are taken here: tiers.gd sorts a block's cells by (-n, wife id, husband id, cell) and its off-forest cells by
    # (n, ...) before any move in that block, and blocks share no cell, so both orders read the month's starting n
    pos = np.empty(len(order), dtype=np.int64)
    blk = np.repeat(np.arange(len(hbs)), np.diff(boff))
    pos[order] = np.arange(len(order)) - boff[blk]
    cells_all = np.arange(len(cn), dtype=np.int64)
    bof = np.empty(len(cn), dtype=np.int64)
    bof[order] = blk
    desc = np.lexsort((cells_all, ids[ch], ids[cw], -cn, bof))
    asc = np.lexsort((cells_all, ids[ch], ids[cw], cn, bof))
    bdesc = pos[desc]
    basc = pos[asc]
    c5_r = np.array(tl["c5_r"], dtype=np.float64)
    c5_v = np.array(tl["c5_v"], dtype=np.float64)
    cnt = np.zeros(4, dtype=np.int64)
    nbk.c5_blocks(p.month, boff, order.astype(np.int64), bdesc, basc, caps, hbs.astype(np.int64), cw, ch, cn, ids[cw], ids[ch], key1, key2,
                  np.uint64(keyed.head(p.seed_v, "t22_c5")), c5_r, c5_v, cnt)
    tl["cp_blocks_capped"] = int(tl["cp_blocks_capped"]) + int(cnt[0])
    tl["c5_over"] = int(tl["c5_over"]) + int(cnt[1])
    tl["c5_x"] = int(tl["c5_x"]) + int(cnt[2])
    tl["c5_moves"] = int(tl["c5_moves"]) + int(cnt[3])
    tl["c5_r"] = c5_r.tolist()
    tl["c5_v"] = c5_v.tolist()
    keep = cn > 0
    p.tr_cp_hh = _arr("i", chh[keep])
    p.tr_cp_w = _arr("i", cw[keep])
    p.tr_cp_h = _arr("i", ch[keep])
    p.tr_cp_n = _arr("i", cn[keep])


def _t22_cap_nb(p, w, u, l, kb):
    # month.py's _t22_cap with the pair search in nbk.cap_best; z (zrow is the identity) and the merges as there
    tl = w["tally"]
    n = len(l)
    num = []
    for name in ("income", "assets"):
        arr = p.tr_points[name]
        idx = sorted(range(n), key=lambda i: (float(arr[l[i]]), i))
        r = M._zf(n)
        for k in range(n):
            r[idx[k]] = float(k) / float(max(1, n - 1))
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
    numa = np.array(num, dtype=np.float64)
    nsca = np.array(nsc, dtype=np.float64)
    cata = np.array(cat, dtype=np.int64)
    csca = np.array(csc, dtype=np.float64)
    comp = np.array([M._t22_comp(p, w, int(g)) for g in l], dtype=np.float64)
    alive = np.array(l, dtype=np.int64)
    qa = np.array([p.tr_pt_q[g] for g in l], dtype=np.int64)
    ma = np.array([float(p.tr_pt_mass[g]) for g in l], dtype=np.float64)
    left = n
    b10 = M._b10(p.tr_key[u * KEY_STRIDE + 1] * 5)
    hd_m = keyed.head(p.seed_v, "t22_merge")
    pq = p.tr_pt_q
    mass = p.tr_pt_mass
    while left > kb:
        per_q = [0, 0, 0, 0]
        for g5 in alive:
            if g5 >= 0:
                per_q[pq[g5]] += 1
        cross_ok = per_q[0] <= 1 and per_q[1] <= 1 and per_q[2] <= 1 and per_q[3] <= 1
        bi, bj = nbk.cap_best(alive, qa, ma, numa, nsca, cata, csca, comp, cross_ok)
        gi = int(alive[bi])
        gj = int(alive[bj])
        lo = bi if p.tr_pt_id[gi] < p.tr_pt_id[gj] else bj
        hi = bj if lo == bi else bi
        glo = int(alive[lo])
        ghi = int(alive[hi])
        wl = float(mass[glo])
        wh = float(mass[ghi])
        ku = float(keyed.h64(hd_m, u, p.month, p.tr_pt_id[glo] * 100000000 + p.tr_pt_id[ghi]) >> 11) / keyed.TWO53
        keep = lo if ku * (wl + wh) < wl else hi
        drop = hi if keep == lo else lo
        gk = int(alive[keep])
        gd = int(alive[drop])
        if pq[gk] != pq[gd]:
            tl["cbq"] = int(tl["cbq"]) + 1
            tl["cbq_mass"] = int(tl["cbq_mass"]) + mass[gk] + mass[gd]
        M._t22_cb(p, w, gk, gd, b10, wl, wh)
        M._t22_book_mu(p, gk, gd, wl, wh, keep == lo)
        M._t22_merge(p, w, gk, gd, u)
        comp[keep] = M._t22_comp(p, w, gk)
        ma[keep] = float(mass[gk])
        alive[drop] = -1
        left -= 1
        tl["c2"] = int(tl["c2"]) + 1
    return [int(g4) for g4 in alive if g4 >= 0]


def _rebuild_tail_np(p, w, order, nid):
    # The rebuild's couple and household entries (month.py's loops) as integer NumPy steps: the same filters, the first-seen order
    # of each key, the duplicates' masses summed
    no = len(order)
    cn = np.array(p.tr_cp_n, dtype=np.int64)
    cw = np.array(p.tr_cp_w, dtype=np.int64)
    ch = np.array(p.tr_cp_h, dtype=np.int64)
    chh = np.array(p.tr_cp_hh, dtype=np.int64)
    pos = cn > 0
    a = np.where(pos, nid[cw], -1)
    b = np.where(pos, nid[ch], -1)
    good = pos & (a >= 0) & (b >= 0)
    lost = int(cn[pos & ~good].sum())
    gi = np.nonzero(good)[0]
    ck = (a[gi] * no + b[gi]) * (len(p.tr_hh_keys) + 1) + chh[gi]
    uk, first, inv = np.unique(ck, return_index=True, return_inverse=True)
    sums = np.bincount(inv, weights=None, minlength=len(uk)).astype(np.int64) * 0
    np.add.at(sums, inv, cn[gi])
    fo = np.argsort(first, kind="stable")
    src = gi[first[fo]]
    p.tr_cp_hh = _arr("i", chh[src])
    p.tr_cp_w = _arr("i", a[src])
    p.tr_cp_h = _arr("i", b[src])
    p.tr_cp_n = _arr("i", sums[fo])
    hn = np.array(p.tr_hm_n, dtype=np.int64)
    hp = np.array(p.tr_hm_pt, dtype=np.int64)
    hr = np.array(p.tr_hm_role, dtype=np.int64)
    hmh = np.array(w["hm_h"], dtype=np.int64)
    pos2 = hn > 0
    np2 = np.where(pos2, nid[hp], -1)
    good2 = pos2 & (np2 >= 0)
    lost_hm = int(hn[pos2 & ~good2].sum())
    e = np.nonzero(good2)[0]
    e = e[np.lexsort((e, hmh[e]))]
    hk = (hmh[e] * no + np2[e]) * 8 + hr[e]
    uk2, first2, inv2 = np.unique(hk, return_index=True, return_inverse=True)
    sums2 = np.zeros(len(uk2), dtype=np.int64)
    np.add.at(sums2, inv2, hn[e])
    fo2 = np.argsort(first2, kind="stable")
    src2 = e[first2[fo2]]
    nk = len(p.tr_hh_keys)
    hh_of = hmh[src2]
    hoff = np.searchsorted(hh_of, np.arange(nk + 1), side="left")
    p.tr_hm_off = _arr(M.TYPECODE[p.kinds["tr_hm_off"]], hoff)
    p.tr_hm_pt = _arr("i", np2[src2])
    p.tr_hm_role = _arr("i", hr[src2])
    p.tr_hm_n = _arr("i", sums2[fo2])
    w["tally"]["lost"] = lost
    w["tally"]["lost_hm"] = lost_hm


def _rebuild_nb2(p, w):
    lists = w["lists"]
    order = []
    off = []
    for u in range(p.tr_units):
        off.append(len(order))
        for g in lists[u]:
            if p.tr_pt_mass[g] > 0:
                order.append(g)
    off.append(len(order))
    oi = np.array(order, dtype=np.int64)
    no = len(order)
    nid = np.full(len(p.tr_pt_mass), -1, dtype=np.int64)
    nid[oi] = np.arange(no)
    cap = no
    for name, st in CELL.items():
        src = getattr(p, name).reshape(-1, st)
        setattr(p, name, np.ascontiguousarray(src[oi].reshape(-1)))
    p.cap = cap
    p.tr_pt_off = _arr("q", off)
    for name in ("tr_pt_mass", "tr_pt_id", "tr_pt_code", "tr_pt_q", "tr_pt_muq", "tr_pt_mug"):
        src = getattr(p, name)
        setattr(p, name, _arr(src.typecode if isinstance(src, M.array) else ("d" if name in ("tr_pt_muq", "tr_pt_mug") else "i"), np.asarray(src)[oi]))
    for name in p.tr_points:
        p.tr_points[name] = _perm_np(p.tr_points[name], order, w["stride"][name])
    for name2 in w["ins"]:
        pts = _arr("q", np.asarray(w["ins"][name2], dtype=np.int64)[oi])
        pts.extend(w["ins_ind"][name2])
        p.tr_instruments[name2] = pts
    _rebuild_tail_np(p, w, order, nid)
    ids = set(p.tr_pt_id)
    for rk3 in list(p.tr_pt_rem.keys()):
        if (int(rk3) // (AGE_SLOTS * NS)) not in ids:
            del p.tr_pt_rem[rk3]
    M._point_wealth(p)


def _unit_totals(p, w, units, lists, chunk=3000):
    # T2s-cx's totals (month.py's _t22_totals) of every listed unit at once: segment sums over each unit's points of the cells, the
    # couple and household masses by point (an entry counts at each of its points, as cp_of and hm_of hold it) and the instruments
    # Why per-unit sums once and not per unit at its turn: a unit's compression writes only its own points' arrays and moves no
    # couple or household mass, so every unit's totals before (and after) read the same values either way
    n = len(p.tr_pt_mass)
    cpm = np.zeros(n, dtype=np.int64)
    cn = np.asarray(p.tr_cp_n, dtype=np.int64)
    np.add.at(cpm, np.asarray(p.tr_cp_w, dtype=np.int64), cn)
    np.add.at(cpm, np.asarray(p.tr_cp_h, dtype=np.int64), cn)
    hmm = np.zeros(n, dtype=np.int64)
    np.add.at(hmm, np.asarray(p.tr_hm_pt, dtype=np.int64), np.asarray(p.tr_hm_n, dtype=np.int64))
    S2 = AGE_SLOTS * NS
    cols = [p.tr_pt_age[:n * AGE_SLOTS].reshape(n, AGE_SLOTS), p.tr_pt_jan[:n * AGE_SLOTS].reshape(n, AGE_SLOTS),
            p.tr_pt_old[:n * AGE_SLOTS].reshape(n, AGE_SLOTS), p.tr_pt_ms[:n * 4].reshape(n, 4), cpm.reshape(n, 1), hmm.reshape(n, 1)]
    for name in w["ins"]:
        cols.append(np.asarray(w["ins"][name], dtype=np.int64).reshape(n, 1))
    cols += [p.tr_pt_ag[:n * S2].reshape(n, S2), p.tr_pt_jg[:n * S2].reshape(n, S2), p.tr_pt_og[:n * S2].reshape(n, S2),
             p.tr_pt_T[:n * 4 * NG].reshape(n, 4 * NG)]
    ncol = sum(c.shape[1] for c in cols)
    parts = []
    for i in range(0, len(units), chunk):
        seg = [lists[u] for u in units[i:i + chunk]]
        lens = np.array([len(x) for x in seg], dtype=np.int64)
        idx = np.fromiter((g for x in seg for g in x), dtype=np.int64, count=int(lens.sum()))
        starts = np.concatenate([[0], np.cumsum(lens)[:-1]]).astype(np.int64)
        mat = np.concatenate([c[idx] for c in cols], axis=1)
        parts.append(np.add.reduceat(mat, starts, axis=0))
    out = np.concatenate(parts, axis=0) if parts else np.zeros((0, ncol), dtype=np.int64)
    assert int(np.abs(out).max(initial=0)) < (1 << 53)
    return out


def _t22_compress_nb(p, w):
    lists = w["lists"]
    tl = w["tally"]
    todo = []
    for u in range(p.tr_units):
        l = []
        for g in lists[u]:
            if p.tr_pt_mass[g] > 0:
                l.append(g)
            else:
                tl["dropped"] = int(tl["dropped"]) + 1
        lists[u] = l
        if len(l) > 1:
            todo.append(u)
    before = _unit_totals(p, w, todo, lists)
    for u in todo:
        l = M._t22_coalesce(p, w, u, lists[u])
        kb = M.cap_target(p, u, l)
        if len(l) > int(M.math.ceil(1.5 * float(kb))):
            l = M._t22_cap(p, w, u, l, kb)
        lists[u] = l
    after = _unit_totals(p, w, todo, lists)
    tl["cx_bad"] = int(tl["cx_bad"]) + int(np.any(before != after, axis=1).sum())


if os.environ.get("TIERS_CX") != "py":
    M._t22_compress = _t22_compress_nb
if os.environ.get("TIERS_C2") != "py":
    M._t22_cap = _t22_cap_nb
if os.environ.get("TIERS_RB") != "py":
    M._t22_rebuild = _rebuild_nb2
if os.environ.get("TIERS_C5") != "py":
    M._t22_c5 = _t22_c5_kernel
