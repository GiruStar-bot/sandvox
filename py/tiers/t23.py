# T2.3, round 1 (docs/team/modern/py/T23_PLAN.md §1 (a), (b) and §8 AMENDED by M044): the household side of T2.2's deaths and ageing.
# Called from month.step behind p.t23: after_age after _t22_age, after_deaths after _t22_deaths. The tallies go to tr_margins["t23"].
from core import keyed, prims
from core.gd import gd_round, idiv, maxi, mini

R_HEAD, R_PARTNER, R_CHILD, R_PARENT, R_OTHER = 0, 1, 2, 3, 4
T_SINGLE, T_COUPLE, T_COUPLE_CHILDREN, T_SINGLE_PARENT, T_OTHER, T_INSTITUTION = 0, 1, 2, 3, 4, 5
SIZE_MIN = [0, 1, 2, 1, 1, 0]
SIZE_MAX = [0, 1, 4, 4, 4, 0]
COUPLE_T = (T_COUPLE, T_COUPLE_CHILDREN)
PARTNER_T = (T_COUPLE, T_COUPLE_CHILDREN, T_OTHER)
REST_ROLES = (R_CHILD, R_PARENT, R_OTHER)
KEY_STRIDE = 6
NTN = 36
SLOT_STRIDE = 1024

# Why module flags and not fields of p: the must-fails' switches (MF-b, MF-b2, MF-dh, MF-cph1, MF-cph2) must never reach the state
SKIP_DEATH_HH = False
WIDOW_KEEP = False
FIRST_ENTRY = False
PARTNER_BY_T = False
CP_STAY = False


