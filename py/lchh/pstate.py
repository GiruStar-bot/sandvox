# The persons' state for the life course and households port (LC_HH_PORT_PLAN §1-§3): read from oracle_dump_lc_hh.gd's cuts, the
# helpers of people.gd, relations.gd and groups.gd the two files call, and the cut's per-field digest
import hashlib
import json
import os

from core import digest, keyed
from core.digest import Packed

ID_MASK = (1 << 62) - 1
PID_LOW = 0x7FFFFFFFFFFF

# people.gd's constants (the dump's registry.json repeats them; L0-k compares)
MALE, FEMALE = 0, 1
HK_SINGLE, HK_COUPLE, HK_COUPLE_CHILDREN, HK_SINGLE_PARENT, HK_OTHER = 0, 1, 2, 3, 4
R_HEAD, R_PARTNER, R_CHILD, R_PARENT, R_OTHER = 0, 1, 2, 3, 4
GRADE_POOR, GRADE_LIMITED = 2, 3
EMP_NONE, EMP_REGULAR, EMP_NONREGULAR, EMP_UNEMPLOYED, EMP_STUDENT, EMP_RETIRED = 0, 1, 2, 3, 4, 5
D_SECURITY, D_AUTONOMY, D_FAMILY = 1, 4, 7
AGES, SEXES = 101, 2
AGE_BANDS = (15, 30, 45, 65)
NT, NE, ND = 10, 10, 10
EMOTIONS = ("joy", "sadness", "anger", "anxiety", "fear", "relief", "hope", "loneliness", "discontent", "trust")
C = 12
M = 3
K_FAMILY = 0
TRUST0 = (80.0, 50.0, 40.0, 30.0)
MOVE_KEEP = 0.5

KIND_OF = {"i64": "i64", "i32": "i32", "f64": "f64"}


def pid(seed_v, region, slot_year, sex, k):
    # sim/earth_core/keyed.gd:64
    h = keyed.h64(keyed.head(seed_v, "pid"), region, slot_year, sex)
    return keyed.mix((h + k * keyed.GOLD) & keyed.M64) & ID_MASK


