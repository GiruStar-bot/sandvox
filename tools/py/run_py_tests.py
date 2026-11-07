#!/usr/bin/env python3
"""Tiered, parallel runner for the Python test suite (py/tests/test_*.py).

Why this exists (v4.1 audit, suite-speed fix): the Python suite had no runner
at all, so the only way to run it was every file, serially, including the
multi-minute build tests. The Godot suite already has tiers
(tools/run_tests.sh + tools/test/tiers.json); this gives the Python suite the
same shape:

  python3 tools/py/run_py_tests.py                 # --tier full, -j 3
  python3 tools/py/run_py_tests.py --tier fast     # PR gate: lint/qnan/age_d (seconds)
  python3 tools/py/run_py_tests.py test_country    # name filters (substring)
  python3 tools/py/run_py_tests.py --list          # list the selected tests only

Tiers:
  fast: the sub-10-second checks measured in the v4.1 audit
        (test_lint_core ~0.4s, test_qnan ~0.0s, test_age_d ~1.4s).
  full: every standalone py/tests/test_*.py, run in parallel (-j). The wall
        time is bounded by the slowest single test, not the sum. Harnesses
        that require an oracle trace directory argument (NEEDS_ARGS below)
        are reported as SKIP, not run bare.

Each test is a standalone script that prints a final `RESULT {json}` line;
a test passes only if it exits 0 AND its RESULT line reports failed == 0
(a missing RESULT line is a failure, mirroring tools/run_tests.sh).
Per-test wall times are always printed: timings that are not shown cannot
be managed.

Known environment/fixture dependencies (pre-existing, verified identical
on unmodified main): test_gdsort.py needs outputs/py_oracle/gdsort.json
and test_e0_econ.py needs the econ oracle dump, both produced by Godot
tools (tools/py/oracle_dump*.gd), not by make_oracle.py; test_nb_twins.py
needs the optional llvmlite package; test_world_tables.py needs
data/modern/checks.json, which the public repo does not ship;
test_persons_layer.py in its default "all" mode needs four sample dump
sets (s1_n20, s7_n30, h_s1_n20, h_s7_n30, persons + to_dict series) of
which make_oracle.py generates only the s1_n20 persons series that
test_country.py consumes. Without those fixtures these tests fail on a
clean clone exactly as before this runner existed.
"""
import argparse
import concurrent.futures
import json
import os
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TEST_DIR = os.path.join(ROOT, "py", "tests")

FAST = ["test_lint_core.py", "test_qnan.py", "test_age_d.py"]

# Harnesses that cannot run bare: they take an oracle trace directory as
# argv[1] (produced by the Godot-side trace tools) and crash without it.
# The full tier reports them as SKIP instead of pretending they failed;
# run them directly with a trace dir when doing oracle parity work.
NEEDS_ARGS = {
    "test_econ_parity.py",
    "test_mech.py",
    "test_persons_mf.py",
    "test_persons_resume.py",
    "test_persons_stage.py",
    "test_resume.py",
    "test_start_stage.py",
}


def discover():
    return sorted(f for f in os.listdir(TEST_DIR) if f.startswith("test_") and f.endswith(".py"))


def run_one(name, timeout):
    path = os.path.join(TEST_DIR, name)
    t0 = time.time()
    try:
        proc = subprocess.run(
            [sys.executable, path],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        elapsed = time.time() - t0
        out = proc.stdout + proc.stderr
        result = None
        for line in out.splitlines():
            if line.startswith("RESULT "):
                try:
                    result = json.loads(line[len("RESULT "):])
                except ValueError:
                    result = None
        ok = proc.returncode == 0 and result is not None and int(result.get("failed", 1)) == 0
        detail = ""
        if result is None:
            detail = "no RESULT line"
        elif int(result.get("failed", 0)) != 0:
            detail = "failed=%s" % result.get("failed")
        elif proc.returncode != 0:
            detail = "exit=%d" % proc.returncode
        return name, ok, elapsed, detail, out
    except subprocess.TimeoutExpired:
        return name, False, time.time() - t0, "timeout>%ds" % timeout, ""


def main():
    ap = argparse.ArgumentParser(description="Tiered parallel runner for py/tests")
    ap.add_argument("--tier", choices=["fast", "full"], default="full")
    ap.add_argument("-j", type=int, default=3, help="parallel test processes (default 3)")
    ap.add_argument("--timeout", type=int, default=1800, help="per-test timeout in seconds")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("filters", nargs="*", help="substring filters on test file names")
    args = ap.parse_args()

    names = FAST if args.tier == "fast" else discover()
    if args.filters:
        names = [n for n in names if any(f in n for f in args.filters)]
    skipped = [n for n in names if n in NEEDS_ARGS] if not args.filters else []
    names = [n for n in names if n not in NEEDS_ARGS or args.filters]
    if args.list:
        for n in names:
            print(n)
        for n in skipped:
            print("%s (SKIP: needs an oracle trace dir argument)" % n)
        return 0
    if not names:
        print("no tests selected")
        return 2
    for n in skipped:
        print("SKIP %-28s (needs an oracle trace dir argument)" % n)

    print("running %d test(s), tier=%s, -j %d" % (len(names), args.tier, args.j))
    t0 = time.time()
    results = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, args.j)) as ex:
        futs = {ex.submit(run_one, n, args.timeout): n for n in names}
        for fut in concurrent.futures.as_completed(futs):
            name, ok, elapsed, detail, _out = fut.result()
            results[name] = (ok, elapsed, detail)
            print("%s %-28s %7.1fs %s" % ("PASS" if ok else "FAIL", name, elapsed, detail), flush=True)
    wall = time.time() - t0
    n_fail = sum(1 for ok, _e, _d in results.values() if not ok)
    print("-" * 60)
    print("%d passed, %d failed, wall %.1fs (sum of tests %.1fs)" % (
        len(results) - n_fail, n_fail, wall, sum(e for _o, e, _d in results.values())))
    return 1 if n_fail else 0


if __name__ == "__main__":
    sys.exit(main())
