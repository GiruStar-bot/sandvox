"""data/modern/people/jpn_tiers_2024.json: the tiered population's start inputs (ISS_TIERED_POPULATION.md §12.2), each labelled.
S: the status cohort (via the status layer at run time), 表V-1-3's cells (R62), R64's types (via the households spec), R67a's tiers,
R67c's household instruments (F). D: the conditional shares H1's construction gives, tabulated once (h1tab@<commit>, 47 x 2,128,
seed 1) inside R69's complete 表V-1-3. R69: census 2020 labour status, the prefectures' broad age shares and labour totals. T: the class
applied uniformly by age, the shape inside each broad age group.
  python3 -I tools/modern/build_tiers_spec.py <h1tab json> <households spec json> <R62 csv> <R67a csv> <R67c csv> <R69 csv> <out json> [<R70 csv> [<R72 csv> [<R76 births csv> <R76 marital csv> <R76 LFS csv> [<R77 couples csv> <R77 single-age csv> <R77 couple-only csv> [<R83 csv> [<R84 relation csv> <R84 family-type csv> [<R85 csv>]]]]]]]"""
import csv, json, math, re, sys

TYPES = ["one_person", "couple_only", "couple_children", "single_parent", "other", "institution"]
EMP = ["not_in_labour_force", "regular", "non_regular", "unemployed", "student", "retired"]
ROLES = ["head", "partner", "child", "parent", "other"]
CLASSES = ["top_0_01", "top_0_1", "top_1", "top_10", "middle_40", "bottom_50", "none"]


def nums(text):
    return [float(x) for x in re.findall(r"(\d+(?:\.\d+)?)", text)]


def shares(counts):
    t = float(sum(counts))
    return [round(c / t, 6) if t > 0 else 0.0 for c in counts]


WAGE_BANDS = ["～１９歳", "２０～２４歳", "２５～２９歳", "３０～３４歳", "３５～３９歳", "４０～４４歳", "４５～４９歳", "５０～５４歳",
              "５５～５９歳", "６０～６４歳", "６５～６９歳", "７０歳～"]
PENSION_BANDS = ["６５～６９", "７０～７４", "７５～７９", "８０歳以上"]
KINDS = ["basic_only", "basic+kosei", "basic+kyosai", "basic+kosei+kyosai", "kosei_only", "kyosai_only", "other"]


def r70_blocks(r70):
    """§12.9 M1, M2, M4 from R70 (research-notes): the cash ratio of 賃金構造 2022, the pensions by entitlement, the earnings index"""
    by = {}
    for r in r70:
        by[(r["topic"], r["item"])] = r
    ratio = {}
    for typ in ("regular", "non_regular"):
        ratio[typ] = {}
        for sx, key in (("M", "male"), ("F", "female")):
            row = []
            for band in WAGE_BANDS:
                v = {m: float(by[("wage_2022", "%s %s %s %s" % (typ, sx, band, m))]["value"])
                     for m in ("monthly_kimatte_k", "monthly_shoteinai_k", "annual_bonus_k")}
                row.append(round((12.0 * v["monthly_kimatte_k"] + v["annual_bonus_k"]) / (12.0 * v["monthly_shoteinai_k"]), 6))
            ratio[typ][key] = row
    none = {}
    basic = {}
    for sx, key in (("M", "male"), ("F", "female")):
        none[key] = [round(float(by[("no_pension_share", "%s %s" % (sx, b))]["value"]) / 100.0, 6) for b in PENSION_BANDS]
        basic[key] = []
        for b in PENSION_BANDS:
            k = [float(by[("pension_kind_share", "%s %s %s" % (sx, b, kd))]["value"]) for kd in KINDS]
            basic[key].append(round(k[0] / sum(k), 6))

    def classes(topic, col):
        rows = [r for r in r70 if r["topic"] == topic and r["item"].startswith("monthly 10k yen")]
        out = []
        mean = None
        for r in rows:
            v = [float(x) for x in r["value"].split(" / ")]
            label = r["item"][len("monthly 10k yen "):].split(":")[0]
            if "平均" in label:
                mean = v[col]
            elif label not in ("total", "合計"):
                out.append(v[col])
        return out, mean
    def top_width(c, mean_yen):
        # the open last class's width (万円) that makes the piecewise-uniform mean the published mean (D), at least one class: where the
        # uniform classes alone already give the mean within the in-class shape's error (women's 厚生年金, 104,883 against 104,878 yen),
        # no width reaches it
        n = sum(c)
        inner = sum((i + 0.5) * x for i, x in enumerate(c[:-1]))
        return round(max(1.0, 2.0 * ((mean_yen / 1e4 * n - inner) / c[-1] - (len(c) - 1))), 6)
    kosei = {}
    kokumin = {}
    kosei_s = {}
    kokumin_s = {}
    for key, ck, cb in (("male", 1, 4), ("female", 2, 5)):
        c, m = classes("kosei_amount_class_fy2022", ck)
        kosei[key] = {"counts": c, "mean_yen": m, "top_width": top_width(c, m)}
        c2, m2 = classes("kokumin_amount_class_fy2022", cb)
        kokumin[key] = {"counts": c2, "mean_yen": m2, "top_width": top_width(c2, m2)}
        c3, m3 = classes("kosei_short_amount_class_fy2022", ck)
        kosei_s[key] = {"counts": c3, "mean_yen": m3, "top_width": top_width(c3, m3)}
        c4, m4 = classes("kokumin_short_amount_class_fy2022", cb)
        kokumin_s[key] = {"counts": c4, "mean_yen": m4, "top_width": top_width(c4, m4)}
    short = {}
    for key in ("male", "female"):
        short[key] = {"employee": round(sum(kosei_s[key]["counts"]) / (sum(kosei_s[key]["counts"]) + sum(kosei[key]["counts"])), 6),
                      "basic_only": round(sum(kokumin_s[key]["counts"]) / (sum(kokumin_s[key]["counts"]) + sum(kokumin[key]["counts"])), 6)}
    idx = {r["item"]: float(r["value"]) for r in r70 if r["topic"] == "wage_index" and r["label"] in ("S", "D") and " / " not in r["value"]}
    return {
        "wage_cash_ratio": {"value": {"bands_from": [15, 20, 25, 30, 35, 40, 45, 50, 55, 60, 65, 70], "regular": ratio["regular"], "non_regular": ratio["non_regular"]},
                            "label": "§12.9 M2: b = (12 x きまって支給 + 年間賞与) ÷ (12 x 所定内) by 5-year band x sex x 正社員 / 正社員以外, D from 賃金構造基本統計調査 2022 雇用形態別 第1表 (S, pub 2023-03-17; firms 10+, general workers); a ratio on the persons layer's own 所定内 table (the PM's option A)", "source": "R70 §3 (wage_2022)"},
        "pension_entitlement": {"value": {"bands_from": [65, 70, 75, 80], "none_share": none, "basic_only_share": basic,
                                          "short_record_share": short, "employee_classes": kosei, "basic_only_classes": kokumin,
                                          "employee_short_classes": kosei_s, "basic_only_short_classes": kokumin_s},
                                "label": "§12.9 M1: none = the survey's non-receipt share of known status (D, 国民生活基礎調査 2022 第063表, deferral included); basic_only = its share of the recipients' kinds renormalised to 100 (multiple answers, D); every other kind takes the 厚生年金 (第1号) amount classes (D: 共済 unified 2015); each kind is a mixture of its 25-year+ table and its short-record (通算老齢・25年未満) table, short_record_share = the short-record holders among the kind's holders by sex (D from 事業の概況 FY2022 counts, R70b); the amount classes per 1 万円 a month by sex (S, 事業の概況 FY2022; 厚生年金's include the basic pension), the last class open with the width that gives the published mean, at least one class (D)", "source": "R70 §2"},
        "hh_income_index_2021_2022": {"value": idx["multiplier 2021 -> 2022"], "label": "§12.9 M4: 毎月勤労統計 現金給与総額 index 2021 100.3 -> 2022 102.3 (D from S, 令和4年分 確報); T1s-hi's 2021 targets brought to 2022", "source": "R70 §4"},
    }


R70_WIFE_BANDS = ["1_30歳未満", "2_30～39歳", "3_40～49歳", "4_50～59歳", "5_60～69歳", "6_70歳以上"]


def r70_couple_blocks(r70):
    """§14.2c (4) from R70 §1: the wives' employment by the husband's income class and the wife's age band, and the both-earning Spearman ρ"""
    rows = [r for r in r70 if r["topic"] == "wife_emp_by_husband_income"]
    edges, couples, employed = [], [], []
    for b in R70_WIFE_BANDS:
        cs, es, ed = [], [], []
        for r in sorted([r for r in rows if r["item"].startswith("wife age %s," % b)], key=lambda r: r["item"]):
            note = dict(kv.split("=") for kv in r["note"].split() if "=" in kv)
            cs.append(int(note["couples"]))
            es.append(int(note["wife_employed"]))
            cls = r["item"].split("husband income ")[1].split("_", 1)[1]
            ed.append(0.0 if cls.endswith("未満") else nums(cls)[0])
        assert len(cs) == 16, (b, len(cs))
        couples.append(cs)
        employed.append(es)
        edges = ed
    rho = []
    for b in R70_WIFE_BANDS:
        r = [r for r in r70 if r["topic"] == "couple_corr" and r["item"].startswith("wife_age %s:" % b) and "Spearman" in r["item"]]
        assert len(r) == 1, b
        rho.append(float(r[0]["value"]))
    return {
        "couple_wife_employment": {"value": {"wife_band_from": [0, 30, 40, 50, 60, 70], "class_from_man_yen_year": edges, "couples": couples,
                                             "wife_employed": employed},
                                   "label": "§14.2c (4): couples and employed wives by the husband's annual income class from his main job (16 classes, the lower edges in 万円 a year) and the wife's age band, D from 就業構造基本調査 2022 第240-2表 (S, pub 2023-07-21); the seed's odds ratio is the class's odds of an employed wife over the band's all-classes odds; a husband with no work income takes the first class (TO_E 03:24 (b), T until R76)", "source": "R70 §1 (wife_emp_by_husband_income)"},
        "couple_spearman_both_earn": {"value": {"wife_band_from": [0, 30, 40, 50, 60, 70], "rho_s": rho},
                                      "label": "§14.2c (4): Spearman ρ of the two incomes among couples where both earn, by the wife's age band (D, class mid-points, R70 §1); the Gaussian copula's form T, Pearson ρ = 2 sin(π ρ_S ÷ 6)", "source": "R70 §1 (couple_corr)"},
    }


