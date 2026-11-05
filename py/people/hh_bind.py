# people.gd's households-on half at cd165891 (PERSONS_PORT_PLAN §9, P-b), bound onto P as bind.py binds the shim: the start
# (_create_households with HH.load_spec), the households' registry rows, the growth and compaction py/lchh's life course calls on its
# state (new_person, grow_persons, remove_persons), the prefecture moves (set_pref, move_reason, move_destination, move_to) and the
# save's households part. py/lchh's functions run on P itself; loop_c.py holds the month's households branches
import country
from core import keyed
from core.gd import idiv
from lchh import households as HH
from lchh import life_course as LC
from people import act as ACT
from people import grp as GRP
from people import rel as REL
from people.sections import _ranks
from tiers.start import load
from tiers.start.p import P, PArr



# households.gd 14
def hh_load_spec(p):
    # Why not a missing file's exception: CANON.load_json gives null for it, which the caller reports as households.gd does
    try:
        d = load.load_json(country.load(p.state).path("households_spec"))
    except FileNotFoundError:
        d = None
    if not isinstance(d, dict):
        return "households: no spec for " + p.state
    p.hh_spec = d
    return ""


def _packed(p):
    # Why not py/lchh's lists as they come: its pstate keeps each array's kind aside and its build_start and LC.start assign plain
    # lists, where P's digest, save and remove_persons read the kind from the array
    for h in p.household_fields():
        v = getattr(p, str(h[0]))
        if not isinstance(v, PArr):
            setattr(p, str(h[0]), PArr(str(h[2]), v))


# people.gd 314
def move_reason(p, i):
    if p.hh_role[i] == P.R_PARTNER:
        return ""
    if p._job_reason(i) or (p.hh_role[i] == P.R_HEAD and p.partner[i] >= 0 and p._job_reason(p.partner[i])):
        return "job"
    return "family" if p._kin_elsewhere(i) >= 0 else ""


# people.gd 322
def _job_reason(p, i):
    return p.employment[i] == P.EMP_UNEMPLOYED or p.last_action[i] == ACT.A_SEARCH or p.last_action[i] == ACT.A_CHANGE


# people.gd 326
def _kin_elsewhere(p, i):
    for c in range(REL.C):
        j = p.contact_idx[i * REL.C + c]
        if j >= 0 and p.contact_kind[i * REL.C + c] == REL.K_FAMILY and p.pref[j] != p.pref[i]:
            return p.pref[j]
    return -1


# people.gd 334
def move_destination(p, i, m):
    if p.households and p.move_reason(i) == "family":
        return p._kin_elsewhere(i)
    tot = 0.0
    for code in p.pref_pop:
        if code != p.pref[i]:
            tot += float(p.pref_pop[code])
    x = p.u("move_to", i, m) * tot
    acc = 0.0
    last = p.pref[i]
    for code2 in p.pref_codes:
        c = int(code2)
        if c == p.pref[i]:
            continue
        acc += float(p.pref_pop[c])
        last = c
        if x < acc:
            return c
    return last


# people.gd 362
def move_to(p, i, dest, reason=""):
    if p.households:
        LC.move_household(p, i, dest, reason)
        return
    p.pref[i] = dest
    p._moved(i, dest)


# people.gd 580
def _create_households(p, prefectures, n_per):
    if hh_load_spec(p) != "":
        p.error = "households: no spec for " + p.state
        return p.error
    for code in p.pref_codes:
        p.pref_pop[int(code)] = float(prefectures[code]["pop_thousand"]) * 1000.0
    # Why not the prefectures passed on: households.gd build_start takes them and reads none
    HH.build_start(p, n_per)
    _packed(p)
    for i in range(p.n):
        p._draw_attributes(i)
        p._draw_traits(i)
        p._draw_dream(i)
    LC.start(p)
    _packed(p)
    _ranks(p)
    for j in range(p.n):
        p._compose_drives(j)
        p._init_states(j)
    HH.link_family(p)
    REL.build(p)
    GRP.seed_groups(p)
    p.reweight(PArr("f64"), True)
    LC.solve_c(p)
    return ""


