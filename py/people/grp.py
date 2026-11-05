# The twin of sim/modern/people/groups.gd (REL_PORT_PLAN §1), in its names, loops and operation order
from .deps import gd
from . import rel as REL

KINDS = ["union", "community", "circle", "association", "party_group", "movement"]
G_UNION = 0
G_COMMUNITY = 1
G_CIRCLE = 2
G_ASSOCIATION = 3
G_PARTY = 4
G_MOVEMENT = 5
PURPOSE = [1, 2, 6, 5, 9, 9]
DUES = [0.15, 0.03, 0.1, 0.1, 0.05, 0.0]
M = 3
RELATION = {"union|association": -0.3, "union|party_group": 0.3, "movement|party_group": -0.5, "movement|union": 0.3,
            "movement|community": 0.1, "circle|community": 0.3, "association|party_group": 0.2}
PETITION_SHARE = 0.05
PETITION_DISCONTENT = 0.5
PETITION_EVERY = 12
WAGE_DEMAND_DEFICIT = 0.5
DISSOLVE_BELOW = 3
DISSOLVE_MONTHS = 6
UNION_COVER = 1.3
START_RATES = {"union": 0.161, "community": 0.30, "circle": 0.20, "association": 0.10, "party_group": 0.01}


def kind_id(name):
    return KINDS.index(name) if name in KINDS else -1


def classes(p, i):
    a = p.age[i]
    return {"age_band": "child" if a < 15 else ("young" if a < 30 else ("middle" if a < 60 else "older")),
            "employment": p.EMPLOYMENT[p.employment[i]],
            "income_tercile": "low" if p.rank[i] < 0.3333 else ("mid" if p.rank[i] < 0.6667 else "high"),
            "education": p.EDUCATION[p.education[i]],
            "prefecture": str(p.pref[i])}


def seed_groups(p):
    for code in p.pref_codes:
        for kind in range(5):
            _new_group(p, kind, int(code), -1)
    for i in range(p.n):
        if p.age[i] < 15:
            continue
        draw_cover(p, i, 0)
        for kind in range(5):
            rate = float(START_RATES[KINDS[kind]])
            if kind == G_UNION:
                if p.union_cover[i] == 0:
                    continue
                rate = 1.0 / UNION_COVER
            if kind == G_COMMUNITY and p.age[i] < 25:
                rate *= 0.3
            if kind == G_CIRCLE:
                rate = 0.1 + 0.3 * p.pref_leisure[i]
            if kind == G_ASSOCIATION and p.education[i] < 2:
                rate *= 0.3
            if kind == G_PARTY:
                rate *= 0.5 + p.pol_interest[i]
            if p.u("groupstart", i, kind) < rate:
                g = find_group(p, kind, p.pref[i])
                if g >= 0:
                    join(p, i, g)


def union_rate(p, i):
    if p.employment[i] == p.EMP_REGULAR:
        return float(START_RATES["union"])
    return 0.5 * float(START_RATES["union"]) if p.employment[i] == p.EMP_NONREGULAR else 0.0


def draw_cover(p, i, k):
    p.union_cover[i] = 1 if p.u("unioncover", i, k) < UNION_COVER * union_rate(p, i) else 0


def new_job(p, i):
    for m in range(M):
        g = p.member_of[i * M + m]
        if g >= 0 and int(p.groups[g]["kind"]) == G_UNION:
            leave(p, i, g)
    draw_cover(p, i, p.month + 1)
    if p.union_cover[i] == 1 and memberships(p, i) < M and p.u("unionhire", i, p.month) < 1.0 / UNION_COVER:
        gu = find_group(p, G_UNION, p.pref[i])
        if gu >= 0:
            join(p, i, gu)


def _new_group(p, kind, pref, founder):
    gid = len(p.groups)
    p.groups.append({"id": gid, "kind": kind, "pref": pref, "purpose": PURPOSE[kind], "members": 0, "weight": 0.0, "resources": 0.0,
                     "influence": 0.0, "trust_mean": 0.0, "discontent_mean": 0.0, "deficit_mean": 0.0, "founded": p.month,
                     "founder": founder, "status": 0, "small_months": 0, "actions": 0})
    return gid


def find_group(p, kind, pref):
    for g in p.groups:
        if int(g["kind"]) == kind and int(g["pref"]) == pref and int(g["status"]) == 0:
            return int(g["id"])
    return -1


