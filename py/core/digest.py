# The typed tree both layers' oracle dumps write (PY_TRIAL_PLAN §3) and the per-field digest over the canonical bytes of
# oracle_dump.gd's _canon, shared by the tiers and econ (CORE_GUIDE §6)
import hashlib
import json
import os
import struct
import sys
from array import array

import numpy as np

KINDS = {"i64": np.int64, "i32": np.int32, "f64": np.float64, "f32": np.float32, "u8": np.uint8}
CANON_KIND = {"i64": b"q", "i32": b"l", "f64": b"D", "f32": b"F", "u8": b"B"}


class Packed:
    # A Godot packed array: its kind kept beside the values, because the digest and the month's integer or float arithmetic read it
    __slots__ = ("kind", "a")

    def __init__(self, kind, a):
        self.kind = kind
        self.a = a

    def __len__(self):
        return len(self.a)


class PackedStr(list):
    pass


class GInt(int):
    pass


AS_LISTS = [False]


def _dec(node, d):
    if node is None or isinstance(node, bool):
        return node
    if "i" in node:
        return int(node["i"])
    if "f" in node:
        return struct.unpack("<d", struct.pack("<q", int(node["f"])))[0]
    if "s" in node:
        return node["s"]
    if "a" in node:
        return [_dec(x, d) for x in node["a"]]
    if "d" in node:
        return {_dec(k, d): _dec(v, d) for k, v in node["d"]}
    if "p" in node:
        if node["p"] == "str":
            return PackedStr(node["v"])
        if "hex" in node:
            raw = bytes.fromhex(node["hex"])
        else:
            with open(os.path.join(d, node["file"]), "rb") as f:
                raw = f.read()
        if AS_LISTS[0] and node["p"] in ("f64", "f32"):
            # Why a typed array for floats: a list holds a 24-byte object per float
            fa = array("d" if node["p"] == "f64" else "f", raw)
            if sys.byteorder != "little":
                fa.byteswap()
            return Packed(node["p"], fa)
        a = np.frombuffer(raw, dtype=KINDS[node["p"]])
        del raw
        return Packed(node["p"], a.tolist() if AS_LISTS[0] else a.copy())
    raise ValueError("unknown node %r" % (node,))


def _hook(d):
    # Why an object hook: json.load would first hold the whole typed tree (its tr_hh alone is millions of small dicts) beside the
    # decoded one; the hook decodes each node as it is parsed, innermost first
    def hook(node):
        if len(node) == 1 or "p" in node:
            if "i" in node:
                return int(node["i"])
            if "f" in node:
                return struct.unpack("<d", struct.pack("<q", int(node["f"])))[0]
            if "s" in node:
                return node["s"]
            if "a" in node:
                return node["a"]
            if "d" in node:
                return {k: v for k, v in node["d"]}
            if "p" in node:
                return _dec(node, d)
        return node
    return hook


def load(d, as_lists=False):
    # as_lists: each packed array read straight into a Python list (the pure month's form), so the NumPy copy never coexists with it
    AS_LISTS[0] = as_lists
    try:
        with open(os.path.join(d, "state.json"), encoding="utf-8") as f:
            return json.load(f, object_hook=_hook(d))
    finally:
        AS_LISTS[0] = False


def _sort_key(k):
    return (0, k) if isinstance(k, (int, float)) and not isinstance(k, bool) else (1, k)


def _hash_values(h, a, dt, chunk=1 << 20):
    # The values' little-endian bytes in the oracle's kind, without a whole-field copy (CORE_LAYOUT_PLAN option 5): a NumPy array of
    # that kind is hashed through its buffer, anything else (a list, a narrower array) is converted chunk by chunk
    if isinstance(a, np.ndarray) and a.dtype == dt and a.flags.c_contiguous and sys.byteorder == "little":
        h.update(memoryview(a).cast("B"))
        return
    for i in range(0, len(a), chunk):
        h.update(memoryview(np.ascontiguousarray(np.asarray(a[i:i + chunk]), dtype=dt)).cast("B"))


def canon(h, v):
    if isinstance(v, np.integer):
        v = int(v)
    elif isinstance(v, np.floating):
        v = float(v)
    if v is None:
        h.update(b"n")
    elif isinstance(v, bool):
        h.update(b"b1" if v else b"b0")
    elif isinstance(v, int):
        h.update(b"i" + struct.pack("<q", v))
    elif isinstance(v, float):
        h.update(b"f" + struct.pack("<d", v))
    elif isinstance(v, str):
        s = v.encode("utf-8")
        h.update(b"s" + struct.pack("<q", len(s)))
        h.update(s)
    elif isinstance(v, PackedStr):
        h.update(b"S" + struct.pack("<q", len(v)))
        for s2 in v:
            canon(h, s2)
    elif isinstance(v, Packed):
        h.update(CANON_KIND[v.kind] + struct.pack("<q", len(v.a)))
        _hash_values(h, v.a, KINDS[v.kind])
    elif isinstance(v, list):
        h.update(b"a" + struct.pack("<q", len(v)))
        for x in v:
            canon(h, x)
    elif isinstance(v, dict):
        h.update(b"d" + struct.pack("<q", len(v)))
        for k in sorted(v.keys(), key=_sort_key):
            canon(h, k)
            canon(h, v[k])
    else:
        raise TypeError("no canonical form for %r" % type(v))


def month_digest(hs):
    lines = "".join("%s %s\n" % (n, hs[n]) for n in sorted(hs))
    return hashlib.sha256(lines.encode("utf-8")).hexdigest()


def read_hashes(path):
    out = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            n, h = line.split()
            out[n] = h
    return out


def enc(v, d, files):
    # oracle_dump.gd's typed tree: ints and floats exact, dictionaries in insertion order, packed arrays as raw little-endian files
    if isinstance(v, (bool, type(None))):
        return v
    if isinstance(v, np.integer):
        v = int(v)
    elif isinstance(v, np.floating):
        v = float(v)
    if isinstance(v, int):
        return {"i": str(v)}
    if isinstance(v, float):
        return {"f": str(struct.unpack("<q", struct.pack("<d", v))[0])}
    if isinstance(v, str):
        return {"s": v}
    if isinstance(v, PackedStr):
        return {"p": "str", "v": list(v)}
    if isinstance(v, Packed):
        files[0] += 1
        name = "%05d.bin" % files[0]
        with open(os.path.join(d, name), "wb") as f:
            _write_values(f, v.a, KINDS[v.kind])
        return {"p": v.kind, "file": name, "n": len(v.a)}
    if isinstance(v, list):
        return {"a": [enc(x, d, files) for x in v]}
    if isinstance(v, dict):
        return {"d": [[enc(k, d, files), enc(x, d, files)] for k, x in v.items()]}
    raise TypeError("no saved form for %r" % type(v))


def _write_values(f, a, dt, chunk=1 << 20):
    if isinstance(a, np.ndarray) and a.dtype == dt and a.flags.c_contiguous and sys.byteorder == "little":
        f.write(memoryview(a).cast("B"))
        return
    for i in range(0, len(a), chunk):
        f.write(np.ascontiguousarray(np.asarray(a[i:i + chunk]), dtype=dt).tobytes())
