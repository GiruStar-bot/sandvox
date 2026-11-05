# REL_PORT_PLAN §4: the relations, groups and actions rows against oracle_dump_rel.gd's cuts
#   python py/tests/run_rel.py <oracle dir> [rows]      rows: a comma list of R0,S0,D-hook,A,B,R,W,RANK,REC,U,K,SR,MF1,MF2,MF3 (default all)
#   REL_MODE=tiers python py/tests/run_rel.py <oracle dir> [rows]: P-a mode (plan section 6), D-hook-t,A,B,R,W,RANK,REC,MF2
#   python py/tests/run_rel_cov.py <oracle dir> runs them all under a line trace for row COV
# Env: REL_SEEDS (1,7,42), REL_MONTHS (36), REL_U_SEED (7)
import json
import math
import os
import re
import shutil
import sys
import tempfile

from common import Kit, ROOT
from people import shim, rel, grp, act
from people.deps import load, read_hashes, enc, _codec

P = shim.P


def first_diff(a, b):
    if isinstance(a, _codec.Packed):
        a = list(a.a)
    if isinstance(b, _codec.Packed):
        b = list(b.a)
    if isinstance(a, dict) and isinstance(b, dict):
        if set(a) != set(b):
            return "keys differ: only python %s, only oracle %s" % (sorted(set(a) - set(b), key=str)[:5], sorted(set(b) - set(a), key=str)[:5])
        for k in sorted(a, key=_codec._sort_key):
            r = first_diff(a[k], b[k])
            if r is not None:
                return "key %r: %s" % (k, r)
        return None
    if isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            return "length %d vs %d" % (len(a), len(b))
        for i in range(len(a)):
            r = first_diff(a[i], b[i])
            if r is not None:
                return "index %d: %s" % (i, r)
        return None
    if type(a) != type(b) or a != b:
        return "%r (%s) vs %r (%s)" % (a, type(a).__name__, b, type(b).__name__)
    return None


def compare(kit, label, mine, want_path, ref_dir=None):
    want = read_hashes(want_path)
    hs = shim.hashes(mine)
    bad = sorted(n for n in set(want) | set(hs) if hs.get(n) != want.get(n))
    extra = ""
    if bad and ref_dir and os.path.isdir(ref_dir):
        ref = load(ref_dir)
        extra = "; " + "; ".join("%s: %s" % (n, first_diff(mine.get(n), ref.get(n))) for n in bad[:4])
    kit.check(not bad, "%s: fields differing %d %s%s" % (label, len(bad), bad[:8], extra))
    return bad


def read_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f, object_hook=_codec._hook(os.path.dirname(path)))


def row_r0(kit):
    # Every keyed or DetMath call of the three modules, through p.u / p.normal (people.gd: KEYED.u / KEYED.normal) or directly
    calls = set()
    for name in ("relations.gd", "groups.gd", "actions.gd"):
        with open(os.path.join(ROOT, "sim/modern/people", name), encoding="utf-8") as f:
            src = f.read()
        calls |= {"KEYED." + m for m in re.findall(r"KEYED\.(\w+)\(", src)}
        calls |= {"DM." + m for m in re.findall(r"\bDM\.(\w+)\(", src)}
        calls |= {"KEYED.u" for _ in re.findall(r"\bp\.u\(", src)}
        calls |= {"KEYED.normal" for _ in re.findall(r"\bp\.normal\(", src)}
        if re.search(r"\b(randf|randi|randfn|exp|log|pow|sin|cos)\(", re.sub(r"DM\.\w+\(", "", src)):
            calls.add("a builtin draw or libm call")
    have = {"KEYED.u", "KEYED.below", "KEYED.normal", "DM.exp"}
    kit.check(calls <= have, "R0: the modules' keyed and DetMath calls %s are all in core (%s)" % (sorted(calls), sorted(have)))


