# The Numba twins (core/nb.py) on P0 and P1's rows: the same SHA-256s as the GDScript oracle's (L1_GDSCRIPT_PARITY.txt), with
# prims' samplers and DetMath swapped for the compiled ones
#   python py/tests/test_nb_twins.py
import time

import numpy as np

import test_p01_primitives as t
from common import Kit, f_bits, sha_i64
from core import detmath, keyed, nb, prims


def main():
    kit = Kit("py/tests/test_nb_twins.py")
    want = t.oracle()
    for name, f in (("exp", nb.exp), ("log", nb.log), ("inv_normal", nb.inv_normal)):
        xs = [keyed.u(9, "nb_" + name, j, 0, 0) * (40.0 if name == "exp" else 1.0) - (20.0 if name == "exp" else 0.0) for j in range(200000)]
        xs += [0.0, 1e-300, 5e-324, 1.0, 2.0, 1e300, 0.075, 0.925]
        ref = getattr(detmath, name)
        bad = sum(1 for x in xs if f_bits([f(x)]) != f_bits([ref(x)]) and not (ref(x) != ref(x) and f(x) != f(x)))
        kit.check(bad == 0, "nb.%s against detmath.%s at %d inputs: %d differ" % (name, name, len(xs), bad))
    xs = [(1.0 - detmath.pow(10.0, -6.0 * keyed.u(13, "nb_pow", j, 0, 0)) * 0.5, float(1 + keyed.below(1000000 if j % 2 else 64, 13, "nb_pe", j, 0, 0))) for j in range(200000)]
    bad = sum(1 for q, e in xs if f_bits([nb.pow_(q, e)]) != f_bits([detmath.pow(q, e)]))
    kit.check(bad == 0, "nb.pow_ against detmath.pow at %d inputs: %d differ" % (len(xs), bad))
    hd = np.uint64(keyed.head(1, "nb_u"))
    bad = sum(1 for j in range(200000) if nb.u_from(hd, j * 7919, -j, j) != keyed.u(1, "nb_u", j * 7919, -j, j))
    kit.check(bad == 0, "nb.u_from against keyed.u at 200000 keys (negative b included): %d differ" % bad)
    prims.binomial = nb.binomial
    prims.hypergeometric = nb.hypergeometric
    rows = [("E1-b DM-b grid and switch cells x 10^5 keyed u", t.dm_b), ("E1-b DM-b sampler CDF boundaries at n p q >= 12", t.dm_b_tv),
            ("E1-inv DM-b inversion CDF boundaries at n p q < 12", t.dm_b_inv), ("E1-hg HG-b cells", t.hg_b), ("E1-inv HG-b inversion CDF boundaries below the switch", t.hg_b_inv)]
    for label, fn in rows:
        t0 = time.perf_counter()
        got = fn()
        kit.check(got == want[label], "nb P1 %s: %s, gdscript %s (%.1f s)" % (label, got[:16], want[label][:16], time.perf_counter() - t0))
    holds = np.array([3, 0, 17, 250, 1, 40, 9, 1200], dtype=np.int64)
    out = np.zeros(8, dtype=np.int64)
    hda = np.uint64(keyed.head(1, "hg_a"))
    vals = []
    import hashlib
    h = hashlib.sha256()
    t0 = time.perf_counter()
    for d in [1, 7, 300, int(holds.sum())]:
        acc = np.zeros(100000 * 8, dtype=np.int64)
        for r in range(100000):
            nb.hypergeometric_split(holds, d, hda, d * 100000 + r, out)
            acc[r * 8:(r + 1) * 8] = out
        h.update(acc.tobytes())
    got = h.hexdigest()
    kit.check(got == want["E1-hg HG-a splits"], "nb P1 E1-hg HG-a splits: %s, gdscript %s (%.1f s)" % (got[:16], want["E1-hg HG-a splits"][:16], time.perf_counter() - t0))
    kit.finish()


if __name__ == "__main__":
    main()
