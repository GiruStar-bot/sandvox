# L0-t (LC_HH_PORT_PLAN §5), no Godot. What is right:
# - the persons' life course reads the same rate functions as the tiers' month (one source), which P2 proved against GDScript;
# - over the whole grid they give one answer per input, whichever caller reads them;
# - the Godot sort's emulation returns a sorted order on any input, and the order of the distinct keys alone, so only ties can move.
import json
import os

from common import Kit, ROOT
from core import keyed
from tiers import month as TM
from lchh import gdsort, life_course as LC


class Spec:
    def __init__(self):
        self.hh_spec = json.load(open(os.path.join(ROOT, "data/modern/people/jpn_households_2024.json"), encoding="utf-8"))


def main():
    kit = Kit("py/tests/test_lchh_pure.py")
    same = [(LC.shares, TM.lc_shares), (LC.ltci_share, TM.lc_ltci_share), (LC.income_factor, TM.lc_income_factor),
            (LC.death_q, TM.lc_death_q), (LC.grade_kernel, TM.lc_grade_kernel), (LC.grade_flows, TM.lc_grade_flows),
            (LC.h_regrade, TM.lc_h_regrade)]
    kit.check(all(a is b for a, b in same), "L0-t: life_course.py's 7 rate functions are py/tiers/month.py's lc_* twins (one source)")
    p = Spec()
    bad = 0
    n = 0
    for a in range(101):
        for s in range(2):
            pi0 = LC.shares(p, a, s)
            for c in range(2):
                if list(LC.grade_kernel(p, c, pi0)) != list(TM.lc_grade_kernel(p, c, pi0)):
                    bad += 1
                n += 1
            for k in range(4):
                for g in range(5):
                    if LC.death_q(p, 1.3, a, g, k, 0.01, 12.0) != TM.lc_death_q(p, 1.3, a, g, k, 0.01, 12.0):
                        bad += 1
                    n += 1
    kit.check(bad == 0, "L0-t grid: a 0-100, both sexes, classes, grades and quartiles: %d values, %d differing" % (n, bad))
    ok_sorted = True
    ok_distinct = True
    for sz in range(0, 301, 7):
        for ties in (2, 5, 1000000):
            keys = [float(keyed.below(ties, 1, "gdsort_test", sz, ties, i)) for i in range(sz)]
            rows = [[k, 0.0, i] for i, k in enumerate(keys)]
            gdsort.sort_custom(rows, LC._row_less)
            got = [r[0] for r in rows]
            if got != sorted(keys) or sorted(r[2] for r in rows) != list(range(sz)):
                ok_sorted = False
            if ties == 1000000 and len(set(keys)) == sz and [r[2] for r in rows] != sorted(range(sz), key=lambda i: keys[i]):
                ok_distinct = False
    kit.check(ok_sorted, "L0-sort (self): the emulated Godot sort returns a sorted permutation, sizes 0-300 with and without ties")
    kit.check(ok_distinct, "L0-sort (self): with distinct keys its order is the only sorted one")
    kit.finish()


if __name__ == "__main__":
    main()
