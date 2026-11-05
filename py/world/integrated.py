# The integrated month (INTEGRATED_MONTH_PLAN): modern_world.gd advance_to's persons-on body over py/world's World, py/econ's month and
# the persons through §5's five methods, with a hook after each boundary step
from . import actors as MA
from . import data as MD
from .gdtypes import F64, field_hashes, load_state
from .world import World

DUMMY_IFACE = {"month": [], "release": []}
# Why a name and not the literal of modern_world.gd: row I-mf3 (§7) sets it to 1000.5 to show the release glue is compared
RELEASE_T_PER_KT = 1000.0


class EconLink:
    # py/econ's EconMonth as py/world's world calls it. Why not a change to py/world: its econ calls (check_enforcement, to_dict) are
    # EconReplay's, and the world port stays as verified
    def __init__(self, econ):
        self.e = econ

    def __getattr__(self, name):
        return getattr(self.e, name)

    def check_enforcement(self, month):
        pass

    def to_dict(self):
        return {}


class PersonsStub:
    # The persons' five methods from the oracle's iface (§5): the supply at M4, the summary at M8; step records the env it was given
    def __init__(self, iface_of):
        self.iface_of = iface_of
        self.month = 0
        self.env_seen = {}

    def supply(self):
        s = self.iface_of(self.month + 1)["supply"]
        return {"search_share": s["search_share"], "wage_demand_share": s["wage_demand_share"], "scales": dict(s["scales"])}

    def step(self, env):
        self.env_seen[self.month + 1] = env
        self.month += 1

    def summary(self):
        return self.iface_of(self.month)["summary"]

    def fields(self):
        return []

    def to_dict(self):
        return {"month": self.month}


def from_oracle(world_dir, econ, persons):
    # Why the persons' params out for the restore and back after: py/world's create refuses the persons (W1-p is replayed there); the
    # world's own params, persons keys included, are the oracle's and enter the tree
    st = load_state(world_dir)
    st2 = dict(st)
    st2["params"] = {k: v for k, v in st["params"].items() if not str(k).startswith("people")}
    w = World.from_dict(st2, DUMMY_IFACE)
    w.params = st["params"]
    w.econ = EconLink(econ)
    w.people = persons
    return w


def hashes(w):
    from econ import state as ES
    return {"world": field_hashes(w.tree()), "econ": ES.field_hashes(w.econ.e)}


def advance_to(w, day, hook=None, order=None):
    # advance_to's body (modern_world.gd), persons on; hook(tag) after B1-B5; order="s4_first" runs M9 before M4-M8 (row I-mf)
    S = len(MD.SOURCES)
    field = w.field
    sup = F64([0.0] * (field.E * S))
    while field.day < day:
        for e in range(field.E):
            for s in range(S):
                sup[e * S + s] = field.supply_of(e, s)
        field.step()
        w.register.observe_day(field, sup)
        logged = len(w.status.lever_log)
        w.status.step()
        for i in range(logged, len(w.status.lever_log)):
            row = w.status.lever_log[i]
            if str(row[4]) == "applied":
                w.chronicle.add(field.day, "lever_applied", str(row[1]), "field", {"lever": str(row[2]), "value": float(row[3])}, "lead time over; the response function ran")
                if str(row[2]) == "rice_stock_release" and w.econ is not None and float(row[3]) > 0.0:
                    got = w.econ.release_state_rice(field.day // 30, float(row[3]) * RELEASE_T_PER_KT)
                    w.chronicle.add(field.day, "release", "JPN", "state", {"rice_t": got, "asked_kt": float(row[3])}, "食糧法: the MA stock to the market")
        if w.econ is not None and MA.is_month_end(field.day):
            if hook:
                hook("b01")
            if order == "s4_first":
                w._s4_month(logged)
            if w.people is not None:
                psup = w.people.supply()
                w.econ.labour.receive(float(psup["search_share"]), float(psup["wage_demand_share"]), psup["scales"])
            w.econ.step()
            if w.people is not None:
                w.status.ind["JPN"]["unemployment_rate"] = w.econ.labour.u
                lf = w.status.value("JPN", "employed") + w.status.value("JPN", "unemployed")
                w.status.ind["JPN"]["unemployed"] = lf * w.econ.labour.u
                w.status.ind["JPN"]["employed"] = lf * (1.0 - w.econ.labour.u)
            if hook:
                hook("b02")
            for r in w.econ.chronicle_rows(w.data.base_year, w.econ.world.month - 1):
                if str(r["ledger"]) == "goods" and str(r["field"]) == "price":
                    w.chronicle.add(field.day, "price", "JPN", "market", {"commodity": str(r["key"]).split("|")[0], "before": r["before"], "after": r["after"]}, str(r["why"]))
            if w.people is not None:
                applied_ids = [str(w.status.lever_log[i][2]) for i in range(logged, len(w.status.lever_log)) if str(w.status.lever_log[i][4]) == "applied"]
                w.people.step({"inflation_month": float(w.econ.world.env.get("inflation", 0.02)) / 12.0, "food_price_yoy": float(w.econ.world.env.get("food_price_yoy", 0.0)),
                               "unemployment_rate": w.econ.labour.u, "wage_index": w.econ.labour.wage_index, "levers": applied_ids, "cohort": w.status.cohort["JPN"]})
                sm = w.people.summary()
                w.chronicle.add(field.day, "people", "JPN", "persons", {"anxiety_p50": float(sm["anxiety_p10_p50_p90"][1]), "discontent_p50": float(sm["discontent_p10_p50_p90"][1]),
                                "real_income_p50": float(sm["real_income_p10_p50_p90"][1]), "pressure_mean": float(sm["pressure_mean"]), "unemployment_rate": float(sm["unemployment_rate"])},
                                "weighted quantiles over the representative persons")
                w.chronicle.add(field.day, "labour", "JPN", "economy", {"unemployment_rate": w.econ.labour.u, "wage_index": w.econ.labour.wage_index,
                                "food_demand_scale": float(w.econ.labour.demand_scale.get("food_products", 1.0)), "search_share": w.econ.labour.search_share},
                                "the labour market's month (T rules): the persons' supply in, unemployment and the wage index out")
            if hook:
                hook("b03")
            if order != "s4_first":
                w._s4_month(logged)
            if hook:
                hook("b04")
        w.chronicle.observe_field(field, w.data.keys)
        if field.day % 365 == 0:
            w.register.close_year(w, w.data.base_year + field.day // 365 - 1)
            for k in w.status.entities:
                w.chronicle.add(field.day, "year_close", k, "field", {"pop_total": w.status.value(k, "pop_total"), "gov_debt_total": w.status.value(k, "gov_debt_total"),
                                "niip": w.status.value(k, "niip"), "debt_to_gdp": w.status.value(k, "debt_to_gdp")}, "the year's statuses")
        if MA.is_month_end(field.day):
            w._month()
            if hook:
                hook("b05")


def advance_forced(w, day, forces, hook=None, order=None):
    # oracle_dump_month.gd's MONTH_FORCE (§7): at the end of each forced day inside (field.day, day], status.set_lever, then on to day
    d0 = w.field.day
    for fd, k, lid, v in forces:
        if d0 < int(fd) <= day:
            advance_to(w, int(fd), hook, order)
            w.status.set_lever(str(k), str(lid), float(v))
    advance_to(w, day, hook, order)