class Ctx:
    def __init__(self, p, w):
        self.p = p
        self.w = w
        self.kidx = {}
        self.f = []
        self.hl = []
        self.ent = {}
        self.emap = {}
        for h in range(len(p.tr_hh_keys)):
            self._key_in(p.tr_hh_keys[h], h)
        for e in range(len(p.tr_hm_n)):
            h2 = w["hm_h"][e]
            self.hl[h2].append(e)
            self._ent_in(h2, p.tr_hm_pt[e], e)
            rk = (h2, p.tr_hm_pt[e], p.tr_hm_role[e])
            if rk not in self.emap:
                self.emap[rk] = e
        self.cps = {}
        for c in range(len(p.tr_cp_n)):
            self._cp_in(c)
        self.cpmap = {}
        self.di = {}
        self.tl = {"aged_hh": 0, "aged_partner_cp": 0, "aged_partner_t": 0, "cp_moved": 0, "deaths": 0, "alloc_cp": 0, "alloc_gen": 0,
                   "alloc_nh": 0, "alloc_bad": 0, "alloc_over_covered": 0, "unbooked": 0, "neg_entries": 0, "neg_first": "",
                   "hh_left": 0, "hh_moved": 0, "hh_merged": 0, "surv_missing": 0, "partner_short": 0, "head_short": 0, "rest_short": 0,
                   "new_keys": 0, "widowed_head": 0, "partner_full": 0, "head_full": 0, "partner_none": 0, "head_kept": 0, "aged_kept": 0, "widow_in_place": 0, "hh_kept_gap": 0, "aged_hh10": 0,
                   "dx_cut_short": 0, "dx_surv_missing": 0, "dx_covered_moved": 0, "dx_overflow": 0}
        self.unc_age = {}
        self.unc_death = {}
        self.unc_cur = self.unc_age
        self.cut_gap = {}

    def _key_in(self, k, h):
        fs = k.split("|")
        self.kidx[k] = h
        self.f.append([int(fs[0]), int(fs[1]), int(fs[2]), int(fs[3]), int(fs[4])])
        self.hl.append([])

    def _ent_in(self, h, g, e):
        k = (h, g)
        if k not in self.ent:
            self.ent[k] = []
        self.ent[k].append(e)

    def _cp_in(self, c):
        p = self.p
        for g in (p.tr_cp_w[c], p.tr_cp_h[c]):
            k = (p.tr_cp_hh[c], g)
            if k not in self.cps:
                self.cps[k] = []
            self.cps[k].append(c)

    def key(self, c, t, hb, z, k):
        ks = "%02d|%d|%02d|%d|%d" % (c, t, hb, z, k)
        if ks in self.kidx:
            return self.kidx[ks]
        p = self.p
        h = len(p.tr_hh_keys)
        p.tr_hh_keys.append(ks)
        p.tr_hh[ks] = {"count": 0, "members": {}}
        self.w["htype"].append(t)
        self._key_in(ks, h)
        self.tl["new_keys"] += 1
        return h

    def unc(self, h, g, d):
        if self.f[h][1] in COUPLE_T:
            k = (h, g)
            self.unc_cur[k] = self.unc_cur.get(k, 0) + d

    def gap_pair(self, h, g, d):
        k = (h, g)
        self.cut_gap[k] = self.cut_gap.get(k, 0) + d

    def unc_out(self, d):
        p = self.p
        return {"%s|%d" % (p.tr_hh_keys[k[0]], p.tr_pt_id[k[1]]): v for k, v in sorted(d.items()) if v != 0}

    def count(self, h):
        return int(self.p.tr_hh[self.p.tr_hh_keys[h]]["count"])

    def cross(self, h):
        return int(self.p.tr_hh[self.p.tr_hh_keys[h]].get("cross", 0))

    def add_count(self, h, x):
        d = self.p.tr_hh[self.p.tr_hh_keys[h]]
        d["count"] = int(d["count"]) + x

    def add_cross(self, h, x):
        d = self.p.tr_hh[self.p.tr_hh_keys[h]]
        d["cross"] = int(d.get("cross", 0)) + x

    def add(self, h, g, r, x):
        p = self.p
        rk = (h, g, r)
        e = self.emap.get(rk, -1)
        if e < 0:
            e = len(p.tr_hm_n)
            p.tr_hm_pt.append(g)
            p.tr_hm_role.append(r)
            p.tr_hm_n.append(0)
            self.w["hm_h"].append(h)
            self.w["hm_of"][g].append(e)
            self.hl[h].append(e)
            self._ent_in(h, g, e)
            self.emap[rk] = e
        p.tr_hm_n[e] += x

    def mass(self, h, g, roles):
        p = self.p
        m = 0
        for e in self.ent.get((h, g), ()):
            if p.tr_hm_role[e] in roles and p.tr_hm_n[e] > 0:
                m += p.tr_hm_n[e]
        return m

    def take(self, h, g, r):
        p = self.p
        for e in self.ent.get((h, g), ()):
            if p.tr_hm_role[e] == r and p.tr_hm_n[e] > 0:
                p.tr_hm_n[e] -= 1
                return e
        return -1

    def cpm(self, h, g, side):
        p = self.p
        m = 0
        for c in self.cps.get((h, g), ()):
            if p.tr_cp_hh[c] == h and (p.tr_cp_h[c] if side == R_HEAD else p.tr_cp_w[c]) == g:
                m += p.tr_cp_n[c]
        return m

    def free(self, h, g, r):
        # Why not the entries' whole mass in a couple type: the persons the couple table holds there leave only with their couple
        # (§8), so a draw under T may take only the head and partner mass the table does not cover
        return maxi(0, self.mass(h, g, (r,)) - self.cpm(h, g, r))

    def pool(self, h, roles, freed):
        p = self.p
        out = []
        seen = {}
        for e in self.hl[h]:
            r = p.tr_hm_role[e]
            n = p.tr_hm_n[e]
            if r not in roles or n <= 0:
                continue
            if freed:
                g = p.tr_hm_pt[e]
                sk = (g, r)
                if sk not in seen:
                    seen[sk] = self.free(h, g, r)
                n = mini(n, seen[sk])
                seen[sk] -= n
            if n > 0:
                out.append((e, n))
        return out

    def size(self, h):
        z = self.f[h][3]
        if z < 4:
            return z + 1
        H = self.count(h)
        if H <= 0:
            return 5
        persons = self.cross(h)
        for e in self.hl[h]:
            persons += maxi(0, self.p.tr_hm_n[e])
        return maxi(5, int(gd_round(float(persons) / float(H))))

    def band(self, g):
        return self.p.tr_key[self.w["unit_of"][g] * KEY_STRIDE + 1]

    def klass(self, g):
        return self.p.tr_pt_code[g] // NTN


def _u(hd, a, b, c):
    return float(keyed.h64(hd, a, b, c) >> 11) / keyed.TWO53


def _pick(items, u, extra=0):
    tot = extra
    for it in items:
        tot += it[1]
    if tot <= 0:
        return -2
    x = mini(int(u * float(tot)), tot - 1)
    acc = 0
    for it2 in items:
        acc += it2[1]
        if x < acc:
            return it2[0]
    return -1


