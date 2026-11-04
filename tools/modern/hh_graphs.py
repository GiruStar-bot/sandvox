"""The households' overlay graphs (ISS roadmap 10.6): the behaviour run's own outputs (hh_run.jsonl) over the official statistics the
households spec holds (data/modern/people/jpn_households_2024.json, built from R62/R63/R64), one PNG per graph, each naming its source
table, the calibration period (inputs up to 2024-01) and the check period (realised 2024-2025).
  <python with matplotlib> -I tools/modern/hh_graphs.py <hh_run.jsonl> <spec json> <out dir> [<realised json>]
The realised 2024-2025 values (R65, CHECK ONLY) and the 社人研 令和5年推計 TFR (PROJECTION) are read from the optional fourth file,
data/modern/checks/jpn_r65_check.json; without it the graphs say PENDING R65. Past 2025 the model is compared only with the
projection, labelled as one."""
import json
import math
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
# Why a fallback list and not one CJK font: the Latin text keeps DejaVu; the source tables' names need a CJK face (installed here)
plt.rcParams["font.family"] = ["DejaVu Sans", "WenQuanYi Zen Hei", "Unifont-JP"]

CAL = "Calibration period: inputs up to 2024-01."
MODEL = "#1f5fa8"
OFFICIAL = "#c0392b"


def footer(fig, source, realised):
    chk = "Check period: realised 2024-2025 " + ("from R65 (CHECK ONLY, black marks); past 2025 the 社人研 令和5年推計 (PROJECTION, grey)" if realised else "PENDING R65 (researcher4: realised 2024-2025, check only)") + "."
    fig.text(0.01, 0.01, "Source: " + source + "\n" + CAL + " " + chk + "\nModel: hh_run national run, seed 1 (model output).", fontsize=7, va="bottom")


def v(spec, key):
    return spec[key]["value"]


def lc(spec, key):
    return spec["life_course"]["value"][key]["value"]


def save(fig, out, name):
    fig.subplots_adjust(bottom=0.22)
    fig.savefig(out + "/" + name, dpi=130)
    plt.close(fig)


