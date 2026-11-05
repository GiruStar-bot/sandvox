# The month's hot loops as Numba kernels over NumPy arrays (PY_TRIAL_PLAN §2, §6.3): month.py's grade_table, the cell loops of
# _t22_age and _t22_deaths, and _t22_grades' cell loop, each in the oracle's loop order with its float tallies accumulated in that order.
# Why the splits and the marital part stay outside the kernels: they append to lists and read dictionaries; the cell loops read
# nothing they write (a split's new point has no unaged mass; a death's marital part reads no cell array), so running them after
# the kernel in the same order gives the same state (checked by P2)
import numpy as np
from numba import njit

from core.nb import binomial, hypergeometric, hypergeometric_split, u_from, below_from

AGE_SLOTS = 16
NG = 5
NK = 2
NS = NG * NK
BANDS = 18
AGES = 101


@njit(cache=True)
def slots_in(b):
    return AGE_SLOTS if b == BANDS - 1 else 5


@njit(cache=True)
def b10(a):
    x = a // 10
    return x if x < 8 else 8


# Why every read of a cell array is cast to int64: the cells are stored as int32 (CORE_LAYOUT_PLAN §2) and the samplers recurse on
# their arguments' types, so one int64 signature keeps them one compiled function and every product in int64

@njit(cache=True)
def grade_table(T, ag, ub, us, loff, lidx):
    base = 2 * 9 * 4 * NG
    out = np.zeros(base + AGES * 2 * NG, dtype=np.int64)
    for u in range(len(ub)):
        b = ub[u]
        s = us[u]
        row = (s * 9 + b10(b * 5)) * 4 * NG
        for j in range(loff[u], loff[u + 1]):
            g = lidx[j]
            for x in range(4 * NG):
                out[row + x] += T[g * 4 * NG + x]
            for sl in range(slots_in(b)):
                for sb in range(NS):
                    out[base + ((b * 5 + sl) * 2 + s) * NG + sb // NK] += ag[(g * AGE_SLOTS + sl) * NS + sb]
    return out


@njit(cache=True)
def birth_months(bm_best, bm_sh, hd_bm, j, age, m, out):
    sh = bm_sh[bm_best[age]]
    left = m
    fr = np.empty(12)
    o = below_from(12, hd_bm, j, age, 0)
    for k in range(12):
        x = float(m) * sh[k]
        out[k] = int(np.floor(x))
        left -= out[k]
        fr[k] = -(x - float(out[k]))
    order = np.empty(12, dtype=np.int64)
    used = np.zeros(12, dtype=np.bool_)
    for r in range(12):
        best = -1
        for k in range(12):
            if used[k]:
                continue
            if best < 0 or fr[k] < fr[best] or (fr[k] == fr[best] and (k - o + 12) % 12 < (best - o + 12) % 12):
                best = k
        used[best] = True
        order[r] = best
    for r in range(left):
        out[order[r % 12]] += 1


@njit(cache=True)
def age_collect(month, ub, us, U0, loff, lidx, ids, pq, og, jg, rem_keys, rem_vals, bm_best, bm_sh, hd_bm, hd_age, nn,
                mv_u, mv_g, mv_sl, mv_sb, mv_x, cnt):
    # _t22_age's first loop (M035): each cell's mass born this month, in the oracle's (unit, point, slot, cell) order, pooled into
    # nn by its new age x sex x quartile x (class, state). cnt: [due, clamped, arrivals recorded]
    mc = month % 12
    W = NK * NG
    S = np.zeros(12, dtype=np.int64)
    for u in range(U0):
        b = ub[u]
        s = us[u]
        for j in range(loff[u], loff[u + 1]):
            g = lidx[j]
            id_ = ids[g]
            k = pq[g]
            for sl in range(slots_in(b)):
                a = b * 5 + sl
                a2 = a + 1 if a + 1 < AGES - 1 else AGES - 1
                for sb in range(NS):
                    cx = (g * AGE_SLOTS + sl) * NS + sb
                    o = np.int64(og[cx])
                    if o <= 0:
                        continue
                    gk = id_ * NS + sb
                    rk = (id_ * AGE_SLOTS + sl) * NS + sb
                    ri = np.searchsorted(rem_keys, rk)
                    has_r = ri < len(rem_keys) and rem_keys[ri] == rk
                    if has_r:
                        for kk in range(12):
                            S[kk] = rem_vals[ri, kk]
                    else:
                        birth_months(bm_best, bm_sh, hd_bm, gk, a, np.int64(jg[cx]), S)
                    nr = 0
                    for k2 in range(mc, 12):
                        nr += S[k2]
                    cnt[0] += S[mc]
                    x = o
                    if mc < 11:
                        if nr < o:
                            nr = o
                            cnt[1] += 1
                        x = hypergeometric(nr, S[mc] if S[mc] < nr else nr, o, u_from(hd_age, gk, a, month))
                    if has_r:
                        rem_vals[ri, mc] = 0
                    if x <= 0:
                        continue
                    n = cnt[2]
                    mv_u[n] = u
                    mv_g[n] = g
                    mv_sl[n] = sl
                    mv_sb[n] = sb
                    mv_x[n] = x
                    cnt[2] = n + 1
                    nn[((a2 * 2 + s) * 4 + k) * W + (sb % NK) * NG + sb // NK] += float(x)


@njit(cache=True)
def age_apply(month, nmv, mv_u, mv_g, mv_sl, mv_sb, mv_x, ub, us, ids, pq, og, ag, old, age, acn, T, pm, hd_grade, hd_ms, led,
              gvar, gafter, gstay, gstay_c, gn_c, b4_var, b4_after, b4_n, b4_exit, up_g, up_u, up_a, up_x, up_of, cnt):
    # _t22_age's second loop (M035): each arrival re-graded within its class to pi(a) by sequential binomials, its marital states from
    # its state's column, joined at its new age; the band-top arrivals summed per point into up_x in first-arrival order (the oracle's
    # ups dictionary). cnt: [moved persons, the re-grade's moved, points to split]
    W = NK * NG
    lb = 2 * 9 * 4 * NG
    xs = np.zeros(NG, dtype=np.int64)
    col = np.zeros(4, dtype=np.int64)
    md = np.zeros(4, dtype=np.int64)
    for e in range(nmv):
        u2 = mv_u[e]
        g2 = mv_g[e]
        sl2 = mv_sl[e]
        sb2 = mv_sb[e]
        m = mv_x[e]
        b2 = ub[u2]
        s3 = us[u2]
        top = AGE_SLOTS - 1 if b2 == BANDS - 1 else 4
        a4 = b2 * 5 + sl2
        a5 = a4 + 1 if a4 + 1 < AGES - 1 else AGES - 1
        id2 = ids[g2]
        gr2 = sb2 // NK
        cl = sb2 % NK
        cell2 = (a5 * 2 + s3) * 4 + pq[g2]
        rw = cl * NG + gr2
        cx2 = (g2 * AGE_SLOTS + sl2) * NS + sb2
        b10s = b10(b2 * 5)
        row2 = (s3 * 9 + b10(a5)) * NG
        rmass = m
        rp = 1.0
        for g3 in range(NG):
            pg = pm[cell2 * W * NG + rw * NG + g3]
            gvar[row2 + g3] += float(m) * pg * (1.0 - pg)
            x2 = rmass
            if g3 < NG - 1:
                if rp > 0.0 and rmass > 0:
                    pr = pg / rp
                    pr = 0.0 if pr < 0.0 else (1.0 if pr > 1.0 else pr)
                    x2 = binomial(rmass, pr, u_from(hd_grade, id2 * NS + sb2, a5, month * NG + g3))
                else:
                    x2 = 0
            rp -= pg
            rmass -= x2
            xs[g3] = x2
            gafter[row2 + g3] += float(x2)
        gstay[row2 + gr2] += float(xs[gr2])
        gstay_c[cl * 18 * NG + row2 + gr2] += float(xs[gr2])
        gn_c[cl * 18 * NG + row2 + gr2] += float(m)
        if a5 >= 65:
            r5 = s3 * 7 + ((a5 - 65) // 5 if (a5 - 65) // 5 < 6 else 6)
            q4 = pm[cell2 * W * NG + rw * NG + 4]
            b4_var[r5] += float(m) * q4 * (1.0 - q4)
            b4_after[r5] += float(xs[4])
            if gr2 == 4:
                b4_n[r5] += float(m)
                b4_exit[r5] += float(xs[3])
        cnt[0] += m
        og[cx2] -= m
        ag[cx2] -= m
        old[g2 * AGE_SLOTS + sl2] -= m
        age[g2 * AGE_SLOTS + sl2] -= m
        acn[u2 * AGE_SLOTS + sl2] -= m
        for g4 in range(NG):
            x3 = xs[g4]
            if x3 <= 0:
                continue
            led[lb + (a4 * 2 + s3) * NG + gr2] -= x3
            led[lb + (a5 * 2 + s3) * NG + g4] += x3
            if g4 != gr2:
                cnt[1] += x3
                for k3 in range(4):
                    col[k3] = np.int64(T[g2 * 4 * NG + k3 * NG + gr2])
                hypergeometric_split(col, x3, hd_ms, (((id2 * NS + sb2) * NG + g4) * 128 + a5) * 256 + month % 256, md)
                for k4 in range(4):
                    T[g2 * 4 * NG + k4 * NG + gr2] -= md[k4]
                    T[g2 * 4 * NG + k4 * NG + g4] += md[k4]
                    led[(s3 * 9 + b10s) * 4 * NG + k4 * NG + gr2] -= md[k4]
                    led[(s3 * 9 + b10s) * 4 * NG + k4 * NG + g4] += md[k4]
            dsb = g4 * NK + cl
            if a4 >= AGES - 1:
                ag[(g2 * AGE_SLOTS + sl2) * NS + dsb] += x3
                age[g2 * AGE_SLOTS + sl2] += x3
                acn[u2 * AGE_SLOTS + sl2] += x3
            elif sl2 < top:
                ag[(g2 * AGE_SLOTS + sl2 + 1) * NS + dsb] += x3
                age[g2 * AGE_SLOTS + sl2 + 1] += x3
                acn[u2 * AGE_SLOTS + sl2 + 1] += x3
            else:
                slot = up_of[g2]
                if slot < 0:
                    slot = cnt[2]
                    up_of[g2] = slot
                    up_g[slot] = g2
                    up_u[slot] = u2
                    up_a[slot] = a5
                    cnt[2] = slot + 1
                up_x[slot, dsb] += x3


@njit(cache=True)
def death_cells(month, ub, us, U, loff, lidx, mass, ids, pq, ag, og, old, age, acn, qtab, mu_inf, hd_d, hd_o, led,
                x_as, e_as, v_as, x_g, x_k, d_as, d_old, d_g, d_k, dead_out, dead_g_out):
    for u in range(U):
        b = ub[u]
        s = us[u]
        for j in range(loff[u], loff[u + 1]):
            g = lidx[j]
            dead_out[j] = 0
            for z in range(NG):
                dead_g_out[j, z] = 0
            if mass[g] <= 0:
                continue
            id_ = np.int64(ids[g])
            k = pq[g]
            for sl in range(slots_in(b)):
                a = b * 5 + sl
                ix = a * 2 + s
                for sb in range(NS):
                    gr = sb // NK
                    cx = (g * AGE_SLOTS + sl) * NS + sb
                    m = np.int64(ag[cx])
                    if m <= 0:
                        continue
                    gk = id_ * NS + sb
                    qm = 1.0 if mu_inf[ix] else qtab[(ix * NG + gr) * 4 + k]
                    x_as[ix] += float(m) / 12.0
                    e_as[ix] += float(m) * qm
                    v_as[ix] += float(m) * qm * (1.0 - qm)
                    x_g[ix * NG + gr] += float(m) / 12.0
                    x_k[ix * 4 + k] += float(m) / 12.0
                    d = binomial(m, qm, u_from(hd_d, gk, a, month))
                    if d <= 0:
                        continue
                    o = np.int64(og[cx])
                    od = hypergeometric(m, o, d, u_from(hd_o, gk, a, month))
                    led[2 * 9 * 4 * NG + ix * NG + gr] -= d
                    og[cx] -= od
                    ag[cx] -= d
                    old[g * AGE_SLOTS + sl] -= od
                    age[g * AGE_SLOTS + sl] -= d
                    acn[u * AGE_SLOTS + sl] -= d
                    d_as[ix] += d
                    d_old[ix] += od
                    d_g[ix * NG + gr] += d
                    d_k[ix * 4 + k] += d
                    dead_g_out[j, gr] += d
                    dead_out[j] += d


@njit(cache=True)
def _uf(parent, x):
    r = x
    while parent[r] != r:
        r = parent[r]
    y = x
    while parent[y] != r:
        nx = parent[y]
        parent[y] = r
        y = nx
    return r


@njit(cache=True)
def c5_blocks(month, boff, bcells, bdesc, basc, bcap, bhb, cw, ch, cn, idw, idh, key1, key2, hd5, c5_r, c5_v, cnt):
    # cnt: [cp_blocks_capped, c5_over, c5_x, c5_moves]. Each block's nodes are local: wife w -> 2 i, husband h -> 2 i + 1 over the
    # block's distinct points, as tiers.gd's w * 2 and h * 2 + 1
    # Why a fixed incidence order and not the dictionary order of _c5_path: the live edges form a forest (an edge joins only
    # unjoined ends, or re-joins ends whose path lost an edge), so the path between two nodes is unique whatever the search order
    for bi in range(len(bcap)):
        c0 = boff[bi]
        nc = boff[bi + 1] - c0
        cap = bcap[bi]
        if nc <= cap:
            continue
        cnt[0] += 1
        cells = bcells[c0:c0 + nc]
        wn = np.empty(nc, dtype=np.int64)
        hn = np.empty(nc, dtype=np.int64)
        nodes = np.empty(2 * nc, dtype=np.int64)
        for i in range(nc):
            nodes[2 * i] = cw[cells[i]] * 2
            nodes[2 * i + 1] = ch[cells[i]] * 2 + 1
        un = np.unique(nodes)
        nn = len(un)
        for i in range(nc):
            wn[i] = np.searchsorted(un, cw[cells[i]] * 2)
            hn[i] = np.searchsorted(un, ch[cells[i]] * 2 + 1)
        before = np.zeros(nn, dtype=np.int64)
        tot_b = 0
        for i in range(nc):
            before[wn[i]] += cn[cells[i]]
            before[hn[i]] += cn[cells[i]]
            tot_b += cn[cells[i]]
        deg = np.zeros(nn + 1, dtype=np.int64)
        for i in range(nc):
            deg[wn[i] + 1] += 1
            deg[hn[i] + 1] += 1
        for x in range(nn):
            deg[x + 1] += deg[x]
        inc = np.empty(2 * nc, dtype=np.int64)
        fill = deg[:nn].copy()
        for i in range(nc):
            inc[fill[wn[i]]] = i
            fill[wn[i]] += 1
            inc[fill[hn[i]]] = i
            fill[hn[i]] += 1
        order = bdesc[c0:c0 + nc]
        parent = np.arange(nn)
        active = np.zeros(nc, dtype=np.bool_)
        off = np.empty(nc, dtype=np.int64)
        noff = 0
        for r in range(nc):
            i = order[r]
            ra = _uf(parent, wn[i])
            rb = _uf(parent, hn[i])
            if ra != rb:
                parent[ra] = rb
                active[i] = True
            else:
                off[noff] = i
                noff += 1
        isoff = np.zeros(nc, dtype=np.bool_)
        for r in range(noff):
            isoff[off[r]] = True
        oo = np.empty(noff, dtype=np.int64)
        r2 = 0
        for r in range(nc):
            if isoff[basc[c0 + r]]:
                oo[r2] = basc[c0 + r]
                r2 += 1
        live = nc
        prev_node = np.empty(nn, dtype=np.int64)
        prev_edge = np.empty(nn, dtype=np.int64)
        queue = np.empty(nn, dtype=np.int64)
        path = np.empty(nc, dtype=np.int64)
        fkeys = np.empty(4 * nc + 4, dtype=np.int64)
        fsum = np.empty(4 * nc + 4, dtype=np.int64)
        for r in range(noff):
            if live <= cap:
                break
            i3 = oo[r]
            c3 = cells[i3]
            if cn[c3] <= 0:
                continue
            start = hn[i3]
            goal = wn[i3]
            for x in range(nn):
                prev_node[x] = -2
            prev_node[start] = -1
            qh = 0
            qt = 0
            queue[qt] = start
            qt += 1
            while qh < qt and prev_node[goal] == -2:
                x = queue[qh]
                qh += 1
                for t in range(deg[x], deg[x + 1]):
                    e = inc[t]
                    if not active[e]:
                        continue
                    y = hn[e] if wn[e] == x else wn[e]
                    if prev_node[y] == -2:
                        prev_node[y] = x
                        prev_edge[y] = e
                        queue[qt] = y
                        qt += 1
            if prev_node[goal] == -2:
                active[i3] = True
                continue
            npath = 0
            at = goal
            while at != start:
                path[npath] = prev_edge[at]
                npath += 1
                at = prev_node[at]
            # the path from start to goal is the reverse of the walk back from goal
            ncyc = npath + 1
            d1 = np.int64(1) << np.int64(60)
            d2 = np.int64(1) << np.int64(60)
            for k in range(ncyc):
                e = i3 if k == 0 else path[npath - k]
                v = cn[cells[e]]
                if k % 2 == 1:
                    d1 = v if v < d1 else d1
                else:
                    d2 = v if v < d2 else d2
            u = u_from(hd5, month, bhb[bi], idw[c3] * 100000000 + idh[c3])
            dv = d1 if u * float(d1 + d2) < float(d2) else -d2
            nf = 0
            for k in range(ncyc):
                e = i3 if k == 0 else path[npath - k]
                sg = 1 if k % 2 == 0 else -1
                c5 = cells[e]
                cn[c5] += sg * dv
                for kk in range(2):
                    f = key1[c5] if kk == 0 else key2[c5]
                    if f < 0:
                        continue
                    hit = -1
                    for z in range(nf):
                        if fkeys[z] == f:
                            hit = z
                            break
                    if hit < 0:
                        fkeys[nf] = f
                        fsum[nf] = sg
                        nf += 1
                    else:
                        fsum[hit] += sg
            for z in range(nf):
                c5_r[fkeys[z]] += float(fsum[z] * dv)
                c5_v[fkeys[z]] += float(d1) * float(d2) * float(fsum[z] * fsum[z])
            cnt[3] += 1
            lost_edge = False
            for k in range(1, ncyc):
                e = path[npath - k]
                if cn[cells[e]] <= 0:
                    active[e] = False
                    lost_edge = True
                    live -= 1
            if cn[c3] <= 0:
                live -= 1
            elif lost_edge:
                active[i3] = True
        kept = 0
        after = np.zeros(nn, dtype=np.int64)
        tot_a = 0
        for i in range(nc):
            v = cn[cells[i]]
            if v > 0:
                kept += 1
                after[wn[i]] += v
                after[hn[i]] += v
                tot_a += v
        if kept > cap:
            cnt[1] += 1
        same = tot_a == tot_b
        for x in range(nn):
            bpos = before[x] > 0
            apos = after[x] > 0
            if bpos != apos or (bpos and before[x] != after[x]):
                same = False
                break
        if not same:
            cnt[2] += 1


@njit(cache=True)
def cap_best(alive, q, mass, num, nsc, cat, csc, comp, cross_ok):
    # _t22_cap's pair of least w_i w_k d, in its loop order, the first pair kept on a tie (its strict <), d summed in its order
    n = len(alive)
    best = np.inf
    bi = -1
    bj = -1
    for i3 in range(n):
        if alive[i3] < 0:
            continue
        for j3 in range(i3 + 1, n):
            if alive[j3] < 0:
                continue
            if not cross_ok and q[i3] != q[j3]:
                continue
            d = 0.0
            for qq in range(num.shape[0]):
                dz = num[qq, i3] - num[qq, j3]
                d += dz * dz * nsc[qq]
            for q2 in range(cat.shape[0]):
                if cat[q2, i3] != cat[q2, j3]:
                    d += csc[q2]
            for q3 in range(comp.shape[1]):
                d += (comp[i3, q3] - comp[j3, q3]) * (comp[i3, q3] - comp[j3, q3])
            cost = mass[i3] * mass[j3] * d
            if cost < best:
                best = cost
                bi = i3
                bj = j3
    return bi, bj
