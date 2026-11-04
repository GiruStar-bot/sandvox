"""data/modern/dc_history.json: the data-centre start and its persistence growth per base year (R55 Q5; MODERN_PLAN 3), from
R55_dc_history.csv.
  python3 -I tools/modern/build_dc.py --r55 data/modern/src/R55_dc_history.csv --out data/modern/dc_history.json
Rule (R55 Q5, T): yearly growth = the mean yearly growth of the last years known at the vintage date, per macro region; a region with no
series takes the world's. The start uses the vintage a run could know: a 2022 start the end-2022 vintage (R55's recommendation: the IEA
Sep 2022 world value, 270 TWh for 2021, split US 70 / EU 77 / JP 14 and the rest to CN, TW, KR and ROW by GDP); a 2024 start the
IEA Energy and AI 2025 table (data dated 2020-2024, per the PM's data-dated rule; R53's 415 TWh split stays). Each value below names the
CSV row text it must match, so the tool stops if R55's table changes."""
import argparse, csv, hashlib, json

# base year: start world TWh, given macro TWh (the rest by GDP over the macros named in rest_over, or the R53 split), growth per macro
BLOCKS = {
    "2022": {
        "vintage": "end-2022 (R55 Q5 recommendation)",
        "world_twh": (270.0, "World", "2021", "220-320 (excl. crypto)", "D: middle of 220-320; band +-50 declared by R55"),
        "given_twh": {"US": (70.0, "US", "2014", "~70", "S: LBNL 2016, flat"), "EU": (77.0, "EU28", "2018", "76.8", "S: EC 2020 (EU28 read as EU)"),
                      "JP": (14.0, "Japan", "2018", "14", "S: JST FY2020")},
        "rest_over": ["CN", "TW", "KR", "ROW"],
        "rest_note": "T: the residual by GDP; mainland China disputed (Greenpeace/NCEPU 161 TWh for 2018, secondary)",
        "growth": {"world": ((270.0 / 200.0) ** (1 / 6) - 1, "World 2015 ~200 -> 2021 270 (IEA Sep 2022 vintage)", "D"),
                   "US": (0.01, "US ~70 flat (LBNL 2016: R55 'US ~1%/yr')", "S"),
                   "EU": ((76.8 / 53.9) ** (1 / 8) - 1, "EU28 2010 53.9 -> 2018 76.8 (EC 2020)", "D")},
        "checks": [("World", "2015", "~200"), ("EU28", "2010", "53.9")],
    },
    "2024": {
        "vintage": "IEA Energy and AI, Apr 2025 (Table A.4), data dated 2020-2024",
        "world_twh": None,
        "given_twh": {},
        "rest_over": [],
        "rest_note": "the start keeps R53's 415 TWh and its 45/25/15 split (compute_chain.json)",
        "growth": {"world": ((416.0 / 269.0) ** 0.25 - 1, "World 2020 269 -> 2024 416", "D"),
                   "US": ((183.0 / 108.0) ** 0.25 - 1, "US 2020 108 -> 2024 183", "D"),
                   "EU": ((68.0 / 57.0) ** 0.25 - 1, "Europe 2020 57 -> 2024 68 (read as EU)", "D"),
                   "CN": ((102.0 / 62.0) ** 0.25 - 1, "Mainland China 2020 62 -> 2024 102", "D"),
                   "JP": ((48.0 / 31.0) ** 0.25 - 1, "Asia-Pacific less mainland China 2020 31 -> 2024 48 (T: JP, KR, TW take it)", "D + T"),
                   "KR": ((48.0 / 31.0) ** 0.25 - 1, "as JP", "D + T"), "TW": ((48.0 / 31.0) ** 0.25 - 1, "as JP", "D + T"),
                   "ROW": ((15.0 / 11.0) ** 0.25 - 1, "World less US, Europe, Asia-Pacific: 2020 11 -> 2024 15", "D")},
        "checks": [("World", "2020/2023/2024", "269/361/416"), ("US", "2020/2023/2024", "108/154/183"), ("Europe", "2020/2023/2024", "57/66/68"),
                   ("Mainland China", "2020/2023/2024", "62/84/102")],
    },
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--r55", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    raw = open(a.r55, "rb").read()
    rows = list(csv.DictReader(raw.decode("utf-8").splitlines()))

    def must(region, year, text):
        for r in rows:
            if r["region"] == region and r["year_described"] == year and text in r["twh"]:
                return r["source_file_line"]
        raise SystemExit("R55_dc_history.csv has no %s %s %r" % (region, year, text))

    out = {"r55_sha256": hashlib.sha256(raw).hexdigest(), "rule": "R55 Q5 (T): persistence of the mean yearly growth known at the vintage, per macro region; a macro with no series takes the world's", "years": {}}
    for y, b in BLOCKS.items():
        blk = {"vintage": b["vintage"], "rest_over": b["rest_over"], "rest_note": b["rest_note"], "given_twh": {}, "growth": {}, "sources": []}
        if b["world_twh"] is not None:
            v, reg, yr, text, label = b["world_twh"]
            blk["world_twh"] = {"value": v, "label": label, "source": must(reg, yr, text)}
        for m, (v, reg, yr, text, label) in b["given_twh"].items():
            blk["given_twh"][m] = {"value": v, "label": label, "source": must(reg, yr, text)}
        for m, (g, basis, label) in b["growth"].items():
            blk["growth"][m] = {"value": g, "basis": basis, "label": label}
        for reg, yr, text in b["checks"]:
            blk["sources"].append(must(reg, yr, text))
        out["years"][y] = blk
    json.dump(out, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1, sort_keys=True)
    open(a.out, "a").write("\n")
    print("DC_HISTORY %s" % {y: {m: round(g["value"], 4) for m, g in b["growth"].items()} for y, b in out["years"].items()})


if __name__ == "__main__":
    main()
