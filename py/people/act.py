# The twin of sim/modern/people/actions.gd (REL_PORT_PLAN §1), in its names, loops and operation order
import math

from .deps import detmath, gd

ACTIONS = ["keep_course", "search_job", "change_job", "train", "thrift", "splurge", "rest", "socialize", "support_family", "move",
           "pursue_dream", "join_group", "found_group", "leave_group"]
NA = 14
A_KEEP = 0
A_SEARCH = 1
A_CHANGE = 2
A_TRAIN = 3
A_THRIFT = 4
A_SPLURGE = 5
A_REST = 6
A_SOCIALIZE = 7
A_SUPPORT = 8
A_MOVE = 9
A_DREAM = 10
A_JOIN = 11
A_FOUND = 12
A_LEAVE = 13
TAU = 0.03
TRAIN_COST = 3.0
MOVE_COST = 50.0
SOCIAL_COST = 1.0
SUPPORT_COST = 2.0
CHANGE_P = 0.25
SEARCH_BOOST = 1.6
NO_SEARCH = 0.6


def dream_drive(p, k):
    return [p.D_AUTONOMY, p.D_FAMILY, p.D_GROWTH, p.D_SECURITY, p.D_CONTRIBUTION, p.D_RECOGNITION, p.D_SECURITY, p.D_CHANGE][k]


def candidates(p, i):
    out = [A_KEEP]
    a = p.age[i]
    e = p.employment[i]
    if a < 15:
        return [A_KEEP, A_REST, A_SOCIALIZE]
    if e == p.EMP_UNEMPLOYED:
        out.append(A_SEARCH)
    if e == p.EMP_REGULAR or e == p.EMP_NONREGULAR:
        out.append(A_CHANGE)
    if a < 60 and e != p.EMP_RETIRED:
        out.append(A_TRAIN)
    out.extend([A_THRIFT, A_SPLURGE, A_REST, A_SOCIALIZE, A_SUPPORT])
    if a >= 18 and a < 60:
        out.append(A_MOVE)
    if p.dream_kind[i] >= 0 and p.dream_status[i] == 0:
        out.append(A_DREAM)
    if a >= 18:
        out.extend([A_JOIN, A_FOUND, A_LEAVE])
    return out


def feasible(p, i, a):
    G = p.GRP
    if a == A_SEARCH:
        return "" if p.employment[i] == p.EMP_UNEMPLOYED else "not unemployed"
    if a == A_CHANGE:
        return "" if (p.employment[i] == p.EMP_REGULAR or p.employment[i] == p.EMP_NONREGULAR) else "no job to leave"
    if a == A_TRAIN:
        if p.assets[i] < TRAIN_COST:
            return "assets below the training cost"
        return "" if p.employment[i] != p.EMP_RETIRED else "retired"
    if a == A_SPLURGE:
        return "" if p.income[i] > 0.0 or p.assets[i] > 10.0 else "no money to spend"
    if a == A_SOCIALIZE:
        return "" if p.assets[i] >= SOCIAL_COST or p.age[i] < 15 else "no money for it"
    if a == A_SUPPORT:
        if p.hh_kind[i] == p.HK_SINGLE and p.age[i] > 60:
            return "no family household"
        return "" if p.income[i] > SUPPORT_COST else "no income to give"
    if a == A_MOVE:
        if p.assets[i] < MOVE_COST:
            return "assets below the moving cost"
        if p.households and p.move_reason(i) == "":
            return "no reason to move"
        return "" if p.age[i] >= 18 and p.age[i] < 60 else "age"
    if a == A_DREAM:
        return "" if (p.dream_kind[i] >= 0 and p.dream_status[i] == 0) else "no active dream"
    if a == A_JOIN:
        if G.memberships(p, i) >= G.M:
            return "no room for another membership"
        return "" if G.pick_group(p, i) >= 0 else "no group to join here"
    if a == A_FOUND:
        if G.find_group(p, G.G_MOVEMENT, p.pref[i]) >= 0:
            return "a movement exists here already"
        if G.memberships(p, i) >= G.M:
            return "no room for another membership"
        return "" if G.discontented_contacts(p, i) >= 2 else "fewer than two discontented contacts"
    if a == A_LEAVE:
        return "" if G.memberships(p, i) > 0 else "no membership to leave"
    return ""


