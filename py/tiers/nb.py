# Numba twins of keyed.py, detmath.py's exp / log / pow / inv_normal and prims.py's binomial, hypergeometric and
# hypergeometric_split (PY_TRIAL_PLAN §2: fastmath off, no parallel); the same constants and operation order as the pure ones
# Why not numba.cfunc over the pure modules: they read Python ints of any size and dicts, which nopython mode cannot type
import math

import numpy as np
from llvmlite import ir
from numba import njit, types
from numba.extending import intrinsic

from . import detmath as dm

U64 = np.uint64


@intrinsic
def f2i(typingctx, x):
    sig = types.int64(types.float64)

    def codegen(context, builder, signature, args):
        return builder.bitcast(args[0], ir.IntType(64))
    return sig, codegen


@intrinsic
def i2f(typingctx, x):
    sig = types.float64(types.int64)

    def codegen(context, builder, signature, args):
        return builder.bitcast(args[0], ir.DoubleType())
    return sig, codegen


GOLD = U64(0x9E3779B97F4A7C15)
MIX1 = U64(0xBF58476D1CE4E5B9)
MIX2 = U64(0x94D049BB133111EB)
TWO53 = 9007199254740992.0


@njit(cache=True)
def mix(x):
    x = (x ^ (x >> U64(30))) * MIX1
    x = (x ^ (x >> U64(27))) * MIX2
    return x ^ (x >> U64(31))


@njit(cache=True)
def u_from(hd, a, b, c):
    h = mix(hd + U64(a) * GOLD)
    h = mix(h + U64(b) * GOLD)
    h = mix(h + U64(c) * GOLD)
    return float(h >> U64(11)) / TWO53


@njit(cache=True)
def below_from(n, hd, a, b, c):
    return int(math.floor(u_from(hd, a, b, c) * float(n))) if n > 0 else 0


INVLN2 = dm.INVLN2
LN2HI = dm.LN2HI
LN2LO = dm.LN2LO
EXP_HI = dm.EXP_HI
EXP_LO = dm.EXP_LO
P1 = dm.P1
P2 = dm.P2
P3 = dm.P3
P4 = dm.P4
P5 = dm.P5
TWO54 = dm.TWO54
MIN_NORMAL = dm.MIN_NORMAL
THIRD = dm.THIRD
LG1, LG2, LG3, LG4, LG5, LG6, LG7 = dm.LG[1:8]
INF = math.inf
PA = np.array(dm.PPND_A)
PB = np.array(dm.PPND_B)
PC = np.array(dm.PPND_C)
PD = np.array(dm.PPND_D)
PE = np.array(dm.PPND_E)
PF = np.array(dm.PPND_F)
PQ = dm.PPND_Q
PR = dm.PPND_R
PS = dm.PPND_S
PLO = dm.PPND_LO
PHI = dm.PPND_HI


@njit(cache=True)
def p2(k):
    if k < -1022:
        return i2f(np.int64(1) << np.int64(k + 1074))
    return i2f(np.int64(k + 1023) << np.int64(52))


@njit(cache=True)
def exp(x):
    if x != x:
        return x
    if x > EXP_HI:
        return INF
    if x < EXP_LO:
        return 0.0
    dk = math.floor(x * INVLN2 + 0.5) * 1.0
    hi = x - dk * LN2HI
    lo = dk * LN2LO
    r = hi - lo
    t = r * r
    c = r - t * (P1 + t * (P2 + t * (P3 + t * (P4 + t * P5))))
    if dk == 0.0:
        return 1.0 - ((r * c) / (c - 2.0) - r)
    y = 1.0 - ((lo - (r * c) / (2.0 - c)) - hi)
    k = int(dk)
    if k > 1023:
        return (y * 2.0) * p2(1023)
    if k < -1022:
        return (y * p2(k + 1000)) * p2(-1000)
    return y * p2(k)


@njit(cache=True)
def log(x):
    if not x > 0.0:
        return -INF if x == 0.0 else math.nan
    if x == INF:
        return x
    k = 0
    if x < MIN_NORMAL:
        x *= TWO54
        k = -54
    hx = f2i(x) >> np.int64(32)
    ex = (hx >> np.int64(20)) - 1023
    hx &= 0xfffff
    i = (hx + 0x95f64) & 0x100000
    ex += i >> 20
    k += ex
    f = x * p2(-ex) - 1.0
    if ((hx + 2) & 0xfffff) < 3:
        if f == 0.0:
            if k == 0:
                return 0.0
            dk0 = float(k)
            return dk0 * LN2HI + dk0 * LN2LO
        r0 = f * f * (0.5 - THIRD * f)
        if k == 0:
            return f - r0
        dk1 = float(k)
        return dk1 * LN2HI - ((r0 - dk1 * LN2LO) - f)
    s = f / (2.0 + f)
    dk = float(k)
    z = s * s
    w = z * z
    t1 = w * (LG2 + w * (LG4 + w * LG6))
    t2 = z * (LG1 + w * (LG3 + w * (LG5 + w * LG7)))
    r = t2 + t1
    if ((hx - 0x6147a) | (0x6b851 - hx)) > 0:
        hfsq = 0.5 * f * f
        if k == 0:
            return f - (hfsq - s * (hfsq + r))
        return dk * LN2HI - ((hfsq - (s * (hfsq + r) + dk * LN2LO)) - f)
    if k == 0:
        return f - s * (f - r)
    return dk * LN2HI - ((s * (f - r) - dk * LN2LO) - f)


