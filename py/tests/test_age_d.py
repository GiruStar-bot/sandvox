# Start rule (D)'s rows (START_PORT_PLAN §5): D-c conservation, D-s determinism, D-n the national monthly flows, D-sx the
# international net's sex split (the PM's ruling on (5)), D-k cohort counts
import copy
import csv
import inspect
import json
import math
from fractions import Fraction
import os
import sys

from common import Kit, ROOT
from tiers.start import age_d as D

FLOWS = os.path.join(ROOT, "data", "modern", "jpn", "flows_2023_2024")
REL = "data/modern/jpn/cohort_2025-01-01.json"


def rows(name):
    with open(os.path.join(FLOWS, name), encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def in_share(part, total, w, wsum):
    x = Fraction(total) * Fraction(w) / Fraction(wsum)
    return part in (math.floor(x), math.ceil(x))


def near(v, base, num, den):
    x = float(base) * float(num) / float(den)
    return v in (math.floor(x), math.ceil(x))


def main():
    kit = Kit("test_age_d.py")
    res = D.age_to_2025(1)
    led = res["ledger"]
    NA = D.NA

    # D-c
    base = res["base"]["table"]
    btot = sum(base[0]) + sum(base[1])
    kit.check(sum(res["base"]["prefectures"]) == btot,
              "D-c base: the prefectures' 2023-10-01 totals sum to the cohort's %d (R81's sum %d thousand)"
              % (btot, sum(res["base"]["pref_thousand"])))
    first = led[0]["nat"]["before"]
    kit.check(first == base, "D-c base: the birth-month groups sum back to every sex x age of the 2023-10-01 cohort")
    tb = td = ti = 0
    for e in led:
        m = e["month"]
        n = e["nat"]
        f = e["flows"]
        bad = []
        for s in range(2):
            for a in range(NA):
                want = n["before"][s][a] - n["aged_out"][s][a] + n["aged_in"][s][a] - n["deaths"][s][a] + n["mig"][s][a] + n["births"][s][a]
                if want != n["after"][s][a] or n["after"][s][a] < 0:
                    bad.append((s, a, want, n["after"][s][a]))
        kit.check(not bad, "D-c %s national: after = before - aged out + aged in - deaths + net migration + births, 202 cells%s"
                  % (m, "" if not bad else " " + str(bad[:5])))
        moved = sum(n["aged_out"][0]) + sum(n["aged_out"][1])
        moved_in = sum(n["aged_in"][0]) + sum(n["aged_in"][1])
        dsum = sum(n["deaths"][0]) + sum(n["deaths"][1])
        msum = sum(n["mig"][0]) + sum(n["mig"][1])
        bsum = n["births"][0][0] + n["births"][1][0]
        band_ok = True
        for s in range(2):
            for b, (lo, hi) in enumerate(D.DEATH_BANDS):
                if sum(n["deaths"][s][lo:hi + 1]) != n["death_bands"][s][b]:
                    band_ok = False
        kit.check(moved == moved_in and dsum == f["deaths"]["value"] and msum == f["intl"]["value"] and bsum == f["births"]["value"]
                  and band_ok and sum(f["births_sex"]) == bsum,
                  "D-c %s flows: aged %d, deaths %d, net migration %d, births %d (m %d / f %d), each 5-year death band kept"
                  % (m, moved, dsum, msum, bsum, f["births_sex"][0], f["births_sex"][1]))
        p = e["pref"]
        pbad = [i for i in range(47) if p["after"][i] != p["before"][i] + p["births"][i] - p["deaths"][i] + p["internal"][i] + p["intl"][i]]
        nat_after = sum(n["after"][0]) + sum(n["after"][1])
        kit.check(not pbad and sum(p["after"]) == nat_after and sum(p["births"]) == bsum and sum(p["deaths"]) == dsum
                  and sum(p["internal"]) == 0 and sum(p["intl"]) == msum and min(p["after"]) >= 0,
                  "D-c %s prefectures: after = before + births - deaths + internal + international for 47, sum %d = national %d%s"
                  % (m, sum(p["after"]), nat_after, "" if not pbad else " bad " + str(pbad)))
        tb += bsum
        td += dsum
        ti += msum
    t = res["table"]
    ftot = sum(t[0]) + sum(t[1])
    kit.check(btot + tb - td + ti == ftot and sum(res["prefectures"]) == ftot,
              "D-c whole window: base %d + births %d - deaths %d + net migration %d = %d at 2025-01-01, prefectures %d"
              % (btot, tb, td, ti, ftot, sum(res["prefectures"])))
    by_age = [[0] * NA, [0] * NA]
    for c in res["cohorts"]:
        by_age[c["sex"]][c["age_2025"]] += c["count_2025"]
    kit.check(by_age == t, "D-c 2025-01-01: the table is the sum of the cohorts' groups by their age")

    # D-s
    res2 = D.age_to_2025(1)
    sha = D.table_sha(t)
    psha = D.pref_sha(res["prefectures"])
    kit.check(res2["table"] == t and res2["prefectures"] == res["prefectures"],
              "D-s same seed twice: the same table (sha256 %s) and prefectures (sha256 %s)" % (sha, psha))
    kit.check(json.dumps(res2["ledger"], sort_keys=True) == json.dumps(led, sort_keys=True), "D-s same seed twice: the same monthly ledger")
    res3 = D.age_to_2025(2)
    t3 = sum(res3["table"][0]) + sum(res3["table"][1])
    f3 = 0
    for e in res3["ledger"]:
        f = e["flows"]
        f3 += f["births"]["value"] - f["deaths"]["value"] + f["intl"]["value"]
    kit.check(D.table_sha(res3["table"]) != sha and t3 == btot + f3 and sum(res3["prefectures"]) == t3,
              "D-s seed 2: a different table (sha256 %s), total %d = base + its own flows (the F / D levels are keyed roundings)"
              % (D.table_sha(res3["table"]), t3))
    try:
        with open(D.OUT, encoding="utf-8") as fh:
            on_disk = json.load(fh)
    except OSError:
        on_disk = None
    kit.check(on_disk == json.loads(json.dumps(D.output(res), ensure_ascii=False)),
              "D-s %s equals this run's table (seed 1)" % REL)

    # D-n
    vn = {r["month"]: r for r in rows("R96f_vital_national.csv")}
    vf = {(r["kind"], r["target"], r["pref_code"], r["metric"], r["release_type"]): r for r in rows("R96f_vital_fill.csv")}
    mi = rows("R96f_mig_international.csv")
    mp = {(r["month"], r["pref_code"], r["scope"], r["sex"]): r for r in rows("R96f_mig_internal_pref.csv")}
    mf = rows("R96f_mig_fill.csv")
    plan = {"births": {"2023-10": (124173, 122425), "jan_jul": (415305, 392304), "fill": (603638, 634458)},
            "deaths": {"2023-10": (280180, 281430), "jan_jul": (939298, 926657), "fill": (1328678, 1310323)}}
    for kind in ("births", "deaths"):
        met = kind + "_total"
        s23 = {t_: int(vf[("same_month_2023", t_, "00", met, "速報")]["value_2023"]) for t_ in ("2024-11", "2024-12")}
        y = vf[("ytd", "2024-11..2024-12", "00", met, "速報")]
        y24, y23 = int(y["value_2024"]), int(y["value_2023"])
        jj = 0
        for e in led:
            m = e["month"]
            x = e["flows"][kind]
            v = x["value"]
            if m in ("2023-11", "2023-12"):
                want = s23["2024-" + m[5:7]]
                kit.check(x["label"] == "S" and v == want, "D-n %s %s S %d = 速報 %s %d (R96f_vital_fill.csv)" % (m, kind, v, m, want))
            elif m in ("2024-08", "2024-09", "2024-10"):
                want = int(vn[m][met])
                kit.check(x["label"] == "S" and v == want and vn[m]["release_type"] == "速報",
                          "D-n %s %s S %d = 速報 %d (R96f_vital_national.csv)" % (m, kind, v, want))
            elif m == "2023-10":
                num = s23["2024-11"] + s23["2024-12"]
                den = int(vn["2023-11"][met]) + int(vn["2023-12"][met])
                kit.check(x["label"] == "D" and (x["num"], x["den"]) == (num, den) == plan[kind]["2023-10"] and x["base"] == int(vn[m][met])
                          and near(v, x["base"], num, den),
                          "D-n %s %s D %d = 概数 2023-10 %d x 速報 2023-11 + 12 / 概数 2023-11 + 12 = %d / %d"
                          % (m, kind, v, x["base"], num, den))
            elif m <= "2024-07":
                num = y24 - sum(int(vn[k][met]) for k in ("2024-08", "2024-09", "2024-10"))
                den = sum(int(vn["2024-%02d" % i][met]) for i in range(1, 8))
                jj += v
                kit.check(x["label"] == "D" and (x["num"], x["den"]) == (num, den) == plan[kind]["jan_jul"] and x["base"] == int(vn[m][met])
                          and near(v, x["base"], num, den),
                          "D-n %s %s D %d = 概数 %s %d x (速報 Jan-Oct YTD %d - 2024-08 .. 10) %d / 概数 2024-01 .. 07 %d"
                          % (m, kind, v, m, x["base"], y24, num, den))
                if m == "2024-07":
                    kit.check(jj == num, "D-n 2024-01 .. 07 %s: the seven D months sum to the 速報 %d exactly" % (kind, num))
            else:
                b = s23[m]
                kit.check(x["label"] == "F" and (x["num"], x["den"]) == (y24, y23) == plan[kind]["fill"] and x["base"] == b
                          and near(v, b, y24, y23),
                          "D-n %s %s F %d = 速報 2023-%s %d x 速報 YTD 2024-01 .. 10 / 2023-01 .. 10 = %d / %d"
                          % (m, kind, v, m[5:7], b, y24, y23))

    est = {r["month"]: int(r["net"]) for r in mi if r["source"].startswith("人口推計") and r["group"] == "total" and r["sex"] == "総数"}
    juki = {(r["month"], r["sex"]): int(r["net"]) for r in mi if r["source"].startswith("住基") and r["group"] == "total"}
    onum = sum(est.values())
    oden = sum(juki[(m, "総数")] for m in est)
    ytd = [r for r in mf if r["kind"] == "YTD" and "参考表" in r["source"] and r["group"] == "total" and r["sex"] == "総数" and r["metric"] == "net"][0]
    dec = {r["sex"]: int(r["value_2023"]) for r in mf if r["kind"] == "same_month_2023" and "参考表" in r["source"] and r["group"] == "total"
           and r["metric"] == "net"}
    kit.check((onum, oden) == (314613, 278389) and (int(ytd["value_2024"]), int(ytd["value_2023"])) == (348297, 339051) and dec["総数"] == 14397,
              "D-n international ratios: 人口推計 / 住基 net on 2023-10 .. 2024-06 = %d / %d; 住基 Jan-Nov YTD %s / %s; 住基 2023-12 net %d"
              % (onum, oden, ytd["value_2024"], ytd["value_2023"], dec["総数"]))
    for e in led:
        m = e["month"]
        x = e["flows"]["intl"]
        if m in est:
            kit.check(x["label"] == "S" and x["value"] == est[m], "D-n %s intl S %d = 人口推計 入国超過" % (m, x["value"]))
        elif m <= "2024-11":
            b = juki[(m, "総数")]
            kit.check(x["label"] == "F" and x["base"] == b and (x["num"], x["den"]) == (onum, oden) and near(x["value"], b, onum, oden),
                      "D-n %s intl F %d = 住基 net %s %d x %d / %d" % (m, x["value"], m, b, onum, oden))
        else:
            xx = float(dec["総数"]) * float(ytd["value_2024"]) / float(ytd["value_2023"]) * float(onum) / float(oden)
            kit.check(x["label"] == "F" and x["base"] == dec["総数"] and (x["ytd_num"], x["ytd_den"]) == (348297, 339051)
                      and x["value"] in (math.floor(xx), math.ceil(xx)),
                      "D-n %s intl F %d = 住基 2023-12 net %d x YTD %d / %d x %d / %d"
                      % (m, x["value"], dec["総数"], x["ytd_num"], x["ytd_den"], onum, oden))

    # D-sx
    have = [m for m in D.MONTHS if (m, "総数") in juki]
    ytd_sex = {r["sex"]: int(r["value_2023"]) for r in mf if r["kind"] == "YTD" and "参考表" in r["source"] and r["group"] == "total"
               and r["metric"] == "net" and r["sex"] in ("男", "女")}
    fallbacks = []
    expected_fb = []
    swapped_pass = []
    for e in led:
        m = e["month"]
        x = e["flows"]["intl"]
        sh = x["sex_share"]
        end = D.MONTHS.index(min(m, have[-1]))
        win = D.MONTHS[max(0, end - 11):end + 1]
        sm = sum(juki[(w, "男")] for w in win)
        sf = sum(juki[(w, "女")] for w in win)
        st = sum(juki[(w, "総数")] for w in win)
        inside = 0 <= sm <= st and 0 <= sf <= st
        want = [sm, sf] if inside else [ytd_sex["男"], ytd_sex["女"]]
        if sh["fallback"]:
            fallbacks.append(m)
        if not inside:
            expected_fb.append(m)
        v, (pm, pf) = x["value"], x["sex"]
        ws = want[0] + want[1]
        ratio = in_share(pm, v, want[0], ws) and in_share(pf, v, want[1], ws)
        if v != 0 and in_share(pf, v, want[0], ws) and in_share(pm, v, want[1], ws):
            swapped_pass.append(m)
        same_sign = all(p_ * v >= 0 for p_ in (pm, pf))
        kit.check(pm + pf == v and sh["sums"] == want and sh["fallback"] == (not inside) and same_sign and ratio
                  and sh["window"] == [win[0], win[-1], len(win)],
                  "D-sx %s net %d = male %d + female %d, each floor or ceil of net x share; shares %.6f / %.6f (住基 net %d / %d over "
                  "%s .. %s, %d months%s)"
                  % (m, v, pm, pf, float(want[0]) / float(ws), float(want[1]) / float(ws), want[0], want[1],
                     win[0], win[-1], len(win), "; FALLBACK to 2023 Jan-Nov YTD" if not inside else ""))
    kit.check(not swapped_pass, "D-sx must-fail: the male and female parts swapped fail the share check in every month (passing: %s)"
              % (", ".join(swapped_pass) if swapped_pass else "none"))
    kit.check(fallbacks == expected_fb, "D-sx fallback months: %s, as the trailing shares outside [0, 1] put them (%s)"
              % (", ".join(fallbacks) if fallbacks else "none", ", ".join(expected_fb) if expected_fb else "none"))

    # D-sx (i), synthetic: a 2023-10 sex net that puts the trailing share outside [0, 1] takes 2023's Jan-Nov YTD sums
    I = D.inputs()
    I["mi"] = copy.deepcopy(I["mi"])
    oct_tot = juki[("2023-10", "総数")]
    for r in I["mi"]:
        if r["month"] == "2023-10" and r["source"].startswith("住基") and r["group"] == "total":
            r["net"] = str({"男": -500, "女": oct_tot + 500, "総数": oct_tot}[r["sex"]])
    sh = D._sex_shares(I, "2023-10")
    parts = D._split(est["2023-10"], [float(sh["sums"][0]), float(sh["sums"][1])], 1, "d_intl_sex", 0)
    ys = ytd_sex["男"] + ytd_sex["女"]
    kit.check(sh["fallback"] and sh["sums"] == [ytd_sex["男"], ytd_sex["女"]] == [200121, 138930]
              and sum(parts) == est["2023-10"] and in_share(parts[0], est["2023-10"], ytd_sex["男"], ys)
              and in_share(parts[1], est["2023-10"], ytd_sex["女"], ys),
              "D-sx (i) synthetic 2023-10 住基 net male -500 / female %d: fallback %s, sums %d / %d = R96f 2023 Jan-Nov YTD by sex; "
              "%d = %d + %d" % (oct_tot + 500, sh["fallback"], sh["sums"][0], sh["sums"][1], est["2023-10"], parts[0], parts[1]))

    # D-pf (ii), synthetic: a prefecture with a negative 2023 net from abroad gets 0, and the rest share the net exactly
    ab = {}
    for row in rows("R100_juki_international_by_pref.csv"):
        if row["scope"] == "総数" and row["sex"] == "総数" and row["pref_code"] != "-":
            ab[(row["pref_code"][:2], row["flow"])] = int(row["count"])
    real_net = [ab[(c, "国外からの転入")] - ab[(c, "国外への転出")] for c in D.PREFS]
    neg = list(real_net)
    k32 = D.PREFS.index("32")
    neg[k32] = -2000
    total = est["2023-10"]

    def case_ii(fn):
        w, floored = fn(neg)
        parts = D._split(total, w, 1, "d_intl_pref", 0)
        want = [max(0, x) for x in neg]
        wsum = sum(want)
        others = [Fraction(want[i], wsum) for i in range(47) if i != k32]
        ok = (floored == ["32"] and parts[k32] == 0 and w == [float(x) for x in want] and sum(others) == 1 and sum(parts) == total
              and all(in_share(parts[i], total, want[i], wsum) for i in range(47)))
        return ok, parts[k32], sum(parts)

    ok, p32, ps = case_ii(D._intl_pref_weights)
    kit.check(ok, "D-pf (ii) synthetic Shimane net -2000: floored, gets %d; the other 46 shares sum to 1 exactly; %d split, parts sum %d"
              % (p32, total, ps))
    src_fn = inspect.getsource(D._intl_pref_weights)
    n_sub = src_fn.count("max(0, x)")
    ns = dict(vars(D))
    exec(src_fn.replace("max(0, x)", "abs(x)"), ns)
    mok, mp32, mps = case_ii(ns["_intl_pref_weights"])
    kit.check(n_sub == 1 and not mok,
              "D-pf must-fail: _intl_pref_weights with max(0, x) replaced by abs(x) (%d site) fails (ii): Shimane gets %d, parts sum %d"
              % (n_sub, mp32, mps))

    for e in led:
        m = e["month"]
        x = e["flows"]["internal"]
        if m <= "2024-11":
            want = [int(mp[(m, c, "総数", "総数")]["net"]) for c in D.PREFS]
            kit.check(x["label"] == "S" and x["pref"] == want and sum(want) == 0, "D-n %s internal S: the 47 prefecture nets = 住基 表1, national 0" % m)
        else:
            r = x["group_ratio"]
            kit.check(x["label"] == "F" and sum(x["pref"]) == 0,
                      "D-n %s internal F: national 0; 2023-12 in / out x Jan-Nov YTD, in-movers 日本人 %d / %d, 外国人 %d / %d"
                      % (m, r["日本人"][0], r["日本人"][1], r["外国人"][0], r["外国人"][1]))

    with open(os.path.join(ROOT, "data", "modern", "SOURCES_D477.csv"), encoding="utf-8", newline="") as fh:
        src = {(r["file"], r["path"]): r for r in csv.DictReader(fh)}
    for e in led:
        m = e["month"]
        for flow, key in (("births", "births"), ("deaths", "deaths"), ("intl", "intl_net")):
            x = e["flows"][flow]
            if x["label"] == "S":
                continue
            r = src.get((REL, ".flows.%s.%s" % (m, key)))
            kit.check(r is not None and r["value"] == str(x["value"]) and r["label"] == x["label"] and r["published"] <= "2024-12-31",
                      "D-n %s %s %s %d: SOURCES_D477 row %s" % (m, key, x["label"], x["value"], "present, published " + r["published"] if r else "MISSING"))
    r = src.get((REL, ".flows.*.intl_net (prefectures)"))
    out_src = D.output(res)["source"]
    kit.check(r is not None and r["label"] == "D (AMENDED)" and "R100" in r["source"] and "provisional" not in r["label"]
              and "R100, research-notes a694abc5" in out_src and "provisional" not in out_src,
              "D-n the international net's prefecture split: SOURCES_D477 label %s (R100), the JSON's source names R100"
              % (r["label"] if r else "MISSING"))
    ab = {}
    for row in rows("R100_juki_international_by_pref.csv"):
        if row["scope"] == "総数" and row["sex"] == "総数" and row["pref_code"] != "-":
            ab[(row["pref_code"][:2], row["flow"])] = int(row["count"])
    net = [ab[(c, "国外からの転入")] - ab[(c, "国外への転出")] for c in D.PREFS]
    w = [max(0, x) for x in net]
    floored = [c for c, x in zip(D.PREFS, net) if x < 0]
    for e in led:
        m = e["month"]
        v = e["flows"]["intl"]["value"]
        got = e["pref"]["intl"]
        ok = sum(got) == v and all(abs(float(got[i]) - float(v) * float(w[i]) / float(sum(w))) < 1.0 for i in range(47))
        kit.check(ok, "D-n %s intl prefectures: %d split by R100's 2023 net from abroad (sum %d; Tokyo %d, floored %s)"
                  % (m, v, sum(w), got[12], ",".join(floored) if floored else "none"))
    for name in sorted(os.listdir(FLOWS)):
        r = src.get(("data/modern/jpn/flows_2023_2024/" + name, "(whole file)"))
        kit.check(r is not None and r["published"] <= "2024-12-31", "D-n %s: SOURCES_D477 file row %s" % (name, r["published"] if r else "MISSING"))

    # D-k
    lines = {}
    for c in res["cohorts"]:
        k = (c["sex"], c["open_top"], c["birth_year"])
        lines.setdefault(k, []).append(c)
    for k in sorted(lines):
        s, top, by = k
        cs = sorted(lines[k], key=lambda c: c["birth_month"])
        resid = [c["count_2025"] - c["count_base"] - c["births"] + c["deaths"] - c["mig"] for c in cs]
        want = D.TOP if top else min(D.TOP, 2024 - by)
        ages = [c["age_2025"] for c in cs]
        kit.check(all(r == 0 for r in resid) and all(a == want for a in ages),
                  "D-k %s born %s months %s: age at 2025-01-01 %s (expected %d); 2023-10-01 %d + births %d - deaths %d + net %d = %d; residual %s"
                  % (D.SEXES[s], ("<=%d (100+ at the base)" % by) if top else str(by), ",".join(str(c["birth_month"]) for c in cs),
                     ",".join(str(a) for a in ages), want, sum(c["count_base"] for c in cs), sum(c["births"] for c in cs),
                     sum(c["deaths"] for c in cs), sum(c["mig"] for c in cs), sum(c["count_2025"] for c in cs), max(abs(r) for r in resid)))
    kit.finish()


if __name__ == "__main__":
    main()
