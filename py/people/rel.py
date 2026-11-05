# The twin of sim/modern/people/relations.gd (REL_PORT_PLAN §1), in its names, loops and operation order
from .deps import keyed
from .deps import gd

C = 12
KINDS = ["family", "friend", "colleague", "neighbour"]
K_FAMILY = 0
K_FRIEND = 1
K_COLLEAGUE = 2
K_NEIGHBOUR = 3
TRUST0 = [80.0, 50.0, 40.0, 30.0]
FACTS = ["food_price_yoy", "unemployment_rate"]
NF = 2
CRED_KIN = 0.8
CRED_RUMOUR = 0.3
PUBLISH_ERR_BY_FACT = [0.0005, 0.001]
RUMOUR_NOISE = 0.02
HELP_SUM = 5.0
DECAY_AFTER = 6
FORGET_BELOW = 5.0
MASK = 0x7FFFFFFFFFFF


def _employed(p, j):
    return p.employment[j] == p.EMP_REGULAR or p.employment[j] == p.EMP_NONREGULAR


def build(p):
    by = {}
    for i in range(p.n):
        if p.pref[i] not in by:
            by[p.pref[i]] = []
        by[p.pref[i]].append(i)
    for i in range(p.n):
        pool = by[p.pref[i]]
        want = targets(p, i).a
        have = [0, 0, 0, 0]
        for c in range(C):
            if p.contact_idx[i * C + c] >= 0:
                have[p.contact_kind[i * C + c]] += 1
        tries = 0
        for kind in range(4):
            while have[kind] < want[kind] and tries < 40:
                found = -1
                while tries < 40 and found < 0:
                    j = pool[KEYED_below(p, len(pool), "contact", i, tries)]
                    tries += 1
                    if j == i or has_contact(p, i, j) or p.contact_count(j) >= C:
                        continue
                    if kind == K_FRIEND and abs(p.age[j] - p.age[i]) > 8:
                        continue
                    if kind == K_COLLEAGUE and not _employed(p, j):
                        continue
                    found = j
                if found < 0:
                    break
                if add(p, i, found, kind):
                    if add(p, found, i, kind):
                        have[kind] += 1
                    else:
                        p.contact_idx[i * C + slot(p, i, found)] = -1
                else:
                    break


def targets(p, i):
    return p.packed("i32", [2 if p.hh_kind[i] >= p.HK_COUPLE else 1, 1 + int(3.0 * p.pref_social[i] + 0.5),
                            2 if _employed(p, i) else 0, 1])


def replenish(p, i, pool):
    if p.age[i] < 15 or len(pool) < 2:
        return
    have = [0, 0, 0, 0]
    for c in range(C):
        if p.contact_idx[i * C + c] >= 0:
            have[p.contact_kind[i * C + c]] += 1
    want = targets(p, i).a
    tries = 0
    for kind in (K_FRIEND, K_COLLEAGUE, K_NEIGHBOUR):
        while have[kind] < want[kind] and tries < 10 and p.contact_count(i) < C:
            j = pool[keyed.below(len(pool), p.seed_v, "replenish", p.pid[i] & MASK, p.month * 16 + tries, 0)]
            tries += 1
            if j == i or has_contact(p, i, j) or p.contact_count(j) >= C or p.age[j] < 15:
                continue
            if kind == K_FRIEND and abs(p.age[j] - p.age[i]) > 8:
                continue
            if kind == K_COLLEAGUE and not _employed(p, j):
                continue
            if add(p, i, j, kind):
                if add(p, j, i, kind):
                    have[kind] += 1
                else:
                    p.contact_idx[i * C + slot(p, i, j)] = -1


def KEYED_below(p, n, tag, i, t):
    return keyed.below(n, p.seed_v, tag, p.pid[i] & MASK, t, 0)


def has_contact(p, i, j):
    for c in range(C):
        if p.contact_idx[i * C + c] == j:
            return True
    return False


