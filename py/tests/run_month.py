# P2 (PY_TRIAL_PLAN §4): the Python month from the oracle's S0, each month's tiers digest against oracle_dump.gd's per-field SHA-256s;
# on a mismatch, the differing fields are printed (and, where the oracle wrote that month's whole state, the first differing index)
#   python py/tests/run_month.py <oracle dir> [months]
import gc
import shutil
import json
import os
import sys
import time

import numpy as np

from common import Kit, peak_mb
from core import digest
from tiers import month, state
if os.environ.get("TIERS_NB") == "1":
    from tiers import month_nb as month


def first_diff(a, b):
    if isinstance(a, state.Packed) and isinstance(b, state.Packed):
        if a.kind != b.kind or len(a.a) != len(b.a):
            return "kind/len %s %d vs %s %d" % (a.kind, len(a.a), b.kind, len(b.a))
        idx = np.nonzero(a.a != b.a)[0]
        return "first index %d: %r vs %r (%d differ)" % (idx[0], a.a[idx[0]], b.a[idx[0]], len(idx)) if len(idx) else "equal values"
    if isinstance(a, dict) and isinstance(b, dict):
        ka, kb = set(a), set(b)
        if ka != kb:
            return "keys differ: only python %s, only oracle %s" % (sorted(ka - kb, key=str)[:5], sorted(kb - ka, key=str)[:5])
        for k in sorted(a, key=digest._sort_key):
            r = first_diff(a[k], b[k])
            if r != "equal values":
                return "key %r: %s" % (k, r)
        return "equal values"
    if type(a) != type(b):
        return "type %s vs %s" % (type(a).__name__, type(b).__name__)
    return "equal values" if a == b else "%r vs %r" % (a, b)


def norm(x):
    if isinstance(x, np.integer):
        return int(x)
    if isinstance(x, np.floating):
        return float(x)
    if isinstance(x, state.Packed):
        return [v.item() if hasattr(v, "item") else v for v in x.a]
    if isinstance(x, dict):
        return {k: norm(v) for k, v in x.items()}
    if isinstance(x, list):
        return [norm(v) for v in x]
    return x


def tally_diff(mine, ref):
    a = norm(mine)
    b = norm(ref)
    out = []
    for k in sorted(set(a) | set(b), key=str):
        if k not in a or k not in b:
            out.append("%s missing on %s" % (k, "python" if k not in a else "oracle"))
        elif repr(a[k]) != repr(b[k]):
            out.append(k)
    return out


def wait_for(path):
    # The oracle writes its month files while this reads them: a file counts as there once it exists, its size holds for 3 s and,
    # for a tally, it parses (a half-written tally failed json at month 26 of the decade)
    last = -1
    while True:
        if os.path.exists(path):
            sz = os.path.getsize(path)
            if sz == last and sz > 0:
                if not path.endswith(".json"):
                    return
                try:
                    with open(path, encoding="utf-8") as f:
                        json.load(f)
                    return
                except ValueError:
                    pass
            last = sz
        time.sleep(3)


def main():
    d = sys.argv[1]
    months = int(sys.argv[2]) if len(sys.argv) > 2 else 13
    kit = Kit("py/tests/run_month.py")
    t0 = time.perf_counter()
    start = os.environ.get("PY_RESUME") or os.path.join(d, "m00")
    p = month.St(state.load(start, as_lists=os.environ.get("TIERS_NB") != "1"))
    print("RSS after load %.0f MB" % (peak_mb()), flush=True)
    print("load %.1f s, units %d, points %d" % (time.perf_counter() - t0, p.tr_units, len(p.tr_pt_mass)), flush=True)
    dg0, hs0 = state.digest_st(p)
    m0 = p.month
    d0, ex0 = d, ()
    if os.environ.get("REF2") and m0 >= int(os.environ.get("SWITCH", "1000000")):
        d0 = os.environ["REF2"]
        ex0 = tuple(x for x in os.environ.get("EXCLUDE", "").split(",") if x)
    want0 = state.read_hashes(os.path.join(d0, "m%02d.sha.txt" % m0))
    bad0 = [n for n in want0 if hs0.get(n) != want0[n] and n not in ex0]
    kit.check(not bad0 and set(hs0) == set(want0), "P2 m%02d (the state read back from %s): fields differing %s" % (m0, os.path.basename(start), bad0[:8] or sorted(set(hs0) ^ set(want0))[:8]))
    save_every = int(os.environ.get("PY_SAVE_EVERY", "0"))
    for m in range(p.month + 1, months + 1):
        t1 = time.perf_counter()
        gc.collect()
        month.step(p)
        p.month += 1
        el = time.perf_counter() - t1
        if getattr(p, "timing", None):
            print("month %d by step %s" % (m, ", ".join("%s %.1f" % kv for kv in p.timing.items())), flush=True)
        print("month %d peak RSS so far %.0f MB" % (m, peak_mb()), flush=True)
        dg, hs = state.digest_st(p)
        # From month SWITCH on, the reference is REF2 (an oracle resumed from a checkpoint), compared without the EXCLUDE fields: the
        # GDScript save leaves them out or re-types them (TO_PM_PY, the resume check; the PM's rule of TO_E.md 07:17)
        dm = d
        excl = ()
        if os.environ.get("REF2") and m >= int(os.environ.get("SWITCH", "1000000")):
            dm = os.environ["REF2"]
            excl = tuple(x for x in os.environ.get("EXCLUDE", "").split(",") if x)
        wait_for(os.path.join(dm, "m%02d.sha.txt" % m))
        wait_for(os.path.join(dm, "m%02d.tally.json" % m))
        want = state.read_hashes(os.path.join(dm, "m%02d.sha.txt" % m))
        bad = [n for n in sorted(want) if hs.get(n) != want[n] and n not in excl]
        extra = ""
        if bad and os.path.isdir(os.path.join(dm, "m%02d" % m)):
            ref = state.load(os.path.join(dm, "m%02d" % m))
            mine = p.tree()
            extra = "; " + "; ".join("%s: %s" % (n, first_diff(mine[n], ref[n])) for n in bad[:6])
        kit.check(not bad, "P2 month %d: %.1f s, digest %s, fields differing %d %s%s%s" % (m, el, dg[:16], len(bad), bad[:8], extra,
                                                                               (" (against %s, %d fields excluded: %s)" % (os.path.basename(dm), len(excl), ",".join(excl))) if excl else ""))
        with open(os.path.join(dm, "m%02d.tally.json" % m), encoding="utf-8") as f:
            ref_tl = digest._dec(json.load(f), d)
        td = tally_diff(p.tr_margins.get("t22", {}), ref_tl)
        kit.check(not td, "P2c month %d: tallies differing %d %s" % (m, len(td), td[:8]))
        if bad:
            break
        if save_every and m % save_every == 0:
            sd = os.path.join(os.environ.get("PY_SAVE_DIR", d), "py_ckpt_m%03d" % m)
            state.save(p, sd)
            print("saved the Python state at month %d to %s" % (m, sd), flush=True)
            # Why only the latest is kept: each save is the whole state (2.6 GB at K = 4), and two filled the disk at month 24
            prev = os.path.join(os.environ.get("PY_SAVE_DIR", d), "py_ckpt_m%03d" % (m - save_every))
            if os.path.isdir(prev):
                shutil.rmtree(prev)
    print("peak RSS %.0f MB" % (peak_mb()), flush=True)
    kit.finish()


if __name__ == "__main__":
    main()
