# The rows of LC_HH_PORT_PLAN §5 against oracle_dump_lc_hh.gd's output: L0-k, L0-sort, L-h, L0-s, then per month L1 (or L1s by the
# dump's seed), L1y, L1-sort, L1c and L-c; L-sr at month 12, L-mf1 at month 6, L-mf2 over months 1-12, L-mf3 at the first month with a
# birth. On a mismatch, the first differing field (and index, where the oracle wrote the whole cut)
#   python py/tests/run_lchh.py <dump dir> [months]
import copy
import json
import os
import struct
import sys

from common import Kit
from core import digest as state, keyed
from core.digest import Packed
from lchh import gdsort, households as HH, life_course as LC, pstate as ps
from lchh.checks import invariants

# Fields only the life course and the rake write: people.gd's month (parts A-C) must leave them as the last cut left them (L1c)
LC_ONLY = ("lc_c", "lc_qcut", "lc_t22b", "lc_c_band", "lc_births", "lc_deaths", "lc_nm_short", "ever_married", "union_month",
           "last_birth", "births_n", "health_class", "next_k")


def F(bits):
    return struct.unpack("<d", struct.pack("<q", int(bits)))[0]


def B(x):
    return str(struct.unpack("<q", struct.pack("<d", x))[0])


def plain(v):
    if isinstance(v, Packed):
        return list(v.a)
    if isinstance(v, list):
        return [plain(x) for x in v]
    if isinstance(v, dict):
        return {k: plain(x) for k, x in v.items()}
    return v


def first_diff(a, b, path=""):
    a, b = plain(a), plain(b)
    if isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            return "%s length %d vs %d" % (path, len(a), len(b))
        for i in range(len(a)):
            r = first_diff(a[i], b[i], "%s[%d]" % (path, i))
            if r:
                return r
        return ""
    if isinstance(a, dict) and isinstance(b, dict):
        if set(a) != set(b):
            return "%s keys only python %s, only oracle %s" % (path, sorted(set(a) - set(b), key=str)[:5], sorted(set(b) - set(a), key=str)[:5])
        for k in sorted(a, key=state._sort_key):
            r = first_diff(a[k], b[k], "%s[%r]" % (path, k))
            if r:
                return r
        return ""
    if type(a) != type(b) or a != b:
        return "%s %r (%s) vs %r (%s)" % (path, a, type(a).__name__, b, type(b).__name__)
    return ""


class Dump:
    def __init__(self, d):
        self.d = d
        self.reg, self.spec, self.hh_spec = ps.load_dump_common(d)
        self.kinds = {f[0]: f[1] for f in self.reg["fields"]}

    def has(self, cut):
        return os.path.isdir(os.path.join(self.d, cut))

    def load(self, cut):
        return ps.load_cut(self.d, cut, self.reg, self.spec, self.hh_spec)

    def hashes(self, cut):
        return state.read_hashes(os.path.join(self.d, cut + ".sha.txt"))

    def json(self, name):
        with open(os.path.join(self.d, name), encoding="utf-8") as f:
            return json.load(f)


def compare(dm, p, cut, label, kit, quiet_ok=False):
    want = dm.hashes(cut)
    _, got = p.digest()
    bad = [n for n in sorted(want) if got.get(n) != want[n]]
    extra = sorted(set(got) ^ set(want))
    detail = ""
    if bad and dm.has(cut):
        ref = dm.load(cut)
        detail = "; " + "; ".join("%s:%s" % (n, first_diff(p.field(n), ref.field(n))) for n in bad[:4])
    kit.check(not bad and not extra, "%s: fields differing %d %s%s%s" % (label, len(bad), bad[:8], (" names " + str(extra)) if extra else "", detail))
    return bad


