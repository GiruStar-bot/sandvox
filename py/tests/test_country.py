# The country frame's light rows (FRAME_PLAN §4, §6.4): F-reg, and a stub's manifest
#   python py/tests/test_country.py
# F-reg: the registry has one row per entity of data/modern/entities.json (215), ids unique and equal to the entities' keys, Japan
# the only "filled"; every stub's manifest carries the UNSOURCED label and a placeholder population
# F-stub: every one of the 214 stubs builds its persons' start on its one region and steps one month under its ruler's seat (a
# scripted tax rise) with no error; its non-finite values are listed. Nothing else is claimed for a stub
# F-seat: a seat for Japan and for one stub of each kind (UN member, observer, dependency, region) observes with a header naming the
# country (a stub's with the UNSOURCED label, Japan's without), and the scripted lever reaches the month's env
# F-seal: no SOURCES_D477 row's edition is after Japan's cut-off unless it is CHECK ONLY; the undated rows are reported. Must-fail: one
# row moved to 2025-01-02 is caught
# F-load: Japan's start and persons read their files only through the manifest: every file the loader reads is a manifest file
# F-0w: Japan's sample persons (seed 1, n_per 20) step their month 1 equal to the oracle's with all 214 stubs stepped beside them
# F-iso: must-fail: a stub that writes one of Japan's values makes F-0w's month differ
# F-lit: a country literal ("JPN", a "_2024.json" file name, a "%02d" region format) appears in py/ outside py/country only in the files
# FRAME_PLAN §8 lists as not yet moved (the world, econ, py/lchh, rule (D), the tiers start's region codes); a literal in any other file
# fails. Must-fail: the same scan over a line with "JPN" in a file off the list is caught
# F-mf: Japan's manifest with pension_age 66 in place of 65 makes the tiers start differ from the oracle at 06_class (the pension law
# reads it), so the frame carries the value it claims to carry (AMENDED: the persons' sample does not read it, people.gd reads it with
# tiers on only; that is reported)
import csv
import re
import json
import math
import os

from common import Kit, ROOT
import country  # noqa: E402  (after common, which puts py/ on the path)


