# T23_PLAN §12: the national re-reads on a fresh national S0 (tools/py/oracle_dump.gd, no ORACLE_PREFS), one national state alive:
#   on   p.t23 on, months 1-13: T2s-b, T2s-b2, T2s-dh every month (exact); T2s-cph-Δ every month (the ageing bracket exact; in the
#        deaths bracket every off pair is a tallied unpaired T2.2 cut, any other fails); T2s-hh at months 0, 1, 12 (report);
#        T2s-qk@y1 and T2s-dgq@y1 (sim/modern/test_modern_t2_month.gd's reads, py/tests/t2_rows.py), "bundle-mean quartiles; T2.3's
#        household moves only"
#   off  p.t23 off, months 1-12: the month-1 per-field hashes against the oracle's (P2), and T2s-qk@y1, T2s-dgq@y1 as the port's check
#        against that test's GDScript read on the refresh (qk 0.1334 against 0.1313; dgq 0 grade and 0 income misses)
#   python3 py/tests/run_t23_nat.py <national dump dir> [on|off] [months]
import os
import sys
import time

from common import Kit, peak_mb
from tiers import month, state
import run_t23 as R
import t2_rows

NAME = ["one-person", "couple", "couple + children", "single parent", "other", "institution"]


def hh_table(p):
    out = {}
    for k, v in p.tr_hh.items():
        f = k.split("|")
        key = (int(f[1]), int(f[3]))
        out[key] = out.get(key, 0) + int(v["count"])
    return out


def hh_line(tab, base, m):
    txt = ""
    tot = 0
    for t in range(6):
        cells = []
        for z in range(5):
            n = tab.get((t, z), 0)
            tot += n
            if n or base.get((t, z), 0):
                cells.append("%s %d (%+d)" % ("5+" if z == 4 else str(z + 1), n, n - base.get((t, z), 0)))
        txt += " %s: %s;" % (NAME[t], ", ".join(cells) if cells else "-")
    return "REPORT T2s-hh m%02d (households move by deaths and ageing; no partnering, births or leaving home before T2.5) households by type x size class, national, (change against the start): total %d;%s" % (m, tot, txt)


def cphd_nat(kit, p, m):
    oa, od, na, nd = R.cphd(p)
    tl = p.tr_margins["t23"]
    gap = tl.get("cut_gap", {})
    other = [o for o in od if o[3] != o[4] + int(gap.get(o[0], 0))]
    kit.check(not oa and not other, "T2s-cph-Δ m%02d (national; the deaths bracket under the registered gap) ageing bracket: pairs off %d of %d (uncovered bookings tallied in %d pairs); deaths bracket: pairs off %d of %d, of them a tallied unpaired T2.2 cut %d, any other %d; first other %s; first ageing off %s; the gap cases: cut deaths the dying's entry in B could not hold %d, survivors not in B %d, covered persons moved without their couple %d, deaths past the free mass %d" % (
        m, len(oa), na, len(tl["unc_age"]), len(od), nd, len(od) - len(other), len(other), other[0] if other else "-", oa[0] if oa else "-",
        tl["dx_cut_short"], tl["dx_surv_missing"], tl["dx_covered_moved"], tl["dx_overflow"]))


def main():
    d = sys.argv[1]
    mode = sys.argv[2] if len(sys.argv) > 2 else "on"
    months = int(sys.argv[3]) if len(sys.argv) > 3 else (13 if mode == "on" else 12)
    kit = Kit("py/tests/run_t23_nat.py " + mode)
    t0 = time.perf_counter()
    p = R.load(d)
    print("load %.0f s, units %d, points %d, household-bundles %d, entries %d, couple entries %d; RSS peak %.0f MB" % (
        time.perf_counter() - t0, p.tr_units, len(p.tr_pt_mass), len(p.tr_hh_keys), len(p.tr_hm_n), len(p.tr_cp_n), peak_mb()), flush=True)
    yr = {}
    label = "year 1, T2.3 off" if mode == "off" else "year 1, T2.3 on; bundle-mean quartiles; T2.3's household moves only"
    if mode == "on":
        p.t23 = True
        R.install()
        base = hh_table(p)
        print(hh_line(base, base, 0), flush=True)
    for m in range(1, months + 1):
        R.TIME["t23"] = 0.0
        R.TIME["snap"] = 0.0
        el = R.step(p)
        tl = p.tr_margins["t22"]
        if m <= 12:
            t2_rows.year_add(yr, tl)
        if mode == "on":
            t3 = p.tr_margins["t23"]
            print("month %d (T2.3 on) %.0f s (T2.3 %.0f s, snapshots %.0f s); households moved by ageing %d (10-year crossings %d, kept %d); deaths %d; peak RSS so far %.0f MB" % (
                m, el, R.TIME["t23"], R.TIME["snap"], int(t3["aged_hh"]), int(t3["aged_hh10"]), int(t3["aged_kept"]), int(t3["deaths"]), peak_mb()), flush=True)
            R.rows(kit, p, m, " (national)")
            cphd_nat(kit, p, m)
            if m in (1, 12):
                print(hh_line(hh_table(p), base, m), flush=True)
        else:
            print("month %d (T2.3 off) %.0f s; peak RSS so far %.0f MB" % (m, el, peak_mb()), flush=True)
            if m == 1 and os.path.exists(os.path.join(d, "m01.sha.txt")):
                dg, hs = state.digest_st(p)
                want = state.read_hashes(os.path.join(d, "m01.sha.txt"))
                bad = [n for n in sorted(want) if hs.get(n) != want[n]]
                kit.check(not bad and set(hs) == set(want), "P2 m01 (national, T2.3 off, against the oracle's per-field hashes): digest %s, fields differing %d %s" % (dg[:16], len(bad), bad[:6]))
        if m == 12:
            t2_rows.t2s_dgq(kit, p, yr, label)
            t2_rows.t2s_qk(kit, p, yr, label)
    print("whole run %.0f s, peak RSS %.0f MB" % (time.perf_counter() - t0, peak_mb()), flush=True)
    kit.finish()


if __name__ == "__main__":
    main()
