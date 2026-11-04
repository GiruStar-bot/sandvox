"""Known failures by row (V114, TO_E 14:11): a known_failures.json entry names the rows it excuses, and a test's failure is KNOWN
only if every failing row is one of them. Used by tools/run_tests.sh; tested by tools/test/test_known_rows.py.

classify(entry, result, reasons) -> (status, reasons, warnings)
  entry   the known_failures.json entry for the file, or None
  result  the test's RESULT dict, or None
  reasons the runner's reasons for a FAIL before the known entry is read
"""

import re

LINE_ROW = re.compile(r"^(line \d+):")
SUB_ROW = re.compile(r"^(\S+ \([a-z]{1,3}\))[ :]")


def _row_reason(r):
    return r == "exit 1" or r.endswith(" failed")


def row_name(label):
    """A failure label's row name: its first token with a sub-row such as "(a)" or "(ii)", or "line N" for labels of the form
    "line N: ..." (V115, TO_E 15:35)"""
    m = LINE_ROW.match(label) or SUB_ROW.match(label)
    if m:
        return m.group(1)
    return label.split(" ", 1)[0].rstrip(":")


def classify(entry, result, reasons, today):
    reasons = list(reasons)
    warns = []
    if entry is None:
        return ("FAIL" if reasons else "PASS"), reasons, warns
    if str(entry.get("expires", "")) < today:
        if reasons:
            reasons.append("known entry expired %s" % entry.get("expires"))
        return ("FAIL" if reasons else "PASS"), reasons, warns
    rows = entry.get("rows")
    if not reasons:
        warns.append("listed in known_failures.json but passed: remove the entry")
        return "WARN", reasons, warns
    if not isinstance(rows, list) or not rows or any(not isinstance(r, str) or len(r.strip()) < 2 for r in rows):
        reasons.append("known entry names no rows, or an empty or too-short row name")
        return "FAIL", reasons, warns
    # Why not a file match (before): a new failing row in a listed file was hidden as KNOWN (V114's T1s-nh mutation)
    other = [r for r in reasons if not _row_reason(r)]
    failures = (result or {}).get("failures", [])
    failed = int((result or {}).get("failed", 0))
    if result is None or failed > len(failures):
        reasons.append("failures not all listed in RESULT (%d failed, %d listed)" % (failed, len(failures)))
        return "FAIL", reasons, warns
    if not failures:
        # Why not KNOWN (before V115): a crash or an unreported failure exits 1 with no row named, and is not the registered one
        reasons.append("failed without naming a failed row")
        return "FAIL", reasons, warns
    # Why not a prefix of the label (before V115): a short or empty row name matched every label
    unknown = [f for f in failures if row_name(f) not in rows]
    if unknown:
        reasons.append("not a known row: " + unknown[0][:120])
    if other or unknown:
        return "FAIL", reasons, warns
    passed_rows = [r for r in rows if not any(row_name(f) == r for f in failures)]
    if passed_rows:
        warns.append("known rows passed: %s (remove them)" % "; ".join(passed_rows))
    return "KNOWN", reasons, warns
