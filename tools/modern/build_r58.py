"""data/modern/r58.json: R58's data-centre inputs published by the end of 2022 (PM 2026-10-28 22:10), from R58_dc_2022.csv, each value checked
against its row's text. They replace, for a run starting in a year R58 covers, the compute chain's PUE and DC lead time (both dated 2024-25).
  python3 -I tools/modern/build_r58.py --r58 data/modern/src/R58_dc_2022.csv --out data/modern/r58.json
PUE per macro region as R58 Part 1 proposes (T): US the Uptime 2020 derivation, EU Uptime 2020's Europe, CN the 2021 national average
(secondary), JP, KR, TW and ROW the world's Uptime 2021 value. DC lead: planning to operation about 18 months (one contractor quote,
January 2022, secondary) = 18 x 365 / 12 days, rounded. No world MW before 2023 (R58 NOT FOUND): the IT load factor and the capacity stay
the compute chain's 2024 values, so C12 stays not independent for the build rule."""
import argparse, csv, hashlib, json


def row(rows, item, scope):
    for r in rows:
        if r["item"] == item and r["scope"] == scope:
            return r
    raise SystemExit("R58 row not found: %s / %s" % (item, scope))


def must(r, text):
    if text not in r["value"]:
        raise SystemExit("R58 row %r / %r no longer says %r" % (r["item"], r["scope"], text))
    return r["source_file_line"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--r58", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    raw = open(a.r58, "rb").read()
    rows = list(csv.DictReader(raw.decode("utf-8").splitlines()))
    world = row(rows, "PUE", "world")
    region = row(rows, "PUE", "Europe / Africa+ME / US-Canada")
    china = row(rows, "PUE", "mainland China")
    lead = row(rows, "lead time", "world")
    mw = row(rows, "capacity MW", "world")
    must(mw, "NOT FOUND")
    w_src = must(world, "1.57")
    pue = {"US": {"value": 1.53, "data_year": 2020, "published": 2020, "label": "D (Uptime 2020: Europe 'almost 5% lower')", "source": must(region, "~1.53")},
           "EU": {"value": 1.46, "data_year": 2020, "published": 2020, "label": "S (Uptime 2020, Europe)", "source": must(region, "1.46")},
           "CN": {"value": 1.49, "data_year": 2021, "published": 2022, "label": "2nd (broker report, June 2022)", "source": must(china, "1.49")}}
    for m in ["JP", "KR", "TW", "ROW"]:
        pue[m] = {"value": 1.57, "data_year": 2021, "published": 2021, "label": "S (Uptime 2021, world); T: R58 gives no value of its own for it", "source": w_src}
    out = {
        "r58_sha256": hashlib.sha256(raw).hexdigest(),
        "years": {"2022": {
            "pue": pue,
            "lead_days_dc": {"value": round(18 * 365 / 12), "data_year": 2022, "published": 2022, "label": "2nd (one contractor quote, January 2022); T: no grid wait added",
                             "source": must(lead, "~18 months")},
        }},
        "not_inputs": "world DC capacity in MW before 2023 is NOT FOUND (R58); the grid waits dated 2022 (Dublin, Northern Virginia) are not modelled per site",
    }
    json.dump(out, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1, sort_keys=True)
    open(a.out, "a").write("\n")
    print("R58 2022: PUE %s; DC lead %d days" % (", ".join("%s %.2f" % (m, v["value"]) for m, v in sorted(pue.items())), out["years"]["2022"]["lead_days_dc"]["value"]))


if __name__ == "__main__":
    main()
