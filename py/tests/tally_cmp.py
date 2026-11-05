# The tiers' tally (tr_margins["t22"]) compared by value, P2c's rule: every key, every number with its type (int or float) and its
# bits, arrays element by element whatever their kind (a Python list or a Godot packed array), the "usec" keys left out. Why not by
# hash: tr_margins is a tally and not state (CORE_GUIDE §2), and the Python month keeps several of its arrays as lists where
# tiers.gd keeps packed arrays, which a hash would count as a difference of kind, not of value
import struct

from core.digest import Packed


def _plain(v):
    if isinstance(v, Packed):
        return [x.item() if hasattr(x, "item") else x for x in v.a]
    if isinstance(v, list) and hasattr(v, "kind"):
        return list(v)
    return v


def _num(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def diff(a, b, path="t22", out=None, packed=False):
    # packed: inside a packed array on either side, where an element's kind is the array's, so an int and a float of one value agree
    out = [] if out is None else out
    packed = packed or isinstance(a, Packed) or isinstance(b, Packed) or hasattr(a, "kind") or hasattr(b, "kind")
    a, b = _plain(a), _plain(b)
    if isinstance(a, dict) and isinstance(b, dict):
        ka = {k for k in a if not (isinstance(k, str) and k.startswith("usec"))}
        kb = {k for k in b if not (isinstance(k, str) and k.startswith("usec"))}
        for k in sorted(ka ^ kb, key=str):
            out.append("%s/%s missing on one side" % (path, k))
        for k in sorted(ka & kb, key=str):
            diff(a[k], b[k], "%s/%s" % (path, k), out)
    elif isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            out.append("%s length %d vs %d" % (path, len(a), len(b)))
        for i, (x, y) in enumerate(zip(a, b)):
            diff(x, y, "%s[%d]" % (path, i), out, packed)
    elif packed and _num(a) and _num(b):
        if struct.pack("<d", float(a)) != struct.pack("<d", float(b)):
            out.append("%s %r vs %r" % (path, a, b))
    elif isinstance(a, float) and isinstance(b, float):
        if struct.pack("<d", a) != struct.pack("<d", b):
            out.append("%s %r vs %r" % (path, a, b))
    elif type(a) is not type(b) or a != b:
        out.append("%s %r vs %r" % (path, a, b))
    return out
