# Start rule (D) (START_PORT_PLAN §5, AMENDED by the PM's ruling on M040): the 人口推計 2023-10-01 cohort aged to 2025-01-01 on
# birth-month groups, in integers, with the in-window monthly flows of R96f and the 2023 tables of R96g
import csv
import hashlib
import json
import math
import os
import struct
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))

from core import detmath, keyed
from core.prims import systematic
from tiers.start.load import load_json

# Why not load.ROOT: START_DATA_ROOT points step (a) at the frozen oracle's data, and rule (D) reads this branch's in-window inputs
ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
FLOWS = os.path.join(ROOT, "data", "modern", "jpn", "flows_2023_2024")
OUT = os.path.join(ROOT, "data", "modern", "jpn", "cohort_2025-01-01.json")
WINDOW_END = "2024-12-31"

MONTHS = ["2023-10", "2023-11", "2023-12"] + ["2024-%02d" % k for k in range(1, 13)]
TOP = 100
NA = TOP + 1
SEXES = ("male", "female")
PREFS = ["%02d" % k for k in range(1, 48)]
DEATH_BANDS = [(5 * b, 5 * b + 4) for b in range(20)] + [(TOP, TOP)]
DEATH_LABELS = ["%d～%d歳" % (lo, hi) for lo, hi in DEATH_BANDS[:20]] + ["100歳以上"]
MOVER_BANDS = [(5 * b, 5 * b + 4) for b in range(18)] + [(90, TOP)]
MOVER_LABELS = ["%d歳～%d歳" % (lo, hi) for lo, hi in MOVER_BANDS[:18]] + ["90歳以上"]
R96F = "R96f (research-notes 33f578dc)"
R96G = "R96g (research-notes 81317116)"


def _cal(m):
    return int(m[5:7])


