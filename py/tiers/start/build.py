# TR.build_start (tiers.gd 60-299 at cd165891) as its stages, cut where tools/py/start_trace.gd checks them. Each stage reads and
# writes p and ctx, ctx holding build_start's locals by their GDScript names (and "prefectures")
import importlib

from tiers.start import persons  # noqa: F401  (binds the persons functions onto P)

STAGES = [
    ("01_base", "a_fit", "st01_base"),
    ("02_couples", "a_fit", "st02_couples"),
    ("03_fit", "a_fit", "st03_fit"),
    ("04_cap_floor", "a_fit", "st04_cap_floor"),
    ("05_round", "a_fit", "st05_round"),
    ("06_class", "b_class", "st06_class"),
    ("07_cells", "b_class", "st07_cells"),
    ("08_units", "b_class", "st08_units"),
    ("09_individuals", "c_points", "st09_individuals"),
    ("10_drop_empty", "c_points", "st10_drop_empty"),
    ("11_class_residual", "c_points", "st11_class_residual"),
    ("12_points", "c_points", "st12_points"),
    ("13_transfers", "f_rest", "st13_transfers"),
    ("14_households", "d_households", "st14_households"),
    ("15_never_married", "f_rest", "st15_never_married"),
    ("16_married_apart", "f_rest", "st16_married_apart"),
    ("17_instruments", "f_rest", "st17_instruments"),
    ("18_t21", "e_t21", "st18_t21"),
]
NAMES = [s[0] for s in STAGES]


def stage_fn(name):
    # Why a lookup at run time and not imports at the top: each stage group's module can be ported and tested alone
    for st, mod, fn in STAGES:
        if st == name:
            return getattr(importlib.import_module("tiers.start." + mod), fn)
    raise KeyError(name)


def run(p, ctx, first, last, on_stage=None):
    # The stages after `first` (exclusive; None: from the start) through `last` (inclusive)
    i0 = 0 if first is None else NAMES.index(first) + 1
    i1 = NAMES.index(last)
    for i in range(i0, i1 + 1):
        stage_fn(NAMES[i])(p, ctx)
        if on_stage:
            on_stage(NAMES[i], p, ctx)


def build_start(p, prefectures, on_stage=None):
    ctx = {"prefectures": prefectures}
    run(p, ctx, None, NAMES[-1], on_stage)
    return ctx
