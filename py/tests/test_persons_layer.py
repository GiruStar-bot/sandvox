# Row L (the persons layer the integrated month calls, py/people/layer.py): people.create's sample path (tiers off, households off)
# and the months stepped with the integrated month's env give, at every month, the oracle's hashes (tools/py/persons_sample_dump.gd
# at cd165891): every people.fields() row, the saved scalars and dictionaries, the records, supply() and summary(); to_dict() at the end.
# Row Q-b (P-b, PERSONS_PORT_PLAN §9): the same with households on (SAMPLE_HOUSEHOLDS=1), plus every household_fields() row, the
# registry with its digest flags, and the households' state outside it; and its must-fail, one household's member order reversed
#   START_DATA_ROOT=<cd165891 tree> python py/tests/test_persons_layer.py [<oracle dir>] [L|Q-b]
import copy
import os
import sys

from common import Kit, ROOT
import country  # noqa: E402  (after common, which puts py/ on the path)
from core import digest
from core.digest import Packed
from people.layer import Persons
from tiers.start import create, load
from tiers.start import trace

SUMMARY_CODE = 13


def env_of(cohort):
    return {"inflation_month": 0.02 / 12.0, "food_price_yoy": 0.0, "unemployment_rate": 0.025, "wage_index": 1.0, "levers": [],
            "cohort": cohort}


def state_hash(p, n):
    if n.startswith("rec."):
        return trace.sha(getattr(p, n[4:]))
    if n == "hh_fields":
        return trace.sha(p.household_fields())
    if n.startswith("hh."):
        return trace.sha(getattr(p, n[3:]))
    if n.startswith("hhx."):
        v = getattr(p, n[4:])
        if n == "hhx.hh_members":
            # Why not the list as P holds it: py/lchh keeps a household's members as a list, Godot as a PackedInt32Array
            v = [Packed("i32", list(x)) for x in v]
        return trace.sha(v)
    return trace.sha(getattr(p, n))


def month_hashes(ps, names):
    p = ps.p
    got = {}
    for n in names:
        if not n.startswith("iface."):
            got[n] = state_hash(p, n)
    got["iface.supply"] = trace.sha(ps.supply())
    got["iface.summary"] = trace.sha(ps.summary())
    got["iface.summary_%d" % SUMMARY_CODE] = trace.sha(ps.summary(SUMMARY_CODE))
    return got


def differing(ref, got):
    return [n for n in sorted(ref) if got.get(n) != ref[n]]


def start(seed, n_per, households):
    co, qx = create.status_cohort_qx("JPN", 2024)
    prefs = load.load_json(country.load("JPN").path("regions"))["prefectures"]
    return Persons.create("JPN", seed, co, qx, prefs, n_per, 2024, households=households), env_of(co)


def run(k, d, seed, n_per, months, read, households=False):
    ps, env = start(seed, n_per, households)
    tag = "seed %d n_per %d" % (seed, n_per)
    row = "Q-b" if households else "L"
    for m in range(0, months + 1):
        if m > 0:
            ps.step(env)
        ref = digest.read_hashes(os.path.join(d, "m%02d.persons.sha.txt" % m))
        if m not in read:
            ps.supply()
            continue
        got = month_hashes(ps, ref)
        state = [n for n in ref if not n.startswith("iface.")]
        bad = differing({n: ref[n] for n in state}, got)
        if m == 0:
            k.check(not bad, "%s-0 %s: the sample start's %d hashes equal the oracle's%s" % (row, tag, len(state), (", differing " + " ".join(bad)) if bad else ""))
        else:
            k.check(not bad, "%s-1%s m%02d %s: %d of %d hashes equal the oracle's%s" % (
                row, "" if seed == 1 else "s", m, tag, len(state) - len(bad), len(state), (", differing " + " ".join(bad)) if bad else ""))
        k.check(got["iface.supply"] == ref["iface.supply"], "%s-s m%02d %s: supply() equals the oracle's" % (row, m, tag))
        k.check(got["iface.summary"] == ref["iface.summary"] and got["iface.summary_%d" % SUMMARY_CODE] == ref["iface.summary_%d" % SUMMARY_CODE],
                "%s-y m%02d %s: summary() and summary(%d) equal the oracle's" % (row, m, tag, SUMMARY_CODE))
    return ps


