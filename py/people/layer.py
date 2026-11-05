# The persons layer as the integrated month calls it (py/world/integrated.py's PersonsStub, INTEGRATED_MONTH_PLAN §5): people.gd's
# create (its sample paths: tiers off, households off or on), supply, summary, fields and to_dict at cd165891, on the persons' object P
# (py/tiers/start/p.py) with the start's, loop C's and the shim's methods bound, and the month as py/people/month.py's step
import base64
import copy
import math
import struct

from core import detmath as DM
import country
from core import digest, keyed
from core.gd import fdiv, maxf
from core.gdsort import sort, sort_custom
from people import bind  # noqa: F401
from people import act as ACT
from people import grp as GRP
from people import month as MONTH
from people import rel as REL
from people.sections import _ranks
from tiers.start import load, trace
from tiers.start.p import P, PArr, from_tree

_PACK = {"i64": "<%dq", "i32": "<%di", "f64": "<%dd"}


# people.gd 273
def load_spec(p, key, commodities_path=None):
    p.state = key
    d = load.load_json(country.load(key).path("people_spec"))
    if not isinstance(d, dict):
        p.error = "people: no spec for " + key
        return p.error
    p.spec = d
    commodities_path = commodities_path or country.load(key).path("commodities")
    cm = load.load_json(commodities_path)
    if not isinstance(cm, dict) or "food_products" not in cm.get("commodities", {}):
        p.error = "people: no food price elasticity (%s)" % commodities_path
        return p.error
    p.food_elasticity = float(cm["commodities"]["food_products"]["demand_elasticity"])
    return ""


# people.gd 447
def create(p, key, seed, cohort_, qx_, prefectures, n_per=0, year=2024):
    if p.load_spec(key) != "":
        return p.error
    p.seed_v = seed
    # Why an instance value over people.gd's constant: the pension age is the country's (FRAME_PLAN §3, row F-mf)
    p.PENSION_AGE = int(country.load(key).constants["pension_age"])
    p.base_year = year
    p.cohort = PArr("f64", [float(x) for x in cohort_])
    p.qx = PArr("f64", [float(x) for x in qx_])
    if n_per <= 0:
        n_per = int(p.spec["n_per_prefecture"]["value"])
    p.pref_codes = list(prefectures.keys())
    sort(p.pref_codes)
    if p.tiers:
        raise NotImplementedError("tiers on: _create_tiers is py/tiers/start/create.py's")
    if p.households:
        return p._create_households(prefectures, n_per)
    AS = P.AGES * P.SEXES
    cum = PArr("f64")
    cum.resize(AS)
    tot = 0.0
    for i in range(AS):
        tot += p.cohort[i]
        cum[i] = tot
    p.n = len(p.pref_codes) * n_per
    p._resize(p.n)
    i = 0
    for code in p.pref_codes:
        popn = float(prefectures[code]["pop_thousand"]) * 1000.0
        p.pref_pop[int(code)] = popn
        for k in range(n_per):
            u = keyed.u(p.seed_v, "cohort", int(code), k, 0) * tot
            cell = 0
            while cell < AS - 1 and cum[cell] < u:
                cell += 1
            a = cell // P.SEXES
            s = cell % P.SEXES
            p.pref[i] = int(code)
            p.k_in_pref[i] = k
            p.age[i] = a
            p.sex[i] = s
            p.pid[i] = keyed.pid(p.seed_v, int(code), p.base_year - a, s, k)
            p.weight[i] = popn / float(n_per)
            p._draw_attributes(i)
            p._draw_traits(i)
            p._draw_dream(i)
            i += 1
    _ranks(p)
    for j in range(p.n):
        p._compose_drives(j)
        p._init_states(j)
    REL.build(p)
    GRP.seed_groups(p)
    return ""


# people.gd 304
def food_price_response(p, i):
    return DM.pow(1.0 + maxf(-0.5, p.believed_food_rise(i)), p.food_elasticity) if p.food_elasticity != 0.0 else 1.0


# people.gd 1079
def cost_of_living(p, i):
    return p._cost(p.hh_kind[i], p.hh_size[i])


# people.gd 1620
def food_plan(p):
    tot = 0.0
    for i in range(p.n):
        if p.age[i] < 18:
            continue
        factor = [0.85, 1.0, 1.2][p.plan[i]] * p.food_price_response(i)
        tot += fdiv(p.weight[i] * p.cost_of_living(i), p.price_index) / maxf(1.0, p.hh_size[i]) * factor * p.basket[i * 4]
    return tot


