# Writes data/modern/countries.json, the country registry (FRAME_PLAN §6.1): one row per entity of data/modern/entities.json, Japan
# "filled" with its own manifest, every other "stub" on the shared template data/modern/stub/country.json. Why generated and not
# typed: the ids and names must be entities.json's exactly, and a rerun after entities.json changes keeps them so
#   python tools/py/country_registry.py
import json
import os

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
FILLED = {"JPN": "data/modern/jpn/country.json"}


def main():
    with open(os.path.join(ROOT, "data", "modern", "entities.json"), encoding="utf-8") as f:
        ents = json.load(f)["entities"]
    rows = []
    for e in sorted(ents, key=lambda x: x["key"]):
        cid = e["key"]
        rows.append({"id": cid, "name_en": e["name_en"], "kind": e["kind"], "macro": e.get("macro", ""),
                     "status": "filled" if cid in FILLED else "stub",
                     "manifest": FILLED.get(cid, "data/modern/stub/country.json")})
    out = {"source": "data/modern/entities.json (the field's entities: ids and names)",
           "note": "FRAME_PLAN §6.1 (D483): every country is a stub except the filled ones; a stub's numbers are placeholders, "
                   "labelled UNSOURCED, and claim nothing about the country",
           "countries": rows}
    with open(os.path.join(ROOT, "data", "modern", "countries.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
        f.write("\n")
    print("countries %d, filled %d" % (len(rows), sum(1 for r in rows if r["status"] == "filled")))


if __name__ == "__main__":
    main()
