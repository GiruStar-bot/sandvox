"""What known_rows.classify must do (V114, TO_E 14:11). One line per case: 'ok <label>' or 'FAIL <label>'. Run by test_known_rows.gd."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import known_rows

TODAY = "2026-10-31"
ENTRY = {"file": "sim/modern/test_modern_tiers.gd", "expires": "2026-11-14", "rows": ["T1s-lp"]}
LP = "T1s-lp (R85 第49-2表, CHECK, ±5pt T) 16 of 42 cells beyond 5 points"
NH = "T1s-nh (§12.12 (9), CHECK) households with a non-head couple: 3 of 47 below"


def result(failures, failed=None):
    return {"failed": len(failures) if failed is None else failed, "failures": failures}


def reasons_of(res):
    return ["exit 1", "%d failed" % res["failed"]] if res["failed"] else []


def case(label, entry, res, want, extra=()):
    st, rs, ws = known_rows.classify(entry, res, reasons_of(res) + list(extra), TODAY)
    # Why not the reasons verbatim: the runner counts the words "SCRIPT ERROR" in a log as a script error of this test
    print(("ok   " if st == want else "FAIL ") + "%s: %s (want %s) %s" % (label, st, want, "; ".join(rs + ws).replace("SCRIPT ERROR", "script-error")))


# V114's mutation: a known file with a second, unregistered row broken must be a FAIL, not KNOWN
case("V114 mutation, T1s-nh broken beside the known T1s-lp", ENTRY, result([LP, NH]), "FAIL")
case("only the known row fails", ENTRY, result([LP]), "KNOWN")
case("an entry naming no rows", {"file": ENTRY["file"], "expires": "2026-11-14"}, result([LP]), "FAIL")
case("failures beyond the RESULT's list", ENTRY, result([LP], failed=2), "FAIL")
case("a script error beside the known row", ENTRY, result([LP]), "FAIL", ["1 SCRIPT ERROR"])
case("an expired entry", dict(ENTRY, expires="2026-10-30"), result([LP]), "FAIL")
case("the listed file passes", ENTRY, result([]), "WARN")
case("a file with no entry fails", None, result([NH]), "FAIL")
case("a known row that passed is reported", dict(ENTRY, rows=["T1s-lp", "T1s-cm"]), result([LP]), "KNOWN")
# V115 (TO_E 15:35): an empty or too-short row name matched every label as a prefix; the row name must be exact
case("V115 an empty row name", dict(ENTRY, rows=[""]), result([NH]), "FAIL")
case("V115 a row name that is only a prefix", dict(ENTRY, rows=["T1s"]), result([NH]), "FAIL")
case("V115 a prefix of another row's name", dict(ENTRY, rows=["T1s-n"]), result([NH]), "FAIL")
# V115: exit 1 with no failed row named (a crash, an unreported failure) is not the registered failure
case("V115 exit 1 with no row named", ENTRY, {"failed": 0, "failures": []}, "FAIL", ["exit 1"])
case("a 'line N:' row matched by its name", {"file": "x", "expires": "2026-11-14", "rows": ["line 1"]}, result(["line 1: one apex over everyone ...", "line 3: waiting ..."]), "FAIL")
case("V115 a row does not excuse its sub-row", dict(ENTRY, rows=["T1s-hh0"]), result(["T1s-hh0 (a) (V113) the children outside the window"]), "FAIL")
case("the 'line N:' rows both known", {"file": "x", "expires": "2026-11-14", "rows": ["line 1", "line 3"]}, result(["line 1: one apex over everyone ...", "line 3: waiting ..."]), "KNOWN")