def _classify(t0, roles):
    if t0 == T_INSTITUTION:
        return t0
    if len(roles) <= 1:
        return T_SINGLE
    cnt = [0, 0, 0, 0, 0]
    for r in roles:
        cnt[r] += 1
    if cnt[R_PARENT] + cnt[R_OTHER] > 0:
        return T_OTHER
    if cnt[R_CHILD] == 0:
        return T_COUPLE if cnt[R_PARTNER] == 1 else T_OTHER
    return T_COUPLE_CHILDREN if cnt[R_PARTNER] == 1 else T_SINGLE_PARENT


def _cp_move(x, c, h2):
    p = x.p
    w = x.w
    p.tr_cp_n[c] -= 1
    rk = (h2, p.tr_cp_w[c], p.tr_cp_h[c])
    c2 = x.cpmap.get(rk, -1)
    if c2 < 0:
        c2 = len(p.tr_cp_n)
        p.tr_cp_hh.append(h2)
        p.tr_cp_w.append(p.tr_cp_w[c])
        p.tr_cp_h.append(p.tr_cp_h[c])
        p.tr_cp_n.append(0)
        w["cp_of"][p.tr_cp_w[c]].append(c2)
        w["cp_of"][p.tr_cp_h[c]].append(c2)
        x.cpmap[rk] = c2
        x._cp_in(c2)
    p.tr_cp_n[c2] += 1
    x.tl["cp_moved"] += 1


def _couple_of(x, h, g, u):
    # Why not a draw among h's partner entries: the couple table records the head's partner (§8 (b)); only the head mass it does not
    # cover may go without one
    p = x.p
    items = []
    tot = 0
    for c in x.cps.get((h, g), ()):
        if p.tr_cp_hh[c] == h and p.tr_cp_h[c] == g and p.tr_cp_n[c] > 0 and x.mass(h, p.tr_cp_w[c], (R_PARTNER,)) > 0:
            items.append((c, p.tr_cp_n[c]))
            tot += p.tr_cp_n[c]
    none_w = maxi(0, x.mass(h, g, (R_HEAD,)) + 1 - x.cpm(h, g, R_HEAD))
    return _pick(items, u, none_w)


def _draw(x, h, roles, freed, u, extra=0):
    p = x.p
    e = _pick(x.pool(h, roles, freed), u, extra)
    if e < 0:
        return e
    p.tr_hm_n[e] -= 1
    return e


def _rest(x, h, n_slots, hd, a, b, c0, mem):
    for i in range(n_slots):
        e = _draw(x, h, REST_ROLES, False, _u(hd, a, b, c0 + 3 + i))
        if e < 0:
            x.tl["rest_short"] += n_slots - i
            break
        mem.append([x.p.tr_hm_pt[e], x.p.tr_hm_role[e], False, x.p.tr_hm_role[e], -1])


def _place(x, h, mem, head_kept, cp, t_keep, z_keep):
    p = x.p
    fh = x.f[h]
    present = 0
    for m0 in mem:
        present += 1 if m0[0] >= 0 else 0
    if present == 0:
        if mem:
            x.add_cross(h, -1)
        x.add_count(h, -1)
        x.tl["hh_left"] += 1
        return
    hb = fh[2]
    k = fh[4]
    if not head_kept and t_keep < 0:
        nh = -1
        for i in range(len(mem)):
            if mem[i][1] == R_PARTNER:
                nh = i
        if nh < 0:
            nh = 0
            for i2 in range(len(mem)):
                if p.tr_points["age"][mem[i2][0]] > p.tr_points["age"][mem[nh][0]]:
                    nh = i2
        mem[nh][1] = R_HEAD
        hb = x.band(mem[nh][0])
        k = x.klass(mem[nh][0])
    if t_keep >= 0:
        t2 = t_keep
        z2 = z_keep if z_keep >= 0 else mini(4, len(mem) - 1)
    else:
        t2 = _classify(fh[1], [m[1] for m in mem])
        z2 = mini(4, len(mem) - 1)
    h2 = x.key(fh[0], t2, hb, z2, k)
    for m2 in mem:
        if m2[0] < 0:
            x.add_cross(h, -1)
            x.add_cross(h2, 1)
        else:
            x.add(h2, m2[0], m2[1], 1)
            _unc_move(x, h, h2, m2)
    if cp >= 0 and not CP_STAY:
        _cp_move(x, cp, h2)
    x.add_count(h, -1)
    x.add_count(h2, 1)
    x.tl["hh_moved"] += 1


