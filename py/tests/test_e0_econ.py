# ECON_PORT_PLAN §3 rows E0 and E0-j (AMENDED A2), declared before the econ port's code:
# E0: every DetMath and keyed call sim/modern/econ makes is one the Python core already has (DetMath exp and pow; keyed normal, u and
#     below), and econ calls no other DetMath or keyed function.
# E0-j: one SHA-256 over every econ data file after canon equals the GDScript oracle's (tools/py/oracle_dump_econ.gd ORACLE_MODE=json):
#     each file read as Godot reads it (every JSON number a float) and snapped by canon.gd's rule, hashed by the tiers' canonical bytes.
#   python3 py/tests/test_e0_econ.py <the oracle's econ_json.sha.txt>
import glob
import hashlib
import json
import math
import os
import re
import sys

from common import Kit, ROOT
from core import detmath, keyed
from core.digest import canon as _canon

ECON_GD = os.path.join(ROOT, "sim", "modern", "econ")
ECON_DATA = os.path.join(ROOT, "data", "modern", "econ")
WANT_CALLS = {"DM.exp", "DM.pow", "KEYED.normal", "KEYED.u", "KEYED.below"}
TWINS = {"DM.exp": (detmath, "exp"), "DM.pow": (detmath, "pow"), "KEYED.normal": (keyed, "normal"), "KEYED.u": (keyed, "u"),
         "KEYED.below": (keyed, "below")}


def canon_f(x):
    # canon.gd's canon_f, operation for operation
    if not math.isfinite(x):
        return x
    if abs(x) >= 1e7:
        r = math.floor(x + 0.5)
        return float(r) if abs(x - r) < 1e-3 else x
    return math.floor(x * 1e9 + 0.5) / 1e9


def canon(v):
    if isinstance(v, float):
        return canon_f(v)
    if isinstance(v, dict):
        return {k: canon(x) for k, x in v.items()}
    if isinstance(v, list):
        return [canon(x) for x in v]
    return v


def load_json(path):
    # Why parse_int=float: Godot's JSON parser returns every number as a float, so an integer in a file is a float in the oracle
    with open(path, encoding="utf-8") as f:
        return canon(json.load(f, parse_int=float))


def json_hashes():
    lines = ""
    for path in sorted(glob.glob(os.path.join(ECON_DATA, "*.json")), key=os.path.basename):
        h = hashlib.sha256()
        _canon(h, load_json(path))
        lines += "%s %s\n" % (os.path.basename(path), h.hexdigest())
    return lines


def main():
    k = Kit("py/tests/test_e0_econ.py")
    calls = set()
    for path in sorted(glob.glob(os.path.join(ECON_GD, "*.gd"))):
        src = open(path, encoding="utf-8").read()
        for m in re.finditer(r"\b(DM|KEYED)\.([a-z_]+)\(", src):
            calls.add(m.group(1) + "." + m.group(2))
    k.check(calls == WANT_CALLS, "E0 the DetMath and keyed calls in sim/modern/econ: %s (declared %s)" % (sorted(calls), sorted(WANT_CALLS)))
    missing = [c for c, (mod, fn) in TWINS.items() if not callable(getattr(mod, fn, None))]
    k.check(not missing, "E0 each has its twin in the Python core (py/core/detmath.py, keyed.py): missing %s" % missing)
    got = json_hashes()
    total = hashlib.sha256(got.encode("utf-8")).hexdigest()
    if len(sys.argv) > 1:
        want = open(sys.argv[1], encoding="utf-8").read()
        bad = [ln.split()[0] for ln, w in zip(got.splitlines(), want.splitlines()) if ln != w]
        same_files = [ln.split()[0] for ln in got.splitlines()] == [ln.split()[0] for ln in want.splitlines()]
        k.check(got == want, "E0-j every econ data file after canon, Python %s vs GDScript %s (%d files; the same file list %s; differing %s)"
                % (total[:16], hashlib.sha256(want.encode("utf-8")).hexdigest()[:16], len(got.splitlines()), same_files, bad))
    else:
        k.check(False, "E0-j needs the oracle's econ_json.sha.txt (tools/py/oracle_dump_econ.gd ORACLE_MODE=json); Python's is %s" % total[:16])
    k.finish()


if __name__ == "__main__":
    main()
