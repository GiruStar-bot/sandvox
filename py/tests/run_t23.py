# T23_PLAN round 1 (§3, §4, §7; §8 AMENDED by M044) on the two-prefecture start (ORACLE_PREFS=13,47 of tools/py/oracle_dump.gd):
#   T2s-cph@m0  S0 with T2.3 off, report (M044: if not exact, a T1 / T2.2 gap)
#   T2s-off     T2.3 off: every month's per-field hashes equal the oracle's (P2), months 1-13
#   T2s-b, T2s-b2, T2s-dh   T2.3 on, every month; T2s-cph every month as a report
#   T2s-ref     T2.3 on: the pure digests at months 1, 12 and 13
#   MF-b, MF-b2, MF-dh, MF-cph1, MF-cph2   each switch makes its row fail
#   T2s-cph-Δ   (§10) T2.3 on, every month: across the deaths bracket (just before _t22_deaths to just after after_deaths) and the
#               ageing bracket (just around after_age), every (bundle, point) residual (couples − head and partner entries, couple
#               types) changes by exactly T2.3's tallied uncovered bookings; MF-cph1 fails it at month 1, MF-cph2 at the first crossing
#   COST        (§10 (1)) per month: households moved by ageing, those that are also 10-year crossings, and T2.3's share of the step
#   python3 py/tests/run_t23.py <oracle dir> [months] [parts: s0,off,on,mf]
import gc
import os
import sys
import time

from common import Kit, peak_mb
from tiers import month, state, t23

SIZE_MIN = t23.SIZE_MIN
SIZE_MAX = t23.SIZE_MAX


def load(d):
    return month.St(state.load(os.path.join(d, "m00"), as_lists=True))


def units_of(p):
    uo = [0] * p.tr_pt_off[p.tr_units]
    for u in range(p.tr_units):
        for g in range(p.tr_pt_off[u], p.tr_pt_off[u + 1]):
            uo[g] = u
    return uo


def cph(p):
    cp = {}
    cs = {}
    for c in range(len(p.tr_cp_n)):
        h = p.tr_cp_hh[c]
        for g in (p.tr_cp_w[c], p.tr_cp_h[c]):
            cp[(h, g)] = cp.get((h, g), 0) + p.tr_cp_n[c]
        cs[h] = cs.get(h, 0) + p.tr_cp_n[c]
    ent = {}
    for h in range(len(p.tr_hh_keys)):
        for e in range(p.tr_hm_off[h], p.tr_hm_off[h + 1]):
            if p.tr_hm_role[e] <= 1:
                ent[(h, p.tr_hm_pt[e])] = ent.get((h, p.tr_hm_pt[e]), 0) + p.tr_hm_n[e]
    off = {}
    sums = {}
    for h in range(len(p.tr_hh_keys)):
        k = p.tr_hh_keys[h]
        if int(k.split("|")[1]) not in t23.COUPLE_T:
            continue
        cnt = int(p.tr_hh[k]["count"])
        if cs.get(h, 0) != cnt:
            sums[k] = (cs.get(h, 0), cnt, int(p.tr_hh[k].get("cross", 0)))
    for key in sorted(set(cp) | set(ent)):
        k2 = p.tr_hh_keys[key[0]]
        if int(k2.split("|")[1]) not in t23.COUPLE_T:
            continue
        a = cp.get(key, 0)
        b = ent.get(key, 0)
        if a != b:
            off[(k2, p.tr_pt_id[key[1]])] = (a, b)
    return off, sums


def cph_line(off, sums):
    d = 0
    for v in off.values():
        d += abs(v[0] - v[1])
    sx = sum(1 for v in sums.values() if v[0] != v[1] - v[2])
    return "(bundle, point) pairs off %d (|diff| %d persons), bundles with Σ couples ≠ households %d (≠ households − cross %d); first %s" % (
        len(off), d, len(sums), sx, (sorted(off.items())[0] if off else "-"))