LFS_WIFE_BANDS = ["妻15～24歳", "妻25～34歳", "妻35～44歳", "妻45～54歳", "妻55～64歳", "妻65歳以上"]


def r76_blocks(births, marital, lfs):
    """§14.2c (2), (6) and (b) from R76: the births' month shares by year, the marital state by prefecture x sex x 5-year band, and the
    wives' work when the husband is not at work"""
    years = sorted(set(int(r["year"]) for r in births))
    shares = []
    for y in years:
        by = {int(r["month"]): int(r["value"]) for r in births if int(r["year"]) == y and r["measure"] == "births" and r["month"] != "total"}
        assert sorted(by) == list(range(1, 13)), y
        tot = float(sum(by.values()))
        shares.append([round(by[m] / tot, 8) for m in range(1, 13)])
    bands = ["%02d_%d～%d歳" % (i + 1, 15 + 5 * i, 19 + 5 * i) for i in range(17)] + ["18_100歳以上"]
    states = ["1_未婚", "2_有配偶", "3_死別", "4_離別"]
    cell = {}
    for r in marital:
        cell[(r["area"], r["sex"], r["marital"], r["age"])] = int(r["persons"].replace(",", "") or 0)
    by_pref = {}
    for code in range(1, 48):
        area = [a for a in set(k[0] for k in cell) if a.startswith("%02d000_" % code)]
        assert len(area) == 1, code
        rows = []
        for sx in ["1_男", "2_女"]:
            srow = []
            for b in bands:
                v = [cell.get((area[0], sx, st, b), 0) for st in states]
                tot = float(sum(v))
                srow.append([round(x / tot, 6) if tot > 0 else 0.0 for x in v])
            rows.append(srow)
        by_pref[str(code)] = rows
    def lfs_cell(age, level, wst, hst):
        r = [x for x in lfs if x["sheet"] == "1" and x["wife_age"] == age and x["wife_level"] == level and x["wife_status"] == wst and x["husband_status"] == hst]
        assert len(r) == 1, (age, level, wst, hst)
        v = r[0]["value_10k_households"]
        return 0.0 if v == "-" else float(v)
    odds_ratio = []
    for age in LFS_WIFE_BANDS:
        all_c = lfs_cell(age, "2", age, "総数")
        all_e = lfs_cell(age, "4", "就業者", "総数")
        no_c = lfs_cell(age, "2", age, "失業者") + lfs_cell(age, "2", age, "非労働力人口")
        no_e = lfs_cell(age, "4", "就業者", "失業者") + lfs_cell(age, "4", "就業者", "非労働力人口")
        if no_c <= 0.0:
            odds_ratio.append(1.0)
            continue
        ra, rn = all_e / all_c, no_e / no_c
        odds_ratio.append(round((rn / (1.0 - rn)) / (ra / (1.0 - ra)), 6) if 0.0 < rn < 1.0 else 1.0)
    return {
        "birth_month_shares": {"value": {"years": years, "shares": shares},
                               "label": "§14.2c (2): live births by month of birth over the year's births (S, 人口動態統計 2022 確定数 上巻 出生 第4.2表, pub 2023-09-15); a cohort without its year's row takes the nearer listed year, the earlier on a tie, before 1947 1947's (D; TO_E 03:40 (1))", "source": "R76 (i)"},
        "marital_by_pref_sex_band": {"value": {"band_from": [15 + 5 * i for i in range(18)], "states": ["never_married", "married", "widowed", "divorced"], "by_pref": by_pref},
                                     "label": "§14.2c (6): the shares of the known states by prefecture x sex (men, women) x 5-year band 15-19 .. 95-99, 100+ (S, 国勢調査 2020 人口等基本集計 第4-3表, pub 2021-11-30); 不詳 left out, so the known states share it in proportion (D); single ages flat within a band (D, no national single-age profile in R76; TO_E 03:40 (2))", "source": "R76 (ii)"},
        "couple_wife_work_husband_not_at_work": {"value": {"wife_band_from": [15, 25, 35, 45, 55, 65], "odds_ratio": odds_ratio},
                                                 "label": "§14.2c (b): the odds of an employed wife when the husband is unemployed or out of the labour force over the odds among all couples, by the wife's age band (D from S, 労働力調査 詳細集計 2022 年平均 第V-1表, pub 2023-02-14; TO_E 03:40 (3), in place of the T row); a band with no such couples, or a rate of 0 or 1, takes 1 (T)", "source": "R76 (iii)"},
    }


R77_BANDS = ["%d-%d" % (15 + 5 * i, 19 + 5 * i) for i in range(14)] + ["85+"]
R77_COARSE = ["1_60歳未満", "2_60～64歳", "3_65～69歳", "4_70～74歳", "5_75～79歳", "6_80～84歳", "7_85歳以上"]


def r77_blocks(couples, single, coupleonly, marital):
    """§12.12 from R77 (国勢調査 2020 第17-1表 and 第32表) and R76's population by prefecture x sex x band (the shares' denominators)"""
    num = lambda s: int(str(s).replace(",", "") or 0)
    by_pref = {}
    for code in range(0, 48):
        area = [a for a in set(r["area"] for r in couples) if a.startswith("%02d000_" % code)]
        assert len(area) == 1, code
        tab = [[0] * 15 for _ in range(15)]
        for r in couples:
            if r["area"] == area[0]:
                tab[R77_BANDS.index(r["husband_band"])][R77_BANDS.index(r["wife_band"])] = num(r["couples"])
        by_pref[str(code)] = tab
    ages = list(range(15, 86))
    sing = [[0] * 71 for _ in range(71)]
    for r in single:
        ha = int(r["husband_age"].replace("歳以上", "").replace("歳", ""))
        wa = int(r["wife_age"].replace("歳以上", "").replace("歳", ""))
        sing[ha - 15][wa - 15] = num(r["couples"])
    co = {}
    for code in range(0, 48):
        area = [a for a in set(r["area"] for r in coupleonly) if a.startswith("%02d000_" % code)]
        assert len(area) == 1, code
        tab = [[0] * 7 for _ in range(7)]
        for r in coupleonly:
            if r["area"] == area[0] and r["husband_age"] in R77_COARSE and r["wife_age"] in R77_COARSE:
                tab[R77_COARSE.index(r["husband_age"])][R77_COARSE.index(r["wife_age"])] = num(r["couple_only_households"])
        co[str(code)] = tab
    pop = {}
    bands = ["%02d_%d～%d歳" % (i + 1, 15 + 5 * i, 19 + 5 * i) for i in range(14)]
    for code in range(0, 48):
        area = [a for a in set(r["area"] for r in marital) if a.startswith("%02d000_" % code)]
        assert len(area) == 1, code
        rows = []
        for sx in ["1_男", "2_女"]:
            row = []
            for b in bands:
                row.append(sum(num(r["persons"]) for r in marital if r["area"] == area[0] and r["sex"] == sx and r["marital"] == "0_総数" and r["age"] == b))
            row.append(sum(num(r["persons"]) for r in marital if r["area"] == area[0] and r["sex"] == sx and r["marital"] == "0_総数" and r["age"] in ("15_85～89歳", "16_90～94歳", "17_95～99歳", "18_100歳以上")))
            rows.append(row)
        pop[str(code)] = rows
    return {
        "couples_by_age": {"value": {"band_from": [15 + 5 * i for i in range(15)], "by_pref": by_pref, "single_ages_from": 15, "single_national": sing},
                           "label": "§12.12: couples in general households by the husband's x the wife's 5-year band (15-19 .. 80-84, 85+), national ('0') and 47 prefectures (D, sums of S single ages), and the national single ages 15 .. 84, 85+ (S); 国勢調査 2020 人口等基本集計 第17-1表 (statInfId 000032142538, pub 2021-11-30)", "source": "R77 §1"},
        "couple_only_by_age": {"value": {"coarse_from": [0, 60, 65, 70, 75, 80, 85], "by_pref": co},
                               "label": "§12.12 (3): couple-only households by the husband's x the wife's coarse band (under 60, 60-64 .. 80-84, 85+), national ('0') and prefectures (S, 国勢調査 2020 第32表, statInfId 000032142673, pub 2021-11-30)", "source": "R77 §1"},
        "population_2020_by_pref_sex_band": {"value": {"band_from": [15 + 5 * i for i in range(15)], "by_pref": pop},
                                             "label": "§12.12 (1), T1s-w: 国勢調査 2020's persons 15+ by prefecture x sex (men, women) x 5-year band 15-19 .. 80-84, 85+ (S, 人口等基本集計 第4-3表 総数, R76)", "source": "R76 (ii)"},
    }


