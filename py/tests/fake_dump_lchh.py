# A dump in oracle_dump_lc_hh.gd's layout, written by the Python port itself from the smoke run's synthetic state. It checks
# run_lchh.py's plumbing and that its must-fail rows can fail, before the oracle's dump exists. It proves nothing about GDScript:
# every value in it is Python's
#   python py/tests/fake_dump_lchh.py <out dir> [n_per] [months]
import json
import os
import struct
import sys

import common  # noqa: F401  (the path to py/)
from core import digest as state, keyed
from lchh import gdsort, households as HH, life_course as LC, pstate as ps
import smoke_lchh as sm
from run_lchh_k import in_group, k6_prepare


def B(x):
    return str(struct.unpack("<q", struct.pack("<d", x))[0])


def snap(p, d, whole=True):
    hs = p.hashes()
    with open(d + ".sha.txt", "w", encoding="utf-8") as f:
        f.write("".join("%s %s\n" % (n, hs[n]) for n in sorted(hs)))
    if whole:
        p.save(d)


def main():
    out = sys.argv[1]
    n_per = int(sys.argv[2]) if len(sys.argv) > 2 else 10
    months = int(sys.argv[3]) if len(sys.argv) > 3 else 13
    os.makedirs(os.path.join(out, "start"), exist_ok=True)
    seed = 1
    reg = sm.registry()
    reg["consts"] = {"C": ps.C, "M": ps.M, "NT": ps.NT, "NE": ps.NE, "ND": ps.ND, "AGES": ps.AGES, "SEXES": ps.SEXES,
                     "K_FAMILY": ps.K_FAMILY, "TRUST0": list(ps.TRUST0), "MOVE_KEEP": ps.MOVE_KEEP, "AGE_BANDS": list(ps.AGE_BANDS),
                     "EMOTIONS": list(ps.EMOTIONS), "D_FAMILY": ps.D_FAMILY, "D_AUTONOMY": ps.D_AUTONOMY, "D_SECURITY": ps.D_SECURITY,
                     "GRADE_POOR": ps.GRADE_POOR, "GRADE_LIMITED": ps.GRADE_LIMITED, "EMP_STUDENT": ps.EMP_STUDENT,
                     "EMP_RETIRED": ps.EMP_RETIRED}
    lcw = list(ps_lc_writes())
    reg["lc_writes"] = lcw
    with open(os.path.join(out, "registry.json"), "w", encoding="utf-8") as f:
        json.dump(reg, f)
    # the start, cut by cut, as oracle_dump_lc_hh.gd's _create_hooked
    p0 = sm.start_state(seed, n_per)
    os.makedirs(os.path.join(out, "spec"), exist_ok=True)
    files = [0]
    with open(os.path.join(out, "spec", "state.json"), "w", encoding="utf-8") as f:
        json.dump({"spec": state.enc(p0.spec, os.path.join(out, "spec"), files),
                   "hh_spec": state.enc(p0.hh_spec, os.path.join(out, "spec"), files)}, f)
    with open(os.path.join(out, "start", "n_per.json"), "w") as f:
        json.dump({"n_per": n_per}, f)
    p = _start_cuts(seed, n_per, out)
    grid = {"seed": seed, "keyed": [], "pid": [], "sort": []}
    for t in ("death", "lc_partner", "hhtype"):
        for a in (-1, 0, 13, 140737488355327):
            grid["keyed"].append([t, a, B(keyed.u(seed, t, a, 7, 3)), keyed.below(17, seed, t, a, 7, 3), B(keyed.normal(seed, t, a, 7, 3))])
    grid["pid"].append([13, 2024, 1, 5, str(ps.pid(seed, 13, 2024, 1, 5))])
    for sz in (0, 1, 17, 64):
        keys = [float(keyed.below(3, seed, "sortgrid", sz, 3, i)) for i in range(sz)]
        rows = [[k, 0.0, i] for i, k in enumerate(keys)]
        gdsort.sort_custom(rows, LC._row_less)
        grid["sort"].append({"keys": [B(k) for k in keys], "perm": [r[2] for r in rows]})
    with open(os.path.join(out, "grid.json"), "w") as f:
        json.dump(grid, f)
    hook = [[0, "a", "a", "b", "b"]]
    for m in range(1, months + 1):
        y = []
        for i in range(p.n):
            if p.month % 12 == int(p.pid[i] % 12):
                e = LC.equivalized(p, i)
                qk = LC.quartile(p, i)
                q = LC.h_death(p, p.age[i], p.sex[i], p.health[i], qk)
                died = LC.dies(p, i)
                y.append({"call": "dies", "pid": str(p.pid[i]), "age": p.age[i], "sex": p.sex[i], "health": p.health[i], "e": B(e),
                          "quartile": qk, "q": B(q), "died": died})
                if died:
                    continue
                p.age[i] += 1
                im0, ik0 = p.intends_marry[i], p.intended_kids[i]
                LC.year_turn(p, i)
                y.append({"call": "year_turn", "pid": str(p.pid[i]), "age": p.age[i], "sex": p.sex[i], "births_n": p.births_n[i],
                          "intends_marry0": im0, "intended_kids0": ik0, "intends_marry": p.intends_marry[i], "intended_kids": p.intended_kids[i]})
        tag = os.path.join(out, "m%02d" % m)
        snap(p, tag + "_pre")
        with open(tag + "_y.json", "w") as f:
            json.dump(y, f)
        pre_pids = set(p.pid[:p.n])
        LC.grade_birthday(p)
        n_before = p.n
        LC.month(p)
        # the newborns' people-owned fields: the smoke's synthetic draws stand in for draw_person / finish_person
        nbs = [i for i in range(p.n) if p.pid[i] not in pre_pids]
        sm._people_draws(p, nbs)
        p.reweight(None)
        with open(tag + "_sort.json", "w") as f:
            json.dump([[r[2] for r in rows] for rows in LC.quartile_rows(p)], f)
        LC.quartile_cuts(p)
        snap(p, tag + "_post", whole=m in (1, 6, 12))
        rows = []
        for i in nbs:
            row = {"pid": str(p.pid[i])}
            for fl in reg["fields"]:
                if fl[2] > 0 and fl[0] not in lcw:
                    st = fl[2]
                    vals = getattr(p, fl[0])[i * st:(i + 1) * st]
                    row[fl[0]] = [B(v) if fl[1] == "f64" else str(v) for v in vals]
            rows.append(row)
        with open(tag + "_newborn.json", "w") as f:
            json.dump({"n_pre": n_before, "rows": rows}, f)
        hook.append([m, "a", "a", "b", "b"])
        p.month += 1
        # people.gd's month stands in: next month's incomes and emotions redrawn
        for i in range(p.n):
            p.income[i] = 0.0 if p.age[i] < 18 else 40.0 * keyed.u(seed, "smoke_inc2", p.pid[i] & ps.PID_LOW, p.month, 0)
    _cases(p, out)
    with open(os.path.join(out, "hook.json"), "w") as f:
        json.dump(hook, f)
    print("fake dump written to %s: %d months, n %d" % (out, months, p.n))