def t2s_b(p):
    uo = units_of(p)
    comp = [0] * p.tr_units
    for e in range(len(p.tr_hm_n)):
        comp[uo[p.tr_hm_pt[e]]] += p.tr_hm_n[e]
    nh_u = p.tr_margins["t23"]["nh_u"]
    bad = []
    for u in range(p.tr_units):
        if comp[u] + nh_u[u] != p.tr_count[u]:
            bad.append((month._key_str(p.tr_key, u), p.tr_count[u], comp[u], nh_u[u]))
    return bad, int(p.tr_margins["t22"].get("lost_hm", 0))


def t2s_b2(p):
    bad_h = []
    bad_p = []
    bad_f = []
    deficit = 0
    short = {}
    over = 0
    for h in range(len(p.tr_hh_keys)):
        k = p.tr_hh_keys[h]
        f = k.split("|")
        t = int(f[1])
        z = int(f[3])
        cnt = int(p.tr_hh[k]["count"])
        cr = int(p.tr_hh[k].get("cross", 0))
        hd = 0
        pt = 0
        ps = cr
        for e in range(p.tr_hm_off[h], p.tr_hm_off[h + 1]):
            n = p.tr_hm_n[e]
            ps += n
            if p.tr_hm_role[e] == 0:
                hd += n
            elif p.tr_hm_role[e] == 1:
                pt += n
        if hd + cr != cnt:
            bad_h.append((k, cnt, hd, cr))
        if t in t23.COUPLE_T:
            if pt > hd + cr:
                bad_p.append((k, hd, pt, cr))
            deficit += max(0, hd + cr - pt)
        if (z < SIZE_MIN[t] or z > SIZE_MAX[t]) and (ps > 0 or cnt > 0):
            bad_f.append((k, cnt, ps))
        short[t] = short.get(t, 0) + max(0, (z + 1) * cnt - ps)
        if z < 4 and ps > (z + 1) * cnt:
            over += ps - (z + 1) * cnt
    return bad_h, bad_p, bad_f, deficit, short, over


def t2s_dh(p):
    tl = p.tr_margins["t23"]
    neg_c = [(k, int(v["count"]), int(v.get("cross", 0))) for k, v in p.tr_hh.items() if int(v["count"]) < 0 or int(v.get("cross", 0)) < 0]
    return int(tl["neg_entries"]), tl["neg_first"], neg_c, int(tl["alloc_bad"]), int(tl["unbooked"]), int(tl["deaths"]), \
        int(tl["alloc_cp"]) + int(tl["alloc_gen"]) + int(tl["alloc_nh"])


SNAP = {}
TIME = {"t23": 0.0, "snap": 0.0}


def _snap(name, p, w):
    t0 = time.perf_counter()
    SNAP[name] = t23._cph_pairs(p, w)
    TIME["snap"] += time.perf_counter() - t0


def install():
    deaths0 = month._t22_deaths
    age0 = t23.after_age
    after0 = t23.after_deaths

    def deaths(p, w):
        if getattr(p, "t23", False):
            _snap("d0", p, w)
        deaths0(p, w)

    def age(p, w):
        _snap("a0", p, w)
        t0 = time.perf_counter()
        age0(p, w)
        TIME["t23"] += time.perf_counter() - t0
        _snap("a1", p, w)

    def after(p, w):
        t0 = time.perf_counter()
        after0(p, w)
        TIME["t23"] += time.perf_counter() - t0
        _snap("d1", p, w)

    month._t22_deaths = deaths
    t23.after_age = age
    t23.after_deaths = after


def delta_off(a, b, tally):
    off = []
    for k in sorted(set(a) | set(b)):
        va = a.get(k, (0, 0))
        vb = b.get(k, (0, 0))
        dr = (vb[0] - vb[1]) - (va[0] - va[1])
        key = "%s|%d" % k
        if dr != int(tally.get(key, 0)):
            off.append((key, va, vb, dr, int(tally.get(key, 0))))
    for key2 in sorted(tally):
        parts = key2.rsplit("|", 1)
        if (parts[0], int(parts[1])) not in a and (parts[0], int(parts[1])) not in b and int(tally[key2]) != 0:
            off.append((key2, (0, 0), (0, 0), 0, int(tally[key2])))
    return off


