# Row Q-r (PERSONS_PORT_PLAN §4): the Python persons and tiers state saved at month 6 and restored continues equal to the straight
# run: months 7-13 compared with the oracle's trace, as Q-1 compares them. The save is every attribute of the persons' object as a
# typed tree (core/digest's), so a field left out of the save shows as a differing field after the restore
#   START_DATA_ROOT=<cd165891 tree> python py/tests/test_persons_resume.py <trace dir> <save dir>
import json
import os
import shutil
import sys

from common import Kit
import tally_cmp  # noqa: E402  (after common, which puts py/ on the path)
from core import digest
from people import month
from tiers.start import create, trace
from tiers.start.p import P, from_tree, to_tree

ENV = {"inflation_month": 0.02 / 12.0, "food_price_yoy": 0.0, "unemployment_rate": 0.025, "levers": []}


def save(p, d):
    shutil.rmtree(d, ignore_errors=True)
    os.makedirs(d)
    files = [0]
    tree = {k: digest.enc(to_tree(v), d, files) for k, v in vars(p).items()}
    with open(os.path.join(d, "state.json"), "w", encoding="utf-8") as f:
        json.dump(tree, f)


def restore(d):
    p = P()
    for k, v in digest.load(d).items():
        setattr(p, k, from_tree(v))
    return p


def main():
    tdir, sdir = sys.argv[1], sys.argv[2]
    k = Kit("py/tests/test_persons_resume.py")
    p = create.create()
    for m in range(1, 7):
        month.step(p, dict(ENV))
    save(p, sdir)
    del p
    p = restore(sdir)
    for m in range(7, 14):
        month.step(p, dict(ENV))
        ref = digest.read_hashes(os.path.join(tdir, "m%02d_c8.sha.txt" % m))
        bad = []
        for n in sorted(ref):
            if n == "tr_margins":
                continue
            if n.startswith("rec."):
                h = trace.sha(getattr(p, n[4:]))
            elif n.startswith("tr_"):
                h = trace.stage_hashes(p, {}, [n])[n]
            else:
                h = trace.sha(getattr(p, n))
            if h != ref[n]:
                bad.append(n)
        k.check(not bad, "Q-r month %d after the month-6 restore: %d of %d hashes equal to the oracle's%s" % (
            m, len(ref) - 1 - len(bad), len(ref) - 1, (", differing " + " ".join(bad[:20])) if bad else ""))
        tally = os.path.join(os.environ.get("TALLY_DIR", ""), "m%02d.tally.json" % m)
        if os.path.exists(tally):
            with open(tally, encoding="utf-8") as f:
                dt = tally_cmp.diff(p.tr_margins["t22"], digest._dec(json.load(f), ""))
            k.check(not dt, "Q-r month %d the tiers' tally equal by value%s" % (m, (": " + "; ".join(dt[:5])) if dt else ""))
    k.finish()


if __name__ == "__main__":
    main()
