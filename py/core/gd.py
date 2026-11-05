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


def roundf(x):
    # GDScript's round() of a float: C's round, half away from zero, returning a float. Why not gd_round: floor(x + 0.5) rounds
    # 0.49999999999999994 up, because x + 0.5 is inexact there, and it returns an int
    if not math.isfinite(x) or x == 0.0:
        return x
    if x < 0.0:
        return -roundf(-x)
    r = math.floor(x)
    return float(r + 1) if x - r >= 0.5 else float(r)


_INF = float("inf")


def default_nan():
    # x86-64 SSE's default NaN (0xFFF8000000000000), which Godot's 0.0 / 0.0 and inf - inf give. Why not float("nan"): its bits are
    # 0x7FF8000000000000, and the digest hashes a float's bits (M042 §2b); the parity platform is x86-64
    return _INF - _INF


def fdiv(a, b):
    # GDScript's float division: ±inf or NaN by zero where Python raises
    if b != 0.0:
        return a / b
    if math.isnan(a):
        return a
    if a == 0.0:
        return default_nan()
    return math.copysign(_INF, a) * math.copysign(1.0, b)


def fsqrt(x):
    # GDScript's sqrt: NaN (x86-64's default) for a negative argument where Python raises; sqrt(-0.0) is -0.0 in both
    if x < 0.0:
        return default_nan()
    return math.sqrt(x)
