# ECON_PORT_PLAN §3 rows E0-s, E1, E1s, E1d, E1r, E-c (E-c-x, E-c-f; AMENDED A6), E-mf and E-mf2 against the GDScript oracle
# (tools/py/oracle_dump_econ.gd), declared before the port's code:
#   E0-s  the Python start built from the data files: its month-0 field hashes equal the oracle's month 0
#   E1    people off, no shocks: from the oracle's month-0 state, every field's hash equals the oracle's at months 1-36
#   E1s   people off, seeded shocks, seeds 1, 7 and 42: the shocks drawn in Python equal the oracle's month-0 shocks, then months 1-36
#   E1d   people off, the declared drought (months 12-23, rice and vegetables x 0.6): months 1-36
#   E1r   the Python state saved at month 12 and restored continues equal to the straight run and to the oracle, months 13-24
#   E2    with labour, the persons' interface replayed from the oracle month by month (their supply in, the state's rice releases):
#         every field, wage_index and u included, equals the oracle's at months 1-36
#   E-c   every run: the shadow ledger's totals conserve exactly (E-c-x) and each float is within its bound of the shadow (E-c-f)
#   E-c-mf must-fail (AMENDED A8, M039's addendum): on a copy after month 6, (a) 1e-9 bn credited to one account with no transfer record,
#         (b) one goods journal row dropped, (c) one account's float moved 2 x its own bound from the shadow: each makes E-c-f fail and
#         name that account or good
#   E-mf  must-fail: rice's price nudged by one ulp at month 6 makes month 6's digest differ, and the first differing path is that price
#   E-mf2 must-fail: the yield draw's tag changed by one character makes E1s's shocks differ from the oracle's at their first month
#   python3 test_econ_parity.py <oracle root: unseeded/ seed1/ seed7/ seed42/ drought/ [people/]>
import hashlib
import json
import math
import os
import struct
import sys
import tempfile

from common import Kit
from econ import state
from econ.month import EconMonth
from econ.shadow import Shadow

MONTHS = 36


def bits(x):
    return struct.unpack("<q", struct.pack("<d", x))[0]


def first_diff(a, b, path=""):
    # The first path where two decoded states differ, type first, floats by their bits; None when equal
    if type(a) is not type(b) and not (isinstance(a, dict) and isinstance(b, dict)):
        return "%s (type %s vs %s)" % (path, type(a).__name__, type(b).__name__)
    if isinstance(a, float):
        return None if bits(a) == bits(b) else "%s (%r vs %r)" % (path, a, b)
    if isinstance(a, dict):
        for k in sorted(set(a) | set(b), key=str):
            if k not in a or k not in b:
                return "%s.%s (only on one side)" % (path, k)
            d = first_diff(a[k], b[k], "%s.%s" % (path, k))
            if d:
                return d
        return None
    if isinstance(a, list):
        if len(a) != len(b):
            return "%s (length %d vs %d)" % (path, len(a), len(b))
        for i, (x, y) in enumerate(zip(a, b)):
            d = first_diff(x, y, "%s[%d]" % (path, i))
            if d:
                return d
        return None
    return None if a == b else "%s (%r vs %r)" % (path, a, b)


def enc(v):
    # oracle_dump_econ.gd's typed tree, so a Python save is read back by the same loader as the oracle's
    if v is None or isinstance(v, bool):
        return v
    if isinstance(v, int):
        return {"i": str(v)}
    if isinstance(v, float):
        return {"f": str(bits(v))}
    if isinstance(v, str):
        return {"s": v}
    if isinstance(v, list):
        return {"a": [enc(x) for x in v]}
    if isinstance(v, dict):
        return {"d": [[enc(k), enc(x)] for k, x in v.items()]}
    raise TypeError(type(v))


def save(e, d):
    os.makedirs(d, exist_ok=True)
    f = state.fields(e)
    with open(os.path.join(d, "state.json"), "w", encoding="utf-8") as fh:
        json.dump({n: enc(f[n]) for n in sorted(f)}, fh)