class P:
    # One cut's state. Per-person and per-household packed arrays are Python lists, their kind in self.kinds; hh_members is a list of
    # lists; dictionaries keep the dump's insertion order
    def __init__(self, reg, spec, hh_spec, tree):
        self.reg = reg
        self.spec = spec
        self.hh_spec = hh_spec
        self.kinds = {}
        self.per_person = []
        for f in reg["fields"]:
            self.kinds[f[0]] = f[1]
            if int(f[2]) > 0:
                self.per_person.append((f[0], int(f[2])))
        for h in reg["household_fields"]:
            self.kinds[h[0]] = h[2]
            if int(h[3]) > 0:
                self.per_person.append((h[0], int(h[3])))
        self.kinds["lc_dying"] = "i32"
        self.names = sorted([f[0] for f in reg["fields"]] + [h[0] for h in reg["household_fields"]] + list(reg["extras"]))
        for k in self.names:
            v = tree[k]
            if k == "hh_members":
                v = [list(x.a) for x in v]
            elif k in self.kinds:
                v = list(v.a) if isinstance(v, Packed) else list(v)
            setattr(self, k, v)
        self.replay = None       # the month's newborns' replayed fields, by pid (LC_HH_PORT_PLAN §2)
        self.replay_off = False  # L-mf3

    # --- the digest (oracle_dump_lc_hh.gd _snap)
    def field(self, k):
        v = getattr(self, k)
        if k == "hh_members":
            return [Packed("i32", x) for x in v]
        if k in self.kinds:
            return Packed(self.kinds[k], v)
        return v

    def hashes(self):
        out = {}
        for k in self.names:
            h = hashlib.sha256()
            digest.canon(h, self.field(k))
            out[k] = h.hexdigest()
        return out

    def digest(self):
        hs = self.hashes()
        return digest.month_digest(hs), hs

    def save(self, d):
        os.makedirs(d, exist_ok=True)
        files = [0]
        tree = {k: digest.enc(self.field(k), d, files) for k in self.names}
        with open(os.path.join(d, "state.json"), "w", encoding="utf-8") as f:
            json.dump(tree, f)

    # --- people.gd
    def u(self, tag, i, b=0, c=0):
        return keyed.u(self.seed_v, tag, self.pid[i] & PID_LOW, b, c)

    def below(self, tag, i, b, c, h):
        return self.u(tag, i, b, c) < h

    def emotion(self, i, name):
        return self.emo[i * NE + EMOTIONS.index(name)]

    def contact_count(self, i):
        k = 0
        for c in range(C):
            if self.contact_idx[i * C + c] >= 0:
                k += 1
        return k

    def set_pref(self, i, code):
        was = self.pref[i]
        self.pref[i] = code
        if code != was:
            self._moved(i, code)

    def _moved(self, i, dest):
        for m in range(M):
            g = self.member_of[i * M + m]
            if g >= 0 and int(self.groups[g]["pref"]) != dest:
                grp_leave(self, i, g)
        for c in range(C):
            j = self.contact_idx[i * C + c]
            if j < 0 or self.contact_kind[i * C + c] == K_FAMILY or self.pref[j] == dest:
                continue
            if self.u("movekeep", i, self.month * C + c) >= MOVE_KEEP:
                rel_unlink_slot(self, i, c)

    def place_persons(self, m):
        self.n = m
        # people._resize: Godot's resize keeps the held values and zero-fills the rest, then a non-zero default fills the whole array
        for f in self.reg["fields"]:
            st = int(f[2])
            if st > 0:
                z = 0.0 if f[1] == "f64" else 0
                arr = getattr(self, f[0])
                arr.extend([z] * max(0, m * st - len(arr)))
                del arr[m * st:]
                if int(f[3]) != 0:
                    fill = float(f[3]) if f[1] == "f64" else int(f[3])
                    arr[:] = [fill] * len(arr)

    def place_person(self, i, code, kk, a, s):
        self.pref[i] = code
        self.k_in_pref[i] = kk
        self.age[i] = a
        self.sex[i] = s
        self.pid[i] = pid(self.seed_v, code, self.base_year - a, s, kk)

    def grow_persons(self, m):
        n0 = self.n
        for name, st in self.per_person:
            arr = getattr(self, name)
            z = 0.0 if self.kinds[name] == "f64" else 0
            # Why no shrink: the only caller is new_person with m = n + 1, and every array holds n x stride values (§7.1)
            arr.extend([z] * (m * st - len(arr)))
        for i in range(n0, m):
            for c in range(C):
                self.contact_idx[i * C + c] = -1
            for g in range(M):
                self.member_of[i * M + g] = -1
        self.n = m

    def new_person(self, code, k):
        j = self.n
        self.grow_persons(j + 1)
        self.pref[j] = code
        self.k_in_pref[j] = 1000000 + k
        self.age[j] = 0
        self.sex[j] = MALE if keyed.u(self.seed_v, "lc_sex", code, k, 0) < 0.512 else FEMALE
        self.pid[j] = pid(self.seed_v, code, self.base_year + self.month // 12, self.sex[j], 1000000 + k)
        return j

    def _replay_person(self, j, which):
        # draw_person / finish_person's outputs, from the oracle's post state (LC_HH_PORT_PLAN §2). Why both calls copy every replayed
        # field: their split of the fields is people.gd's, and the life course reads none of them between the two calls except health,
        # which it writes itself
        if self.replay_off or self.replay is None or which != "finish":
            return
        row = self.replay.get(self.pid[j])
        if row is None:
            raise KeyError("no replayed fields for newborn pid %d" % self.pid[j])
        for name, vals in row.items():
            st = len(vals)
            arr = getattr(self, name)
            for c in range(st):
                arr[j * st + c] = vals[c]

    def draw_person(self, j):
        self._replay_person(j, "draw")

    def finish_person(self, j):
        self._replay_person(j, "finish")

    def remove_persons(self, dead):
        n_old = len(dead)
        remap = [0] * self.n
        k = 0
        for i in range(self.n):
            if i < n_old and dead[i] == 1:
                remap[i] = -1
            else:
                remap[i] = k
                k += 1
        if k == self.n:
            return
        for name, s in self.per_person:
            arr = getattr(self, name)
            for i2 in range(self.n):
                t = remap[i2]
                if t >= 0 and t != i2:
                    for c in range(s):
                        arr[t * s + c] = arr[i2 * s + c]
            del arr[k * s:]
        ci = self.contact_idx
        for c2 in range(len(ci)):
            j = ci[c2]
            if j >= 0:
                ci[c2] = remap[j]
        for i3 in range(k):
            if self.partner[i3] >= 0:
                self.partner[i3] = remap[self.partner[i3]]
        self.n = k
        from . import households
        households.refresh_members(self)

    def cell_target(self, cohort_now=None):
        # people.reweight's head (people.gd:399-408): the cell target and the scale since the start
        c_now = cohort_now if cohort_now is not None and len(cohort_now) == AGES * SEXES else self.cohort
        tot_start = 0.0
        tot_now = 0.0
        for k in range(AGES * SEXES):
            tot_start += self.cohort[k]
            tot_now += c_now[k]
        ct = [0.0] * ((len(AGE_BANDS) + 1) * SEXES)
        for a in range(AGES):
            for s in range(SEXES):
                ct[band_of(a) * SEXES + s] += c_now[a * SEXES + s] / tot_now
        return ct, tot_now / tot_start

    def reweight(self, cohort_now=None, start_types=False):
        from . import households
        ct, scale = self.cell_target(cohort_now)
        households.rake(self, ct, scale, start_types)


def band_of(a):
    for b in range(len(AGE_BANDS)):
        if a < AGE_BANDS[b]:
            return b
    return len(AGE_BANDS)


# --- relations.gd
def rel_has_contact(p, i, j):
    for c in range(C):
        if p.contact_idx[i * C + c] == j:
            return True
    return False


def rel_add(p, i, j, kind):
    for c in range(C):
        if p.contact_idx[i * C + c] < 0:
            p.contact_idx[i * C + c] = j
            p.contact_kind[i * C + c] = kind
            p.contact_trust[i * C + c] = TRUST0[kind]
            p.contact_last[i * C + c] = p.month
            return True
    return False


def rel_slot(p, i, j):
    for c in range(C):
        if p.contact_idx[i * C + c] == j:
            return c
    return -1


def rel_unlink(p, i, j):
    c = rel_slot(p, i, j)
    if c >= 0:
        p.contact_idx[i * C + c] = -1


def rel_unlink_slot(p, i, c):
    j = p.contact_idx[i * C + c]
    back = rel_slot(p, j, i)
    if back >= 0:
        p.contact_idx[j * C + back] = -1
    p.contact_idx[i * C + c] = -1


def rel_drop_all(p, i):
    for c in range(C):
        j = p.contact_idx[i * C + c]
        if j >= 0:
            back = rel_slot(p, j, i)
            if back >= 0:
                p.contact_idx[j * C + back] = -1
        p.contact_idx[i * C + c] = -1


# --- groups.gd
def grp_leave(p, i, gid):
    for m in range(M):
        if p.member_of[i * M + m] == gid:
            p.member_of[i * M + m] = -1
            g = p.groups[gid]
            g["members"] = int(g["members"]) - 1
            g["weight"] = float(g["weight"]) - p.weight[i]


# --- the dump
def load_dump_common(d):
    with open(os.path.join(d, "registry.json"), encoding="utf-8") as f:
        reg = json.load(f)
    sp = digest.load(os.path.join(d, "spec"))
    return reg, sp["spec"], sp["hh_spec"]


def load_cut(d, cut, reg, spec, hh_spec):
    return P(reg, spec, hh_spec, digest.load(os.path.join(d, cut), as_lists=True))


def load_newborns(d, m, kinds):
    import struct
    name = m if isinstance(m, str) else "m%02d_newborn.json" % m
    with open(os.path.join(d, name), encoding="utf-8") as f:
        nb = json.load(f)
    out = {}
    for row in nb["rows"]:
        r = {}
        for name, vals in row.items():
            if name == "pid":
                continue
            if kinds[name] == "f64":
                r[name] = [struct.unpack("<d", struct.pack("<q", int(v)))[0] for v in vals]
            else:
                r[name] = [int(v) for v in vals]
        out[int(row["pid"])] = r
    return out