def r72_blocks(r72, r70):
    """§12.9 M1b, M1c from R72 (research-notes): the survivors' pensions and 生活保護 at the start"""
    by = {(r["topic"], r["item"]): float(r["value"]) for r in r72 if re.fullmatch(r"-?\d+(\.\d+)?", r["value"].strip())}
    age = lambda b: by[("survivor_kosei_age_fy2021", "厚生年金(第1号) 遺族年金 right holders age " + b)]
    holders = [age("65～69"), age("70～74"), age("75～79"), age("80～84") + age("85～89") + age("90歳以上")]
    kinds = {(r["item"].split()[0], r["item"].split()[1], r["item"].split()[2]): float(r["value"]) for r in r70 if r["topic"] == "pension_kind_share"}
    kosei_only = [round(kinds[("F", b, "kosei_only")] / sum(kinds[("F", b, k)] for k in KINDS), 6) for b in PENSION_BANDS]
    return {
        "survivors": {"value": {"bands_from": [65, 70, 75, 80], "right_holders": holders,
                                "recipient_ratio": round(by[("survivor_total_fy2022", "厚生年金(第1号) survivors' benefit (遺族給付) recipients")] / age("合計"), 6),
                                "mean_yen": by[("survivor_mean_fy2022", "厚生年金(第1号) 遺族年金 recipients' mean monthly amount")],
                                "women_kosei_only_share": kosei_only},
                      "label": "§12.9 M1b: 遺族厚生年金 right holders by band (年報 FY2021, S) x recipients ÷ right holders (5.77 M FY2022 ÷ 6.07 M, D); the paid mean (概況 FY2022, S; the spread NF); all to women (by sex NF, T: a widower's entitlement is narrow); the women's 厚生-only share of the kinds by band (国民生活基礎調査 2022, D) counts the survivors already in R70's kinds", "source": "R72 §1, R70 §2a"},
        "protection": {"value": {"elderly_households": by[("seikatsu_hogo_2021", "elderly households")],
                                 "minimum_yen": by[("seikatsu_hogo_2021", "per household per month: minimum cost of living, total (最低生活費)")]},
                       "label": "§12.9 M1c: 被保護者調査 July 2021 (S): the elderly protected households, applied to the 65+ one-person households as an upper bound (D), and the protected households' mean minimum cost of living (housing included; medical and care aid in kind left out)", "source": "R72 §2"},
    }


AGE_OPEN = {"14歳以下": (10, 15), "19歳以下": (15, 20), "45歳以上": (45, 50), "50歳以上": (50, 55), "75歳以上": (75, 80)}


def age_span(label):
    """an age label of R83 as [lo, hi): a 5-year group, a single age, or an open group (D)"""
    if label in AGE_OPEN:
        return AGE_OPEN[label]
    n = [int(x) for x in re.findall(r"\d+", label.translate(str.maketrans("０１２３４５６７８９", "0123456789")))]
    if len(n) == 2:
        return (n[0], n[1] + 1)
    return (n[0], n[0] + 1)


def pct(groups, q):
    """the q-quantile of the births over [lo, hi) groups, linear inside each group"""
    groups = sorted(groups)
    tot = sum(n for _, _, n in groups)
    acc = 0.0
    for lo, hi, n in groups:
        if n > 0 and acc + n >= q * tot:
            return round(lo + (hi - lo) * (q * tot - acc) / n, 4)
        acc += n
    return float(groups[-1][1])


def r83_block(r83):
    """§12.12 (5) R83's child window: per year the 1st-99th percentile of mother's age at birth (first births from 1970, all births
    before), and 2022's fathers at first births to married parents"""
    skip = ("総数", "不詳")
    by = {}
    for r in r83:
        if r["table"] == "series_mother_5y" and r["mother_age"] not in skip:
            by.setdefault(("all", int(r["year"])), []).append(age_span(r["mother_age"]) + (float(r["births"]),))
        if r["table"] == "series_order_mother_5y" and r["birth_order"] == "第1子" and r["mother_age"] not in skip:
            by.setdefault(("first", int(r["year"])), []).append(age_span(r["mother_age"]) + (float(r["births"]),))
    years = sorted(set(y for _, y in by))
    rows = []
    shares = []
    for y in years:
        kind = "first" if ("first", y) in by else "all"
        g = by[(kind, y)]
        rows.append([y, kind, pct(g, 0.01), pct(g, 0.99)])
        t = sum(n for _, _, n in g)
        shares.append([[lo, hi, round(n / t, 6)] for lo, hi, n in sorted(g)])
    fa = [age_span(r["father_age"]) + (float(r["births"]),) for r in r83 if r["table"] == "2022_mother_x_father_legit"
          and r["birth_order"] == "第1子" and r["mother_age"] == "総数" and r["father_age"] not in skip]
    ft = sum(n for _, _, n in fa)
    return {"child_window": {"value": {"mother": rows, "father": [pct(fa, 0.01), pct(fa, 0.99)], "mother_shares": shares,
                                       "father_shares": [[lo, hi, round(n / ft, 6)] for lo, hi, n in sorted(fa)]},
                             "label": "§12.12 (5): per birth year the 1st-99th percentile of mother's age at birth (first births 第1子 from 1970, all births before; linear inside each age group, open groups as declared, D), and the father's at 2022's first births to married parents (D, the only father table); from S counts",
                             "source": "R83 (人口動態統計 2022 確定数 上巻 第4.6表, 第4.17表; 中巻 第8表)"}}


def r84_block(rel, fam):
    """§12.12 (9) R84: per prefecture (and '0' national) the head's spouses, the children's spouses by sex x R77 band (15-19 .. 85+),
    the head's (and spouse's) parents who are men by R77 band, and the two-couple households (夫婦と両親 + 夫婦，子供と両親; the upper
    bound adds 夫婦，(子供，)親と他の親族)"""
    out = {}
    def key(area):
        return str(int(area[:2]))
    def band(age):
        k = int(age[:2]) - 4
        return min(k, 14) if 0 <= k <= 17 else -1
    for r in rel:
        if r["family_type"] != "0_総数" or not r["age"][:2].isdigit():
            continue
        p = out.setdefault(key(r["area"]), {"head_spouses": 0, "child_spouse_m": [0] * 15, "child_spouse_f": [0] * 15, "parents_m": [0] * 15,
                                               "two_couple_low": 0, "two_couple_high": 0})
        n = int(float(r["persons"]))
        if r["relation"] == "02_配偶者" and r["sex"] == "0_総数" and r["age"] == "00_総数":
            p["head_spouses"] = n
        b = band(r["age"])
        if b < 0:
            continue
        if r["relation"] == "04_子の配偶者" and r["sex"] in ("1_男", "2_女"):
            p["child_spouse_m" if r["sex"] == "1_男" else "child_spouse_f"][b] += n
        if r["relation"] in ("05_世帯主の父母", "06_世帯主の配偶者の父母") and r["sex"] == "1_男":
            p["parents_m"][b] += n
    for r in fam:
        p = out.get(key(r["area"]))
        if p is None:
            continue
        n = int(float(r["households"]))
        if r["family_type"] in ("1201_夫婦と両親から成る世帯", "1203_夫婦，子供と両親から成る世帯"):
            p["two_couple_low"] += n
            p["two_couple_high"] += n
        if r["family_type"] in ("1207_夫婦，親と他の親族（子供を含まない）から成る世帯", "1208_夫婦，子供，親と他の親族から成る世帯"):
            p["two_couple_high"] += n
    return {"nonhead_couples": {"value": {"bands_from": [15 + 5 * b for b in range(15)], "by_pref": out},
                                "label": "§12.12 (9): the head's spouses, the children's spouses by sex x 5-year band (85+ open), the head's and spouse's parents who are men by band, and the two-couple households (夫婦と両親 + 夫婦，子供と両親; the upper bound adds 夫婦，(子供，)親と他の親族), national ('0') and prefectures (S counts; the couples by position they imply are D)",
                                "source": "R84 (国勢調査 2020 人口等基本集計 第13-2表, 第12-1表; pub 2021-11-30)"}}


