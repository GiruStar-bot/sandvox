"""A view spec for the modern mode's view layer (MODERN_PLAN 4): per field entity, how one state's view shows it.
  python3 -I tools/modern/build_view.py --rules tools/modern/view_jpn_rules.json --ne <ne_10m_admin_0_countries.geojson> \
      --entities data/modern/entities.json --r54 data/modern/src/R54_japan_view.csv --out data/modern/views/jpn.json
Kinds: state, self, region, not_recognised, not_listed, territory (of its administering state), unknown (not in the view at all).
A view from R54's table ("source": "r54") takes its statuses and names from there (the rules file says how); the test fixture
("source": "fixture") makes every UN member and states_extra a state, regions as listed, dependent territories territory, English names.
Aliases (for reading what a seat writes, never shown) are NE's names in other languages and the table's other forms."""
import argparse, csv, hashlib, json, re

ALIAS_FIELDS = ["NAME_EN", "NAME_ZH", "NAME_ZHT", "NAME_KO", "NAME_RU", "NAME_JA", "NAME_FR", "NAME_ES", "NAME_AR"]
KINDS = ["state", "self", "region", "not_recognised", "not_listed", "territory", "unknown"]


def host_of(e):
    m = re.search(r"dependency of ([A-Z]{3})", e["administered_by"])
    return m.group(1) if m else None


def from_r54(rules, ent, rows54):
    by_name = {e["name_en"]: e["key"] for e in ent["entities"]}
    by_name.update(rules["r54_names"])
    out, notes = {}, []
    for r in rows54:
        k = by_name.get(r["entity_en"])
        st = r["japan_status"]
        ja = r["mofa_ja"]
        if k is None:
            notes.append({"row": r["entity_en"], "status": st, "mofa_ja": ja, "source": r["source_file_line"]})
            continue
        al = [x.strip() for x in r["aliases_ja"].replace("；", ";").split(";") if x.strip()]
        if st.startswith("self"):
            name, other = al[0], [ja.split(" (")[0]]
            al = al[1:]
            kind = "self"
        elif st.startswith("not recognised / not listed"):
            m = re.search(r"MOFA text name: ([^)]+)\)", ja)
            name, other, kind = m.group(1).split(" / ")[0], [], "not_listed"
        else:
            parts = [x.strip() for x in ja.split("|")]
            name = parts[1][len("short: "):] if len(parts) > 1 else parts[0]
            other = [parts[0]] if len(parts) > 1 else []
            kind = "state" if st == "recognised state" else ("region" if st.startswith("region") else "not_recognised")
        out[k] = {"kind": kind, "name": name, "aliases_view": sorted(set(other + [re.sub(r" \(.*\)$", "", x) for x in al]) - {name}),
                  "status_text": st, "region_group": r["mofa_region"], "source": r["source_file_line"]}
    for e in ent["entities"]:
        if e["kind"] == "dependency":
            out[e["key"]] = {"kind": "territory", "of": host_of(e), "name": rules["territories"][e["key"]], "aliases_view": [],
                             "status_text": "territory of its administering state", "source": rules["territory_sources"][e["key"]]}
    return out, notes


def from_fixture(rules, ent):
    out = {}
    for e in ent["entities"]:
        k = e["key"]
        if k in rules["regions"]:
            kind = "region"
        elif e["kind"] == "dependency":
            kind = "territory"
        elif e["kind"] == "un_member" or k in rules["states_extra"]:
            kind = "state"
        else:
            kind = "unknown"
        row = {"kind": kind, "name": e["name_en"], "aliases_view": [], "source": "fixture"}
        if kind == "territory":
            row["of"] = host_of(e)
        out[k] = row
    return out, []


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rules", required=True)
    ap.add_argument("--ne", required=True)
    ap.add_argument("--entities", required=True)
    ap.add_argument("--r54")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    rules = json.load(open(a.rules, encoding="utf-8"))
    ent = json.load(open(a.entities, encoding="utf-8"))
    raw = open(a.ne, "rb").read()
    props = {f["properties"]["ADM0_A3"]: f["properties"] for f in json.loads(raw.decode("utf-8"))["features"]}
    src = {"ne_sha256": hashlib.sha256(raw).hexdigest()}
    if rules["source"] == "r54":
        raw54 = open(a.r54, "rb").read()
        rows, notes = from_r54(rules, ent, list(csv.DictReader(raw54.decode("utf-8").splitlines())))
        src["r54_sha256"] = hashlib.sha256(raw54).hexdigest()
    else:
        rows, notes = from_fixture(rules, ent)
    for e in ent["entities"]:
        k = e["key"]
        row = rows.setdefault(k, {"kind": "unknown", "name": e["name_en"], "aliases_view": [], "source": "not in the view"})
        p = props[e["ne_a3"]]
        row["aliases"] = sorted(({p[f] for f in ALIAS_FIELDS if p.get(f)} | {e["name_en"]} | set(row.pop("aliases_view"))) - {row["name"]})
    out = {"view": rules["view"], "holder": rules["holder"], "language": rules["language"], "provisional": rules["provisional"],
           "rule": rules["rule"], "entities": dict(sorted(rows.items())), "claims": rules["claims"], "sea_names": rules.get("sea_names", {}),
           "not_entities": notes, "sources": src, "counts": {k: sum(r["kind"] == k for r in rows.values()) for k in KINDS}}
    json.dump(out, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1, sort_keys=True)
    open(a.out, "a").write("\n")
    print("VIEW %s %s, %d rows that are no field entity" % (rules["view"], out["counts"], len(notes)))


if __name__ == "__main__":
    main()
