"""The modern mode's entity table from R54's entity list on Natural Earth's de-facto admin-0 layer (MODERN_PLAN 1.3).
  python3 -I tools/modern/build_entities.py --ne <ne_10m_admin_0_countries.geojson> --r54 data/modern/src/R54_entities.csv \
      --rules tools/modern/entity_rules.json --out data/modern/entities.json
Rule (entity_rules.json, stated there): R54's entities but the de-facto ones with no base data (those start inside their host, flagged);
each NE feature to the entity of its code, a merged territory to its host, a feature R54 does not name to its administrator, the
unadministered scraps to none. Internal ids are the row order (sorted by key), and the field never shows them.
kind from R54's type: un_member, observer, region (other separately administered), dependency (dependent territory)."""
import argparse, csv, hashlib, json

KINDS = [("UN member", "un_member"), ("UN observer", "observer"), ("other separately administered region (dependent territory)", "dependency"),
         ("other separately administered region", "region")]


def kind_of(t):
    for prefix, k in KINDS:
        if t.startswith(prefix):
            return k
    raise SystemExit("R54 type not known: " + t)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ne", required=True)
    ap.add_argument("--r54", required=True)
    ap.add_argument("--rules", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    raw = open(a.ne, "rb").read()
    fs = json.loads(raw.decode("utf-8"))["features"]
    r54raw = open(a.r54, "rb").read()
    r54 = list(csv.DictReader(r54raw.decode("utf-8").splitlines()))
    rules = json.load(open(a.rules, encoding="utf-8"))
    defacto = rules["defacto_in_host"]
    merged = {r["iso3"]: r["entity_id"] for r in r54 if r["type"].startswith("merged")}
    listed = [r for r in r54 if not r["type"].startswith("merged") and r["entity_id"] not in defacto]
    keys = {r["entity_id"] for r in listed}
    props = {}
    feature_entity = {}
    for f in fs:
        p = f["properties"]
        a3 = p["ADM0_A3"]
        code = rules["ne_codes"].get(a3, a3)
        if a3 in rules["unadministered"]:
            continue
        if code in keys:
            feature_entity[a3] = code
            props[code] = p
        elif code in defacto:
            feature_entity[a3] = defacto[code]
        elif code in merged or p["ISO_A3"] in merged:
            feature_entity[a3] = merged.get(code, merged.get(p["ISO_A3"]))
        elif a3 in rules["leftover"]:
            feature_entity[a3] = rules["leftover"][a3]
        else:
            raise SystemExit("NE feature with no rule: %s %s" % (a3, p["NAME_EN"]))
    missing = sorted(keys - set(props))
    if missing:
        raise SystemExit("R54 entities with no NE feature: %s" % missing)
    rows = []
    for r in sorted(listed, key=lambda r: r["entity_id"]):
        k = r["entity_id"]
        p = props[k]
        rows.append({"key": k, "ne_a3": p["ADM0_A3"], "iso_a3": r["iso3"].split(" ")[0], "name_en": r["name"], "kind": kind_of(r["type"]),
                     "r54_type": r["type"], "administered_by": r["administered_by"], "macro": rules["macro_names"].get(r["macro"], r["macro"]),
                     "label": [p["LABEL_X"], p["LABEL_Y"]], "defacto_inside": sorted(d for d, h in defacto.items() if h == k)})
    members = {r["key"]: [r["iso_a3"]] + sorted(i for i, h in merged.items() if h == r["key"]) + rules["wdi_extra"].get(r["key"], []) for r in rows}
    out = {"rule": rules["rule"], "provisional": False,
           "source": {"ne": {"file": a.ne.split("/")[-1], "sha256": hashlib.sha256(raw).hexdigest()},
                      "r54": {"file": "src/R54_entities.csv", "sha256": hashlib.sha256(r54raw).hexdigest()}},
           "entities": rows, "feature_entity": dict(sorted(feature_entity.items())), "data_codes": members,
           "defacto_in_host": defacto, "unadministered": rules["unadministered"],
           "counts": {"entities": len(rows), **{k: sum(r["kind"] == k for r in rows) for _, k in KINDS}}}
    json.dump(out, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1, sort_keys=True)
    open(a.out, "a").write("\n")
    print("ENTITIES %s" % out["counts"])


if __name__ == "__main__":
    main()
