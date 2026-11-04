# P0 and P1 (PY_TRIAL_PLAN §4): native/test_tier_parity.gd's E0, E1 and E1-inv inputs replayed through the Python twin; each row's
# SHA-256 equals the GDScript one recorded in docs/team/modern/py/L1_GDSCRIPT_PARITY.txt (a copy of docs/team/modern/cpp/L1_LINUX_PARITY.txt)
#   python3 py/tests/test_p01_primitives.py
import hashlib
import math
import os
import re
import sys
import time

from common import Kit, ROOT, f_bits, i64_bytes, sha_i64
from tiers import detmath, keyed, prims
from tiers.gd import gd_round, maxi, mini, maxf, minf

N_KEYS = 20000
DRAWS = 100000
NS = [1, 3, 10, 30, 100, 1000, 10000, 100000, 1000000]
PS = [1e-6, 1e-4, 1e-2, 0.1, 0.3, 0.5, 0.8]
SW_V = [8.0, 9.0, 10.0, 11.0, 11.99, 12.0, 12.5, 13.0]
BITS = [[1, 0.5, 0.3, 0], [10, 0.1, 0.95, 3], [100, 0.3, 0.5, 30], [1000, 0.01, 0.99, 18], [1000000, 1e-06, 0.7, 1], [1000000, 0.5, 0.123, 499420],
        [50, 0.8, 0.42, 40], [30, 0.5, 0.999999, 27], [200, 0.06, 0.0001, 2], [5000, 0.002, 0.5, 10]]


def oracle():
    out = {}
    for line in open(os.path.join(ROOT, "docs/team/modern/py/L1_GDSCRIPT_PARITY.txt"), encoding="utf-8"):
        m = re.match(r"^ok   (.*?): .*sha256 gdscript ([0-9a-f]{64})", line)
        if m:
            out[m.group(1)] = m.group(2)
    return out


def cells():
    out = [[n, p] for n in NS for p in PS]
    for v in SW_V:
        for p2 in [1e-4, 0.01, 0.5, 0.8]:
            out.append([int(math.ceil(v / (p2 * (1.0 - p2)))), p2])
    return out


def boundary(draw, k):
    a = 0.0
    b = 1.0
    for _ in range(60):
        m = 0.5 * (a + b)
        if draw(m) <= k:
            a = m
        else:
            b = m
    return f_bits([0.5 * (a + b)])[0]


def hg_var(n, k, d):
    return float(d) * k / n * (1.0 - float(k) / n) * float(n - d) / float(n - 1)


def hg_d(n, k, target):
    lo = 1
    hi = n // 2
    while lo < hi:
        m = (lo + hi) // 2
        if hg_var(n, k, m) >= target:
            hi = m
        else:
            lo = m + 1
    return lo


def cell_value(tag, a, b):
    kind = keyed.below(5, 21, tag + "/kind", a, b, 0)
    base = float(keyed.below(30, 21, tag + "/int", a, b, 0))
    if kind == 0:
        return 0.0
    if kind == 1:
        return base
    if kind == 2:
        return base + 1e-10
    if kind == 3:
        return maxf(0.0, base - 1e-10)
    return base * keyed.u(21, tag + "/frac", a, b, 0) + keyed.u(21, tag + "/frac2", a, b, 0)


def keyed_vec(tag, t):
    return [cell_value(tag, t, i) for i in range(keyed.below(12, 21, tag + "/len", t, 0, 0))]


def keyed_holds(tag, t):
    return [0 if keyed.below(4, 21, tag + "/z", t, i, 0) == 0 else keyed.below(2000, 21, tag + "/h", t, i, 0)
            for i in range(keyed.below(12, 21, tag + "/len", t, 0, 0))]


