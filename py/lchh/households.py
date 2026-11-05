# The twin of sim/modern/people/households.gd (LC_HH_PORT_PLAN §1): the start's households, the rake at the household level, the
# family links and the household readings, with the GDScript's loop orders
from core import detmath, keyed
from core.gd import clampi, gd_round, maxf, maxi, mini

from . import pstate as ps

TYPES = ("one_person", "couple_only", "couple_children", "single_parent", "other")
MALE_AT_BIRTH = 0.512
INSTITUTION = 5
SIZE_ATTEMPTS = 16
PILOT = 400
FINE = (0, 15, 25, 35, 45, 55, 65, 75, 85)


def _v(p, k):
    return p.hh_spec[k]["value"]


def _band_index(a, bands):
    for b in range(len(bands)):
        s = str(bands[b])
        if s.endswith("+"):
            if a >= int(s[:-1]):
                return b
            continue
        lo, hi = s.split("-")
        if a >= int(lo) and a <= int(hi):
            return b
    return -1


def _draw_age(p, x, sexes, lo, hi, shape):
    tot = 0.0
    for s in sexes:
        for a in range(lo, hi + 1):
            tot += p.cohort[a * ps.SEXES + s] * float(shape(a, s))
    target = x * tot
    acc = 0.0
    last = (lo, int(sexes[0]))
    for s2 in sexes:
        for a2 in range(lo, hi + 1):
            wgt = p.cohort[a2 * ps.SEXES + s2] * float(shape(a2, s2))
            if wgt <= 0.0:
                continue
            acc += wgt
            last = (a2, s2)
            if target < acc:
                return last
    return last


def _pick(shares, keys, x):
    acc = 0.0
    for k in keys:
        acc += float(shares[k])
        if x < acc:
            return k
    return str(keys[len(keys) - 1])


def _children(p, code, k, ma, r=0):
    def u(tag, j):
        return keyed.u(p.seed_v, tag, code, k, r * 8 + j)
    nk = int(_pick(_v(p, "children_given_any"), ["1", "2", "3", "4"], u("hhkids", 0)))
    bb = _v(p, "births_by_mother_age")
    left = _v(p, "left_home_by_age")
    out = []
    for c in range(nk):
        band = _pick(bb, ["15-19", "20-24", "25-29", "30-34", "35-39", "40-44", "45-49"], u("hhbirthage", c))
        lo = int(band.split("-")[0])
        b = lo + int(5.0 * u("hhbirthyear", c))
        ca = ma - b
        if ca < 0:
            continue
        cs = ps.MALE if u("hhkidsex", c) < MALE_AT_BIRTH else ps.FEMALE
        if ca >= 18:
            lb = "18-19" if ca < 20 else ("20-24" if ca < 25 else ("25-29" if ca < 30 else ("30-34" if ca < 35 else "35+")))
            if u("hhkidhome", c) < float(left[lb][cs]):
                continue
        out.append((ca, cs))
    return out


def _band_range(p, band):
    if band.endswith("+"):
        return (int(band[:-1]), ps.AGES - 1)
    lh = band.split("-")
    return (int(lh[0]), int(lh[1]))


def _householder_ages(p, alone_shape):
    ta = _v(p, "type_by_householder_age")
    bands = ta["bands"]
    hh = [0.0] * len(bands)
    for b in range(len(bands)):
        lo, hi = _band_range(p, str(bands[b]))
        al = 0.0
        for a in range(lo, hi + 1):
            for s in range(2):
                al += p.cohort[a * ps.SEXES + s] * float(alone_shape(a, s))
        hh[b] = al / maxf(1e-9, float(ta["shares"][b][0]))
    out = []
    for t in range(len(TYPES)):
        w = [0.0] * len(bands)
        for b2 in range(len(bands)):
            w[b2] = float(ta["shares"][b2][t]) * hh[b2]
        out.append([bands, w])
    return out