def run(k, row, e, odir, first=1, last=MONTHS, shadow=True, straight=None):
    # Steps e month by month from month first - 1, comparing each month's field hashes with the oracle's; E-c on every month
    sh = Shadow(e) if shadow else None
    worst = (0.0, "")
    for m in range(first, last + 1):
        e.step()
        got = state.field_hashes(e)
        want = state.read_hashes(os.path.join(odir, "m%02d.sha.txt" % m))
        if got != want:
            bad = sorted(n for n in set(got) | set(want) if got.get(n) != want.get(n))
            k.check(False, "%s month %d: the first differing fields %s (%d of %d)" % (row, m, bad[:3], len(bad), len(want)))
            return False
        if straight is not None and state.digest(e)[0] != straight[m]:
            k.check(False, "%s month %d: differs from the straight run" % (row, m))
            return False
        if sh:
            sh.month(e)
            money, goods = sh.exact()
            gaps, w = sh.float_gaps(e)
            worst = max(worst, w)
            if money != 0 or any(v != 0 for v in goods.values()):
                k.check(False, "E-c-x %s month %d: money %r, goods %s" % (row, m, float(money), [g for g, v in goods.items() if v != 0][:3]))
                return False
            if gaps:
                k.check(False, "E-c-f %s month %d: %s" % (row, m, gaps[:2]))
                return False
    k.check(True, "%s months %d-%d: every field equals the oracle's (%s)" % (row, first, last, odir.rstrip("/").split("/")[-1]))
    if sh:
        k.check(True, "E-c %s: exact conservation every month (E-c-x); every account and good within its bound (E-c-f), worst gap / bound %.3g at %s"
                % (row, worst[0], worst[1]))
    return True


def unbits(node):
    return None if node is None else struct.unpack("<d", struct.pack("<q", int(node["f"])))[0]


def e2(k, odir, months=MONTHS):
    # The persons' month replayed from the oracle's interface: what they supplied before the economy's step, and the releases
    e = state.from_tree(os.path.join(odir, "m00"))
    sh = Shadow(e)
    for m in range(1, months + 1):
        with open(os.path.join(odir, "m%02d.iface.json" % m), encoding="utf-8") as fh:
            iv = json.load(fh)
        e.labour.receive(unbits(iv["search_share"]), unbits(iv["wage_demand_share"]), {c: unbits(v) for c, v in iv["scales"].items()})
        for r in iv.get("rice_releases", []):
            e.release_state_rice(m - 1, unbits(r))
        e.step()
        got = state.field_hashes(e)
        want = state.read_hashes(os.path.join(odir, "m%02d.sha.txt" % m))
        if got != want:
            bad = sorted(n for n in set(got) | set(want) if got.get(n) != want.get(n))
            k.check(False, "E2 month %d: the first differing fields %s (%d of %d)" % (m, bad[:3], len(bad), len(want)))
            return
        if bits(e.labour.wage_index) != bits(unbits(iv["wage_index"])) or bits(e.labour.u) != bits(unbits(iv["u"])):
            k.check(False, "E2 month %d: wage_index or u differs from the interface" % m)
            return
        sh.month(e)
        money, goods = sh.exact()
        gaps, _ = sh.float_gaps(e)
        if money != 0 or any(v != 0 for v in goods.values()) or gaps:
            k.check(False, "E-c E2 month %d: money %r, gaps %s" % (m, float(money), gaps[:2]))
            return
    k.check(True, "E2 months 1-%d: every field, wage_index and u equal the oracle's with the persons' interface replayed; E-c holds" % months)


def ec_mf(k, odir):
    from fractions import Fraction

    def at6():
        e = state.from_tree(os.path.join(odir, "m00"))
        sh = Shadow(e)
        for m in range(6):
            e.step()
            if m < 5:
                sh.month(e)
        return e, sh

    acct = "crop_farming_JPN"
    e, sh = at6()
    e.world.cash[acct] += 1e-9
    sh.month(e)
    bad, _ = sh.float_gaps(e)
    k.check([b[1] for b in bad] == [acct], "E-c-mf (a) 1e-9 bn credited to %s with no record: E-c-f fails on %s" % (acct, [b[1] for b in bad]))
    e, sh = at6()
    drop = next(i for i, r in enumerate(e.world.journal) if r[0] == "produce")
    good = e.world.journal[drop][1]
    del e.world.journal[drop]
    sh.month(e)
    bad, _ = sh.float_gaps(e)
    k.check([b[1] for b in bad] == [good], "E-c-mf (b) one journal row of %s dropped: E-c-f fails on %s" % (good, [b[1] for b in bad]))
    e, sh = at6()
    sh.month(e)
    b_a = (1 + 2 * Fraction(1, 2 ** 53)) * sh.bound[acct]
    e.world.cash[acct] = float(sh.cash[acct] + 2 * b_a)
    bad, _ = sh.float_gaps(e)
    k.check([b[1] for b in bad] == [acct], "E-c-mf (c) %s's float 2 x its bound (%.3g bn) from the shadow: E-c-f fails on %s"
            % (acct, float(b_a), [b[1] for b in bad]))


