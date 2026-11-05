# Godot's packed arrays as typed lists, the canonical bytes and per-field SHA-256 of oracle_dump.gd's _canon, and its typed tree
# (WORLD_PORT_PLAN §2)
import hashlib
import json
import math
import os
import struct

from core import digest


class F64(list):
    pass


class I32(list):
    pass


class I64(list):
    pass


class U8(list):
    pass


class PStr(list):
    pass


_PK = {F64: (b"D", "<%dd", "f64"), I32: (b"l", "<%di", "i32"), I64: (b"q", "<%dq", "i64"), U8: (b"B", "<%dB", "u8")}
_KIND = {"f64": F64, "i32": I32, "i64": I64, "u8": U8}


def nan():
    return struct.unpack("<d", struct.pack("<Q", 0x7FF8000000000000))[0]


NAN = nan()


def _to_core(v):
    # The world's typed lists as py/core's Packed / PackedStr, so the canonical bytes are core's (no second copy of oracle_dump.gd's _canon)
    t = type(v)
    if t in _PK:
        return digest.Packed(_PK[t][2], v)
    if t is PStr:
        return digest.PackedStr(v)
    if isinstance(v, dict):
        return {k: _to_core(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [_to_core(x) for x in v]
    return v


def _from_core(v):
    if isinstance(v, digest.Packed):
        return _KIND[v.kind](v.a.tolist() if hasattr(v.a, "tolist") else list(v.a))
    if isinstance(v, digest.PackedStr):
        return PStr(v)
    if isinstance(v, dict):
        return {k: _from_core(x) for k, x in v.items()}
    if isinstance(v, list):
        return [_from_core(x) for x in v]
    return v


def canon(h, v):
    digest.canon(h, _to_core(v))


def sha(v):
    h = hashlib.sha256()
    canon(h, v)
    return h.hexdigest()


def field_hashes(tree):
    return {n: sha(tree[n]) for n in sorted(tree)}


day_digest = digest.month_digest
read_hashes = digest.read_hashes


def bits(x):
    return struct.unpack("<q", struct.pack("<d", x))[0]


def unbits(b):
    return struct.unpack("<d", struct.pack("<q", int(b)))[0]


def dec(node, d=""):
    # oracle_dump.gd's typed tree back to the world's values, through core's decoder
    return _from_core(digest._dec(node, d))


def load_state(d):
    return _from_core(digest.load(d))


def round_trip(v):
    # The save of W1-r and W2-r: core's typed tree written to a directory and read back
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        files = [0]
        tree = digest.enc(_to_core(v), td, files)
        with open(os.path.join(td, "state.json"), "w", encoding="utf-8") as f:
            json.dump(tree, f)
        return _from_core(digest.load(td))


def deep(v):
    # Godot's duplicate(true): containers copied, packed arrays keep their kind
    t = type(v)
    if t in _PK or t is PStr:
        return t(v)
    if isinstance(v, list):
        return [deep(x) for x in v]
    if isinstance(v, dict):
        return {k: deep(x) for k, x in v.items()}
    return v


def is_finite(x):
    return not (math.isnan(x) or math.isinf(x))