def cphd(p):
    tl = p.tr_margins["t23"]
    oa = delta_off(SNAP["a0"], SNAP["a1"], tl["unc_age"])
    od = delta_off(SNAP["d0"], SNAP["d1"], tl["unc_death"])
    return oa, od, len(set(SNAP["a0"]) | set(SNAP["a1"])), len(set(SNAP["d0"]) | set(SNAP["d1"]))


def cphd_line(p, m, tag):
    oa, od, na, nd = cphd(p)
    tl = p.tr_margins["t23"]
    sa = sum(tl["unc_age"].values())
    sd = sum(tl["unc_death"].values())
    first = (oa or od or ["-"])[0]
    gap = tl.get("cut_gap", {})
    expl = sum(1 for o in od if o[3] == o[4] + int(gap.get(o[0], 0)))
    return (not oa and not od), "T2s-cph-Δ m%02d%s ageing bracket: pairs off %d of %d (uncovered bookings tallied in %d pairs, Σ %+d); deaths bracket: pairs off %d of %d (tallied in %d pairs, Σ %+d); first off (pair, (couples, entries) before, after, Δ residual, tally) %s; REPORT the deaths bracket's off pairs whose Δ is the tally plus T2.2 couple cuts T2.3 could not pair (the dying holds no entry in the couple's bundle, or the survivor is not there; the registered T1 / T2.2 gap): %d of %d; the gap cases in the couple types: cut deaths the dying's entry in B could not hold %d, survivors not in B %d, covered persons moved without their couple %d, deaths past the free mass %d" % (
        m, tag, len(oa), na, len(tl["unc_age"]), sa, len(od), nd, len(tl["unc_death"]), sd, first, expl, len(od), tl["dx_cut_short"], tl["dx_surv_missing"],
        tl["dx_covered_moved"], tl["dx_overflow"])


def step(p):
    gc.collect()
    t1 = time.perf_counter()
    month.step(p)
    p.month += 1
    return time.perf_counter() - t1


def run_off(kit, d, months):
    p = load(d)
    off, sums = cph(p)
    print("REPORT T2s-cph@m0 (S0, T2.3 off; M044: run first as a report): " + cph_line(off, sums), flush=True)
    exact0 = not off and not sums
    bh, bp, bf, dfc, short, over = t2s_b2(p)
    print("REPORT T2s-b2@m0 (S0): heads + cross off %d, partners above heads + cross %d, forbidden %d, partner deficit %d, persons short of size x households by type %s, above it %d" % (
        len(bh), len(bp), len(bf), dfc, dict(sorted(short.items())), over), flush=True)
    for m in range(1, months + 1):
        el = step(p)
        dg, hs = state.digest_st(p)
        want = state.read_hashes(os.path.join(d, "m%02d.sha.txt" % m))
        bad = [n for n in sorted(want) if hs.get(n) != want[n]]
        kit.check(not bad and set(hs) == set(want), "T2s-off m%02d (T2.3 off against the oracle's per-field hashes): %.1f s, digest %s, fields differing %d %s" % (m, el, dg[:16], len(bad), bad[:6]))
        off, sums = cph(p)
        print("REPORT T2s-cph m%02d (T2.3 off): %s" % (m, cph_line(off, sums)), flush=True)
    return exact0