def add(p, i, j, kind):
    for c in range(C):
        if p.contact_idx[i * C + c] < 0:
            p.contact_idx[i * C + c] = j
            p.contact_kind[i * C + c] = kind
            p.contact_trust[i * C + c] = TRUST0[kind]
            p.contact_last[i * C + c] = p.month
            return True
    return False


def raise_trust(p, i, c, amount):
    p.contact_trust[i * C + c] = gd.minf(100.0, p.contact_trust[i * C + c] + amount)


def unlink(p, i, j):
    c = slot(p, i, j)
    if c >= 0:
        p.contact_idx[i * C + c] = -1


def unlink_slot(p, i, c):
    j = p.contact_idx[i * C + c]
    back = slot(p, j, i)
    if back >= 0:
        p.contact_idx[j * C + back] = -1
    p.contact_idx[i * C + c] = -1


def clear_met(p, i):
    p.met[i] = 0


def forget(p, i):
    for f in range(NF):
        p.belief_known[i * NF + f] = 0


def drop_all(p, i):
    for c in range(C):
        j = p.contact_idx[i * C + c]
        if j >= 0:
            back = slot(p, j, i)
            if back >= 0:
                p.contact_idx[j * C + back] = -1
        p.contact_idx[i * C + c] = -1


def slot(p, i, j):
    for c in range(C):
        if p.contact_idx[i * C + c] == j:
            return c
    return -1


def trust_move(p, i, j, amount):
    c = slot(p, i, j)
    if c >= 0:
        p.contact_trust[i * C + c] = gd.clampf(p.contact_trust[i * C + c] + amount, 0.0, 100.0)
        p.contact_last[i * C + c] = p.month


def pick_partner(p, i, tag):
    tot = 0.0
    for c in range(C):
        if p.contact_idx[i * C + c] >= 0:
            tot += p.contact_trust[i * C + c] + 1.0
    if tot <= 0.0:
        return -1
    x = p.u(tag, i, p.month) * tot
    acc = 0.0
    for c in range(C):
        if p.contact_idx[i * C + c] >= 0:
            acc += p.contact_trust[i * C + c] + 1.0
            if x < acc:
                return p.contact_idx[i * C + c]
    return -1


def most_trusted(p, i, kind=-1):
    best = -1
    bt = -1.0
    for c in range(C):
        j = p.contact_idx[i * C + c]
        if j >= 0 and (kind < 0 or p.contact_kind[i * C + c] == kind) and p.contact_trust[i * C + c] > bt:
            bt = p.contact_trust[i * C + c]
            best = j
    return best


def interact(p, counts):
    for i in range(p.n):
        if p.flags[i] & p.F_SOCIALISED:
            j = pick_partner(p, i, "partner")
            if j >= 0:
                p.move_emotion(i, "loneliness", -0.12 * p.pref_social[i], "met_contact", "sociability", counts)
                p.move_emotion(j, "loneliness", -0.08 * p.pref_social[j], "met_contact", "sociability", counts)
                p.move_emotion(i, "joy", 0.06, "met_contact", "", counts)
                p.move_emotion(j, "joy", 0.04, "met_contact", "", counts)
                trust_move(p, i, j, 3.0)
                trust_move(p, j, i, 3.0)
                p.met[i] = 1
                p.met[j] = 1
        if p.flags[i] & p.F_SUPPORTED:
            f = most_trusted(p, i, 0)
            if f >= 0:
                p.add_assets(f, p.ACT.SUPPORT_COST)
                trust_move(p, f, i, 5.0)
                p.move_emotion(f, "trust", 0.03, "supported_by_family", "", counts)
        if p.dd[i * p.ND + p.D_SECURITY] > 0.6 and p.age[i] >= 18:
            h = most_trusted(p, i)
            if h >= 0:
                c = slot(p, h, i)
                tr = p.contact_trust[h * C + c] / 100.0 if c >= 0 else 0.3
                gives = p.assets[h] >= HELP_SUM and p.u("help", h, p.month) < p.trait_of(h, "cooperativeness") * tr
                if gives:
                    p.add_assets(h, -HELP_SUM)
                    p.add_assets(i, HELP_SUM)
                    trust_move(p, i, h, 3.0)
                    p.move_emotion(i, "relief", 0.2, "helped_by_contact", "", counts)
                    p.move_emotion(i, "trust", 0.05, "helped_by_contact", "", counts)
                    p.count_kind(counts, "help_given", h, HELP_SUM, "cooperativeness x trust (T)")
                else:
                    trust_move(p, i, h, -4.0)
                    p.move_emotion(i, "sadness", 0.05, "refused_by_contact", "", counts)
                    p.count_kind(counts, "help_refused", h, 0.0, "assets or cooperativeness x trust below the draw (T)")
    for i in range(p.n):
        for c in range(C):
            j = p.contact_idx[i * C + c]
            if j < 0:
                continue
            if p.month - p.contact_last[i * C + c] > DECAY_AFTER:
                p.contact_trust[i * C + c] -= 2.0
            if p.contact_kind[i * C + c] == K_FAMILY:
                p.contact_trust[i * C + c] = gd.maxf(p.contact_trust[i * C + c], FORGET_BELOW)
                continue
            if p.contact_trust[i * C + c] < FORGET_BELOW:
                p.contact_idx[i * C + c] = -1
                back = slot(p, j, i)
                if back >= 0:
                    p.contact_idx[j * C + back] = -1


