# Row G-sort (START_PORT_PLAN §2): core/gdsort.py orders every case as Godot's Array.sort() and sort_custom() did, ties included
#   python py/tests/test_gdsort.py [outputs/py_oracle/gdsort.json]
import json
import os
import struct
import sys

from common import Kit, ROOT
from core import gdsort


def dec(n):
    if "i" in n:
        return int(n["i"])
    if "f" in n:
        return struct.unpack("<d", struct.pack("<q", int(n["f"])))[0]
    if "s" in n:
        return n["s"]
    if "a" in n:
        return [dec(x) for x in n["a"]]
    return {dec(k): dec(v) for k, v in n["d"]}


def same(a, b):
    # equal values of the same types, so 1 and 1.0 count as different, as they do in Godot's sorted output
    if type(a) is not type(b):
        return False
    if isinstance(a, list):
        return len(a) == len(b) and all(same(x, y) for x, y in zip(a, b))
    return a == b


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "outputs/py_oracle/gdsort.json")
    with open(path, encoding="utf-8") as f:
        cases = dec(json.load(f))
    k = Kit("py/tests/test_gdsort.py")
    bad_c = bad_d = 0
    nc = nd = 0
    for c in cases:
        if c["kind"] == "custom":
            nc += 1
            a = [list(r) for r in c["in"]]
            gdsort.sort_custom(a, lambda x, y: x[0] < y[0])
            if [r[1] for r in a] != c["out"]:
                bad_c += 1
        else:
            nd += 1
            a = list(c["in"])
            gdsort.sort(a)
            if not same(a, c["out"]):
                bad_d += 1
    k.check(bad_c == 0, "G-sort sort_custom with ties: %d of %d cases in Godot's order" % (nc - bad_c, nc))
    k.check(bad_d == 0, "G-sort Array.sort() on mixed values: %d of %d cases in Godot's order" % (nd - bad_d, nd))
    k.finish()


if __name__ == "__main__":
    main()