# people.gd 629
def household_fields(p=None):
    return [["hh_id", "hh_id", "i32", 1, True], ["hh_role", "role", "i32", 1, True], ["partner", "partner", "i32", 1, True],
            ["ever_married", "ever_married", "i32", 1, True], ["ever_left", "ever_left", "i32", 1, True], ["union_month", "union_month", "i32", 1, True],
            ["last_birth", "last_birth", "i32", 1, True], ["births_n", "births_n", "i32", 1, True],
            ["hh_type", "type", "i32", 0, True], ["hh_pref", "pref", "i32", 0, True], ["hh_weight", "weight", "f64", 0, True], ["lc_c", "lc_c", "f64", 0, True], ["lc_qcut", "lc_qcut", "f64", 0, True],
            ["lc_expected", "lc_expected", "f64", 0, False], ["lc_deaths", "lc_deaths", "i32", 0, False],
            ["lc_nm_short", "lc_nm_short", "f64", 0, False], ["intends_marry", "intends_marry", "i32", 1, True], ["intended_kids", "intended_kids", "i32", 1, True],
            ["health_class", "health_class", "i32", 1, True]]


# people.gd 641
def per_person_arrays(p):
    out = []
    for f in p.fields():
        if int(f[2]) > 0:
            out.append([getattr(p, str(f[0])), int(f[2])])
    for h in p.household_fields():
        if int(h[3]) > 0:
            out.append([getattr(p, str(h[0])), int(h[3])])
    return out


# people.gd 853
def set_pref(p, i, code):
    was = p.pref[i]
    p.pref[i] = code
    if p.households and code != was:
        p._moved(i, code)


# people.gd 877
def new_person(p, code, k):
    j = p.n
    p.grow_persons(j + 1)
    p.pref[j] = code
    p.k_in_pref[j] = 1000000 + k
    p.age[j] = 0
    p.sex[j] = P.MALE if keyed.u(p.seed_v, "lc_sex", code, k, 0) < 0.512 else P.FEMALE
    p.pid[j] = keyed.pid(p.seed_v, code, p.base_year + idiv(p.month, 12), p.sex[j], 1000000 + k)
    return j


# people.gd 901
def grow_persons(p, m):
    n0 = p.n
    for e in p.per_person_arrays():
        e[0].resize(m * int(e[1]))
    for i in range(n0, m):
        for c in range(REL.C):
            p.contact_idx[i * REL.C + c] = -1
        for g in range(GRP.M):
            p.member_of[i * GRP.M + g] = -1
    p.n = m


# people.gd 915
def remove_persons(p, dead):
    n_old = len(dead)
    remap = PArr("i32")
    remap.resize(p.n)
    k = 0
    for i in range(p.n):
        if i < n_old and dead[i] == 1:
            remap[i] = -1
        else:
            remap[i] = k
            k += 1
    if k == p.n:
        return
    for e in p.per_person_arrays():
        arr = e[0]
        s = int(e[1])
        for i2 in range(p.n):
            t = remap[i2]
            if t >= 0 and t != i2:
                for c in range(s):
                    arr[t * s + c] = arr[i2 * s + c]
        arr.resize(k * s)
    for c2 in range(len(p.contact_idx)):
        j = p.contact_idx[c2]
        if j >= 0:
            p.contact_idx[c2] = remap[j]
    for i3 in range(k):
        if p.partner[i3] >= 0:
            p.partner[i3] = remap[p.partner[i3]]
    p.n = k
    HH.refresh_members(p)


for _f in (move_reason, _job_reason, _kin_elsewhere, move_destination, move_to, _create_households, household_fields, per_person_arrays,
           set_pref, new_person, grow_persons, remove_persons):
    setattr(P, _f.__name__, _f)
