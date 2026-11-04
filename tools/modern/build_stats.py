"""Per-entity statistics for the modern field (MODERN_PLAN 1.3) from the official files on the modern-data branch (PM 2026-10-28 22:10).
  python3 -I tools/modern/build_stats.py --data <modern-data checkout> --ember latest|2022-07 --entities data/modern/entities.json \
      --years 2016,2017,2018,2019,2020,2021,2022,2023,2024 --out data/modern/stats.json
Sources (an entity's value is the sum over its data codes: its own and the territories R54 merges into it):
  population: WDI SP.POP.TOTL; where WDI has no row, WPP 2024 estimates (years up to 2023 only, never its projections)
  GDP: WDI NY.GDP.MKTP.CD (current US$) and NY.GDP.MKTP.KD (constant 2015 US$); Taiwan from DGBAS (per-capita GDP in US$, the four quarters
    summed, x population) and DGBAS's real growth rate
  electricity: Ember's yearly long-format release, generation by fuel, demand and net imports (TWh); --ember picks the file: "2022-07" (the
    July 2022 vintage, data to 2021) or "latest"; a code the chosen file leaves out entirely is read from the next of: the latest long file
    (ember_revised), the latest release's generation file (Albania, ember_revised_gen)
Why not fill a year a file leaves out for a code it has (Kosovo's 2021 in the 2022 vintage) from a later file: the loader holds the latest
earlier year, which is what had been published by the vintage's date
Owner ruling (a): where a 2022 vintage is gone the latest file is used for years up to the start, labelled REVISED; every figure carries its
source tag (wdi_revised, wpp2024_revised, dgbas_revised, ember_2022_07, ember_revised, ember_revised_gen). A value with no source row is null: never guessed."""
import argparse, csv, gzip, hashlib, json, os, re
from collections import defaultdict

ELEC = {"Coal": "coal", "Gas": "gas", "Other Fossil": "oil", "Nuclear": "nuclear", "Hydro": "hydro", "Wind": "wind", "Solar": "solar",
        "Bioenergy": "bioenergy", "Other Renewables": "other_renewable"}
EMBER = {"2022-07": ("raw/ember_yearly_full_release_long_format_vintage_2022-07.csv.gz", "Country code", "ember_2022_07"),
         "latest": ("raw/ember_yearly_full_release_long_format.csv.gz", "ISO 3 code", "ember_revised")}
# rows kept but PROVISIONAL (licence or source to replace)
PROVISIONAL = {"JPN": {"figures": ["generation", "demand", "net_imports"] + list(ELEC.values()),
                       "why": "Ember's Japan yearly generation is sourced from the Energy Institute, terms NOT FOUND (R53, PM 2026-10-28 15:50); ANRE's "
                              "table 2-(1) on modern-data covers electricity businesses only (FY2021 863.8 TWh, solar 19.0 TWh) and leaves out captive "
                              "and most rooftop generation, so it cannot replace the whole-country series; a government energy balance would"}}