def row_keyed(dm, kit):
    g = dm.json("grid.json")
    seed = g["seed"]
    bad = []
    for t, a, ub, bl, nb in g["keyed"]:
        if B(keyed.u(seed, t, a, 7, 3)) != ub or keyed.below(17, seed, t, a, 7, 3) != bl or B(keyed.normal(seed, t, a, 7, 3)) != nb:
            bad.append((t, a))
    for r, y, s, k, pv in g["pid"]:
        if str(ps.pid(seed, r, y, s, k)) != pv:
            bad.append(("pid", r, y, s, k))
    cs = dm.reg["consts"]
    mine = {"C": ps.C, "M": ps.M, "NT": ps.NT, "NE": ps.NE, "ND": ps.ND, "AGES": ps.AGES, "SEXES": ps.SEXES, "K_FAMILY": ps.K_FAMILY,
            "TRUST0": list(ps.TRUST0), "MOVE_KEEP": ps.MOVE_KEEP, "AGE_BANDS": list(ps.AGE_BANDS), "EMOTIONS": list(ps.EMOTIONS),
            "D_FAMILY": ps.D_FAMILY, "D_AUTONOMY": ps.D_AUTONOMY, "D_SECURITY": ps.D_SECURITY, "GRADE_POOR": ps.GRADE_POOR,
            "GRADE_LIMITED": ps.GRADE_LIMITED, "EMP_STUDENT": ps.EMP_STUDENT, "EMP_RETIRED": ps.EMP_RETIRED}
    cbad = [k for k in mine if cs.get(k) != mine[k] and not (isinstance(mine[k], (int, float)) and cs.get(k) == float(mine[k]))]
    kit.check(not bad and not cbad, "L0-k: %d keyed values and %d pids against GDScript, constants; differing %s %s" % (
        len(g["keyed"]), len(g["pid"]), bad[:5], cbad))
    bad2 = []
    for i, s in enumerate(g["sort"]):
        rows = [[F(b), 0.0, j] for j, b in enumerate(s["keys"])]
        gdsort.sort_custom(rows, LC._row_less)
        if [r[2] for r in rows] != s["perm"]:
            bad2.append((len(s["keys"]), i))
    kit.check(not bad2, "L0-sort: %d Godot sort_custom permutations (sizes 0-300, ties and none); differing %s" % (len(g["sort"]), bad2[:5]))


def row_hook(dm, kit):
    h = dm.json("hook.json")
    bad = [r[0] for r in h if r[1] != r[2] or r[3] != r[4]]
    kit.check(not bad, "L-h: the dump's hooked start and step equal people.create / people.step at months 0-%d; differing %s" % (h[-1][0], bad[:8]))


def row_start(dm, kit):
    n_per = dm.json("start/n_per.json")["n_per"]
    for cut, fn in (("hh", lambda p: HH.build_start(p, n_per)), ("lc", LC.start), ("link", HH.link_family),
                    ("rake", lambda p: (p.reweight(None, True), LC.solve_c(p)))):
        p = dm.load("start/%s_pre" % cut)
        fn(p)
        compare(dm, p, "start/%s_post" % cut, "L0-s %s" % cut, kit)


def stub(p, pid, age, sex):
    # One person, for recomputing a Y call from its logged inputs (LC_HH_PORT_PLAN §2)
    s = copy.copy(p)
    s.pid, s.age, s.sex = [pid], [age], [sex]
    return s


def row_y(dm, pre, prev_expected, m, kit):
    y = dm.json("m%02d_y.json" % m)
    bad = []
    died = []
    exp = list(prev_expected)
    idx = {pre.pid[i]: i for i in range(pre.n)}
    for r in y:
        pid = int(r["pid"])
        if r["call"] == "dies":
            e = F(r["e"])
            qk = LC.quartile_of(pre, e, r["age"])
            q = LC.h_death(pre, r["age"], r["sex"], r["health"], qk)
            d = keyed.u(pre.seed_v, "death", pid & ps.PID_LOW, pre.month, 0) < q
            exp[LC._dband(r["age"]) * 2 + r["sex"]] += q
            if qk != r["quartile"] or B(q) != r["q"] or d != r["died"]:
                bad.append(("dies", pid, qk, r["quartile"], B(q) == r["q"], d, r["died"]))
            if r["died"]:
                died.append(idx[pid])
        elif r["call"] == "year_turn":
            s = stub(pre, pid, r["age"], r["sex"])
            s.births_n, s.intends_marry, s.intended_kids = [r["births_n"]], [r["intends_marry0"]], [r["intended_kids0"]]
            LC.year_turn(s, 0)
            if s.intends_marry[0] != r["intends_marry"] or s.intended_kids[0] != r["intended_kids"]:
                bad.append(("year_turn", pid, s.intends_marry[0], r["intends_marry"], s.intended_kids[0], r["intended_kids"]))
        elif r["call"] == "retire":
            if (keyed.u(pre.seed_v, "retire", pid & ps.PID_LOW, pre.month, 0) < LC.h_retire(pre)) != r["retired"]:
                bad.append(("retire", pid))
    if list(pre.lc_dying) != died:
        bad.append(("lc_dying", len(pre.lc_dying), len(died)))
    if [B(x) for x in exp] != [B(x) for x in pre.lc_expected]:
        bad.append(("lc_expected",))
    kit.check(not bad, "L1y month %d: %d calls (%d deaths), outputs, lc_dying and lc_expected; differing %d %s" % (
        m, len(y), len(died), len(bad), bad[:4]))


def _sort_row(dm, p, m, kit):
    if kit is None:
        return
    perms = dm.json("m%02d_sort.json" % m if isinstance(m, int) else m)
    mine = [[r[2] for r in rows] for rows in LC.quartile_rows(p)]
    bad = [b for b in range(9) if mine[b] != perms[b]]
    kit.check(not bad, "L1-sort %s: the quartile cuts' permutations in 9 bands; bands differing %s" % (
        "month %d" % m if isinstance(m, int) else m, bad))