def e0_rows():
    rows = []
    rows.append(("E0 keyed raw", [keyed.raw(7, "e0_raw", j, -j, j * 31) for j in range(N_KEYS)]))
    rows.append(("E0 keyed u (a UTF-8 tag)", f_bits([keyed.u(-3, "e0_u/ü", j * 1000003, j, 0) for j in range(N_KEYS)])))
    rows.append(("E0 keyed below (n 1, 7, 1000, 2^40)", [keyed.below(m, 11, "e0_below", j, m, 0) for m in [1, 7, 1000, 1 << 40] for j in range(N_KEYS)]))
    rows.append(("E0 keyed normal", f_bits([keyed.normal(5, "e0_normal", j, 0, 0) for j in range(N_KEYS)])))
    ps = [0.0, -1.0, 1.0, 2.0, 1.0 / 9007199254740992.0, 1.0 - 1.0 / 9007199254740992.0, 0.075, 0.925, 0.0749999999, 0.9250000001, 0.5, 1e-300, 1e-20, 1.0 - 1e-16]
    ps += [keyed.u(9, "e0_inv", j, 0, 0) for j in range(N_KEYS)]
    rows.append(("E0 inv_normal (keyed u, tails, branch edges)", f_bits([detmath.inv_normal(p) for p in ps])))
    pw = []
    for j in range(N_KEYS):
        q = 1.0 - detmath.pow(10.0, -6.0 * keyed.u(13, "e0_pow_p", j, 0, 0)) * 0.5
        e = float(1 + keyed.below(1000000 if j % 2 == 0 else 64, 13, "e0_pow_n", j, 0, 0))
        pw.append(detmath.pow(q, e))
    rows.append(("E0 DetMath.pow at (q, n) as binomial reads them", f_bits(pw)))
    return rows


def dm_b():
    h = hashlib.sha256()
    for nn, pp in cells():
        key2 = int(pp * 1e9)
        h.update(i64_bytes([prims.binomial(nn, pp, keyed.u(1, "dm_b", nn, key2, j)) for j in range(DRAWS)]))
    return h.hexdigest()


def dm_b_tv():
    h = hashlib.sha256()
    for nn, pp in cells():
        if nn * pp * (1.0 - pp) < prims.BINOM_SWITCH:
            continue
        mu = nn * pp
        sd = math.sqrt(nn * pp * (1.0 - pp))
        lo = maxi(0, int(math.floor(mu - 9.0 * sd)))
        hi = mini(nn, int(math.ceil(mu + 9.0 * sd)))
        draw = lambda u, nn=nn, pp=pp: prims.binomial(nn, pp, u)
        h.update(i64_bytes([boundary(draw, k) for k in range(maxi(0, lo - 1), hi + 1)]))
    return h.hexdigest()


def dm_b_inv():
    h = hashlib.sha256()
    for nn, pp in cells():
        pl = minf(pp, 1.0 - pp)
        if nn * pp * (1.0 - pp) >= prims.BINOM_SWITCH:
            continue
        hi = mini(nn, int(math.ceil(nn * pl + 9.0 * math.sqrt(nn * pp * (1.0 - pp)) + 40.0)))
        draw = lambda u, nn=nn, pp=pp: prims.binomial(nn, pp, u)
        lo = 0 if pl == pp else maxi(0, nn - hi)
        top = hi if pl == pp else nn
        h.update(i64_bytes([boundary(draw, k) for k in range(lo, top + 1)]))
    return h.hexdigest()


def hg_b_inv():
    n = 1000000
    h = hashlib.sha256()
    for v in SW_V:
        for frac2 in [1e-4, 0.01, 0.5]:
            k = int(gd_round(frac2 * n))
            d = hg_d(n, k, v)
            var_x = hg_var(n, k, d)
            if var_x >= prims.BINOM_SWITCH:
                continue
            mean = float(d) * k / n
            hi = mini(mini(d, k), int(math.ceil(mean + 9.0 * math.sqrt(var_x) + 40.0)))
            draw = lambda u, k=k, d=d: prims.hypergeometric(n, k, d, u)
            h.update(i64_bytes([boundary(draw, x) for x in range(0, hi + 1)]))
    return h.hexdigest()


def hg_a():
    holds = [3, 0, 17, 250, 1, 40, 9, 1200]
    big_n = sum(holds)
    h = hashlib.sha256()
    for d in [1, 7, 300, big_n]:
        out = []
        for r in range(100000):
            out += prims.hypergeometric_split(holds, d, 1, "hg_a", d * 100000 + r)
        h.update(i64_bytes(out))
    return h.hexdigest()


def hg_b():
    n = 1000000
    cs = [[frac, prims.BINOM_SWITCH] for frac in [0.5, 0.1, 0.01, 1e-3, 1e-4]]
    for v in SW_V:
        for frac2 in [1e-4, 0.01, 0.5]:
            cs.append([frac2, v])
    h = hashlib.sha256()
    for frac, target in cs:
        k = int(gd_round(frac * n))
        d = hg_d(n, k, target)
        var_x = hg_var(n, k, d)
        out = []
        if var_x < prims.BINOM_SWITCH:
            for j2 in range(2000):
                out.append(prims.hypergeometric(n, k, d, keyed.u(1, "hg_b", d, k, j2)))
        else:
            mean = float(d) * k / n
            sd = math.sqrt(var_x)
            lo = maxi(0, int(math.floor(mean - 9.0 * sd)))
            hi = mini(mini(d, k), int(math.ceil(mean + 9.0 * sd)))
            draw = lambda u, k=k, d=d: prims.hypergeometric(n, k, d, u)
            out = [boundary(draw, x) for x in range(maxi(0, lo - 1), hi + 1)]
        h.update(i64_bytes(out))
    return h.hexdigest()