def row_s0(kit, d, seed):
    s0 = os.path.join(d, "m00")
    with open(os.path.join(d, "s0g.txt"), encoding="utf-8") as f:
        g = f.read().strip()
    kit.check(g.startswith("ok"), "S0-g@s%d (oracle): %s" % (seed, g))
    p = P.read(s0)
    p.contact_idx = [-1] * len(p.contact_idx)
    p.contact_kind = [0] * len(p.contact_kind)
    p.contact_trust = [0.0] * len(p.contact_trust)
    p.contact_last = [0] * len(p.contact_last)
    p.member_of = [-1] * len(p.member_of)
    p.union_cover = [0] * len(p.union_cover)
    p.groups = []
    rel.build(p)
    grp.seed_groups(p)
    t = p.tree()
    links = ("contact_idx", "contact_kind", "contact_trust", "contact_last", "member_of", "union_cover", "groups")
    want = read_hashes(s0 + ".sha.txt")
    hs = shim.hashes({k: t[k] for k in links})
    bad = [k for k in links if hs[k] != want[k]]
    extra = ""
    if bad:
        ref = load(s0)
        extra = "; " + "; ".join("%s: %s" % (n, first_diff(t[n], ref[n])) for n in bad[:4])
    kit.check(not bad, "S0@s%d: the built links equal the created state's, differing %s%s" % (seed, bad, extra))


def row_dhook(kit, d, seed, months):
    with open(os.path.join(d, "dhook.txt"), encoding="utf-8") as f:
        lines = [x for x in f.read().splitlines() if x]
    bad = [x for x in lines if not x.startswith("ok")]
    kit.check(len(lines) == months and not bad, "D-hook@s%d (oracle): %d months, failing %s" % (seed, len(lines), bad[:3]))


def run_a(p):
    p.section_a()
    return p.tree(("counts", "dec_counts", "ref_counts"))


def row_a(kit, d, seed, m, mutate=None, label="A"):
    p = P.read(os.path.join(d, "m%02d_pre" % m))
    if mutate:
        mutate(p)
    return compare(kit, "%s@s%d@m%d" % (label, seed, m), run_a(p), os.path.join(d, "m%02d_a.sha.txt" % m), os.path.join(d, "m%02d_a" % m))


def truth_of(d, m):
    return read_json(os.path.join(d, "m%02d_truth.json" % m))


def row_b(kit, d, seed, m, mutate=None, label="B", p=None):
    if p is None:
        p = P.read(os.path.join(d, "m%02d_a" % m))
    if mutate:
        mutate(p)
    p.section_b(truth_of(d, m))
    return compare(kit, "%s@s%d@m%d" % (label, seed, m), p.tree(("counts",)), os.path.join(d, "m%02d_b.sha.txt" % m), os.path.join(d, "m%02d_b" % m))


def _rows_of(p, js):
    C = rel.C
    out = []
    for j in js:
        out.append([j, p.contact_idx[j * C:(j + 1) * C], p.contact_kind[j * C:(j + 1) * C], p.contact_trust[j * C:(j + 1) * C],
                    p.contact_last[j * C:(j + 1) * C], p.age[j], p.employment[j], p.hh_kind[j], p.pref_social[j], p.pid[j]])
    return out


def _plain(x):
    if isinstance(x, _codec.Packed):
        return [v.item() if hasattr(v, "item") else v for v in x.a]
    if isinstance(x, list):
        return [_plain(v) for v in x]
    return x


def row_r(kit, d, seed, m, label="R"):
    p = P.read(os.path.join(d, "m%02d_b" % m))
    recs = read_json(os.path.join(d, "m%02d_r.json" % m))
    pools = {}
    for i in range(p.n):
        pools.setdefault(p.pref[i], []).append(i)
    C = rel.C
    bad = []
    for k, rec in enumerate(recs):
        i = rec["i"]
        pool = pools.get(rec["pref"], [])
        if len(pool) != rec["pool_n"]:
            bad.append("call %d (person %d): pool %d vs the oracle's %d" % (k, i, len(pool), rec["pool_n"]))
            break
        for row in _plain(rec["pre"]):
            j = row[0]
            p.contact_idx[j * C:(j + 1) * C] = row[1]
            p.contact_kind[j * C:(j + 1) * C] = row[2]
            p.contact_trust[j * C:(j + 1) * C] = row[3]
            p.contact_last[j * C:(j + 1) * C] = row[4]
            p.age[j], p.employment[j], p.hh_kind[j], p.pref_social[j], p.pid[j] = row[5], row[6], row[7], row[8], row[9]
        rel.replenish(p, i, pool)
        mine = _rows_of(p, _plain(rec["js"]))
        want = _plain(rec["post"])
        r = first_diff(mine, want)
        if r is not None:
            bad.append("call %d (person %d): %s" % (k, i, r))
            break
    kit.check(not bad, "%s@s%d@m%d: %d replenish calls, first differing %s" % (label, seed, m, len(recs), bad[:1]))