def sha(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def wdi(path, codes):
    out = defaultdict(dict)
    with gzip.open(path, "rt", encoding="utf-8-sig") as f:
        r = csv.reader(f)
        head = next(r)
        ci, ii = head.index("Country Code"), head.index("Indicator Code")
        years = {i: int(h) for i, h in enumerate(head) if h.isdigit()}
        for row in r:
            if row[ii] in codes:
                for i, y in years.items():
                    if row[i] != "":
                        out[(row[ci], row[ii])][y] = float(row[i])
    return out


def wpp(path):
    out = defaultdict(float)
    with gzip.open(path, "rt", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            if row["ISO3_code"] and row["Variant"] == "Medium" and row["PopTotal"]:
                out[(row["ISO3_code"], int(row["Time"]))] += float(row["PopTotal"]) * 1000.0
    return out


def dgbas(data):
    t = open(os.path.join(data, "raw/taiwan_ogdl/6800_per_capita_quarterly.xml"), encoding="utf-8").read()
    pc = defaultdict(float)
    n = defaultdict(int)
    for item, period, typ, val in re.findall(r"<Item>([^<]+)</Item><TIME_PERIOD>(\d{4})Q\d</TIME_PERIOD><FREQ>Q</FREQ><TYPE>([^<]+)</TYPE>\s*"
                                             r"<Item_VALUE>([^<]*)</Item_VALUE>", t):
        if item == "平均每人GDP、當期價格U.S.元" and typ == "原始值" and val:
            pc[int(period)] += float(val)
            n[int(period)] += 1
    t2 = open(os.path.join(data, "raw/taiwan_ogdl/44230_gdp_contribution_by_expenditure_year.xml"), encoding="utf-8").read()
    growth = {}
    for item, period, typ, val in re.findall(r"<Item>([^<]+)</Item><TIME_PERIOD>(\d{4})</TIME_PERIOD><FREQ>Y</FREQ><TYPE>([^<]+)</TYPE>\s*"
                                             r"<Item_VALUE>([^<]*)</Item_VALUE>", t2):
        if item == "經濟成長率(百分點)" and typ == "原始值" and val:
            growth[int(period)] = float(val) / 100.0
    return {y: v for y, v in pc.items() if n[y] == 4}, growth


def ember(path, col):
    out = defaultdict(dict)
    with gzip.open(path, "rt", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            if r["Unit"] != "TWh" or r["Value"] == "":
                continue
            key = None
            if r["Category"] == "Electricity generation" and r["Subcategory"] == "Fuel" and r["Variable"] in ELEC:
                key = ELEC[r["Variable"]]
            elif r["Category"] == "Electricity demand" and r["Variable"] == "Demand":
                key = "demand"
            elif r["Category"] == "Electricity imports" and r["Variable"] == "Net Imports":
                key = "net_imports"
            if key:
                out[(r[col], int(r["Year"]))][key] = float(r["Value"])
    return out


GEN_FILE = "raw/ember_release_generation_yearly_global.csv.gz"
GEN = {"Coal": "coal", "Gas": "gas", "Other fossil": "oil", "Nuclear": "nuclear", "Hydro": "hydro", "Wind": "wind", "Solar": "solar",
       "Bioenergy": "bioenergy", "Other renewables": "other_renewable", "Demand": "demand", "Net imports": "net_imports"}


def ember_gen(path):
    out = defaultdict(dict)
    with gzip.open(path, "rt", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            if r["Area type"] == "Country or economy" and r["Electricity source"] in GEN and r["Generation (TWh)"] != "":
                out[(r["ISO 3 code"], int(r["Year"]))][GEN[r["Electricity source"]]] = float(r["Generation (TWh)"])
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--ember", required=True, choices=sorted(EMBER))
    ap.add_argument("--entities", required=True)
    ap.add_argument("--years", default="2016,2017,2018,2019,2020,2021,2022,2023,2024")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    years = [int(y) for y in a.years.split(",")]
    ent = json.load(open(a.entities, encoding="utf-8"))
    members = ent["data_codes"]
    wdi_path = os.path.join(a.data, "extracts/wdi_selected.csv.gz")
    w = wdi(wdi_path, {"SP.POP.TOTL", "NY.GDP.MKTP.CD", "NY.GDP.MKTP.KD"})
    wpp_path = os.path.join(a.data, "extracts/wpp2024_single_age_2010-2023.csv.gz")
    wp = wpp(wpp_path)
    tw_pc, tw_growth = dgbas(a.data)
    epath, ecol, etag = EMBER[a.ember]
    em = ember(os.path.join(a.data, epath), ecol)
    em_tag = {k: etag for k in em}
    chain = [] if a.ember == "latest" else [ember(os.path.join(a.data, EMBER["latest"][0]), EMBER["latest"][1])]
    chain.append(ember_gen(os.path.join(a.data, GEN_FILE)))
    for more, tag in zip(chain, ["ember_revised", "ember_revised_gen"][-len(chain):]):
        have = {c for c, _ in em}
        for k, v in more.items():
            if k[0] not in have:
                em[k], em_tag[k] = v, tag

    def wsum(codes, ind, y):
        vals = [w[(c, ind)][y] for c in codes if y in w.get((c, ind), {})]
        return sum(vals) if vals else None

    out = {"years": years, "ember": a.ember, "units": {"population": "persons", "gdp": "current US$", "gdp_real": "constant 2015 US$ (TWN: none)",
           "electricity": "TWh a year"},
           "sources": {"modern-data/" + p: sha(os.path.join(a.data, p)) for p in [epath] + ([] if a.ember == "latest" else [EMBER["latest"][0]]) + [GEN_FILE, "extracts/wdi_selected.csv.gz", "extracts/wpp2024_single_age_2010-2023.csv.gz",
                                                                                  "raw/taiwan_ogdl/6800_per_capita_quarterly.xml",
                                                                                  "raw/taiwan_ogdl/44230_gdp_contribution_by_expenditure_year.xml"]},
           "members": members, "entities": {}, "provisional": PROVISIONAL}
    gaps = defaultdict(list)
    for e in ent["entities"]:
        k = e["key"]
        codes = members[k]
        rows = {}
        for y in years:
            pop = wsum(codes, "SP.POP.TOTL", y)
            p_src = "wdi_revised" if pop is not None else None
            if pop is None and y <= 2023:
                vals = [wp[(c, y)] for c in codes if (c, y) in wp]
                pop = sum(vals) if vals else None
                p_src = "wpp2024_revised" if pop is not None else None
            gdp = wsum(codes, "NY.GDP.MKTP.CD", y)
            g_src = "wdi_revised" if gdp is not None else None
            gdp_real = wsum(codes, "NY.GDP.MKTP.KD", y)
            real_growth = None
            if k == "TWN" and y in tw_pc and pop is not None:
                gdp, g_src = tw_pc[y] * pop, "dgbas_revised"
                real_growth = tw_growth.get(y)
            row = {"population": pop, "population_src": p_src, "gdp": gdp, "gdp_src": g_src, "gdp_real": gdp_real, "gdp_real_growth": real_growth}
            ev = [em[(c, y)] for c in codes if (c, y) in em]
            tags = sorted({em_tag[(c, y)] for c in codes if (c, y) in em})
            for name in list(ELEC.values()) + ["demand", "net_imports"]:
                vs = [d[name] for d in ev if name in d]
                row[name] = sum(vs) if vs else None
            srcs = [row[s] for s in ELEC.values() if row[s] is not None]
            row["generation"] = sum(srcs) if srcs else None
            row["electricity_src"] = "+".join(tags) if row["generation"] is not None else None
            rows[str(y)] = row
            for q in ("population", "gdp", "generation", "demand"):
                if row[q] is None:
                    gaps["%s_%d" % (q, y)].append(k)
        out["entities"][k] = rows
    out["gaps"] = {k: sorted(v) for k, v in sorted(gaps.items())}
    json.dump(out, open(a.out, "w", encoding="utf-8"), separators=(",", ":"), sort_keys=True, ensure_ascii=False)
    open(a.out, "a").write("\n")
    for y in years:
        print("STATS %s %d: population gaps %d, gdp gaps %d, generation gaps %d, demand gaps %d" % (a.ember, y, len(gaps.get("population_%d" % y, [])),
              len(gaps.get("gdp_%d" % y, [])), len(gaps.get("generation_%d" % y, [])), len(gaps.get("demand_%d" % y, []))))


if __name__ == "__main__":
    main()
