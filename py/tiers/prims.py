# The T2.0 primitives: the twin of sim/modern/people/tiers.gd's binomial, hypergeometric, hypergeometric_split, merge_least,
# dep_round, _systematic (+ _largest_fix), split_holds, cap_to and largest_keyed, in the oracle's operation order
import math
from . import detmath, keyed
from .gd import mini, maxi, clampi, maxf, minf

BINOM_SWITCH = 12.0
INF = float("inf")


def binomial(n, p, u):
    if n <= 0 or p <= 0.0:
        return 0
    if p >= 1.0:
        return n
    if p > 0.5:
        return n - binomial(n, 1.0 - p, 1.0 - u)
    q = 1.0 - p
    npq = float(n) * p * q
    if npq < BINOM_SWITCH:
        cap = mini(n, int(float(n) * p + 40.0 * math.sqrt(npq) + 40.0))
        f = detmath.pow(q, float(n))
        acc = f
        k = 0
        while acc < u and k < cap:
            f *= float(n - k) * p / (float(k + 1) * q)
            if f <= 0.0:
                break
            k += 1
            acc += f
        return k
    return clampi(int(math.ceil(float(n) * p + math.sqrt(npq) * detmath.inv_normal(u) - 0.5)), 0, n)


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
    var_x = mean * (1.0 - float(k) / float(n)) * float(n - d) / float(maxi(1, n - 1))
    hi = mini(d, k)
    if var_x < BINOM_SWITCH:
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
    return clampi(int(math.ceil(mean + math.sqrt(var_x) * detmath.inv_normal(u) - 0.5)), 0, hi)


def hypergeometric_split(holds, d, seed_v, tag, key):
    out = [0] * len(holds)
    n_rem = 0
    for h in holds:
        n_rem += h
    d_rem = mini(d, n_rem)
    hd = keyed.head(seed_v, tag)
    for i in range(len(holds)):
        if d_rem <= 0:
            break
        k = holds[i]
        x = d_rem if k >= n_rem else hypergeometric(n_rem, k, d_rem, float(keyed.h64(hd, key, i, 0) >> 11) / keyed.TWO53)
        out[i] = x
        d_rem -= x
        n_rem -= k
    return out


def merge_least(w, x, seed_v, tag, key):
    lo = 0
    hi = 1
    best = INF
    for a in range(len(w)):
        for b in range(a + 1, len(w)):
            c = float(w[a]) * float(w[b]) * (x[a] - x[b]) * (x[a] - x[b])
            if c < best:
                best = c
                lo = a
                hi = b
    keep_lo = keyed.u(seed_v, tag, key, 0, 0) * float(w[lo] + w[hi]) < float(w[lo])
    kept = lo if keep_lo else hi
    drop = hi if keep_lo else lo
    w2 = list(w)
    x2 = list(x)
    w2[kept] = w[kept] + w[drop]
    del w2[drop]
    del x2[drop]
    return [w2, x2]


def systematic(v, total, seed_v, tag, key):
    n = len(v)
    out = [0] * n
    used = 0
    fr = [0.0] * n
    sf = 0.0
    for i in range(n):
        x = maxf(0.0, v[i])
        out[i] = int(math.floor(x))
        fr[i] = x - float(out[i])
        used += out[i]
        sf += fr[i]
    left = total - used
    if left > 0 and sf > 0.0:
        step = sf / float(left)
        at = keyed.u(seed_v, tag, key, 0, 0) * step
        acc = 0.0
        placed = 0
        for i2 in range(n):
            acc += fr[i2]
            while placed < left and at < acc:
                out[i2] += 1
                placed += 1
                at += step
        used += placed
    return _largest_fix(out, v, total, used)


def _largest_fix(out, v, total, used):
    n = len(v)
    while used < total and n > 0:
        best = 0
        for j in range(n):
            if v[j] - float(out[j]) > v[best] - float(out[best]):
                best = j
        out[best] += 1
        used += 1
    while used > total:
        worst = -1
        for j2 in range(n):
            if out[j2] > 0 and (worst < 0 or float(out[j2]) - v[j2] > float(out[worst]) - v[worst]):
                worst = j2
        out[worst] -= 1
        used -= 1
    return out