class _W:
    pass


class Quiet(Kit):
    # A must-fail row's inner comparison: its FAIL is the expected outcome, so it is not printed as one
    def check(self, ok, label):
        pass


def row_w(kit, d, seed, m, label="W"):
    t = load(os.path.join(d, "m%02d_wpre" % m))
    w = _W()
    w.weight = list(t["weight"].a.tolist())
    w.member_of = list(t["member_of"].a.tolist())
    w.groups = t["groups"]
    w.n = len(w.weight)
    grp.refresh_weights(w)
    compare(kit, "%s@s%d@m%d" % (label, seed, m), {"groups": w.groups}, os.path.join(d, "m%02d_w.sha.txt" % m))


def call_table(p):
    # oracle_dump_rel.gd's _call_table, the same calls in the same order (REL_PORT_PLAN AMENDED U1)
    outs = []
    a37 = [i for i in range(p.n) if i % 37 == 0]
    a41 = [i for i in range(p.n) if i % 41 == 5]
    for i in a37:
        outs.append(["classes.%d" % i, grp.classes(p, i)])
        outs.append(["targets.%d" % i, rel.targets(p, i)])
        outs.append(["union_rate.%d" % i, grp.union_rate(p, i)])
        for a in (act.A_THRIFT, act.A_SPLURGE, act.A_SOCIALIZE):
            outs.append(["contact_action_share.%d.%d" % (i, a), rel.contact_action_share(p, i, a)])
        outs.append(["action_law.%d" % i, act.action_law(p, i)])
        outs.append(["pick_group.%d" % i, grp.pick_group(p, i)])
        outs.append(["discontented_contacts.%d" % i, grp.discontented_contacts(p, i)])
        outs.append(["most_trusted.%d" % i, rel.most_trusted(p, i)])
        outs.append(["most_trusted_family.%d" % i, rel.most_trusted(p, i, rel.K_FAMILY)])
        outs.append(["pick_partner.%d" % i, rel.pick_partner(p, i, "partner")])
    for ka in range(6):
        for kb in range(6):
            outs.append(["relation.%d.%d" % (ka, kb), grp.relation(ka, kb)])
    outs.append(["group_summary", grp.group_summary(p)])
    for ck in ("age_band", "employment", "income_tercile", "education", "prefecture"):
        outs.append(["summary_by_class.%s" % ck, grp.summary_by_class(p, ck, p.emotion_column("anxiety"))])
    for i in a37:
        grp.new_job(p, i)
    for i in a41:
        c0 = c1 = -1
        for c in range(rel.C):
            if p.contact_idx[i * rel.C + c] >= 0:
                if c0 < 0:
                    c0 = c
                elif c1 < 0:
                    c1 = c
        if c0 >= 0:
            j = p.contact_idx[i * rel.C + c0]
            rel.unlink(p, j, i)
            outs.append(["has_contact_after_unlink.%d" % i, rel.has_contact(p, j, i)])
            outs.append(["add_back.%d" % i, rel.add(p, j, i, rel.K_FRIEND)])
        if c1 >= 0:
            rel.unlink_slot(p, i, c1)
        rel.drop_all(p, i)
        rel.forget(p, i)
        grp.clear_cover(p, i)
    return outs