def _unc_move(x, h, h2, m):
    if not m[2]:
        if m[3] <= R_PARTNER and x.f[h][1] in COUPLE_T and m[4] < 0:
            x.tl["dx_covered_moved"] += 1
        return
    if m[3] <= R_PARTNER:
        x.unc(h, m[0], 1)
    if m[1] <= R_PARTNER:
        x.unc(h2, m[0], -1)


def _with_head(x, h, g, hd, a, b, c0, mem, s_left, s, by_t):
    t = x.f[h][1]
    cp = -1
    gap = 0
    if t in PARTNER_T and s_left > 0 and (t != T_OTHER or s >= 3):
        if by_t:
            e, unc = _partner_t(x, h, False, _u(hd, a, b, c0))
        else:
            cp = _couple_of(x, h, g, _u(hd, a, b, c0))
            e = -1
            unc = False
            if cp >= 0:
                e = x.take(h, x.p.tr_cp_w[cp], R_PARTNER)
                x.tl["aged_partner_cp"] += 1
                mem[0][4] = 0
            else:
                mem[0][2] = cp == -1
                if cp == -2 and t in COUPLE_T:
                    return -1, s_left, -2
                if t in COUPLE_T:
                    e, unc = _partner_t(x, h, True, _u(hd, a, b, c0 + 2))
                    x.tl["aged_partner_t"] += 1
                    if e == -3:
                        return -1, s_left, -3
                cp = -1
        if e >= 0:
            mem.append([x.p.tr_hm_pt[e], R_PARTNER, unc, R_PARTNER, 0 if cp >= 0 else -1])
            s_left -= 1
        elif t in COUPLE_T:
            x.tl["partner_short"] += 1
    return cp, s_left, gap


def _role_mass(x, h, r):
    m = 0
    for it in x.pool(h, (r,), False):
        m += it[1]
    return m


def _partner_t(x, h, freed, u, cross_leaving=0):
    t = x.f[h][1]
    extra = 0
    if t == T_OTHER:
        pt = 0
        for it in x.pool(h, (R_PARTNER,), False):
            pt += it[1]
        extra = maxi(0, x.count(h) - pt)
    fr = freed and t in COUPLE_T
    e = _draw(x, h, (R_PARTNER,), fr, u, extra)
    if e == -2 and fr:
        # Why not leave the partner slot empty where h has no partner deficit: the partner left behind would stand above its heads
        # (T2s-b2); why not a covered partner: it would leave without its couple (T2s-cph-Δ). The caller keeps the household (-3)
        if _role_mass(x, h, R_PARTNER) <= _role_mass(x, h, R_HEAD) + x.cross(h) - cross_leaving:
            x.tl["partner_none"] += 1
            return -2, False
        return -3, False
    return e, fr and e >= 0


def _cph_pairs(p, w):
    out = {}
    for c in range(len(p.tr_cp_n)):
        h = p.tr_cp_hh[c]
        if w["htype"][h] not in COUPLE_T:
            continue
        for g in (p.tr_cp_w[c], p.tr_cp_h[c]):
            k = (p.tr_hh_keys[h], p.tr_pt_id[g])
            v = out.get(k, (0, 0))
            out[k] = (v[0] + p.tr_cp_n[c], v[1])
    for e in range(len(p.tr_hm_n)):
        h2 = w["hm_h"][e]
        if p.tr_hm_role[e] > R_PARTNER or w["htype"][h2] not in COUPLE_T:
            continue
        k2 = (p.tr_hh_keys[h2], p.tr_pt_id[p.tr_hm_pt[e]])
        v2 = out.get(k2, (0, 0))
        out[k2] = (v2[0], v2[1] + p.tr_hm_n[e])
    return out


def _cph_flow(p, w, tl):
    a = w["t23_cph0"]
    b = _cph_pairs(p, w)
    off = []
    for k in sorted(set(a) | set(b)):
        va = a.get(k, (0, 0))
        vb = b.get(k, (0, 0))
        # Why not Δ couples = Δ entries per pair: where the start or T2.2's split left a pair off, its uncovered mass leaves alone
        # (§8: only the covered mass leaves with its couple), which narrows the gap; a booking that breaks the table widens it
        if abs(vb[0] - vb[1]) > abs(va[0] - va[1]):
            off.append("%s|%d" % k)
    tl["cph_flow_off"] = len(off)
    tl["cph_flow_pairs"] = off


