# A diagnostic, not a parity row (LC_HH_PORT_PLAN §5): the Python life course and households run on a synthetic persons' state, with
# no oracle, so the port's code paths run before the dump arrives. What it shows:
# - the code runs;
# - the same seed gives the same digest twice;
# - a mid-stage save and restore gives the straight run's digest;
# - L-c's invariants hold every month.
# What it cannot show: equality with GDScript. people.gd's own month is not here, so the state is synthetic: drives, deficits, emotions,
# traits and incomes are keyed draws, and contacts come only from the family links.
#   python py/tests/smoke_lchh.py [n_per] [months]
import json
import os
import re
import shutil
import sys
import tempfile

from common import Kit, ROOT
from core import digest as state, keyed
from lchh import households as HH, life_course as LC, pstate as ps
from lchh.checks import invariants

STRIDE = {"1": 1, "0": 0, "K_MEM": 8, "REL.C": 12, "REL.NF": 2, "GRP.M": 3, "NT": 10, "ND": 10, "NE": 10, "ACT.NA": 14, "4": 4}


def registry():
    # people.gd's fields() and household_fields(), read from the source
    src = open(os.path.join(ROOT, "sim/modern/people/people.gd"), encoding="utf-8").read()
    body = src[src.index("func fields()"):src.index("func household_fields()")]
    fields = []
    for m in re.finditer(r'\["(\w+)", "(i64|i32|f64)", ([\w.]+), (-?[\d.]+), ([^\]]+)\]', body):
        fields.append([m.group(1), m.group(2), STRIDE[m.group(3)], float(m.group(4)), None])
    body2 = src[src.index("func household_fields()"):src.index("func per_person_arrays()")]
    hf = []
    for m in re.finditer(r'\["(\w+)", "(\w+)", "(i64|i32|f64)", (\d), (true|false)\]', body2):
        hf.append([m.group(1), m.group(2), m.group(3), int(m.group(4)), m.group(5) == "true"])
    extras = ["n", "month", "seed_v", "base_year", "hh_n", "hh_members", "next_k", "life_log", "lc_births", "lc_dying", "lc_t22b",
              "lc_c_band", "groups", "pref_pop", "pref_codes"]
    return {"fields": fields, "household_fields": hf, "extras": extras}


def start_state(seed, n_per):
    reg = registry()
    spec = json.load(open(os.path.join(ROOT, "data/modern/people/jpn_people_2024.json"), encoding="utf-8"))
    hh_spec = json.load(open(os.path.join(ROOT, "data/modern/people/jpn_households_2024.json"), encoding="utf-8"))
    prefs = json.load(open(os.path.join(ROOT, "data/modern/polity/jpn_prefectures.json"), encoding="utf-8"))["prefectures"]
    tree = {}
    for f in reg["fields"]:
        tree[f[0]] = []
    for h in reg["household_fields"]:
        tree[h[0]] = list(LC_INIT.get(h[0], []))
    codes = sorted(prefs)
    cohort = []
    for a in range(ps.AGES):
        for s in range(2):
            cohort.append(1.0e6 * (1.0 - a / 120.0) * (0.98 if s == 0 else 1.0))
    tree["cohort"] = cohort
    tree.update({"n": 0, "month": 0, "seed_v": seed, "base_year": 2024, "hh_n": 0, "hh_members": [], "next_k": {}, "life_log": [],
                 "lc_births": [], "lc_dying": [], "lc_t22b": {}, "lc_c_band": 0, "groups": [],
                 "pref_pop": {int(c): float(prefs[c]["pop_thousand"]) * 1000.0 for c in codes}, "pref_codes": codes})
    p = ps.P(reg, spec, hh_spec, tree)
    HH.build_start(p, n_per)
    _people_draws(p, range(p.n))
    LC.start(p)
    HH.link_family(p)
    _contacts(p)
    p.reweight(None, True)
    LC.solve_c(p)
    return p


LC_INIT = {"lc_expected": [0.0] * 8, "lc_deaths": [0] * 8}