def row_u(kit, d, seed):
    p = P.read(os.path.join(d, "u_in"))
    outs = call_table(p)
    want = read_hashes(os.path.join(d, "u_out.sha.txt"))
    ref = {o[0]: o[1] for o in read_json(os.path.join(d, "u_out.json"))}
    bad = []
    for label, v in outs:
        if shim.sha(v) != want.get(label):
            bad.append("%s: %s" % (label, first_diff(v, ref.get(label))))
    missing = sorted(set(want) - {o[0] for o in outs})
    kit.check(not bad and not missing, "U@s%d: %d results, differing %d %s, missing %s" % (seed, len(outs), len(bad), bad[:3], missing[:3]))
    compare(kit, "U-post@s%d" % seed, p.tree(), os.path.join(d, "u_post.sha.txt"))


def first_adult(p, code, k):
    seen = 0
    for i in range(p.n):
        if p.age[i] >= 18 and (code < 0 or p.pref[i] == code):
            if seen == k:
                return i
            seen += 1
    return -1


def cases(p):
    # oracle_dump_rel.gd's _cases, the same calls in the same order (REL_PORT_PLAN AMENDED K1)
    outs = []
    a0 = first_adult(p, -1, 0)
    outs.append(["kind_id.union", grp.kind_id("union")])
    outs.append(["kind_id.none", grp.kind_id("none")])
    outs.append(["slot_self", rel.slot(p, a0, a0)])
    rel.unlink(p, a0, a0)
    for i in range(p.n):
        if i % 29 == 3:
            rel.clear_met(p, i)
    for gid in range(len(p.groups)):
        ok = grp.join(p, a0, gid)
        outs.append(["join.%d" % gid, ok])
        if not ok and not grp.is_member(p, a0, gid):
            break
    outs.append(["join.again", grp.join(p, a0, p.member_of[a0 * grp.M])])
    f1 = first_adult(p, 13, 0)
    f2 = first_adult(p, 13, 1)
    c0 = {}
    outs.append(["found.1", grp.found_movement(p, f1, c0)])
    outs.append(["found.2", grp.found_movement(p, f1, c0)])
    outs.append(["found.3", grp.found_movement(p, f2, c0)])
    outs.append(["found.counts", c0])
    gm = grp.find_group(p, grp.G_MOVEMENT, 13)
    if gm < 0:
        gm = grp._new_group(p, grp.G_MOVEMENT, 13, -1)
    kept = 0
    for i in range(p.n):
        if grp.is_member(p, i, gm):
            if kept < 2:
                kept += 1
            else:
                grp.leave(p, i, gm)
    for i in range(p.n):
        if kept < 2 and p.pref[i] == 13 and p.age[i] >= 18 and grp.memberships(p, i) < grp.M and not grp.is_member(p, i, gm):
            grp.join(p, i, gm)
            kept += 1
    p.groups[gm]["small_months"] = grp.DISSOLVE_MONTHS - 1
    c1 = {}
    grp.step(p, c1)
    outs.append(["dissolve.status", int(p.groups[gm]["status"])])
    outs.append(["dissolve.counts", c1])
    c2 = {}
    grp.step(p, c2)
    outs.append(["after.counts", c2])
    p.group_influence = False
    c3 = {}
    grp.step(p, c3)
    p.group_influence = True
    outs.append(["no_influence.counts", c3])
    for i in range(p.n):
        if p.employment[i] == p.EMP_REGULAR or p.employment[i] == p.EMP_NONREGULAR:
            grp.new_job(p, i)
    b0 = first_adult(p, 47, 0)
    rel.drop_all(p, b0)
    for j in range(p.n):
        if rel.C <= p.contact_count(b0):
            break
        if j != b0 and p.pref[j] == 47 and not rel.has_contact(p, b0, j):
            rel.add(p, b0, j, rel.K_NEIGHBOUR)
    outs.append(["full_row", p.contact_count(b0)])
    rel.build(p)
    return outs


