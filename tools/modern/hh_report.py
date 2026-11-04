"""The households' behaviour checks (ISS_CHECKS.md HB1..HB11) read from one behaviour run's hh_run.jsonl. Every target and tolerance
is the spec's checks block (data/modern/people/jpn_households_2024.json "checks", built from R62/R63 by build_households_spec.py),
the one source; nothing is typed here. One line per check, each with the run id and its standard error: a weighted share's on the
Kish effective n of its own domain (the run's "neff", (sum w)^2 / sum w^2 over the domain's persons), a weighted event rate's on the
effective n of its events' weights, an unweighted rate's or mean's on its count. The year-10 checks need a run of 10 years: a shorter
file is refused unless --smoke is given, and then every line says SMOKE (not evidence).
  python3 -I tools/modern/hh_report.py <hh_run.jsonl> <spec json> [--smoke]"""
import json
import math
import sys


def main():
    rows = [json.loads(x) for x in open(sys.argv[1], encoding="utf-8") if x.strip()]
    spec = json.load(open(sys.argv[2], encoding="utf-8"))
    chk = spec["checks"]["value"]
    last = rows[-1]
    smoke = "--smoke" in sys.argv[3:]
    if last["run_year"] < 10 and not smoke:
        sys.exit("REFUSED: the run ends at year %d; HB1-HB10 are read at year 10 (HB5's cohort under 25 at month 0 is 30-34 only from year 10). Pass --smoke to read it as a smoke test" % last["run_year"])
    run = last.get("run", "?") + (" SMOKE" if smoke else "")
    flows = [r for r in rows if r["run_year"] > 0]
    late = flows[-5:]
    span = "years %d-%d" % (late[0]["run_year"], late[-1]["run_year"])
    kl = last.get("kish", {})
    ne = last.get("neff")
    if ne is None:
        sys.exit("REFUSED: the run has no per-domain effective n (written since hh_run.gd's V099 item 1)")
    out = []

    def line(cid, ok, text):
        out.append("%s %-5s %-14s %s" % (run, cid, ok, text))

    def se(p, neff):
        return math.sqrt(max(p * (1 - p), 1e-9) / max(1.0, neff))

    def kish(ws):
        return sum(ws) ** 2 / max(1e-9, sum(w * w for w in ws))

    names = ["one_person", "couple_only", "couple_children", "single_parent", "other"]
    ts = chk["type_shares"]
    worst = max(abs(last["types"][k] - ts["value"][nm]) for k, nm in enumerate(names))
    line("HB1", "PASS" if worst <= ts["tolerance"] else "FAIL", "types at year %d: %s against %s (+-%g pt; worst %.1f pt; SE %s on %d effective of %d private households)" % (last["run_year"], " / ".join("%.3f" % x for x in last["types"]), " / ".join("%.3f" % ts["value"][nm] for nm in names), 100 * ts["tolerance"], 100 * worst, " / ".join("%.3f" % se(x, kl.get("households_eff", 1.0)) for x in last["types"]), kl.get("households_eff", 0), kl.get("households", 0)))
    al = spec["alone_share_by_band"]["value"]
    idx = (0, 1, 2, 5, 6, 7)
    want = [al["men"][i] for i in idx] + [al["women"][i] for i in idx]
    got = last["alone"][0] + last["alone"][1]
    ses = [se(g, n) for g, n in zip(got, ne["alone"])]
    worst_b = max(abs(g - w) for g, w in zip(got, want))
    tol = chk["alone_cells"]["tolerance"]
    line("HB1b", "PASS" if worst_b <= tol else "FAIL", "alone cells at year %d: worst %.1f pt (+-%g pt); model(published, SE) %s" % (last["run_year"], 100 * worst_b, 100 * tol, " ".join("%.3f(%.3f,%.3f)" % (g, w, e) for g, w, e in zip(got, want, ses))))
    o = last["old_65"]
    a65 = chk["alive_65plus"]
    tgt = [a65["alone"], a65["couple_only"], a65["with_child"]]
    line("HB1c", "PASS" if all(abs(a - b) <= a65["tolerance"] for a, b in zip(o, tgt)) else "FAIL", "65+ alone / couple / with a child at year %d %s against %s (+-%g pt; SE %s)" % (last["run_year"], " / ".join("%.3f" % x for x in o), " / ".join("%.3f" % x for x in tgt), 100 * a65["tolerance"], " / ".join("%.3f" % se(x, ne["old_65"]) for x in o)))
    line("HB2", "SANITY", "mean size %.3f against %.2f (the monthly size margin holds it: an identity)" % (last["mean_size"], chk["mean_size"]["value"]))
    tfr = []
    bw = [0.0] * 7
    nb = 0.0
    for r in late:
        tfr.append(sum(5.0 * r["births_by_mother_age"][b] / max(1.0, r["women_by_band"][b]) for b in range(7)))
        nb += sum(r["births_by_mother_age"])
        for b in range(7):
            bw[b] += r["births_weighted"][b]
    tb = sum(bw) or 1.0
    bands = ["15-19", "20-24", "25-29", "30-34", "35-39", "40-44", "45-49"]
    off = chk["births_by_mother_age"]["value"]
    worst_age = max(abs(bw[b] / tb - off[bands[b]]) for b in range(7))
    t5 = sum(tfr) / len(tfr)
    ct = chk["tfr"]
    line("HB3", "PASS" if abs(t5 - ct["value"]) <= ct["tolerance"] and worst_age <= chk["births_by_mother_age"]["tolerance"] else "FAIL", "TFR %s %.2f (%.2f +- %.2f; SE %.2f on %d births, unweighted); births by mother's age worst %.1f pt (+-%g): %s" % (span, t5, ct["value"], ct["tolerance"], t5 / math.sqrt(max(1.0, nb)), nb, 100 * worst_age, 100 * chk["births_by_mother_age"]["tolerance"], " ".join("%.3f" % (x / tb) for x in bw)))
    deaths, expo = {}, {}
    for r in flows:
        for k, d in r["deaths"].items():
            deaths[k] = deaths.get(k, 0.0) + d
        for k, e in r["exposure"].items():
            expo[k] = expo.get(k, 0.0) + e
    def life(s, bump=None, h=0.0):
        lx, e = 1.0, 0.0
        for b in range(21):
            k = "%d%s" % (b, s)
            mx = (deaths.get(k, 0.0) + (h if b == bump else 0.0)) / max(1.0, expo.get(k, 0.0))
            if b == 18:
                # Why not close at 100+: a few persons there make its rate, and lx / mx, noise; 90+ is one open band.
                dt = sum(deaths.get("%d%s" % (c, s), 0.0) for c in range(18, 21)) + (h if bump == 18 else 0.0)
                xt = sum(expo.get("%d%s" % (c, s), 0.0) for c in range(18, 21))
                e = e + lx * xt / dt if dt > 0 else float("nan")
                break
            q = min(1.0, 5 * mx / (1 + 2.5 * mx))
            e += 2.5 * (lx + lx * (1 - q))
            lx *= 1 - q
        return e

    e0, e0se = {}, {}
    for s in ["M", "F"]:
        e0[s] = life(s)
        # the delta method: each band's deaths Poisson (var = deaths, unweighted), the 90+ band one; e0's change per death numerically
        var = 0.0
        for b in range(19):
            dd = deaths.get("%d%s" % (b, s), 0.0) if b < 18 else sum(deaths.get("%d%s" % (c, s), 0.0) for c in range(18, 21))
            if dd > 0:
                var += ((life(s, b, 1.0) - e0[s]) ** 2) * dd
        e0se[s] = math.sqrt(var)
    ce = chk["e0"]
    prev = {r["run_year"]: r for r in rows}
    cm = chk["marital_fertility"]
    cells, ok3b = [], True
    for b in cm["bands"]:
        lo = int(b.split("-")[0])
        bi = (lo - 15) // 5
        bw_b = sum(r["births_weighted"][bi] for r in late)
        bn_b = sum(r["births_by_mother_age"][bi] for r in late)
        wv_b = sum(0.5 * (prev[r["run_year"] - 1]["married_wives"].get(str(lo), 0.0) + r["married_wives"].get(str(lo), 0.0)) for r in late)
        m = 1000.0 * bw_b / wv_b if wv_b > 0 else float("nan")
        ref = cm["per_1000"][cm["bands"].index(b)]
        ok3b = ok3b and m == m and ref / cm["factor"] <= m <= ref * cm["factor"]
        cells.append("%s %.1f(%.1f, SE %.1f)" % (b, m, ref, m / math.sqrt(max(1.0, bn_b))))
    line("HB3b", "PASS" if ok3b else "FAIL", "births per 1,000 married women %s, within a factor of %g of %d: %s" % (span, cm["factor"], cm["year"], " ".join(cells)))
    cf2 = chk["first_marriage_rate"]
    cells, ok5c = [], True
    for s5i, sx in ((0, "men"), (1, "women")):
        for k, b in enumerate(cf2["bands"]):
            lo = int(b.split("-")[0])
            key = str(lo // 5)
            fw = sum(r.get("first_partnering_w", [{}, {}])[s5i].get(key, 0.0) for r in late)
            fn = sum(1 for r in late for a5 in r["first_partnering_ages"][s5i] if lo <= a5 <= lo + 4)
            nw = sum(0.5 * (prev[r["run_year"] - 1].get("never_married_w", [{}, {}])[s5i].get(key, 0.0) + r.get("never_married_w", [{}, {}])[s5i].get(key, 0.0)) for r in late)
            m = 1000.0 * fw / nw if nw > 0 else float("nan")
            ref = cf2[sx][k]
            ok5c = ok5c and m == m and ref / cf2["factor"] <= m <= ref * cf2["factor"]
            cells.append("%s %s %.1f(%.1f, SE %.1f)" % (sx, b, m, ref, m / math.sqrt(max(1.0, fn))))
    line("HB5c", "PASS" if ok5c else "FAIL", "first partnerings per 1,000 never-married %s, within a factor of %g of %d: %s" % (span, cf2["factor"], cf2["year"], " ".join(cells)))
    cv = chk["movers_per_1000"]
    cells, ok12 = [], True
    for b, ref in zip(cv["bands"], cv["per_1000"]):
        key = str(int(b.split("-")[0]) // 5)
        mw = sum(r.get("movers_by_band", {}).get(key, [0, 0, 0, 0])[0] for r in late)
        pw = sum(r.get("movers_by_band", {}).get(key, [0, 0, 0, 0])[1] for r in late)
        mn = sum(r.get("movers_by_band", {}).get(key, [0, 0, 0, 0])[2] for r in late)
        m = 1000.0 * mw / pw if pw > 0 else float("nan")
        ok12 = ok12 and m == m and ref / cv["factor"] <= m <= ref * cv["factor"]
        cells.append("%s %.1f(%.1f, SE %.1f)" % (b, m, ref, m / math.sqrt(max(1.0, mn))))
    line("HB12", "PASS" if ok12 else "FAIL", "inter-prefecture movers per 1,000 %s, within a factor of %g of %d: %s" % (span, cv["factor"], cv["year"], " ".join(cells)))
    line("HB4", "SANITY", "e0 years 1-%d %.2f / %.2f against %.2f / %.2f (+-%g year; SE %.2f / %.2f, the deaths Poisson; the hazard is the table: a sanity test)" % (last["run_year"], e0["M"], e0["F"], ce["men"], ce["women"], ce["tolerance"], e0se["M"], e0se["F"]))
    nm = last["never_married"]
    cn = chk["never_married_30_34"]
    nse = [se(nm[s][3], ne["never_married_30_34"][s]) for s in (0, 1)]
    line("HB5", "PASS" if abs(nm[0][3] - cn["men"]) <= cn["tolerance"] and abs(nm[1][3] - cn["women"]) <= cn["tolerance"] else "FAIL", "never married 30-34 at year %d %.3f / %.3f against %.3f / %.3f (+-%g pt; SE %.3f / %.3f; the cohort under 25 at month 0)" % (last["run_year"], nm[0][3], nm[1][3], cn["men"], cn["women"], 100 * cn["tolerance"], nse[0], nse[1]))
    fa = [[], []]
    for r in late:
        for s2 in (0, 1):
            fa[s2] += r["first_partnering_ages"][s2]
    fm = [sum(x) / max(1, len(x)) for x in fa]
    fsd = [math.sqrt(sum((v - m) ** 2 for v in x) / max(1, len(x) - 1)) for x, m in zip(fa, fm)]
    cf = chk["first_marriage_age"]
    line("HB5a", "PASS" if abs(fm[0] - cf["men"]) <= cf["tolerance"] and abs(fm[1] - cf["women"]) <= cf["tolerance"] else "FAIL", "first-partnering ages %s %.1f / %.1f against %.1f / %.1f (+-%g; SE %.2f / %.2f on %d / %d, unweighted)" % (span, fm[0], fm[1], cf["men"], cf["women"], cf["tolerance"], fsd[0] / math.sqrt(max(1, len(fa[0]))), fsd[1] / math.sqrt(max(1, len(fa[1]))), len(fa[0]), len(fa[1])))
    cr = chk["remarriage_share"]
    fr = [[0.0, 0.0], [0.0, 0.0]]
    for r in late:
        for s5 in (0, 1):
            for k5 in (0, 1):
                fr[s5][k5] += r.get("partnered_first_re", [[0, 0], [0, 0]])[s5][k5]
    rs = [fr[s5][1] / max(1e-9, fr[s5][0] + fr[s5][1]) for s5 in (0, 1)]
    line("HB5d", "PASS" if abs(rs[0] - cr["husbands"]) <= cr["tolerance"] and abs(rs[1] - cr["wives"]) <= cr["tolerance"] else "FAIL", "remarriage share of partnerings %s %.3f / %.3f against %.3f / %.3f (+-%g pt; weighted)" % (span, rs[0], rs[1], cr["husbands"], cr["wives"], 100 * cr["tolerance"]))
    line("HB5b", "NOT MEASURABLE", "never married at 50 within ten years (the start seeded that cohort)")
    lh = chk["ever_left"]
    el = last["ever_left"]
    e27 = last.get("ever_left_25_27")
    if e27 is None:
        line("HB6", "NOT MEASURABLE", "the run has no 25-27 band (written since hh_run.gd 45c6ba16)")
    else:
        got6 = [[el[s][0], el[s][1], e27[s]] for s in (0, 1)]
        want6 = [[lh[k][s] for k in ("18-19", "20-24", "25-29")] for s in (0, 1)]
        se6 = [[se(got6[s][b], ne["ever_left"][s][b]) for b in range(3)] for s in (0, 1)]
        ok6 = all(abs(got6[s][b] - want6[s][b]) <= lh["tolerance"] for s in (0, 1) for b in range(3))
        line("HB6", "PASS" if ok6 else "FAIL", "ever left 18-19 / 20-24 / 25-27 at year %d (the cohort under 18 at month 0; 25-27 read against 25-29) men %s women %s against %s / %s (+-%g pt; SE men %s women %s)" % (last["run_year"], " ".join("%.2f" % x for x in got6[0]), " ".join("%.2f" % x for x in got6[1]), " ".join("%.2f" % x for x in want6[0]), " ".join("%.2f" % x for x in want6[1]), 100 * lh["tolerance"], " ".join("%.3f" % x for x in se6[0]), " ".join("%.3f" % x for x in se6[1])))
        uw = last.get("unmarried_with_parent", {})
        cu = chk["unmarried_with_parents_18_34"]
        line("HB6b", "NOTED", "unmarried 18-27 living with a parent at year %d %.3f / %.3f (18-34 %.3f / %.3f) against JNFS16's 18-34 %.3f / %.3f (no tolerance: the run's 18-27 is not the published band)" % (last["run_year"], uw["men"][0], uw["women"][0], uw["men"][1], uw["women"][1], cu["men"], cu["women"]))
    g2 = last.get("grade2_by_decade")
    co = chk["outpatient"]
    if g2 is None:
        line("HB8", "NOT MEASURABLE", "the run has no grade 2+ by decade (written since hh_run.gd 45c6ba16)")
    else:
        outp = [co["30s"], co["40s"], co["50s"]]
        ratio = [g2[3 + k] / outp[k] for k in range(3)]
        se8 = [se(g2[3 + k], ne["grade2"][k]) / outp[k] for k in range(3)]
        # Why not PASS/FAIL: grade 2+ is set from the symptom rate, and 通院者率 is a different measure (the PM, 2026-10-30 03:40)
        line("HB8", "NO CHECK", "no independent health check yet; for reference, grade 2+ at 30s / 40s / 50s at year %d %s against 通院者率 %s: ratios %s (+-%g; SE of the ratio %s); HLE an identity (grade 4 is R64's rate)" % (last["run_year"], " / ".join("%.3f" % g2[3 + k] for k in range(3)), " / ".join("%.3f" % x for x in outp), " / ".join("%.2f" % x for x in ratio), co["ratio_tolerance"], " / ".join("%.3f" % x for x in se8)))
    dw, dn, dur, dws = 0.0, 0, [0.0, 0.0, 0.0], []
    for r in late:
        for d in r["divorces"]:
            dw += d[1]
            dn += 1
            dws.append(d[1])
            dur[0] += d[1] if d[0] < 5 else 0.0
            dur[1] += d[1] if d[0] >= 20 else 0.0
            dur[2] += d[1]
    pop = sum(r["population"] for r in late) / len(late)
    crude = 1000.0 * dw / len(late) / pop
    cc = chk["divorce_crude"]
    line("HB9a", "PASS" if abs(crude - cc["value"]) <= cc["tolerance"] else "FAIL", "divorces %.2f per 1,000 a year, %s (%.2f +- %.2f; SE %.2f on %d divorces, effective %.0f)" % (crude, span, cc["value"], cc["tolerance"], crude / math.sqrt(max(1.0, kish(dws))), dn, kish(dws)))
    s5, s20 = dur[0] / max(1e-9, dur[2]), dur[1] / max(1e-9, dur[2])
    cd = chk["divorce_duration"]
    line("HB9b", "PASS" if abs(s5 - cd["under_5"]) <= cd["tolerance"] and abs(s20 - cd["20_plus"]) <= cd["tolerance"] else "FAIL", "durations %s <5 y %.3f (%.3f), 20+ y %.3f (%.3f) (+-%g pt; SE %.3f / %.3f)" % (span, s5, cd["under_5"], s20, cd["20_plus"], 100 * cd["tolerance"], se(s5, kish(dws)), se(s20, kish(dws))))
    cw = chk["divorce_rate_wife"]
    dv, wv, dc = {}, {}, {}
    for r in flows:
        for d in r["divorces"]:
            if len(d) > 2 and d[2] >= 0:
                b = "<=19" if d[2] < 20 else "%d-%d" % (d[2] // 5 * 5, d[2] // 5 * 5 + 4)
                dv[b] = dv.get(b, 0.0) + d[1]
                dc[b] = dc.get(b, []) + [d[1]]
        for k, w in r.get("married_wives", {}).items():
            b = "<=19" if int(k) < 20 else "%d-%d" % (int(k), int(k) + 4)
            wv[b] = wv.get(b, 0.0) + w
    i0, i1 = cw["bands"].index(cw["from"]), cw["bands"].index(cw["to"])
    cells, ok9c = [], True
    for b, ref in list(zip(cw["bands"], cw["per_1000"]))[i0:i1 + 1]:
        m = 1000.0 * dv.get(b, 0.0) / wv[b] if wv.get(b, 0.0) > 0 else float("nan")
        ok9c = ok9c and m == m and ref / cw["factor"] <= m <= ref * cw["factor"]
        cells.append("%s %.1f(%.1f, SE %.1f)" % (b, m, ref, m / math.sqrt(max(1.0, kish(dc.get(b, []))))))
    line("HB9c", "PASS" if ok9c else "FAIL", "per 1,000 married wives, years 1-%d pooled, %s..%s within a factor of %g: %s" % (last["run_year"], cw["from"], cw["to"], cw["factor"], " ".join(cells)))
    line("HB10", "SANITY", "women 85+ in an institution at year %d %.3f (the start set %.3f)" % (last["run_year"], last["inst_women_85"], chk["institution_women_85"]["value"]))
    k0 = rows[0].get("kish", {})
    line("HB11", "REPORT", "effective households within prefectures %s -> %s; national %s -> %s; persons_eff %s -> %s of %d (each share's SE uses its own domain's effective n)" % (round(k0.get("households_eff_within", 0)), round(kl.get("households_eff_within", 0)), round(k0.get("households_eff", 0)), round(kl.get("households_eff", 0)), round(k0.get("persons_eff", 0)), round(kl.get("persons_eff", 0)), last["persons"]))
    print("\n".join(out))


if __name__ == "__main__":
    main()