# people.gd 1630
def supply(p):
    if math.isnan(p.food_plan_start):
        p.food_plan_start = p.food_plan()
    lf = 0.0
    searching = 0.0
    for i in range(p.n):
        if p.employment[i] >= P.EMP_REGULAR and p.employment[i] <= P.EMP_UNEMPLOYED:
            lf += p.weight[i]
            if p.search[i] == 1:
                searching += p.weight[i]
    unions = 0
    demanding = 0
    for g in p.groups:
        if int(g["kind"]) == GRP.G_UNION and int(g["members"]) > 0:
            unions += 1
    for r in p.group_log:
        if str(r["kind"]) == "wage_demand" and int(r["month"]) == p.month - 1:
            demanding += 1
    return {"search_share": searching / maxf(1.0, lf), "wage_demand_share": float(demanding) / maxf(1.0, float(unions)),
            "scales": {"food_products": p.food_plan() / maxf(1e-9, p.food_plan_start)}}


# people.gd 1652
def quantiles(p, values, idx, qs=(0.1, 0.5, 0.9)):
    rows = []
    tot = 0.0
    for i in idx:
        rows.append([values[i], p.weight[i], p.pid[i]])
        tot += p.weight[i]
    sort_custom(rows, lambda a, b: float(a[0]) < float(b[0]) if float(a[0]) != float(b[0]) else int(a[2]) < int(b[2]))
    out = []
    for q in qs:
        q = float(q)
        acc = 0.0
        v = float(rows[len(rows) - 1][0]) if len(rows) > 0 else 0.0
        for r in rows:
            acc += float(r[1])
            if acc >= q * tot:
                v = float(r[0])
                break
        out.append(v)
    return out


# people.gd 1681
def deficit_column(p, name):
    d = P.DRIVES.index(name)
    out = PArr("f64")
    out.resize(p.n)
    for i in range(p.n):
        out[i] = p.dd[i * P.ND + d]
    return out


# people.gd 1691
def summary(p, code=-1):
    idx = []
    tot = 0.0
    unemp = 0.0
    lf = 0.0
    dreams_active = 0.0
    pres = 0.0
    for i in range(p.n):
        if code >= 0 and p.pref[i] != code:
            continue
        idx.append(i)
        tot += p.weight[i]
        if p.employment[i] == P.EMP_UNEMPLOYED:
            unemp += p.weight[i]
        if p.employment[i] >= P.EMP_REGULAR and p.employment[i] <= P.EMP_UNEMPLOYED:
            lf += p.weight[i]
        if p.dream_kind[i] >= 0 and p.dream_status[i] == 0:
            dreams_active += p.weight[i]
        pres += p.weight[i] * p.pressure(i)
    out = {"persons": len(idx), "population": tot, "unemployment_rate": unemp / maxf(1.0, lf),
           "dreams_active_share": dreams_active / maxf(1.0, tot), "pressure_mean": pres / maxf(1.0, tot)}
    inc = PArr("f64")
    inc.resize(p.n)
    for i in idx:
        inc[i] = fdiv(p.income[i], p.price_index)
    out["real_income_p10_p50_p90"] = p.quantiles(inc, idx)
    for name in ["anxiety", "discontent", "hope", "joy", "trust"]:
        out[name + "_p10_p50_p90"] = p.quantiles(p.emotion_column(name), idx)
    out["economic_security_deficit_p10_p50_p90"] = p.quantiles(p.deficit_column("economic_security"), idx)
    acts = {}
    for i in idx:
        nm = ACT.ACTIONS[p.last_action[i]]
        acts[nm] = float(acts.get(nm, 0.0)) + p.weight[i] / maxf(1.0, tot)
    out["last_action_shares"] = acts
    known = 0.0
    cc = 0.0
    bel = PArr("f64")
    bel.resize(p.n)
    known_idx = []
    for i in idx:
        cc += p.weight[i] * p.contact_count(i)
        if p.belief_known[i * REL.NF] == 1:
            known += p.weight[i]
            bel[i] = p.belief[i * REL.NF]
            known_idx.append(i)
    out["contacts_mean"] = cc / maxf(1.0, tot)
    out["food_price_known_share"] = known / maxf(1.0, tot)
    out["food_price_belief_p10_p50_p90"] = p.quantiles(bel, known_idx) if len(known_idx) > 0 else [0.0, 0.0, 0.0]
    mem_w = 0.0
    mov_w = 0.0
    for i in idx:
        if GRP.memberships(p, i) > 0:
            mem_w += p.weight[i]
        if p.in_movement(i):
            mov_w += p.weight[i]
    out["in_a_group_share"] = mem_w / maxf(1.0, tot)
    out["in_a_movement_share"] = mov_w / maxf(1.0, tot)
    return out