def ps_lc_writes():
    return ["pid", "pref", "k_in_pref", "age", "sex", "hh_kind", "hh_size", "health", "weight", "contact_idx", "contact_kind",
            "contact_last", "contact_trust", "member_of"]


def _start_cuts(seed, n_per, out):
    # start_state runs the cuts in one go; here each cut's pre and post is written, from a fresh build
    p = sm.start_state(seed, n_per)
    q = ps.P(p.reg, p.spec, p.hh_spec, _empty_tree(p))
    S = os.path.join(out, "start")
    snap(q, S + "/hh_pre")
    HH.build_start(q, n_per)
    snap(q, S + "/hh_post")
    sm._people_draws(q, range(q.n))
    snap(q, S + "/lc_pre")
    LC.start(q)
    snap(q, S + "/lc_post")
    snap(q, S + "/link_pre")
    HH.link_family(q)
    snap(q, S + "/link_post")
    sm._contacts(q)
    snap(q, S + "/rake_pre")
    q.reweight(None, True)
    LC.solve_c(q)
    snap(q, S + "/rake_post")
    return q


def _empty_tree(p):
    t = {}
    for f in p.reg["fields"]:
        t[f[0]] = [] if f[0] != "cohort" else list(p.cohort)
    for h in p.reg["household_fields"]:
        t[h[0]] = list(sm.LC_INIT.get(h[0], []))
    t.update({"n": 0, "month": 0, "seed_v": p.seed_v, "base_year": p.base_year, "hh_n": 0, "hh_members": [], "next_k": {},
              "life_log": [], "lc_births": [], "lc_dying": [], "lc_t22b": {}, "lc_c_band": 0, "groups": [], "pref_pop": dict(p.pref_pop),
              "pref_codes": list(p.pref_codes)})
    return t



