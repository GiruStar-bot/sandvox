# Step (c)'s rows (START_PORT_PLAN §4): the start at 2025-01 on modern's in-window data and rule (D)'s table
#   python py/tests/test_start_2025.py [runs]   (runs 2: the determinism row builds the start twice)
# S0-c-pop: the start's population (Σ tr_count plus the top tier's individuals) equals rule (D)'s total at 2025-01-01, exactly (a hard row, D477)
# S0-c-det: the same seed builds the same start, on the tiers digest (a hard row)
# S0-c-dg: the start's tiers digest, recorded for the Numba path and for later months to reproduce
import sys

from common import Kit
import country
from tiers import state
from tiers.start import build, create, load
from tiers.start.p import to_tree


def build_2025():
    p, prefectures = create.inputs_2025()
    build.build_start(p, prefectures)
    for i in range(p.n):
        p.weight[i] = 1.0
    names = sorted(k for k in vars(p) if k.startswith("tr_") and k != "tr_margins")
    dg, _ = state.digest({n: to_tree(getattr(p, n)) for n in names})
    return p, dg


def main():
    runs = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    k = Kit("py/tests/test_start_2025.py")
    d = load.load_json(country.load("JPN").path("start_2025"))
    p, dg = build_2025()
    # Why the individuals too: the top tier's persons are the persons layer's (p.n), not in any bundle's tr_count
    pop = sum(int(x) for x in p.tr_count) + p.n
    k.check(pop == int(d["total"]), "S0-c-pop the start's population (bundles %d + individuals %d) equals rule (D)'s total %d at 2025-01-01"
            % (pop - p.n, p.n, int(d["total"])))
    print("S0-c-dg tiers digest %s, units %d, points %d" % (dg, p.tr_units, p.tr_pt_off[p.tr_units]))
    if runs > 1:
        _, dg2 = build_2025()
        k.check(dg2 == dg, "S0-c-det the same seed builds the same start: %s" % dg2)
    k.finish()


if __name__ == "__main__":
    main()