def main():
    k = Kit("py/tests/test_country.py")
    reg = country.registry()
    with open(os.path.join(ROOT, "data", "modern", "entities.json"), encoding="utf-8") as f:
        keys = sorted(e["key"] for e in json.load(f)["entities"])
    ids = [r["id"] for r in reg]
    k.check(len(reg) == 215 and sorted(ids) == keys and len(set(ids)) == len(ids),
            "F-reg %d rows, one per entities.json entity, ids unique" % len(reg))
    filled = [r["id"] for r in reg if r["status"] == "filled"]
    k.check(filled == ["JPN"], "F-reg Japan is the only filled country: %s" % filled)
    stubs = [country.load(r["id"]) for r in reg if r["status"] == "stub"]
    bad = [c.id for c in stubs if not c.label.startswith("UNSOURCED") or "population_placeholder" not in c.constants]
    k.check(len(stubs) == 214 and not bad, "F-reg the 214 stubs carry the UNSOURCED label and a placeholder population%s" % (
        (": " + " ".join(bad[:10])) if bad else ""))
    j = country.load("JPN")
    k.check(j.status == "filled" and j.cutoff == "2024-12-31" and j.path("people_spec").endswith("jpn_people_2024.json"),
            "F-reg Japan's manifest names today's files and the cut-off 2024-12-31")
    env = {"inflation_month": 0.02 / 12.0, "food_price_yoy": 0.0, "unemployment_rate": 0.025, "wage_index": 1.0}
    errors, nonfinite = [], {}
    seats = {}
    for r in reg:
        try:
            c = country.load(r["id"])
            seat = seat_of(c)
            seat.month(dict(env, cohort=seat.persons.p.cohort))
            seats[r["id"]] = seat
            p = seat.persons.p
            for row in p.fields():
                v = getattr(p, str(row[0]))
                if row[1] == "f64":
                    nf = sum(1 for x in v if not math.isfinite(x))
                    if nf:
                        nonfinite[(r["id"], str(row[0]))] = nf
        except Exception as ex:
            errors.append("%s: %s" % (r["id"], repr(ex)[:80]))
    k.check(not errors, "F-stub all %d countries (214 stubs and Japan's sample) built and stepped one month under a seat with no error%s" % (
        len(reg), (": " + "; ".join(errors[:5])) if errors else ""))
    print("info F-stub non-finite persons values: %d (country, field) pairs%s" % (len(nonfinite), (", e.g. %s" % list(nonfinite.items())[:3]) if nonfinite else ""))
    kinds = {}
    for r in reg:
        kinds.setdefault(r["kind"], r["id"])
    picks = ["JPN"] + [kinds[kd] for kd in ("un_member", "observer", "dependency", "region") if kd in kinds and kinds[kd] != "JPN"]
    names = {r["id"]: r["name_en"] for r in reg}
    bad = []
    for cid in picks:
        s2 = seats[cid]
        obs = s2.observe()
        head = s2.text_of(obs).split("\n")[0]
        stub = s2.c.status == "stub"
        got_env = s2.persons.env_seen.get(1, {})
        ok = (bool(s2.c.name_en) and s2.c.name_en == names[cid] and s2.c.name_en in head and cid in head
              and ("UNSOURCED" in head) == stub and obs["status"] == ("stub" if stub else "filled")
              and (obs["label"].startswith("UNSOURCED") if stub else obs["label"] == "")
              and list(got_env.get("levers", [])) == ["consumption_tax_rate"])
        try:
            s2.act(["not_a_lever"])
            ok = False
        except ValueError:
            pass
        if not ok:
            bad.append(cid)
    k.check(not bad, "F-seat seats for %s: each country's name (the registry's, non-empty) and id head its observation, the status and label "
            "are the country's, the scripted lever is in the env the persons received, an unknown lever is refused%s" % (
                " ".join(picks), (": failing " + " ".join(bad)) if bad else ""))
    pops = {cid: st.observe()["population"] for cid, st in seats.items()}
    want_stub = float(country.load("AFG").constants["population_placeholder"])
    off_stub = [cid for cid, st in seats.items() if st.c.status == "stub" and pops[cid] != want_stub]
    jp = seats["JPN"].persons.p
    want_j = 0.0
    for code in sorted(jp.pref_pop):
        want_j += float(jp.pref_pop[code])
    k.check(not off_stub and pops["JPN"] == want_j and want_j > 1e8, "F-pop every stub observes its placeholder population %.0f (UNSOURCED); "
            "Japan observes the sum of its prefectures, %.0f%s" % (want_stub, want_j, (": off " + " ".join(off_stub[:8])) if off_stub else ""))
    with open(os.path.join(ROOT, "data", "modern", "SOURCES_D477.csv"), encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    late, undated = country.seal_check(j, rows)
    moved = [dict(r) for r in rows]
    moved[0]["published"] = "2025-01-02"
    late2, _ = country.seal_check(j, moved)
    undated_probe = [dict(rows[0], published="", source="", label="S", action="")]
    _, undated2 = country.seal_check(j, undated_probe)
    laws_fy24 = json.load(open(os.path.join(ROOT, "data", "modern", "polity", "jpn_laws.json"), encoding="utf-8"))["laws"]["budget_fy2024"]["lines_bn_jpy"]
    fy24_sum = sum(float(v) for k_l, v in laws_fy24.items() if k_l != "total")
    fy24_ok = abs(fy24_sum - float(laws_fy24["total"])) < 1e-6
    k.check(not late and not undated and len(late2) == 1 and len(undated2) == 1 and fy24_ok,
            "F-seal %d SOURCES rows, none after the cut-off 2024-12-31 (CHECK ONLY excepted) and 0 unexcused undated rows; "
            "a row moved to 2025-01-02 (%d) or stripped of its date (%d) is caught; budget_fy2024 lines sum to %.1f bn JPY" % (
                len(rows), len(late2), len(undated2), fy24_sum))
    print("info F-seal unexcused undated rows (no ISO date and not THEORY/DECLARED): %d of %d" % (len(undated), len(rows)))
    bypass = country.Country(dict(json.load(open(os.path.join(ROOT, "data", "modern", "stub", "country.json"), encoding="utf-8")), id="ZZZ",
                                  name_en="bypass"))
    bypass.files = dict(bypass.files, status="res://data/modern/checks.json")
    refused = []
    variants = ("res://data/modern/checks.json", "res://data/modern/checks/x.json", "res://docs/team/research/reports/sealed/x.csv",
                "res://data/modern/./checks.json", "res://data/modern/../modern/checks.json", "res://data/modern//checks.json",
                "res://data/modern/stub/../checks.json", "res://data/modern/CHECKS.json", "res://data/sealed/x.json",
                "res://../outside.json", os.path.join(ROOT, "data", "modern", "checks.json"))
    for f in variants:
        try:
            country.refuse_sealed(f, "ZZZ")
        except ValueError:
            refused.append(f)
    import shutil
    import tempfile
    link_dir = tempfile.mkdtemp(dir=os.path.join(ROOT, "data", "modern", "stub"))
    try:
        link = os.path.join(link_dir, "regions.json")
        try:
            os.symlink(os.path.join(ROOT, "data", "modern", "checks.json"), link)
        except OSError as ex:
            link = None
            print("info F-seal-l the symlink row was not run: this system refuses os.symlink (%s)" % repr(ex)[:60])
        if link is not None:
            variants = variants + ("res://" + os.path.relpath(link, ROOT).replace(os.sep, "/"),)
            try:
                country.refuse_sealed(variants[-1], "ZZZ")
            except ValueError:
                refused.append(variants[-1])
    finally:
        shutil.rmtree(link_dir)
    try:
        bypass.path("status")
        served = True
    except ValueError:
        served = False
    late_row = dict(country.sources_of(j)[0])
    late_row["published"] = "2025-01-02"
    late3, _ = country.seal_check(j, [late_row])
    real_sources = country.sources_of
    country.sources_of = lambda c: [late_row]
    country._cache.pop("JPN", None)
    try:
        country.load("JPN")
        loaded_late = True
    except ValueError:
        loaded_late = False
    finally:
        country.sources_of = real_sources
        country._cache.pop("JPN", None)
    late3 = late3 if not loaded_late else []
    ok_files = [f for f in country.load("JPN").files.values()] + [f for f in country.load("AFG").files.values()]
    wrongly = []
    for f in ok_files:
        try:
            country.refuse_sealed(f, "JPN")
        except ValueError:
            wrongly.append(f)
    k.check(len(refused) == len(variants) and not served and len(late3) == 1 and not wrongly,
            "F-seal-l the loader refuses a sealed, check-only or outside-data file in every spelling (V019b's ./, ../, //, stub/../, the case, an "
            "absolute path, a symlink in data/modern/stub/ named regions.json pointing at checks.json: %d of %d), accepts Japan's and a stub's own files, and refuses V019's bypass (a stub's "
            "status naming checks.json: %s); a manifest file's SOURCES row dated 2025-01-02 makes Country.load refuse%s" % (len(refused), len(variants), "refused" if not served else "SERVED",
                                                                                ": wrongly refused " + " ".join(wrongly) if wrongly else ""))
    from tiers.start import load as L
    seen = []
    real = L.load_json

    def spy(path):
        seen.append(path)
        return real(path)

    import builtins
    opened = []
    real_open = builtins.open

    def spy_open(f, *a, **kw):
        opened.append(str(f))
        return real_open(f, *a, **kw)

    L.load_json = spy
    builtins.open = spy_open
    try:
        import test_persons_layer as TPL
        TPL.start(1, 20, False)
        from tiers.start import create
        create.inputs()
    finally:
        L.load_json = real
        builtins.open = real_open
    allowed = set(L.ROOT + "/" + f[len("res://"):] for f in j.files.values())
    allowed |= {os.path.join(ROOT, "data", "modern", "countries.json"), os.path.join(ROOT, "data", "modern", "jpn", "country.json"),
                os.path.join(ROOT, "data", "modern", "SOURCES_D477.csv")}
    stray = sorted(set(os.path.abspath(x) for x in opened if "/data/" in x and os.path.abspath(x) not in {os.path.abspath(y) for y in allowed}))
    outside = sorted(set(x for x in seen if x not in set(j.files.values()))) + stray
    k.check(seen and not outside, "F-load Japan's start and persons read %d files through load_json and open %d data files, all the "
            "manifest's (or the registry and SOURCES)%s" % (len(set(seen)), len(set(opened)), (": outside " + " ".join(outside)) if outside else ""))
    base = os.path.join(ROOT, "outputs", "py_oracle", "ps", "s1_n20")
    if os.path.exists(os.path.join(base, "m01.persons.sha.txt")):
        from core import digest
        import test_persons_layer as TPL
        for leak in (False, True):
            ps, env1 = TPL.start(1, 20, False)
            ref0 = digest.read_hashes(os.path.join(base, "m00.persons.sha.txt"))
            TPL.month_hashes(ps, list(ref0))
            for cid, st in seats.items():
                if cid != "JPN":
                    st.month(dict(env, cohort=st.persons.p.cohort))
                    if leak and cid == "AFG":
                        ps.p.price_index = st.persons.p.price_index * 1.0000001
            ps.step(env1)
            ref1 = digest.read_hashes(os.path.join(base, "m01.persons.sha.txt"))
            d1 = TPL.differing(ref1, TPL.month_hashes(ps, list(ref1)))
            if not leak:
                k.check(not d1, "F-0w Japan's sample month 1 equals the oracle's with 214 stubs stepped beside it%s" % (
                    (": differing " + " ".join(d1[:8])) if d1 else ""))
            else:
                k.check(bool(d1), "F-iso a stub writing Japan's price_index makes F-0w's month 1 differ: %s" % " ".join(d1[:8]))
    else:
        k.check(False, "F-0w needs the oracle's sample dump at outputs/py_oracle/ps/s1_n20")
    lit = re.compile(r'"JPN"|_2024\.json|"%02d"')
    allowed = set(NOT_MOVED)
    hits = {}
    for dp, dn, fn in os.walk(os.path.join(ROOT, "py")):
        rel = os.path.relpath(dp, ROOT).replace(os.sep, "/")
        if rel.startswith("py/country") or rel.startswith("py/tests") or "__pycache__" in rel:
            continue
        for f in fn:
            if f.endswith(".py"):
                path = rel + "/" + f
                with open(os.path.join(dp, f), encoding="utf-8") as fh:
                    n = sum(1 for line in fh if lit.search(line))
                if n:
                    hits[path] = n
    outside = sorted(x for x in hits if x not in allowed)
    caught = bool(lit.search('    key = "JPN"')) and "py/people/month.py" not in allowed
    k.check(not outside and caught, "F-lit %d literals in %d files, all in FRAME_PLAN §8's not-yet-moved list%s; a literal in another file is "
            "caught" % (sum(hits.values()), len(hits), (": outside " + " ".join(outside)) if outside else ""))
    from tiers.start import build, create, trace
    from core import digest
    cj = country.load("JPN")
    old = cj.constants["pension_age"]
    try:
        cj.constants["pension_age"] = 66
        p, prefectures = create.inputs()
        ctx = {"prefectures": prefectures}
        build.run(p, ctx, None, "06_class")
        st = os.path.join(ROOT, "outputs", "py_oracle", "st", "06_class.sha.txt")
        ref = digest.read_hashes(st) if os.path.exists(st) else {}
        got = trace.stage_hashes(p, ctx, list(ref))
        d6 = [n for n in sorted(ref) if got[n] != ref[n]]
        first66 = sample_first_diff(base, digest)
        cj.constants["pension_age"] = old
        first65 = sample_first_diff(base, digest)
    finally:
        cj.constants["pension_age"] = old
    k.check(bool(ref) and bool(d6) and first65 is None,
            "F-mf pension_age 66 in Japan's manifest makes the tiers start differ at 06_class (%s); with 65 the sample persons equal the "
            "oracle through month 13" % " ".join(d6[:5]))
    print("info F-mf the sample persons (tiers off) with 66: first differing month %s; people.gd reads PENSION_AGE only with tiers on, "
          "and _year's retirement at 65 is its own literal (loop_c.py, FRAME_PLAN §8's open list)" % (first66[0] if first66 else "none"))
    k.finish()


def sample_first_diff(base, digest):
    # The L run's own steps (state hashes, then supply, each month from 0), so only the manifest's value can part it from the oracle
    import test_persons_layer as TPL
    ps, env1 = TPL.start(1, 20, False)
    for m in range(0, 14):
        if m > 0:
            ps.step(env1)
        ref = digest.read_hashes(os.path.join(base, "m%02d.persons.sha.txt" % m))
        d = TPL.differing(ref, TPL.month_hashes(ps, list(ref)))
        if d:
            return m, d
    return None


NOT_MOVED = ["py/econ/actors.py", "py/econ/month.py", "py/lchh/households.py", "py/tiers/start/a_fit.py", "py/tiers/start/age_d.py",
             "py/tiers/start/create.py", "py/tiers/start/p.py", "py/tiers/start/tconst.py", "py/world/integrated.py", "py/world/world.py"]


def seat_of(c):
    from country.seat import RulerSeat
    from people.layer import Persons
    from tiers.start import create, load
    co, qx = create.status_cohort_qx(c.id, 2024)
    regions = load.load_json(c.path("regions"))["prefectures"]
    n_per = int(c.constants.get("persons_per_region", 2))
    ps = Persons.create(c.id, 1, co, qx, regions, n_per, 2024)
    return RulerSeat(c, ps, script=lambda obs: ["consumption_tax_rate"])


if __name__ == "__main__":
    main()