def r85_block(r85):
    """T1s-lp, T1s-gapm (R85): nationally, the share living with a parent by sex x 5-year band (15-19 .. 65-69) x marital (never
    married, married), the undeterminable left out; and the couple households whose youngest child is under 18 by the wife's band
    (15-19 .. 60-64, 65+)"""
    lp = {}
    for r in r85:
        if r["table"] != "living_with_parent" or not r["area"].startswith("00000") or r["sex"] not in ("1_男", "2_女"):
            continue
        if r["marital"] not in ("1_未婚", "2_有配偶") or not r["age"][:2].isdigit():
            continue
        b = int(r["age"][:2]) - 4
        if b < 0 or b > 10:
            continue
        k = (r["sex"][0], r["marital"][0], b)
        e = lp.setdefault(k, {})
        e[r["category"]] = float(r["value"])
    share = {"men": {"never": [0.0] * 11, "married": [0.0] * 11}, "women": {"never": [0.0] * 11, "married": [0.0] * 11}}
    for (sx, mr, b), e in lp.items():
        den = e.get("0_総数", 0.0) - e.get("3_同居しているか否か判定できない者", 0.0)
        share["men" if sx == "1" else "women"]["never" if mr == "1" else "married"][b] = round(e.get("2_同居している", 0.0) / den, 6) if den > 0 else 0.0
    young = ["youngest %s | oldest 0_総数" % c for c in ("1_0歳", "2_1～2歳", "3_3～5歳", "4_6～8歳", "5_9～11歳", "6_12～14歳", "7_15～17歳")]
    hh = [0.0] * 11
    for r in r85:
        if r["table"] == "wife_age_x_child_age" and r["category"] == "0_総数" and r["child_age"] in young and r["age"][:2] != "00":
            hh[int(r["age"][:2]) - 1] += float(r["value"])
    return {"coresident": {"value": {"band_from": [15 + 5 * b for b in range(11)], "living_with_parent": share,
                                     "wife_band_from": [15 + 5 * b for b in range(11)], "young_child_households": hh},
                           "label": "T1s-lp, T1s-gapm: the share living with a parent by sex x band x marital (never married, married), the undeterminable left out (S counts, 第49-2表; whether 親 includes the spouse's parents is R85's CHECK); couple households whose youngest child is under 18 by the wife's band, the last band 65+ (S, 第15-5表)",
                           "source": "R85 (国勢調査 2020 就業状態等基本集計 第49-2表; 人口等基本集計 第15-5表)"}}


def m016_blocks(rel, r85):
    """§12.13 (M016, TO_E 13:31): per prefecture (and '0' national) the private households' 子 by sex x 5-year band (0-4 .. 85+) as
    [all, in a nuclear household, the band's private-household persons, its persons in nuclear households, in non-nuclear ones]
    (第13-2表); nationally the persons living with a parent by
    sex x 5-year band (15-19 .. 85+) x marital (never married, married, widowed, divorced) as [in a nuclear household, in another,
    all of the marital state, undeterminable] (第49-2表)"""
    cr = {}
    for r in rel:
        if r["sex"] not in ("1_男", "2_女") or not r["age"][:2].isdigit():
            continue
        b = int(r["age"][:2]) - 1
        if b < 0 or b > 20 or r["family_type"] not in ("0_総数", "11_核家族世帯", "12_核家族以外の世帯"):
            continue
        p = cr.setdefault(str(int(r["area"][:2])), {"m": [[0, 0, 0, 0, 0] for _ in range(18)], "f": [[0, 0, 0, 0, 0] for _ in range(18)]})
        e = p["m" if r["sex"] == "1_男" else "f"][min(b, 17)]
        n = int(float(r["persons"]))
        if r["relation"] == "03_子" and r["family_type"] != "12_核家族以外の世帯":
            e[0 if r["family_type"] == "0_総数" else 1] += n
        elif r["relation"] == "00_総数":
            e[{"0_総数": 2, "11_核家族世帯": 3, "12_核家族以外の世帯": 4}[r["family_type"]]] += n
    cat = {"21_核家族世帯で同居": 0, "22_その他の世帯で同居": 1, "0_総数": 2, "3_同居しているか否か判定できない者": 3}
    lm = {"m": [[[0.0] * 4 for _ in range(4)] for _ in range(15)], "f": [[[0.0] * 4 for _ in range(4)] for _ in range(15)]}
    for r in r85:
        if r["table"] != "living_with_parent" or not r["area"].startswith("00000") or r["sex"] not in ("1_男", "2_女"):
            continue
        if r["marital"][0] not in "1234" or not r["age"][:2].isdigit() or r["category"] not in cat:
            continue
        b = int(r["age"][:2]) - 4
        if b < 0 or b > 17:
            continue
        lm["m" if r["sex"] == "1_男" else "f"][min(b, 14)][int(r["marital"][0]) - 1][cat[r["category"]]] += float(r["value"])
    return {"child_role": {"value": {"band_from": [5 * b for b in range(18)], "by_pref": cr},
                           "label": "§12.13 L: the private households' 子 (世帯主との続き柄) by sex x 5-year band (85+ open) as [all, in a nuclear household, the band's private-household persons, its persons in nuclear households, in non-nuclear ones], national ('0') and prefectures (S counts, 2020)",
                           "source": "R84 (国勢調査 2020 人口等基本集計 第13-2表, statInfId 000032142511, pub 2021-11-30)"},
            "coresident_marital": {"value": {"band_from": [15 + 5 * b for b in range(15)], "marital": ["never married", "married", "widowed", "divorced"],
                                             "columns": ["with a parent, nuclear", "with a parent, other", "all", "undeterminable"], "men": lm["m"], "women": lm["f"]},
                                   "label": "§12.13 L's marital split: persons by sex x 5-year band (85+ open) x marital, living with a parent in a nuclear / another household, all, undeterminable, national (S counts, 2020; the split applied to 2024 is D)",
                                   "source": "R85 (国勢調査 2020 就業状態等基本集計 第49-2表, statInfId 000032201427, pub 2022-05-27)"}}


def m022_block(r64, r84rel, couples, r86):
    """§12.16 (3), M022 (math-reports 3c61479c, TO_E 18:00): the 2020 within-couple shares of couple-only (s1) and couple + children
    (s2) households by the householder's = the husband's band (T), national: R64's householder-age shares x 第13-2表's heads, each
    type scaled to census 2020's count, over R77's couples by husband band; and IPSS 2018's 'other' ratio 2024 / 2020"""
    bands = R77_BANDS
    r64s = {}
    for r in r64:
        name = r["name"]
        if not name.startswith("national, householder age "):
            continue
        age, kind = name[len("national, householder age "):].split(", ")
        i = int(age[:2]) if age[:2].isdigit() else 0
        if 2 <= i <= 16:
            r64s[(bands[i - 2], kind)] = float(r["value"]) / 100
    heads = dict.fromkeys(bands, 0.0)
    for r in r84rel:
        if r["area"].startswith("00000") and r["sex"] == "0_総数" and r["family_type"] == "0_総数" and r["relation"] == "01_世帯主" and r["age"][:2].isdigit():
            i = int(r["age"][:2])
            if 4 <= i <= 21:
                heads[bands[min(i - 4, 14)]] += float(r["persons"])
    c20 = dict.fromkeys(bands, 0.0)
    for r in couples:
        if r["area"].startswith("00000_"):
            c20[r["husband_band"]] += float(str(r["couples"]).replace(",", "") or 0)
    ip = {}
    for r in r86:
        if r["area"] == "national" and r["householder"] == "all" and r["age"] == "all":
            ip[(r["edition"], r["year"], r["type"])] = float(r["households_1000"]) * 1000
    out = {}
    for kind, t in (("couple_only", "s1"), ("couple_children", "s2")):
        h = {b: r64s.get((b, kind), 0.0) * heads[b] for b in bands}
        z = ip[("census 2020", "2020", kind)] / sum(h.values())
        out[t] = [h[b] * z / c20[b] if c20[b] else 0.0 for b in bands]
    out["other_ratio"] = ip[("2018 national", "2024", "other")] / ip[("2018 national", "2020", "other")]
    return {"m022_within_couple": {
        "value": dict(out, band_from=[15 + 5 * i for i in range(15)]),
        "label": "§12.16 (3) M022: the 2020 national within-couple shares by husband band of couple-only (s1) and couple + children (s2) households (R64's householder-age type shares x 第13-2表's heads, each scaled to census 2020's type count, over R77's couples; D; T: the householder is the husband), raked per prefecture in T1 to its census 2020 counts; type 4 = 1 - s1 - s2; other_ratio = IPSS 2018's 'other' 2024 / 2020 for the single-headed 'other' households (T: the same rate as the couple-headed)",
        "source": "R64 (第12-1表), R84 (第13-2表), R77 (第17-1表), R86 (IPSS 2018)"}}


def r90_block(res, cen):
    """§12.16 (4) (TO_E 18:05): the immigration part, 在留外国人統計 2023-06 - 2020-12 by prefecture x sex x 5-year band 15-19 .. 85+
    (85+ absent, 0), and census 2020's foreigners' marital shares by sex x band (第46表, the unknown pro rata)"""
    bands = R77_BANDS
    imm = {}
    for r in res:
        code = int(r["prefecture"][:2])
        sx = 0 if r["sex"].endswith("男") else (1 if r["sex"].endswith("女") else -1)
        if code > 47 or sx < 0 or r["age"] not in bands:
            continue
        row = imm.setdefault(str(code), [[0.0] * 15, [0.0] * 15])
        row[sx][bands.index(r["age"])] += float(r["persons"]) * (1 if r["year_month"] == "2023-06" else -1)
    assert len(imm) == 47
    imm["0"] = [[sum(imm[str(c)][sx][b] for c in range(1, 48)) for b in range(15)] for sx in range(2)]
    sh = [[[0.0] * 5 for _ in range(15)] for _ in range(2)]
    for r in cen:
        if not r["area"].startswith("00000") or r["nationality"] != "1_外国人" or r["sex"] not in ("1_男", "2_女"):
            continue
        i = int(r["age"][:2]) if r["age"][:2].isdigit() else 0
        m = int(r["marital"][0])
        if 1 <= i <= 17 and 1 <= m <= 5:
            sh[0 if r["sex"] == "1_男" else 1][min(i - 1, 14)][m - 1] += float(r["persons"])
    shares = [[[x[k] / sum(x[:4]) if sum(x[:4]) > 0 else 0.0 for k in range(4)] for x in s2] for s2 in sh]
    return {"immigration_2020_2023": {
        "value": {"band_from": [15 + 5 * i for i in range(15)], "by_pref": imm, "marital_shares": shares},
        "label": "§12.16 (4) R90: the residual's immigration part, 在留外国人統計 2023-06 - 2020-12 by prefecture ('0' the sum) x sex x 5-year band 15-19 .. 85+ (D; the same band at both dates, T; 85+ absent, 0), and census 2020's foreigners' shares [never married, married, widowed, divorced] by sex x band (第46表, the unknown pro rata, D); the net 15+ arrivals (+0.32 M) are at most about 12% of M021's +2.66 M residual, so the rest (2020's age-unknown persons) stays T (TO_E 18:40)",
        "source": "R90 (在留外国人統計 000032104608 / 000040124405; 国勢調査 2020 第46表 000032142712)"}}


