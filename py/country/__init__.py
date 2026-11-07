# The country frame (FRAME_PLAN §1): a country is its manifest, data/modern/<id>/country.json, naming each input file by its role,
# its cut-off and its constants; a layer asks the Country for a role and never names a file or a country itself. Why the manifest
# read from the repository and the files through tiers.start.load: step (a)'s rows read the frozen oracle's data (START_DATA_ROOT),
# which predates the manifests
import json
import os
import re

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))


class Country:
    def __init__(self, m):
        self.id = m["id"]
        self.name_en = m["name_en"]
        self.status = m["status"]
        self.cutoff = m.get("cutoff", "")
        self.files = m.get("files", {})
        self.constants = m.get("constants", {})
        self.label = m.get("label", "")

    def path(self, role):
        if role not in self.files:
            raise KeyError("country %s: no file for the role %s" % (self.id, role))
        f = self.files[role]
        refuse_sealed(f, self.id)
        # Why the stub's own files from the repository: they are the frame's, not a country's data, so a run on another data root
        # (step (a)'s, the frozen oracle's) still finds them
        if f.startswith("res://data/modern/stub/"):
            return os.path.join(ROOT, f[len("res://"):])
        return f

    def key(self):
        # the key people.gd and the specs use for the country's files and entity
        return self.id


_cache = {}
_registry = []


def registry():
    # data/modern/countries.json's rows (FRAME_PLAN §6.1), written by tools/py/country_registry.py from entities.json
    if not _registry:
        with open(os.path.join(ROOT, "data", "modern", "countries.json"), encoding="utf-8") as f:
            _registry.extend(json.load(f)["countries"])
    return _registry


def load(cid="JPN"):
    # A filled country's own manifest; a stub's is the shared template with the registry's id and name in it
    if cid not in _cache:
        row = next((r for r in registry() if r["id"] == cid), None)
        if row is None:
            raise KeyError("country %s is not in data/modern/countries.json" % cid)
        with open(os.path.join(ROOT, row["manifest"]), encoding="utf-8") as f:
            m = json.load(f)
        if row["status"] == "stub":
            m["id"] = row["id"]
            m["name_en"] = row["name_en"]
        c = Country(m)
        for f in c.files.values():
            refuse_sealed(f, c.id)
        late, undated = seal_check(c, sources_of(c))
        if late or undated:
            bad = late[0] if late else undated[0]
            raise ValueError("country %s: %d late and %d unexcused undated SOURCES rows of its files (cut-off %s), e.g. %s %s" % (
                c.id, len(late), len(undated), c.cutoff, bad.get("file", ""), bad.get("path", "")))
        _cache[cid] = c
    return _cache[cid]


def _resolved(f):
    rel = f[len("res://"):] if f.startswith("res://") else f
    return os.path.realpath(os.path.join(ROOT, rel))


def refuse_sealed(f, cid):
    # FRAME_PLAN §2: a manifest names only inputs inside data/, never a sealed or check-only file. The path is resolved first (dot
    # segments, doubled slashes, links) and compared case-folded. Why resolve and not match the text: V019b served checks.json through
    # ./, ../, // and stub/../ spellings of the same file, and a case-insensitive file system (Windows) would serve CHECKS.json
    a = _resolved(f)
    data = os.path.realpath(os.path.join(ROOT, "data"))
    if os.path.commonpath([a, data]) != data:
        raise ValueError("country %s: the file %s resolves outside data/ (%s)" % (cid, f, a))
    rel = os.path.relpath(a, data).replace(os.sep, "/").lower()
    parts = rel.split("/")
    if rel == "modern/checks.json" or rel.startswith("modern/checks/") or "sealed" in parts:
        raise ValueError("country %s: the file %s is sealed or check-only and may not be read as an input" % (cid, f))


def sources_of(c):
    # The SOURCES_D477 rows of the files c's manifest names
    import csv
    names = set()
    for f in c.files.values():
        names.add(f[len("res://"):] if f.startswith("res://") else os.path.relpath(f, ROOT).replace(os.sep, "/"))
    with open(os.path.join(ROOT, "data", "modern", "SOURCES_D477.csv"), encoding="utf-8") as fh:
        return [r for r in csv.DictReader(fh) if r.get("file", "") in names]


def first_date(text):
    # The edition a SOURCES row used: the first ISO date (YYYY-MM or YYYY-MM-DD, 18xx-20xx) or standalone year (YYYY) in its published text
    m = re.search(r"((?:18|19|20)\d\d)-(\d\d)(?:-(\d\d))?", text)
    if m is not None:
        return "%s-%s-%s" % (m.group(1), m.group(2), m.group(3) or "01")
    m_y = re.search(r"\b((?:18|19|20)\d\d)\b", text)
    return None if m_y is None else "%s-12-31" % m_y.group(1)


def is_declared_or_derived(r):
    lbl = r.get("label", "").strip()
    act = r.get("action", "").strip()
    if "(DECLARED)" in act or "THEORY" in lbl.upper() or "DECLARED" in lbl.upper():
        return True
    if lbl.startswith("T") or lbl.startswith("D") or "D from" in lbl or "§12.5 F6" in lbl:
        return True
    return False


def seal_check(c, rows):
    # F-seal (FRAME_PLAN §2): the rows whose edition is after the country's cut-off and not labelled CHECK, and the unexcused undated rows
    late, undated = [], []
    for r in rows:
        d = first_date(r.get("published", ""))
        if d is None and not is_declared_or_derived(r):
            d = first_date(r.get("source", ""))
        if d is None:
            if not is_declared_or_derived(r):
                undated.append(r)
        elif d > c.cutoff and "CHECK" not in (r.get("label", "") + r.get("action", "")).upper():
            late.append(r)
    return late, undated