def after_age(p, w):
    x = Ctx(p, w)
    w["t23"] = x
    w["t23_cuts"] = []
    w["t23_cph0"] = _cph_pairs(p, w)
    hd = keyed.head(p.seed_v, "t23_age_hh")
    nk = len(p.tr_hh_keys)
    for h in range(nk):
        fh = x.f[h]
        for e in list(x.hl[h]):
            if p.tr_hm_role[e] != R_HEAD or p.tr_hm_n[e] <= 0:
                continue
            g = p.tr_hm_pt[e]
            b = x.band(g)
            if b == fh[2]:
                continue
            n = p.tr_hm_n[e]
            for _i in range(n):
                if p.tr_hm_n[e] <= 0:
                    break
                ai = x.di.get(("a", h), 0)
                x.di[("a", h)] = ai + 1
                s = x.size(h)
                p.tr_hm_n[e] -= 1
                mem = [[g, R_HEAD, False, R_HEAD, -1]]
                cp, left, gap = _with_head(x, h, g, hd, p.month, h, ai * SLOT_STRIDE, mem, s - 1, s, False)
                if gap < 0:
                    # Why not move it with a covered partner, or with none: the first leaves a couple behind (T2s-cph-Δ), the second a
                    # partner above its heads (T2s-b2); the household waits at its band for a later month
                    p.tr_hm_n[e] += 1
                    x.tl["aged_kept"] += 1
                    break
                _rest(x, h, left, hd, p.month, h, ai * SLOT_STRIDE, mem)
                h2 = x.key(fh[0], fh[1], b, fh[3], fh[4])
                for m in mem:
                    x.add(h2, m[0], m[1], 1)
                    _unc_move(x, h, h2, m)
                if mini(idiv(b * 5, 10), 8) != mini(idiv(fh[2] * 5, 10), 8):
                    x.tl["aged_hh10"] += 1
                if cp >= 0 and not CP_STAY:
                    _cp_move(x, cp, h2)
                x.add_count(h, -1)
                x.add_count(h2, 1)
                x.tl["aged_hh"] += 1
    n_pts = len(p.tr_pt_mass)
    held = [0] * n_pts
    for e2 in range(len(p.tr_hm_n)):
        held[p.tr_hm_pt[e2]] += p.tr_hm_n[e2]
    w["t23_m0"] = list(p.tr_pt_mass)
    w["t23_nh0"] = [p.tr_pt_mass[g2] - held[g2] for g2 in range(n_pts)]
    x.tl["unc_age"] = x.unc_out(x.unc_age)
    p.tr_margins["t23"] = x.tl


def _alloc(holds, d, hd, a, b, i0):
    out = [0] * len(holds)
    n_rem = 0
    for v in holds:
        n_rem += v
    d_rem = mini(d, n_rem)
    for i in range(len(holds)):
        if d_rem <= 0:
            break
        k = holds[i]
        y = d_rem if k >= n_rem else prims.hypergeometric(n_rem, k, d_rem, _u(hd, a, b, i0 + i))
        out[i] = y
        d_rem -= y
        n_rem -= k
    return out


