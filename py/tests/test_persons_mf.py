# The persons' must-fails (PERSONS_PORT_PLAN §4 Q-mf, §7 Q-mf2): rows that cannot fail read nothing, so each mutation below must
# make the oracle's month-1 hashes differ, in the field named
#   python py/tests/test_persons_mf.py <trace dir>
# Q-mf: one person's income nudged by one ulp at month 1's start makes c7 differ, and income is among the differing fields
# Q-mf2: the decision's draw tag changed by one character ("choose" to "choosf") in Python only makes c2 differ in last_action,
# plan or search
import math
import os
import sys

from common import Kit
from core import digest
from people import act, month
from tiers.start import trace

ENV = {"inflation_month": 0.02 / 12.0, "food_price_yoy": 0.0, "unemployment_rate": 0.025, "levers": []}


def differing(p, ctx, ref):
    out = []
    for n in sorted(ref):
        if n == "tr_margins" or n.startswith("tr_"):
            continue
        if n.startswith("rec."):
            h = trace.sha(getattr(p, n[4:]))
        elif n.startswith("local."):
            h = trace.stage_hashes(p, ctx, [n])[n]
        else:
            h = trace.sha(getattr(p, n))
        if h != ref[n]:
            out.append(n)
    return out


def main():
    d = sys.argv[1]
    k = Kit("py/tests/test_persons_mf.py")
    p, ctx = trace.load_stage(os.path.join(d, "m01_c0"))
    i = max(range(p.n), key=lambda j: p.income[j])
    p.income[i] = math.nextafter(p.income[i], math.inf)
    month.run(p, ctx, "c0", "c7", dict(ENV))
    bad = differing(p, ctx, digest.read_hashes(os.path.join(d, "m01_c7.sha.txt")))
    k.check("income" in bad, "Q-mf one ulp on person %d's income makes month 1's c7 differ, income among them: %s" % (i, " ".join(bad[:12])))
    p, ctx = trace.load_stage(os.path.join(d, "m01_c1"))
    real_u = type(p).u

    def u_mut(self, tag, j, b=0, c=0):
        return real_u(self, "choosf" if tag == "choose" else tag, j, b, c)

    type(p).u = u_mut
    try:
        month.run(p, ctx, "c1", "c2", dict(ENV))
    finally:
        type(p).u = real_u
    bad2 = differing(p, ctx, digest.read_hashes(os.path.join(d, "m01_c2.sha.txt")))
    k.check(bool({"last_action", "plan", "search"} & set(bad2)),
            "Q-mf2 the decision tag \"choose\" changed by one character makes month 1's c2 differ: %s" % " ".join(bad2[:12]))
    k.finish()


if __name__ == "__main__":
    main()
