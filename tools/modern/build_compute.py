"""The compute chain's macro table (MODERN_PLAN 1.3) from R53's rows, each value checked against its row's text.
  python3 -I tools/modern/build_compute.py --r53 data/modern/src/R53_modern_data.csv --r54 data/modern/src/R54_compute_shares.csv \
      --out data/modern/compute_chain.json
Macro regions (R53 Q4): CN (mainland China), TW, JP, KR, US, EU (EU-27), ROW. A share R53 gives for some regions only leaves a remainder;
how a remainder is placed is a stated THEORY rule per row ("rest"). SOURCED values keep R53's source line. The SIA/BCG rows R54 read from the
report's figures (R54_compute_shares.csv, every macro region given) replace R53's text for fab capacity, <10 nm logic and ATP."""
import argparse, csv, hashlib, json

MACROS = ["CN", "TW", "JP", "KR", "US", "EU", "ROW"]
R54_COLS = {"US": "US", "EU": "EU", "JP": "JP", "KR": "KR", "TW": "TW", "CN": "CN", "RoW": "ROW"}
# good: (R54 block, item, year), read whole from R54_compute_shares.csv
R54_ROWS = {"fab_capacity": ("fab capacity", "total", "2022"), "logic_lt10nm": ("fab capacity", "logic <10 nm", "2022"), "atp": ("value added", "ATP", "2022")}
# good: (R53 quantity text to find, the text the value must appear in, {macro: share}, rest rule, label)
SHARES = {
    "fab_capacity": ("wafer fab capacity 2022", "24/18/17/17/10/8/7", {"CN": 0.24, "TW": 0.18, "JP": 0.17, "KR": 0.17, "US": 0.10, "EU": 0.08, "ROW": 0.07},
                     None, "SOURCED"),
    "logic_lt10nm": ("logic <10 nm 2022", "69/31", {"TW": 0.69, "KR": 0.31}, None, "SOURCED"),
    "atp": ("ATP capacity 2022", "30/28/20", {"CN": 0.30, "TW": 0.28, "ROW": 0.20}, "by fab_capacity over JP, KR, US, EU", "SOURCED + THEORY rest"),
    "lithography": ("lithography by HQ EU", "89%", {"EU": 0.89}, "JP (R53: ArF immersion only from the Netherlands and Japan)", "SOURCED + THEORY rest"),
    "photoresist": ("photoresist Japan", "90%", {"JP": 0.90}, "by fab_capacity over the others", "SOURCED + THEORY rest"),
    "silicon_wafers": ("silicon wafers Japan HQ", "56%", {"JP": 0.56}, "by fab_capacity over the others", "SOURCED + THEORY rest"),
    "gallium": ("primary gallium mainland China", "99%", {"CN": 0.99}, "ROW", "SOURCED + THEORY rest"),
    "neon": ("semiconductor neon Ukraine", "45-54%", {"ROW": 0.495}, "by fab_capacity over all but ROW", "SECONDARY (mid of 45-54%, Ukraine in ROW) + THEORY rest"),
    "dc_electricity": ("data-centre electricity 2024", "45/25/15", {"US": 0.45, "CN": 0.25, "EU": 0.15}, "JP 19 TWh (R53: under 20 TWh), then by GDP over TW, KR, ROW",
                       "SOURCED (EU read as R53's 'Europe') + THEORY rest"),
}
# entity a share of ROW goes to by name, not by the GDP rule
NAMED_IN_ROW = {"neon": "UKR"}
SCALARS = {
    "dc_electricity_twh_2024": (415.0, "data-centre electricity 2024", "415 TWh", "SOURCED"),
    "dc_capacity_gw_2024": (100.0, "installed DC capacity now", "~100 GW", "SOURCED"),
    "pue": (1.43, "PUE global", "1.43", "SOURCED"),
    "dc_water_bn_l_per_yr": (560.0, "DC water consumption now", "~560", "THEORY (IEA model)"),
    "semi_electricity_twh": (100.0, "semiconductor industry electricity", "> 100 TWh", "SECONDARY (a lower bound)"),
    "jp_dc_twh": (19.0, "data-centre electricity 2024", "45/25/15", "THEORY: R53 gives Japan under 20 TWh"),
}
# The year each input's data is dated (PM ruling 2026-10-28 14:10, no look-ahead: a run may only use data dated up to its start year), with
# its basis; None = not stated in R53/R54 (undated: listed for R55). Where only the source's publication year is known, that year is used.
DATED = {
    "shares/fab_capacity": (2022, "SIA/BCG 2024, 2022 figures"), "shares/logic_lt10nm": (2022, "SIA/BCG 2024, 2022 figures"),
    "shares/atp": (2022, "SIA/BCG 2024, 2022 figures"), "shares/lithography": (2024, "publication: SIA/BCG 2024 / CSET"),
    "shares/photoresist": (2021, "publication: CSET 2021"), "shares/silicon_wafers": (2021, "publication: CSET 2021"),
    "shares/gallium": (2024, "USGS MCS 2025 (2024 data)"), "shares/neon": (None, "press (Reuters calc), year not stated"),
    "shares/dc_electricity": (2024, "IEA Energy and AI 2025, 2024 figures"),
    "scalars/dc_electricity_twh_2024": (2024, "IEA Energy and AI 2025"), "scalars/dc_capacity_gw_2024": (2024, "IEA Energy and AI 2025 ('now')"),
    "scalars/pue": (2024, "publication: IEA / Uptime"), "scalars/dc_water_bn_l_per_yr": (2024, "IEA Energy and AI 2025 ('now')"),
    "scalars/semi_electricity_twh": (None, "IEA (secondary), year not stated"), "scalars/jp_dc_twh": (2024, "IEA Energy and AI 2025, 2024"),
    "lead_days/dc": (2025, "publication: IEA 2025"), "lead_days/fab": (None, "CSET No Permits No Fabs, year not stated"),
    "lead_days/transmission": (None, "IEA grids, year not stated"), "lead_days/nuclear": (2024, "WNA, units connected 2024"),
    "lead_days/solar": (None, "R53 md (Australia), year not stated"), "lead_days/wind": (None, "R53 md (Australia), year not stated"),
    "lead_days/gas": (None, "R53 md, year not stated"), "lead_days/storage": (2025, "as dc"), "lead_days/coal": (None, "as gas"),
    "lead_days/oil": (None, "as gas"), "lead_days/hydro": (2024, "as nuclear"), "lead_days/bioenergy": (None, "as gas"),
    "lead_days/other_renewable": (None, "as wind"),
}
# lead times in days (R53 Q3); a range takes its middle (stated)
LEAD_DAYS = {
    "dc": (912, "data centre to operation", "2-3 yr", "SOURCED (middle of 2-3 yr)"),
    "fab": (682, "fab construction start to production", "682 days", "SOURCED"),
    "transmission": (2190, "transmission lines / new grid / transformers", "4-8 yr", "SOURCED (middle of 4-8 yr)"),
    "nuclear": (3468, "nuclear construction", "114 months", "SOURCED (114 months x 30.42 days)"),
    "solar": (1247, None, None, "SOURCED: R53_modern_data.md section 1 item 3, solar 41 months (Australia), x 30.42 days"),
    "wind": (1612, None, None, "SOURCED: R53_modern_data.md section 1 item 3, onshore wind 53 months (Australia), x 30.42 days"),
    "gas": (1825, None, None, "SECONDARY: R53_modern_data.md section 1 item 3, gas turbines about 5 yr"),
    "storage": (912, None, None, "THEORY: no storage lead time in R53; the data centre's middle (2.5 yr) is used"),
    "coal": (1825, None, None, "THEORY: no coal or oil plant lead time in R53; the gas turbine's 5 yr is used"),
    "oil": (1825, None, None, "THEORY: as coal"),
    "hydro": (3468, None, None, "THEORY: no hydro lead time in R53; nuclear's 114 months is used"),
    "bioenergy": (1825, None, None, "THEORY: as coal"),
    "other_renewable": (1612, None, None, "THEORY: as onshore wind"),
}


