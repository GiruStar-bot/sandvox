"""data/modern/SOURCES_D477.csv's inventory part (V123 LA-0; the PM, TO_E 20:45 items 3 and 5): one row per sourced block of every
numeric input leaf under data/modern (JSON; checks/ and MANIFEST.json are not inputs), with the block's own or nearest ancestor's source
text, label, the publication date read from that text, and for declared (T) or derived (D) blocks the commit that last set the block's
first line (git blame). The purge rows already in the file (those not marked "inventory") are kept as they are, first.
  python3 -I tools/modern/sources_inventory.py            (from the repository root; rewrites data/modern/SOURCES_D477.csv)
A block is a dict carrying a source-like key (source, sources, *_source, basis, vintage); its leaves are the numbers under it that no
deeper block claims. A file with no source-like key anywhere is one row, sourced from its MANIFEST entry where it has one.
Dates: "published YYYY-MM-DD" (or -MM) in the text wins; else the latest full or year-month date in the text; else a year alone
(publication date CHECK, R96e); else UNDATED (R96e). A date after 2024-12-31 marks the row LA? for verifyくん. R96e's and R96i's
researched dates (data/modern/src) replace the undated, year-only and declared rows' dates, and R96i's also the text-read ones."""
import csv, json, os, re, subprocess, sys

ROOT = os.getcwd()
DM = os.path.join(ROOT, "data/modern")
SRC_KEYS = ("source", "sources", "basis", "vintage")
OUT = os.path.join(DM, "SOURCES_D477.csv")
CUT = "2024-12-31"


# Why a hand parser and not json.load: the block's first line is needed for git blame, and the standard parser keeps no positions
class P:
    def __init__(self, t):
        self.t, self.i, self.line = t, 0, 1

    def ws(self):
        while self.i < len(self.t) and self.t[self.i] in " \t\r\n":
            if self.t[self.i] == "\n":
                self.line += 1
            self.i += 1

    def val(self):
        self.ws()
        c = self.t[self.i]
        ln = self.line
        if c == "{":
            self.i += 1
            out = {}
            self.ws()
            if self.t[self.i] == "}":
                self.i += 1
                return ("o", out, ln, self.line)
            while True:
                self.ws()
                k = self.str()
                self.ws()
                self.i += 1
                out[k] = self.val()
                self.ws()
                if self.t[self.i] == ",":
                    self.i += 1
                    continue
                self.i += 1
                return ("o", out, ln, self.line)
        if c == "[":
            self.i += 1
            out = []
            self.ws()
            if self.t[self.i] == "]":
                self.i += 1
                return ("a", out, ln)
            while True:
                out.append(self.val())
                self.ws()
                if self.t[self.i] == ",":
                    self.i += 1
                    continue
                self.i += 1
                return ("a", out, ln)
        if c == '"':
            return ("s", self.str(), ln)
        m = re.compile(r"-?\d+(\.\d+)?([eE][-+]?\d+)?|true|false|null").match(self.t, self.i)
        self.i = m.end()
        s = m.group(0)
        return ("n", s, ln) if s[0] in "-0123456789" else ("k", s, ln)

    def str(self):
        j = self.i + 1
        while True:
            if self.t[j] == "\\":
                j += 2
                continue
            if self.t[j] == '"':
                break
            j += 1
        s = json.loads(self.t[self.i:j + 1])
        self.i = j + 1
        return s


def src_text(node):
    parts = []
    for k, v in node.items():
        if (k in SRC_KEYS or k.endswith("_source")) and v[0] == "s":
            parts.append("%s: %s" % (k, v[1]))
    return " | ".join(parts)


def label_of(node):
    v = node.get("label")
    return v[1] if v and v[0] == "s" else ""


def count(v, stop_at_blocks=True):
    if v[0] == "n":
        return 1
    if v[0] == "o":
        if stop_at_blocks and src_text(v[1]):
            return 0
        return sum(count(x) for x in v[1].values())
    if v[0] == "a":
        return sum(count(x) for x in v[1])
    return 0