def main():
    root = sys.argv[1]
    k = Kit("py/tests/test_econ_parity.py")
    od = lambda t: os.path.join(root, t)
    e = EconMonth()
    k.check(e.create("JPN") == "", "E0-s the Python start builds")
    got = state.field_hashes(e)
    want = state.read_hashes(os.path.join(od("unseeded"), "m00.sha.txt"))
    bad = sorted(n for n in set(got) | set(want) if got.get(n) != want.get(n))
    if bad:
        o = state.load_tree(os.path.join(od("unseeded"), "m00"))
        f = state.fields(e)
        print("E0-s first differing paths: %s" % [first_diff(f.get(n), o.get(n), n) for n in bad[:3]])
    k.check(not bad, "E0-s month-0 fields equal the oracle's: differing %s (%d fields)" % (bad[:5], len(want)))
    run(k, "E1", state.from_tree(os.path.join(od("unseeded"), "m00")), od("unseeded"))
    for seed in (1, 7, 42):
        e = state.from_tree(os.path.join(od("seed%d" % seed), "m00"))
        e.shocks = []
        e.seed_shocks(seed, MONTHS // 12 + 1)
        same = state.field_hashes(e)["econ.shocks"] == state.read_hashes(os.path.join(od("seed%d" % seed), "m00.sha.txt"))["econ.shocks"]
        k.check(same, "E1s seed %d: the shocks drawn in Python equal the oracle's (%d shocks)" % (seed, len(e.shocks)))
        if same:
            run(k, "E1s seed %d" % seed, e, od("seed%d" % seed))
    run(k, "E1d", state.from_tree(os.path.join(od("drought"), "m00")), od("drought"))
    e = state.from_tree(os.path.join(od("unseeded"), "m00"))
    straight = {}
    for m in range(1, 25):
        e.step()
        straight[m] = state.digest(e)[0]
    e = state.from_tree(os.path.join(od("unseeded"), "m00"))
    for m in range(12):
        e.step()
    tmp = tempfile.mkdtemp(prefix="e1r_")
    save(e, os.path.join(tmp, "m12"))
    r = state.from_tree(os.path.join(tmp, "m12"))
    k.check(state.digest(r)[0] == straight[12], "E1r the restored month 12 equals the saved one")
    run(k, "E1r", r, od("unseeded"), first=13, last=24, shadow=False, straight=straight)
    e = state.from_tree(os.path.join(od("unseeded"), "m00"))
    for m in range(6):
        e.step()
    e.world.goods["rice|JPN"]["price"] = math.nextafter(e.world.goods["rice|JPN"]["price"], math.inf)
    differs = state.digest(e)[0] != hashlib.sha256("".join("%s %s\n" % (n, h) for n, h in sorted(state.read_hashes(os.path.join(od("unseeded"), "m06.sha.txt")).items())).encode()).hexdigest()
    o6 = state.load_tree(os.path.join(od("unseeded"), "m06"))
    path = first_diff(state.fields(e)["world.goods"], o6["world.goods"], "world.goods")
    k.check(differs and path is not None and path.startswith("world.goods.rice|JPN.price"),
            "E-mf one ulp on rice's price at month 6: the digest differs %s; the first differing path %s" % (differs, path))
    ec_mf(k, od("unseeded"))
    import core.keyed as KY
    real_normal = KY.normal

    def bent(seed_v, tag, a=0, b=0, c=0):
        return real_normal(seed_v, tag.replace("yield:", "yielD:"), a, b, c)
    import econ.month as EMOD
    EMOD.KEYED.normal = bent
    try:
        e = state.from_tree(os.path.join(od("seed7"), "m00"))
        e.shocks = []
        e.seed_shocks(7, MONTHS // 12 + 1)
    finally:
        EMOD.KEYED.normal = real_normal
    want7 = state.load_tree(os.path.join(od("seed7"), "m00"))["econ.shocks"]
    got7 = state.fields(e)["econ.shocks"]
    firsts = [i for i, (x, y) in enumerate(zip(got7, want7)) if first_diff(x, y)]
    k.check(bool(firsts), "E-mf2 the yield tag 'yield:' -> 'yielD:': the seeded shocks differ from the oracle's from shock %s (month %s)"
            % (firsts[0] if firsts else None, want7[firsts[0]]["from_month"] if firsts else None))
    if os.path.isdir(od("people")):
        e2(k, od("people"))
    else:
        k.check(False, "E2 needs the oracle's people dump (ORACLE_MODE=people)")
    k.finish()


if __name__ == "__main__":
    main()