def _people_draws(p, idx):
    # The synthetic stand-in for people.gd's draws: keyed values in the ranges the life course reads
    for i in idx:
        for d in range(ps.ND):
            p.dw[i * ps.ND + d] = 0.05 + 0.2 * p.u("smoke_dw", i, d)
            p.dd[i * ps.ND + d] = p.u("smoke_dd", i, d)
        for e in range(ps.NE):
            p.emo[i * ps.NE + e] = p.u("smoke_emo", i, e)
        for t in range(ps.NT):
            p.traits[i * ps.NT + t] = 0.02 + 0.96 * p.u("smoke_tr", i, t)
        p.income[i] = 0.0 if p.age[i] < 18 else 40.0 * p.u("smoke_inc", i)
        p.employment[i] = ps.EMP_STUDENT if 15 <= p.age[i] < 22 else (ps.EMP_RETIRED if p.age[i] >= 65 else ps.EMP_REGULAR)


def _contacts(p):
    # Friends inside the prefecture, so that partnering's two-step meeting has singles to find (REL.build is people.gd's)
    by = {}
    for i in range(p.n):
        by.setdefault(p.pref[i], []).append(i)
    for i in range(p.n):
        pool = by[p.pref[i]]
        for c in range(4):
            j = pool[keyed.below(len(pool), p.seed_v, "smoke_friend", p.pid[i] & ps.PID_LOW, c, 0)]
            if j != i and not ps.rel_has_contact(p, i, j) and ps.rel_add(p, i, j, 1):
                if not ps.rel_add(p, j, i, 1):
                    ps.rel_unlink(p, i, j)


def _kinds(rows):
    out = {}
    for r in rows:
        out[r[2]] = out.get(r[2], 0) + 1
    return out


def year_part(p):
    # people._year's life-course calls (people.gd:1440-1463) on the persons whose month it is
    for i in range(p.n):
        if p.month % 12 == int(p.pid[i] % 12):
            if LC.dies(p, i):
                continue
            p.age[i] += 1
            LC.year_turn(p, i)


def run(seed, n_per, months, kit, save_at=None, tmp=None):
    p = start_state(seed, n_per)
    errs = invariants(p, p.n, 0, 0)
    kit.check(not errs, "smoke seed %d start: %d persons, %d households, invariants %s" % (seed, p.n, p.hh_n, errs[:3]))
    digests = [p.digest()[0]]
    for m in range(1, months + 1):
        year_part(p)
        n0 = p.n
        deaths = len(set(p.lc_dying))
        nlog = len(p.life_log)
        LC.grade_birthday(p)
        LC.month(p)
        births = sum(1 for r in p.life_log[nlog:] if r[2] == "birth")
        _people_draws(p, range(n0 - deaths, p.n))
        if save_at == m:
            d = os.path.join(tmp, "mid")
            p.save(d)
            p = ps.P(p.reg, p.spec, p.hh_spec, state.load(d, as_lists=True))
        p.reweight(None)
        LC.quartile_cuts(p)
        errs = invariants(p, n0, deaths, births)
        kit.check(not errs, "smoke seed %d month %d: n %d, deaths %d, births %d, events %s, invariants %s" % (
            seed, m, p.n, deaths, births, _kinds(p.life_log[nlog:]), errs[:3]))
        p.month += 1
        digests.append(p.digest()[0])
    return digests


def main():
    n_per = int(sys.argv[1]) if len(sys.argv) > 1 else 20
    months = int(sys.argv[2]) if len(sys.argv) > 2 else 13
    kit = Kit("py/tests/smoke_lchh.py")
    tmp = tempfile.mkdtemp()
    try:
        a = run(1, n_per, months, kit)
        b = run(1, n_per, months, kit)
        kit.check(a == b, "smoke determinism: seed 1 twice, months 0-%d, digests equal (last %s)" % (months, a[-1][:16]))
        c = run(1, n_per, months, kit, save_at=6, tmp=tmp)
        kit.check(a == c, "smoke save/restore: saved mid-stage at month 6, digests equal to the straight run")
        d = run(7, n_per, months, kit)
        kit.check(a[-1] != d[-1], "smoke seeds differ: seed 7's last digest is not seed 1's")
    finally:
        shutil.rmtree(tmp)
    kit.finish()


if __name__ == "__main__":
    main()
