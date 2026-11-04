"""R77c (ISS_TIERED_POPULATION §12.15): census couples aged to a later date by M014's R3 (M013's cohort method with R82's single-age
crosses, the leaving-the-table flow and the married mortality ratio), and the same code's 2015 -> 2020 backtest (the six rows).

Run (standard library only; every input is a download, so python3 -I):
    python3 -I tools/modern/r77c_couples.py OUT.json R77_census_couples_age.csv R77_census_couples_single_age_national.csv \
        R78_census2015_couples_age.csv R78_census2015_couples_single_age_national.csv R78_census2015_population_age_sex_pref.csv \
        R76_census2020_marital.csv R80_marriages_divorces_by_age.csv R80_series_and_margins.csv R80_lifetables_2020_2021.csv \
        R82_marriages_divorces_single_age.csv R82_census_marital_2015_2020.csv R82_mortality_by_marital.csv \
        R75_ipss_mortality_projection.csv R81_pref_age_estimates.csv R88_marriages_by_prefecture.csv \
        R89_pref_life_tables.csv [r88|men] [pref|nat]
"""
import csv
import json
import math
import sys
import unicodedata

BANDS = ["15-19", "20-24", "25-29", "30-34", "35-39", "40-44", "45-49", "50-54",
         "55-59", "60-64", "65-69", "70-74", "75-79", "80-84", "85+"]
NAT = "00000"
MIN_CELL = 10000
MIN_DEATHS = 100
MORT_BANDS = BANDS[2:14] + ["85-89", "90-94", "95-99", "100+"]
TOL = {"nat_wife": 0.0420, "nat_husband": 0.0440, "pref_wife": 0.0471, "pref_husband": 0.0437, "pref_rel": 0.0316, "joint_35": 0.0682,
       "joint_all": 0.0688}
TOL_MEN = {"pref_wife": 0.0644, "pref_husband": 0.0600, "pref_rel": 0.0492}
R88_COL = {"19歳以下": "15-19", "-19歳": "15-19", "80歳以上": "80-84", "80歳-": "80-84"}