def after_deaths(p, w):
    x = w["t23"]
    tl = x.tl
    x.unc_cur = x.unc_death
    m0 = w["t23_m0"]
    nh = list(w["t23_nh0"])
    n_pts = len(m0)
    dead = [m0[g] - p.tr_pt_mass[g] for g in range(n_pts)]
    for g0 in range(n_pts):
        tl["deaths"] += dead[g0]
    nh_u = [0] * p.tr_units
    if SKIP_DEATH_HH:
        _nh_units(p, w, nh, nh_u)
        tl["nh_u"] = nh_u
        tl["unc_death"] = {}
        tl["cut_gap"] = {}
        _cph_flow(p, w, tl)
        return
    booked = [0] * n_pts
    events = []
    if not PARTNER_BY_T:
        for (c, g, y) in w["t23_cuts"]:
            B = p.tr_cp_hh[c]
            if x.f[B][1] not in PARTNER_T:
                continue
            r = R_PARTNER if p.tr_cp_w[c] == g else R_HEAD
            other = p.tr_cp_h[c] if r == R_PARTNER else p.tr_cp_w[c]
            xb = mini(mini(y, x.mass(B, g, (r,))), dead[g] - booked[g])
            if x.f[B][1] in COUPLE_T:
                tl["dx_cut_short"] += y - maxi(0, xb)
            for _i in range(xb):
                x.take(B, g, r)
            if x.f[B][1] in COUPLE_T and y > xb:
                # Why not move the survivor out of B for the cut the dying's entry cannot hold: the survivor's household in B is then
                # headed by another point, which would stay behind above B's households (T2s-b2)
                x.gap_pair(B, g, -(y - xb))
                x.gap_pair(B, other, -(y - xb))
            if xb <= 0:
                continue
            booked[g] += xb
            tl["alloc_cp"] += xb
            events.append((0, B, g, r, other, xb))
    hd = keyed.head(p.seed_v, "t23_death_hh")
    for u in range(p.tr_units):
        for g2 in w["lists"][u]:
            if g2 >= n_pts or dead[g2] - booked[g2] <= 0:
                continue
            rest = dead[g2] - booked[g2]
            es = sorted(w["hm_of"][g2])
            holds = []
            seen = {}
            for e in es:
                n = maxi(0, p.tr_hm_n[e])
                h = w["hm_h"][e]
                r2 = p.tr_hm_role[e]
                if r2 <= R_PARTNER and x.f[h][1] in COUPLE_T and not PARTNER_BY_T:
                    sk = (h, r2)
                    if sk not in seen:
                        seen[sk] = x.free(h, g2, r2)
                    n = mini(n, seen[sk])
                    seen[sk] -= n
                holds.append(n)
            holds.append(maxi(0, nh[g2]))
            id_ = p.tr_pt_id[g2]
            if FIRST_ENTRY and es:
                got = [0] * len(holds)
                got[0] = rest
            else:
                got = _alloc(holds, rest, hd, p.month, id_, 0)
                left = rest
                for v in got:
                    left -= v
                if not PARTNER_BY_T:
                    for i0 in range(len(es)):
                        if got[i0] > 0 and p.tr_hm_role[es[i0]] <= R_PARTNER:
                            x.unc(w["hm_h"][es[i0]], g2, got[i0])
                if left > 0:
                    holds2 = [maxi(0, p.tr_hm_n[es[i]]) - got[i] for i in range(len(es))]
                    got2 = _alloc(holds2, left, hd, p.month, id_, len(holds))
                    for i2 in range(len(es)):
                        got[i2] += got2[i2]
                        left -= got2[i2]
                        if got2[i2] > 0 and p.tr_hm_role[es[i2]] <= R_PARTNER and x.f[w["hm_h"][es[i2]]][1] in COUPLE_T:
                            tl["dx_overflow"] += got2[i2]
                    tl["alloc_over_covered"] += _sum(got2)
                if left > 0:
                    tl["unbooked"] += left
                    tl["alloc_bad"] += 1
            for i3 in range(len(es)):
                if got[i3] <= 0:
                    continue
                e3 = es[i3]
                p.tr_hm_n[e3] -= got[i3]
                tl["alloc_gen"] += got[i3]
                events.append((1, w["hm_h"][e3], g2, p.tr_hm_role[e3], -1, got[i3]))
            nh[g2] -= got[len(es)]
            tl["alloc_nh"] += got[len(es)]
    for e4 in range(len(p.tr_hm_n)):
        if p.tr_hm_n[e4] < 0:
            tl["neg_entries"] += 1
            if tl["neg_first"] == "":
                tl["neg_first"] = "%s point id %d role %d n %d" % (p.tr_hh_keys[w["hm_h"][e4]], p.tr_pt_id[p.tr_hm_pt[e4]], p.tr_hm_role[e4], p.tr_hm_n[e4])
    hd2 = keyed.head(p.seed_v, "t23_cohh")
    for ev in events:
        for _j in range(ev[5]):
            _death(x, ev, hd2)
    _nh_units(p, w, nh, nh_u)
    tl["nh_u"] = nh_u
    tl["unc_death"] = x.unc_out(x.unc_death)
    tl["cut_gap"] = x.unc_out(x.cut_gap)
    _cph_flow(p, w, tl)


def _sum(v):
    s = 0
    for a in v:
        s += a
    return s


def _nh_units(p, w, nh, nh_u):
    for u in range(p.tr_units):
        for g in w["lists"][u]:
            if g < len(nh):
                nh_u[u] += nh[g]