def row_k(kit, d, seed):
    p = P.read(os.path.join(d, "k_in"))
    outs = cases(p)
    want = read_hashes(os.path.join(d, "k_out.sha.txt"))
    ref = {o[0]: o[1] for o in read_json(os.path.join(d, "k_out.json"))}
    bad = ["%s: %s" % (label, first_diff(v, ref.get(label))) for label, v in outs if shim.sha(v) != want.get(label)]
    missing = sorted(set(want) - {o[0] for o in outs})
    kit.check(not bad and not missing, "K@s%d: %d results, differing %d %s, missing %s" % (seed, len(outs), len(bad), bad[:3], missing[:3]))
    compare(kit, "K-post@s%d" % seed, p.tree(), os.path.join(d, "k_post.sha.txt"))
    return {o[0]: o[1] for o in outs}


class _Rec(P):
    # The state _ranks or the records read: a few fields, so P's whole-state checks are skipped
    def __init__(self, tree):
        self._kinds = {}
        self._keys = list(tree.keys())
        for k, v in tree.items():
            if isinstance(v, _codec.Packed):
                self._kinds[k] = v.kind
                v = [x.item() if hasattr(x, "item") else x for x in v.a]
            setattr(self, k, v)


def row_rank(kit, d, seed, m, label="RANK"):
    p = _Rec(load(os.path.join(d, "m%02d_kpre" % m)))
    p._ranks()
    compare(kit, "%s@s%d@m%d" % (label, seed, m), {"rank": _codec.Packed(p._kinds["rank"], p.rank)}, os.path.join(d, "m%02d_rank.sha.txt" % m))


def row_rec(kit, d, seed, m, label="REC"):
    p = _Rec(load(os.path.join(d, "m%02d_recpre" % m)))
    p.records(p.counts, p.dec_counts, p.ref_counts)
    compare(kit, "%s@s%d@m%d" % (label, seed, m), {"decisions": p.decisions, "refusals": p.refusals, "events": p.events},
            os.path.join(d, "m%02d_rec.sha.txt" % m))


def _digests(path):
    # "month digest" lines (the dump's dhook files) or the verify box's "ORACLE_REL tiers seed S month M frozen <hex>" lines
    out = {}
    with open(path, encoding="utf-8") as f:
        for x in f.read().split("\n"):
            w = x.split()
            if len(w) == 2:
                out[int(w[0])] = w[1]
            elif len(w) >= 7 and w[0] == "ORACLE_REL":
                out[int(w[5])] = w[7] if len(w) > 7 else w[6]
    return out


def row_dhook_t(kit, d, seed, months):
    # REL_PORT_PLAN AMENDED T2: the hooked run's straight months (its first chunk) against the frozen reference; the months after a
    # resume are read as the diagnostic R-t, not gating
    import glob
    ref_path = os.environ.get("REL_TIERS_REF") or os.path.join(d, "dhook_ref_from01.txt")
    ref = _digests(ref_path)
    # dhook_t.txt is the name before the checkpoint (ac4da178's script), whose single run is all straight
    f01 = os.path.join(d, "dhook_t_from01.txt")
    first = _digests(f01 if os.path.exists(f01) else os.path.join(d, "dhook_t.txt"))
    same = lambda a, b: a[:min(len(a), len(b))] == b[:min(len(a), len(b))]
    bad = sorted(m for m in first if m in ref and not same(first[m], ref[m]))
    both = sorted(m for m in first if m in ref)
    kit.check(bool(both) and not bad, "D-hook-t@s%d (oracle): straight months %s against the frozen reference, differing %s" % (seed, both, bad))
    later = {}
    for path in sorted(glob.glob(os.path.join(d, "dhook_t_from*.txt"))):
        if not path.endswith("from01.txt"):
            later.update(_digests(path))
    r_bad = sorted(m for m in later if m in ref and not same(later[m], ref[m]))
    print("diag R-t@s%d: resumed months %s against the frozen reference, differing %s" % (seed, sorted(m for m in later if m in ref), r_bad), flush=True)