def _householder_age(p, bw, x_band, x_age, sex):
    w = bw[1]
    tot = 0.0
    for v in w:
        tot += v
    acc = 0.0
    b = len(w) - 1
    for i in range(len(w)):
        acc += w[i]
        if x_band * tot < acc:
            b = i
            break
    lo, hi = _band_range(p, str(bw[0][b]))
    return _draw_age(p, x_age, [sex], lo, hi, lambda _a, _s: 1.0)[0]


def _construct(p, c, k, t, cx):
    age_of = cx["age_of"]
    alone_shape = cx["alone_shape"]
    gap = cx["gap"]
    gp = cx["gp"]
    hb = cx["hb"]

    def u(tag, j=0):
        return keyed.u(p.seed_v, tag, c, k, j)

    def gap_n(tag, j=0):
        return int(gd_round(float(gap["mean"]) + float(gap["sd"]) * keyed.normal(p.seed_v, tag, c, k, j)))
    A1 = ps.AGES - 1
    ms = []
    if t == ps.HK_SINGLE:
        as0 = _draw_age(p, u("hhalone"), [ps.MALE, ps.FEMALE], 15, A1, alone_shape)
        ms.append([as0[0], as0[1], ps.R_HEAD, -1])
    elif t == ps.HK_COUPLE:
        man = _householder_age(p, age_of[ps.HK_COUPLE], u("hhband"), u("hhage"), ps.MALE)
        ms.append([man, ps.MALE, ps.R_HEAD, 1])
        ms.append([clampi(man - gap_n("hhgap"), 18, A1), ps.FEMALE, ps.R_PARTNER, 0])
    elif t == ps.HK_COUPLE_CHILDREN or t == ps.HK_SINGLE_PARENT:
        if t == ps.HK_COUPLE_CHILDREN:
            psx = ps.MALE
        else:
            psx = ps.FEMALE if u("hhspsex") < float(_v(p, "single_parent_mother")) else ps.MALE
        ha = _householder_age(p, age_of[t], u("hhband"), u("hhage"), psx)
        mother_age = clampi(ha - gap_n("hhgap"), 18, A1) if t == ps.HK_COUPLE_CHILDREN else ha
        kids = []
        for r in range(int(hb["redraws"])):
            kids = _children(p, c, k, mother_age, r)
            if kids:
                break
        ms.append([ha, psx, ps.R_HEAD, 1 if t == ps.HK_COUPLE_CHILDREN else -1])
        if t == ps.HK_COUPLE_CHILDREN:
            ms.append([mother_age, ps.FEMALE, ps.R_PARTNER, 0])
        for kd in kids:
            ms.append([kd[0], kd[1], ps.R_CHILD, -1])
        if not kids:
            t = ps.HK_COUPLE if t == ps.HK_COUPLE_CHILDREN else ps.HK_SINGLE
    else:
        ha4 = _householder_age(p, age_of[ps.HK_OTHER], u("hhband"), u("hhage"), ps.MALE)
        if ha4 < int(hb["old_from"]):
            mother4 = clampi(ha4 - gap_n("hhgap"), 18, A1)
            ms.append([ha4, ps.MALE, ps.R_HEAD, 1])
            ms.append([mother4, ps.FEMALE, ps.R_PARTNER, 0])
            for kd4 in _children(p, c, k, mother4):
                ms.append([kd4[0], kd4[1], ps.R_CHILD, -1])
            ga = clampi(mother4 + int(gd_round(float(gp["offset_mean"]) + float(gp["offset_sd"]) * keyed.normal(p.seed_v, "hhgrand", c, k, 0))), 50, A1)
            ms.append([ga, ps.FEMALE if u("hhgrandsex") < float(gp["female"]) else ps.MALE, ps.R_PARENT, -1])
        else:
            spouse = u("hholdspouse") < float(hb["old_spouse"])
            hs = ps.MALE if spouse else (ps.FEMALE if u("hhgrandsex") < float(gp["female"]) else ps.MALE)
            ms.append([ha4, hs, ps.R_HEAD, 1 if spouse else -1])
            if spouse:
                ms.append([clampi(ha4 - gap_n("hhgap"), 18, A1), ps.FEMALE, ps.R_PARTNER, 0])
            cw = clampi(ha4 - int(gd_round(float(hb["child_gap_mean"]) + float(hb["child_gap_sd"]) * keyed.normal(p.seed_v, "hhchildgap", c, k, 0))), 18, A1)
            ch = clampi(cw + gap_n("hhgap", 1), 18, A1)
            son = u("hhson") < float(hb["son"])
            o = len(ms)
            ms.append([ch, ps.MALE, ps.R_CHILD if son else ps.R_OTHER, o + 1])
            ms.append([cw, ps.FEMALE, ps.R_OTHER if son else ps.R_CHILD, o])
            for kd5 in _children(p, c, k, cw):
                ms.append([kd5[0], kd5[1], ps.R_OTHER, -1])
    return [t, ms]


