# The tiers' state: its fields' digest (every tr_* field but tr_margins) and its save, on core/digest's typed tree
import hashlib
import json
import os

from core.digest import (KINDS, CANON_KIND, Packed, PackedStr, GInt, load, canon, enc, month_digest,  # noqa: F401
                         read_hashes)


def field_hashes(st):
    out = {}
    for n in sorted(k for k in st if k.startswith("tr_") and k != "tr_margins"):
        h = hashlib.sha256()
        canon(h, st[n])
        out[n] = h.hexdigest()
    return out


def digest_st(p):
    # The tiers digest of a month St, one field built and hashed at a time
    out = {}
    for n in p.fields():
        h = hashlib.sha256()
        canon(h, p.field(n))
        out[n] = h.hexdigest()
    return month_digest(out), out


def digest(st):
    hs = field_hashes(st)
    return month_digest(hs), hs


SAVE_SCALARS = ("hh_spec", "month", "seed_v", "base_year")


def save(p, d):
    # The whole state a month reads or a digest covers: every tr_* field (as St.field gives it, in the oracle's kinds) and the
    # scalars; load() reads it back. Why every tr_* field and not the month's working set: a field left out comes back empty, which
    # is what made the GDScript save's restore differ in four fields (TO_PM_PY, the resume check)
    os.makedirs(d, exist_ok=True)
    files = [0]
    tree = {}
    for k in p.fields():
        tree[k] = enc(p.field(k), d, files)
    for k in SAVE_SCALARS:
        tree[k] = enc(getattr(p, k), d, files)
    with open(os.path.join(d, "state.json"), "w", encoding="utf-8") as f:
        json.dump(tree, f)