def r75_block(rows):
    """§14.6 (2), M009 (3): the mortality path's ratio q_IPSS(a, s, t) / q_IPSS(a, s, 2022) by variant x year 2023 .. 2035 x sex x single
    age 0 .. 100 (100 the open 100+, read at IPSS's age 100, D)"""
    q = {}
    for r in rows:
        if r["age"].isdigit() and int(r["age"]) <= 100:
            q[(r["variant"], int(r["year"]), r["sex"], int(r["age"]))] = float(r["qx"])
    years = list(range(2023, 2036))
    out = {}
    for v in ("medium", "high", "low"):
        out[v] = {}
        for sx in ("M", "F"):
            out[v][sx] = [[q[(v, y, sx, a)] / q[(v, 2022, sx, a)] for a in range(101)] for y in years]
    return {"mortality_ratio_ipss_2023": {
        "value": {"base_year": 2022, "years": years, "ages": 101, "by_variant": out},
        "label": "§14.6 (2), M009 (3), R75 (TO_E 03:30): the tiers' q_x(a, s, t) = the observed 2022 table x this ratio, IPSS 2023 medium's q(t) / q(2022) at the same single age and sex (PROJECTION; high and low the input band for years 5 and 10); 100 the open 100+ at IPSS's age 100 (D)",
        "source": "R75 (国立社会保障・人口問題研究所 日本の将来推計人口 令和5年推計 表7, 7B, 7C, pub 2023-04-26)"}}


def one_person_check(r69, r86, r87, r84rel):
    """§12.16 T1s-1pi (TO_E 17:55, 18:32): one-person households by householder sex x 10-year band at the start, census 2020's (表V-1-3's
    raw one-person persons = their householders, + the age-unknown one-person persons by M017b's IPF, M024) x IPSS 2018's
    (2025 / 2020)^(4/5) (R86, the 5-year bands summed)"""
    bands = ["15-24", "25-34", "35-44", "45-54", "55-64", "65-74", "75-84", "85+"]
    five = [["15～19歳", "20～24歳"], ["25～29歳", "30～34歳"], ["35～39歳", "40～44歳"], ["45～49歳", "50～54歳"], ["55～59歳", "60～64歳"],
            ["65～69歳", "70～74歳"], ["75～79歳", "80～84歳"], ["85歳以上"]]
    ages = ["0-4", "5-9", "10-14", "15-19", "20-24", "25-29", "30-34", "35-39", "40-44", "45-49", "50-54", "55-59", "60-64", "65-69",
            "70-74", "75-79", "80-84", "85+"]
    kinds = {"13_単独世帯": "one-person", "14_世帯の家族類型「不詳」": "type unknown", "2_施設等の世帯": "institutions"}
    added, unknown = {}, {}
    for r in r87:
        if not r["prefecture"].startswith("00000") or r["sex"] == "T":
            continue
        if r["table"] == "age_raw_vs_imputed" and r["added_by_imputation"]:
            i = int(r["age"][:2])
            if 1 <= i <= 21:
                k = (r["sex"], ages[min(i - 1, 17)])
                added[k] = added.get(k, 0.0) + float(r["added_by_imputation"])
        if r["table"] == "age_unknown_by_household_type" and r["household_type"] in kinds:
            unknown[(r["sex"], kinds[r["household_type"]])] = float(r["raw"])
    t132 = {}
    for r in r84rel:
        if not r["area"].startswith("00000") or r["sex"] == "0_総数" or r["relation"] != "00_総数":
            continue
        if r["age"][:2].isdigit() and 1 <= int(r["age"][:2]) <= 21:
            k = ("M" if r["sex"] == "1_男" else "F", ages[min(int(r["age"][:2]) - 1, 17)], r["family_type"][:2])
            t132[k] = t132.get(k, 0.0) + float(r["persons"])
    out = []
    for sx in ("M", "F"):
        # M017b's IPF (math-reports m017b_age_unknown.py): rows where the age-unknown live, columns the ages the imputation added,
        # the seed the age-known persons outside nuclear and non-nuclear households (第13-2表)
        rest = {a: t132.get((sx, a, "0_"), 0.0) - t132.get((sx, a, "11"), 0.0) - t132.get((sx, a, "12"), 0.0) for a in ages}
        rows = {k: unknown[(sx, k)] for k in kinds.values()}
        cols = {a: max(added.get((sx, a), 0.0), 0.0) for a in ages}
        z = sum(rows.values()) / sum(cols.values())
        cols = {a: c * z for a, c in cols.items()}
        x = {}
        for a in ages:
            x[("one-person", a)] = 0.0 if ages.index(a) < 3 else max(rest[a], 1.0)
            x[("type unknown", a)] = max(rest[a], 1.0)
            x[("institutions", a)] = 1.0
        for _ in range(500):
            for kind, target in rows.items():
                t = sum(v for (k, a), v in x.items() if k == kind)
                for key in [k for k in x if k[0] == kind]:
                    x[key] *= target / t if t else 0.0
            for a, target in cols.items():
                t = sum(v for (k, aa), v in x.items() if aa == a)
                for key in [k for k in x if k[1] == a]:
                    x[key] *= target / t if t else 0.0
        v13 = [0.0] * 8
        for r in r69:
            if r["topic"] == "V-1-3" and r["unit"] == "persons" and r["item"].startswith(sx + " ") and r["item"].endswith(" one-person"):
                b = r["item"].split(" ")[1]
                if b in bands:
                    v13[bands.index(b)] = float(r["value"])
        assert all(v > 0 for v in v13)
        ip = {}
        for r in r86:
            if r["edition"] == "2018 national" and r["type"] == "one_person" and r["householder"] == sx and r["year"] in ("2020", "2025"):
                ip[(r["year"], r["age"])] = float(r["households_1000"]) * 1000
        row = []
        for bi, ia in enumerate(five):
            unk = sum(x[("one-person", a)] for a in ages[3 + 2 * bi:5 + 2 * bi]) if bi < 7 else x[("one-person", "85+")]
            ratio = (sum(ip[("2025", a)] for a in ia) / sum(ip[("2020", a)] for a in ia)) ** 0.8
            row.append((v13[bi] + unk) * ratio)
        out.append(row)
    return {"one_person_check_2024": {
        "value": {"bands": bands, "by_sex": out, "tolerance": {"cell": 0.076, "cells_beyond_at_most": 1, "max": 0.152, "levelled": "to T1's one-person total before the cell errors (M023, M024)"}},
        "label": "§12.16 T1s-1pi (TO_E 17:55, 18:32; CHECK, PROJECTION): one-person households by householder sex x 10-year band at 2024, 国勢調査 2020 表V-1-3's one-person persons + 第5表's age-unknown 単独世帯 by M017b's IPF (S/D, M024: INDEPENDENT of T1 in the age drift, IPSS 2018's 2025/2020 ratio per band ^(4/5); SHARED with T1 in the age-unknown's allocation); the tolerance M024's: levelled to T1's total, at most one cell beyond 7.6% and none beyond 15.2%",
        "source": "R69 (表V-1-3), R87 (第5表's age-unknown and the imputation's added ages), R84 (第13-2表), R86 (IPSS 2018 national 結果表)"}}


def r81_block(r81):
    """§12.12 R81's swap (declared 0e207a8b): 人口推計 2022-10-01's 総人口 by prefecture x sex x 5-year band 0-4 .. 85+ (S, thousands)"""
    bands = ["%d～%d歳" % (5 * i, 5 * i + 4) for i in range(17)] + ["85歳以上"]
    by_pref = {}
    for r in r81:
        if r["year"] != "2022" or r["population"] != "総人口" or r["sex"] not in ("男", "女") or r["age"] == "総数":
            continue
        rows = by_pref.setdefault(str(int(r["pref_code"][:2])), [[0] * 18, [0] * 18])
        rows[0 if r["sex"] == "男" else 1][bands.index(r["age"])] = int(r["thousand_persons"]) * 1000
    assert len(by_pref) == 48 and all(all(all(x > 0 for x in s) for s in v) for v in by_pref.values())
    foreign = [[0] * 15, [0] * 15]
    for r in r81:
        if r["year"] != "2022" or r["pref_code"] != "00000" or r["sex"] not in ("男", "女") or r["age"] == "総数":
            continue
        b = bands.index(r["age"])
        if b >= 3:
            sign = 1 if r["population"] == "総人口" else -1
            foreign[0 if r["sex"] == "男" else 1][min(b - 3, 14)] += sign * int(r["thousand_persons"]) * 1000
    return {"foreign_2022_by_sex_band": {
        "value": {"band_from": [15 + 5 * i for i in range(15)], "national": foreign},
        "label": "§12.16 T1s-res's context: 人口推計 2022-10-01's 総人口 - 日本人人口 nationally by sex x 5-year band 15-19 .. 85+ (D, a stock, not 2020-24's flow)",
        "source": "R81 (総務省統計局 人口推計 第10表, statInfId 000040045496, pub 2023-04-12)"},
        "population_2022_by_pref_sex_band": {
        "value": {"band_from": [5 * i for i in range(18)], "by_pref": by_pref},
        "label": "§12.12 R81's swap (0): 人口推計 2022-10-01's total population (総人口) by prefecture x sex (men, women) x 5-year band 0-4 .. 80-84, 85+, persons (S, published in thousands)",
        "source": "R81 (総務省統計局 人口推計 第10表, statInfId 000040045496, pub 2023-04-12)"}}