def delta(p, i, a):
    d = [0.0] * 10
    e = p.employment[i]
    if a == A_SEARCH:
        d[p.D_SECURITY] = -0.45
        d[p.D_AUTONOMY] = -0.1
        d[p.D_RECOGNITION] = -0.1
    elif a == A_CHANGE:
        d[p.D_SECURITY] = -0.2 if e == p.EMP_NONREGULAR else -0.05
        d[p.D_RECOGNITION] = -0.15
        d[p.D_AUTONOMY] = -0.1
        d[p.D_BELONGING] = 0.05
    elif a == A_TRAIN:
        d[p.D_GROWTH] = -0.3
        d[p.D_SECURITY] = -0.15 * (0.5 + p.trait_of(i, "future_orientation"))
        d[p.D_ENJOYMENT] = 0.1
    elif a == A_THRIFT:
        d[p.D_SECURITY] = -0.15 * (1.0 + 4.0 * p.believed_cost_rise(i))
        d[p.D_ENJOYMENT] = 0.15
    elif a == A_SPLURGE:
        d[p.D_ENJOYMENT] = -0.3
        d[p.D_SECURITY] = 0.15
        d[p.D_RECOGNITION] = -0.05
    elif a == A_REST:
        d[p.D_ENJOYMENT] = -0.2
        d[p.D_SURVIVAL] = -0.05
        d[p.D_RECOGNITION] = 0.05
    elif a == A_SOCIALIZE:
        d[p.D_BELONGING] = -0.25 * (0.5 + p.pref_social[i])
        d[p.D_ENJOYMENT] = -0.1
    elif a == A_SUPPORT:
        d[p.D_FAMILY] = -0.3
        d[p.D_SECURITY] = 0.1
        d[p.D_CONTRIBUTION] = -0.1
    elif a == A_MOVE:
        d[p.D_SECURITY] = -0.25 if e == p.EMP_UNEMPLOYED else -0.08
        d[p.D_BELONGING] = 0.2
        d[p.D_AUTONOMY] = -0.05
    elif a == A_DREAM:
        d[dream_drive(p, p.dream_kind[i])] = -0.3 * p.dream_importance[i]
        d[p.D_ENJOYMENT] = 0.1
    elif a == A_JOIN:
        d[p.D_BELONGING] = -0.25
        d[p.D_CONTRIBUTION] = -0.1
        d[p.D_CHANGE] = -0.1 if p.emotion(i, "discontent") > 0.4 else 0.0
        d[p.D_ENJOYMENT] = 0.05
    elif a == A_FOUND:
        d[p.D_CHANGE] = -0.4
        d[p.D_RECOGNITION] = -0.15
        d[p.D_CONTRIBUTION] = -0.1
        d[p.D_ENJOYMENT] = 0.15
    elif a == A_LEAVE:
        d[p.D_ENJOYMENT] = -0.05
        d[p.D_BELONGING] = 0.1
    return d


def score(p, i, a):
    d = delta(p, i, a)
    anx = p.emotion(i, "anxiety")
    dis = p.emotion(i, "discontent") + p.emotion(i, "anger")
    hope = p.emotion(i, "hope")
    lone = p.emotion(i, "loneliness")
    u = 0.0
    top = -1
    top_v = 0.0
    mod = ""
    for k in range(10):
        w = p.dw[i * 10 + k]
        if k == 1:
            w *= 1.0 + anx
        elif k == 9 or k == 4:
            w *= 1.0 + 0.8 * dis
        elif k == 2:
            w *= 1.0 + lone
        v = -w * d[k] * (0.3 + p.dd[i * 10 + k])
        u += v
        if v > top_v:
            top_v = v
            top = k
    if top == p.D_SECURITY and anx > 0.4:
        mod = "anxiety"
    elif (top == p.D_CHANGE or top == p.D_AUTONOMY) and dis > 0.5:
        mod = "discontent"
    elif top == p.D_BELONGING and lone > 0.4:
        mod = "loneliness"
    cost = [0.0, 0.0, 0.0, TRAIN_COST, 0.0, 0.2 * p.income[i], 0.0, SOCIAL_COST, SUPPORT_COST, MOVE_COST / 12.0, 0.1 * p.income[i], 0.1, 0.0, 0.0][a]
    if cost > 0.0:
        u -= 0.3 * p.lam[i] * cost / gd.maxf(5.0, p.income[i] + 0.2 * p.assets[i] / 12.0) * p.dw[i * p.ND + p.D_SECURITY]
    if a == A_CHANGE or a == A_MOVE or (a == A_DREAM and p.dream_kind[i] == 0):
        u -= 0.12 * p.lam[i] * (1.0 - p.trait_of(i, "risk_tolerance")) * (1.2 - 0.6 * hope)
    if a == A_FOUND:
        u *= 0.4 + 0.6 * p.trait_of(i, "openness") + 0.4 * (0.5 - p.trait_of(i, "authority_attitude"))
    if a == A_TRAIN or a == A_DREAM or a == A_MOVE:
        u *= 0.5 + p.trait_of(i, "future_orientation")
    u += 0.3 * p.q_act[i * NA + a]
    if a == A_THRIFT or a == A_SPLURGE or a == A_SOCIALIZE:
        u += 0.06 * p.pref_social[i] * p.REL.contact_action_share(p, i, a)
    return {"u": u, "top_drive": top, "modulated_by": mod}


