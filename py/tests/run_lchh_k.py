# The K rows of LC_HH_PORT_PLAN §7 (L-K1 to L-K8) and L-ran, called by run_lchh.py after the monthly rows
import copy
import inspect
import json
import os
import struct
import sys

from lchh import checks, gdsort, households as HH, life_course as LC, pstate as ps
from lchh.checks import invariants


def F(bits):
    return struct.unpack("<d", struct.pack("<q", int(bits)))[0]


def B(x):
    return str(struct.unpack("<q", struct.pack("<d", x))[0])


# L-ran's paths (LC_HH_PORT_PLAN §7, §7.1): (row, function, the whole line as it reads, stripped, and which occurrence of that
# exact line in the function). Why whole lines and not snippets: a snippet such as `continue` could match an earlier line
PATHS = [
    ('L-K1 a: a head moves its household', LC.move_household, 'ms = list(p.hh_members[h])', 0),
    ('L-K1 b: a couple moves out together', LC.move_household, '_move_out(p, man, hn, ps.R_HEAD)', 0),
    ('L-K1 c: a member moves out alone', LC.move_household, '_log(p, i, "moved", -1, {"to": dest, "members": 1, "reason": reason})', 0),
    ('L-K1 d: an institution resident stays', LC.move_household, 'return []', 0),
    ('L-K1: _moved leaves a group of the old prefecture', ps.P._moved, 'grp_leave(self, i, g)', 0),
    ('L-K1: _moved drops a contact left behind', ps.P._moved, 'rel_unlink_slot(self, i, c)', 0),
    ('L-K1: unlink_slot clears the other side', ps.rel_unlink_slot, 'p.contact_idx[j * C + back] = -1', 0),
    ('L-K2: dies appends a death', LC.dies, 'p.lc_dying.append(i)', 0),
    ('L-K2: _deaths skips a duplicate', LC._deaths, 'continue', 0),
    ('L-K2/L1: stage()', LC.stage, 'grade_birthday(p)', 0),
    ('L-K3: an INF cut', LC.quartile_cuts, 'p.lc_qcut[b2 * 3 + q] = INF', 0),
    ('L-K4: the heap path', gdsort._partial_sort, '_make_heap(arr, first, middle, less)', 0),
    ("L-K4: adjust_heap's child step", gdsort._adjust_heap, 'second -= 1', 0),
    ("L-K4: push_heap's climb", gdsort._push_heap, 'hole = parent', 0),
    ('L-K4: sort_heap', gdsort._sort_heap, '_pop_heap_to(arr, first, last - 1, last - 1, arr[last - 1], less)', 0),
    ('L-K5: h_death at an INF mu', LC.h_death, 'return 1.0', 0),
    ("L-K5: _band_index skips a '+' band", HH._band_index, 'continue', 0),
    ('L-K5: _band_index finds none', HH._band_index, 'return -1', 0),
    ('L-K5: _draw_age skips a zero weight', HH._draw_age, 'continue', 0),
    ("L-K5: _draw_age's last fallback", HH._draw_age, 'return last', 1),
    ("L-K5: _pick's fallback", HH._pick, 'return str(keys[len(keys) - 1])', 0),
    ('L-K6: _scale_cell with no record', HH._scale_cell, 'return', 0),
    ('L-K6: link_family skips a held contact', HH.link_family, 'continue', 0),
    ('L-K6: link_family unlinks when the reverse add fails', HH.link_family, 'ps.rel_unlink(p, i, j)', 0),
    ('L-K6: _tilt_sizes skips a zero target', HH._tilt_sizes, 'continue', 0),
    ('L-K7: kish', HH.kish, 'eff_in += b[0] * b[0] / maxf(1e-12, b[1])', 0),
    ('L-K7: type_shares', HH.type_shares, 'out["mean_size"] = persons / maxf(1e-9, tot)', 0),
    ("L-K9: _grade_of's fallback", LC._grade_of, 'return NG - 1', 0),
    ("L-K10: a newborn without replayed fields raises", ps.P._replay_person, 'raise KeyError("no replayed fields for newborn pid %d" % self.pid[j])', 0),
    ("L-K11: rel_slot finds no slot", ps.rel_slot, 'return -1', 0),
] + [("L-K8: invariants' error %d" % k, checks.invariants, t, 0) for k, t in enumerate([
    'errs.append("persons %d != %d - %d + %d" % (p.n, n_before, deaths, births))',
    'errs.append("person %d in two households" % i)',
    'errs.append("member %d of %d has hh_id %d" % (i, h, p.hh_id[i]))',
    'errs.append("member %d weight" % i)',
    'errs.append("%d persons in households of %d" % (len(seen), p.n))',
    'errs.append("partners %d %d" % (i, j))',
    'errs.append("prefecture %d: %r vs %r" % (code, v, p.pref_pop[code] * scale))',
])]


