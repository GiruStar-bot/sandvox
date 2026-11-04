# The keyed draws: the twin of sim/earth_core/keyed.gd (splitmix64 finaliser, FNV-1a over the tag's UTF-8 bytes)
# Why not random / numpy.random: a draw must be a pure function of its key, so a value never depends on how many came before
import math
from . import detmath

M64 = (1 << 64) - 1
GOLD = 0x9E3779B97F4A7C15
MIX1 = 0xBF58476D1CE4E5B9
MIX2 = 0x94D049BB133111EB
FNV_OFFSET = 0xCBF29CE484222325
FNV_PRIME = 1099511628211
TWO53 = 9007199254740992.0

_heads = {}


def mix(x):
    x = ((x ^ (x >> 30)) * MIX1) & M64
    x = ((x ^ (x >> 27)) * MIX2) & M64
    return x ^ (x >> 31)


def tag_hash(tag):
    h = FNV_OFFSET
    for byte in tag.encode("utf-8"):
        h = ((h ^ byte) * FNV_PRIME) & M64
    return h


def head(seed_v, tag):
    k = (seed_v, tag)
    h = _heads.get(k)
    if h is None:
        h = mix(mix((seed_v + GOLD) & M64) ^ tag_hash(tag))
        _heads[k] = h
    return h


def h64(hd, a, b, c):
    h = mix((hd + a * GOLD) & M64)
    h = mix((h + b * GOLD) & M64)
    return mix((h + c * GOLD) & M64)


def raw(seed_v, tag, a=0, b=0, c=0):
    return h64(head(seed_v, tag), a, b, c) >> 11


def u(seed_v, tag, a=0, b=0, c=0):
    return float(h64(head(seed_v, tag), a, b, c) >> 11) / TWO53


def below(n, seed_v, tag, a=0, b=0, c=0):
    return int(math.floor(u(seed_v, tag, a, b, c) * float(n))) if n > 0 else 0


def normal(seed_v, tag, a=0, b=0, c=0):
    u1 = u(seed_v, tag + "/1", a, b, c)
    u1 = u1 if u1 > 1e-12 else 1e-12
    u2 = u(seed_v, tag + "/2", a, b, c)
    return math.sqrt(-2.0 * detmath.log(u1)) * detmath.cos(6.283185307179586 * u2)
