import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "tools", "py"))
import lint_core  # noqa: E402

BAD = {
    "R6-sum": "x = np.sum(a)\n",
    "R6-libm": "y = math.exp(z)\n",
    "R6-rand": "r = np.random.rand()\n",
    "R6-time": "t = time.time()\n",
    "R6-copy": "def h64(hd, a, b, c):\n",
}
GOOD = ["y = detmath.exp(z)\n", "s = np.cumsum(a)\n", "t = time.time()  # lint-ok: into p.timing\n", "# np.sum is banned\n"]

fails = []
for rid, line in BAD.items():
    got = [h[0] for h in lint_core.lint_lines("py/x/m.py", [line])]
    if got != [rid]:
        fails.append("must-fail %s not caught: %r -> %r" % (rid, line, got))
if lint_core.lint_lines("py/core/keyed.py", [BAD["R6-copy"]]):
    fails.append("a primitive defined in py/core must not be flagged")
for line in GOOD:
    got = lint_core.lint_lines("py/x/m.py", [line])
    if got:
        fails.append("false hit on %r: %r" % (line, got))
real = lint_core.lint_r6()
if real:
    fails.append("py/ has %d unaccepted hits: %r" % (len(real), real[:3]))
for f in fails:
    print("FAIL", f)
print('RESULT {"file": "py/tests/test_lint_core.py", "failed": %d, "checks": %d}' % (len(fails), len(BAD) + 2 + len(GOOD)))
sys.exit(1 if fails else 0)
