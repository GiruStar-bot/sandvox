# The Python side of tools/py/start_trace.gd: the same "name hex" lines at a stage (every tr_* field, tr_margins without its
# "usec" keys; the persons' registry arrays and scalars; the stage's locals), and a stage's whole state read back from the
# oracle's typed tree
import hashlib

from core import digest
from tiers.start.p import P, from_tree, to_tree

PERSON_SCALARS = ["n", "pref_pop", "pension", "wage_index", "price_index", "spec", "hh_spec", "seed_v", "base_year", "month"]


def _strip_usec(v):
    if isinstance(v, dict):
        return {k: _strip_usec(x) for k, x in v.items() if not (isinstance(k, str) and k.startswith("usec"))}
    return v


def sha(v):
    h = hashlib.sha256()
    digest.canon(h, to_tree(v))
    return h.hexdigest()


def stage_hashes(p, ctx, names):
    # The hashes of the names the oracle wrote at this stage (its .sha.txt), so both sides hash the same set
    out = {}
    for n in names:
        if n.startswith("persons."):
            out[n] = sha(getattr(p, n[len("persons."):]))
        elif n.startswith("local."):
            k = n[len("local."):]
            out[n] = sha(ctx[k]) if k in ctx else "missing"
        elif n == "tr_margins":
            out[n] = sha(_strip_usec(p.tr_margins))
        else:
            out[n] = sha(getattr(p, n))
    return out


def load_stage(d):
    # p and ctx from start_trace.gd's full dump of a stage (TRACE_FULL)
    tree = digest.load(d)
    p = P()
    p.tiers = True
    ctx = {}
    # Why kept: a persons' dump before c7 holds only the persons' tr_* reads, and the test must tell a field the dump left out from one
    # the sections wrote
    p.dump_keys = set(tree)
    for k, v in tree.items():
        if k.startswith("tr_"):
            setattr(p, k, from_tree(v))
        elif k.startswith("persons."):
            setattr(p, k[len("persons."):], from_tree(v))
        elif k.startswith("local."):
            ctx[k[len("local."):]] = from_tree(v)
    # Why not keep the dump's two copies: in Godot cp's dictionaries are the ones it gave p (tiers.gd 96-98, 119), so a later
    # stage's change to p.tr_nh_couples (_place_nonhead) moves local.cp too
    cp = ctx.get("cp")
    if isinstance(cp, dict):
        for ck, pf in (("couples", "tr_couples"), ("nonhead", "tr_nh_couples")):
            if ck in cp and sha(cp[ck]) == sha(getattr(p, pf)):
                cp[ck] = getattr(p, pf)
        if "h4s" in cp and "h4s" in p.tr_margins and sha(cp["h4s"]) == sha(p.tr_margins["h4s"]):
            p.tr_margins["h4s"] = cp["h4s"]
    return p, ctx