# people.gd 1750
def _b64(arr):
    return base64.b64encode(struct.pack(_PACK[arr.kind] % len(arr), *arr)).decode("ascii")


# people.gd 1754
def to_dict(p):
    if p.tiers:
        raise NotImplementedError("the save's _tiers_dict is the tiers port's")
    packed = {"i64": {}, "i32": {}, "f64": {}}
    for f in p.fields():
        packed[str(f[1])][str(f[0])] = _b64(getattr(p, str(f[0])))
    out = {"state": p.state, "seed": p.seed_v, "base_year": p.base_year, "n": p.n, "month": p.month, "price_index": p.price_index,
           "wage_index": p.wage_index, "food_plan_start": p.food_plan_start, "pref_codes": list(p.pref_codes), "pref_pop": dict(p.pref_pop),
           "pension": copy.deepcopy(p.pension), "i64": packed["i64"], "i32": packed["i32"], "f64": packed["f64"],
           "events": copy.deepcopy(p.events), "trace_pids": list(p.trace_pids), "trace": copy.deepcopy(p.trace), "decisions": copy.deepcopy(p.decisions),
           "refusals": copy.deepcopy(p.refusals), "groups": copy.deepcopy(p.groups), "group_log": copy.deepcopy(p.group_log)}
    for k, v in p._households_dict().items():
        if k not in out:
            out[k] = v
    return out


# people.gd 1770
def _households_dict(p, numeric=False):
    if not p.households:
        return {}
    out = {}
    for h in p.household_fields():
        if numeric and bool(h[4]):
            out[str(h[1])] = list(getattr(p, str(h[0])))
        elif not numeric:
            out[str(h[1])] = _b64(getattr(p, str(h[0])))
    if numeric:
        out["life_log_n"] = len(p.life_log)
    else:
        out["n"] = p.hh_n
        out["next_k"] = dict(p.next_k)
        out["life_log"] = copy.deepcopy(p.life_log)
        out["lc_births"] = copy.deepcopy(p.lc_births)
    return {"households": out}


for _f in (load_spec, create, food_price_response, cost_of_living, food_plan, supply, quantiles, deficit_column, summary, to_dict,
           _households_dict):
    setattr(P, _f.__name__, _f)


class Persons:
    # The integrated month's five persons methods (INTEGRATED_MONTH_PLAN §5) over one P
    def __init__(self, p):
        self.p = p
        self.env_seen = {}

    @classmethod
    def create(cls, key, seed, cohort, qx, prefectures, n_per, year, households=False):
        p = P()
        p.tiers = False
        p.households = bool(households)
        err = p.create(key, seed, cohort, qx, prefectures, n_per, year)
        if err != "":
            raise ValueError(err)
        return cls(p)

    @classmethod
    def from_tree(cls, d):
        # The persons as the integrated oracle writes them at a month's end (oracle_dump_month.gd's mMM_persons: the persons' fields,
        # the records as "rec.", pref_codes, base_year, seed_v, spec), with what load_spec reads beside the spec
        p = P()
        p.tiers = False
        p.households = False
        for k, v in digest.load(d).items():
            setattr(p, k[4:] if k.startswith("rec.") else k, from_tree(v))
        cm = load.load_json(country.load(p.state).path("commodities"))
        p.food_elasticity = float(cm["commodities"]["food_products"]["demand_elasticity"])
        return cls(p)

    def hashes(self):
        # The persons' per-field hashes in oracle_dump_month.gd's names (PERSONS_PORT_PLAN §2, "rec." for the records)
        p = self.p
        names = [str(r[0]) for r in p.fields()] + ["n", "month", "price_index", "wage_index", "food_plan_start", "pref_pop", "pension",
                                                    "groups"]
        out = {n: trace.sha(getattr(p, n)) for n in names}
        for n in ("decisions", "refusals", "events", "trace", "group_log"):
            out["rec." + n] = trace.sha(getattr(p, n))
        if p.households:
            for h in p.household_fields():
                out["hh." + str(h[0])] = trace.sha(getattr(p, str(h[0])))
        return out

    @property
    def month(self):
        return self.p.month

    def supply(self):
        return self.p.supply()

    def step(self, env):
        self.env_seen[self.p.month + 1] = env
        MONTH.step(self.p, env)

    def summary(self, code=-1):
        return self.p.summary(code)

    def fields(self):
        return self.p.fields()

    def to_dict(self):
        return self.p.to_dict()