def in_group(p, h):
    return any(p.member_of[j * ps.M + m] >= 0 for j in p.hh_members[h] for m in range(ps.M))


def k6_prepare(p):
    # oracle_dump_lc_hh.gd's _k6_prepare (LC_HH_PORT_PLAN §7, AMENDED)
    for h in range(p.hh_n):
        ms = p.hh_members[h]
        if len(ms) < 2 or not HH._private(p, h):
            continue
        i, j = ms[0], ms[1]
        ps.rel_drop_all(p, i)
        x = 0
        while p.contact_count(j) < ps.C and x < p.n:
            if x != j and not ps.rel_has_contact(p, j, x):
                ps.rel_add(p, j, x, 1)
            x += 1
        return


class Tracer:
    # The lines run in the functions of PATHS only. Why not the stdlib trace module over everything: the rows then take 3 times longer
    def __init__(self):
        self.want = {}
        for label, fn, snip, occ in PATHS:
            code = fn.__code__
            src, first = inspect.getsourcelines(fn)
            hits = [first + k for k, line in enumerate(src) if line.strip() == snip]
            if occ >= len(hits):
                raise ValueError("L-ran: %s: the line %r (occurrence %d) is not in %s" % (label, snip, occ, fn.__qualname__))
            self.want[label] = (code, hits[occ])
        self.codes = {c for c, _ in self.want.values()}
        self.ran = set()

    def _local(self, frame, event, arg):
        if event == "line":
            self.ran.add((frame.f_code, frame.f_lineno))
        return self._local

    def _global(self, frame, event, arg):
        return self._local if frame.f_code in self.codes else None

    def start(self):
        sys.settrace(self._global)

    def stop(self):
        sys.settrace(None)

    def missing(self):
        return ["%s (line %d)" % (label, key[1]) for label, key in self.want.items() if key not in self.ran]


def _compare(dm, p, cut, label, kit):
    from run_lchh import compare
    return compare(dm, p, cut, label, kit)