def rows(kit, p, m, tag):
    bad_b, lost = t2s_b(p)
    kit.check(not bad_b and lost == 0, "T2s-b m%02d%s compositions + no-household mass = the person-bundle's count: %d of %d keys off, persons lost at the rebuild %d; first %s" % (
        m, tag, len(bad_b), p.tr_units, lost, bad_b[0] if bad_b else "-"))
    bh, bp, bf, dfc, short, over = t2s_b2(p)
    kit.check(not bh and not bp and not bf, "T2s-b2 m%02d%s heads + cross = households off in %d bundles, partners above heads + cross in the couple types %d, forbidden sizes %d; first %s; REPORT the couple types' partner deficit %d, persons short of size x households by type %s, persons above it %d" % (
        m, tag, len(bh), len(bp), len(bf), (bh or bp or bf or ["-"])[0], dfc, dict(sorted(short.items())), over))
    ne, nf, nc, ab, ub, dd, al = t2s_dh(p)
    kit.check(ne == 0 and not nc and ab == 0 and al == dd, "T2s-dh m%02d%s entries below 0: %d (first %s), household counts below 0: %d %s; points with Σ allocated ≠ d: %d (unbooked %d); deaths %d, allocated %d" % (
        m, tag, ne, nf or "-", len(nc), nc[:2], ab, ub, dd, al))
    return bool(bad_b) or lost != 0, bool(bh or bp or bf), bool(ne or nc or ab or al != dd)


def run_on(kit, d, months):
    p = load(d)
    p.t23 = True
    ref = {}
    hist = {}
    cost = []
    for m in range(1, months + 1):
        TIME["t23"] = 0.0
        TIME["snap"] = 0.0
        el = step(p)
        tl = p.tr_margins["t23"]
        print("month %d (T2.3 on) %.1f s; t23 %s" % (m, el, {k: v for k, v in tl.items() if k not in ("nh_u", "cph_flow_pairs", "unc_age", "unc_death", "cut_gap")}), flush=True)
        rows(kit, p, m, "")
        okd, line = cphd_line(p, m, "")
        kit.check(okd, line)
        st = el - TIME["snap"]
        cost.append((m, int(tl["aged_hh"]), int(tl["aged_hh10"]), TIME["t23"], st))
        off, sums = cph(p)
        hist[m] = set(tl["cph_flow_pairs"])
        print("REPORT T2s-cph m%02d (T2.3 on): level %s; pairs whose |couples − head + partner entries| widens over T2.3's span %d, first %s" % (
            m, cph_line(off, sums), len(hist[m]), tl["cph_flow_pairs"][:1]), flush=True)
        if m in (1, 12, 13):
            dg, _hs = state.digest_st(p)
            ref[m] = dg
            print("REPORT T2s-ref m%02d digest %s" % (m, dg), flush=True)
    print("REPORT COST (§10 (1), T2.3 on, two-prefecture start): month | households moved by ageing (5-year crossings) | of them 10-year crossings | ratio 5y/10y | T2.3 s | step s (snapshots excluded) | T2.3 share", flush=True)
    for (m2, a5, a10, ts, st2) in cost:
        print("REPORT COST m%02d | %d | %d | %.2f | %.2f | %.2f | %.1f%%" % (m2, a5, a10, float(a5) / float(a10) if a10 else 0.0, ts, st2, 100.0 * ts / st2 if st2 > 0 else 0.0), flush=True)
    t5 = sum(c[1] for c in cost)
    t10 = sum(c[2] for c in cost)
    print("REPORT COST total months 1-%d | %d | %d | %.2f | %.1f | %.1f | %.1f%%" % (len(cost), t5, t10, float(t5) / float(t10) if t10 else 0.0, sum(c[3] for c in cost), sum(c[4] for c in cost),
                                                                      100.0 * sum(c[3] for c in cost) / max(1e-9, sum(c[4] for c in cost))), flush=True)
    return ref, hist