def r77c_block(r77c):
    """§12.15 R77c: tools/modern/r77c_couples.py's start couples and its backtest's six rows"""
    nat = [[0.0] * 15 for _ in range(15)]
    for k, v in r77c["national"].items():
        h, w = k.split("|")
        nat[R77_BANDS.index(h)][R77_BANDS.index(w)] = v
    by_pref = {"0": nat}
    by_pref.update(r77c["by_pref"])
    assert len(by_pref) == 48
    return {"couples_2024": {
        "value": {"band_from": [15 + 5 * i for i in range(15)], "by_pref": by_pref, "marriage_share": r77c["marriage_share"], "rates": r77c["rates"],
                  "backtest": r77c["backtest"], "totals": r77c["totals"]},
        "label": "§12.15 R77c: couples at 2024.75 by the husband's x the wife's 5-year band (15-19 .. 80-84, 85+), national ('0', the cohort projection) and 47 prefectures (the national cell transition, divorces by the aged stock, marriages by marriage_share: 'r88' = each year's event cell x R88's prefecture share, M020 D20, TO_E 16:58; rates 'pref' = each prefecture's survival by R89's ratios and its leaving by R82, TO_E 17:10), aged from R77's 2020 couples by M014's R3 (D); the backtest is the same code on R78's 2015 couples against R77's 2020",
        "source": "tools/modern/r77c_couples.py on R75, R76, R77, R78, R80, R81, R82, R88, R89"},
        "marital_2024": {
        "value": r77c["marital_2024"],
        "label": "§12.16 M021: per prefecture ('0' the sum) x sex x band 15-19 .. 85+ at the start, [R77c's couple persons, 2020's married-apart ratio (R82 married - R77 couple persons) / couple persons, never married by the cohort identity (R82 2020 x the prefecture's survival - first marriages 2020-24 by R80 x R88's share; -1 at 15-19, the remainder), widowed and divorced (2020's aged + R77c's flows - remarriages x their shares), the remarriages]; the national never-married shares 2015 and 2020 by band (R82, unknown pro rata) for T1s-nmt (D)",
        "source": "tools/modern/r77c_couples.py on R80, R82, R88, R89 and R77c's couples"}}


def m017_blocks(r86, r87):
    """§12.14 (M017, M017b; TO_E 14:19, 14:24): the 2024 household-type target per prefecture (and '0' national) for one-person,
    couple only, couple + children, lone parent, other: census 2020 x IPSS 2018's 2024 / 2020 per type nationally, the prefectures by
    census 2020 x (IPSS 2019's 2025 / 2020)^(4/5) raked to the national per type (households); IPSS 2024's 2024 as the CHECK. And per
    prefecture x sex the census's age-unknown by where they live [one-person, family type unknown, institutions] and by 5-year band
    (0-4 .. 85+) the raw and the imputed persons"""
    types = ["one_person", "couple_only", "couple_children", "lone_parent", "other"]
    names = {}
    for r in r87:
        code = str(int(r["prefecture"][:2]))
        names[r["prefecture"][6:]] = code
    names["national"] = "0"
    val = {}
    for r in r86:
        if r["householder"] != "all" or r["age"] != "all" or r["type"] not in types + ["total"]:
            continue
        val[(r["edition"], r["year"], names[r["area"]], r["type"])] = float(r["households_1000"]) * 1000.0
    nat = {t: val[("census 2020", "2020", "0", t)] * val[("2018 national", "2024", "0", t)] / val[("2018 national", "2020", "0", t)] for t in types}
    raw = {}
    for c in sorted(set(k[2] for k in val if k[0] == "census 2020" and k[2] != "0"), key=int):
        raw[c] = [val[("census 2020", "2020", c, t)] * (val[("2019 prefecture", "2025", c, t)] / val[("2019 prefecture", "2020", c, t)]) ** 0.8 for t in types]
    tgt = {"0": [round(nat[t], 1) for t in types]}
    for i, t in enumerate(types):
        s = sum(v[i] for v in raw.values())
        for c, v in raw.items():
            tgt.setdefault(c, [0.0] * 5)[i] = round(v[i] * nat[t] / s, 1)
    check = {t: val[("2024 national", "2024", "0", t)] for t in types + ["total"]}
    census = {c: [round(val[("census 2020", "2020", c, t)], 1) for t in types] for c in sorted(set(k[2] for k in val if k[0] == "census 2020"), key=int)}
    au = {}
    kind = {"13_単独世帯": 0, "14_世帯の家族類型「不詳」": 1, "2_施設等の世帯": 2}
    for r in r87:
        c = str(int(r["prefecture"][:2]))
        if r["sex"] not in ("M", "F"):
            continue
        e = au.setdefault(c, {"m": {"rows": [0, 0, 0], "raw": [0] * 18, "imputed": [0] * 18}, "f": {"rows": [0, 0, 0], "raw": [0] * 18, "imputed": [0] * 18}})[r["sex"].lower()]
        if r["table"] == "age_unknown_by_household_type" and r["household_type"] in kind and r["age"][3:] == "年齢「不詳」":
            e["rows"][kind[r["household_type"]]] += int(float(r["raw"]))
        elif r["table"] == "age_raw_vs_imputed" and r["age"][:2].isdigit() and 1 <= int(r["age"][:2]) <= 21:
            b = min(int(r["age"][:2]) - 1, 17)
            e["raw"][b] += int(float(r["raw"]))
            e["imputed"][b] += int(float(r["imputed"]))
    return {"household_target": {"value": {"types": types, "by_pref": tgt, "check_2024_ipss2024": check, "census_2020": census},
                                 "label": "§12.14 (2): the 2024 households by type, census 2020 x IPSS 2018's 2020 -> 2024 ratio per type (national), the prefectures by census 2020 x IPSS 2019's (2025 / 2020)^(4/5) raked to the national per type (PROJECTION, D); IPSS 2024 edition's 2024 a CHECK only (published after the cutoff); census_2020 the base (S), for the shares within a type (M019)",
                                 "source": "R86 (IPSS 2018 national, 2019 prefecture; census 2020 第12-1表; IPSS 2024 CHECK)"},
            "age_unknown": {"value": {"band_from": [5 * b for b in range(18)], "rows": ["one-person", "family type unknown", "institutions"], "by_pref": au},
                            "label": "§12.14 (3), M017b: per prefecture x sex the census 2020's age-unknown persons by where they live (one-person, family type unknown, institutions; raw, S) and the persons by 5-year band raw and imputed (不詳補完; the difference D)",
                            "source": "R87 (国勢調査 2020 第1-4表 raw and 不詳補完 参考表; 第5表)"}}


def _sig12(x):
    if isinstance(x, float):
        return float("%.12g" % x)
    if isinstance(x, list):
        return [_sig12(v) for v in x]
    if isinstance(x, dict):
        return {k: _sig12(v) for k, v in x.items()}
    return x