def split_holds(holds, x, seed_v, tag, a, b):
    tot = 0
    for hd in holds:
        tot += hd
    if tot <= 0 or x <= 0:
        return [0] * len(holds)
    xx = mini(x, tot)
    v = [float(xx) * float(holds[i]) / float(tot) for i in range(len(holds))]
    return cap_to(systematic(v, xx, seed_v, tag, a * 12 + b), holds)


def cap_to(out, holds):
    over = 0
    for i2 in range(len(holds)):
        if out[i2] > holds[i2]:
            over += out[i2] - holds[i2]
            out[i2] = holds[i2]
    for i3 in range(len(holds)):
        if over <= 0:
            break
        room = mini(over, holds[i3] - out[i3])
        out[i3] += room
        over -= room
    return out


def largest_keyed(v, total, seed_v, tag, a, b):
    n = len(v)
    out = [0] * n
    used = 0
    rows = []
    o = keyed.below(maxi(1, n), seed_v, tag, a, b, 0)
    for i in range(n):
        out[i] = int(math.floor(v[i]))
        used += out[i]
        rows.append((-(v[i] - math.floor(v[i])), (i - o + n) % n, i))
    # Why not a port of Godot's sort: the second key (i - o) mod n is distinct per row, so the order is total and any sort agrees
    rows.sort()
    r = 0
    while used < total:
        out[rows[r % n][2]] += 1
        used += 1
        r += 1
    return out


def dep_round(x, nr, nc, seed_v, tag, key, rounded=None):
    nn = nr * nc
    out = [0] * nn
    f = [0.0] * nn
    for i in range(nn):
        fl = math.floor(x[i] + 1e-9)
        out[i] = int(fl)
        r = x[i] - fl
        if r >= 1.0 - 1e-9:
            out[i] += 1
        elif r > 1e-9:
            f[i] = r
    step = 0
    scan = 0
    while True:
        start = -1
        while scan < nn:
            if f[scan] > 0.0:
                start = scan
                break
            scan += 1
        if start < 0:
            break
        n_nodes = 1
        pos = {start // nc: 0}
        cells = []
        cur = start // nc
        prev = -1
        frm = -1
        while True:
            nxt = -1
            if cur < nr:
                for j in range(nc):
                    if f[cur * nc + j] > 0.0 and cur * nc + j != prev:
                        nxt = cur * nc + j
                        break
            else:
                for i2 in range(nr):
                    if f[i2 * nc + cur - nr] > 0.0 and i2 * nc + cur - nr != prev:
                        nxt = i2 * nc + cur - nr
                        break
            if nxt < 0:
                break
            other = (nr + nxt % nc) if cur < nr else (nxt // nc)
            cells.append(nxt)
            if other in pos:
                frm = pos[other]
                break
            pos[other] = n_nodes
            n_nodes += 1
            prev = nxt
            cur = other
        if frm < 0:
            c0 = cells[-1] if cells else start
            out[c0] += 1 if f[c0] >= 0.5 else 0
            f[c0] = 0.0
            if rounded is not None:
                rounded[0] += 1
            continue
        cyc = cells[frm:]
        alpha = 1e300
        beta = 1e300
        for k in range(len(cyc)):
            c = cyc[k]
            if k % 2 == 0:
                alpha = minf(alpha, 1.0 - f[c])
                beta = minf(beta, f[c])
            else:
                alpha = minf(alpha, f[c])
                beta = minf(beta, 1.0 - f[c])
        d = alpha if keyed.u(seed_v, tag, key, step, 0) < beta / (alpha + beta) else -beta
        step += 1
        for k2 in range(len(cyc)):
            c2 = cyc[k2]
            f[c2] += d if k2 % 2 == 0 else -d
            if f[c2] <= 1e-9:
                f[c2] = 0.0
            elif f[c2] >= 1.0 - 1e-9:
                f[c2] = 0.0
                out[c2] += 1
    return out
