"""data/modern/people/jpn_households_2024.json: the households' start values (ISS_HOUSEHOLD_REDESIGN.md §10.1) from R62's CSV
(research-notes R62_households_lifecourse.csv) where it is machine-readable, the rest from R62's report tables with their source lines,
and the T parts labelled. Only sources up to 2024-01 are read (R62's own rule).
R63 (research-notes d1e3ad0a, R63_household_redesign_gaps.csv) gives the health and divorce rows of the life course (§10.2).
R64 (research-notes, R64_estat_tables.csv) gives the types by householder age and by prefecture, and grade 4 (§10.1 amendment 5,
§10.2 amendment 1).
The life table (R62_qx_2022.csv: 令和4年簡易生命表, single years 0-105+) is the life course's death hazard (§2.1).
R66 (research-notes 3bb2000b, R66_life_course_behaviour.csv) gives the persons' intentions as START values (P: to marry, the number
of children) and marital fertility, first-marriage rates and movers by age as CHECKS only (C) (§10.6).
  python3 -I tools/modern/build_households_spec.py <R62 csv> data/modern/people/jpn_households_2024.json <R63 csv> <R64 csv> <R62 qx csv>
      <R66 csv> <R94 csv> data/modern/jpn/status_2024.json"""
import csv, json, math, re, sys


def nums(text):
    return [float(x) for x in re.findall(r"(\d+(?:\.\d+)?)", text)]


def ltci_share(r94_path, status_path):
    """T2.2c (M034 §1): LTCI's April 2022 recipients (R94, table 000040099769, 総数 of every level) / the start's 2024 persons
    (data/modern/jpn/status_2024.json's cohort), by R94's 5-year bands x sex; the open band to 100+"""
    st = json.load(open(status_path, encoding="utf-8"))["cohort"]
    unit = float(st.get("unit_persons", 1.0))
    pop = {}
    for r in st["ages"]:
        pop[(int(r["age"]), "men")] = float(r["male"]) * unit
        pop[(int(r["age"]), "women")] = float(r["female"]) * unit
    rows = []
    for r in csv.DictReader(open(r94_path, encoding="utf-8")):
        if r["table"] != "000040099769" or r["to_state"] != "総数" or r["sex"] not in ("男", "女"):
            continue
        nums = [int(x) for x in re.findall(r"\d+", r["age_band"])]
        if not nums:
            continue
        lo = nums[0]
        hi = 100 if "以上" in r["age_band"] else nums[1]
        rows.append((lo, hi, "men" if r["sex"] == "男" else "women", 1000.0 * float(r["value"])))
    out = {"from": sorted({lo for lo, _, _, _ in rows}), "men": [], "women": []}
    for sx in ("men", "women"):
        for lo in out["from"]:
            for lo2, hi2, sx2, v in rows:
                if lo2 == lo and sx2 == sx:
                    out[sx].append(round(v / sum(pop[(a, sx)] for a in range(lo, hi2 + 1)), 6))
    return out


def _smooth_logit(bands, weight):
    """M035 §3: the logit piecewise linear through one node per band [lo, hi, value] at the band's weight-mean age, linear beyond the
    outer nodes, the nodes moved until every band's weighted mean equals its value to 1e-10; the single ages 0-100"""
    lg = lambda x: math.log(x / (1 - x))
    ex = lambda x: 1 / (1 + math.exp(-x))
    nodes = []
    for lo, hi, v in bands:
        w = [weight(a) for a in range(lo, hi + 1)]
        nodes.append([sum(a * x for a, x in zip(range(lo, hi + 1), w)) / sum(w), lg(v)])

    def curve(a):
        if len(nodes) == 1:
            return nodes[0][1]
        if a <= nodes[0][0]:
            return nodes[0][1] + (nodes[1][1] - nodes[0][1]) / (nodes[1][0] - nodes[0][0]) * (a - nodes[0][0])
        for (x0, y0), (x1, y1) in zip(nodes, nodes[1:]):
            if a <= x1:
                return y0 + (y1 - y0) * (a - x0) / (x1 - x0)
        return nodes[-1][1] + (nodes[-1][1] - nodes[-2][1]) / (nodes[-1][0] - nodes[-2][0]) * (a - nodes[-1][0])

    for _ in range(2000):
        worst = 0.0
        for i, (lo, hi, v) in enumerate(bands):
            w = [weight(a) for a in range(lo, hi + 1)]
            mean = sum(ex(curve(a)) * x for a, x in zip(range(lo, hi + 1), w)) / sum(w)
            nodes[i][1] += lg(v) - lg(mean)
            worst = max(worst, abs(mean - v))
        if worst < 1e-10:
            break
    assert worst < 1e-10, worst
    return [round(ex(curve(a)), 12) for a in range(101)]