def choose(p, i, month):
    law = action_law(p, i)
    ok = law["actions"]
    ws = law["weights"].a
    scores = law["scores"]
    x = p.u("choose", i, month) * float(law["total"])
    pick = len(ok) - 1
    acc = 0.0
    for j in range(len(ok)):
        acc += ws[j]
        if x < acc:
            pick = j
            break
    chosen = scores[pick]
    return {"action": int(ok[pick]), "top_drive": int(chosen["top_drive"]), "modulated_by": str(chosen["modulated_by"]),
            "u": float(chosen["u"]), "refused": law["refused"], "options": len(ok)}


def action_law(p, i):
    cands = candidates(p, i)
    ok = []
    refused = []
    scores = []
    for a in cands:
        why = feasible(p, i, a)
        if why == "":
            ok.append(a)
            scores.append(score(p, i, a))
        else:
            refused.append([a, why])
    best = -math.inf
    for s in scores:
        best = gd.maxf(best, float(s["u"]))
    ws = []
    tot = 0.0
    for s in scores:
        w = detmath.exp((float(s["u"]) - best) / TAU)
        ws.append(w)
        tot += w
    return {"actions": ok, "weights": p.packed("f64", ws), "total": tot, "scores": scores, "refused": refused}


def apply(p, i, a, month):
    G = p.GRP
    p.reset_choices(i)
    if a == A_SEARCH:
        p.set_search(i, 1)
    elif a == A_CHANGE:
        p.set_search(i, 2)
    elif a == A_TRAIN:
        p.spend(i, TRAIN_COST)
        p.add_skill(i, 2.0 * (0.5 + p.trait_of(i, "openness")))
    elif a == A_THRIFT:
        p.set_plan(i, 0)
    elif a == A_SPLURGE:
        p.set_plan(i, 2)
    elif a == A_REST:
        p.add_flag(i, p.F_REST)
    elif a == A_SOCIALIZE:
        p.spend(i, SOCIAL_COST)
        p.add_flag(i, p.F_SOCIALISED)
    elif a == A_SUPPORT:
        p.spend(i, SUPPORT_COST)
        p.add_flag(i, p.F_SUPPORTED)
    elif a == A_MOVE:
        p.spend(i, MOVE_COST)
        p.move_to(i, p.move_destination(i, month), p.move_reason(i) if p.households else "")
        p.add_flag(i, p.F_MOVED)
    elif a == A_DREAM:
        p.set_plan(i, 0)
        p.add_flag(i, p.F_DREAM)
    elif a == A_JOIN:
        g = G.pick_group(p, i)
        if g >= 0:
            G.join(p, i, g)
            p.add_flag(i, p.F_JOINED)
    elif a == A_FOUND:
        p.add_flag(i, p.F_FOUNDED)
    elif a == A_LEAVE:
        pick = -1
        low = math.inf
        for m in range(G.M):
            g = p.member_of[i * G.M + m]
            if g >= 0:
                dv = p.dd[i * 10 + G.PURPOSE[int(p.groups[g]["kind"])]]
                if dv < low:
                    low = dv
                    pick = g
        if pick >= 0:
            G.leave(p, i, pick)
