"""Render a modern-mode chronicle (JSONL from modern_chronicle.gd, or the "chronicle" block of a saved world) as a time-ordered text
for the owner's reading (BLUEPRINT L4). Facts only; each row's "why" is the reason code the actor or the field gave.

    python -I tools/modern/chronicle.py <chronicle.jsonl | world.json> [--place JPN] [--kind decision,lever_set,...]
"""
import json
import sys


def load(path):
    text = open(path, encoding="utf-8").read()
    if path.endswith(".jsonl"):
        return [json.loads(line) for line in text.splitlines() if line.strip()]
    doc = json.loads(text)
    return doc.get("chronicle", {}).get("rows", [])


def fmt_facts(f):
    parts = []
    for k, v in f.items():
        if isinstance(v, float):
            parts.append("%s=%.4g" % (k, v))
        elif isinstance(v, (list, dict)):
            parts.append("%s=%s" % (k, json.dumps(v, ensure_ascii=False)))
        else:
            parts.append("%s=%s" % (k, v))
    return ", ".join(parts)


def main(argv):
    sys.stdout.reconfigure(encoding="utf-8")
    if len(argv) < 2:
        print(__doc__)
        return 1
    rows = load(argv[1])
    place = None
    kinds = None
    i = 2
    while i < len(argv):
        if argv[i] == "--place":
            place = argv[i + 1]
            i += 2
        elif argv[i] == "--kind":
            kinds = set(argv[i + 1].split(","))
            i += 2
        else:
            i += 1
    rows = sorted(rows, key=lambda r: (r["day"], r["kind"], r["place"]))
    n = 0
    for r in rows:
        if place and r["place"] != place:
            continue
        if kinds and r["kind"] not in kinds:
            continue
        why = (" -- " + r["why"]) if r.get("why") else ""
        print("%s  [%s] %s (%s): %s%s" % (r["date"], r["kind"], r["place"], r["who"], fmt_facts(r.get("facts", {})), why))
        n += 1
    print("%d rows" % n)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