def run_stage(dm, pre, m, kit=None, mf=None, save_dir=None):
    pre.replay = ps.load_newborns(dm.d, m, dm.kinds)
    if mf == "replay_off":
        pre.replay_off = True
    if save_dir is None:
        LC.stage(pre, None, lambda q: _sort_row(dm, q, m, kit))
        return pre
    LC.grade_birthday(pre)
    LC.month(pre)
    if save_dir is not None:
        pre.save(save_dir)
        rp = state.load(save_dir, as_lists=True)
        rep = pre.replay
        pre = ps.P(dm.reg, dm.spec, dm.hh_spec, rp)
        pre.replay = rep
    pre.reweight(None)
    if kit is not None:
        perms = dm.json("m%02d_sort.json" % m)
        mine = [[r[2] for r in rows] for rows in LC.quartile_rows(pre)]
        bad = [b for b in range(9) if mine[b] != perms[b]]
        kit.check(not bad, "L1-sort month %d: the quartile cuts' permutations in 9 bands; bands differing %s" % (m, bad))
    LC.quartile_cuts(pre)
    return pre


def main():
    d = sys.argv[1]
    months = int(sys.argv[2]) if len(sys.argv) > 2 else 36
    kit = Kit("py/tests/run_lchh.py")
    import run_lchh_k
    tracer = run_lchh_k.Tracer()
    tracer.start()
    dm = Dump(d)
    row_keyed(dm, kit)
    row_hook(dm, kit)
    row_start(dm, kit)
    prev = dm.load("start/rake_post")
    mf3_done = False
    for m in range(1, months + 1):
        pre = dm.load("m%02d_pre" % m)
        row_y(dm, pre, prev.lc_expected, m, kit)
        hs_prev, hs_pre = prev.hashes(), pre.hashes()
        bad_c = [n for n in LC_ONLY if hs_prev.get(n) != hs_pre.get(n)]
        kit.check(not bad_c, "L1c month %d: the life course's own fields unchanged by people.gd's month since the last cut; changed %s" % (m, bad_c))
        n0 = pre.n
        deaths = len(set(pre.lc_dying))
        nb = len(ps.load_newborns(d, m, dm.kinds))
        post = run_stage(dm, dm.load("m%02d_pre" % m), m, kit)
        bad = compare(dm, post, "m%02d_post" % m, "L1 month %d (seed %d, n %d -> %d)" % (m, pre.seed_v, n0, post.n), kit)
        errs = invariants(post, n0, deaths, nb)
        kit.check(not errs, "L-c month %d: persons, membership, partners, weights, prefecture totals; %s" % (m, errs[:3]))
        if m == 12:
            sd = os.path.join(d, "py_sr_m12")
            p2 = run_stage(dm, dm.load("m%02d_pre" % m), m, save_dir=sd)
            kit.check(p2.digest()[0] == post.digest()[0], "L-sr month 12: saved after LC.month, restored, the rake and cuts: equal to the straight stage")
        if m == 6:
            p3 = dm.load("m06_pre")
            p3.hh_weight[0] = F(int(B(p3.hh_weight[0])) + 1)
            for i in p3.hh_members[0]:
                p3.weight[i] = p3.hh_weight[0]
            p3 = run_stage(dm, p3, m)
            _, h3 = p3.digest()
            want = dm.hashes("m06_post")
            diff = [n for n in sorted(want) if h3.get(n) != want[n]]
            kit.check("hh_weight" in diff and "weight" in diff, "L-mf1 month 6: one household weight nudged by one ulp: post differs in %s" % diff[:6])
        if nb > 0 and not mf3_done:
            mf3_done = True
            p4 = run_stage(dm, dm.load("m%02d_pre" % m), m, mf="replay_off")
            _, h4 = p4.digest()
            want = dm.hashes("m%02d_post" % m)
            diff = [n for n in sorted(want) if h4.get(n) != want[n]]
            kit.check(bool(diff), "L-mf3 month %d (%d births): the newborns' replayed fields not copied: post differs in %s" % (m, nb, diff[:6]))
        prev = post
        if bad:
            break
    LC.TAG_PARTNER[0] = "lc_partnex"
    hit = []
    try:
        for m in range(1, min(12, months) + 1):
            p5 = run_stage(dm, dm.load("m%02d_pre" % m), m)
            if p5.hashes().get("partner") != dm.hashes("m%02d_post" % m).get("partner"):
                hit.append(m)
                break
    finally:
        LC.TAG_PARTNER[0] = "lc_partner"
    kit.check(bool(hit), "L-mf2: the partnering tag changed by one character: partner differs at month %s" % hit)
    run_lchh_k.rows(dm, kit)
    tracer.stop()
    miss = tracer.missing()
    kit.check(not miss, "L-ran: %d declared paths ran; not run %s" % (len(tracer.want) - len(miss), miss))
    kit.finish()


if __name__ == "__main__":
    main()