def _cases(p, out):
    # oracle_dump_lc_hh.gd's _cases, in Python (LC_HH_PORT_PLAN §7). Synthetic groups first: GRP.seed_groups is people.gd's, and
    # without memberships K1's group leave has nothing to leave
    for i in range(min(40, p.n)):
        p.groups.append({"pref": p.pref[i], "members": 1, "weight": p.weight[i], "kind": 0, "status": 0})
        p.member_of[i * ps.M] = len(p.groups) - 1
    K = os.path.join(out, "k")
    os.makedirs(K, exist_ok=True)

    def bits(d):
        return {k: (B(v) if isinstance(v, float) else str(v)) for k, v in d.items()}
    json.dump({"kish": bits(HH.kish(p)), "type_shares": bits(HH.type_shares(p))}, open(os.path.join(K, "k7.json"), "w"))
    al = p.hh_spec["alone_share_by_band"]["value"]["bands"]
    ze = lambda a, _s: 0.0 if a % 2 == 0 else 1.0
    json.dump({"band_index": [HH._band_index(10, al), HH._band_index(90, al)],
               "draw_age": [list(HH._draw_age(p, x, [0, 1], 15, ps.AGES - 1, ze)) for x in (0.5, 1.0)],
               "pick": HH._pick(HH._v(p, "type_shares"), HH.TYPES, 1.0),
               "h_death": [B(LC.h_death(p, a, s, 4, 0)) for a in range(111) for s in range(2)]}, open(os.path.join(K, "k5.json"), "w"))
    arrs = json.load(open(os.path.join(common.ROOT, "tools/py/lchh_k4_sort.json")))["arrays"]
    perms = []
    for e in arrs:
        r = [[float(v), 0.0, i] for i, v in enumerate(e["keys"])]
        gdsort.sort_custom(r, LC._row_less)
        perms.append([x[2] for x in r])
    json.dump(perms, open(os.path.join(K, "k4.json"), "w"))
    found = {"a": -1, "b": -1, "c": -1, "d": -1}
    used = set()
    for i in range(p.n):
        h = p.hh_id[i]
        if h in used:
            continue
        if p.hh_type[h] == LC.INSTITUTION:
            kind = "d"
        elif p.hh_role[i] <= ps.R_PARTNER:
            kind = "a" if len(p.hh_members[h]) >= 2 and in_group(p, h) else ""
        elif p.partner[i] >= 0 and p.hh_id[p.partner[i]] == h:
            kind = "b"
        else:
            kind = "c"
        if kind and found[kind] < 0:
            found[kind] = i
            used.add(h)
    snap(p, os.path.join(K, "k1_pre"))
    mv = []
    for kind in "abcd":
        i2 = found[kind]
        if i2 < 0:
            mv.append([kind, "-1", -1, []])
            continue
        dest = next(int(c) for c in p.pref_codes if int(c) != p.pref[i2])
        mv.append([kind, str(p.pid[i2]), dest, [str(p.pid[j]) for j in LC.move_household(p, i2, dest, "job")]])
    snap(p, os.path.join(K, "k1_post"))
    json.dump(mv, open(os.path.join(K, "k1.json"), "w"))
    snap(p, os.path.join(K, "k2_pre"))
    dc = []
    died = []
    for i in range(p.n):
        d = LC.dies(p, i)
        dc.append([str(p.pid[i]), d])
        if d:
            died.append(i)
    dc += [[str(p.pid[i]), LC.dies(p, i)] for i in died]
    json.dump(dc, open(os.path.join(K, "k2.json"), "w"))
    pre_pids = set(p.pid[:p.n])
    n_pre = p.n
    LC.grade_birthday(p)
    LC.month(p)
    nbs = [i for i in range(p.n) if p.pid[i] not in pre_pids]
    sm._people_draws(p, nbs)
    p.reweight(None)
    json.dump([[r[2] for r in rows] for rows in LC.quartile_rows(p)], open(os.path.join(K, "k2_sort.json"), "w"))
    LC.quartile_cuts(p)
    snap(p, os.path.join(K, "k2_post"))
    lcw = ps_lc_writes()
    rows = []
    for i in nbs:
        row = {"pid": str(p.pid[i])}
        for fl in p.reg["fields"]:
            if fl[2] > 0 and fl[0] not in lcw:
                st = fl[2]
                row[fl[0]] = [B(v) if fl[1] == "f64" else str(v) for v in getattr(p, fl[0])[i * st:(i + 1) * st]]
        rows.append(row)
    json.dump({"n_pre": n_pre, "rows": rows}, open(os.path.join(K, "k2_newborn.json"), "w"))
    snap(p, os.path.join(K, "k3_pre"))
    for i in range(p.n):
        if p.age[i] < 10:
            p.age[i] = 10
    LC.quartile_cuts(p)
    snap(p, os.path.join(K, "k3_post"))
    snap(p, os.path.join(K, "k6_pre"))
    k6_prepare(p)
    HH._scale_cell(p, [0, 0, 0, 1.0], lambda h: HH._private(p, h) and p.hh_type[h] == ps.HK_SINGLE)
    HH.link_family(p)
    ms = p.hh_spec["mean_size_by_prefecture"]["value"]
    old = ms["13"]
    ms["13"] = 0.0
    HH._tilt_sizes(p)
    ms["13"] = old
    snap(p, os.path.join(K, "k6_post"))


if __name__ == "__main__":
    main()
