"""data/modern/r57.json: R57's inputs for the fab growth rule (MODERN_PLAN 3), from R57_fab_growth.csv and R56_values.csv, each value checked
against its row's text.
  python3 -I tools/modern/build_r57.py --r57 data/modern/src/R57_fab_growth.csv --r56 data/modern/src/R56_values.csv --out data/modern/r57.json
The field's fab capacity unit is the world's capacity at the start (sum 1): for a 2022 start, end-2021's 25.6 M wspm (200 mm-eq, SEMI, V22, D).
Rule (R57 Part 2-3, T as R57 declares): a year's industry fab capex = KAPPA x semiconductor revenue; the private part is split by fab capacity
share and raised by each region's public share; capacity added = capex / cost per wspm (R56's band, declared, not averaged); 682 days to
production, then a linear ramp; utilisation at its base, up to its top while chips are short."""
import argparse, csv, hashlib, json


def row(rows, item, scope, metric):
    for r in rows:
        if r["item"] == item and r["scope"] == scope and r["metric"] == metric:
            return r
    raise SystemExit("R57 row not found: %s / %s / %s" % (item, scope, metric))


def must(r, text):
    if text not in r["value"]:
        raise SystemExit("R57 row %r no longer says %r" % (r["item"], text))
    return r["source_file_line"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--r57", required=True)
    ap.add_argument("--r56", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    raw = open(a.r57, "rb").read()
    rows = list(csv.DictReader(raw.decode("utf-8").splitlines()))
    raw56 = open(a.r56, "rb").read()
    rows56 = list(csv.DictReader(raw56.decode("utf-8").splitlines()))
    cap = row(rows, "capacity", "world", "2020/2021/2022 level")
    capex = row(rows, "capex", "world", "2019/2020/2021 US$ bn")
    ratio = row(rows, "capex/revenue", "world", "2010/2013/2016/2017/2018/2019/2020/2021")
    rule = row(rows, "rule (theory)", "world", "capex")
    pub = row(rows, "public share of TCO", "US / KR-TW-SG / CN", "10-yr TCO")
    build = row(rows, "build time", "world", "construction start to production")
    ref = {}
    for r in rows56:
        for k, item, text in [("low", "65 nm analog fab, 40k wspm", "~125k/wspm"), ("ref", "3D NAND fab, 100k wspm", "~200k/wspm"),
                              ("high", "5 nm logic fab, 35k wspm", "~571k USD/wspm")]:
            if r["part"] == "7 capex" and r["item"] == item:
                if text not in r["value"]:
                    raise SystemExit("R56 capex row %r changed" % item)
                ref[k] = r["source_file_line"]
    out = {
        "r57_sha256": hashlib.sha256(raw).hexdigest(),
        "world_wspm_start": {"2022": {"value": 25.6e6, "label": "D: SEMI 2022-09-27, end-2021 (+7.4% on 2020)", "source": must(cap, "~25.6")}},
        "revenue_usd_start": {"2022": {"value": 153.9e9 / 0.277, "label": "D: 2021 capex 153.9 bn / capex-to-revenue 27.7%",
                                        "source": must(capex, "~153.9") + "; " + must(ratio, "27.7")}},
        "kappa": {"value": 0.21, "band": [0.16, 0.28], "label": "T (R57): the pre-pandemic mean 20.6%, rounded as R57 states", "source": must(rule, "kappa 0.21")},
        "cost_per_wspm": {"low": 125e3, "ref": 200e3, "high": 571e3, "default": "ref",
                          "label": "S/D (R56 reference fabs); a band, not an average (R56); the default is the NAND reference (T)", "sources": ref},
        "public_share": {"US": 0.125, "KR": 0.275, "TW": 0.275, "JP": 0.275, "CN": 0.35, "EU": 0.125, "ROW": 0.275,
                         "label": "S: SIA/BCG TCO shares, middles: US 10-15, KR/TW/SG 25-30, CN 30-40; T: JP as KR/TW/SG, EU as the US, ROW as KR/TW/SG",
                         "source": must(pub, "10-15 / 25-30 / 30-40")},
        "build_days": {"value": 682, "source": must(build, "682 days")},
        "ramp_days": {"value": 274, "label": "T (R57): linear over 9 months after production starts"},
        "utilisation": {"base": 0.86, "top": 0.95, "label": "T (R57): base the 2019-20 mean, top the upper bound", "source": must(rule, "utilisation 0.86 (max 0.95)")},
        "not_inputs": "the US CHIPS Act (Aug 2022) and later programmes are dated events after a 2022 start: checks, not inputs; public shares stand in for subsidies",
    }
    json.dump(out, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1, sort_keys=True)
    open(a.out, "a").write("\n")
    print("R57 revenue %.1f bn, kappa %.2f, capex/yr %.1f bn, world %.1f M wspm" % (out["revenue_usd_start"]["2022"]["value"] / 1e9, 0.21,
          0.21 * out["revenue_usd_start"]["2022"]["value"] / 1e9, 25.6))


if __name__ == "__main__":
    main()