def _death(x, ev, hd):
    p = x.p
    kind, h, g, r, other, _n = ev
    t = x.f[h][1]
    if x.count(h) <= 0:
        x.tl["hh_merged"] += 1
        if kind == 0 and t in COUPLE_T:
            x.tl["dx_surv_missing"] += 1
            x.gap_pair(h, other, -1)
        return
    di = x.di.get(("d", h), 0)
    x.di[("d", h)] = di + 1
    a = p.month
    c0 = di * SLOT_STRIDE
    s = x.size(h)
    if s <= 1 or t == T_SINGLE or t == T_INSTITUTION:
        _place(x, h, [], False, -1, -1, -1)
        return
    mem = []
    if kind == 0:
        e = x.take(h, other, R_HEAD if r == R_PARTNER else R_PARTNER)
        if e >= 0:
            ro = p.tr_hm_role[e]
            mem.append([other, ro, False, ro, 0])
            _rest(x, h, s - 2, hd, a, h, c0, mem)
            if r == R_HEAD and WIDOW_KEEP:
                x.tl["widowed_head"] += 1
                _place(x, h, mem, True, -1, t, -1)
                return
            if ro == R_PARTNER:
                x.tl["widowed_head"] += 1
            _place(x, h, mem, ro == R_HEAD, -1, -1, -1)
            return
        x.tl["surv_missing"] += 1
        if t in COUPLE_T:
            x.tl["dx_surv_missing"] += 1
            x.gap_pair(h, other, -1)
    left = s - 1
    if r == R_HEAD:
        if t in PARTNER_T and (t != T_OTHER or s >= 3):
            e2, unc2 = _partner_t(x, h, not PARTNER_BY_T, _u(hd, a, h, c0))
            if e2 == -3:
                # Why not move the household with a covered partner: its couple would stay behind (T2s-cph-Δ); in place the partner's
                # head and partner entries sum as before, and h is one partner short (T2s-b2's reported deficit)
                ew = _draw(x, h, (R_PARTNER,), False, _u(hd, a, h, c0))
                x.add(h, p.tr_hm_pt[ew], R_HEAD, 1)
                x.tl["widow_in_place"] += 1
                return
            if e2 >= 0:
                mem.append([p.tr_hm_pt[e2], R_PARTNER, unc2, R_PARTNER, -1])
                left -= 1
            elif t in COUPLE_T:
                x.tl["partner_short"] += 1
        _rest(x, h, left, hd, a, h, c0, mem)
        if mem and mem[0][1] == R_PARTNER and WIDOW_KEEP:
            x.tl["widowed_head"] += 1
            _place(x, h, mem, True, -1, t, -1)
            return
        _place(x, h, mem, False, -1, -1, -1)
        return
    freed = r == R_PARTNER and t in COUPLE_T and not PARTNER_BY_T
    eh = _draw(x, h, (R_HEAD,), freed, _u(hd, a, h, c0 + 1), x.cross(h))
    h_unc = freed and eh >= 0
    if eh == -2 and freed:
        # Why not a covered head: it would leave without its couple (T2s-cph-Δ); the household stays, one partner short (T2s-b2's
        # reported deficit)
        x.tl["head_kept"] += 1
        return
    if eh == -2:
        x.tl["hh_merged"] += 1
        x.tl["head_short"] += 1
        return
    cp = -1
    if eh < 0:
        mem.append([-1, R_HEAD, False, R_HEAD, 0])
        left -= 1
        if r != R_PARTNER and t in COUPLE_T and left > 0:
            e3, unc3 = _partner_t(x, h, not PARTNER_BY_T, _u(hd, a, h, c0), 1)
            if e3 == -3:
                x.tl["hh_kept_gap"] += 1
                return
            if e3 >= 0:
                mem.append([p.tr_hm_pt[e3], R_PARTNER, unc3, R_PARTNER, -1])
                left -= 1
    else:
        gh = p.tr_hm_pt[eh]
        mem.append([gh, R_HEAD, h_unc, R_HEAD, -1])
        left -= 1
        if r != R_PARTNER:
            cp, left, gap = _with_head(x, h, gh, hd, a, h, c0, mem, left, s, PARTNER_BY_T)
            if gap < 0:
                p.tr_hm_n[eh] += 1
                x.tl["hh_kept_gap"] += 1
                return
    _rest(x, h, left, hd, a, h, c0, mem)
    _place(x, h, mem, True, cp, -1, -1)