def blocks(v, path, inherited, out):
    if v[0] == "o":
        own = src_text(v[1])
        if own:
            n = sum(count(x) for k, x in v[1].items())
            out.append((path or "(root)", n, own, label_of(v[1]), (v[2], v[3]), False))
            for k, x in v[1].items():
                blocks(x, path + "." + k, (path or "(root)", own, label_of(v[1])), out)
            return
        direct = sum(1 for x in v[1].values() if x[0] == "n") + sum(count(x) for x in v[1].values() if x[0] == "a")
        if direct and inherited is None:
            out.append((path or "(root)", direct, "", label_of(v[1]), (v[2], v[3]), False))
        elif direct:
            out.append((path or "(root)", direct, "inherited from %s: %s" % (inherited[0], inherited[1]), label_of(v[1]) or inherited[2], (v[2], v[3]), True))
        for k, x in v[1].items():
            if x[0] in "o":
                blocks(x, path + "." + k, inherited, out)
    elif v[0] == "a":
        for i, x in enumerate(v[1]):
            if x[0] == "o":
                blocks(x, path + "[%d]" % i, inherited, out)


DATE = re.compile(r"(?<!\d)(19|20)\d\d-(0[1-9]|1[0-2])(-(0[1-9]|[12]\d|3[01]))?(?!\d)")
PUB = re.compile(r"(published|公表|公開|released?)[^0-9]{0,12}((19|20)\d\d-(0[1-9]|1[0-2])(-\d\d)?)", re.I)
YEAR = re.compile(r"(?<![\d.])((19|20)\d\d)(?![\d.])")


REVIEWED = [
    ("2032F = CHECK only", "a 2032 forecast named inside the 2024 report; the input is the report's in-window figure"),
    ("2025年度PB黒字化目標", "a fiscal-year target set by the Cabinet before 2025, not a 2025 publication"),
    ("is look-ahead", "the text names the look-ahead edition it replaced"),
    ("the level held from 2025-01", "the date the held level applies from; the source is 2024-12-30"),
    ("survey dates 2024-01-09..2024-12-23", "weekly values each published in window; the 2025-01-22 date is the file copy used (CHECK, as in R96c)"),
]


def published(text):
    m = PUB.findall(text)
    if m:
        d = max(x[1] for x in m)
        return d, "published (from text)"
    ds = [x.group(0) for x in DATE.finditer(text)]
    if ds:
        return max(ds), "latest date in text (publication CHECK)"
    ys = [y[0] for y in YEAR.findall(text)]
    if ys:
        return max(ys), "year only (publication date CHECK, R96e)"
    return "", "UNDATED (R96e)"


def blame(rel):
    r = subprocess.run(["git", "blame", "--line-porcelain", "HEAD", "--", rel], capture_output=True, text=True, cwd=ROOT)
    lines, cur, times = {}, None, {}
    for ln in r.stdout.splitlines():
        m = re.match(r"^([0-9a-f]{40}) \d+ (\d+)", ln)
        if m:
            cur = (m.group(1)[:8], int(m.group(2)))
            lines[cur[1]] = cur[0]
        elif ln.startswith("committer-time ") and cur:
            times[cur[0]] = int(ln.split()[1])
    return lines, times


def newest(bl, span):
    lines, times = bl
    cs = {lines[i] for i in range(span[0], span[1] + 1) if i in lines}
    return max(cs, key=lambda c: times.get(c, 0)) if cs else "?"


R96E = os.path.join(DM, "src/R96e_compute_chain_and_dates.csv")
R96I = os.path.join(DM, "src/R96i_checks_dated.csv")


def r96e_dates():
    """R96e (research-notes 6fdbf51b) dated the inventory's undated and year-only rows, R96i (research-notes e7b5c51c) the CHECK rows
    R96f named, R96i's row winning where both date one: (file, path) -> (published, verdict, source, report)"""
    out = {}
    for path, rep in ((R96E, "R96e"), (R96I, "R96i")):
        if not os.path.exists(path):
            continue
        for r in csv.DictReader(open(path, encoding="utf-8")):
            if r.get("part", "").startswith("1") or r["verdict"] not in ("OK", "DECLARED"):
                continue
            f = r["file"] if r["file"].startswith("data/modern/") else "data/modern/" + r["file"]
            out[(f, r["path"])] = (r["published"], r["verdict"], r["source"], rep)
    return out