def row_of(rows, quantity):
    for i, r in enumerate(rows):
        if quantity in r["quantity"]:
            return i, r
    raise SystemExit("R53 row not found: " + quantity)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--r53", required=True)
    ap.add_argument("--r54", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    raw = open(a.r53, "rb").read()
    rows = list(csv.DictReader(raw.decode("utf-8").splitlines()))
    raw54 = open(a.r54, "rb").read()
    rows54 = list(csv.DictReader(raw54.decode("utf-8").splitlines()))
    out = {"macros": MACROS, "r53_sha256": hashlib.sha256(raw).hexdigest(), "r54_sha256": hashlib.sha256(raw54).hexdigest(), "shares": {}, "scalars": {}, "lead_days": {},
           "named_in_row": NAMED_IN_ROW, "member_rule": "a macro region's share goes to its member entities by their GDP share inside it (THEORY); "
           "NAMED_IN_ROW entities take ROW's share of that good alone"}
    for g, (q, text, given, rest, label) in SHARES.items():
        if g in R54_ROWS:
            blk, item, year = R54_ROWS[g]
            j, r54 = next((j, r) for j, r in enumerate(rows54) if (r["block"], r["item"], r["year"]) == (blk, item, year))
            out["shares"][g] = {"given": {m: int(r54[c]) / 100.0 for c, m in R54_COLS.items() if int(r54[c]) != 0}, "rest": None,
                                "label": "SOURCED (SIA/BCG 2024 figure, read by R54)", "r54_row": j + 2, "source": r54["source"]}
            continue
        i, r = row_of(rows, q)
        if text not in r["value"]:
            raise SystemExit("R53 row %d (%s) has no %r" % (i + 2, q, text))
        out["shares"][g] = {"given": given, "rest": rest, "label": label, "r53_row": i + 2, "source": r["source_file_line"]}
    for k, (v, q, text, label) in SCALARS.items():
        i, r = row_of(rows, q)
        if text not in r["value"] + r["quantity"]:
            raise SystemExit("R53 row %d (%s) has no %r" % (i + 2, q, text))
        out["scalars"][k] = {"value": v, "label": label, "r53_row": i + 2}
    for k, (v, q, text, label) in LEAD_DAYS.items():
        rec = {"days": v, "label": label}
        if q is not None:
            i, r = row_of(rows, q)
            if text not in r["value"]:
                raise SystemExit("R53 row %d (%s) has no %r" % (i + 2, q, text))
            rec["r53_row"] = i + 2
        out["lead_days"][k] = rec
    for k, (y, basis) in DATED.items():
        blk, name = k.split("/")
        out[blk][name]["data_year"] = y
        out[blk][name]["data_year_basis"] = basis
    json.dump(out, open(a.out, "w", encoding="utf-8"), indent=1, sort_keys=True)
    open(a.out, "a").write("\n")
    print("COMPUTE goods %d scalars %d lead times %d (R53 sha256 %s)" % (len(out["shares"]), len(out["scalars"]), len(out["lead_days"]), out["r53_sha256"][:12]))


if __name__ == "__main__":
    main()
