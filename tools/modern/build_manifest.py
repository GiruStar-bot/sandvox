"""data/modern/MANIFEST.json: every data file of the modern mode with its sha256, how it was made, its sources, licences and labels, what is
provisional, the official input files (the orphan modern-data branch, PM 2026-10-28 22:10) and what is still missing (MODERN_PLAN 1.5).
  python3 -I tools/modern/build_manifest.py --fetch-log <download folder>/fetch_log.json --data <modern-data checkout> --data-commit <sha> \
      --out data/modern/MANIFEST.json
Each modern-data file is recorded with its sha256 as read here, checked against the branch's own lists (ORIGINALS_SHA256.json for files kept
whole, raw/MANUAL_SHA256.txt for the browser downloads); a text file whose CRLF line ends were turned into LF on commit is matched by its
CRLF form, a gzipped original by its content, and either is recorded so; any other mismatch in raw/ stops the build."""
import argparse, gzip, hashlib, json, os

FILES = {
    "regions.json": {"tool": "tools/modern/dump_regions.gd, then tools/modern/canon_json_file.py (the committed bytes are this chain's output, V091)", "from": "world/planet/earth_regions.gd (present-day coast)", "label": "DERIVED"},
    "src/R53_modern_data.csv": {"tool": "byte copy of research-notes R53_modern_data.csv", "from": "R53", "label": "SOURCED (R53's own labels per row)"},
    "src/R54_entities.csv": {"tool": "byte copy of research-notes R54_entities.csv", "from": "R54 Part 2", "label": "SOURCED"},
    "src/R54_compute_shares.csv": {"tool": "byte copy of research-notes R54_compute_shares.csv", "from": "R54 Part 2 (SIA/BCG 2024 figures)", "label": "SOURCED"},
    "src/R54_japan_view.csv": {"tool": "byte copy of research-notes R54_japan_view.csv", "from": "R54 Part 3 (MOFA)", "label": "SOURCED"},
    "src/R54_visibility.csv": {"tool": "byte copy of research-notes R54_visibility.csv", "from": "R54 Part 4", "label": "SOURCED / DERIVED / THEORY per row"},
    "src/R54_checks.csv": {"tool": "byte copy of research-notes R54_checks.csv", "from": "R54 Part 5 (declared before any run)", "label": "SOURCED"},
    "entities.json": {"tool": "tools/modern/build_entities.py + entity_rules.json", "from": "R54_entities.csv, ne_10m_admin_0_countries.geojson", "label": "SOURCED list + DERIVED (rule)"},
    "entity_regions.json": {"tool": "tools/modern/build_entity_cells.py", "from": "ne_10m_admin_0_countries.geojson, regions.json", "label": "DERIVED"},
    "stats.json": {"tool": "tools/modern/build_stats.py --ember latest", "from": "modern-data: WDI extract, WPP 2024 extract, DGBAS, Ember latest", "label": "SOURCED, REVISED (owner ruling a)",
                   "provisional": "Japan's electricity rows (Ember via the Energy Institute, terms NOT FOUND); a government whole-country series would replace them"},
    "stats_v2022.json": {"tool": "tools/modern/build_stats.py --ember 2022-07 --years 2019,2020,2021", "from": "modern-data: WDI extract, WPP 2024 extract, DGBAS, Ember July 2022 vintage",
                         "label": "SOURCED; electricity in its 2022 vintage, population and GDP REVISED (owner ruling a)",
                         "provisional": "Japan's electricity rows (as stats.json)"},
    "compute_chain.json": {"tool": "tools/modern/build_compute.py", "from": "R54_compute_shares.csv, R53_modern_data.csv", "label": "SOURCED shares + THEORY remainders (per row)",
                           "provisional": "hand-down inside a macro region by GDP (R54's fallback): R54's rule by BACI exports needs BACI (blocked here)"},
    "views/jpn.json": {"tool": "tools/modern/build_view.py + view_jpn_rules.json", "from": "R54_japan_view.csv, R55_territory_names.csv, NE names", "label": "SOURCED (MOFA); 3 territories in general usage"},
    "views/test_b.json": {"tool": "tools/modern/build_view.py + view_test_b_rules.json", "from": "test fixture", "label": "TEST FIXTURE (no real view)"},
    "visibility.json": {"tool": "tools/modern/build_visibility.py", "from": "R54_visibility.csv", "label": "SOURCED / DERIVED per row; T for the uniform estimate error"},
    "src/R55_dc_history.csv": {"tool": "byte copy of research-notes R55_dc_history.csv", "from": "R55 Q5", "label": "SOURCED (by vintage)"},
    "src/R55_territory_names.csv": {"tool": "byte copy of research-notes R55_territory_names.csv", "from": "R55 Q6 (MOFA)", "label": "SOURCED (10 of 13)"},
    "src/R55_rule_actors.csv": {"tool": "byte copy of research-notes R55_rule_actors.csv", "from": "R55 Q1/Q4", "label": "S / D / MA / T per row (the rule set's parameters)"},
    "dc_history.json": {"tool": "tools/modern/build_dc.py", "from": "R55_dc_history.csv", "label": "SOURCED values, DERIVED growth, T persistence rule (R55 Q5)"},
    "src/R56_values.csv": {"tool": "byte copy of research-notes R56_values.csv", "from": "R56", "label": "S / D / 2nd per row, with vintage and licence"},
    "src/R56_alliances.csv": {"tool": "byte copy of research-notes R56_alliances.csv", "from": "R56 Part 5", "label": "SOURCED (dates; NF where marked)"},
    "src/R56_hs_codes.csv": {"tool": "byte copy of research-notes R56_hs_codes.csv", "from": "R56 Part 4", "label": "SOURCED (WCO)"},
    "src/R56_file_only.csv": {"tool": "byte copy of research-notes R56_file_only.csv", "from": "R56", "label": "the owner's download list"},
    "r56.json": {"tool": "tools/modern/build_r56.py", "from": "R56_values.csv, R56_alliances.csv", "label": "SOURCED values (V22), T where the tool says (lifetimes, WACC mapping, ally types)"},
    "src/R57_fab_growth.csv": {"tool": "byte copy of research-notes R57_fab_growth.csv", "from": "R57", "label": "S / D / 2nd / T per row"},
    "r57.json": {"tool": "tools/modern/build_r57.py", "from": "R57_fab_growth.csv, R56_values.csv", "label": "D levels, S shares, T rule parameters (as R57 declares)"},
    "src/R58_dc_2022.csv": {"tool": "byte copy of research-notes R58_dc_2022.csv", "from": "R58", "label": "S / D / 2nd / NF / T per row"},
    "r58.json": {"tool": "tools/modern/build_r58.py", "from": "R58_dc_2022.csv", "label": "S / D / 2nd PUE by macro region, 2nd DC lead (as R58 proposes, T)"},
    "checks.json": {"tool": "tools/modern/build_checks.py", "from": "R54_checks.csv", "label": "SOURCED (declared before any run)"},
}
LICENCES = {
    "ne_10m_admin_0_countries.geojson": "public domain (Natural Earth)", "ne_10m_admin_0_countries_jpn.geojson": "public domain (Natural Earth)",
}
# modern-data files: (path, licence, vintage, revised, read by)
INPUTS = [
    ("raw/ember_yearly_full_release_long_format_vintage_2022-07.csv.gz", "CC BY 4.0", "July 2022 (data to 2021)", False, "build_stats.py (stats_v2022.json)"),
    ("raw/ember_yearly_full_release_long_format.csv.gz", "CC BY 4.0", "latest (2026)", True, "build_stats.py (stats.json)"),
    ("raw/ember_release_generation_yearly_global.csv.gz", "CC BY 4.0", "latest (2026)", True, "not read yet (capacity GW for the reserve margin)"),
    ("raw/eia_INTL_latest.zip", "public domain", "latest", True, "not read yet (oil and gas balances)"),
    ("raw/eia_INTL_wayback_2023-02-16.zip", "public domain", "Feb 2023 capture", True, "not read yet (oil and gas balances, 2022 run)"),
    ("raw/imf_WEOOct2022all_wayback_2022-10-19.tsv_utf16.gz", "IMF terms: commercial use with attribution", "Oct 2022, exact", False, "not read yet (fiscal rules)"),
    ("raw/nrel_ATB_2022_v2_Workbook_Corrected_7-21-2022.xlsx", "CC BY 4.0", "2022 v2", False, "not read yet (O&M split; WEO 2022 costs are used)"),
    ("raw/wgi_wgidataset.xlsx", "CC BY 4.0", "latest; years <= start", True, "not read yet (institutional quality, fiscal rules)"),
    ("raw/OGHIST_2026_10_08.xlsx", "CC BY 4.0", "history; the FY of the start year", False, "not read yet (income groups)"),
    ("raw/CLASS_hist_2026_10_08.xlsx", "CC BY 4.0", "history", False, "not read yet"),
    ("raw/taiwan_ogdl/6800_per_capita_quarterly.xml", "OGDL v1.0", "latest", True, "build_stats.py (Taiwan GDP)"),
    ("raw/taiwan_ogdl/44230_gdp_contribution_by_expenditure_year.xml", "OGDL v1.0", "latest", True, "build_stats.py (Taiwan real growth)"),
    ("raw/taiwan_ogdl/14226_population_single_age_sex_area.csv", "OGDL v1.0", "2020 only", True, "not read (one year only; WPP gives Taiwan's population)"),
    ("raw/usgs/MCS2026_Commodities_Data.csv", "CC0", "2026", True, "not read yet (minerals)"),
    ("raw/japan_anre/denryoku_chosa_hatsuden_jisseki_FY2021.xlsx", "PDL 1.0", "FY2021", False, "cross-check only: electricity businesses, no captive or most rooftop generation"),
    ("raw/japan_anre/denryoku_chosa_hatsuden_jisseki_FY2022.xlsx", "PDL 1.0", "FY2022", False, "cross-check only"),
    ("raw/japan_anre/denryoku_chosa_hatsuden_jisseki_FY2025.xlsx", "PDL 1.0", "FY2025", False, "cross-check only"),
    ("extracts/wdi_selected.csv.gz", "CC BY 4.0", "latest (extract of WDI_CSV.zip)", True, "build_stats.py (population, GDP, real GDP)"),
    ("extracts/wpp2024_single_age_2010-2023.csv.gz", "CC BY 3.0 IGO", "WPP 2024 estimates", True, "build_stats.py (population where WDI has none)"),
    ("extracts/wpp2024_single_age_2024-2050.csv.gz", "CC BY 3.0 IGO", "WPP 2024 projections", False, "never an input (projections); checks only"),
    ("extracts/baci_hs17_v202601_selected_hs6.csv.gz", "Etalab 2.0", "V202601 (extract)", True, "not read yet (compute hand-down, trade values)"),
    ("extracts/baci_hs17_v202601_pair_chapter_totals.csv.gz", "Etalab 2.0", "V202601 (extract)", True, "not read yet (trade values)"),
]
BLOCKED = [
    {"needed": "Taiwan Energy Administration supply and demand", "host": "moeaea.gov.tw / data.gov.tw", "licence": "OGDL v1.0", "replaces": "nothing: blocked by the site even in a browser; Taiwan's electricity is in Ember"},
    {"needed": "a Japanese government whole-country generation series (energy balance)", "host": "ANRE / e-Stat", "licence": "PDL 1.0", "replaces": "Japan's provisional Ember rows (ANRE table 2-(1) covers electricity businesses only)"},
    {"needed": "peak demand by entity at a <=2022 vintage", "host": "not found yet", "licence": "-", "replaces": "nothing yet: R55's 15% reserve margin needs peaks; capacity GW is in Ember's July 2022 vintage on modern-data"},
    {"needed": "ATOP v5.1, COW alliances, the OECD export-restriction inventory", "host": "-", "licence": "NOT FOUND", "replaces": "nothing: not fetched, NOT FOR THE PRODUCT"},
    {"needed": "Beck 2023 koppen_geiger_0p1.tif and the ERA5 monthly npz", "host": "figshare / Copernicus CDS", "licence": "CC BY 4.0 / Copernicus", "replaces": "earth_climate.bin without the 3000 BC corrections (not read by the field yet)"},
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fetch-log", required=True)
    ap.add_argument("--data", required=True)
    ap.add_argument("--data-commit", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    base = os.path.dirname(a.out)
    files = {}
    for name, meta in FILES.items():
        data = open(os.path.join(base, name), "rb").read()
        files[name] = dict(meta, sha256=hashlib.sha256(data).hexdigest(), bytes=len(data))
    fetched = []
    for row in json.load(open(a.fetch_log, encoding="utf-8")):
        if row["name"] in LICENCES:
            fetched.append(dict(row, licence=LICENCES[row["name"]], note="mirror copy (Natural Earth's host is blocked here)"))
    known = {}
    for r in json.load(open(os.path.join(a.data, "extracts/ORIGINALS_SHA256.json"), encoding="utf-8")):
        known[r["sha256"]] = r["file"]
    for line in open(os.path.join(a.data, "raw/MANUAL_SHA256.txt"), encoding="utf-8"):
        if line.strip():
            h, f = line.split(None, 1)
            known[h] = f.strip().lstrip("*")
    inputs = []
    for path, lic, vintage, revised, used in INPUTS:
        raw = open(os.path.join(a.data, path), "rb").read()
        h = hashlib.sha256(raw).hexdigest()
        listed = known.get(h)
        note = None
        if listed is None and path.startswith("raw/") and path.endswith(".gz"):
            h_in = hashlib.sha256(gzip.decompress(raw)).hexdigest()
            if h_in in known:
                listed, note = known[h_in], "gzip of the original; its content has the listed sha256 " + h_in
        if listed is None and b"\r" not in raw and not path.endswith(".gz"):
            h_crlf = hashlib.sha256(raw.replace(b"\n", b"\r\n")).hexdigest()
            if h_crlf in known:
                listed, note = known[h_crlf], "committed with LF line ends; the original (CRLF) has the listed sha256 " + h_crlf
        if listed is None and path.startswith("raw/"):
            raise SystemExit("modern-data %s: sha256 %s is in neither ORIGINALS_SHA256.json nor MANUAL_SHA256.txt" % (path, h))
        inputs.append({"path": path, "branch": "modern-data", "commit": a.data_commit, "sha256": h, "listed_as": listed or "extract or gzip of an original (see README)",
                       "licence": lic, "vintage": vintage, "revised": revised, "read_by": used, **({"matched": note} if note else {})})
    out = {"files": files, "fetched": fetched, "inputs": inputs, "blocked_here": BLOCKED,
           "rules": "labels per MODERN_PLAN: SOURCED / DERIVED / THEORY / CALIBRATED; projections and dated policy events are checks, never inputs; R54 declared the hindcast checks before any run (checks.json); nothing is CALIBRATED against them"}
    json.dump(out, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1, sort_keys=True)
    open(a.out, "a").write("\n")
    print("MANIFEST files %d, mirror copies %d, modern-data inputs %d (%d listed by sha256), still missing %d" % (len(files), len(fetched), len(inputs),
          sum(1 for i in inputs if not i["listed_as"].startswith("extract")), len(BLOCKED)))


if __name__ == "__main__":
    main()