def is_member(p, i, gid):
    for m in range(M):
        if p.member_of[i * M + m] == gid:
            return True
    return False


def memberships(p, i):
    k = 0
    for m in range(M):
        if p.member_of[i * M + m] >= 0:
            k += 1
    return k


def clear_cover(p, i):
    p.union_cover[i] = 0


def join(p, i, gid):
    if is_member(p, i, gid):
        return False
    for m in range(M):
        if p.member_of[i * M + m] < 0:
            p.member_of[i * M + m] = gid
            g = p.groups[gid]
            g["members"] = int(g["members"]) + 1
            g["weight"] = float(g["weight"]) + p.weight[i]
            return True
    return False


def leave(p, i, gid):
    for m in range(M):
        if p.member_of[i * M + m] == gid:
            p.member_of[i * M + m] = -1
            g = p.groups[gid]
            g["members"] = int(g["members"]) - 1
            g["weight"] = float(g["weight"]) - p.weight[i]


def refresh_weights(p):
    for g in p.groups:
        g["weight"] = 0.0
    for i in range(p.n):
        for m in range(M):
            gid = p.member_of[i * M + m]
            if gid >= 0:
                p.groups[gid]["weight"] = float(p.groups[gid]["weight"]) + p.weight[i]
    for g2 in p.groups:
        if int(g2["status"]) == 0:
            g2["influence"] = float(g2["weight"]) / 1e6 * (1.0 + gd.minf(1.0, float(g2["resources"]) / 100.0))


def pick_group(p, i):
    order = []
    mv = find_group(p, G_MOVEMENT, p.pref[i])
    if mv >= 0 and p.emotion(i, "discontent") > 0.4:
        order.append(mv)
    if (p.employment[i] == p.EMP_REGULAR or p.employment[i] == p.EMP_NONREGULAR) and p.union_cover[i] == 1:
        order.append(find_group(p, G_UNION, p.pref[i]))
    if p.pref_social[i] > 0.5:
        order.append(find_group(p, G_CIRCLE, p.pref[i]))
    if p.education[i] == 2:
        order.append(find_group(p, G_ASSOCIATION, p.pref[i]))
    if p.pol_interest[i] > 0.5:
        order.append(find_group(p, G_PARTY, p.pref[i]))
    order.append(find_group(p, G_COMMUNITY, p.pref[i]))
    for g in order:
        if g >= 0 and not is_member(p, i, g):
            return g
    return -1


def discontented_contacts(p, i):
    k = 0
    for c in range(REL.C):
        j = p.contact_idx[i * REL.C + c]
        if j >= 0 and p.emotion(j, "discontent") > 0.5:
            k += 1
    return k


def found_movement(p, i, counts):
    if find_group(p, G_MOVEMENT, p.pref[i]) >= 0:
        return -1
    gid = _new_group(p, G_MOVEMENT, p.pref[i], i)
    join(p, i, gid)
    for c in range(REL.C):
        j = p.contact_idx[i * REL.C + c]
        if j >= 0 and p.emotion(j, "discontent") > 0.5 and memberships(p, j) < M:
            join(p, j, gid)
    p.count_kind(counts, "movement_founded", i, float(p.groups[gid]["members"]),
                 "a discontented person with discontented contacts (T: change deficit and 2+ such contacts)")
    p.group_log.append({"month": p.month, "group": gid, "kind": "founded", "pref": p.pref[i], "members": int(p.groups[gid]["members"]),
                        "why": "founder's discontent %.2f, %d discontented contacts" % (p.emotion(i, "discontent"), discontented_contacts(p, i))})
    return gid