def single_age_prevalence(life):
    """M035 §3: grade 2+ (the 10-year symptom bands), grade 4 (the 5-year limitation bands) and 4b (LTCI's 5-year bands) smoothed
    to single ages 0-100 by sex, each band weighted by the 2022 table's survivors l_x; 4b 0 below its first band"""
    out = {"g2plus": {}, "g4": {}, "b4": {}}
    lim = life["limitation_rate"]["value"]
    lt = life["ltci_share"]["value"]
    for sx in ("men", "women"):
        q = life["qx_2022"]["value"][sx]
        lx = [1.0]
        for a in range(100):
            lx.append(lx[-1] * (1 - min(q[min(a, len(q) - 1)], 0.999)))
        wt = lambda a: lx[a]
        sym = life["symptom_rate"]["value"][sx]
        out["g2plus"][sx] = _smooth_logit([(10 * i, 10 * i + 9 if i < 8 else 100, sym[i]) for i in range(9)], wt)
        fr = lim["from"]
        out["g4"][sx] = _smooth_logit([(fr[i] if i > 0 else 0, fr[i + 1] - 1 if i + 1 < len(fr) else 100, lim[sx][i]) for i in range(len(fr))], wt)
        lf = lt["from"]
        b4 = _smooth_logit([(lf[i], lf[i + 1] - 1 if i + 1 < len(lf) else 100, lt[sx][i]) for i in range(len(lf))], wt)
        out["b4"][sx] = [0.0 if a < lf[0] else b4[a] for a in range(101)]
    return out