def learn(p, truth, counts):
    prev = list(p.belief)
    prev_known = list(p.belief_known)
    readers = 0
    heard = 0
    for i in range(p.n):
        if p.age[i] < 15:
            continue
        reads = p.u("reads", i, p.month) < p.pol_interest[i]
        for f in range(NF):
            k = i * NF + f
            tv = float(truth.get(FACTS[f], 0.0))
            if reads:
                err = float(PUBLISH_ERR_BY_FACT[f]) * (2.0 * keyed.u(p.seed_v, "puberr", f, p.month, 0) - 1.0)
                p.belief[k] = tv + err
                p.belief_known[k] = 1
                p.belief_source[k] = 0
                p.belief_month[k] = p.month
                if f == 0:
                    readers += 1
            elif p.contact_news:
                acc = 0.0
                wsum = 0.0
                for c in range(C):
                    j = p.contact_idx[i * C + c]
                    if j < 0 or prev_known[j * NF + f] == 0:
                        continue
                    cred = CRED_KIN if p.contact_kind[i * C + c] == K_FAMILY else CRED_RUMOUR
                    w = cred * p.contact_trust[i * C + c] / 100.0
                    acc += w * (prev[j * NF + f] + RUMOUR_NOISE * p.normal("rumour", i, p.month, c))
                    wsum += w
                if wsum > 0.0:
                    told = acc / wsum
                    cw = gd.minf(1.0, wsum)
                    p.belief[k] = told if p.belief_known[k] == 0 else (1.0 - cw) * p.belief[k] + cw * told
                    p.belief_known[k] = 1
                    p.belief_source[k] = 1
                    p.belief_month[k] = p.month
                    if f == 0:
                        heard += 1
            if f == 1 and p.employment[i] == p.EMP_UNEMPLOYED:
                p.belief[k] = gd.maxf(p.belief[k], tv) + 0.05
                p.belief_known[k] = 1
                p.belief_source[k] = 2
                p.belief_month[k] = p.month
    if readers > 0:
        p.count_kind(counts, "read_register", 0, float(readers), "political interest x one keyed draw")
    if heard > 0:
        p.count_kind(counts, "heard_from_contacts", 0, float(heard), "credibility kin 0.8 / rumour 0.3 x trust, with noise")


def contact_action_share(p, i, action):
    n = 0
    m = 0
    for c in range(C):
        j = p.contact_idx[i * C + c]
        if j >= 0:
            n += 1
            if p.last_action[j] == action:
                m += 1
    return float(m) / float(n) if n > 0 else 0.0