def step(p, counts):
    G = len(p.groups)
    sum_t = [0.0] * G
    sum_d = [0.0] * G
    sum_def = [0.0] * G
    cnt = [0] * G
    pref_n = {}
    for i in range(p.n):
        pref_n[p.pref[i]] = int(pref_n.get(p.pref[i], 0)) + 1
        for m in range(M):
            gid = p.member_of[i * M + m]
            if gid < 0:
                continue
            g = p.groups[gid]
            kind = int(g["kind"])
            due = DUES[kind]
            if p.assets[i] >= due:
                p.add_assets(i, -due)
                g["resources"] = float(g["resources"]) + due
            sum_t[gid] += p.trait_of(i, "trust_in_others")
            sum_d[gid] += p.emotion(i, "discontent")
            sum_def[gid] += p.dd[i * 10 + int(g["purpose"])]
            cnt[gid] += 1
            for c in range(REL.C):
                j = p.contact_idx[i * REL.C + c]
                if j >= 0 and is_member(p, j, gid):
                    REL.raise_trust(p, i, c, 1.0)
    for g in p.groups:
        if int(g["status"]) != 0:
            continue
        gid = int(g["id"])
        n = cnt[gid]
        g["trust_mean"] = sum_t[gid] / n if n > 0 else 0.0
        g["discontent_mean"] = sum_d[gid] / n if n > 0 else 0.0
        g["deficit_mean"] = sum_def[gid] / n if n > 0 else 0.0
        kind = int(g["kind"])
        share = float(n) / gd.maxf(1.0, float(pref_n.get(int(g["pref"]), 1)))
        if (kind == G_MOVEMENT and share >= PETITION_SHARE and float(g["discontent_mean"]) >= PETITION_DISCONTENT
                and p.month - int(g.get("last_petition", -PETITION_EVERY)) >= PETITION_EVERY):
            g["last_petition"] = p.month
            g["actions"] = int(g["actions"]) + 1
            p.group_log.append({"month": p.month, "group": gid, "kind": "petition", "pref": int(g["pref"]), "members": n,
                                "why": "members %.1f%% of the prefecture's sample, discontent %.2f (T thresholds 5%%, 0.5)" % (100.0 * share, float(g["discontent_mean"]))})
            p.count_kind(counts, "petition", 0, float(n), "a movement above the size and discontent lines (T)")
        if kind == G_UNION and n > 0 and float(g["deficit_mean"]) >= WAGE_DEMAND_DEFICIT:
            g["actions"] = int(g["actions"]) + 1
            p.group_log.append({"month": p.month, "group": gid, "kind": "wage_demand", "pref": int(g["pref"]), "members": n,
                                "why": "members' economic-security deficit %.2f (T line 0.5)" % float(g["deficit_mean"])})
            p.count_kind(counts, "wage_demand", 0, float(n), "a union whose members are pressed (T)")
        if kind == G_MOVEMENT:
            g["small_months"] = int(g["small_months"]) + 1 if n < DISSOLVE_BELOW else 0
            if int(g["small_months"]) >= DISSOLVE_MONTHS:
                g["status"] = 1
                for i in range(p.n):
                    if is_member(p, i, gid):
                        leave(p, i, gid)
                p.group_log.append({"month": p.month, "group": gid, "kind": "dissolved", "pref": int(g["pref"]), "members": n,
                                    "why": "fewer than %d members for %d months" % (DISSOLVE_BELOW, DISSOLVE_MONTHS)})
    if not p.group_influence:
        return
    for i in range(p.n):
        for m in range(M):
            gid = p.member_of[i * M + m]
            if gid >= 0 and int(p.groups[gid]["kind"]) == G_MOVEMENT:
                k = i * p.NE + p.EMOTIONS.index("discontent")
                p.pull_emotion(k, float(p.groups[gid]["discontent_mean"]), 0.05)


def relation(kind_a, kind_b):
    if kind_a == kind_b:
        return 0.5
    k1 = KINDS[gd.mini(kind_a, kind_b)] + "|" + KINDS[gd.maxi(kind_a, kind_b)]
    k2 = KINDS[gd.maxi(kind_a, kind_b)] + "|" + KINDS[gd.mini(kind_a, kind_b)]
    return float(RELATION.get(k1, RELATION.get(k2, 0.0)))


def summary_by_class(p, class_key, values):
    by = {}
    for i in range(p.n):
        c = str(classes(p, i)[class_key])
        if c not in by:
            by[c] = []
        by[c].append(i)
    out = {}
    for c in sorted(by.keys()):
        w = 0.0
        for i in by[c]:
            w += p.weight[i]
        out[c] = {"persons": len(by[c]), "weight": w, "p10_p50_p90": p.quantiles(values, by[c])}
    return out


def group_summary(p):
    out = []
    for g in p.groups:
        if int(g["status"]) == 0 and int(g["members"]) > 0:
            out.append({"id": int(g["id"]), "kind": KINDS[int(g["kind"])], "pref": int(g["pref"]), "members": int(g["members"]),
                        "weight": float(g["weight"]), "resources": float(g["resources"]), "discontent_mean": float(g["discontent_mean"]),
                        "actions": int(g["actions"])})
    return out