@njit(cache=True)
def pow_(x, y):
    if y == 0.0 or x == 1.0:
        return 1.0
    if y == 1.0:
        return x
    if y == 2.0:
        return x * x
    if y == 0.5 and x > 0.0 and x < INF:
        return math.sqrt(x)
    if x != x or y != y:
        return math.nan
    if math.floor(y) == y and abs(y) <= 64.0:
        n = int(abs(y))
        acc = 1.0
        b = x
        while True:
            if n & 1:
                acc *= b
            n >>= 1
            if n == 0:
                break
            b *= b
        return 1.0 / acc if y < 0.0 else acc
    neg = False
    ax = x
    if x < 0.0:
        if math.floor(y) != y:
            return math.nan
        ax = -x
        neg = abs(y) < TWO54 and math.floor(y * 0.5) != y * 0.5
    if ax == 0.0:
        r = 0.0 if y > 0.0 else INF
    elif ax == INF:
        r = INF if y > 0.0 else 0.0
    else:
        r = exp(y * log(ax))
    return -r if neg else r


@njit(cache=True)
def poly8(c, x):
    r = c[7]
    for k in range(6, -1, -1):
        r = r * x + c[k]
    return r


@njit(cache=True)
def inv_normal(p):
    pc = PLO if p <= 0.0 else (PHI if p >= 1.0 else p)
    q = pc - 0.5
    if abs(q) <= PQ:
        r = PR - q * q
        return q * poly8(PA, r) / poly8(PB, r)
    t = pc if q < 0.0 else 1.0 - pc
    t = math.sqrt(-log(t))
    if t <= 5.0:
        t -= PS
        v = poly8(PC, t) / poly8(PD, t)
    else:
        t -= 5.0
        v = poly8(PE, t) / poly8(PF, t)
    return -v if q < 0.0 else v


@njit(cache=True)
def binomial(n, p, u):
    if n <= 0 or p <= 0.0:
        return 0
    if p >= 1.0:
        return n
    if p > 0.5:
        return n - binomial(n, 1.0 - p, 1.0 - u)
    q = 1.0 - p
    npq = float(n) * p * q
    if npq < 12.0:
        cap0 = int(float(n) * p + 40.0 * math.sqrt(npq) + 40.0)
        cap = n if n < cap0 else cap0
        f = pow_(q, float(n))
        acc = f
        k = 0
        while acc < u and k < cap:
            f *= float(n - k) * p / (float(k + 1) * q)
            if f <= 0.0:
                break
            k += 1
            acc += f
        return k
    v = int(math.ceil(float(n) * p + math.sqrt(npq) * inv_normal(u) - 0.5))
    return 0 if v < 0 else (n if v > n else v)


@njit(cache=True)
def hypergeometric(n, k, d, u):
    if d <= 0 or k <= 0:
        return 0
    if k >= n:
        return d
    if 2 * k > n:
        return d - hypergeometric(n, n - k, d, 1.0 - u)
    if 2 * d > n:
        return k - hypergeometric(n, k, n - d, 1.0 - u)
    mean = float(d) * float(k) / float(n)
    var_x = mean * (1.0 - float(k) / float(n)) * float(n - d) / float(n - 1 if n - 1 > 1 else 1)
    hi = d if d < k else k
    if var_x < 12.0:
        f = 1.0
        for i in range(d):
            f *= float(n - k - i) / float(n - i)
        acc = f
        x = 0
        while acc < u and x < hi:
            f *= float(k - x) * float(d - x) / (float(x + 1) * float(n - k - d + x + 1))
            if f <= 0.0:
                break
            x += 1
            acc += f
        return x
    v = int(math.ceil(mean + math.sqrt(var_x) * inv_normal(u) - 0.5))
    return 0 if v < 0 else (hi if v > hi else v)


@njit(cache=True)
def hypergeometric_split(holds, d, hd, key, out):
    n_rem = 0
    for i in range(len(holds)):
        out[i] = 0
        n_rem += holds[i]
    d_rem = d if d < n_rem else n_rem
    for i in range(len(holds)):
        if d_rem <= 0:
            break
        k = holds[i]
        x = d_rem if k >= n_rem else hypergeometric(n_rem, k, d_rem, u_from(hd, key, i, 0))
        out[i] = x
        d_rem -= x
        n_rem -= k