def _size_lambdas(p, cx, by_pref, ts):
    sizes = []
    smax = 1
    for t in range(len(TYPES)):
        sz = []
        for q in range(PILOT):
            b = _construct(p, -1, q * SIZE_ATTEMPTS, t, cx)
            sz.append(len(b[1]))
            smax = maxi(smax, len(b[1]))
        sizes.append(sz)
    cx["size_max"] = smax
    target = _v(p, "mean_size_by_prefecture")
    out = {}
    for code in p.pref_codes:
        sh = by_pref[code] if code in by_pref else [float(ts[tn]) for tn in TYPES]
        lo = -3.0
        hi = 3.0
        for _it in range(40):
            mid = 0.5 * (lo + hi)
            m = 0.0
            for t2 in range(len(TYPES)):
                w = 0.0
                ws = 0.0
                for s2 in sizes[t2]:
                    x = detmath.exp(mid * float(s2 - smax))
                    w += x
                    ws += x * float(s2)
                m += float(sh[t2]) * ws / maxf(1e-12, w)
            if m < float(target.get(code, 2.21)):
                lo = mid
            else:
                hi = mid
        out[int(code)] = 0.5 * (lo + hi)
    return out


def _inst_share(inst, a, s):
    for b in range(len(inst["bands"])):
        if a >= int(inst["bands"][b][0]) and a <= int(inst["bands"][b][1]):
            return float(inst["men" if s == 0 else "women"][b])
    return 0.0