def row_rck(kit, d, d_split, seed, lo, hi):
    # REL_PORT_PLAN AMENDED T3: the run split at a checkpoint and resumed gives the unsplit run's cut hashes and digests, months lo..hi
    bad = []
    for m in range(lo, hi + 1):
        for k in ("pre", "a", "b", "wpre", "w", "rank", "rec", "kpre", "recpre"):
            fa, fb = os.path.join(d, "m%02d_%s.sha.txt" % (m, k)), os.path.join(d_split, "m%02d_%s.sha.txt" % (m, k))
            if not os.path.exists(fa) or not os.path.exists(fb):
                bad.append("m%02d_%s missing" % (m, k))
                continue
            ha, hb = read_hashes(fa), read_hashes(fb)
            diff = sorted(n for n in set(ha) | set(hb) if ha.get(n) != hb.get(n))
            if diff:
                bad.append("m%02d_%s %s" % (m, k, diff[:4]))
    import glob
    da, db = {}, {}
    for path in glob.glob(os.path.join(d, "dhook_t*.txt")):
        da.update(_digests(path))
    for path in glob.glob(os.path.join(d_split, "dhook_t*.txt")):
        db.update(_digests(path))
    bad += ["digest m%02d" % m for m in range(lo, hi + 1) if da.get(m) is None or da.get(m) != db.get(m)]
    kit.check(not bad, "R-ck@s%d: the resumed months %d-%d equal the unsplit run's cut hashes and digests, differing %s" % (seed, lo, hi, bad[:6]))


def row_mf2(kit, d, seed, label):
    real_u = P.u

    def u2(self, tag, i, b=0, c=0):
        return real_u(self, "choosE" if tag == "choose" else tag, i, b, c)
    P.u = u2
    try:
        bad = row_a(Quiet("MF2"), d, seed, 1, None, "MF2-inner")
    finally:
        P.u = real_u
    kit.check("last_action" in bad, "%s@s%d@m1: the choice tag changed makes A differ, fields %s" % (label, seed, bad[:8]))


def row_sr(kit, d, seed, m):
    p = P.read(os.path.join(d, "m%02d_pre" % m))
    t = run_a(p)
    tmp = tempfile.mkdtemp(prefix="rel_sr_")
    try:
        files = [0]
        tree = {k: enc(v, tmp, files) for k, v in t.items()}
        with open(os.path.join(tmp, "state.json"), "w", encoding="utf-8") as f:
            json.dump(tree, f)
        back = P.read(tmp)
        t2 = back.tree(("counts", "dec_counts", "ref_counts"))
        h1, h2 = shim.hashes(t), shim.hashes(t2)
        bad = sorted(k for k in set(h1) | set(h2) if h1.get(k) != h2.get(k))
        kit.check(not bad, "SR@s%d@m%d: Python's S_A read back has equal hashes, differing %s" % (seed, m, bad[:8]))
        # the read-back state lost the free text of the group log, which section B only appends to
        row_b(kit, d, seed, m, label="SR-B", p=back)
    finally:
        shutil.rmtree(tmp)


def row_mf(kit, d, seed):
    def nudge_trust(p):
        k = next(k for k in range(len(p.contact_idx)) if p.contact_idx[k] >= 0)
        p.contact_trust[k] = math.nextafter(p.contact_trust[k], math.inf)
    k0 = Quiet("MF1")
    bad = row_a(k0, d, seed, 6, nudge_trust, "MF1-inner")
    kit.check(bool(bad) and bad[0] == "contact_trust", "MF1@s%d@m6: a trust nudged by one ulp makes A differ, first field %s" % (seed, bad[:1]))
    real_u = P.u

    def u2(self, tag, i, b=0, c=0):
        return real_u(self, "choosE" if tag == "choose" else tag, i, b, c)
    P.u = u2
    try:
        k1 = Quiet("MF2")
        bad = row_a(k1, d, seed, 1, None, "MF2-inner")
    finally:
        P.u = real_u
    kit.check("last_action" in bad, "MF2@s%d@m1: the choice tag changed makes A differ, fields %s" % (seed, bad[:8]))

    def nudge_res(p):
        # REL_PORT_PLAN AMENDED MF3-1: the weight, which section B never writes; a resources ulp can be rounded away by the dues
        g = p.groups[0]
        g["weight"] = math.nextafter(float(g["weight"]), math.inf)
    k2 = Quiet("MF3")
    bad = row_b(k2, d, seed, 3, nudge_res, "MF3-inner")
    kit.check("groups" in bad, "MF3@s%d@m3: a group's weight nudged makes B's groups differ (AMENDED MF3-1), fields %s" % (seed, bad[:8]))


