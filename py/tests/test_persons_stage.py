# The persons' month by section against the oracle's trace (PERSONS_PORT_PLAN §3, §6): from the oracle's whole state at month M's
# section FROM, the Python sections run through TO, and every hash the oracle wrote at TO must be equal (the persons' fields and
# scalars, the records "rec.", the locals "local.", every tr_*)
#   python py/tests/test_persons_stage.py <trace dir> <M> <FROM> <TO>
import os
import sys
import time

from common import Kit, peak_mb
import json

import tally_cmp
from core import digest
from people import month
from tiers.start import trace

ENV = {"inflation_month": 0.02 / 12.0, "food_price_yoy": 0.0, "unemployment_rate": 0.025, "levers": []}


def main():
    d, m, first, last = sys.argv[1], int(sys.argv[2]), sys.argv[3], sys.argv[4]
    k = Kit("py/tests/test_persons_stage.py %d %s %s" % (m, first, last))
    t0 = time.perf_counter()
    p, ctx = trace.load_stage(os.path.join(d, "m%02d_%s" % (m, first)))
    t1 = time.perf_counter()
    month.run(p, ctx, first, last, dict(ENV))
    t2 = time.perf_counter()
    ref = digest.read_hashes(os.path.join(d, "m%02d_%s.sha.txt" % (m, last)))
    names = list(ref)
    # Why the oracle's FROM hash for a tr_* field the dump left out (the tiers' whole state is in the c7 dump only): only TR.step
    # (c7 -> c8) writes the tiers, so the oracle's own FROM and TO hashes must agree, and the Python sections never held the field
    ref_from = digest.read_hashes(os.path.join(d, "m%02d_%s.sha.txt" % (m, first)))
    carried = [n for n in names if n.startswith("tr_") and n not in p.dump_keys]
    got = {}
    for n in names:
        if n in carried:
            got[n] = ref_from.get(n, "missing")
        elif n.startswith("rec."):
            got[n] = trace.sha(getattr(p, n[4:]))
        elif n.startswith("local.") or n.startswith("tr_"):
            got.update(trace.stage_hashes(p, ctx, [n]))
        else:
            got[n] = trace.sha(getattr(p, n))
    bad = [n for n in sorted(ref) if n != "tr_margins" and got[n] != ref[n]]
    k.check(not bad, "Q-1 m%02d %s->%s: %d of %d hashes equal to the oracle's (tr_margins by value below)%s" % (
        m, first, last, len(ref) - len(bad) - 1, len(ref) - 1, (", differing " + " ".join(bad[:40])) if bad else ""))
    if last == "c8" and "tr_margins" in ref:
        tally = os.path.join(os.environ.get("TALLY_DIR", os.path.join(d, "..", "fz")), "m%02d.tally.json" % m)
        with open(tally, encoding="utf-8") as f:
            dt = tally_cmp.diff(p.tr_margins["t22"], digest._dec(json.load(f), ""))
        k.check(not dt, "Q-1t m%02d the tiers' tally (tr_margins t22) equal to the oracle's by value, P2c's rule%s" % (
            m, (": " + "; ".join(dt[:10])) if dt else ""))
    if carried:
        print("info %d tr_* fields not in the dump, taken as the oracle's %s hashes (unchanged in the oracle: %s)" % (
            len(carried), first, "yes" if all(ref_from.get(n) == ref[n] for n in carried) else "NO"))
    print("time load %.1f s, sections %.1f s, peak %.0f MB" % (t1 - t0, t2 - t1, peak_mb()))
    k.finish()


if __name__ == "__main__":
    main()
