# REL_PORT_PLAN row COV (AMENDED K1): every rule line of py/people's rel.py, grp.py and act.py runs at least once over run_rel.py's rows,
# except the lines the plan declares unreachable
#   python py/tests/run_rel_cov.py <oracle dir>
import ast
import os
import sys
import trace

from common import Kit, ROOT

FILES = {name: os.path.join(ROOT, "py", "people", name) for name in ("rel.py", "grp.py", "act.py")}
# (file, enclosing function, the line's text): REL_PORT_PLAN AMENDED K1's list, each reason there
UNREACHABLE = {("act.py", "feasible", 'return "no reason to move"'),
               ("rel.py", "build", "p.contact_idx[i * C + slot(p, i, found)] = -1"),
               ("rel.py", "replenish", "p.contact_idx[i * C + slot(p, i, j)] = -1"),
               ("rel.py", "pick_partner", "return -1@last")}


def unreachable_lines(name, path):
    with open(path, encoding="utf-8") as f:
        src = f.read()
    lines = src.splitlines()
    out = set()
    for node in ast.walk(ast.parse(src)):
        if not isinstance(node, ast.FunctionDef):
            continue
        body = range(node.lineno, node.end_lineno + 1)
        for (fn, func, text) in UNREACHABLE:
            if fn != name or func != node.name:
                continue
            if text.endswith("@last"):
                want = text[:-5]
                hits = [ln for ln in body if lines[ln - 1].strip() == want]
                out.add(hits[-1])
            else:
                out |= {ln for ln in body if lines[ln - 1].strip() == text}
    return out


def main():
    hits = set()
    paths = {os.path.realpath(p): n for n, p in FILES.items()}

    def tracer(frame, event, arg):
        fn = paths.get(os.path.realpath(frame.f_code.co_filename))
        if fn is None:
            return None

        def local(frame2, event2, arg2):
            if event2 == "line":
                hits.add((fn, frame2.f_lineno))
            return local
        if event == "call":
            hits.add((fn, frame.f_lineno))
        return local

    for m in [m for m in sys.modules if m == "people" or m.startswith("people.")]:
        del sys.modules[m]
    sys.settrace(tracer)
    import run_rel
    sys.argv = sys.argv[:3]
    code = 0
    try:
        run_rel.main()
    except SystemExit as e:
        code = e.code or 0
    finally:
        sys.settrace(None)
    kit = Kit("py/tests/run_rel_cov.py")
    kit.check(code == 0, "COV: the rows themselves pass under the trace (exit %s)" % code)
    for name, path in FILES.items():
        exe = {ln for ln in trace._find_executable_linenos(path) if ln is not None}
        un = unreachable_lines(name, path)
        missing = sorted(ln for ln in exe if (name, ln) not in hits and ln not in un)
        ran_un = sorted(ln for ln in un if (name, ln) in hits)
        kit.check(not missing, "COV %s: %d executable lines, %d declared unreachable, not run %s" % (name, len(exe), len(un), missing[:20]))
        kit.check(not ran_un, "COV %s: no line declared unreachable ran, ran %s" % (name, ran_un))
    kit.finish()


if __name__ == "__main__":
    main()