def check_to_dict(k, ps, d, months, row, tag):
    ref = digest.read_hashes(os.path.join(d, "m%02d.to_dict.sha.txt" % months))
    dct = ps.to_dict()
    got = {"to_dict.%s" % key: trace.sha(v) for key, v in dct.items()}
    got["to_dict"] = trace.sha(dct)
    for key, v in dct.get("households", {}).items():
        got["to_dict.households.%s" % key] = trace.sha(v)
    bad = differing(ref, got)
    k.check(not bad, "%s-d m%02d %s: to_dict() equals the oracle's (%d hashes)%s" % (row, months, tag, len(ref), (", differing " + " ".join(bad)) if bad else ""))


def must_fail_order(k, d, months):
    # One household's member order reversed after month 1 makes a later month part from the oracle (PERSONS_PORT_PLAN §9). The
    # household is the mother's of month 2's first birth: _birth links the newborn to its household's members in their order. Why not
    # a head's removal, which §9 names: in this sample no head leaves a household whose new head the order decides (months 1-13)
    ps, env = start(1, 20, True)
    ps.supply()
    ps.step(env)
    ref1 = digest.read_hashes(os.path.join(d, "m01.persons.sha.txt"))
    k.check(not differing(ref1, month_hashes(ps, ref1)), "Q-b-mf seed 1 n_per 20: the run before the reversal equals the oracle at m01")
    p = ps.p
    probe = copy.deepcopy(ps)
    probe.step(env)
    births = [r for r in probe.p.life_log if str(r[2]) == "birth" and int(r[0]) == 1]
    if not births:
        k.check(False, "Q-b-mf seed 1 n_per 20: month 2 has a birth to reverse a household at")
        return
    h = p.hh_id[list(p.pid).index(int(births[0][3]))]
    size = len(p.hh_members[h])
    p.hh_members[h].reverse()
    first = None
    for m in range(2, months + 1):
        ps.step(env)
        ref = digest.read_hashes(os.path.join(d, "m%02d.persons.sha.txt" % m))
        got = month_hashes(ps, ref)
        bad = differing(ref, got)
        if bad:
            first = (m, bad)
            break
    k.check(first is not None, "Q-b-mf seed 1 n_per 20: household %d's %d members reversed after m01 part from the oracle%s" % (
        h, size, (" first at m%02d in %s" % (first[0], " ".join(first[1]))) if first else ", but no month 2-13 differs"))


def main():
    base = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "outputs", "py_oracle", "ps")
    which = sys.argv[2] if len(sys.argv) > 2 else "all"
    k = Kit("py/tests/test_persons_layer.py")
    if which in ("all", "L"):
        d1 = os.path.join(base, "s1_n20")
        ps = run(k, d1, 1, 20, 13, set(range(0, 14)))
        check_to_dict(k, ps, d1, 13, "L", "seed 1 n_per 20")
        run(k, os.path.join(base, "s7_n30"), 7, 30, 13, {1, 13})
    if which in ("all", "Q-b"):
        h1 = os.path.join(base, "h_s1_n20")
        ps = run(k, h1, 1, 20, 13, set(range(0, 14)), households=True)
        check_to_dict(k, ps, h1, 13, "Q-b", "seed 1 n_per 20")
        run(k, os.path.join(base, "h_s7_n30"), 7, 30, 13, {0, 1, 13}, households=True)
        must_fail_order(k, h1, 13)
    k.finish()


if __name__ == "__main__":
    main()