def main():
    rows = {(r["item"], r["metric"]): r for r in csv.DictReader(open(sys.argv[1], encoding="utf-8"))}
    types = rows[("1 households", "family type, share of general households")]["value"]
    v = nums(types)
    type_shares = {"one_person": v[0] / 100, "couple_only": v[1] / 100, "couple_children": v[2] / 100, "single_parent": v[3] / 100, "other": v[4] / 100}
    ch = nums(rows[("2 fertility", "distribution of children, couples married 15-19 y")]["value"])   # 0, 7.7, 1, 19.7, 2, 50.8, 3, 18.6, 4, 3.2
    children = {"1": ch[3], "2": ch[5], "3": ch[7], "4": ch[9]}
    tot = sum(children.values())
    children = {k: round(x / tot, 6) for k, x in children.items()}
    mb = nums(rows[("2 fertility", "births by mother's age (5-y), 2022")]["value"])   # 19, 0.6, 20, 24, 6.9, ...
    births_by_age = {"15-19": mb[1], "20-24": mb[4], "25-29": mb[7], "30-34": mb[10], "35-39": mb[13], "40-44": mb[16], "45-49": mb[18]}
    tot = sum(births_by_age.values())
    births_by_age = {k: round(x / tot, 6) for k, x in births_by_age.items()}
    left = nums(rows[("5 leaving home", "ever left the parental home, men / women %")]["value"])
    left_home = {"18-19": [left[2] / 100, left[3] / 100], "20-24": [left[6] / 100, left[7] / 100], "25-29": [left[10] / 100, left[11] / 100], "30-34": [left[14] / 100, left[15] / 100], "35+": [left[18] / 100, left[19] / 100]}
    r63 = {r["name"]: r for r in csv.DictReader(open(sys.argv[3], encoding="utf-8-sig"))}
    bands10 = ["0-9", "10-19", "20-29", "30-39", "40-49", "50-59", "60-69", "70-79", "80+"]
    symptom = {"men": [], "women": []}
    for b in bands10:
        v3 = [float(x) / 1000 for x in r63["有訴者率 (symptom complaint) age %s, total/men/women" % b]["value"].split("/")]
        symptom["men"].append(round(v3[1], 4))
        symptom["women"].append(round(v3[2], 4))
    ratio = {b: float(r63["functional limitation: share-with / share-without ratio, age %s" % b]["value"]) for b in ["6-19", "20-29", "30-39", "40-49", "50-59", "60-69", "70-79", "80+"]}
    ratio10 = [ratio["6-19"], ratio["6-19"], ratio["20-29"], ratio["30-39"], ratio["40-49"], ratio["50-59"], ratio["60-69"], ratio["70-79"], ratio["80+"]]
    div_bands = ["<=19", "20-24", "25-29", "30-34", "35-39", "40-44", "45-49", "50-54", "55-59", "60-64"]
    divorce_wife = [float(r63["divorce rate per married persons, age %s, husband/wife" % b]["value"].split("/")[1]) for b in div_bands]
    nm = nums(rows[("2 marriage", "never married by age (men / women), %")]["value"])   # 25, 29, 76.4, 65.8, 30, 34, ...
    nm50 = nums(rows[("2 marriage", "never married at 50 (mean of 45-49 and 50-54)")]["value"])
    r64 = {r["name"]: float(r["value"]) for r in csv.DictReader(open(sys.argv[4], encoding="utf-8-sig"))}
    t64 = ["single", "couple_only", "couple_children", "single_parent"]
    def five(prefix):
        v5 = [r64[prefix + t] for t in t64] + [r64[prefix + "other_relatives"] + r64[prefix + "non_relative"]]
        tot5 = sum(v5)
        return [round(x / tot5, 5) for x in v5]
    age_keys = ["02_15～19歳", "03_20～24歳", "04_25～29歳", "05_30～34歳", "06_35～39歳", "07_40～44歳", "08_45～49歳", "09_50～54歳", "10_55～59歳", "11_60～64歳", "12_65～69歳", "13_70～74歳", "14_75～79歳", "15_80～84歳", "16_85歳以上"]
    age_bands = ["15-19", "20-24", "25-29", "30-34", "35-39", "40-44", "45-49", "50-54", "55-59", "60-64", "65-69", "70-74", "75-79", "80-84", "85+"]
    by_age = [five("national, householder age %s, " % k) for k in age_keys]
    pref_names = sorted({n.split(",")[0] for n in r64 if n[:2].isdigit() and n[2:5] == "000" and not n.startswith("00000")})
    by_pref = {n[:2]: five(n + ", ") for n in pref_names}
    lim_keys = ["6～ 9歳", "10～14", "15～19", "20～24", "25～29", "30～34", "35～39", "40～44", "45～49", "50～54", "55～59", "60～64", "65～69", "70～74", "75～79", "80～84", "85歳以上"]
    lim = {"from": [6, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55, 60, 65, 70, 75, 80, 85],
           "men": [round(r64["日常生活に影響のある者率, 男, age %s" % k] / 1000, 4) for k in lim_keys],
           "women": [round(r64["日常生活に影響のある者率, 女, age %s" % k] / 1000, 4) for k in lim_keys]}
    qrows = list(csv.DictReader(open(sys.argv[5], encoding="utf-8-sig")))
    qx2022 = {"men": [float(r["qx_male"]) for r in qrows], "women": [float(r["qx_female"]) for r in qrows]}
    prefs = json.load(open("data/modern/polity/jpn_prefectures.json", encoding="utf-8"))["prefectures"]
    size_by_pref = {code: float(r63["mean general-household size, %s" % v["name"]]["value"]) for code, v in prefs.items()}
    r66 = {r["name"]: r for r in csv.DictReader(open(sys.argv[6], encoding="utf-8-sig"))}

    def p66(name):
        r = r66[name]
        assert r["kind"] == "P", name
        return float(r["value"])

    def c66(name):
        r = r66[name]
        assert r["kind"] == "C", name
        return float(r["value"])

    ib = ["18-19", "20-24", "25-29", "30-34"]
    intend = {"bands": ib, "men": [round(p66("intend_to_marry_men_%s" % b) / 100, 4) for b in ib], "women": [round(p66("intend_to_marry_women_%s" % b) / 100, 4) for b in ib]}
    kb = ["20-24", "25-29", "30-34", "35-39", "40-44", "45-49"]
    kids = {"bands": kb, "all": {str(k): round(p66("couples_intended_share_%s" % ("5+" if k == 5 else k)) / 100, 4) for k in range(6)},
            "by_age": [{str(k): round(p66("couples_intended_share_%s_wife_%s" % ("5plus" if k == 5 else k, b)) / 100, 4) for k in range(6)} for b in kb],
            "n_by_age": [int(p66("couples_intended_n_wife_%s" % b)) for b in kb]}
    mfb = ["20-24", "25-29", "30-34", "35-39", "40-44"]
    fmb = [(25, 29), (30, 34), (35, 39)]
    mvb = ["20-24", "25-29", "30-34", "35-39", "40-44", "45-49", "50-54", "55-59", "60-64"]
    life = {
        "health_bands": {"value": bands10, "label": "10-year bands of 国民生活基礎調査 2022", "source": "R63 §6"},
        "symptom_rate": {"value": symptom, "label": "S (有訴者率 per person, 2022): grade 2+", "source": "R63 §6 (R62 e_kok22_04.txt:17-26)"},
        "limitation_odds_ratio": {"value": ratio10, "label": "D (R63: share-with / share-without by age; under 10 at the 6-19 ratio, T)", "source": "R63 §6 (e_kok22_04.txt:197-233)"},
        "limitation_rate": {"value": lim, "label": "S (日常生活に影響のある者率, 国民生活基礎調査 2022 第110表, per person; under 6 at 6-9's, T): grade 4 (§10.2 amendment 1)", "source": "R64 §2 (e-Stat statInfId 000040071882)"},
        "limitation_overall": {"value": 0.10, "label": "T (R63's 8-12%; walking alone 6.9% the floor)", "source": "§10.2"},
        "poor_share_of_rest": {"value": 1.0 / 3.0, "label": "T: grade 3 is a third of (grade 2+ - grade 4)", "source": "§10.2"},
        "grade_redraw_year": {"value": 0.3, "label": "T: a grade lasts about three years (no transition table: NF)", "source": "§10.2"},
        "medical_level": {"value": 1.0, "label": "T (2024 = 1; divides the grade 3-4 shares in the redraw)", "source": "§10.2"},
        "qx_2022": {"value": qx2022, "label": "S (令和4年簡易生命表, single years 0-105+; the last row stands for 105+)", "source": "R62 (R62_qx_2022.csv, c_life22_06.txt / c_life22_07.txt)"},
        "death_multiplier": {"value": [1.0, 1.29, 3.233, 5.03, 5.03], "label": "CALIBRATED (grades 1-4, current-grade hazard multipliers m0^lambda, m0 = [1, 1.2, 2.317, 3.18] (M010's pooled HRs: AGES 1B fair/poor SRH, D; x NIPPON DATA90 model 2, D; grade 2 T; T2.2c: 4b's m = 4a's, T, so that Tosa stays held out), lambda 1.3964 solved so that the HR by BASELINE grade over 4 years at 65+, grades moving on T2.2b's kernel, equals AGES 1B's pooled 2.317; under 65 T; both sexes)", "source": "M032b (math-reports 8eddecd1); M010 §3; R74 §4; TO_E 13:50"},
        "grade_kernel": {"value": {"stable_share": 0.535, "stable": {"good_stay": 0.989, "bad_stay": 0.914}, "mobile": {"good_stay": 0.803, "bad_stay": 0.443}, "within_stay": 0.7, "adl_stay": 0.525, "bad_stay_one_year": 0.604, "p_stable_given_side": {"good": 0.58, "bad": 0.33}, "care_exit": 0.0125}, "label": "D at 51-76 (R92's SRH paths by wave, M032's two-class fit: the classes' good-to-good and bad-to-bad one-year stays; grade 4's stay ADL any-to-any 0.525 x the class's bad stay / 0.604, D/T); T outside 51-76 (the same values); the within-side stay 0.7 T; P(stable | side) from the fit's stationary mix; care_exit, 4b's yearly exit to 4a, T within Sendai's D 0.5-2% (M034 §1)", "source": "R92 (research-notes 7700db47); M032 §2 (math-reports b64de03c); TO_E 13:47; M034 (math-reports 666e2642), R94; TO_E 17:14"},
        "ltci_share": {"value": ltci_share(sys.argv[7], sys.argv[8]), "label": "D (LTCI's April 2022 recipients, 要支援1-要介護5, home and institution, / the start's 2024 persons, by 5-year band x sex): grade 4b's prevalence; grade 4 raised to it where it is the larger (T2.2c)", "source": "R94 (research-notes c5ce5161, 介護給付費等実態統計 table 000040099769); data/modern/jpn/status_2024.json; M034 §1"},
        "death_income_factor": {"value": {"b0": 0.159550021637047, "b1": -0.016611385872074697, "a0": 75.0, "range": [67.0, 82.0], "tau2": 0.02165264764298906, "cov": [[0.005476667963836734, 2.3341142137501444e-05], [2.3341142137501448e-05, 0.0001353550384211957]]}, "label": "D (M010's form, M011's v2: I_q(a) = exp(0.5 q (b0 + b1 (clamp(a, 67, 82) - a0))), q = 0 top .. 3 bottom equivalized-income quartile in the 10-year band; b0, b1 the meta-regression with the declared prior over R73's main set by GLS with the AGES-JAGES overlap (rho 0.3, T), study families for the prior's rule and the Hartung-Knapp variance, transcribed from m010_pooled_inputs.py v2's output at 7ac5b83d; the pooled slope kept, the within-study fit reported (M011 (5)); the log-linear rank form T; AGES L1 left out (the open 生活保護 item); both sexes T)", "source": "M010 §1-§3 (aedecdef), M011 (math-reports 7ac5b83d); TO_E 03:53, 04:57"},
        "never_married": {"value": {"ages": [25, 30, 35, 40, 45], "men": [nm[2] / 100, nm[6] / 100, nm[10] / 100, nm[14] / 100, nm50[0] / 100], "women": [nm[3] / 100, nm[7] / 100, nm[11] / 100, nm[15] / 100, nm50[1] / 100]},
                          "label": "S (国勢調査 2020 表III-2; 45+ at the at-50 share, D): the start's one-person adults, an input", "source": "R62 §2"},
        "partnering": {"value": {"kappa": 0.015, "window": {"18": 0.3, "20": 1.0, "50": 0.5, "65": 0.2, "75": 0.0}, "gap": [-6, 10], "trait_compat": 0.5}, "label": "T (read as checks: HB5, HB5c, HB5d; §10.6 A1 the trait compatibility; §10.7 B1 one encounter a month, the 20 tries removed)", "source": "§10.2, §10.6"},
        "birth": {"value": {"kappa": 0.03, "fecundity": {"15": 0.4, "20": 1.0, "35": 0.7, "40": 0.3, "45": 0.03, "50": 0.0}, "gap_months": 12}, "label": "T (read as checks: HB3, HB3b); the want weights by parity replaced by the intended children (§10.6 A2)", "source": "§10.2, §10.6"},
        "leaving_home": {"value": {"kappa": 0.006, "earner_man_yen": 15.0, "earner": 1.5, "not_earner": 0.5, "student_at_18": 2.0}, "label": "T (read as checks: HB6)", "source": "§10.2"},
        "divorce_choice": {"value": {"kappa": 0.004, "money_line": 0.5, "money": 1.5, "young_child_age": 6, "young_child": 0.7, "early_m0": 4.0, "early_tau_years": 3.0}, "label": "T (§10.4: a choice; §10.6 A3: the early mismatch m0, tau; read as checks HB9a-c, never calibrated)", "source": "§10.4, §10.6"},
        "intend_to_marry": {"value": intend, "label": "P (R66 item 3: 出生動向基本調査 2021, unmarried 18-34 who intend to marry some day; 35+ at 30-34's, T): a START value of the inner state (§10.6 A1)", "source": "R66 (b_jnfs16_gaiyo.txt:766-770, b_jnfs16_r03.txt:88-153)"},
        "intended_children": {"value": kids, "label": "P (R66 item 1: JNFS16 2021 couples' intended children, D shares, 5+ read as 5): a START value (§10.6 A2), drawn by the wife's age band (§10.9; under 20 at 20-24's, 50+ at 45-49's, T; 20-24 rests on 35 couples); 'all' is the former one distribution, kept for the record", "source": "R66 f8ae79cc (b_jnfs16c_freq.md:4851-4879; e-Stat 7-1-2-2)"},
        "completed_parity": {"value": {"0": ch[1] / 100, "1": ch[3] / 100, "2": ch[5] / 100, "3": ch[7] / 100, "4": ch[9] / 100}, "label": "S (JNFS16 図表6-2, couples married 15-19 years; 4+ read as 4): the start's parity of women 35+ (A3-1)", "source": "R62 §2 (b_jnfs16_gaiyo.pdf p44)"},
        "divorce_children_with_mother": {"value": 0.85, "label": "T (as the start's single parents)", "source": "§10.2"},
        "moving_in": {"value": {"kappa": 0.01, "grade4": 2.0, "gap": [20, 45]}, "label": "T (read as checks: HB1c)", "source": "§10.2"},
        "institution": {"value": {"kappa": 0.006, "alone": 2.0, "with_others": 0.5, "from_age": 75}, "label": "T (read as checks: HB10)", "source": "§10.2"},
        "union_start_age": {"value": 29.7, "label": "S (the wife's mean first-marriage age, 2022): the start's couples began at the woman's age - 29.7 (T)", "source": "R62 §2"},
    }
    old65 = nums(rows[("4 care", "65+ family form")]["value"])
    tfr = nums(rows[("2 fertility", "age-specific TFR contributions 2022")]["value"])[-1]
    e0 = nums(rows[("3 mortality", "life table qx by single year 0-105+")]["value"])[-2:]
    fm = nums(rows[("2 marriage", "mean first-marriage age")]["value"])
    outp = nums(rows[("4 health", "通院者率 (in outpatient care) per 1,000 by age")]["value"])   # <10, 131, 10, 138, 20, 154, 30, 211, ...
    crude = nums(rows[("6 divorce", "divorces and crude rate")]["value"].split(";")[1])[0]
    uwp = nums(rows[("5 leaving home", "unmarried living with parents")]["value"])
    dshare = {k: float(r63["share of divorces, duration %s" % k]["value"]) / 100 for k in ["<5 years", "20-25 years", "25-30 years", "30-35 years", "35+ years"]}
    checks = {
        "alive_65plus": {"alone": round(old65[0] / 100, 4), "couple_only": round(old65[1] / 100, 4), "with_child": round(old65[2] / 100, 4), "tolerance": 0.05},
        "type_shares": {"value": type_shares, "tolerance": 0.03},
        "alone_cells": {"tolerance": 0.05, "note": "alone_share_by_band's S cells (15-44 and 65+)"},
        "mean_size": {"value": 2.21, "tolerance": 0.1},
        "tfr": {"value": tfr, "tolerance": 0.15},
        "births_by_mother_age": {"value": births_by_age, "tolerance": 0.05},
        "e0": {"men": e0[0], "women": e0[1], "tolerance": 1.0},
        "never_married_30_34": {"men": round(nm[6] / 100, 4), "women": round(nm[7] / 100, 4), "tolerance": 0.05},
        "first_marriage_age": {"men": fm[0], "women": fm[1], "tolerance": 1.5},
        "ever_left": {"18-19": left_home["18-19"], "20-24": left_home["20-24"], "25-29": left_home["25-29"], "tolerance": 0.07},
        "unmarried_with_parents_18_34": {"men": round(uwp[0] / 100, 4), "women": round(uwp[1] / 100, 4)},
        "outpatient": {"30s": round(outp[7] / 1000, 4), "40s": round(outp[9] / 1000, 4), "50s": round(outp[11] / 1000, 4), "ratio_tolerance": 0.3},
        "divorce_crude": {"value": crude, "tolerance": 0.3},
        "divorce_duration": {"under_5": round(dshare["<5 years"], 4), "20_plus": round(sum(v for k, v in dshare.items() if k != "<5 years"), 4), "tolerance": 0.07},
        "divorce_rate_wife": {"bands": div_bands, "per_1000": divorce_wife, "factor": 2.0, "from": "20-24", "to": "55-59"},
        "institution_women_85": {"value": 0.261},
        "remarriage_share": {"husbands": round(nums(rows[("6 remarriage", "share of marriages that are a remarriage")]["value"])[0] / 100, 4), "wives": round(nums(rows[("6 remarriage", "share of marriages that are a remarriage")]["value"])[1] / 100, 4), "tolerance": 0.07},
        "marital_fertility": {"bands": mfb, "per_1000": [c66("marital_fertility_all_orders_%s" % b) for b in mfb], "factor": 1.5, "year": 2015},
        "first_marriage_rate": {"bands": ["%d-%d" % b for b in fmb], "men": [round(sum(c66("first_marriage_rate_men_%d" % a) for a in range(b[0], b[1] + 1)) / 5, 2) for b in fmb],
                                "women": [round(sum(c66("first_marriage_rate_women_%d" % a) for a in range(b[0], b[1] + 1)) / 5, 2) for b in fmb], "factor": 1.5, "year": 2015},
        "movers_per_1000": {"bands": mvb, "per_1000": [c66("interpref_move_rate_japanese_both_%s" % b) for b in mvb], "factor": 2.0, "year": 2023},
    }
    life["prevalence_single_age"] = {"value": single_age_prevalence(life), "label": "D from the spec's own bands (M035 §3): grade 2+, grade 4 and 4b smoothed to single ages 0-100 by sex, a band-mean-preserving piecewise-linear logit, each band weighted by the 2022 table's survivors; LC.shares reads these", "source": "M035 (math-reports 587acffb); the spec's symptom_rate, limitation_rate, ltci_share, qx_2022; TO_E 17:51"}
    spec = {
        "note": "ISS households (ISS_HOUSEHOLD_REDESIGN.md §10.1): the start's household types and members. Labels S (published), D (derived), T (declared). Built by tools/modern/build_households_spec.py from R62 (research-notes 08153f0d).",
        "type_shares": {"value": type_shares, "label": "S", "source": "国勢調査 2020 図V-1-1 via R62 §1 (g_census20_outline01.txt:2106-2110)"},
        "mean_size": {"value": 2.21, "label": "S (a check, H1s-b)", "source": "国勢調査 2020 (g_census20_outline01.txt:917-923)"},
        "alone_share_by_band": {"value": {"bands": ["15-24", "25-34", "35-44", "45-54", "55-64", "65-74", "75-84", "85+"],
                                          "men": [0.185, 0.288, 0.170, 0.169, 0.168, 0.167, 0.127, 0.146],
                                          "women": [0.157, 0.197, 0.094, 0.120, 0.147, 0.173, 0.260, 0.256]},
                                "label": "S (表V-1-3) for 15-44 and 65+; T for 45-54 and 55-64 (linear between 35-44 and 65-74: R62 gives no 45-64 row)",
                                "source": "国勢調査 2020 表V-1-3 via R62 §1 (g_census20_outline01.txt:2336-2355)"},
        "couple_only_shape_men": {"value": {"bands": ["25-34", "35-44", "45-54", "55-64", "65-74", "75-84", "85+"], "share": [0.08, 0.06, 0.10, 0.25, 0.40, 0.40, 0.25]},
                                  "label": "T, PENDING the e-Stat 家族類型 x 年齢 table; anchored on R62's '65+ in a couple-only household 40.7%' (国民生活基礎調査 2022)",
                                  "source": "ISS_HOUSEHOLD_REDESIGN.md §10.1"},
        "mother_ages": {"value": [25, 59], "label": "T", "source": "the mother of an 'other' (three-generation) household is 25-59 at the start"},
        "parent_ages": {"value": {"from": 20, "redraws": 16}, "label": "T (§10.1 amendment 1)", "source": "the mother of a couple + children household and the single parent: 20 to the oldest age by the population, redrawn until a child is at home"},
        "partner_age_gap": {"value": {"mean": 2.0, "sd": 3.0}, "label": "T (R62: first-marriage ages 31.1 / 29.7, a gap of 1.4)", "source": "§10.1"},
        "children_given_any": {"value": children, "label": "D from S (JNFS16 図表6-2: 0 7.7, 1 19.7, 2 50.8, 3 18.6, 4+ 3.2%, renormalised without 0; 4+ read as 4)", "source": "R62 §2 (b_jnfs16_gaiyo.pdf p44)"},
        "births_by_mother_age": {"value": births_by_age, "label": "S/D (人口動態統計 2022 第4表; ≤19 read as 15-19, 45+ as 45-49)", "source": "R62 §2 (a_kakutei22_all.txt:1093-1111)"},
        "left_home_by_age": {"value": left_home, "label": "S (第8回世帯動態調査 2019 表8: ever left, men / women); 35+ held at 35-39 (T past 39)", "source": "R62 §5 (h_dotai8_gaiyo.txt:370-389)"},
        "single_parent_mother": {"value": 0.85, "label": "T", "source": "§10.1"},
        "grandparent": {"value": {"offset_mean": 28.0, "offset_sd": 4.0, "female": 0.75}, "label": "T", "source": "§10.1: the 'other' type built as three-generation"},
        "type_by_householder_age": {"value": {"bands": age_bands, "shares": by_age}, "label": "D from S (国勢調査 2020 第12-1表; other = other relatives + non-relatives)", "source": "R64 §1 (e-Stat statInfId 000032142504)"},
        "type_by_prefecture": {"value": by_pref, "label": "D from S (国勢調査 2020 第12-1表; other = other relatives + non-relatives)", "source": "R64 §1"},
        "mean_size_by_prefecture": {"value": size_by_pref, "label": "S (国勢調査 2020 表I-5-1; a start and monthly margin, ruling D)", "source": "R63 §4 (R62 g_census20_outline01.txt:1114-1161)"},
        "institution_start": {"value": {"bands": [[75, 84], [85, 200]], "men": [0.03, 0.13], "women": [0.05, 0.261]}, "label": "S for women 85+ (表V-1-3: 26.1%); T for the other three cells; none under 75 (NF)", "source": "§10.3 ruling A"},
        "householder_build": {"value": {"redraws": 16, "old_from": 60, "old_spouse": 0.6, "child_gap_mean": 28.0, "child_gap_sd": 4.0, "son": 0.75}, "label": "T (§10.1 amendment 5)", "source": "§10.1"},
        "life_course": {"value": life, "label": "§10.2", "source": "R62, R63"},
        "checks": {"value": checks,
                   "label": "S, CHECKS ONLY: every target the H1 and H2 checks read (ISS_CHECKS.md), with the tolerance declared there; never an input. alive_65plus 国民生活基礎調査 2022 表4 (R62 §4); TFR 人口動態統計 2022 第5表; e0 令和4年簡易生命表; first-marriage ages 月報年計 2022; never married 国勢調査 2020 表III-2; ever left home 世帯動態調査 2019 表8; unmarried with parents JNFS16; 通院者率 国民生活基礎調査 2022 表13; divorces 確定数 2022 and 離婚に関する統計 (2020 data; R63 §7)",
                   "source": "R62 (R62_households_lifecourse.csv), R63 (R63_household_redesign_gaps.csv)"},
    }
    open(sys.argv[2], "w", encoding="utf-8").write(json.dumps(spec, ensure_ascii=False, indent=1) + "\n")
    print("HOUSEHOLDS SPEC", type_shares, children, births_by_age, left_home)


if __name__ == "__main__":
    main()
