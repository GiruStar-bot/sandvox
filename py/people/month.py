# people.gd step (1240-1307 at cd165891) as its sections, cut where tools/py/persons_trace.gd checks them (c0 .. c8). Each section
# reads and writes p (the start's P with the persons' methods bound) and ctx (step's locals by their GDScript names). The owners
# (PERSONS_PORT_PLAN §7): c1, c4, c5 and c8 are Cpくん's; c2, c3, c6 and c7 are the REL builder's (S1, S4, S3)
import importlib

from people import bind  # noqa: F401

SECTIONS = [
    ("c1", "people.loop_c", "sec_c1"),
    ("c2", "people.sections", "sec_c2"),
    ("c3", "people.sections", "sec_c3"),
    ("c4", "people.loop_c", "sec_c4"),
    ("c5", "people.loop_c", "sec_c5"),
    ("c6", "people.sections", "sec_c6"),
    ("c7", "people.sections", "sec_c7"),
    ("c8", "people.tiers_step", "sec_c8"),
]
NAMES = ["c0"] + [s[0] for s in SECTIONS]


def section_fn(name):
    for st, mod, fn in SECTIONS:
        if st == name:
            return getattr(importlib.import_module(mod), fn)
    raise KeyError(name)


def run(p, ctx, first, last, env):
    # The sections after `first` through `last` of one month
    for i in range(NAMES.index(first) + 1, NAMES.index(last) + 1):
        section_fn(NAMES[i])(p, ctx, env)


def step(p, env):
    ctx = {}
    run(p, ctx, "c0", "c8", env)
