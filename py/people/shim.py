# The people.gd methods the three modules call (REL_PORT_PLAN §1, the shim), as people.gd writes them, on a cut's state read from
# oracle_dump_rel.gd. Households off only. Why not a fuller person: everything else is the persons port's (Cpくん), which replaces this
import copy
import hashlib

from .deps import keyed, gd, Packed, PackedStr, canon, load
from . import rel, grp, act

TRAITS = ["risk_tolerance", "patience", "sociability", "trust_in_others", "competitiveness", "cooperativeness", "authority_attitude",
          "openness", "fairness", "future_orientation"]
EMOTIONS = ["joy", "sadness", "anger", "anxiety", "fear", "relief", "hope", "loneliness", "discontent", "trust"]
DRIVES = ["survival_safety", "economic_security", "belonging", "recognition", "autonomy", "growth", "enjoyment", "family",
          "contribution", "change"]
EMPLOYMENT = ["not_in_labour_force", "regular", "non_regular", "unemployed", "student", "retired"]
EDUCATION = ["high_school_or_less", "vocational_junior_college", "university_or_more"]
MASK = 0x7FFFFFFFFFFF


class P:
    REL = rel
    GRP = grp
    ACT = act
    TRAITS = TRAITS
    EMOTIONS = EMOTIONS
    DRIVES = DRIVES
    EMPLOYMENT = EMPLOYMENT
    EDUCATION = EDUCATION
    D_SURVIVAL, D_SECURITY, D_BELONGING, D_RECOGNITION, D_AUTONOMY, D_GROWTH, D_ENJOYMENT, D_FAMILY, D_CONTRIBUTION, D_CHANGE = range(10)
    F_REST, F_SOCIALISED, F_SUPPORTED, F_MOVED, F_DREAM, F_JOINED, F_FOUNDED = 1, 2, 4, 8, 16, 32, 64
    EMP_NONE, EMP_REGULAR, EMP_NONREGULAR, EMP_UNEMPLOYED, EMP_STUDENT, EMP_RETIRED = range(6)
    HK_SINGLE, HK_COUPLE, HK_COUPLE_CHILDREN, HK_SINGLE_PARENT, HK_OTHER = range(5)
    NT = 10
    NE = 10
    ND = 10

    def __init__(self, tree):
        # Packed arrays become Python lists while the modules run; their kinds are kept for the digest
        self._kinds = {}
        self._keys = list(tree.keys())
        for k, v in tree.items():
            if isinstance(v, Packed):
                self._kinds[k] = v.kind
                v = [x.item() if hasattr(x, "item") else x for x in v.a]
            setattr(self, k, v)
        if getattr(self, "trace_pids", []):
            raise ValueError("the shim does not write the trace: trace_pids must be empty")
        if getattr(self, "households", False):
            raise NotImplementedError("households on: move_to and move_reason are life_course's (REL_PORT_PLAN §5)")

    @classmethod
    def read(cls, d):
        return cls(load(d))

    @staticmethod
    def packed(kind, values):
        return Packed(kind, list(values))

    def tree(self, extra=()):
        out = {}
        for k in self._keys:
            if k in ("counts", "dec_counts", "ref_counts"):
                continue
            v = getattr(self, k)
            out[k] = Packed(self._kinds[k], v) if k in self._kinds else v
        out["group_log"] = [{a: b for a, b in e.items() if a != "why"} for e in self.group_log]
        for k in extra:
            out[k] = getattr(self, k)
        return out

    def u(self, tag, i, b=0, c=0):
        return keyed.u(self.seed_v, tag, self.pid[i] & MASK, b, c)

    def normal(self, tag, i, b=0, c=0):
        return keyed.normal(self.seed_v, tag, self.pid[i] & MASK, b, c)

    def trait_of(self, i, name):
        return self.traits[i * self.NT + TRAITS.index(name)]

    def emotion(self, i, name):
        return self.emo[i * self.NE + EMOTIONS.index(name)]

    def emotion_column(self, name):
        e = EMOTIONS.index(name)
        return [self.emo[i * self.NE + e] for i in range(self.n)]

    def pull_emotion(self, k, target, rate):
        self.emo[k] = gd.clampf(self.emo[k] + rate * (target - self.emo[k]), 0.0, 1.0)

    def _move(self, i, emotion_name, amount, why, scaled_by, counts):
        if abs(amount) < 1e-9:
            return
        k = i * self.NE + EMOTIONS.index(emotion_name)
        before = self.emo[k]
        self.emo[k] = gd.clampf(before + amount, 0.0, 1.0)
        self._count(counts, why + ":" + emotion_name, i, self.emo[k] - before, "scaled by " + scaled_by if scaled_by != "" else "flat")

    def move_emotion(self, i, emotion_name, amount, why, scaled_by, counts):
        self._move(i, emotion_name, amount, why, scaled_by, counts)

    def count_kind(self, counts, kind, i, move, why):
        self._count(counts, kind, i, move, why)

    def _count(self, counts, kind, i, move, why):
        if kind not in counts:
            counts[kind] = {"n": 0, "w": 0.0, "move": 0.0, "why": why}
        c = counts[kind]
        c["n"] = int(c["n"]) + 1
        c["w"] = float(c["w"]) + self.weight[i]
        c["move"] = float(c["move"]) + move

    def _count_decision(self, dc, a, top, mod, i):
        key = act.ACTIONS[a]
        if key not in dc:
            dc[key] = {"month": self.month, "action": key, "count": 0, "weight": 0.0, "top_drives": {}, "modulated": {}}
        row = dc[key]
        row["count"] = int(row["count"]) + 1
        row["weight"] = float(row["weight"]) + self.weight[i]
        td = DRIVES[top] if top >= 0 else "none"
        row["top_drives"][td] = int(row["top_drives"].get(td, 0)) + 1
        if mod != "":
            row["modulated"][mod] = int(row["modulated"].get(mod, 0)) + 1

    def in_movement(self, i):
        for m in range(grp.M):
            gid = self.member_of[i * grp.M + m]
            if gid >= 0 and int(self.groups[gid]["kind"]) == grp.G_MOVEMENT:
                return True
        return False

    def contact_count(self, i):
        k = 0
        for c in range(rel.C):
            if self.contact_idx[i * rel.C + c] >= 0:
                k += 1
        return k

    def reset_choices(self, i):
        self.plan[i] = 1
        self.search[i] = 0
        self.flags[i] = 0

    def set_search(self, i, v):
        self.search[i] = v

    def set_plan(self, i, v):
        self.plan[i] = v

    def add_flag(self, i, bit):
        self.flags[i] |= bit

    def spend(self, i, amount):
        self.assets[i] = gd.maxf(0.0, self.assets[i] - amount)

    def add_assets(self, i, delta):
        self.assets[i] += delta

    def add_skill(self, i, gain):
        self.skill[i] = gd.minf(100.0, self.skill[i] + gain)

    def believed_food_rise(self, i):
        return self.belief[i * rel.NF] if self.belief_known[i * rel.NF] == 1 else 0.0

    def believed_cost_rise(self, i):
        return self.basket[i * 4] * self.believed_food_rise(i)

    def move_reason(self, i):
        raise NotImplementedError("households on: move_reason reads the household roles (REL_PORT_PLAN §5)")

    def move_destination(self, i, m):
        tot = 0.0
        for code in self.pref_pop:
            if code != self.pref[i]:
                tot += float(self.pref_pop[code])
        x = self.u("move_to", i, m) * tot
        acc = 0.0
        last = self.pref[i]
        for code2 in self.pref_codes:
            c = int(code2)
            if c == self.pref[i]:
                continue
            acc += float(self.pref_pop[c])
            last = c
            if x < acc:
                return c
        return last

    def move_to(self, i, dest, reason=""):
        self.pref[i] = dest
        self._moved(i, dest)

    def _moved(self, i, dest):
        for m in range(grp.M):
            g = self.member_of[i * grp.M + m]
            if g >= 0 and int(self.groups[g]["pref"]) != dest:
                grp.leave(self, i, g)
        for c in range(rel.C):
            j = self.contact_idx[i * rel.C + c]
            if j < 0 or self.contact_kind[i * rel.C + c] == rel.K_FAMILY or self.pref[j] == dest:
                continue
            if self.u("movekeep", i, self.month * rel.C + c) >= 0.5:
                rel.unlink_slot(self, i, c)

    def quantiles(self, values, idx, qs=(0.1, 0.5, 0.9)):
        rows = []
        tot = 0.0
        for i in idx:
            rows.append([values[i], self.weight[i], self.pid[i]])
            tot += self.weight[i]
        # Why a key with the pid last: people.gd's comparator orders by value, then pid, which is a total order
        rows.sort(key=lambda r: (r[0], r[2]))
        out = []
        for q in qs:
            acc = 0.0
            v = rows[len(rows) - 1][0] if len(rows) > 0 else 0.0
            for r in rows:
                acc += float(r[1])
                if acc >= q * tot:
                    v = float(r[0])
                    break
            out.append(v)
        return out

    def _ranks(self):
        # people.gd:1005-1020
        by = {}
        for i in range(self.n):
            if self.pref[i] not in by:
                by[self.pref[i]] = []
            by[self.pref[i]].append(i)
        for code in by:
            idx = by[code]
            # Why a key and not Godot's comparator: income then pid is a total order, so every correct sort gives the same list
            idx.sort(key=lambda a: (self.income[a], self.pid[a]))
            tot = 0.0
            for i in idx:
                tot += self.weight[i]
            acc = 0.0
            for i in idx:
                acc += self.weight[i]
                self.rank[i] = acc / tot

    def records(self, counts, dec_counts, ref_counts):
        # people.gd:1296-1304
        for key in dec_counts:
            self.decisions.append(dec_counts[key])
        for rk in ref_counts:
            parts = rk.split("|")
            self.refusals.append({"month": self.month, "action": act.ACTIONS[int(parts[0])], "why": parts[1], "count": int(ref_counts[rk])})
        for kind in counts:
            c = counts[kind]
            self.events.append({"month": self.month, "kind": kind, "count": int(c["n"]), "weight": float(c["w"]),
                                "mean_move": float(c["move"]) / gd.maxf(1.0, float(c["n"])), "why": str(c["why"])})

    def section_a(self):
        # people.gd:1253-1266, the decision loop
        counts, dec_counts, ref_counts = {}, {}, {}
        for i in range(self.n):
            ch = act.choose(self, i, self.month)
            a = int(ch["action"])
            act.apply(self, i, a, self.month)
            if a == act.A_FOUND:
                grp.found_movement(self, i, counts)
            self.last_action[i] = a
            self._count_decision(dec_counts, a, int(ch["top_drive"]), str(ch["modulated_by"]), i)
            for r in ch["refused"]:
                rk = "%d|%s" % (int(r[0]), str(r[1]))
                ref_counts[rk] = int(ref_counts.get(rk, 0)) + 1
        self.counts, self.dec_counts, self.ref_counts = counts, dec_counts, ref_counts

    def section_b(self, truth):
        # people.gd:1268-1270
        rel.interact(self, self.counts)
        rel.learn(self, truth, self.counts)
        grp.step(self, self.counts)


def sha(v):
    h = hashlib.sha256()
    canon(h, v)
    return h.hexdigest()


def hashes(tree):
    return {k: sha(v) for k, v in tree.items()}
