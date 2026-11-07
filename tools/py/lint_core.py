"""CORE_GUIDE conformance and change-scope lint (VERIFY_RUBRIC R6, R7).

Usage:
  python tools/py/lint_core.py                       # R6 over py/ (tests excluded)
  python tools/py/lint_core.py --base origin/modern --plan docs/team/modern/py/X_PLAN.md
                                                     # R6 + R7: every changed file is named in the plan

A line may carry `# lint-ok: <reason>` to accept a hit. Exit 1 on any unaccepted hit.
"""
import argparse
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Why not an AST walk: the rules are about call names, and a regex with a no-dot/no-word lookbehind
# keeps detmath.exp apart from math.exp at a fraction of the code; a miss shows up in the oracle digests anyway.
NB = r"(?<![\w.])"
RULES = [
    ("R6-sum", NB + r"(np|numpy)\.(sum|mean|dot|nansum|average)\(", "float reduction out of declared order (CORE_GUIDE 4)"),
    ("R6-sum", NB + r"math\.fsum\(", "float reduction out of declared order (CORE_GUIDE 4)"),
    ("R6-libm", NB + r"math\.(exp|log|log2|log10|pow)\(", "platform libm; use detmath (CORE_GUIDE 3)"),
    ("R6-libm", NB + r"(np|numpy)\.(exp|log|power|log2|log10)\(", "platform libm; use detmath (CORE_GUIDE 3)"),
    ("R6-rand", NB + r"(np|numpy)\.random\b", "unkeyed draw; use keyed (CORE_GUIDE 3)"),
    ("R6-rand", r"^\s*(import random\b|from random\b)", "unkeyed draw; use keyed (CORE_GUIDE 3)"),
    ("R6-time", NB + r"time\.(time|perf_counter|monotonic)\(", "wall clock; allowed only into p.timing (CORE_GUIDE 2)"),
]
CORE_NAMES = ("h64", "head", "u_from", "inv_normal", "gd_round", "idiv", "imod")
COPY = re.compile(r"^def (" + "|".join(CORE_NAMES) + r")\(")


def py_files():
    if os.path.exists(os.path.join(ROOT, "run_simulation.py")):
        yield "run_simulation.py"
    for d, _, fs in os.walk(os.path.join(ROOT, "py")):
        rel = os.path.relpath(d, ROOT).replace(os.sep, "/")
        if rel.startswith("py/tests"):
            continue
        for f in fs:
            if f.endswith(".py"):
                yield rel + "/" + f


def lint_lines(rel, lines):
    hits = []
    in_core = rel.startswith("py/core/")
    for n, line in enumerate(lines, 1):
        if "# lint-ok:" in line or line.lstrip().startswith("#"):
            continue
        for rid, pat, why in RULES:
            if re.search(pat, line):
                hits.append((rid, rel, n, why, line.strip()))
        if not in_core and COPY.match(line):
            hits.append(("R6-copy", rel, n, "a py/core primitive defined outside py/core (CORE_GUIDE 6)", line.strip()))
    return hits


def lint_r6():
    hits = []
    for rel in py_files():
        with open(os.path.join(ROOT, rel), encoding="utf-8") as fh:
            hits += lint_lines(rel, fh.readlines())
    return hits


def lint_r7(base, plan):
    out = subprocess.run(["git", "diff", "--name-only", base + "...HEAD"], cwd=ROOT,
                         capture_output=True, text=True, check=True).stdout.split()
    with open(os.path.join(ROOT, plan), encoding="utf-8") as fh:
        text = fh.read()
    hits = []
    for f in out:
        if f.startswith("docs/") or f in text or os.path.basename(f) in text:
            continue
        hits.append(("R7-scope", f, 0, "changed but not named in " + plan, ""))
    return hits


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base")
    ap.add_argument("--plan")
    a = ap.parse_args()
    hits = lint_r6()
    if a.base and a.plan:
        hits += lint_r7(a.base, a.plan)
    for rid, f, n, why, src in hits:
        print("%s %s:%d %s | %s" % (rid, f, n, why, src))
    print("RESULT lint_core hits=%d" % len(hits))
    sys.exit(1 if hits else 0)


if __name__ == "__main__":
    main()