def main_tiers(root, kit):
    # REL_PORT_PLAN section 6 (AMENDED T1): the cuts in P-a's mode, under <root>/t<seed>/; REL_MONTHS_BY_SEED like 1:24,7:13 (AMENDED T4: seeds 1 and 7);
    # REL_SPLIT_DIR (the split run's ORACLE_OUT) and REL_SPLIT_MONTHS (7-12) for R-ck
    rows = set((sys.argv[2] if len(sys.argv) > 2 else "D-hook-t,A,B,R,W,RANK,REC,R-ck,MF2").split(","))
    plan = [tuple(int(x) for x in sm.split(":")) for sm in os.environ.get("REL_MONTHS_BY_SEED", "1:24,7:13").split(",")]
    for seed, months in plan:
        d = os.path.join(root, "t%d" % seed)
        # D-hook-t reads seed 1 only: the frozen reference exists for it alone (AMENDED T1/T4)
        if "D-hook-t" in rows and seed == plan[0][0]:
            row_dhook_t(kit, d, seed, months)
        for m in range(1, months + 1):
            if "A" in rows:
                row_a(kit, d, seed, m, label="T-A")
            if "B" in rows:
                row_b(kit, d, seed, m, label="T-B")
            if "R" in rows:
                row_r(kit, d, seed, m, label="T-R")
            if "W" in rows:
                row_w(kit, d, seed, m, label="T-W")
            if "RANK" in rows:
                row_rank(kit, d, seed, m, "T-rank")
            if "REC" in rows:
                row_rec(kit, d, seed, m, "T-rec")
        if "R-ck" in rows and os.environ.get("REL_SPLIT_DIR"):
            lo, hi = (int(x) for x in os.environ.get("REL_SPLIT_MONTHS", "7-12").split("-"))
            row_rck(kit, d, os.path.join(os.environ["REL_SPLIT_DIR"], "t%d" % seed), seed, lo, hi)
        if "MF2" in rows and seed == plan[0][0]:
            row_mf2(kit, d, seed, "T-mf")
    kit.finish()


def main():
    root = sys.argv[1]
    if os.environ.get("REL_MODE") == "tiers":
        main_tiers(root, Kit("py/tests/run_rel.py (tiers)"))
        return
    rows = set((sys.argv[2] if len(sys.argv) > 2 else "R0,S0,D-hook,A,B,R,W,RANK,REC,U,K,SR,MF1,MF2,MF3").split(","))
    seeds = [int(s) for s in os.environ.get("REL_SEEDS", "1,7,42").split(",")]
    months = int(os.environ.get("REL_MONTHS", "36"))
    u_seed = int(os.environ.get("REL_U_SEED", "7"))
    kit = Kit("py/tests/run_rel.py")
    if "R0" in rows:
        row_r0(kit)
    for seed in seeds:
        d = os.path.join(root, "s%d" % seed)
        if "S0" in rows:
            row_s0(kit, d, seed)
        if "D-hook" in rows:
            row_dhook(kit, d, seed, months)
        for m in range(1, months + 1):
            if "A" in rows:
                row_a(kit, d, seed, m)
            if "B" in rows:
                row_b(kit, d, seed, m)
            if "R" in rows:
                row_r(kit, d, seed, m)
            if "W" in rows:
                row_w(kit, d, seed, m)
            if "RANK" in rows:
                row_rank(kit, d, seed, m)
            if "REC" in rows:
                row_rec(kit, d, seed, m)
        if "SR" in rows:
            row_sr(kit, d, seed, 12)
        if rows & {"MF1", "MF2", "MF3"}:
            row_mf(kit, d, seed)
        if "U" in rows and seed == u_seed:
            row_u(kit, d, seed)
        if "K" in rows and seed == u_seed:
            row_k(kit, d, seed)
    kit.finish()


if __name__ == "__main__":
    main()