def rows(dm, kit):
    K = os.path.join(dm.d, "k")
    if not os.path.isdir(K):
        kit.check(False, "L-K: the dump has no k/ directory (a dump older than the K cases)")
        return
    post36 = None
    # L-K7: kish and type_shares on the month-36 state (the K1 pre state is that state)
    p = dm.load("k/k1_pre")
    post36 = copy.deepcopy(p)
    k7 = dm.json("k/k7.json")
    mine = {"kish": HH.kish(p), "type_shares": HH.type_shares(p)}
    bad7 = [(g, k) for g in mine for k in mine[g]
            if (B(mine[g][k]) if isinstance(mine[g][k], float) else str(mine[g][k])) != k7[g].get(k)]
    bad7 += [(g, k) for g in k7 for k in k7[g] if k not in mine[g]]
    kit.check(not bad7, "L-K7: kish and type_shares at month 36, %d values; differing %s" % (sum(len(v) for v in k7.values()), bad7[:5]))
    # L-K5: pure calls
    k5 = dm.json("k/k5.json")
    al = p.hh_spec["alone_share_by_band"]["value"]["bands"]
    bad5 = []
    if [HH._band_index(10, al), HH._band_index(90, al)] != k5["band_index"]:
        bad5.append("band_index")

    def zero_even(a, _s):
        return 0.0 if a % 2 == 0 else 1.0
    if [list(HH._draw_age(p, x, [0, 1], 15, ps.AGES - 1, zero_even)) for x in (0.5, 1.0)] != k5["draw_age"]:
        bad5.append("draw_age")
    if HH._pick(HH._v(p, "type_shares"), HH.TYPES, 1.0) != k5["pick"]:
        bad5.append("pick")
    hd = [B(LC.h_death(p, a, s, 4, 0)) for a in range(111) for s in range(2)]
    bad5 += ["h_death a %d s %d" % (k // 2, k % 2) for k in range(len(hd)) if hd[k] != k5["h_death"][k]][:3]
    kit.check(not bad5, "L-K5: pure calls (band_index, draw_age, pick, h_death a 0-110); differing %s" % bad5)
    # L-K4: Godot's order on the crafted arrays
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "tools/py/lchh_k4_sort.json"), encoding="utf-8") as f:
        arrs = json.load(f)["arrays"]
    k4 = dm.json("k/k4.json")
    bad4 = []
    for e, want in zip(arrs, k4):
        r = [[float(v), 0.0, i] for i, v in enumerate(e["keys"])]
        gdsort.sort_custom(r, LC._row_less)
        if [x[2] for x in r] != want:
            bad4.append("%d %s" % (e["n"], e["variant"]))
    kit.check(not bad4 and len(k4) == len(arrs), "L-K4: Godot's sort_custom on %d crafted arrays (introsort depth limit, one with ties); differing %s" % (
        len(arrs), bad4))
    # L-K1: move_household as people.move_to calls it
    mv = dm.json("k/k1.json")
    bad1 = []
    for kind, pid_s, dest, want in mv:
        if pid_s == "-1":
            bad1.append("no person of kind %s in the dump" % kind)
            continue
        i = p.pid.index(int(pid_s))
        got = [str(p.pid[j]) for j in LC.move_household(p, i, dest, "job")]
        if got != want:
            bad1.append("kind %s returned %s vs %s" % (kind, got, want))
    kit.check(not bad1, "L-K1: move_household on 4 persons (head, couple, alone, institution): returns; %s" % bad1)
    _compare(dm, p, "k/k1_post", "L-K1: the state after the moves", kit)
    # L-K2: dies directly, twice for some, then stage()
    p = dm.load("k/k2_pre")
    dc = dm.json("k/k2.json")
    bad2 = []
    for pid_s, died in dc:
        i = p.pid.index(int(pid_s))
        if LC.dies(p, i) != died:
            bad2.append(pid_s)
    kit.check(not bad2, "L-K2: dies called %d times (every person, then those who died again): outcomes; differing %s" % (len(dc), bad2[:4]))
    p.replay = ps.load_newborns(K, "k2_newborn.json", dm.kinds)
    from run_lchh import _sort_row
    LC.stage(p, None, lambda q: _sort_row(dm, q, "k/k2_sort.json", kit))
    _compare(dm, p, "k/k2_post", "L-K2: stage() after the direct deaths", kit)
    # L-K3: band 0 emptied, then the cuts
    p = dm.load("k/k3_pre")
    for i in range(p.n):
        if p.age[i] < 10:
            p.age[i] = 10
    LC.quartile_cuts(p)
    _compare(dm, p, "k/k3_post", "L-K3: the cuts with band 0 empty (INF)", kit)
    kit.check(p.lc_qcut[0:3] == [float("inf")] * 3, "L-K3: band 0's three cuts are INF: %s" % p.lc_qcut[0:3])
    # L-K6
    p = dm.load("k/k6_pre")
    k6_prepare(p)
    HH._scale_cell(p, [0, 0, 0, 1.0], lambda h: HH._private(p, h) and p.hh_type[h] == ps.HK_SINGLE)
    HH.link_family(p)
    ms = p.hh_spec["mean_size_by_prefecture"]["value"]
    old = ms["13"]
    ms["13"] = 0.0
    HH._tilt_sizes(p)
    ms["13"] = old
    _compare(dm, p, "k/k6_post", "L-K6: _scale_cell (no record), link_family on a full state, _tilt_sizes with a zero target", kit)
    # L-K8: invariants() reports each broken rule
    kit.check(not invariants(post36, post36.n, 0, 0), "L-K8 (control): invariants() report nothing on the month-36 state")
    reported = []

    def broke(label, fn, want):
        q = copy.deepcopy(post36)
        nb = fn(q)
        errs = invariants(q, q.n if nb is None else nb, 0, 0)
        ok = any(want in e for e in errs)
        reported.append(ok)
        kit.check(ok, "L-K8 must-fail: %s is reported (%r in %s)" % (label, want, errs[:2]))
    h_multi = next(h for h in range(post36.hh_n) if len(post36.hh_members[h]) >= 2)
    i0 = post36.hh_members[h_multi][0]
    other_h = next(h for h in range(post36.hh_n) if h != h_multi and post36.hh_members[h])
    couple = next(i for i in range(post36.n) if post36.partner[i] >= 0)
    broke("a person count off by one", lambda q: q.n + 1, "persons")
    broke("a person in two households", lambda q: q.hh_members[other_h].append(i0), "in two households")
    broke("a member's hh_id wrong", lambda q: q.hh_id.__setitem__(i0, other_h), "has hh_id")
    broke("a member's weight off its household's", lambda q: q.weight.__setitem__(i0, q.weight[i0] + 1.0), "weight")
    broke("a person in no household", lambda q: q.hh_members[h_multi].remove(i0), "persons in households of")
    broke("a one-sided partner", lambda q: q.partner.__setitem__(q.partner[couple], -1), "partners")

    def double(q):
        q.hh_weight[h_multi] *= 2.0
        for j in q.hh_members[h_multi]:
            q.weight[j] = q.hh_weight[h_multi]
    broke("a prefecture total off", double, "prefecture")

    def empty_pref(q):
        code = q.hh_pref[h_multi]
        for h in range(q.hh_n):
            if q.hh_pref[h] == code:
                q.hh_weight[h] = 0.0
                for j in q.hh_members[h]:
                    q.weight[j] = 0.0
    broke("a prefecture's households all at weight 0", empty_pref, "prefecture")
    # L-K8b (§7.2): prefecture X with no household at all; and the mutant that loops over tot does not see it
    X = post36.hh_pref[0]
    Y = next(int(c) for c in post36.pref_codes if int(c) != X)

    def no_household(q):
        dead = [1 if q.hh_pref[q.hh_id[i]] == X else 0 for i in range(q.n)]
        q.remove_persons(dead)
        for h in range(q.hh_n):
            if q.hh_pref[h] == X:
                q.hh_pref[h] = Y
        return q.n
    q8 = copy.deepcopy(post36)
    n8 = no_household(q8)
    want8 = "prefecture %d:" % X
    errs8 = invariants(q8, n8, 0, 0)
    kit.check(any(e.startswith(want8) for e in errs8) and all(e.startswith(want8) for e in errs8) and X not in set(q8.hh_pref),
              "L-K8b must-fail: prefecture %d with no household is reported, and only it (%s)" % (X, errs8[:2]))
    src = inspect.getsource(checks.invariants)
    if "    for code in p.pref_pop:\n" not in src:
        kit.check(False, "L-K8b-m: invariants() no longer holds the line the mutant replaces")
    else:
        ns = dict(checks.__dict__)
        exec(compile(src.replace("    for code in p.pref_pop:\n", "    for code in tot:\n"), "<K8b mutant>", "exec"), ns)
        errs_m = ns["invariants"](q8, n8, 0, 0)
        kit.check(not any(e.startswith(want8) for e in errs_m),
                  "L-K8b-m: the mutant looping over tot misses prefecture %d (it reports %s), so L-K8b reads the loop" % (X, errs_m[:2]))
    # L-K9 (Python only, §7.1): draw_grade's selection at x = 1.0 falls back to NG - 1, and on the shares' grid it is the inline loop
    bad9 = []
    for a in range(101):
        for s in range(2):
            sh = LC.shares(post36, a, s)
            for x in (0.0, 0.5, 1.0 - 2.0 ** -53):
                acc = 0.0
                g0 = LC.NG - 1
                for g in range(LC.NG):
                    acc += sh[g]
                    if x < acc:
                        g0 = g
                        break
                if LC._grade_of(sh, x) != g0:
                    bad9.append((a, s, x))
    kit.check(LC._grade_of([0.2] * 5, 1.0) == LC.NG - 1 and not bad9,
              "L-K9: _grade_of at x = 1.0 is grade %d; on the grid it equals the inline loop; differing %s" % (LC.NG - 1, bad9[:3]))
    # L-K10 must-fail: a replay without one newborn's pid raises KeyError naming it, on the first month with a birth
    m = next((m for m in range(1, 37) if os.path.exists(os.path.join(dm.d, "m%02d_newborn.json" % m))
              and ps.load_newborns(dm.d, m, dm.kinds)), None)
    if m is None:
        kit.check(False, "L-K10: no month with a birth in the dump")
    else:
        q = dm.load("m%02d_pre" % m)
        rep = ps.load_newborns(dm.d, m, dm.kinds)
        gone = next(iter(rep))
        del rep[gone]
        q.replay = rep
        try:
            LC.stage(q)
            msg = "no error"
        except KeyError as e:
            msg = str(e)
        kit.check(str(gone) in msg, "L-K10 must-fail month %d: newborn pid %d without replayed fields raises: %s" % (m, gone, msg[:80]))
    # L-K11 (Python only): rel_slot is -1 for a person who is not a contact
    i1 = next(i for i in range(post36.n) if post36.contact_count(i) < ps.C)
    stranger = next(j for j in range(post36.n) if j != i1 and not ps.rel_has_contact(post36, i1, j))
    kit.check(ps.rel_slot(post36, i1, stranger) == -1,
              "L-K11: rel_slot(%d, %d) is -1 for a person who is not a contact" % (i1, stranger))