def build_start(p, n_per):
    ts = _v(p, "type_shares")
    by_pref = _v(p, "type_by_prefecture")
    alone = _v(p, "alone_share_by_band")
    gap = _v(p, "partner_age_gap")
    gp = _v(p, "grandparent")
    hb = _v(p, "householder_build")

    def alone_shape(a, s):
        b = _band_index(a, alone["bands"])
        return 0.0 if b < 0 else float(alone["men" if s == 0 else "women"][b])
    age_of = _householder_ages(p, alone_shape)
    inst = _v(p, "institution_start")

    def inst_shape(a, s):
        return _inst_share(inst, a, s)
    inst_frac = 0.0
    ctot = 0.0
    for a0 in range(ps.AGES):
        for s0 in range(2):
            inst_frac += p.cohort[a0 * ps.SEXES + s0] * _inst_share(inst, a0, s0)
            ctot += p.cohort[a0 * ps.SEXES + s0]
    inst_frac /= maxf(1e-9, ctot)
    cx = {"age_of": age_of, "alone_shape": alone_shape, "gap": gap, "gp": gp, "hb": hb}
    lambdas = _size_lambdas(p, cx, by_pref, ts)
    members = []
    types = []
    for code in p.pref_codes:
        c = int(code)
        shares = ts
        if code in by_pref:
            shares = {}
            for t0 in range(len(TYPES)):
                shares[TYPES[t0]] = float(by_pref[code][t0])
        k = 0
        n_inst = int(gd_round(float(n_per) * inst_frac))
        for q in range(n_inst):
            ai = _draw_age(p, keyed.u(p.seed_v, "hhinst", c, q, 0), [0, 1], 75, ps.AGES - 1, inst_shape)
            types.append([c, INSTITUTION])
            members.append([c, len(types) - 1, ai[0], ai[1], ps.R_HEAD, -1])
        count = n_inst
        lam = float(lambdas[c])
        sref = float(cx["size_max"]) if lam >= 0.0 else 1.0
        while count < n_per:
            t = TYPES.index(_pick(shares, TYPES, keyed.u(p.seed_v, "hhtype", c, k, 0)))
            built = []
            for att in range(SIZE_ATTEMPTS):
                built = _construct(p, c, k * SIZE_ATTEMPTS + att, t, cx)
                sz = float(len(built[1]))
                if att == SIZE_ATTEMPTS - 1 or keyed.u(p.seed_v, "hhsize", c, k * SIZE_ATTEMPTS + att, 0) < detmath.exp(lam * (sz - sref)):
                    break
            t = int(built[0])
            ms = built[1]
            types.append([c, t])
            for m in ms:
                members.append([c, len(types) - 1, int(m[0]), int(m[1]), int(m[2]), int(m[3])])
            count += len(ms)
            k += 1
    p.place_persons(len(members))
    p.hh_n = len(types)
    p.hh_type = [0] * p.hh_n
    p.hh_pref = [0] * p.hh_n
    p.hh_weight = [0.0] * p.hh_n
    p.hh_id = [0] * p.n
    for name in ("hh_role", "partner", "ever_married", "ever_left", "union_month", "last_birth", "births_n"):
        setattr(p, name, [0] * p.n)
    p.partner = [-1] * p.n
    per_pref = {}
    for h in range(p.hh_n):
        p.hh_type[h] = int(types[h][1])
        p.hh_pref[h] = int(types[h][0])
    for m2 in members:
        per_pref[int(m2[0])] = int(per_pref.get(int(m2[0]), 0)) + 1
    k_in = {}
    for i in range(p.n):
        code2 = int(members[i][0])
        kk = int(k_in.get(code2, 0))
        k_in[code2] = kk + 1
        p.place_person(i, code2, kk, int(members[i][2]), int(members[i][3]))
        p.hh_id[i] = int(members[i][1])
        p.hh_role[i] = int(members[i][4])
    for h2 in range(p.hh_n):
        p.hh_weight[h2] = float(p.pref_pop[p.hh_pref[h2]]) / float(per_pref[p.hh_pref[h2]])
    refresh_members(p)
    for h4 in range(p.hh_n):
        ms4 = p.hh_members[h4]
        for x in range(len(ms4)):
            off = int(members[ms4[x]][5])
            if off >= 0:
                p.partner[ms4[x]] = ms4[off]
    for i2 in range(p.n):
        h = p.hh_id[i2]
        p.weight[i2] = p.hh_weight[h]
        p.hh_kind[i2] = ps.HK_SINGLE if p.hh_type[h] == INSTITUTION else p.hh_type[h]
        p.hh_size[i2] = float(len(p.hh_members[h]))


def refresh_members(p):
    p.hh_members = [[] for _ in range(p.hh_n)]
    for i in range(p.n):
        p.hh_members[p.hh_id[i]].append(i)


def _fine(a):
    b = 0
    for k in range(len(FINE)):
        if a >= FINE[k]:
            b = k
    return b


def _cell(p, i, fine):
    return (_fine(p.age[i]) if fine else ps.band_of(p.age[i])) * ps.SEXES + p.sex[i]


def _private(p, h):
    return p.hh_type[h] < len(TYPES) and len(p.hh_members[h]) > 0


def _scale_cell(p, t, which):
    w = 0.0
    hs = []
    for h in range(p.hh_n):
        ms = p.hh_members[h]
        if len(ms) == 1 and which(h):
            i = ms[0]
            if p.sex[i] == int(t[2]) and p.age[i] >= int(t[0]) and p.age[i] <= int(t[1]):
                w += p.hh_weight[h]
                hs.append(h)
    if w <= 0.0:
        return
    for h2 in hs:
        p.hh_weight[h2] *= float(t[3]) / w


