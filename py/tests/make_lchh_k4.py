# Writes tools/py/lchh_k4_sort.json for row L-K4 (LC_HH_PORT_PLAN §7): arrays that drive py/lchh/gdsort.py's introsort to its depth
# limit, so its heap path runs. McIlroy's adversary (A Killer Adversary for Quicksort, Software: Practice and Experience 29(4), 1999):
# the keys are fixed lazily, during one sort, so that every pivot is the smallest key still unfixed.
# Why the arrays are committed and not built in the dump: the dump is GDScript, and the arrays only need to exist, not to be rebuilt
#   python py/tests/make_lchh_k4.py
import json
import os

from common import ROOT
from lchh import gdsort, life_course as LC


def adversary(n):
    gas = n
    val = [gas] * n
    state = {"solid": 0, "cand": 0}

    def freeze(x):
        val[x] = state["solid"]
        state["solid"] += 1

    def less(x, y):
        if val[x] == gas and val[y] == gas:
            freeze(x if x == state["cand"] else y)
        if val[x] == gas:
            state["cand"] = x
        elif val[y] == gas:
            state["cand"] = y
        return val[x] < val[y]
    gdsort.sort_custom(list(range(n)), less)
    for i in range(n):
        if val[i] == gas:
            freeze(i)
    return val


def heap_ran(keys):
    calls = [0]
    orig = gdsort._partial_sort

    def counted(*a):
        calls[0] += 1
        return orig(*a)
    gdsort._partial_sort = counted
    try:
        rows = [[float(k), 0.0, i] for i, k in enumerate(keys)]
        gdsort.sort_custom(rows, LC._row_less)
    finally:
        gdsort._partial_sort = orig
    return calls[0]


def main():
    out = []
    for n in (64, 300, 1000):
        keys = adversary(n)
        for variant, ks in (("distinct", keys), ("pairs", [k // 2 for k in keys])):
            h = heap_ran(ks)
            print("n %d %s: heap path calls %d" % (n, variant, h))
            if h > 0:
                out.append({"n": n, "variant": variant, "keys": ks})
    path = os.path.join(ROOT, "tools/py/lchh_k4_sort.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"source": "py/tests/make_lchh_k4.py", "arrays": out}, f)
    print("wrote %d arrays to %s" % (len(out), path))


if __name__ == "__main__":
    main()
