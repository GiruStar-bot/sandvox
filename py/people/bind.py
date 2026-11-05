# The persons' month object is the start's P (py/tiers/start/p.py: every var and const of people.gd, packed arrays as PArr). This
# binds the REL builder's shim methods (relations, groups and actions' callbacks: PERSONS_PORT_PLAN §7, S2) onto it, so the start's
# state steps without a copy. Why not the shim's own P: it holds plain lists with the kinds aside, and the start, loop C and
# TR.step all read and write the same arrays. S2 replaces this file when the shim becomes people's methods.
from people import act, grp, rel, shim
from tiers.start import persons  # noqa: F401  (binds the start's persons functions onto P)
from tiers.start.p import P

_SKIP = {"__init__", "read", "tree", "u", "normal", "section_a", "section_b"}
for _name, _f in list(vars(shim.P).items()):
    if callable(_f) and not _name.startswith("__") and _name not in _SKIP and not hasattr(P, _name):
        setattr(P, _name, _f)
P.REL = rel
P.GRP = grp
P.ACT = act
from people import hh_bind  # noqa: E402,F401  (after the shim's methods: its people.gd move_to and move_reason replace the shim's)