def main():
    tab = json.load(open(sys.argv[1], encoding="utf-8"))
    hh = json.load(open(sys.argv[2], encoding="utf-8"))
    r62 = {(r["item"], r["metric"]): r for r in csv.DictReader(open(sys.argv[3], encoding="utf-8"))}
    r67a = {r["name"]: r for r in csv.DictReader(open(sys.argv[4], encoding="utf-8-sig"))}
    r67c = {r["name"]: r for r in csv.DictReader(open(sys.argv[5], encoding="utf-8-sig"))}
    # D: the conditional shares from the H1 construction, 18 bands x 2 sexes
    type_bs = [[shares(tab["type_by_band_sex"].get("%d,%d" % (b, s), [1, 0, 0, 0, 0, 0])) for b in range(18)] for s in range(2)]
    emp_bs = [[shares(tab["employment_by_band_sex"].get("%d,%d" % (b, s), [1, 0, 0, 0, 0, 0])) for b in range(18)] for s in range(2)]
    role_tbs = {k: shares(v) for k, v in tab["role_by_type_band_sex"].items()}
    size_th = {k: shares(v) for k, v in tab["size_by_type_hband"].items()}
    # R69 (§12.6): the complete 表V-1-3 (S, ten-year bands) as the type margin; the split inside a ten-year band is H1's D table,
    # raked to the S shares (rows the five-year bands' persons in the D table, columns the S shares x their total)
    r69 = list(csv.DictReader(open(sys.argv[6], encoding="utf-8-sig")))
    v13 = {}
    for r in r69:
        if r["topic"] == "V-1-3" and r["unit"] == "persons":
            sx, band, *rest = r["item"].split(" ")
            v13[(sx, band, " ".join(rest))] = float(r["value"])
    V13_TYPES = ["one-person", "couple only", "couple + children", "single parent + children", "other", "institutions"]
    V13_BANDS = [("<15", [0, 1, 2]), ("15-24", [3, 4]), ("25-34", [5, 6]), ("35-44", [7, 8]), ("45-54", [9, 10]), ("55-64", [11, 12]),
                 ("65-74", [13, 14]), ("75-84", [15, 16]), ("85+", [17])]
    s_cells = []
    for si, sx in enumerate(["M", "F"]):
        for band, bs in V13_BANDS:
            want = [v13[(sx, band, t)] for t in V13_TYPES]
            tw = sum(want)
            d = [[float(x) for x in tab["type_by_band_sex"].get("%d,%d" % (b, si), [1, 0, 0, 0, 0, 0])] for b in bs]
            rows = [sum(x) for x in d]
            tr = sum(rows)
            cols = [w / tw * tr for w in want]
            x = [[max(v, 1e-9) if cols[t] > 0 else 0.0 for t, v in enumerate(row)] for row in d]
            for _ in range(200):
                for i, row in enumerate(x):
                    sm = sum(row)
                    if sm > 0:
                        x[i] = [v * rows[i] / sm for v in row]
                for t in range(6):
                    sm = sum(x[i][t] for i in range(len(x)))
                    if sm > 0:
                        for i in range(len(x)):
                            x[i][t] *= cols[t] / sm
            for i, b in enumerate(bs):
                type_bs[si][b] = shares(x[i])
            for t in range(6):
                s_cells.append([si, band, t, round(want[t] / tw, 6)])
    # R69 (§12.6): employment by 5-year age x sex from census 2020's labour status (S/D) and the employment-type shares (D)
    lab, ety = {}, {}
    for r in r69:
        if r["topic"] in ("labour", "emptype"):
            code, sx, age, *what = r["item"].split(" ")
            (lab if r["topic"] == "labour" else ety)[(code, sx, age, " ".join(what))] = float(r["value"]) / 100.0
    AGE = {3: "01_15～19歳", 4: "02_20～24歳", 5: "03_25～29歳", 6: "04_30～34歳", 7: "05_35～39歳", 8: "06_40～44歳", 9: "07_45～49歳",
           10: "08_50～54歳", 11: "09_55～59歳", 12: "10_60～64歳", 13: "11_65～69歳", 14: "12_70～74歳", 15: "13_75～79歳", 16: "14_80～84歳",
           17: "15_85歳以上"}
    AGE_E = dict(AGE)
    AGE_E[17] = "15_85～89歳"
    def emp_row(code, sx, b):
        if b not in AGE:
            return [1.0, 0, 0, 0, 0, 0]
        g = lambda w: lab[(code, sx, AGE[b], w)]
        lf, u = g("labour force rate"), g("unemployment rate")
        school, house, other = g("in school (not working)"), g("housework (not working)"), g("other not in LF (incl. retired)")
        e = lambda w: ety.get((code, sx, AGE_E[b], w), ety[("00000_全国", sx, AGE_E[b], w)])
        emp_sh, reg = e("employees share of employed (known status)"), e("regular share of employees")
        employed = lf * (1.0 - u)
        non_reg = employed * emp_sh * (1.0 - reg)
        retired = other if b >= 12 else 0.0
        nilf = house + (other if b < 12 else 0.0)
        return shares([nilf, employed - non_reg, non_reg, lf * u, school, retired])
    emp_bs = [[emp_row("00000_全国", sx, b) for b in range(18)] for sx in ("M", "F")]
    # R69 (§12.6): each prefecture's broad age shares (S/D) and its labour-force and unemployment rates by sex (S/D)
    pref_age, pref_lab = {}, {}
    for r in r69:
        if r["topic"] == "pref_age" and not r["item"].startswith("00000"):
            code = r["item"][:2]
            pref_age.setdefault(code, {})[r["item"].split(" ", 1)[1]] = float(r["value"])
    for (code, sx, age, what), v in lab.items():
        if age == "00_総数" and code != "00000_全国" and sx == "T" and what in ("labour force rate", "unemployment rate"):
            pref_lab.setdefault(code[:2], {})[what] = v
    nat_lab = {w: lab[("00000_全国", "T", "00_総数", w)] for w in ("labour force rate", "unemployment rate")}
    age_groups = {}
    for code, a in sorted(pref_age.items()):
        u15, o65, o75 = a["share under 15"] / 100.0, a["share 65+"] / 100.0, a["share 75+"] / 100.0
        age_groups[code] = [round(u15, 6), round(1.0 - u15 - o65, 6), round(o65 - o75, 6), round(o75, 6)]
    # R67a: the adults' tiers (DINA shares of adults: top 10 / 1 / 0.1 %; the top 0.01 % from the tax table, D), and their mean incomes
    adult_shares = [0.0001, 0.0009, 0.009, 0.09, 0.40, 0.50]
    # the class means (yen per adult a year): DINA's nested means (S for the bottom 50 %, D for the rest from the shares and the
    # top-group means); the top 0.01 % from the tax table's top 10,451 taxpayers (0.0001 x the start's 104,513,373 adults, D)
    def a(name):
        return float(r67a[name]["value"])
    nni = a("adult_nni_mean_bottom50") / (a("adult_nni_share_bottom50") / 100.0 / 0.5)
    n_top = 10451
    above2 = ["2-5億", "5-10億", "10-20億", "20-50億", "50-100億", "100億超"]
    n2 = sum(a("taxpayers_total_income_%s" % k) for k in above2)
    amt2 = sum(a("taxpayers_total_income_%s_amount" % k) for k in above2) * 1e6
    m12 = a("taxpayers_total_income_1-2億_amount") * 1e6 / a("taxpayers_total_income_1-2億")
    top001 = (amt2 + (n_top - n2) * m12) / n_top
    m10, m1, m01 = a("adult_nni_mean_top10"), a("adult_nni_mean_top1"), a("adult_nni_mean_top0.1")
    class_means = [round(top001), round((0.001 * m01 - 0.0001 * top001) / 0.0009), round((0.01 * m1 - 0.001 * m01) / 0.009),
                   round((0.1 * m10 - 0.01 * m1) / 0.09), round(a("adult_nni_share_middle40") / 100.0 * nni / 0.4), round(a("adult_nni_mean_bottom50"))]
    # the income tail's knots (§12.8 item 9, cash concept): the MOF paper's lines before matching to national income (survey + income
    # tax), which R67a gives in its text only (§1.1 for the top 1 % and 0.1 %, S; §1.4's table for the top 10 %, D); the top 0.01 % line
    # inside the tax table's 1-2 億 class by a Pareto through the class's ends (D); the top index from that tier's mean
    n1 = a("taxpayers_total_income_over_1oku")
    alpha_b = math.log(n1 / n2) / math.log(2.0)
    line001 = 2e8 * (n_top / n2) ** (-1.0 / alpha_b)
    tail = {"shares": [0.1, 0.01, 0.001],
            "lines_yen_year": [6600000.0, 14800000.0, 36900000.0],
            "cash_income_shares_pct": {"top1": 8.06, "top0_1": 2.18},
            "tax_top_0_01": {"line_yen_year": round(line001), "mean_yen_year": round(top001)},
            "dina_lines_yen_year": [a("adult_nni_threshold_top10"), a("adult_nni_threshold_top1"), a("adult_nni_threshold_top0.1")]}
    # R67a: the instruments' age profiles by householder age (<30, 30s, ..., 70s, 80+): financial assets S, the non-financial assets
    # as net wealth less financial assets D (1000 yen per household), the debt profile relative per adult T
    ages7 = ["lt30", "30s", "40s", "50s", "60s", "70s", "80plus"]
    fin = [a("hh_fin_assets_mean_head_age_%s" % g) for g in ages7]
    nonfin = [a("hh_net_wealth_mean_head_age_%s" % g) - x for g, x in zip(ages7, fin)]
    profiles = {"financial": fin, "non_financial": nonfin, "debt": [0.6, 1.6, 1.7, 1.0, 0.4, 0.15, 0.15],
                "by_instrument": {"cash_deposits": "financial", "insurance_pensions": "financial", "equity_funds": "financial", "debt_securities": "financial",
                                  "other_financial": "financial", "land": "non_financial", "fixed_assets": "non_financial", "inventories": "non_financial",
                                  "borrowing": "debt", "other_liabilities": "debt"}}
    # R67c: the household sector's instruments, end-2022, 兆円 (F)
    def c(name):
        return float(r67c[name]["value"])
    instruments = {"cash_deposits": c("sna_hh_a_cash_deposits"), "insurance_pensions": c("sna_hh_a_insurance_pension"), "equity_funds": c("sna_hh_a_equity_funds"),
                   "debt_securities": c("sna_hh_a_debt_securities"), "other_financial": round(c("sna_hh_a_loans") + c("sna_hh_a_derivatives") + c("sna_hh_a_other"), 1),
                   "land": c("sna_hh_land"), "fixed_assets": c("sna_hh_fixed_assets"), "inventories": c("sna_hh_inventories"),
                   "borrowing": c("sna_hh_l_borrowing"), "other_liabilities": c("sna_hh_l_other"), "net_worth": c("sna_hh_net_worth")}
    spec = {
        "note": "ISS tiered population T1 (ISS_TIERED_POPULATION.md §12): the start's inputs. Labels S (published), D (derived), T (declared), F (a field start value matched exactly). Built by tools/modern/build_tiers_spec.py.",
        "k_points": {"value": 4, "label": "T (the owner's order: K = 4 in GDScript, 8 after the port; a parameter)", "source": "§8.4"},
        "classes": {"value": {"names": CLASSES, "adult_shares": adult_shares, "unit_size": [10, 30, 100, 3000, 0, 0, 0], "unit_size_port": [10, 10, 100, 1000, 0, 0, 0], "individuals_top": 3000, "mean_income_yen_year": class_means},
                    "label": "S for the shares of adults (R67a: DINA 2019 top 10 / 1 / 0.1 %; the top 0.01 % D from the tax table); T: the class is applied uniformly to adults by age (by age NF), children 'none'; the unit sizes at E for the GDScript oracle (the PM's ruling, §11.1a, §12.7): the top 0.01 %'s about 3,000 individuals (the owner's answer 2) and its remainder in sub-bundles of 10, the top 0.1 % 30, the top 1 % 100 (D473), the top 10 % 3,000, the merged rest one bundle per cell (0); the C++ port's ladder 1 / 10 / 100 / 1,000 (D473) as unit_size_port; adults are 20 and over (R67a's DINA convention); mean_income_yen_year per class (§12.8 item 3): the bottom 50 % S (DINA 2019), the middle 40 % D (its share x the mean per adult, the mean from the bottom 50 %'s share and mean), the top 10 % less 1 %, 1 % less 0.1 % and 0.1 % less 0.01 % D from DINA's nested means, the top 0.01 % D from the tax table 2021 (the top 10,451 taxpayers: the classes above 2 億 and the rest at the 1-2 億 class mean)",
                    "source": "R67a §1.1, §1.4; D473"},
        "type_by_band_sex": {"value": type_bs, "s_cells": s_cells, "label": "P(household type | 5-year band, sex): the complete 表V-1-3 (S, ten-year bands x sex x six types incl. institutions) with the split inside a ten-year band from H1's construction (D, %s, %d persons) raked to it" % (tab["run"], tab["persons"]), "source": "R69 §2 (V-1-3 rows); H1 §10.1"},
        "employment_by_band_sex": {"value": emp_bs, "label": "P(employment | band, sex): census 2020 labour status by 5-year age x sex (S/D, R69 §3): employed = LF x (1 - u) split regular / non-regular by the employment-type shares (officers, employers, own-account and family workers counted regular, T); unemployed LF x u; student = in school, not working; retired = other not in LF at 60+; not in LF = housework and other under 60 (T)", "source": "R69 §3 (labour, emptype rows)"},
        "age_groups_by_prefecture": {"value": age_groups, "label": "each prefecture's shares under 15, 15-64, 65-74, 75+ (census 2020, S/D, R69 §1): the seed of (0), the shape inside a group and the sex ratio national (T); the long prefecture x 5-year age x sex table is not in the repository (step 2)", "source": "R69 §1 (pref_age rows)"},
        "labour_by_prefecture": {"value": {"national": nat_lab, "prefectures": pref_lab}, "label": "each prefecture's labour-force rate and unemployment rate, both sexes, 15+ (census 2020, S/D, R69 §3; by sex NF in the repository's rows): the national age x sex profile scaled once to them, the same factor for both sexes (T)", "source": "R69 §3 (labour rows, 00_総数)"},
        "role_by_type_band_sex": {"value": role_tbs, "label": "P(role | type, band, sex): D from H1's construction (the compositions)", "source": tab["run"]},
        "size_by_type_hband": {"value": size_th, "label": "household size class (1, 2, 3, 4, 5+) by type x householder band: D from H1's construction", "source": tab["run"]},
        "type_by_prefecture": hh["type_by_prefecture"],
        "type_by_householder_age": hh["type_by_householder_age"],
        "mean_size_by_prefecture": hh["mean_size_by_prefecture"],
        "income_tail": {"value": tail, "label": "§12.8 item 9: the adults' survival above the generator's median runs log-linear through these lines (monthly 万円 = yen a year ÷ 12 ÷ 1e4): on the cash concept (the PM's ruling), the MOF paper's 2019 lines before matching to national income, survey + income tax: top 1 % 14.8 M and top 0.1 % 36.9 M (S, R67a §1.1 text, k_mof_ron371:598-620), top 10 % 6.6 M (D, R67a §1.4's table, no line reference); the shares before matching (8.06 %, 2.18 %) are inputs of the generalized Pareto interpolation (§12.8 10.2, the PM's option A: the MOF inputs alone); DINA's national-income lines kept as dina_lines_yen_year, not comparable; tax_top_0_01 a CHECK only (it cannot share one curve with the MOF shares, runs/gpi_feasibility; 合計所得 may include separately taxed capital gains): the top 0.01 % line D from the tax table 2021 (the 10,451st taxpayer inside the 1-2 億 class, a Pareto through N(> 1 億) = 23,670 and N(> 2 億) = 8,016); above it one Pareto whose index gives the top 0.01 %'s mean (D, classes.mean_income_yen_year[0]). Inputs of the fit, not checks", "source": "R67a §1.1"},
        "never_married": hh["life_course"]["value"]["never_married"],
        "instruments_hh_trillion_yen": {"value": instruments, "label": "F (R67c §1.1: 国民貸借対照表 end-2022, the household sector incl. sole proprietors, 兆円)", "source": "R67c (b34443ae)"},
        "instrument_age_profiles": {"value": profiles, "label": "§12.8 item 6, by householder age <30, 30s, 40s, 50s, 60s, 70s, 80+ read per adult: financial assets R67a's mean (S, 1000 yen, 全国家計構造調査 2019); land, fixed assets and inventories R67a's net wealth less financial assets (D); borrowing and other liabilities a debt profile relative per adult (T: the shape of 家計調査 2023's debt by householder age, not in the repository; R-request); each holder's weight the profile at its age x its income over its age group's mean (T)", "source": "R67a §1.1"},
        "fit": {"value": {"order": ["prefecture_band_sex", "table_V_1_3_band_sex_type", "type_by_prefecture", "employment_by_band_sex", "classes"], "max_rounds": 500, "tol": 1e-9}, "label": "§12.5 F6: lexicographic; (0) and (1) exact in integers, R64's types by prefecture raked to the totals (0) and (1) allow, then an IPF in reals over the three; employment and class factors inside each cell, keyed systematic rounding; residuals reported (T1s-h, T1s-l)", "source": "§12.5 (M001 F6)"},
    }
    if len(sys.argv) > 8:
        r70 = list(csv.DictReader(open(sys.argv[8], encoding="utf-8")))
        spec.update(r70_blocks(r70))
        spec.update(r70_couple_blocks(r70))
        if len(sys.argv) > 9:
            spec.update(r72_blocks(list(csv.DictReader(open(sys.argv[9], encoding="utf-8"))), r70))
            if len(sys.argv) > 12:
                spec.update(r76_blocks(*[list(csv.DictReader(open(sys.argv[k], encoding="utf-8"))) for k in (10, 11, 12)]))
                if len(sys.argv) > 15:
                    spec.update(r77_blocks(*[list(csv.DictReader(open(sys.argv[k], encoding="utf-8"))) for k in (13, 14, 15, 11)]))
                    if len(sys.argv) > 16:
                        spec.update(r83_block(list(csv.DictReader(open(sys.argv[16], encoding="utf-8")))))
                        if len(sys.argv) > 18:
                            spec.update(r84_block(*[list(csv.DictReader(open(sys.argv[k], encoding="utf-8"))) for k in (17, 18)]))
                            if len(sys.argv) > 19:
                                r85 = list(csv.DictReader(open(sys.argv[19], encoding="utf-8")))
                                spec.update(r85_block(r85))
                                spec.update(m016_blocks(list(csv.DictReader(open(sys.argv[17], encoding="utf-8"))), r85))
                                if len(sys.argv) > 21:
                                    r86r, r87r = (list(csv.DictReader(open(sys.argv[k], encoding="utf-8"))) for k in (20, 21))
                                    spec.update(m017_blocks(r86r, r87r))
                                    spec.update(one_person_check(r69, r86r, r87r, list(csv.DictReader(open(sys.argv[17], encoding="utf-8")))))
                                    if len(sys.argv) > 27:
                                        spec.update(r75_block(list(csv.DictReader(open(sys.argv[27], encoding="utf-8")))))
                                    if len(sys.argv) > 26:
                                        spec.update(r90_block(list(csv.DictReader(open(sys.argv[25], encoding="utf-8"))), list(csv.DictReader(open(sys.argv[26], encoding="utf-8")))))
                                    if len(sys.argv) > 24:
                                        spec.update(m022_block(list(csv.DictReader(open(sys.argv[24], encoding="utf-8-sig"))), list(csv.DictReader(open(sys.argv[17], encoding="utf-8"))), list(csv.DictReader(open(sys.argv[13], encoding="utf-8"))), r86r))
                                    if len(sys.argv) > 23:
                                        spec.update(r81_block(list(csv.DictReader(open(sys.argv[22], encoding="utf-8")))))
                                        spec.update(r77c_block(json.load(open(sys.argv[23], encoding="utf-8"))))
    # Why not the floats as computed: a count near 10^6 written with 16 digits sits at canon's nine-decimal snap's precision, and one
    # ulp moves its snapped value (test_modern_data D8); these blocks are written at 12 significant digits
    for k in ("couples_2024", "marital_2024", "m022_within_couple", "one_person_check_2024", "immigration_2020_2023", "mortality_ratio_ipss_2023"):
        if k in spec:
            spec[k]["value"] = _sig12(spec[k]["value"])
    open(sys.argv[7], "w", encoding="utf-8").write(json.dumps(spec, ensure_ascii=False, indent=1) + "\n")
    print("TIERS SPEC s_cells %d" % len(s_cells))


if __name__ == "__main__":
    main()