def main():
    rows = [json.loads(x) for x in open(sys.argv[1], encoding="utf-8") if x.strip()]
    spec = json.load(open(sys.argv[2], encoding="utf-8"))
    out = sys.argv[3]
    realised = sys.argv[4] if len(sys.argv) > 4 else ""
    chk = json.load(open(realised, encoding="utf-8")) if realised else {}
    real = chk.get("realised", {})
    proj = chk.get("projection", {})
    years = [r["year"] for r in rows]
    last = rows[-1]
    flows = [r for r in rows if r["run_year"] > 0]

    # 1 household types by year against the census
    names = ["one_person", "couple_only", "couple_children", "single_parent", "other"]
    census = v(spec, "type_shares")
    fig, ax = plt.subplots(figsize=(7.5, 4.6))
    for k, nm in enumerate(names):
        line, = ax.plot(years, [100 * r["types"][k] for r in rows], marker="o", ms=3, label=nm.replace("_", " ") + " (model)")
        ax.axhline(100 * census[nm], color=line.get_color(), ls="--", lw=1)
    ax.set_xticks(years)
    ax.set_ylabel("% of private households")
    ax.set_title("Household types: model by year (solid) vs census 2020 (dashed)")
    ax.legend(fontsize=7, ncol=2)
    if real:
        ax.text(0.01, 0.97, "2025 census family types: not yet published (R65 NF); the survey's types are defined differently and are not drawn.\nCensus 2025 preliminary: %.2f persons per household (the model holds each prefecture's 2020 size: a consistency read)." % real["2025"]["census_mean_size"], transform=ax.transAxes, fontsize=6, va="top")
    footer(fig, "国勢調査 2020 図V-1-1 (家族類型; R62 §1, R64 §1)", realised)
    save(fig, out, "h2_household_types.png")

    # 2 births by mother's age, model years 6-10 pooled, against 人口動態統計 2022; TFR by year
    bands = ["15-19", "20-24", "25-29", "30-34", "35-39", "40-44", "45-49"]
    pool = [0.0] * 7
    for r in flows[-5:]:
        for b in range(7):
            pool[b] += r["births_weighted"][b]
    tot = sum(pool) or 1.0
    off = v(spec, "births_by_mother_age")
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(9, 4.4))
    x = range(7)
    a1.bar([i - 0.2 for i in x], [100 * p / tot for p in pool], width=0.4, color=MODEL, label="model (last 5 years)")
    a1.bar([i + 0.2 for i in x], [100 * off[b] for b in bands], width=0.4, color=OFFICIAL, label="2022")
    for y, mk in [("2024", "x"), ("2025", "+")]:
        if y in real:
            a1.plot(list(x), [100 * real[y]["births_by_mother_age"][b] for b in bands], mk, color="black", ms=7, label=y + " (CHECK)")
    a1.set_xticks(list(x))
    a1.set_xticklabels(bands, fontsize=7)
    a1.set_ylabel("% of births")
    a1.set_title("Births by mother's age")
    a1.legend(fontsize=7)
    tfr = []
    for r in flows:
        t = 0.0
        for b in range(7):
            t += 5.0 * r["births_by_mother_age"][b] / max(1.0, r["women_by_band"][b])
        tfr.append(t)
    a2.plot([r["year"] for r in flows], tfr, marker="o", color=MODEL, label="model")
    t22 = spec["checks"]["value"]["tfr"]["value"]
    a2.axhline(t22, color=OFFICIAL, ls="--", label="2022: %.2f" % t22)
    if real:
        a2.plot([2024, 2025], [real["2024"]["tfr"], real["2025"]["tfr"]], "x", color="black", ms=8, label="realised 2024-2025 (CHECK)")
        py = sorted(int(k) for k in proj.get("tfr_medium", {}) if int(k) <= max(r["year"] for r in flows))
        a2.plot(py, [proj["tfr_medium"][str(k)] for k in py], ":", color="grey", label="社人研 R5 medium (PROJECTION)")
        a2.fill_between(py, [proj["tfr_low"][str(k)] for k in py], [proj["tfr_high"][str(k)] for k in py], color="grey", alpha=0.15, label="low-high (PROJECTION)")
    a2.set_xticks([r["year"] for r in flows])
    a2.set_title("Total fertility rate")
    a2.legend(fontsize=7)
    footer(fig, "人口動態統計 2022 第4表 (births by mother's age), 第5表(1) (TFR) via R62 §2", realised)
    save(fig, out, "h2_births.png")

    # 3 mortality: the model's death rates by 5-year band (all years pooled) against the 2022 life table
    deaths, expo = {}, {}
    for r in flows:
        for k, d in r["deaths"].items():
            deaths[k] = deaths.get(k, 0.0) + d
        for k, e in r["exposure"].items():
            expo[k] = expo.get(k, 0.0) + e
    q22 = lc(spec, "qx_2022")
    fig, ax = plt.subplots(figsize=(7.5, 4.6))
    for s, nm, col in [("M", "men", MODEL), ("F", "women", "#2e8b57")]:
        xs, ys = [], []
        for b in range(21):
            k = "%d%s" % (b, s)
            if expo.get(k, 0) > 0 and deaths.get(k, 0) > 0:
                xs.append(5 * b + 2.5)
                ys.append(deaths[k] / expo[k])
        ax.plot(xs, ys, "o", color=col, ms=4, label="model, " + nm)
        tab = q22[nm]
        ax.plot(range(len(tab)), [-math.log(max(1e-12, 1.0 - min(0.999999, q))) for q in tab], "-", color=col, lw=1, label="life table 2022, " + nm)
    if real:
        for nm, col in [("men", MODEL), ("women", "#2e8b57")]:
            tab = real["2024"]["qx"][nm]
            ax.plot(range(len(tab)), [-math.log(max(1e-12, 1.0 - min(0.999999, q))) for q in tab], ":", color="black", lw=0.8, label="life table 2024 (CHECK), " + nm if nm == "men" else None)
        ax.text(0.01, 0.97, "e0 realised (CHECK): 2024 %.2f / %.2f, 2025 %.2f / %.2f" % (real["2024"]["e0"]["men"], real["2024"]["e0"]["women"], real["2025"]["e0"]["men"], real["2025"]["e0"]["women"]), transform=ax.transAxes, fontsize=7, va="top")
    ax.set_yscale("log")
    ax.set_xlabel("age")
    ax.set_ylabel("deaths per person-year")
    ax.set_title("Mortality by age: model (points) vs 令和4年簡易生命表 (lines)")
    ax.legend(fontsize=7)
    footer(fig, "令和4年簡易生命表 (single-year qx, R62_qx_2022.csv); the model's hazard is this table x the grade multipliers (an identity, HB4)", realised)
    save(fig, out, "h2_mortality.png")

    # 4 never married by age at the last year, against census 2020; first-partnering ages by year
    nm_spec = lc(spec, "never_married")
    nb = last["never_married_bands"]
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(9, 4.4))
    for s, nmk, col in [(0, "men", MODEL), (1, "women", "#2e8b57")]:
        a1.plot([(b[0] + b[1]) / 2 for b in nb], [100 * x for x in last["never_married"][s]], "o-", color=col, ms=3, label="model %d, %s" % (last["year"], nmk))
        a1.plot([a + 2 for a in nm_spec["ages"]], [100 * x for x in nm_spec[nmk]], "s--", color=col, ms=4, label="census 2020, " + nmk)
    a1.set_xlabel("age")
    a1.set_ylabel("% never married")
    a1.set_title("Never married by age")
    a1.legend(fontsize=6)
    fma = spec["checks"]["value"]["first_marriage_age"]
    for s, nmk, col, off in [(0, "men", MODEL, fma["men"]), (1, "women", "#2e8b57", fma["women"])]:
        a2.plot([r["year"] for r in flows], [sum(r["first_partnering_ages"][s]) / max(1, len(r["first_partnering_ages"][s])) for r in flows], "o-", color=col, ms=3, label="model, " + nmk)
        a2.axhline(off, color=col, ls="--", lw=1, label="2022: %.1f" % off)
    if real:
        for s2, nmk, col in [(0, "men", MODEL), (1, "women", "#2e8b57")]:
            a2.plot([2024, 2025], [real["2024"]["first_marriage_age"][nmk], real["2025"]["first_marriage_age"][nmk]], "x", color="black", ms=7, label="realised (CHECK)" if s2 == 0 else None)
    a2.set_xticks([r["year"] for r in flows])
    a2.set_title("Mean age at first partnering (marriage)")
    a2.legend(fontsize=6)
    footer(fig, "国勢調査 2020 表III-2 (never married); 人口動態統計 月報年計 2022 (first-marriage ages) via R62 §2", realised)
    save(fig, out, "h2_marriage.png")

    # 5 leaving home by age at the last year, against 第8回世帯動態調査 表8
    lh = v(spec, "left_home_by_age")
    # HB6's bands: the cohort under 18 at the start is 18-27 at year 10, so the model's 25-27 is read against 表8's 25-29
    labs = ["18-19", "20-24", "25-29"]
    fig, ax = plt.subplots(figsize=(7.5, 4.6))
    for s, nmk, col in [(0, "men", MODEL), (1, "women", "#2e8b57")]:
        el = last["ever_left"][s][:2] + [last.get("ever_left_25_27", [float("nan"), float("nan")])[s]]
        ax.plot(range(3), [100 * x for x in el], "o-", color=col, label="model %d, %s" % (last["year"], nmk))
        ax.plot(range(3), [100 * lh[b][s] for b in labs], "s--", color=col, label="2019, " + nmk)
    ax.set_xticks(range(3))
    ax.set_xticklabels(["18-19", "20-24", "25-27 (表8: 25-29)"])
    ax.set_ylabel("% ever left the parental home")
    ax.set_title("Leaving home by age")
    if real:
        ax.text(0.01, 0.03, "No realised 2024-2025 measure of leaving home (R65 has none).", transform=ax.transAxes, fontsize=7)
    ax.legend(fontsize=7)
    footer(fig, "社人研 第8回世帯動態調査 2019 表8 (ever left home) via R62 §5", realised)
    save(fig, out, "h2_leaving_home.png")
    # 6 divorce per 1,000 married wives by age (all years pooled) against R63's 2020 rates (HB9c), the crude rate against R65
    chk_div = spec["checks"]["value"]["divorce_rate_wife"]
    dv_b = chk_div["bands"]
    div_w = {}
    for r in flows:
        for d in r.get("divorces", []):
            if len(d) > 2 and d[2] >= 0:
                b = "<=19" if d[2] < 20 else ("%d-%d" % (d[2] // 5 * 5, d[2] // 5 * 5 + 4))
                div_w[b] = div_w.get(b, 0.0) + d[1]
    wives = {}
    for r in flows:
        for k, w in r.get("married_wives", {}).items():
            b = "<=19" if int(k) < 20 else ("%d-%d" % (int(k), int(k) + 4))
            wives[b] = wives.get(b, 0.0) + w
    fig, ax = plt.subplots(figsize=(7.5, 4.6))
    xs = range(len(dv_b))
    ax.plot(xs, [1000.0 * div_w.get(b, 0.0) / wives[b] if wives.get(b, 0) > 0 else float("nan") for b in dv_b], "o-", color=MODEL, label="model (all years pooled)")
    ax.plot(xs, chk_div["per_1000"], "s--", color=OFFICIAL, label="2020 (R63)")
    ax.set_xticks(list(xs))
    ax.set_xticklabels(dv_b, fontsize=7)
    ax.set_yscale("log")
    ax.set_ylabel("divorces per 1,000 married wives a year")
    ax.set_title("Divorce by the wife's age (HB9c)")
    if real:
        ax.text(0.01, 0.03, "Crude divorce rate realised (CHECK): 2024 %.2f, 2025 %.2f per 1,000 population" % (real["2024"]["divorce_rate"], real["2025"]["divorce_rate"]), transform=ax.transAxes, fontsize=7)
    ax.legend(fontsize=7)
    footer(fig, "離婚に関する統計 2022 (2020 data, per 1,000 married wives by age; R63 §7); 人口動態統計 確定数 2024-2025 (R65)", realised)
    save(fig, out, "h2_divorce.png")
    print("GRAPHS", out)


if __name__ == "__main__":
    main()
