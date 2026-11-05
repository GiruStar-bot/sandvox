# Row Q-1 (PERSONS_PORT_PLAN §4, §7 M042 (1)): the Python start (cd165891's data) stepped by the whole Python month, people.step's
# sections c1-c8 with TR.step, compared at every month's end (c8) with the oracle's persons trace: every persons field and scalar,
# the records, every tr_* field
#   START_DATA_ROOT=<cd165891 tree> [PERSONS_SEED=7] python py/tests/run_persons.py <trace dir> <months> [<trace dir for later months>]
import os
import sys
import time

from common import Kit, peak_mb
import json

import tally_cmp
from core import digest
from people import month
from tiers.start import create, trace

ENV = {"inflation_month": 0.02 / 12.0, "food_price_yoy": 0.0, "unemployment_rate": 0.025, "levers": []}


def ref_path(dirs, m):
    for d in dirs:
        f = os.path.join(d, "m%02d_c8.sha.txt" % m)
        if os.path.exists(f):
            return f
    return None


def main():
    dirs = [sys.argv[1]] + sys.argv[3:]
    months = int(sys.argv[2])
    k = Kit("py/tests/run_persons.py")
    t0 = time.perf_counter()
    p = create.create(seed=int(os.environ.get("PERSONS_SEED", "1")))
    print("start %.1f s" % (time.perf_counter() - t0), flush=True)
    for m in range(1, months + 1):
        t1 = time.perf_counter()
        month.step(p, dict(ENV))
        f = ref_path(dirs, m)
        if f is None:
            print("month %d: no oracle hashes, stopped" % m)
            break
        ref = digest.read_hashes(f)
        got = {}
        for n in ref:
            if n.startswith("rec."):
                got[n] = trace.sha(getattr(p, n[4:]))
            elif n.startswith("tr_"):
                got.update(trace.stage_hashes(p, {}, [n]))
            else:
                got[n] = trace.sha(getattr(p, n))
        bad = [n for n in sorted(ref) if n != "tr_margins" and got[n] != ref[n]]
        k.check(not bad, "Q-1 month %d: %d of %d hashes equal to the oracle's (%.1f s)%s" % (
            m, len(ref) - len(bad) - 1, len(ref) - 1, time.perf_counter() - t1, (", differing " + " ".join(bad[:30])) if bad else ""))
        tally = os.path.join(os.environ.get("TALLY_DIR", os.path.join(dirs[0], "..", "fz")), "m%02d.tally.json" % m)
        if not os.path.exists(tally):
            continue
        with open(tally, encoding="utf-8") as f2:
            dt = tally_cmp.diff(p.tr_margins["t22"], digest._dec(json.load(f2), ""))
        k.check(not dt, "Q-1t month %d: the tiers' tally equal to the oracle's by value%s" % (m, (": " + "; ".join(dt[:10])) if dt else ""))
    print("peak %.0f MB" % peak_mb())
    k.finish()


if __name__ == "__main__":
    main()