def _tilt_sizes(p):
    sizes = _v(p, "mean_size_by_prefecture")
    by = {}
    for h in range(p.hh_n):
        if _private(p, h):
            by.setdefault(p.hh_pref[h], []).append(h)
    for code in by:
        target = float(sizes.get("%02d" % code, 0.0))
        if target <= 0.0:
            continue
        hs = by[code]
        lo = -3.0
        hi = 3.0
        for _it in range(40):
            mid = 0.5 * (lo + hi)
            w = 0.0
            ws = 0.0
            for h2 in hs:
                sz = float(len(p.hh_members[h2]))
                x = p.hh_weight[h2] * detmath.exp(mid * (sz - target))
                w += x
                ws += x * sz
            if ws / maxf(1e-12, w) < target:
                lo = mid
            else:
                hi = mid
        lam = 0.5 * (lo + hi)
        for h3 in hs:
            p.hh_weight[h3] *= detmath.exp(lam * (float(len(p.hh_members[h3])) - target))


def rake(p, cell_target, scale, start=False):
    by_pref = _v(p, "type_by_prefecture")
    pop_total = 0.0
    for code0 in p.pref_pop:
        pop_total += float(p.pref_pop[code0]) * scale
    cells = cell_target
    alone_t = []
    inst_t = []
    if start:
        ctot = 0.0
        for k in range(len(p.cohort)):
            ctot += p.cohort[k]
        al = _v(p, "alone_share_by_band")
        for b in range(len(al["bands"])):
            band = str(al["bands"][b])
            if band == "45-54" or band == "55-64":
                continue
            lo, hi = _band_range(p, band)
            for s in range(2):
                cc = 0.0
                for a in range(lo, hi + 1):
                    cc += p.cohort[a * ps.SEXES + s]
                alone_t.append([lo, hi, s, float(al["men" if s == 0 else "women"][b]) * cc / ctot * pop_total])
        inst = _v(p, "institution_start")
        for b2 in range(len(inst["bands"])):
            for s2 in range(2):
                cc2 = 0.0
                for a2 in range(int(inst["bands"][b2][0]), mini(int(inst["bands"][b2][1]), ps.AGES - 1) + 1):
                    cc2 += p.cohort[a2 * ps.SEXES + s2]
                sh = float(inst["men" if s2 == 0 else "women"][b2])
                inst_t.append([int(inst["bands"][b2][0]), int(inst["bands"][b2][1]), s2, sh * cc2 / ctot * pop_total])
        cells = [0.0] * (len(FINE) * ps.SEXES)
        for a3 in range(ps.AGES):
            for s3 in range(2):
                cells[_fine(a3) * ps.SEXES + s3] += p.cohort[a3 * ps.SEXES + s3] / ctot
    for _r in range(30 if start else 8):
        if start:
            tw = {}
            for h0 in range(p.hh_n):
                if _private(p, h0):
                    key = p.hh_pref[h0]
                    if key not in tw:
                        tw[key] = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
                    arr = tw[key]
                    arr[p.hh_type[h0]] += p.hh_weight[h0]
                    arr[5] += p.hh_weight[h0]
            for h1 in range(p.hh_n):
                if not _private(p, h1):
                    continue
                a1 = tw.get(p.hh_pref[h1], [])
                code = "%02d" % p.hh_pref[h1]
                if len(a1) > 0 and a1[p.hh_type[h1]] > 0.0 and code in by_pref:
                    p.hh_weight[h1] *= float(by_pref[code][p.hh_type[h1]]) * a1[5] / a1[p.hh_type[h1]]
        for t in alone_t:
            _scale_cell(p, t, lambda h: _private(p, h) and p.hh_type[h] == ps.HK_SINGLE)
        csum = [0.0] * len(cells)
        all_ = 0.0
        for h4 in range(p.hh_n):
            for i in p.hh_members[h4]:
                csum[_cell(p, i, start)] += p.hh_weight[h4]
                all_ += p.hh_weight[h4]
        logf = [0.0] * len(cells)
        for c in range(len(cells)):
            logf[c] = detmath.log(cells[c] * all_ / csum[c]) if csum[c] > 0.0 and cells[c] > 0.0 else 0.0
        for h in range(p.hh_n):
            ms = p.hh_members[h]
            if not ms:
                continue
            acc = 0.0
            for i2 in ms:
                acc += logf[_cell(p, i2, start)]
            p.hh_weight[h] *= detmath.exp(acc / float(len(ms)))
        for t2 in inst_t:
            _scale_cell(p, t2, lambda h: p.hh_type[h] == INSTITUTION)
        _tilt_sizes(p)
        now = {}
        for h5 in range(p.hh_n):
            now[p.hh_pref[h5]] = float(now.get(p.hh_pref[h5], 0.0)) + p.hh_weight[h5] * float(len(p.hh_members[h5]))
        for h6 in range(p.hh_n):
            w0 = float(now.get(p.hh_pref[h6], 0.0))
            if w0 > 0.0 and p.hh_pref[h6] in p.pref_pop:
                p.hh_weight[h6] *= float(p.pref_pop[p.hh_pref[h6]]) * scale / w0
    for i3 in range(p.n):
        p.weight[i3] = p.hh_weight[p.hh_id[i3]]


