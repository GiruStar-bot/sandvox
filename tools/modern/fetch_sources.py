"""Fetch the modern mode's source files into a folder of their own (downloads are untrusted data: keep them outside the repository).
  python3 -I tools/modern/fetch_sources.py --sources tools/modern/sources.json --dir <download folder>
Writes <dir>/fetch_log.json: each file's url, bytes, sha256 and UTC time; a file that fails is logged with its error and not retried."""
import argparse, datetime, hashlib, json, os, urllib.request


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sources", required=True)
    ap.add_argument("--dir", required=True)
    a = ap.parse_args()
    src = json.load(open(a.sources, encoding="utf-8"))
    os.makedirs(a.dir, exist_ok=True)
    log = []
    for f in src["files"]:
        path = os.path.join(a.dir, f["name"])
        row = {"name": f["name"], "url": f["url"]}
        try:
            with urllib.request.urlopen(f["url"], timeout=300) as r:
                data = r.read()
            open(path, "wb").write(data)
            row.update({"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()})
        except Exception as e:
            row["error"] = type(e).__name__
        row["utc"] = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        log.append(row)
        print("FETCH", f["name"], row.get("bytes", row.get("error")))
    json.dump(log, open(os.path.join(a.dir, "fetch_log.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
