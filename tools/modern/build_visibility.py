"""data/modern/visibility.json: what one seat sees of another entity's figures (MODERN_PLAN 4, view scope b), from R54's visibility table.
  python3 -I tools/modern/build_visibility.py --r54 data/modern/src/R54_visibility.csv --out data/modern/visibility.json
Each field figure below names its R54 row; the tool stops if that row no longer says what the mapping assumes. A figure of year Y is
visible from 1 January Y+1 plus the lag (days). "exact" shows the truth; "estimate" shows truth x (1 + u), u fixed per entity, figure and
year, uniform within the row's spread (T: the spread is R54's, the uniform draw is ours). A field figure not listed here is unpublished:
another seat's observation has no key for it."""
import argparse, csv, hashlib, json

# figure: (R54 figure_type, text the row's what_another_state_sees must contain, basis, lag days, spread, label, note)
FIGURES = {
    "population": ("population total", "exact", "exact", 182, 0.0, "S", "lag ~6 months"),
    "gdp": ("GDP", "exact for SDDS reporters", "exact", 91, 0.0, "S + T",
            "annual figure one quarter late; R54's quarterly series and the 1-2 quarters of non-SDDS reporters need data the field lacks"),
    "generation_twh": ("electricity generation", "exact", "exact", 365, 0.0, "S", "lag ~12 months"),
    "generation_by_source_twh": ("electricity generation", "exact", "exact", 365, 0.0, "S", "Ember's mix in the same release"),
    "demand_twh": ("electricity generation", "exact", "exact", 365, 0.0, "S + T", "T: demand comes in the same Ember release as generation"),
    "fab_capacity": ("fab capacity", "industry estimate only", "estimate", 365, 0.15, "D", "+-15% from source spread"),
    "dc_capacity_mw": ("data-centre capacity/electricity", "industry/IEA estimate", "estimate", 365, 0.25, "D", "+-25% from source spread"),
    "dc_twh": ("data-centre capacity/electricity", "industry/IEA estimate", "estimate", 365, 0.25, "D", "+-25% from source spread"),
}
# entity: figure -> (basis, lag) where R54 names an exception
EXCEPTIONS = {"IRL": {"dc_capacity_mw": ("exact", 152), "dc_twh": ("exact", 152)}}
# Why not publish licences with a lag: export controls are announced when they take effect (T); R54's table has no row for them
PUBLIC_AT_ONCE = ["licences_closed"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--r54", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    raw = open(a.r54, "rb").read()
    rows = {r["figure_type"]: r for r in csv.DictReader(raw.decode("utf-8").splitlines())}
    out = {"r54_sha256": hashlib.sha256(raw).hexdigest(), "figures": {}, "exceptions": EXCEPTIONS, "public_at_once": PUBLIC_AT_ONCE,
           "own_state": "exact, no lag (R54 row 'own state'; MODERN_DESIGN 4)", "unlisted": "unpublished: no key in another seat's observation"}
    for f, (ft, text, basis, lag, spread, label, note) in FIGURES.items():
        r = rows.get(ft)
        if r is None or text not in r["what_another_state_sees"]:
            raise SystemExit("R54 row %r does not say %r" % (ft, text))
        out["figures"][f] = {"r54_row": ft, "basis": basis, "lag_days": lag, "spread": spread, "label": label, "note": note,
                             "r54_lag": r["lag"], "r54_uncertainty": r["uncertainty"], "source": r["basis_file_line"]}
    if "Ireland" not in rows["data-centre capacity/electricity"]["what_another_state_sees"]:
        raise SystemExit("R54's DC row no longer names Ireland's exception")
    json.dump(out, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1, sort_keys=True)
    open(a.out, "a").write("\n")
    print("VISIBILITY %d published figures, exceptions %s" % (len(out["figures"]), list(EXCEPTIONS)))


if __name__ == "__main__":
    main()
