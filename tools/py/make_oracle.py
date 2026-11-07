#!/usr/bin/env python3
"""Generate the Python-port oracle dumps used by py/tests/test_country.py.

Moved out of run_simulation.py (v4.1 audit, suite-speed fix): generating test
fixtures is a development action, not a simulation action. The CLI no longer
creates these files as a side effect of running a simulation.

Usage:
  python3 tools/py/make_oracle.py           # generate only if missing
  python3 tools/py/make_oracle.py --force   # regenerate even if present

PROVENANCE / LIMITATION: these dumps are produced by the Python port itself
(the tiers start build and the Persons layer in this repository). They are a
SELF-consistency oracle for the Python port: test_country.py passing against
them proves the port still matches its own recorded behaviour, NOT parity
with the Godot implementation. Godot parity must be established separately
(e.g. tools/py/oracle_dump.gd) and is not claimed here.

Output (tracked in git; see .gitignore):
  outputs/py_oracle/ps/s1_n20/m00..m13.persons.sha.txt
  outputs/py_oracle/st/06_class.sha.txt
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def oracle_paths():
    ps_dir = os.path.join(ROOT, "outputs", "py_oracle", "ps", "s1_n20")
    st_dir = os.path.join(ROOT, "outputs", "py_oracle", "st")
    return ps_dir, st_dir, os.path.join(ps_dir, "m13.persons.sha.txt"), os.path.join(st_dir, "06_class.sha.txt")


def generate():
    ps_dir, st_dir, _m13, st_file = oracle_paths()
    sys.path.insert(0, os.path.join(ROOT, "py"))
    sys.path.insert(0, os.path.join(ROOT, "py", "tests"))
    import test_persons_layer as TPL
    from tiers.start import build, create, trace

    os.makedirs(ps_dir, exist_ok=True)
    os.makedirs(st_dir, exist_ok=True)

    ps, env1 = TPL.start(1, 20, False)
    names = [str(r[0]) for r in ps.p.fields()] + list(trace.PERSON_SCALARS) + [
        "iface.supply",
        "iface.summary",
        "iface.summary_13",
    ]
    for m in range(0, 14):
        if m > 0:
            ps.step(env1)
        hs = TPL.month_hashes(ps, names)
        with open(os.path.join(ps_dir, "m%02d.persons.sha.txt" % m), "w", encoding="utf-8") as f:
            for k in sorted(hs):
                f.write(f"{k} {hs[k]}\n")

    from tiers.start import cache as start_cache

    def _build_06():
        pp, prefs = create.inputs()
        cc = {"prefectures": prefs}
        build.run(pp, cc, None, "06_class")
        return pp, cc

    # Deterministic build; reuse the shared cache (tiers/start/cache.py)
    # so regenerating the dumps does not repay the ~68 s stage cost.
    p, ctx = start_cache.get_or_build("inputs", "06_class", _build_06)
    st_names = (
        ["persons." + str(r[0]) for r in p.fields()]
        + ["persons." + s for s in trace.PERSON_SCALARS]
        + ["local." + k for k in sorted(ctx.keys())]
        + [k for k in sorted(dir(p)) if k.startswith("tr_") and not callable(getattr(p, k))]
    )
    got = trace.stage_hashes(p, ctx, st_names)
    with open(st_file, "w", encoding="utf-8") as f:
        for k in sorted(got):
            f.write(f"{k} {got[k]}\n")


def main():
    force = "--force" in sys.argv
    _ps, _st, m13_file, st_file = oracle_paths()
    if not force and os.path.exists(m13_file) and os.path.exists(st_file):
        print("oracle dumps already present (use --force to regenerate):")
        print(" ", os.path.relpath(m13_file, ROOT))
        print(" ", os.path.relpath(st_file, ROOT))
        return 0
    print("generating oracle dumps (self-oracle of the Python port; see module docstring)...")
    generate()
    print("wrote:")
    print(" ", os.path.relpath(m13_file, ROOT))
    print(" ", os.path.relpath(st_file, ROOT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