def merges():
    w = [5, 2, 900, 3, 40, 2, 77]
    x = [1.0, 9.0, 3.0, 12.0, 0.5, 7.0, 4.0]
    out = []
    for r in range(10000):
        m = prims.merge_least(w, x, 1, "t2s_c", r)
        out += m[0]
        out += f_bits(m[1])
    return sha_i64(out)


def dep_rounds():
    out = []
    for t in range(400):
        nr = 1 + keyed.below(9, 21, "dr_nr", t, 0, 0)
        nc = 1 + keyed.below(9, 21, "dr_nc", t, 0, 0)
        x = [cell_value("dr", t, i) for i in range(nr * nc)]
        rounded = [t]
        out += prims.dep_round(x, nr, nc, 21, "dr_tab", t, rounded)
        out.append(rounded[0])
    return sha_i64(out)


def systematics():
    out = []
    for t in range(3000):
        v = keyed_vec("sy", t)
        s = 0.0
        for x in v:
            s += x
        total = int(gd_round(s)) + keyed.below(5, 21, "sy_off", t, 0, 0) - 2
        out += prims.systematic(v, maxi(0, total), 21, "sy_tab", t)
        out.append(-1)
    return sha_i64(out)


def splits():
    out = []
    for t in range(3000):
        h = keyed_holds("sh", t)
        x = keyed.below(5000, 21, "sh_x", t, 0, 0) - 10
        out += prims.split_holds(h, x, 21, "sh_tab", t, t % 12)
        out.append(-1)
    return sha_i64(out)


def caps():
    out = []
    for t in range(3000):
        h = keyed_holds("ct", t)
        o = [keyed.below(2500, 21, "ct_o", t, i, 0) for i in range(len(h))]
        out += prims.cap_to(o, h)
        out.append(-1)
    return sha_i64(out)


def largests():
    out = []
    for t in range(3000):
        v = keyed_vec("lk", t)
        if not v:
            continue
        s = 0.0
        for x in v:
            s += math.floor(x)
        total = int(s) + keyed.below(len(v) + 1, 21, "lk_off", t, 0, 0)
        out += prims.largest_keyed(v, total, 21, "lk_tab", t, t % 7)
        out.append(-1)
    return sha_i64(out)


def bits_row():
    return sha_i64([prims.binomial(int(b[0]), float(b[1]), float(b[2])) for b in BITS])


def main():
    kit = Kit("py/tests/test_p01_primitives.py")
    want = oracle()
    kit.check(len(want) == 19, "the oracle's GDScript SHA-256s read from L1_GDSCRIPT_PARITY.txt: %d rows" % len(want))
    only = sys.argv[1:]
    for label, vals in e0_rows():
        got = sha_i64(vals)
        kit.check(got == want.get(label), "P0 %s: python %s, gdscript %s" % (label, got, want.get(label)))
    p1 = [("E1-b DM-b grid and switch cells x 10^5 keyed u", dm_b), ("E1-b DM-b recorded BITS", bits_row),
          ("E1-b DM-b sampler CDF boundaries at n p q >= 12", dm_b_tv), ("E1-inv DM-b inversion CDF boundaries at n p q < 12", dm_b_inv),
          ("E1-inv HG-b inversion CDF boundaries below the switch", hg_b_inv), ("E1-hg HG-a splits", hg_a), ("E1-hg HG-b cells", hg_b),
          ("E1-c T2s-c merges", merges), ("E1-r dep_round tables", dep_rounds), ("E1-r _systematic", systematics),
          ("E1-r split_holds", splits), ("E1-r cap_to", caps), ("E1-r largest_keyed", largests)]
    for label, fn in p1:
        if only and not any(o in label for o in only):
            continue
        t0 = time.perf_counter()
        got = fn()
        kit.check(got == want.get(label), "P1 %s: python %s, gdscript %s (%.2f s)" % (label, got, want.get(label), time.perf_counter() - t0))
    kit.finish()


if __name__ == "__main__":
    main()