def set_member_weight(p, i):
    p.weight[i] = p.hh_weight[p.hh_id[i]]


def add_household_weight(p, w):
    p.hh_weight.append(w)


def _nm_band(a, lo):
    for b in range(len(lo) - 1, -1, -1):
        if a >= int(lo[b]):
            return b if (b < len(lo) - 1 or a <= int(lo[b]) + 9) else -1
    return -1


def link_family(p):
    for h in range(p.hh_n):
        ms = p.hh_members[h]
        for a in range(len(ms)):
            for b in range(a + 1, len(ms)):
                i = ms[a]
                j = ms[b]
                if ps.rel_has_contact(p, i, j):
                    continue
                if ps.rel_add(p, i, j, ps.K_FAMILY):
                    if not ps.rel_add(p, j, i, ps.K_FAMILY):
                        ps.rel_unlink(p, i, j)


def kish(p):
    sw = 0.0
    sw2 = 0.0
    nh = 0
    for h in range(p.hh_n):
        if _private(p, h):
            sw += p.hh_weight[h]
            sw2 += p.hh_weight[h] * p.hh_weight[h]
            nh += 1
    pw = 0.0
    pw2 = 0.0
    for i in range(p.n):
        pw += p.weight[i]
        pw2 += p.weight[i] * p.weight[i]
    by = {}
    for h2 in range(p.hh_n):
        if _private(p, h2):
            a = by.get(p.hh_pref[h2], [0.0, 0.0, 0.0])
            a[0] += p.hh_weight[h2]
            a[1] += p.hh_weight[h2] * p.hh_weight[h2]
            a[2] += 1.0
            by[p.hh_pref[h2]] = a
    eff_in = 0.0
    for code in by:
        b = by[code]
        eff_in += b[0] * b[0] / maxf(1e-12, b[1])
    return {"households": nh, "households_eff": sw * sw / maxf(1e-12, sw2), "households_eff_within": eff_in, "persons": p.n,
            "persons_eff": pw * pw / maxf(1e-12, pw2)}


def type_shares(p):
    w = [0.0] * len(TYPES)
    tot = 0.0
    persons = 0.0
    for h in range(p.hh_n):
        sz = len(p.hh_members[h])
        if sz == 0 or p.hh_type[h] >= len(TYPES):
            continue
        w[p.hh_type[h]] += p.hh_weight[h]
        tot += p.hh_weight[h]
        persons += p.hh_weight[h] * float(sz)
    out = {}
    for t in range(len(TYPES)):
        out[TYPES[t]] = w[t] / maxf(1e-9, tot)
    out["mean_size"] = persons / maxf(1e-9, tot)
    return out
