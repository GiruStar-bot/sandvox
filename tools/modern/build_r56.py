"""data/modern/r56.json: R56's inputs for R55's rules (MODERN_PLAN 3), read from R56_values.csv and R56_alliances.csv, each value checked
against its row's text.
  python3 -I tools/modern/build_r56.py --values data/modern/src/R56_values.csv --alliances data/modern/src/R56_alliances.csv \
      --out data/modern/r56.json
Vintage rule (R56 section 0): values published by 2022-12-31 only (V22). Costs are WEO 2022 Table B.4a (2021, USD 2021): capex USD/kW,
capacity factor, fuel + CO2 + O&M USD/MWh, for US, EU, China and India; learning from IRENA RCS 2022 (end-2021 cumulative MW); WACC from
WEO 2022 Table 4.2 (middle of each range). Alliances are kept with their dates; a run reads the membership in force at its start only."""
import argparse, csv, hashlib, json, re

COST_ITEMS = {"coal": "coal", "gas": "gas CCGT", "solar": "utility PV", "wind": "onshore wind", "nuclear": "nuclear"}
REGIONS = {"US": "US", "EU": "EU", "China": "China", "India": "India"}
# lifetimes for moving the capital part of WEO's LCOE to an entity's WACC (modern_costs.gd)
LIFE_YR = {"solar": (25, "S: WEO 2022"), "wind": (25, "S: WEO 2022"), "coal": (40, "T: R55's retirement age"),
           "gas": (30, "T: NF in R56"), "nuclear": (60, "T: GCAM lifetime (R55)")}
WACC_STATES = {"Europe": None, "United States": "USA", "China": "CHN", "Brazil": "BRA", "India": "IND", "Indonesia": "IDN", "Mexico": "MEX",
               "South Africa": "ZAF"}
# R56 Part 1 (T): high 4-5%, upper-middle 5-10%, lower-middle and low 10-13%; the middle of each
WACC_BY_INCOME = {"high": 0.045, "upper_middle": 0.075, "lower_middle": 0.115, "low": 0.115}
LEARNING_RATE = {"solar": (0.23, "S: Rubin 2015 via R55"), "wind": (0.12, "S: Rubin 2015 via R55")}
CUMULATIVE = {"solar": "solar PV", "wind": "onshore wind"}
# defence treaties and unions count as allies for coalition following (T); arrangements and SCO do not
ALLY_TYPES = ["alliance", "union"]
NOT_ALLIES = ["SCO"]
REGIMES = ["Wassenaar"]
# the G20's member states (the WTO G20 report's scope; the EU, its 20th member, acts through member states here: T)
G20 = ["ARG", "AUS", "BRA", "CAN", "CHN", "FRA", "DEU", "IND", "IDN", "ITA", "JPN", "KOR", "MEX", "RUS", "SAU", "ZAF", "TUR", "GBR", "USA"]
# HS chapters outside food, feed and agriculture (Sections I-IV are chapters 1-24; chapter 77 is reserved): 97 - 24 - 1
NON_FOOD_CHAPTERS = 72


def mid(text):
    a, b = re.findall(r"[\d.]+", text)[:2]
    return (float(a) + float(b)) / 200.0