def band_of(a):
    return BANDS[min((max(a, 15) - 15) // 5, 14)]


def ev_band(a):
    return "80-84" if a >= 80 else band_of(a)


def read_couples(path):
    out = {}
    for r in csv.DictReader(open(path, encoding="utf-8")):
        out.setdefault(r["area"][:5], {})[(r["husband_band"], r["wife_band"])] = float(r["couples"])
    return out


def read_couples_single(path):
    out = {}
    for r in csv.DictReader(open(path, encoding="utf-8")):
        h, w = (85 if x.startswith("85") else int(x.rstrip("歳")) for x in (r["husband_age"], r["wife_age"]))
        out[(h, w)] = out.get((h, w), 0.0) + float(r["couples"])
    return out


def read_pop2015_single(path):
    out = {"M": {}, "F": {}}
    for r in csv.DictReader(open(path, encoding="utf-8")):
        if r["area"][:5] != NAT or r["sex"] not in out:
            continue
        age = r["age"]
        if age == "110歳以上":
            out[r["sex"]][110] = float(r["persons"])
        elif age.endswith("歳") and age[:-1].isdigit():
            out[r["sex"]][int(age[:-1])] = float(r["persons"])
    return out


def read_men2020(path):
    out = {}
    for r in csv.DictReader(open(path, encoding="utf-8")):
        if r["marital"] != "0_総数" or r["sex"] != "1_男" or r["age"].startswith("R"):
            continue
        code = int(r["age"][:2])
        if code:
            d = out.setdefault(r["area"][:5], dict.fromkeys(BANDS, 0.0))
            d[BANDS[min(code - 1, 14)]] += float(r["persons"])
    return out


def read_men2022(path):
    """人口推計 2022-10-01 (R81): men by prefecture x 5-year band 15+ (the start's men in the husband band, T)."""
    out = {}
    for r in csv.DictReader(open(path, encoding="utf-8")):
        if r["year"] != "2022" or r["population"] != "総人口" or r["sex"] != "男" or r["age"] == "総数":
            continue
        lo = int(r["age"].split("～")[0].rstrip("歳以上"))
        if lo < 15:
            continue
        out.setdefault(r["pref_code"], dict.fromkeys(BANDS, 0.0))[band_of(lo)] += 1000.0 * float(r["thousand_persons"])
    return out


def read_r88(path):
    """R88 (人口動態 保管統計表 婚姻 第6表-1, -3): {(year, spouse): {(prefecture code, band): first marriages}}, all registrations"""
    out = {}
    for r in csv.DictReader(open(path, encoding="utf-8")):
        if r["scope"] != "all first marriages registered" or r["pref_code"] == "00":
            continue
        col = r["column"]
        band = R88_COL.get(col, col.replace("歳", "") if col[:2].isdigit() and "-" in col else None)
        if band not in BANDS[:14]:
            continue
        d = out.setdefault((int(r["year"]), r["spouse"]), {})
        key = (r["pref_code"] + "000", band)
        d[key] = d.get(key, 0.0) + float(r["value"])
    return out


def split_year(cross, hmarg, wmarg, prefs, iters=200):
    """M020 D20-1: the year's national cross by event band spread flat over the prefectures, raked to (h, w), to R88's husbands
    (p, h) and to its wives (p, w), the wives first raked to the husbands' prefecture totals; {(h, w): {prefecture: share}}"""
    n = {}
    for (h, w), c in cross.items():
        key = (ev_band(h), ev_band(w))
        n[key] = n.get(key, 0.0) + c
    nh, nw = {}, {}
    for (h, w), c in n.items():
        nh[h] = nh.get(h, 0.0) + c
        nw[w] = nw.get(w, 0.0) + c
    b = {}
    for h in nh:
        tot = sum(hmarg.get((p, h), 0.0) for p in prefs)
        for p in prefs:
            b[(p, h)] = nh[h] * hmarg.get((p, h), 0.0) / tot if tot else nh[h] / len(prefs)
    cm = {}
    for w in nw:
        tot = sum(wmarg.get((p, w), 0.0) for p in prefs)
        for p in prefs:
            cm[(p, w)] = nw[w] * wmarg.get((p, w), 0.0) / tot if tot else nw[w] / len(prefs)
    ptot = {p: sum(b[(p, h)] for h in nh) for p in prefs}
    for _ in range(100):
        for p in prefs:
            s = sum(cm[(p, w)] for w in nw)
            for w in nw:
                cm[(p, w)] *= ptot[p] / s if s else 0.0
        for w in nw:
            s = sum(cm[(p, w)] for p in prefs)
            for p in prefs:
                cm[(p, w)] *= nw[w] / s if s else 0.0
    x = {(p, h, w): c / len(prefs) for (h, w), c in n.items() for p in prefs}
    for _ in range(iters):
        for margin, idx in ((b, (0, 1)), (cm, (0, 2))):
            tot = {}
            for key, v in x.items():
                k2 = (key[idx[0]], key[idx[1]])
                tot[k2] = tot.get(k2, 0.0) + v
            for key in x:
                k2 = (key[idx[0]], key[idx[1]])
                x[key] *= margin[k2] / tot[k2] if tot[k2] else 0.0
        tot = {}
        for (p, h, w), v in x.items():
            tot[(h, w)] = tot.get((h, w), 0.0) + v
        for (p, h, w) in x:
            x[(p, h, w)] *= n[(h, w)] / tot[(h, w)] if tot[(h, w)] else 0.0
    shares = {}
    for (p, h, w), v in x.items():
        shares.setdefault((h, w), {})[p] = v / n[(h, w)] if n[(h, w)] else 0.0
    return shares


def read_r89(path):
    """R89 (令和2年都道府県別生命表): {area: {sex: {age: q}}}, single ages 0-99 (100+ dropped: its q is 1 in every table)"""
    out = {}
    for r in csv.DictReader(open(path, encoding="utf-8")):
        if r["age"].isdigit():
            out.setdefault(r["pref_code"] + "000", {}).setdefault(r["sex"], {})[int(r["age"])] = float(r["qx"])
    return out


def pref_tables(tables, r89, area):
    """Each year's national table with q x R89's q_pref / q_nat (the same series), capped at 1 (§12.15, TO_E 17:10)"""
    nat, own = r89[NAT], r89[area]
    out = {}
    for y, t in tables.items():
        out[y] = {}
        for sex, lx in t.items():
            q = {a: 1 - lx[a + 1] / lx[a] if lx[a] > 0 else 1.0 for a in range(len(lx) - 1)}
            for a in q:
                if a in own[sex] and nat[sex].get(a, 0.0) > 0:
                    q[a] = min(1.0, q[a] * own[sex][a] / nat[sex][a])
            out[y][sex] = life_from_q(q)
    return out


def read_married_pref(path, year):
    """R82: married persons by area x sex x 5-year band (15-19 .. 85+), single ages summed"""
    out = {}
    for r in csv.DictReader(open(path, encoding="utf-8")):
        if int(r["year"]) != year or r["marital"] != "married" or r["sex"] not in ("M", "F"):
            continue
        a = 100 if r["age"] == "100+" else int(r["age"]) if r["age"].isdigit() else None
        if a is None or a < 15:
            continue
        d = out.setdefault(r["area"], {}).setdefault(r["sex"], dict.fromkeys(BANDS, 0.0))
        d[band_of(a)] += float(r["persons"])
    return out


def lam_band(cp, mar):
    """lambda by band on the start year as a synthetic cohort: n(b) = 1 - couple persons / married, (n(b+1) - n(b)) / (1 - n(b))"""
    out = {}
    for side, sex in ((0, "M"), (1, "F")):
        inc = margin(cp, side)
        n = [1 - inc[b] / mar[sex][b] if mar[sex][b] > 0 else 0.0 for b in BANDS]
        lam = [(n[i + 1] - n[i]) / (1 - n[i]) if n[i] < 1 else 0.0 for i in range(14)]
        out[sex] = lam + [lam[13]]
    return out


def lam_pref(lam_nat, lb_nat, lb_p):
    """lambda_p(a) = lambda_nat(a) + lambda_p(b(a)) - lambda_nat(b(a)), clipped to [-1, 1] (T)"""
    return {sex: {a: max(-1.0, min(1.0, lam_nat[sex][a] + lb_p[sex][BANDS.index(band_of(a))] - lb_nat[sex][BANDS.index(band_of(a))]))
                  for a in lam_nat[sex]} for sex in ("M", "F")}


def read_first_re(p_series):
    """R80's marriages by single age at registration, first and re, by year x sex (80+ read as 82, M021)"""
    out = {}
    for r in csv.DictReader(open(p_series, encoding="utf-8")):
        g = r["group"]
        if not r["measure"].startswith("marriages registered") or g not in ("夫－初婚", "夫－再婚", "妻－初婚", "妻－再婚"):
            continue
        a = norm_age(r["column"])
        v = r["value"].replace(",", "")
        if a is None or not v.isdigit():
            continue
        key = (int(r["year"]), "M" if g.startswith("夫") else "F", 82 if a == 80 else a, "first" if g.endswith("初婚") else "re")
        out[key] = out.get(key, 0.0) + float(v)
    return out


def read_marital_single(path, year):
    """R82: {(area, sex, single age (100 = 100+)): {state: persons}}, the unknown shared out pro rata (T)"""
    raw = {}
    for r in csv.DictReader(open(path, encoding="utf-8")):
        if int(r["year"]) != year or r["sex"] not in ("M", "F") or not (r["age"].isdigit() or r["age"] == "100+"):
            continue
        raw.setdefault((r["area"], r["sex"], 100 if r["age"] == "100+" else int(r["age"])), {})[r["marital"]] = float(r["persons"])
    out = {}
    for k, d in raw.items():
        known = sum(d.get(m, 0.0) for m in ("never_married", "married", "widowed", "divorced"))
        z = d.get("total", known) / known if known else 0.0
        out[k] = {m: d.get(m, 0.0) * z for m in ("never_married", "married", "widowed", "divorced")}
    return out


def life_from_q(q):
    lx = [1.0]
    for a in range(max(q) + 1):
        lx.append(lx[-1] * (1 - q[a]))
    return lx


def read_life_r80(path, year):
    q = {"M": {}, "F": {}}
    for r in csv.DictReader(open(path, encoding="utf-8")):
        if r["year"] == year:
            q[r["sex"]][int(r["age"])] = float(r["qx"])
    return {s: life_from_q(v) for s, v in q.items()}


def read_life_r75(path, year):
    q = {"M": {}, "F": {}}
    for r in csv.DictReader(open(path, encoding="utf-8")):
        if r["variant"] == "medium" and r["year"] == year and r["age"].isdigit():
            q[r["sex"]][int(r["age"])] = float(r["qx"])
    return {s: life_from_q(v) for s, v in q.items()}


def norm_age(col):
    c = unicodedata.normalize("NFKC", col).replace(" ", "")
    if c.endswith("歳") and c[:-1].isdigit():
        return int(c[:-1])
    if c.startswith("80歳"):
        return 80
    return None


def read_margins_and_divorces(p_series):
    """The marriages' single-age margins by year x side (80 = 80+), and all divorces by year (R80)."""
    marg, total_div = {}, {}
    for r in csv.DictReader(open(p_series, encoding="utf-8")):
        y = int(r["year"])
        v = r["value"].replace(",", "")
        if r["measure"].startswith("divorces by duration") and r["group"] == "離婚件数" and r["column"] == "総数":
            total_div[y] = float(v)
        if r["measure"].startswith("marriages registered") and r["group"] in ("夫－総数", "妻－総数"):
            a = norm_age(r["column"])
            if a is None or not v.isdigit():
                continue
            d = marg.setdefault((y, "h" if r["group"].startswith("夫") else "w"), {})
            d[a] = d.get(a, 0.0) + float(v)
    return marg, total_div


def read_cross_single(path):
    out = {}
    for r in csv.DictReader(open(path, encoding="utf-8")):
        if r["combination"] != "all" or "unknown" in (r["husband_age"], r["wife_age"]):
            continue
        h, w = (80 if x == "80+" else int(x) for x in (r["husband_age"], r["wife_age"]))
        d = out.setdefault((r["kind"][0], int(r["year"])), {})
        d[(h, w)] = d.get((h, w), 0.0) + float(r["count"])
    return out


def rake(seed, hm, wm, iters=300):
    t = dict(seed)
    for _ in range(iters):
        for side, m in ((0, hm), (1, wm)):
            tot = {}
            for k, c in t.items():
                tot[k[side]] = tot.get(k[side], 0.0) + c
            t = {k: c * m.get(k[side], 0.0) / tot[k[side]] if tot[k[side]] else 0.0 for k, c in t.items()}
    return t


def events(cross, marg, total_div, years, cross_of):
    """Each year's marriages (the year's single-age cross, or cross_of(y)'s, raked to the year's margins) and divorces (the cross
    scaled to all divorces), as M014's events_single"""
    out = {}
    for y, _, _ in years:
        out[("m", y)] = rake(cross[("m", cross_of("m", y))], marg[(y, "h")], marg[(y, "w")])
        d = cross[("d", cross_of("d", y))]
        z = total_div[y] / sum(d.values())
        out[("d", y)] = {k: c * z for k, c in d.items()}
    return out


def read_married(path, status="married", cap=85):
    out = {}
    for r in csv.DictReader(open(path, encoding="utf-8")):
        if r["area"] != NAT or r["marital"] != status or r["sex"] not in ("M", "F"):
            continue
        if not (r["age"].isdigit() or r["age"] == "100+"):
            continue
        a = 100 if r["age"] == "100+" else int(r["age"])
        d = out.setdefault((int(r["year"]), r["sex"]), {})
        d[min(a, cap)] = d.get(min(a, cap), 0.0) + float(r["persons"])
    return out


def read_ratio(path):
    raw = {}
    for r in csv.DictReader(open(path, encoding="utf-8")):
        if r["marital"] == "married":
            raw[(r["sex"], r["age"])] = (float(r["deaths"]), float(r["ratio_to_all"]))
    out = {}
    order = ["15-19", "20-24"] + MORT_BANDS
    for sex in ("M", "F"):
        for i, b in enumerate(order):
            ok = [j for j, bb in enumerate(order) if raw[(sex, bb)][0] >= MIN_DEATHS]
            j = min(ok, key=lambda j: (abs(j - i), -j))
            out[(sex, b)] = raw[(sex, order[j])][1]
    return out


def ratio_band(x):
    a = int(x)
    if a >= 100:
        return "100+"
    if a >= 85:
        lo = 85 + (a - 85) // 5 * 5
        return f"{lo}-{lo + 4}"
    return band_of(a)


class Life:
    """Survival by calendar year: the table of year floor(t) (years outside the given ones take the nearest), x the married ratio"""

    def __init__(self, tables, ratio):
        self.tables = tables
        self.ratio = ratio
        self.years = sorted(tables)

    def table(self, t):
        y = min(max(int(math.floor(t)), self.years[0]), self.years[-1])
        return self.tables[y] if y in self.tables else self.tables[min(self.years, key=lambda z: abs(z - y))]

    def surv(self, sex, a, t0, d):
        """exp(-integral of r mu) for a person aged a last birthday at t0 (exact a + 0.5), over d years"""
        x, t, end, h = a + 0.5, t0, t0 + d, 0.0
        while t < end - 1e-12:
            step = min(math.floor(x) + 1 - x, math.floor(t) + 1 - t, end - t)
            lx = self.table(t)[sex]
            i = min(int(x), len(lx) - 2)
            mu = math.log(max(lx[i], 1e-300) / max(lx[i + 1], 1e-300))
            r = self.ratio[(sex, ratio_band(x))] if self.ratio else 1.0
            h += r * mu * step
            x += step
            t += step
        return math.exp(-h)


def not_in_couple(cs, married, sex):
    side = 0 if sex == "M" else 1
    inc = {}
    for k, c in cs.items():
        inc[k[side]] = inc.get(k[side], 0.0) + c
    return {a: 1 - inc.get(a, 0.0) / married[a] for a in range(15, 86)}


def leaving(n):
    """M014's main reading: the start year as a synthetic cohort, n(a) -> n(a + 5), per five years"""
    lam = {a: (n[min(a + 5, 85)] - n[a]) / (1 - n[a]) for a in range(15, 85)}
    lam[85] = lam[84]
    return lam


def ageing(cs, pop85, life, t0, horizon, lam):
    """The stock of single-age couples cs aged over horizon by survival and leaving: [stock by target cell, cell_to] with
    cell_to[(src cell)] = {target cell: surviving share}"""
    def lam_c(h, w):
        return (lam["M"][min(h, 85)] + lam["F"][min(w, 85)]) / 2 if lam else 0.0

    memo = {}

    def sv(sex, a):
        if (sex, a) not in memo:
            if a < 85:
                memo[(sex, a)] = life.surv(sex, a, t0, horizon)
            else:
                wts = {x: n for x, n in pop85[sex].items() if x >= 85}
                memo[(sex, a)] = sum(n * life.surv(sex, min(x, 105), t0, horizon) for x, n in wts.items()) / sum(wts.values())
        return memo[(sex, a)]

    stock, cell, wid = {}, {}, {}
    k, f = int(horizon), horizon - int(horizon)
    for (h, w), c in cs.items():
        s = sv("M", h) * sv("F", w) * (1 - lam_c(h, w) * horizon / 5.0)
        src = (band_of(h), band_of(w))
        tot = cell.setdefault(src, [0.0, {}])
        tot[0] += c
        wd = wid.setdefault(src, {})
        for sex, own, x in (("F", w, (1 - sv("M", h)) * sv("F", w)), ("M", h, (1 - sv("F", w)) * sv("M", h))):
            key = (sex, band_of(min(own + k, 85)))
            wd[key] = wd.get(key, 0.0) + c * x
        for h2, fh in ((h + k, 1 - f), (h + k + 1, f)):
            for w2, fw in ((w + k, 1 - f), (w + k + 1, f)):
                if fh * fw <= 0:
                    continue
                key = (band_of(min(h2, 85)), band_of(min(w2, 85)))
                stock[key] = stock.get(key, 0.0) + c * s * fh * fw
                tot[1][key] = tot[1].get(key, 0.0) + c * s * fh * fw
    return stock, {src: {k2: v / n for k2, v in d.items()} for src, (n, d) in cell.items() if n}, \
        {src: {k2: v / cell[src][0] for k2, v in d.items()} for src, d in wid.items() if cell[src][0]}


def project_nat(cs, pop85, life, ev, years, t0, horizon, lam):
    """National couples at t0 + horizon by (husband band, wife band): the aged stock plus the surviving net events. Returns
    [pred, stock, net, cell_to, contrib] with cell_to[(src cell)] = {target cell: surviving share} for the prefectures and
    contrib[(year, event husband band, event wife band)] = {target cell: surviving marriages} for R88's split"""
    end = t0 + horizon

    def lam_c(h, w):
        return (lam["M"][min(h, 85)] + lam["F"][min(w, 85)]) / 2 if lam else 0.0

    stock, cell_to, wid_to = ageing(cs, pop85, life, t0, horizon, lam)
    net, contrib, ev_flow = {}, {}, {}
    for kind, sign in (("m", 1.0), ("d", -1.0)):
        for y, share, mid in years:
            d = end - mid
            k2, f2 = int(d), d - int(d)
            for (h0, w0), c in ev[(kind, y)].items():
                hs = range(80, 85) if h0 == 80 else [h0]
                ws = range(80, 85) if w0 == 80 else [w0]
                n = sign * share * c / (len(hs) * len(ws))
                ce = contrib.setdefault((y, ev_band(h0), ev_band(w0)), {}) if kind == "m" else {}
                for h in hs:
                    for w in ws:
                        sh, sw = life.surv("M", h, mid, d), life.surv("F", w, mid, d)
                        base = n * sh * sw * (1 - lam_c(h, w) * d / 5)
                        for h2, fh in ((h + k2, 1 - f2), (h + k2 + 1, f2)):
                            for w2, fw in ((w + k2, 1 - f2), (w + k2 + 1, f2)):
                                key = (kind, band_of(max(h2, 15)), band_of(max(w2, 15)))
                                net[key] = net.get(key, 0.0) + base * fh * fw
                                ce[key[1:]] = ce.get(key[1:], 0.0) + base * fh * fw
                                wt = abs(n) * fh * fw
                                hb2, wb2 = band_of(min(max(h2, 15), 85)), band_of(min(max(w2, 15), 85))
                                if kind == "m":
                                    fl = ev_flow.setdefault(("m", y, ev_band(h0), ev_band(w0)), {})
                                    flows = (("wid", "F", wb2, wt * (1 - sh) * sw), ("wid", "M", hb2, wt * (1 - sw) * sh))
                                else:
                                    fl = ev_flow.setdefault(("d", key[1], key[2]), {})
                                    flows = (("div", "M", hb2, wt * sh), ("div", "F", wb2, wt * sw))
                                for st, sex, b, v in flows:
                                    fl[(st, sex, b)] = fl.get((st, sex, b), 0.0) + v
    pred = dict(stock)
    for (kind, h, w), c in net.items():
        pred[(h, w)] = pred.get((h, w), 0.0) + c
    return pred, stock, net, cell_to, contrib, wid_to, ev_flow


def clip_negative(pp):
    """A prefecture cell below 0 (its share of the divorces above its aged stock, old husbands with young wives) is 0; returns the
    clipped total (T1s-cpb, TO_E 19:48)"""
    neg = 0.0
    for a, cells in pp.items():
        for k, v in cells.items():
            if v < 0.0:
                neg += v
                cells[k] = 0.0
    return neg


def pref_stock(cp, cell_to):
    out = {}
    for src, c in cp.items():
        for key, v in cell_to.get(src, {}).items():
            out[key] = out.get(key, 0.0) + c * v
    return out


def project_pref(cp, cell_to, net, nat_stock, p, contrib, shares, men_p, men_n, mode="r88"):
    """A prefecture: its start cells aged by the national cell transition and survival; divorces by its share of the national aged
    stock in the cell; marriages by mode: 'r88' each year's event cell x the prefecture's share of it by R88 (M020 D20, TO_E 16:58),
    'men' its share of the men in the husband band (M013's rule, withdrawn; kept to reproduce M014's R3)"""
    pred = pref_stock(cp, cell_to)
    stock = dict(pred)
    for (kind, h, w), c in net.items():
        if kind == "d":
            share = stock.get((h, w), 0.0) / nat_stock[(h, w)] if nat_stock.get((h, w)) else 0.0
        elif mode == "men":
            share = men_p[h] / men_n[h] if men_n.get(h) else 0.0
        else:
            continue
        pred[(h, w)] = pred.get((h, w), 0.0) + c * share
    if mode == "r88":
        for (y, hb, wb), cells in contrib.items():
            s = shares[y].get((hb, wb), {}).get(p, 0.0)
            for key, v in cells.items():
                pred[key] = pred.get(key, 0.0) + v * s
    return pred


def margin(t, side):
    out = dict.fromkeys(BANDS, 0.0)
    for k, c in t.items():
        out[k[side]] += c
    return out


def quantile(xs, p):
    s = sorted(xs)
    h = (len(s) - 1) * p
    lo = math.floor(h)
    return s[lo] + (h - lo) * (s[min(lo + 1, len(s) - 1)] - s[lo])


def rows(pred, pp, act, actp, prefs, tol):
    """The six rows' errors (M014's statistic, cells >= 10k)"""
    out = {}
    for side, lab in ((1, "wife"), (0, "husband")):
        pm, am = margin(pred, side), margin(act, side)
        out[f"nat_{lab}"] = [pm[b] / am[b] - 1 for b in BANDS if am[b] >= MIN_CELL]
    cells = [(k, n) for k, n in act.items() if n >= MIN_CELL]
    out["joint_all"] = [pred.get(k, 0.0) / n - 1 for k, n in cells]
    out["joint_35"] = [pred.get(k, 0.0) / n - 1 for k, n in cells if min(BANDS.index(k[0]), BANDS.index(k[1])) >= BANDS.index("35-39")]
    nat_e = {b: margin(pred, 1)[b] / margin(act, 1)[b] - 1 for b in BANDS}
    pw, pr = [], []
    for a in prefs:
        pm, am = margin(pp[a], 1), margin(actp[a], 1)
        for b in BANDS:
            if am[b] >= MIN_CELL:
                e = pm[b] / am[b] - 1
                pw.append(e)
                pr.append((1 + e) / (1 + nat_e[b]) - 1)
    out["pref_wife"] = pw
    out["pref_rel"] = pr
    out["pref_husband"] = [margin(pp[a], 0)[b] / margin(actp[a], 0)[b] - 1 for a in prefs for b in BANDS if margin(actp[a], 0)[b] >= MIN_CELL]
    res = {}
    for k, es in out.items():
        a = [abs(e) for e in es]
        n = len(a)
        beyond = sum(1 for x in a if x > tol[k])
        allowed = 0.05 * n + 2 * math.sqrt(0.05 * 0.95 * n)
        res[k] = {"n": n, "p95": quantile(a, 0.95), "max": max(a), "tol": tol[k], "beyond": beyond, "allowed": allowed,
                  "beyond_twice": sum(1 for x in a if x > 2 * tol[k]), "pass": beyond <= allowed and all(x <= 2 * tol[k] for x in a)}
    return res


def pref_rates(c_start, cs, pop85, nat_tables, ratio, r89, mar, lam_nat, t0, horizon, prefs):
    """§12.15 (TO_E 17:10): each prefecture's cell transition with its own survival (R89 ratios) and leaving (R82), the summed
    prefecture stocks the divorces are shared by, and the widowhood flow per couple (§12.16)"""
    lb_nat = lam_band(c_start[NAT], mar[NAT])
    cell, tot, wid = {}, {}, {}
    for a in prefs:
        life_p = Life(pref_tables(nat_tables, r89, a), ratio)
        cell[a], wid[a] = ageing(cs, pop85, life_p, t0, horizon, lam_pref(lam_nat, lb_nat, lam_band(c_start[a], mar[a])))[1:]
        for key, v in pref_stock(c_start[a], cell[a]).items():
            tot[key] = tot.get(key, 0.0) + v
    return cell, tot, wid


def marital_2024(prefs, mar20, c20, pp, cpf, widp, evf, shares, stf, fr, r88, tables, r89, years, t0, horizon):
    """§12.16 (M021, TO_E 17:15): per prefecture ('0' the sum) x sex x band (15-19 .. 85+) at the start: [R77c's couple persons,
    the 2020 married-apart ratio, never married by the cohort identity (-1 at 15-19, the remainder there), widowed, divorced,
    the remarriages taken off them]"""
    end = t0 + horizon
    k = int(horizon)
    out = {}
    for a in prefs:
        sv = Life(pref_tables(tables, r89, a), None)
        st = pref_stock(c20[a], cpf[a])
        rows = {}
        for side, sex in ((0, "M"), (1, "F")):
            sp = "husband" if sex == "M" else "wife"
            c24, cp20 = margin(pp[a], side), margin(c20[a], side)
            m20 = dict.fromkeys(BANDS, 0.0)
            nev, wid, dv, first, re = (dict.fromkeys(BANDS, 0.0) for _ in range(5))
            for x in range(15, 101):
                d = mar20.get((a, sex, x))
                if not d:
                    continue
                m20[band_of(x)] += d["married"]
                to = band_of(min(x + k, 85))
                surv = sv.surv(sex, min(x, 105), t0, horizon)
                nev[to] += d["never_married"] * surv
                wid[to] += d["widowed"] * surv
                dv[to] += d["divorced"] * surv
            for src, c in c20[a].items():
                for (sx, b), v in widp[a].get(src, {}).items():
                    if sx == sex:
                        wid[b] += c * v
            for key, fl in evf.items():
                if key[0] == "m":
                    shr = shares[key[1]].get((key[2], key[3]), {}).get(a, 0.0)
                else:
                    shr = st.get((key[1], key[2]), 0.0) / stf[(key[1], key[2])] if stf.get((key[1], key[2])) else 0.0
                for (stt, sx, b), v in fl.items():
                    if sx == sex:
                        (wid if stt == "wid" else dv)[b] += v * shr
            for y, share, mid in years:
                dy, lag = min(y, 2022), int(end - mid)
                tot = {b: sum(v for (p2, b2), v in r88[(dy, sp)].items() if b2 == b) for b in BANDS[:14]}
                for e in range(15, 83):
                    eb = ev_band(e)
                    w88 = r88[(dy, sp)].get((a, eb), 0.0) / tot[eb] if tot.get(eb) else 0.0
                    to = band_of(min(e + lag, 85))
                    first[to] += share * fr.get((dy, sex, e, "first"), 0.0) * w88
                    re[to] += share * fr.get((dy, sex, e, "re"), 0.0) * w88
            row = []
            for b in BANDS:
                r = max(0.0, (m20[b] - cp20[b]) / cp20[b]) if cp20[b] > 0 else 0.0
                wd = wid[b] + dv[b]
                w2 = wid[b] - re[b] * wid[b] / wd if wd > 0 else 0.0
                d2 = dv[b] - re[b] * dv[b] / wd if wd > 0 else 0.0
                n2 = -1.0 if b == BANDS[0] else max(0.0, nev[b] - first[b])
                row.append([c24[b], r, n2, max(0.0, w2), max(0.0, d2), re[b]])
            rows[sex] = row
        out[str(int(a[:2]))] = [rows["M"], rows["F"]]
    nat = []
    for si in range(2):
        rr = []
        for bi in range(15):
            col = [sum(out[str(int(a[:2]))][si][bi][j] for a in prefs) for j in range(6)]
            c = col[0]
            col[1] = sum(out[str(int(a[:2]))][si][bi][0] * out[str(int(a[:2]))][si][bi][1] for a in prefs) / c if c else 0.0
            col[2] = -1.0 if bi == 0 else col[2]
            rr.append(col)
        nat.append(rr)
    out["0"] = nat
    return out


def main(out_path, p77, p77s, p78c, p78s, p78p, p76, p80c, p80s, p80l, p82x, p82m, p82d, p75, p81, p88, p89, mode="r88", rates="pref"):
    assert mode in ("r88", "men") and rates in ("pref", "nat"), (mode, rates)
    r89 = read_r89(p89)
    tol = dict(TOL, **TOL_MEN) if mode == "men" else TOL
    r88 = read_r88(p88)
    c20, c15 = read_couples(p77), read_couples(p78c)
    cs15, cs20 = read_couples_single(p78s), read_couples_single(p77s)
    pop15 = read_pop2015_single(p78p)
    men20 = read_men2020(p76)
    marg, total_div = read_margins_and_divorces(p80s)
    cross = read_cross_single(p82x)
    married = read_married(p82m)
    total100 = read_married(p82m, "total", 110)
    ratio = read_ratio(p82d)
    prefs = sorted(a for a in c20 if a != NAT)
    # the backtest, 2015.75 -> 2020.75, as M014's R3: 2020's table alone, 2015's synthetic-cohort leaving, the crosses of 2018 for
    # 2015-17 (D1)
    by = [(2015, 0.25, 2015.875), (2016, 1.0, 2016.5), (2017, 1.0, 2017.5), (2018, 1.0, 2018.5), (2019, 1.0, 2019.5), (2020, 0.75, 2020.375)]
    ev_b = events(cross, marg, total_div, by, lambda k, y: (2018 if y < 2018 else y) if k == "m" else y)
    lam_b = {s: leaving(not_in_couple(cs15, married[(2015, s)], s)) for s in ("M", "F")}
    tab_b = {2020: read_life_r80(p80l, "2020")}
    life_b = Life(tab_b, ratio)
    pred_b, stock_b, net_b, cell_b, con_b, _, _ = project_nat(cs15, pop15, life_b, ev_b, by, 2015.75, 5.0, lam_b)
    cpb, stb, _ = ({a: cell_b for a in prefs}, stock_b, None) if rates == "nat" else pref_rates(c15, cs15, pop15, tab_b, ratio, r89, read_married_pref(p82m, 2015), lam_b, 2015.75, 5.0, prefs)
    sh_b = {y: split_year(ev_b[("m", y)], r88[(y, "husband")], r88[(y, "wife")], prefs) for y, _, _ in by}
    pp_b = {a: project_pref(c15[a], cpb[a], net_b, stb, a, con_b, sh_b, men20[a], men20[NAT], mode) for a in prefs}
    neg_b = clip_negative(pp_b)
    back = rows(pred_b, pp_b, c20[NAT], c20, prefs, tol)
    # the start, 2020.75 -> 2024.75 (§12.15): each year's own table, 2020's synthetic-cohort leaving, 2023 and 2024 at 2022's events
    fy = [(2020, 0.25, 2020.875), (2021, 1.0, 2021.5), (2022, 1.0, 2022.5), (2023, 1.0, 2023.5), (2024, 0.75, 2024.375)]
    marg[(2023, "h")], marg[(2023, "w")], marg[(2024, "h")], marg[(2024, "w")] = marg[(2022, "h")], marg[(2022, "w")], marg[(2022, "h")], marg[(2022, "w")]
    total_div[2023] = total_div[2024] = total_div[2022]
    ev_f = events(cross, marg, total_div, fy, lambda k, y: min(y, 2022))
    lam_f = {s: leaving(not_in_couple(cs20, married[(2020, s)], s)) for s in ("M", "F")}
    tables = {2020: read_life_r80(p80l, "2020"), 2021: read_life_r80(p80l, "2021")}
    for y in (2022, 2023, 2024):
        tables[y] = read_life_r75(p75, str(y))
    life_f = Life(tables, ratio)
    pop20 = {s: total100[(2020, s)] for s in ("M", "F")}
    pred_f, stock_f, net_f, cell_f, con_f, wid_f, evf_f = project_nat(cs20, pop20, life_f, ev_f, fy, 2020.75, 4.0, lam_f)
    cpf, stf, widp = ({a: cell_f for a in prefs}, stock_f, {a: wid_f for a in prefs}) if rates == "nat" else pref_rates(c20, cs20, pop20, tables, ratio, r89, read_married_pref(p82m, 2020), lam_f, 2020.75, 4.0, prefs)
    sh_f = {y: split_year(ev_f[("m", y)], r88[(min(y, 2022), "husband")], r88[(min(y, 2022), "wife")], prefs) for y, _, _ in fy}
    men22 = read_men2022(p81)
    men_n = men22.get(NAT) or {b: sum(men22[a][b] for a in men22) for b in BANDS}
    pp_f = {a: project_pref(c20[a], cpf[a], net_f, stf, a, con_f, sh_f, men22[a], men_n, mode) for a in prefs}
    neg_f = clip_negative(pp_f)
    mar20 = read_marital_single(p82m, 2020)
    m24 = marital_2024(prefs, mar20, c20, pp_f, cpf, widp, evf_f, sh_f, stf, read_first_re(p80s), r88, tables, r89, fy, 2020.75, 4.0)
    nm_share = {}
    for y in (2015, 2020):
        my = mar20 if y == 2020 else read_marital_single(p82m, 2015)
        for sex in ("M", "F"):
            nm_share[(y, sex)] = [0.0] * 15
            al = [0.0] * 15
            for x in range(15, 101):
                d = my.get((NAT, sex, x))
                if d:
                    nm_share[(y, sex)][BANDS.index(band_of(x))] += d["never_married"]
                    al[BANDS.index(band_of(x))] += sum(d.values())
            nm_share[(y, sex)] = [n / t if t else 0.0 for n, t in zip(nm_share[(y, sex)], al)]
    out = {"marriage_share": mode, "rates": rates, "backtest": back,
           "marital_2024": {"by_pref": m24, "never_share_2015": [nm_share[(2015, "M")], nm_share[(2015, "F")]],
                            "never_share_2020": [nm_share[(2020, "M")], nm_share[(2020, "F")]]},
           "national": {"%s|%s" % k: v for k, v in pred_f.items()},
           "by_pref": {str(int(a[:2])): [[pp_f[a].get((h, w), 0.0) for w in BANDS] for h in BANDS] for a in prefs},
           "totals": {"2020": sum(cs20.values()), "start_national": sum(pred_f.values()), "start_prefs": sum(sum(sum(r) for r in v) for v in [[[pp_f[a].get((h, w), 0.0) for w in BANDS] for h in BANDS] for a in prefs]),
                      "negative_clipped": [neg_b, neg_f], "stock": sum(stock_f.values()), "marriages": sum(c for (k, _, _), c in net_f.items() if k == "m"), "divorces": sum(c for (k, _, _), c in net_f.items() if k == "d")}}
    json.dump(out, open(out_path, "w", encoding="utf-8"), indent=1)
    for k, r in back.items():
        print("BACKTEST %-12s n %3d P95 %6.2f%% (tol %5.2f%%) max %6.2f%% beyond %3d allowed %5.1f twice %d %s" % (k, r["n"], 100 * r["p95"], 100 * r["tol"], 100 * r["max"], r["beyond"], r["allowed"], r["beyond_twice"], "PASS" if r["pass"] else "FAIL"))
    print("START couples 2020 %.0f -> start %.0f national (prefectures %.0f); stock %.0f, + marriages %.0f, - divorces %.0f" % (
        out["totals"]["2020"], out["totals"]["start_national"], out["totals"]["start_prefs"], out["totals"]["stock"], out["totals"]["marriages"], -out["totals"]["divorces"]))


if __name__ == "__main__":
    main(*sys.argv[1:20])