def run_mf(kit, d, months, name, flag, row, hist):
    setattr(t23, flag, True)
    try:
        p = load(d)
        p.t23 = True
        hit = None
        for m in range(1, months + 1):
            step(p)
            if row == "cphd":
                okd, line = cphd_line(p, m, " [%s]" % name)
                print(("ok   " if okd else "MF-row ") + line, flush=True)
                if not okd:
                    oa, od, _na, _nd = cphd(p)
                    br = "ageing" if oa else "deaths"
                    o = (oa or od)[0]
                    hit = (m, "%s bracket, bundle %s, point id %s: Δ residual %+d against tally %+d; pairs off: ageing %d, deaths %d; households moved by ageing this month %d" % (
                        br, o[0].rsplit("|", 1)[0], o[0].rsplit("|", 1)[1], o[3], o[4], len(oa), len(od), int(p.tr_margins["t23"]["aged_hh"])))
            elif row == "cph":
                fl = p.tr_margins["t23"]["cph_flow_pairs"]
                new = [k for k in fl if k not in hist.get(m, set())]
                print("%s m%02d: T2s-cph pairs widened %d (T2.3 on: %d), not widened in the T2.3-on run %d" % (name, m, len(fl), len(hist.get(m, ())), len(new)), flush=True)
                if new:
                    hit = (m, "bundle %s, point id %s: |couples − head + partner entries| widens over T2.3's span; %d pairs widen against %d in the T2.3-on run" % (
                        new[0].rsplit("|", 1)[0], new[0].rsplit("|", 1)[1], len(fl), len(hist.get(m, ()))))
            else:
                fb, fb2, fdh = rows(kit_null, p, m, " [%s]" % name)
                if row == "b" and fb:
                    bad_b, lost = t2s_b(p)
                    hit = (m, "person-bundle key %s count %d, entries %d + no-household %d (lost %d)" % (bad_b[0] + (lost,)) if bad_b else (m, "lost %d" % lost))
                elif row == "b2" and fb2:
                    bh, bp, bf, _d, _s2, _o = t2s_b2(p)
                    hit = (m, "heads off %s; partners above heads %s; forbidden %s" % (bh[:1], bp[:1], bf[:1]))
                elif row == "dh" and fdh:
                    ne, nf, nc, ab, _u, dd, al = t2s_dh(p)
                    hit = (m, "entries below 0 %d, first %s; counts below 0 %d" % (ne, nf, len(nc)))
            if hit:
                break
        kit.check(hit is not None, "%s (switch %s): T2s-%s fails%s" % (name, flag, {"cph": "cph (widening read)", "cphd": "cph-Δ"}.get(row, row), (" at month %d: %s" % hit) if hit else " in no month up to %d (the must-fail does not bite)" % months))
    finally:
        setattr(t23, flag, False)


class _Null:
    def check(self, ok, label):
        print(("ok   " if ok else "MF-row ") + label, flush=True)


kit_null = _Null()


def main():
    d = sys.argv[1]
    months = int(sys.argv[2]) if len(sys.argv) > 2 else 13
    parts = sys.argv[3].split(",") if len(sys.argv) > 3 else ["off", "on", "mf"]
    kit = Kit("py/tests/run_t23.py")
    t0 = time.perf_counter()
    if "off" in parts:
        run_off(kit, d, months)
        print("off run %.0f s, peak RSS %.0f MB" % (time.perf_counter() - t0, peak_mb()), flush=True)
    hist = {}
    install()
    if "on" in parts or "mf" in parts:
        t1 = time.perf_counter()
        _ref, hist = run_on(kit, d, months)
        print("on run %.0f s, peak RSS %.0f MB" % (time.perf_counter() - t1, peak_mb()), flush=True)
    if "mf" in parts:
        t2 = time.perf_counter()
        for name, flag, row in (("MF-b", "SKIP_DEATH_HH", "b"), ("MF-b2", "WIDOW_KEEP", "b2"), ("MF-dh", "FIRST_ENTRY", "dh"),
                                ("MF-cph1", "PARTNER_BY_T", "cph"), ("MF-cph2", "CP_STAY", "cph"),
                                ("MF-cph1", "PARTNER_BY_T", "cphd"), ("MF-cph2", "CP_STAY", "cphd")):
            run_mf(kit, d, months, name, flag, row, hist)
        print("must-fails %.0f s, peak RSS %.0f MB" % (time.perf_counter() - t2, peak_mb()), flush=True)
    kit.finish()


if __name__ == "__main__":
    main()