def join_day(text):
    """The latest date the text allows for joining (so 'joined by'), as YYYY-MM-DD; None if no year at all"""
    ys = re.findall(r"(\d{4})(?:-(\d\d)-(\d\d))?", text)
    if not ys:
        return None
    y, m, d = max(ys)
    return "%s-%s-%s" % (y, m or "12", d or "31")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--values", required=True)
    ap.add_argument("--alliances", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    rv = open(a.values, "rb").read()
    rows = list(csv.DictReader(rv.decode("utf-8").splitlines()))
    out = {"values_sha256": hashlib.sha256(rv).hexdigest(), "costs": {}, "life_yr": LIFE_YR, "wacc": {}, "wacc_by_income": WACC_BY_INCOME,
           "learning": {}, "weo_wacc": {"solar": 0.045, "wind": 0.045, "coal": 0.075, "gas": 0.075, "nuclear": 0.075}}
    for r in rows:
        if r["part"] == "1 costs" and r["region"] in REGIONS:
            for src, item in COST_ITEMS.items():
                if r["item"] == item:
                    capex, cf, var, lcoe = [float(x) for x in r["value"].split(";")]
                    out["costs"].setdefault(REGIONS[r["region"]], {})[src] = {"capex_usd_kw": capex, "cf": cf / 100.0, "var_usd_mwh": var,
                                                                                "lcoe_pub": lcoe, "source": r["source_file_line"]}
        if r["part"] == "1 WACC" and r["region"] in WACC_STATES:
            out["wacc"][r["region"]] = {"value": mid(r["value"]), "iso3": WACC_STATES[r["region"]], "source": r["source_file_line"]}
        if r["part"] == "1 learning" and r["year_described"] == "2021":
            for src, item in CUMULATIVE.items():
                if r["item"] == item:
                    out["learning"][src] = {"cum_mw_2021": float(r["value"]), "rate": LEARNING_RATE[src][0], "label": LEARNING_RATE[src][1],
                                            "source": r["source_file_line"]}
        if r["part"] == "3 fiscal" and r["item"].startswith("income thresholds"):
            if not ("<=1085" in r["value"] and "1086-4255" in r["value"] and "4256-13205" in r["value"]):
                raise SystemExit("income thresholds row changed: " + r["value"])
            out["income_thresholds_gni_pc"] = {"low_max": 1085.0, "lower_middle_max": 4255.0, "upper_middle_max": 13205.0, "source": r["source_file_line"]}
        if r["part"] == "4 trade" and r["item"].startswith("new export restrictions"):
            if not ("22 in mid-May to mid-Oct 2022" in r["value"] and "16 food" in r["value"]):
                raise SystemExit("restrictions row changed: " + r["value"])
            out["restrictions"] = {"g20_new_per_yr": 22.0 * 12.0 / 5.0, "non_food_share": 6.0 / 22.0, "source": r["source_file_line"],
                                   "label": "S count, D yearly rate (22 in 5 months), D non-food 6 of 22", "g20": G20,
                                   "non_food_chapters": NON_FOOD_CHAPTERS,
                                   "per_state_good_yr": 22.0 * 12.0 / 5.0 * 6.0 / 22.0 / len(G20) / NON_FOOD_CHAPTERS,
                                   "rule": "T: the G20's non-food rate spread evenly over its 19 states and the 72 non-food HS chapters; one of our goods = one chapter"}
    for src in COST_ITEMS:
        for reg in REGIONS.values():
            if src not in out["costs"].get(reg, {}):
                raise SystemExit("no WEO cost for %s %s" % (reg, src))
    ra = open(a.alliances, "rb").read()
    al = []
    for r in csv.DictReader(ra.decode("utf-8").splitlines()):
        if r["iso3"] == "VEN" and r["org"] == "Rio Treaty" and "disputed" in r["join_date"]:
            continue    # Why not both Venezuela rows: R56's neutral default (T) follows actual administration, so Venezuela is not a party
        al.append({"org": r["org"], "iso3": r["iso3"], "type": r["type"], "joined_by": join_day(r["join_date"]),
                   "left": join_day(r["left_date"]) if r["left_date"] else None, "source": r["source_file_line"]})
    out["alliances"] = {"rows": al, "ally_types": ALLY_TYPES, "not_allies": NOT_ALLIES, "regimes": REGIMES,
                        "rule": "T: coalition partners are members of the same defence treaty or union as of the run's start; the follower must sit in a regime (Wassenaar) too",
                        "sha256": hashlib.sha256(ra).hexdigest()}
    json.dump(out, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1, sort_keys=True)
    open(a.out, "a").write("\n")
    print("R56 costs %s; WACC %d states; learning %s; alliance rows %d" % (sorted(out["costs"]), len(out["wacc"]), sorted(out["learning"]), len(al)))


if __name__ == "__main__":
    main()