def main():
    dates = r96e_dates()
    keep = []
    if os.path.exists(OUT):
        keep = [r for r in csv.DictReader(open(OUT, encoding="utf-8")) if not r["action"].startswith("inventory")]
    purge_paths = {(r["file"], r["path"]) for r in keep}
    manifest = json.load(open(os.path.join(DM, "MANIFEST.json"), encoding="utf-8"))["files"]
    rows = []
    for dp, dn, fn in os.walk(DM):
        for f in sorted(fn):
            rel = os.path.relpath(os.path.join(dp, f), ROOT)
            relm = os.path.relpath(os.path.join(dp, f), DM)
            if not f.endswith(".json") or relm == "MANIFEST.json" or relm.startswith("checks"):
                continue
            t = open(os.path.join(dp, f), encoding="utf-8").read()
            tree = P(t).val()
            out = []
            blocks(tree, "", None, out)
            if not out:
                continue
            if not any(o[2] for o in out):
                out = [("(whole file)", sum(o[1] for o in out), "", "", (1, t.count("\n") + 1), False)]
            bl = blame(rel)
            for path, n, text, label, line, inh in out:
                if n == 0:
                    continue
                if not text and relm in manifest:
                    m = manifest[relm]
                    text = "MANIFEST: from %s; tool %s; label %s" % (m.get("from", "?"), m.get("tool", "?"), m.get("label", "?"))
                pub, how = published(text)
                act = "inventory: " + how
                if pub and pub[:10] > CUT and len(pub) >= 4 and pub[:4] > CUT[:4]:
                    act = "inventory: LA? (the text names %s)" % pub
                    for pat, why in REVIEWED:
                        if pat in text:
                            act = "inventory: reviewed, in window (%s)" % why
                            pub, _ = published(re.sub(r"(19|20)\d\d(-\d\d){0,2}", lambda m: m.group(0) if m.group(0)[:4] <= "2024" else "", text))
                            break
                lab = label.split()[0].strip("(") if label else ""
                if lab[:1] == "T" or label.upper().startswith(("THEORY", "DECLARED")):
                    act = "inventory: basis declared (T), no data; set in %s" % newest(bl, line) + ("" if "UNDATED" in act else " (the text's date: %s)" % (pub or "-"))
                elif lab[:1] == "D" or label.upper().startswith("DERIVED"):
                    act += "; basis: derived (D) from the sources in this row; set in %s" % newest(bl, line)
                rd = dates.get(("data/modern/" + relm, path))
                if rd and ("UNDATED" in act or "year only" in act or "declared (T)" in act or (rd[3] == "R96i" and "publication CHECK" in act)):
                    pub = rd[0]
                    act = "inventory: dated by %s (%s): %s" % (rd[3], rd[1], rd[2][:160]) + (act[act.index(";"):] if ";" in act else "")
                if ("data/modern/" + relm, path) in purge_paths:
                    act += "; replaced in the purge (see its row)"
                rows.append({"file": "data/modern/" + relm, "path": path, "value": "%d numeric leaves" % n, "unit": "",
                             "label": label, "source": text[:400], "published": pub, "verdict_before": "", "action": act})
    with open(OUT, "w", encoding="utf-8", newline="") as fo:
        w = csv.DictWriter(fo, fieldnames=["file", "path", "value", "unit", "label", "source", "published", "verdict_before", "action"], lineterminator="\n")
        w.writeheader()
        w.writerows(keep + rows)
    tally = {}
    for r in rows:
        k = r["action"].split(";")[0]
        if k.startswith("inventory: dated by R96"):
            k = k[:k.index(")") + 1]
        elif k.startswith("inventory: reviewed"):
            k = "inventory: reviewed, in window"
        tally[k] = tally.get(k, 0) + 1
    print("purge rows %d, inventory rows %d, numeric leaves %d" % (len(keep), len(rows), sum(int(r["value"].split()[0]) for r in rows)))
    for k in sorted(tally):
        print("  %5d %s" % (tally[k], k))


if __name__ == "__main__":
    main()
