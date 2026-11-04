"""Write a modern data file's floats at their canonical value (sim/modern/canon.gd canon_f: nine decimals by floor(x * 1e9 + 0.5) / 1e9),
so that a parser one ulp off on another build cannot flip a number that sat on the nine-decimal tie (V089: 276 such numbers in
regions.json, written by Godot's JSON.stringify with ten decimals ending in 5). The canonical value is computed from Python's parse, which
equals Godot's on Linux for these files (V084, V089), so the values the Linux runs read do not change.
  python3 -I tools/modern/canon_json_file.py data/modern/regions.json
Writes the file in place in the dump's form (compact, keys sorted) and prints how many floats changed their written form."""
import json, math, sys


def canon_f(x):
    if not math.isfinite(x) or float(x).is_integer() or abs(x) >= 1e7:
        return x
    return math.floor(x * 1e9 + 0.5) / 1e9


def walk(v, n):
    if isinstance(v, float):
        c = canon_f(v)
        if repr(c) != repr(v):
            n[0] += 1
        return c
    if isinstance(v, list):
        return [walk(x, n) for x in v]
    if isinstance(v, dict):
        return {k: walk(x, n) for k, x in v.items()}
    return v


def main():
    path = sys.argv[1]
    d = json.load(open(path, encoding="utf-8"))
    n = [0]
    out = walk(d, n)
    open(path, "w", encoding="utf-8").write(json.dumps(out, separators=(",", ":"), sort_keys=True, ensure_ascii=False))
    print("CANON %s: %d floats written at their canonical value" % (path, n[0]))


if __name__ == "__main__":
    main()
