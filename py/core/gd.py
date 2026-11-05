# GDScript's semantics where Python's differ (PY_TRIAL_PLAN §2)
import math

M64 = (1 << 64) - 1


def wrap(x):
    x &= M64
    return x - (1 << 64) if x >> 63 else x


def idiv(a, b):
    q = abs(a) // abs(b)
    return q if (a >= 0) == (b >= 0) else -q


def imod(a, b):
    return a - idiv(a, b) * b


def gd_round(x):
    return math.floor(x + 0.5) if x >= 0.0 else -math.floor(-x + 0.5)


def maxf(a, b):
    return a if a > b else b


def minf(a, b):
    return a if a < b else b


def maxi(a, b):
    return a if a > b else b


def mini(a, b):
    return a if a < b else b


def clampi(v, lo, hi):
    return lo if v < lo else (hi if v > hi else v)


def clampf(v, lo, hi):
    return lo if v < lo else (hi if v > hi else v)


def to_int(x):
    return int(x)