def _rows(name):
    with open(os.path.join(FLOWS, name), encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        for k in ("published", "published_2023", "published_2024"):
            for d in (r.get(k) or "").split(";"):
                if d[:2] == "20" and d > WINDOW_END:
                    raise ValueError("%s: %s published %s, after the window" % (name, k, d))
    return rows


def _round1(x, seed_v, tag, key):
    # Why not gd_round: half away from zero moves every .5 the same way, and a keyed draw keeps the expectation at x
    f = int(math.floor(x))
    return f + (1 if keyed.u(seed_v, tag, key, 0, 0) < x - float(f) else 0)


def _split(total, w, seed_v, tag, key):
    # Why not systematic(w, total) directly: systematic places only the fractional parts' residue, so v must already sum to total
    n = len(w)
    if total == 0:
        return [0] * n
    sg = 1 if total > 0 else -1
    t = total * sg
    sw = 0.0
    for x in w:
        if x < 0.0:
            raise ValueError("%s %d: a negative weight" % (tag, key))
        sw += x
    if not sw > 0.0:
        raise ValueError("%s %d: %d to split over zero weight" % (tag, key, total))
    v = [float(t) * x / sw for x in w]
    out = systematic(v, t, seed_v, tag, key)
    return [sg * o for o in out]


def _src(text):
    for tag in ("表1", "参考表", "人口推計", "出入国"):
        if tag in text:
            return tag
    raise ValueError("R96f_mig_fill.csv: an unknown source " + text)


def _pick_year(years, y):
    best = 0
    bd = 1 << 30
    for i in range(len(years)):
        d = abs(int(years[i]) - y)
        if d < bd:
            bd = d
            best = i
    return best


def inputs():
    I = {}
    st = load_json(os.path.join(ROOT, "data", "modern", "jpn", "status_2024.json"))["cohort"]
    if st["date"] != "2023-10-01" or len(st["ages"]) != NA:
        raise ValueError("status_2024.json .cohort is not the 2023-10-01 table of 101 ages")
    base = [[0] * NA, [0] * NA]
    for row in st["ages"]:
        a = int(row["age"])
        for s, key in enumerate(SEXES):
            x = row[key] * st["unit_persons"]
            if x != math.floor(x):
                raise ValueError("cohort age %d %s is not whole persons" % (a, key))
            base[s][a] = int(x)
    I["base"] = base
    pj = load_json(os.path.join(ROOT, "data", "modern", "polity", "jpn_prefectures.json"))["prefectures"]
    I["pref_names"] = [pj[c]["name"] for c in PREFS]
    I["pref_thousand"] = [int(pj[c]["pop_thousand"]) for c in PREFS]
    tiers = load_json(os.path.join(ROOT, "data", "modern", "people", "jpn_tiers_2024.json"))
    I["bm"] = tiers["birth_month_shares"]["value"]
    hh = load_json(os.path.join(ROOT, "data", "modern", "people", "jpn_households_2024.json"))
    qx = hh["life_course"]["value"]["qx_2022"]
    if "令和5年簡易生命表" not in qx["label"]:
        raise ValueError("life_course.qx_2022 is not the 令和5年 table")
    I["q"] = [qx["value"]["men"], qx["value"]["women"]]

    I["vn"] = {r["month"]: r for r in _rows("R96f_vital_national.csv")}
    vp = {}
    for r in _rows("R96f_vital_prefecture.csv"):
        vp[(r["month"], r["pref_code"])] = r
    I["vp"] = vp
    vf = {}
    for r in _rows("R96f_vital_fill.csv"):
        vf[(r["kind"], r["target"], r["pref_code"], r["metric"], r["release_type"])] = r
    I["vf"] = vf
    I["mi"] = _rows("R96f_mig_international.csv")
    mp = {}
    for r in _rows("R96f_mig_internal_pref.csv"):
        mp[(r["month"], r["pref_code"], r["scope"], r["sex"])] = r
    I["mp"] = mp
    mf = {}
    for r in _rows("R96f_mig_fill.csv"):
        mf[(r["kind"], _src(r["source"]), r["area_code"], r["group"], r["sex"], r["metric"])] = r
    I["mf"] = mf
    bd = {}
    for r in _rows("R96g_births_deaths_pref_sex_2023.csv"):
        bd[(r["pref_code"], r["sex"])] = r
    I["bd"] = bd
    da = {}
    for r in _rows("R96g_deaths_age_sex_2023.csv"):
        da[(r["geo"], r["sex"], r["age_group"])] = int(r["deaths"])
    I["da"] = da
    mv = {}
    for r in _rows("R96g_movers_age_sex_2023.csv"):
        if r["geo"] == "00" and r["flow"] == "in" and r["scope"].startswith("総数"):
            mv[(r["sex"], r["age_group"])] = int(r["persons"])
    I["mv"] = mv
    ab = {}
    for r in _rows("R100_juki_international_by_pref.csv"):
        if r["scope"] == "総数" and r["sex"] == "総数" and r["pref_code"] != "-":
            ab[(r["pref_code"][:2], r["flow"])] = int(r["count"])
    I["abroad_net"] = [ab[(c, "国外からの転入")] - ab[(c, "国外への転出")] for c in PREFS]
    return I


def _vital_national(I, seed_v, kind, k):
    vn = I["vn"]
    vf = I["vf"]
    met = kind + "_total"

    def g(m):
        return int(vn[m][met])

    def sok23(target):
        r = vf[("same_month_2023", target, "00", met, "速報")]
        return int(r["value_2023"]), r["published_2023"]

    s11, p11 = sok23("2024-11")
    s12, p12 = sok23("2024-12")
    ytd = vf[("ytd", "2024-11..2024-12", "00", met, "速報")]
    y24 = int(ytd["value_2024"])
    y23 = int(ytd["value_2023"])
    out = {}
    num = s11 + s12
    den = g("2023-11") + g("2023-12")
    out["2023-10"] = {"value": _round1(float(g("2023-10")) * float(num) / float(den), seed_v, "d_vital_round", k * 16),
                      "label": "D", "base": g("2023-10"), "num": num, "den": den,
                      "how": "2023-10 概数 x the 速報 / 概数 ratio of 2023-11 + 12",
                      "published": [vn["2023-10"]["published"], p11, p12, vn["2023-11"]["published"], vn["2023-12"]["published"]]}
    out["2023-11"] = {"value": s11, "label": "S", "how": "速報 2023-11 (R96f_vital_fill.csv)", "published": [p11]}
    out["2023-12"] = {"value": s12, "label": "S", "how": "速報 2023-12 (R96f_vital_fill.csv)", "published": [p12]}
    sok = ["2024-08", "2024-09", "2024-10"]
    spread = y24
    for m in sok:
        if vn[m]["release_type"] != "速報":
            raise ValueError("%s %s is not 速報" % (kind, m))
        spread -= g(m)
    jan_jul = ["2024-%02d" % i for i in range(1, 8)]
    prof = [g(m) for m in jan_jul]
    pden = 0
    for x in prof:
        pden += x
    vals = _split(spread, [float(x) for x in prof], seed_v, "d_vital_spread", k)
    for i, m in enumerate(jan_jul):
        out[m] = {"value": vals[i], "label": "D", "base": prof[i], "num": spread, "den": pden,
                  "how": "the 速報 Jan-Oct YTD less 2024-08 .. 10, spread over 2024-01 .. 07 by 概数's monthly profile",
                  "published": [ytd["published_2024"]] + [vn[x]["published"] for x in sok + jan_jul]}
    for m in sok:
        out[m] = {"value": g(m), "label": "S", "how": "速報 %s (R96f_vital_national.csv)" % m, "published": [vn[m]["published"]]}
    for m, b, p, key in (("2024-11", s11, p11, 13), ("2024-12", s12, p12, 14)):
        out[m] = {"value": _round1(float(b) * float(y24) / float(y23), seed_v, "d_vital_round", k * 16 + key),
                  "label": "F", "base": b, "num": y24, "den": y23,
                  "how": "the 2023 same month (速報) x the 速報 Jan-Oct YTD ratio, 2024 over 2023",
                  "published": [p, ytd["published_2024"], ytd["published_2023"]]}
    return out


def _vital_pref(I, nat, seed_v, kind, k):
    met = kind + "_total"
    vf = I["vf"]
    kak = [float(int(I["bd"][(c, "total")][kind])) for c in PREFS]
    out = {}
    for mi, m in enumerate(MONTHS):
        t = nat[m]["value"]
        if m <= "2024-07":
            out[m] = _split(t, kak, seed_v, "d_pref_" + kind, mi)
        elif m <= "2024-10":
            v = [int(I["vp"][(m, c)][kind]) for c in PREFS]
            sv = 0
            for x in v:
                sv += x
            if sv != t:
                raise ValueError("%s %s: the prefectures sum to %d, not %d" % (kind, m, sv, t))
            out[m] = v
        else:
            w = []
            for c in PREFS:
                b = float(int(vf[("same_month_2023", m, c, met, "速報")]["value_2023"]))
                y = vf[("ytd", "2024-11..2024-12", c, met, "速報")]
                w.append(b * float(int(y["value_2024"])) / float(int(y["value_2023"])))
            out[m] = _split(t, w, seed_v, "d_pref_" + kind, mi)
    return out


def _birth_sex(I, m):
    vn = I["vn"]
    src = m if "2024-01" <= m <= "2024-07" else "2023-" + m[5:7]
    if src in vn and vn[src]["births_m"] != "NF":
        return [int(vn[src]["births_m"]), int(vn[src]["births_f"])], "概数 " + src
    bd = I["bd"]
    return [int(bd[("00", "male")]["births"]), int(bd[("00", "female")]["births"])], "2023 確定 (R96g; 概数 %s not in R96f)" % src


def _juki_net(I, m):
    out = {}
    for r in I["mi"]:
        if r["month"] == m and r["source"].startswith("住基") and r["group"] == "total":
            out[r["sex"]] = (int(r["net"]), r["published"])
    return out


def _sex_shares(I, m):
    # Why not each sex's own 住基 net x the ratio: a sex's net can have the other sign to the total (2024-08's women, -830), the PM's
    # ruling on (5); the trailing window ends at the last in-window 住基 month
    have = [x for x in MONTHS if "総数" in _juki_net(I, x)]
    end = MONTHS.index(min(m, have[-1]))
    win = [x for x in MONTHS[max(0, end - 11):end + 1] if x in have]
    sm = 0
    sf = 0
    st = 0
    pubs = []
    for x in win:
        j = _juki_net(I, x)
        sm += j["男"][0]
        sf += j["女"][0]
        st += j["総数"][0]
        pubs.append(j["総数"][1])
    if sm + sf != st:
        raise ValueError("住基 %s .. %s: the sexes' nets do not sum to the total" % (win[0], win[-1]))
    if 0 <= sm <= st and 0 <= sf <= st and st > 0:
        return {"sums": [sm, sf], "window": [win[0], win[-1], len(win)], "fallback": False, "published": pubs,
                "from": "住基 参考表 net by sex, %s .. %s (%d months)" % (win[0], win[-1], len(win))}
    mf = I["mf"]
    y = [int(mf[("YTD", "参考表", "00", "total", x, "net")]["value_2023"]) for x in ("男", "女")]
    return {"sums": y, "window": ["2023-01", "2023-11", 11], "fallback": True, "published": [],
            "from": "fallback: 住基 参考表 2023 Jan-Nov YTD net by sex (R96f_mig_fill.csv), the trailing share %d / %d being outside [0, 1]"
                    % (sm, st)}


def _intl(I, seed_v):
    est = {}
    for r in I["mi"]:
        if r["source"].startswith("人口推計") and r["group"] == "total" and r["sex"] == "総数":
            est[r["month"]] = (int(r["net"]), r["published"])
    overlap = [m for m in MONTHS if m in est]
    num = 0
    den = 0
    for m in overlap:
        num += est[m][0]
        den += _juki_net(I, m)["総数"][0]
    mf = I["mf"]
    ytd = mf[("YTD", "参考表", "00", "total", "総数", "net")]
    y24 = int(ytd["value_2024"])
    y23 = int(ytd["value_2023"])
    out = {}
    for mi, m in enumerate(MONTHS):
        if m in est:
            t = est[m][0]
            out[m] = {"value": t, "label": "S", "how": "人口推計 確定 入国超過 (R96f_mig_international.csv)", "published": [est[m][1]]}
        elif m <= "2024-11":
            j = _juki_net(I, m)
            t = _round1(float(j["総数"][0]) * float(num) / float(den), seed_v, "d_intl_round", mi)
            out[m] = {"value": t, "label": "F", "base": j["総数"][0], "num": num, "den": den,
                      "how": "the month's 住基 net x 人口推計's net over 住基's on 2023-10 .. 2024-06",
                      "published": [j["総数"][1], est[overlap[-1]][1]]}
        else:
            r = mf[("same_month_2023", "参考表", "00", "total", "総数", "net")]
            b = int(r["value_2023"])
            t = _round1(float(b) * float(y24) / float(y23) * float(num) / float(den), seed_v, "d_intl_round", mi)
            out[m] = {"value": t, "label": "F", "base": b, "num": num, "den": den, "ytd_num": y24, "ytd_den": y23,
                      "how": "住基's net of 2023-12 x the 住基 Jan-Nov YTD net ratio x the overlap ratio",
                      "published": [r["published_2023"], _juki_net(I, "2024-11")["総数"][1], est[overlap[-1]][1]]}
        sh = _sex_shares(I, m)
        out[m]["sex"] = _split(t, [float(sh["sums"][0]), float(sh["sums"][1])], seed_v, "d_intl_sex", mi)
        out[m]["sex_share"] = sh
    return out


def _internal(I, seed_v):
    mp = I["mp"]
    mf = I["mf"]
    out = {}
    for mi, m in enumerate(MONTHS):
        if m <= "2024-11":
            v = [int(mp[(m, c, "総数", "総数")]["net"]) for c in PREFS]
            out[m] = {"pref": v, "label": "S", "how": "住基 表1 net (R96f_mig_internal_pref.csv)", "published": [mp[(m, "00", "総数", "総数")]["published"]]}
            continue
        net = [0] * len(PREFS)
        sums = {}
        pubs = []
        for gi, grp in enumerate(("日本人", "外国人")):
            ins = []
            outs = []
            for pi, c in enumerate(PREFS):
                xs = []
                for met in ("in(他都道府県から)", "out(他都道府県へ)"):
                    b = mf[("same_month_2023", "表1", c, grp, "総数", met)]
                    y = mf[("YTD", "表1", c, grp, "総数", met)]
                    xs.append(float(int(b["value_2023"])) * float(int(y["value_2024"])) / float(int(y["value_2023"])))
                    pubs.append(b["published_2023"])
                ins.append(_round1(xs[0], seed_v, "d_int_in", gi * 64 + pi))
                outs.append(xs[1])
            tin = 0
            for x in ins:
                tin += x
            oi = _split(tin, outs, seed_v, "d_int_out", gi)
            for pi in range(len(PREFS)):
                net[pi] += ins[pi] - oi[pi]
            yn = mf[("YTD", "表1", "00", grp, "総数", "in(他都道府県から)")]
            sums[grp] = (int(yn["value_2024"]), int(yn["value_2023"]))
        out[m] = {"pref": net, "label": "F", "group_ratio": sums,
                  "how": "the 2023-12 month's in and out by prefecture x 日本人 / 外国人 x each one's Jan-Nov YTD ratio; out re-scaled to the filled in",
                  "published": pubs + [_juki_net(I, "2024-11")["総数"][1]]}
    return out


def _death_bands(I, dpref, seed_v):
    da = I["da"]
    w = []
    for c in PREFS:
        row = []
        for s, sx in enumerate(SEXES):
            tot = da[(c, sx, "総数")]
            known = 0
            for lab in DEATH_LABELS:
                known += da[(c, sx, lab)]
            if known + da[(c, sx, "不詳")] != tot:
                raise ValueError("R96g deaths %s %s: the ages do not sum to the total" % (c, sx))
            for lab in DEATH_LABELS:
                row.append(float(da[(c, sx, lab)]) * float(tot) / float(known))
        w.append(row)
    nb = len(DEATH_LABELS)
    out = {}
    for mi, m in enumerate(MONTHS):
        nat = [[0] * nb, [0] * nb]
        for pi in range(len(PREFS)):
            cell = _split(dpref[m][pi], w[pi], seed_v, "d_death_band", mi * 64 + pi)
            for s in range(2):
                for b in range(nb):
                    nat[s][b] += cell[s * nb + b]
        out[m] = nat
    return out


def _intl_pref_weights(net):
    # Why not the prefectures' 2023-10-01 totals (the provisional rule): the international inflow settles where 住基's 2023 net from
    # abroad went (R100, the PM's ruling on (7), AMENDED); a negative net is floored at 0 so the weights stay a share
    floored = [PREFS[i] for i in range(len(net)) if net[i] < 0]
    return [float(max(0, x)) for x in net], floored


def _cohort_year(a0, bm):
    return 2023 - a0 if bm <= 9 else 2022 - a0


def age_to_2025(seed_v=1):
    I = inputs()
    mu = [[-detmath.log(1.0 - I["q"][s][a]) for a in range(TOP)] for s in range(2)]
    bnat = _vital_national(I, seed_v, "births", 0)
    dnat = _vital_national(I, seed_v, "deaths", 1)
    bpref = _vital_pref(I, bnat, seed_v, "births", 0)
    dpref = _vital_pref(I, dnat, seed_v, "deaths", 1)
    dband = _death_bands(I, dpref, seed_v)
    intl = _intl(I, seed_v)
    internal = _internal(I, seed_v)

    g_sex = []
    g_age = []
    g_bm = []
    g_by = []
    g_open = []
    g_cnt = []
    g_base = []
    g_birth = []
    g_death = []
    g_mig = []
    bm = I["bm"]
    for s in range(2):
        for a0 in range(NA):
            w = []
            for k in range(12):
                row = bm["shares"][_pick_year(bm["years"], max(1947, _cohort_year(a0, k + 1)))]
                w.append(float(row[k]))
            cnt = _split(I["base"][s][a0], w, seed_v, "d_bm", s * NA + a0)
            for k in range(12):
                g_sex.append(s)
                g_age.append(a0)
                g_bm.append(k + 1)
                g_by.append(_cohort_year(a0, k + 1))
                g_open.append(a0 == TOP)
                g_cnt.append(cnt[k])
                g_base.append(cnt[k])
                g_birth.append(0)
                g_death.append(0)
                g_mig.append(0)

    ntot = 0
    for s in range(2):
        for a in range(NA):
            ntot += I["base"][s][a]
    pref = _split(ntot, [float(x * 1000) for x in I["pref_thousand"]], seed_v, "d_pref0", 0)
    pref0 = list(pref)
    intl_weights, intl_floored = _intl_pref_weights(I["abroad_net"])

    def table():
        t = [[0] * NA, [0] * NA]
        for i in range(len(g_cnt)):
            t[g_sex[i]][g_age[i]] += g_cnt[i]
        return t

    def at_age():
        ix = [[[] for _ in range(NA)], [[] for _ in range(NA)]]
        for i in range(len(g_cnt)):
            ix[g_sex[i]][g_age[i]].append(i)
        return ix

    def to_groups(flow, mi, tag, tally):
        ix = at_age()
        for s in range(2):
            for a in range(NA):
                f = flow[s][a]
                if f == 0:
                    continue
                ids = ix[s][a]
                if not ids:
                    raise ValueError("%s %s: %d at sex %d age %d, which has no group" % (tag, MONTHS[mi], f, s, a))
                part = _split(f, [float(g_cnt[i]) for i in ids], seed_v, tag, (mi * 2 + s) * NA + a)
                for j, i in enumerate(ids):
                    g_cnt[i] += part[j]
                    tally[i] += part[j]
                    if g_cnt[i] < 0:
                        raise ValueError("%s %s: group %d went below zero" % (tag, MONTHS[mi], i))

    ledger = []
    for mi, m in enumerate(MONTHS):
        cm = _cal(m)
        before = table()
        aged_out = [[0] * NA, [0] * NA]
        aged_in = [[0] * NA, [0] * NA]
        for i in range(len(g_cnt)):
            if g_bm[i] == cm and g_age[i] < TOP:
                aged_out[g_sex[i]][g_age[i]] += g_cnt[i]
                g_age[i] += 1
                aged_in[g_sex[i]][g_age[i]] += g_cnt[i]

        cnt = table()
        deaths = [[0] * NA, [0] * NA]
        for s in range(2):
            for b, (lo, hi) in enumerate(DEATH_BANDS):
                d = dband[m][s][b]
                if lo == hi:
                    deaths[s][lo] += d
                    continue
                part = _split(d, [float(cnt[s][a]) * mu[s][a] for a in range(lo, hi + 1)], seed_v, "d_death_age", (mi * 2 + s) * 32 + b)
                for j in range(hi - lo + 1):
                    deaths[s][lo + j] += part[j]
        neg = [[-deaths[s][a] for a in range(NA)] for s in range(2)]
        to_groups(neg, mi, "d_death_grp", g_death)

        cnt = table()
        mig = [[0] * NA, [0] * NA]
        for s, sx in enumerate(SEXES):
            prof = [float(I["mv"][(sx, lab)]) for lab in MOVER_LABELS]
            bands = _split(intl[m]["sex"][s], prof, seed_v, "d_intl_band", mi * 2 + s)
            for b, (lo, hi) in enumerate(MOVER_BANDS):
                part = _split(bands[b], [float(cnt[s][a]) for a in range(lo, hi + 1)], seed_v, "d_intl_age", (mi * 2 + s) * 32 + b)
                for j in range(hi - lo + 1):
                    mig[s][lo + j] += part[j]
        to_groups(mig, mi, "d_intl_grp", g_mig)

        bsex, bsex_src = _birth_sex(I, m)
        births_s = _split(bnat[m]["value"], [float(bsex[0]), float(bsex[1])], seed_v, "d_birth_sex", mi)
        births = [[0] * NA, [0] * NA]
        for s in range(2):
            births[s][0] = births_s[s]
            g_sex.append(s)
            g_age.append(0)
            g_bm.append(cm)
            g_by.append(int(m[:4]))
            g_open.append(False)
            g_cnt.append(births_s[s])
            g_base.append(0)
            g_birth.append(births_s[s])
            g_death.append(0)
            g_mig.append(0)
        after = table()

        ipref = _split(intl[m]["value"], intl_weights, seed_v, "d_intl_pref", mi)
        pb = list(pref)
        for pi in range(len(PREFS)):
            pref[pi] += bpref[m][pi] - dpref[m][pi] + internal[m]["pref"][pi] + ipref[pi]
            if pref[pi] < 0:
                raise ValueError("prefecture %s below zero in %s" % (PREFS[pi], m))
        ledger.append({
            "month": m,
            "flows": {"births": bnat[m], "deaths": dnat[m], "intl": intl[m], "internal": internal[m],
                      "births_sex": births_s, "births_sex_from": bsex_src, "births_sex_weights": bsex},
            "nat": {"before": before, "aged_out": aged_out, "aged_in": aged_in, "deaths": deaths, "mig": mig, "births": births,
                    "after": after, "death_bands": dband[m]},
            "pref": {"before": pb, "births": bpref[m], "deaths": dpref[m], "internal": internal[m]["pref"], "intl": ipref,
                     "after": list(pref)},
        })

    cohorts = []
    for i in range(len(g_cnt)):
        cohorts.append({"sex": g_sex[i], "birth_year": g_by[i], "birth_month": g_bm[i], "open_top": g_open[i],
                        "age_2025": g_age[i], "count_base": g_base[i], "births": g_birth[i], "deaths": -g_death[i],
                        "mig": g_mig[i], "count_2025": g_cnt[i]})
    return {"seed": seed_v, "table": table(), "prefectures": list(pref), "pref_codes": list(PREFS), "pref_names": I["pref_names"],
            "intl_pref": {"net_2023": I["abroad_net"], "floored": intl_floored},
            "base": {"table": I["base"], "prefectures": pref0, "pref_thousand": I["pref_thousand"]},
            "ledger": ledger, "cohorts": cohorts}


def table_sha(t):
    xs = list(t[0]) + list(t[1])
    return hashlib.sha256(struct.pack("<%dq" % len(xs), *xs)).hexdigest()


def pref_sha(p):
    return hashlib.sha256(struct.pack("<%dq" % len(p), *p)).hexdigest()


SOURCE = ("start rule (D), START_PORT_PLAN §5 (AMENDED by the PM's ruling on M040), py/tiers/start/age_d.py, seed 1: the 人口推計 "
          "2023-10-01 cohort (data/modern/jpn/status_2024.json .cohort, 第1表, published 2024-04-12) on birth-month groups (R76 "
          "birth_month_shares), the prefectures' totals from R81's 2023-10-01 第10表 (data/modern/polity/jpn_prefectures.json) raked to "
          "the cohort's total, aged over 2023-10 .. 2024-12 with R96f's monthly flows (research-notes 33f578dc) and R96g's 2023 "
          "tables (research-notes 81317116), copied in data/modern/jpn/flows_2023_2024/, deaths split by 令和5年簡易生命表's central "
          "rate (R96h, jpn_households_2024.json .life_course.qx_2022); the international net by sex by 住基's trailing 12-month net "
          "shares (D, the PM's ruling on (5)) and over prefectures by their 2023 住基 net from abroad (国外からの転入 - 国外への転出, "
          "総数; R100, research-notes a694abc5, published 2024-07-24; a negative net floored at 0; D, AMENDED, the PM's ruling on (7)); "
          "every input published by 2024-12-31")


def output(res):
    t = res["table"]
    flows = {}
    for e in res["ledger"]:
        f = e["flows"]
        flows[e["month"]] = {"births": f["births"]["value"], "births_label": f["births"]["label"],
                             "deaths": f["deaths"]["value"], "deaths_label": f["deaths"]["label"],
                             "intl_net": f["intl"]["value"], "intl_label": f["intl"]["label"],
                             "internal_label": f["internal"]["label"]}
    tot = 0
    for s in range(2):
        for a in range(NA):
            tot += t[s][a]
    return {
        "unit_persons": 1,
        "date": "2025-01-01",
        "source": SOURCE,
        "seed": res["seed"],
        "sha256_table": table_sha(t),
        "sha256_prefectures": pref_sha(res["prefectures"]),
        "total": tot,
        "ages": [{"age": a, "male": t[0][a], "female": t[1][a]} for a in range(NA)],
        "prefectures": {c: {"name": res["pref_names"][i], "pop": res["prefectures"][i]} for i, c in enumerate(res["pref_codes"])},
        "flows": flows,
    }


def write(res, path=OUT):
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(output(res), f, ensure_ascii=False, indent=1)
        f.write("\n")


def _pub(xs):
    best = ""
    for x in xs:
        for d in (x or "").split(";"):
            if d[:2] == "20" and d > best:
                best = d
    return best


def sources_rows(res):
    rel = "data/modern/jpn/cohort_2025-01-01.json"
    act = "added (start rule D, START_PORT_PLAN §5)"
    rows = []
    for e in res["ledger"]:
        m = e["month"]
        f = e["flows"]
        for key, name, src in (("births", "births", "R96f_vital_national.csv, R96f_vital_fill.csv"),
                               ("deaths", "deaths", "R96f_vital_national.csv, R96f_vital_fill.csv")):
            x = f[key]
            if x["label"] == "S":
                continue
            rows.append([rel, ".flows.%s.%s" % (m, name), str(x["value"]), "persons", x["label"],
                         "%s %s: %s; ratio %d / %d on %s %d (keyed rounding, seed 1)" % (R96F, src, x["how"], x["num"], x["den"],
                                                                                        "the profile month" if m <= "2024-07" and m >= "2024-01" else "base", x["base"]),
                         _pub(x["published"]), "", act])
        x = f["intl"]
        if x["label"] != "S":
            extra = " x the 住基 Jan-Nov YTD net %d / %d" % (x["ytd_num"], x["ytd_den"]) if "ytd_num" in x else ""
            rows.append([rel, ".flows.%s.intl_net" % m, str(x["value"]), "persons", "F",
                         "%s R96f_mig_international.csv, R96f_mig_fill.csv: %s; 住基 net %d%s x %d / %d (keyed rounding, seed 1; the PM's ruling (1))"
                         % (R96F, x["how"], x["base"], extra, x["num"], x["den"]),
                         _pub(x["published"]), "", act])
        x = f["internal"]
        if x["label"] != "S":
            r = x["group_ratio"]
            rows.append([rel, ".flows.%s.internal" % m, "national net 0; 47 prefecture nets", "persons", "F",
                         "%s R96f_mig_fill.csv: %s; national in-movers YTD 日本人 %d / %d, 外国人 %d / %d (keyed rounding, seed 1)"
                         % (R96F, x["how"], r["日本人"][0], r["日本人"][1], r["外国人"][0], r["外国人"][1]),
                         _pub(x["published"]), "", act])
    rows.append([rel, ".ages", "101 single ages x 2 sexes at 2025-01-01 (sha256 %s)" % table_sha(res["table"]), "persons", "D",
                 SOURCE, "2024-12-26", "", act])
    rows.append([rel, ".prefectures", "47 prefecture totals at 2025-01-01 (sha256 %s)" % pref_sha(res["prefectures"]), "persons", "D",
                 "start rule (D): R81's 2023-10-01 totals raked to the cohort's total, then each month's births, deaths, 住基 表1 net and "
                 "the international net", "2024-12-26", "", act])
    fbm = [e["month"] for e in res["ledger"] if e["flows"]["intl"]["sex_share"]["fallback"]]
    fl = ("floored at 0: " + ", ".join(res["intl_pref"]["floored"])) if res["intl_pref"]["floored"] else "no prefecture floored"
    fb = ("used in " + ", ".join(fbm)) if fbm else "not used in any month"
    splits = [
        (".base.prefectures", "R81's 2023-10-01 第10表 totals (sum 124,353 thousand) raked to the 第1表 cohort's total (124,356 thousand) "
                              "by keyed systematic rounding (judgement: the two published tables differ by rounding to thousands)", "2024-04-12"),
        (".ages (birth-month groups)", "each sex x single age of the base split into 12 birth-month groups by R76's shares of each "
                                       "month's birth year (Jan-Sep 2023 - age, Oct-Dec 2022 - age; nearest listed year, earlier on a tie, "
                                       "before 1947 1947's), keyed systematic rounding", "2024-09-17"),
        (".flows.*.births (prefectures)", "2023-10 .. 2024-07: the national 速報 month x each prefecture's share of 2023 確定 births "
                                          "(R96g, the PM's ruling (2)); 2024-08 .. 10 R96f's 速報 rows; 2024-11, 12 the 2023 速報 month x the "
                                          "prefecture's own YTD ratio, raked to the national fill", "2024-12-24"),
        (".flows.*.deaths (prefectures, age x sex)", "prefectures as births (ruling 2); each prefecture's month by its 2023 確定 deaths by "
                                                     "sex x 5-year age (R96g, 不詳 spread within the sex), summed nationally, then each band "
                                                     "to single ages by count(a) x mu(a), mu = -ln(1 - q) of 令和5年簡易生命表 (ruling 3)", "2024-12-24"),
        (".flows.*.births (sex)", "概数's sex shares of the same calendar month (2024-01 .. 07 from 2024, the rest from 2023); 2024-08 and "
                                  "2024-09 take 2023 確定's national sex shares (R96g), since R96f holds no 2023-08 / 09 概数 by sex "
                                  "(accepted by the PM, TO_PM_PY 19:38)", "2024-12-06"),
        (".flows.*.intl_net (sex)", "every month's international net (人口推計's, or the F level) split by sex by 住基 参考表's net shares "
                                    "over the trailing 12 months ending at that month (2024-12: ending at 2024-11, the last in-window 住基 "
                                    "month); R96f holds 住基 by sex only from 2023-10, so the windows ending 2023-10 .. 2024-08 hold "
                                    "fewer than 12 months (2023-10 to that month): R96f_mig_fill.csv's 2023 by-sex rows are one Jan-Nov "
                                    "sum, which cannot give 2023-08, 09 or 2022-11, 12 as months; fallback (share outside [0, 1]) to "
                                    "住基's 2023 Jan-Nov YTD by sex (R96f_mig_fill.csv; R96g has no annual 国外 table): " + fb
                                    + " (the PM's ruling on (5), TO_PM_PY 19:38)", "2024-12-26"),
        (".flows.*.intl_net (age)", "every month by sex to 5-year bands by 住基 2023 年報 第3-1表 in-movers 総数 (R96g), then to single "
                                    "ages by count(a) (judgement)", "2024-01-30"),
        (".flows.*.intl_net (prefectures)", "AMENDED (the PM's ruling on (7)): each month's international net split over "
                                            "prefectures by each one's 2023 住基 net from abroad (国外からの転入 - 国外への転出, 総数; R100, "
                                            "research-notes a694abc5, 住民基本台帳に基づく人口、人口動態及び世帯数 令和6年1月1日現在 参考資料, "
                                            "published 2024-07-24) over the national sum; a prefecture with a negative net floored at 0 and "
                                            "the rest renormalised (" + fl + "); replaces the provisional split by the 2023-10-01 totals",
         "2024-07-24", "D (AMENDED)"),
    ]
    for sp in splits:
        rows.append([rel, sp[0], "split rule", "persons", sp[3] if len(sp) > 3 else "D", "start rule (D): " + sp[1], sp[2], "", act])
    return rows


def file_rows():
    act_f = "added (start rule D input; byte-identical copy of research-notes %s:docs/team/research/reports/%s)"
    out = []
    files = [("R96f_vital_national.csv", "33f578dc", "S", "national births and deaths by month, 2023-10 .. 2024-10 (概数 to 2024-07, 速報 from 2024-08)"),
             ("R96f_vital_prefecture.csv", "33f578dc", "S", "births and deaths by prefecture by month, 2023-10 .. 2024-10"),
             ("R96f_vital_fill.csv", "33f578dc", "S (D ratios)", "the 2023 same months (速報 and 概数) and the 2024-over-2023 YTD sums for the 2024-11, 12 fill"),
             ("R96f_mig_internal_pref.csv", "33f578dc", "S", "住基 表1 moves between prefectures by prefecture x sex x 総数/日本人/外国人, 2023-10 .. 2024-11"),
             ("R96f_mig_international.csv", "33f578dc", "S", "人口推計 確定 入国超過 2023-10 .. 2024-06; 住基 参考表 国外からの転入 / 国外への転出 2023-10 .. 2024-11; 出入国管理統計 (check only)"),
             ("R96f_mig_fill.csv", "33f578dc", "S (D ratios)", "the 2023 same months and Jan-Nov YTD sums for the 2024-12 migration fill"),
             ("R96g_births_deaths_pref_sex_2023.csv", "81317116", "S", "人口動態統計 2023 確定 births and deaths by prefecture x sex (000040207154, 000040206167)"),
             ("R96g_deaths_age_sex_2023.csv", "81317116", "S", "人口動態統計 2023 確定 deaths by prefecture x sex x 5-year age (000040206167)"),
             ("R96g_movers_age_sex_2023.csv", "81317116", "S", "住民基本台帳人口移動報告 2023年 年報 第3-1, 3-2, 4表 movers by prefecture x sex x 5-year age"),
             ("R100_juki_international_by_pref.csv", "a694abc5", "S", "住基 2023 国外からの転入 and 国外への転出 by prefecture x 総数/日本人/外国人 "
                                                                        "(令和6年1月1日現在 参考資料 都道府県別; sex NF; researcher4's CHECK: the bytes are the first "
                                                                        "captures of the edition, 2025-04, no revision likely)")]
    for name, commit, label, what in files:
        rows = _rows(name)
        pubs = []
        for r in rows:
            for k in ("published", "published_2023", "published_2024"):
                if r.get(k):
                    pubs.append(r[k])
        if name == "R96f_mig_fill.csv":
            # Why not the file's own columns: it dates only the 2023 values, and its 2024 YTD sums run to 住基 2024-11
            pubs.append(_juki_net({"mi": _rows("R96f_mig_international.csv")}, "2024-11")["総数"][1])
        out.append(["data/modern/jpn/flows_2023_2024/" + name, "(whole file)", "%d rows" % len(rows), "", label,
                    "%s: %s" % ({"33f578dc": R96F, "81317116": R96G}.get(commit, "R100 (research-notes %s)" % commit), what), _pub(pubs), "",
                    act_f % (commit, name)])
    return out


if __name__ == "__main__":
    r = age_to_2025(1)
    if "--sources" in sys.argv:
        w = csv.writer(sys.stdout, lineterminator="\n")
        for row in file_rows() + sources_rows(r):
            w.writerow(row)
    else:
        write(r)
        print(OUT, table_sha(r["table"]), pref_sha(r["prefectures"]))
