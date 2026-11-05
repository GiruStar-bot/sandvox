# The small tiers.gd helpers every stage group reads (cd165891: _v 50, band_of 54, _slots_in, _zeros_i, _largest)
import math

from core.gd import idiv, mini
from tiers.start import tconst as T
from tiers.start.p import PArr


def _v(p, k):
    return p.tr_spec[k]["value"]


def band_of(a):
    return mini(idiv(a, 5), T.BANDS - 1)


def _slots_in(b):
    return T.AGE_SLOTS if b == T.BANDS - 1 else 5


def _zeros_i(n):
    a = PArr("i64")
    a.resize(n)
    return a


def _largest(v, total):
    # Why sorted and not gdsort here: the comparator breaks every tie by the index, so any correct sort gives Godot's order
    n = len(v)
    out = _zeros_i(n)
    used = 0
    for i in range(n):
        out[i] = int(math.floor(v[i]))
        used += out[i]
    order = sorted(range(n), key=lambda i: (-(v[i] - math.floor(v[i])), i))
    q = 0
    while used < total:
        out[order[q % n]] += 1
        used += 1
        q += 1
    while used > total:
        i2 = order[n - 1 - (q % n)]
        if out[i2] > 0:
            out[i2] -= 1
            used -= 1
        q += 1
    return out
