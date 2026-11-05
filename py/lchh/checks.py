# L-c's invariants (LC_HH_PORT_PLAN §5), shared by the rows' runner and the smoke run
from . import pstate as ps


def invariants(p, n_before, deaths, births):
    errs = []
    if p.n != n_before - deaths + births:
        errs.append("persons %d != %d - %d + %d" % (p.n, n_before, deaths, births))
    seen = {}
    for h in range(p.hh_n):
        for i in p.hh_members[h]:
            if i in seen:
                errs.append("person %d in two households" % i)
            seen[i] = h
            if p.hh_id[i] != h:
                errs.append("member %d of %d has hh_id %d" % (i, h, p.hh_id[i]))
            if p.weight[i] != p.hh_weight[h]:
                errs.append("member %d weight" % i)
    if len(seen) != p.n:
        errs.append("%d persons in households of %d" % (len(seen), p.n))
    for i in range(p.n):
        j = p.partner[i]
        if j >= 0 and (p.partner[j] != i or p.sex[j] == p.sex[i] or p.hh_id[j] != p.hh_id[i]):
            errs.append("partners %d %d" % (i, j))
    _, scale = p.cell_target(None)
    tot = {}
    terms = {}
    for h in range(p.hh_n):
        x = p.hh_weight[h] * float(len(p.hh_members[h]))
        tot[p.hh_pref[h]] = tot.get(p.hh_pref[h], 0.0) + x
        terms[p.hh_pref[h]] = terms.get(p.hh_pref[h], 0.0) + abs(x)
    # Every prefecture of pref_pop (AMENDED §7.1): one with no household, or all at weight 0, is reported. Why not only those in tot:
    # an emptied prefecture never entered it
    for code in p.pref_pop:
        v = tot.get(code, 0.0)
        terms.setdefault(code, 0.0)
        nt = sum(1 for h in range(p.hh_n) if p.hh_pref[h] == code)
        bound = 2.0 * nt * 2.0 ** -53 * terms[code] + 2.0 * 2.0 ** -53 * p.pref_pop[code] * scale
        if abs(v - p.pref_pop[code] * scale) > bound:
            errs.append("prefecture %d: %r vs %r" % (code, v, p.pref_pop[code] * scale))
    return errs
