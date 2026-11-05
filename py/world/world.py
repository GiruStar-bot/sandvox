# modern_world.gd: create, the day, the month's decisions, S4' (enforcement, approval, elections), the save, and this port's tree
# (WORLD_PORT_PLAN §2); the economy is the oracle's, replayed from iface.json (§3)
from . import actors as MA
from . import canon as CANON
from . import ledger
from . import data as MD
from .actors import Actors
from .brain import Brain
from .chain import GOODS_LICENSED, INPUTS
from .chronicle import Chronicle
from .costs import Costs
from .data import ModernData, exists
from .field import Field, PROJECT_KINDS
from .gdtypes import F64, NAN, deep, is_finite, sha, unbits
from .polity.cabinet import Cabinet
from .polity.election import Election
from .polity.enforcement import Enforcement
from .polity.organs import Organs
from .polity.public import Public
from .publish import Register
from .status import Status
from .view import View
from ._core import DM, gd

MIN_BUILD_CAP_MW = 1000.0
FAB_BUILD_CAP = 0.1
SPLIT = ("field", "actors", "register", "status")
DROP = ("run", "econ", "people")
FREE_TEXT = ("why", "line")
NUDGE_FOOD = [-1]   # W-mf2: the replayed month whose food_price_yoy is moved by one ulp


def _f(node):
    return unbits(node["f"])


class _Obj:
    pass


class EconReplay:
    # The economy as the oracle ran it (§3): each month's outputs, the release answers and the econ actors' stocks around enforcement.
    # Why not the econ port: it is Eくん's and parity of this layer must not wait on it (ECON_PORT_PLAN E2's method)
    def __init__(self, iface):
        self.months = iface["month"]
        self.releases = iface["release"]
        self.taps = iface.get("enforcement_dec", [])
        self.cursor = 0
        self.release_cursor = 0
        self.world = _Obj()
        self.world.month = 0
        self.world.env = {}
        self.labour = None
        self.actors = []
        self.mismatch = []
        self.day = 0

    def release_state_rice(self, month, qty_t):
        r = self.releases[self.release_cursor]
        self.release_cursor += 1
        return _f(r["rice_t"])

    def step(self):
        row = self.months[self.cursor]
        self.cursor += 1
        self.world.month = int(row["world_month"]["i"])
        env = {}
        if row["has_inflation"]:
            env["inflation"] = _f(row["inflation"])
        if row["has_food_price_yoy"]:
            env["food_price_yoy"] = _f(row["food_price_yoy"])
            if self.cursor == NUDGE_FOOD[0]:
                import math
                env["food_price_yoy"] = math.nextafter(env["food_price_yoy"], 1e300)
        self.world.env = env
        self._prices = [{"ledger": "goods", "field": "price", "key": p[0], "before": _f(p[1]), "after": _f(p[2]), "why": ""} for p in row["prices"]]
        tap = self.taps[self.cursor - 1] if self.cursor - 1 < len(self.taps) else None
        self.actors = []
        self._after = None
        if tap is not None:
            for r in tap["before"]:
                a = _Obj()
                a.id = r[0]
                a.stocks = {}
                if r[1]:
                    a.stocks["arrears"] = r[2]
                if r[3]:
                    a.stocks["procedure_until"] = r[4]
                self.actors.append(a)
            self._after = tap["after"]
            self._tap_month = tap["month"]

    def check_enforcement(self, month):
        # W2-i: the ported rule leaves the stocks as the oracle's after-row
        if self._after is None:
            return
        for a, r in zip(self.actors, self._after):
            got = [a.id, "arrears" in a.stocks, float(a.stocks.get("arrears", 0.0)), "procedure_until" in a.stocks, a.stocks.get("procedure_until", -1)]
            if sha(got) != sha(list(r)) or self._tap_month != month:
                self.mismatch.append((month, got, r))

    def chronicle_rows(self, base_year, m):
        return self._prices

    def seed_shocks(self, seed, years):
        pass

    def to_dict(self):
        return {"cursor": self.cursor, "release_cursor": self.release_cursor}

    def from_dict(self, d):
        self.cursor = int(d["cursor"]) - 1
        self.release_cursor = int(d["release_cursor"])
        if self.cursor >= 0:
            self.step()
        else:
            self.cursor = 0


def load_iface(path):
    import json
    from .gdtypes import dec
    with open(path, encoding="utf-8") as f:
        iface = json.load(f)
    iface["enforcement_dec"] = dec(iface.get("enforcement", {"a": []})) if iface.get("enforcement") else []
    return iface


class World:
    def __init__(self):
        self.data = None
        self.field = None
        self.actors = None
        self.register = None
        self.params = {}
        self.seats = {}
        self.status = None
        self.brains = {}
        self.chronicle = None
        self.polity = {}
        self.cabinet = None
        self.econ = None
        self.enforcement = None
        self.public = None
        self.election = None
        self.people = None
        self.unemp_prev = NAN
        self.last_election_month = 0
        self.log = []
        self.error = ""
        self.view_salt = b""
        self.iface = None

    def create(self, year, p=None, iface=None):
        p = p or {}
        self.iface = iface
        cg = p.get("compute_growth", "persistence")
        self.params = {"compute_growth": "persistence" if cg == "persistence" else float(cg), "rules": str(p.get("rules", "r55")),
                       "demand_growth": str(p.get("demand_growth", "cagr5"))}
        if self.params["rules"] == "r55":
            self.params["pipeline"] = "lead"
            self.params["pipeline_mix"] = str(p.get("pipeline_mix", "logit"))
            self.params["fab_cost"] = str(p.get("fab_cost", "ref"))
            self.params["coal_retire_yr"] = 1.0 / MA.COAL_AGE_YR
        self.view_salt = bytes.fromhex(str(p.get("view_salt", "")))
        if bool(p.get("people", False)):
            self.error = "py world: the persons' interface replay (W1-p) is not ported yet"
            return self.error
        if self.params["rules"] not in MA.RULE_SETS:
            self.error = "modern world: unknown rule set " + self.params["rules"]
            return self.error
        self.data = ModernData()
        self.error = self.data.load_year(year, self.params["demand_growth"])
        if self.error != "":
            return self.error
        data = self.data
        self.field = Field()
        self.field.create(data, self.params)
        self.actors = Actors()
        self.actors.rule_set = self.params["rules"]
        if self.params["rules"] == "r55":
            self.actors.costs = Costs()
            self.actors.costs.create(data)
            self.actors.load_alliances(data, self.actors.costs.r56["alliances"])
            r57 = CANON.load_json_m("res://data/modern/r57.json")
            y = str(data.base_year)
            if y in r57["world_wspm_start"]:
                cost_key = str(self.params["fab_cost"])
                self.actors.fab = {"kappa": float(r57["kappa"]["value"]), "revenue": float(r57["revenue_usd_start"][y]["value"]),
                                   "world_wspm": float(r57["world_wspm_start"][y]["value"]), "cost_per_wspm": float(r57["cost_per_wspm"][cost_key]),
                                   "public_share": r57["public_share"]}
                self.field.util_base = float(r57["utilisation"]["base"])
                self.field.util_top = float(r57["utilisation"]["top"])
                self.field.fab_ramp_days = int(r57["ramp_days"]["value"])
            for g20 in self.actors.costs.r56["restrictions"]["g20"]:
                self.actors.restrict_p[data.index_of(str(g20))] = float(self.actors.costs.r56["restrictions"]["per_state_good_yr"])
            if self.params["pipeline_mix"] == "logit":
                self.field.pipe_mix = self.actors.pipeline_mix(self.field)
            k = data.index_of("JPN") * len(INPUTS) + INPUTS.index("gallium")
            self.field.input_target[k] = MA.JOGMEC_DAYS
            self.field.input_stock[k] = MA.JOGMEC_DAYS
        self.register = Register()
        self.register.create(data)
        self.status = Status()
        self.error = self.status.load(year, data.keys)
        if self.error != "":
            return self.error
        self.chronicle = Chronicle()
        self.chronicle.create(year)
        for k in self.status.entities:
            self.brains[data.index_of(k)] = Brain()
            org = Organs()
            if org.load_state(k) == "":
                self.polity[k] = org
        if "JPN" in self.polity:
            self.status.legal_check = lambda lid, met: self.polity["JPN"].may_pull_lever(lid, met)
            self.cabinet = Cabinet()
            self.cabinet.setup(self.polity["JPN"])
            if exists("res://data/modern/econ/crop_farming_jpn.json"):
                if iface is None:
                    self.error = "py world: this world runs the economy; give the oracle's iface.json (WORLD_PORT_PLAN §3)"
                    return self.error
                self.econ = EconReplay(iface)
                if "shock_seed" in p:
                    self.params["shock_seed"] = int(p["shock_seed"])
                    self.params["shock_years"] = int(p.get("shock_years", 10))
                    self.econ.seed_shocks(int(self.params["shock_seed"]), int(self.params["shock_years"]))
                self.enforcement = Enforcement()
                self.public = Public()
                self.public.load_state("JPN", self.status.value("JPN", "cabinet_approval"))
                self.election = Election()
                if self.election.load_state("JPN") != "":
                    self.election = None
        return ""

    def advance_to(self, day):
        S = len(MD.SOURCES)
        field = self.field
        sup = F64([0.0] * (field.E * S))
        while field.day < day:
            for e in range(field.E):
                for s in range(S):
                    sup[e * S + s] = field.supply_of(e, s)
            field.step()
            self.register.observe_day(field, sup)
            logged = len(self.status.lever_log)
            self.status.step()
            for i in range(logged, len(self.status.lever_log)):
                row = self.status.lever_log[i]
                if str(row[4]) == "applied":
                    self.chronicle.add(field.day, "lever_applied", str(row[1]), "field", {"lever": str(row[2]), "value": float(row[3])}, "lead time over; the response function ran")
                    if str(row[2]) == "rice_stock_release" and self.econ is not None and float(row[3]) > 0.0:
                        got = self.econ.release_state_rice(field.day // 30, float(row[3]) * 1000.0)
                        self.chronicle.add(field.day, "release", "JPN", "state", {"rice_t": got, "asked_kt": float(row[3])}, "食糧法: the MA stock to the market")
            if self.econ is not None and MA.is_month_end(field.day):
                self.econ.step()
                for r in self.econ.chronicle_rows(self.data.base_year, self.econ.world.month - 1):
                    if str(r["ledger"]) == "goods" and str(r["field"]) == "price":
                        self.chronicle.add(field.day, "price", "JPN", "market", {"commodity": str(r["key"]).split("|")[0], "before": r["before"], "after": r["after"]}, str(r["why"]))
                self._s4_month(logged)
            self.chronicle.observe_field(field, self.data.keys)
            if field.day % 365 == 0:
                self.register.close_year(self, self.data.base_year + field.day // 365 - 1)
                for k in self.status.entities:
                    self.chronicle.add(field.day, "year_close", k, "field", {"pop_total": self.status.value(k, "pop_total"), "gov_debt_total": self.status.value(k, "gov_debt_total"),
                                       "niip": self.status.value(k, "niip"), "debt_to_gdp": self.status.value(k, "debt_to_gdp")}, "the year's statuses")
            if MA.is_month_end(field.day):
                self._month()

    def _s4_month(self, logged_before):
        m = self.econ.world.month - 1
        self.enforcement.step(m, self.econ)
        self.econ.check_enforcement(m)
        for ev in self.enforcement.events:
            if int(ev["month"]) == m:
                self.chronicle.add(self.field.day, str(ev["kind"]), "JPN", "enforcement", ev["facts"], str(ev["why"]))
        u = self.status.value("JPN", "unemployment_rate")
        du = 0.0 if self.unemp_prev != self.unemp_prev else (u - self.unemp_prev) * 100.0
        self.unemp_prev = u
        applied = []
        for i in range(logged_before, len(self.status.lever_log)):
            if str(self.status.lever_log[i][4]) == "applied":
                applied.append(str(self.status.lever_log[i][2]))
        ap = self.public.step(m, float(self.econ.world.env.get("food_price_yoy", 0.0)), du, applied)
        self.status.ind["JPN"]["cabinet_approval"] = ap
        if ledger.ACTIVE is not None and ("ind", "JPN", "cabinet_approval") in ledger.ACTIVE.sh:
            ledger.ACTIVE.start(("ind", "JPN", "cabinet_approval"), ap)
        if self.election is None:
            return
        ym = "%04d-%02d" % (self.data.base_year + m // 12, m % 12 + 1)
        jp = self.polity["JPN"]
        gov = list(jp.governing)
        d_ap = self.public.change_since(self.last_election_month)
        shares = self.election.vote_shares(gov, d_ap, du, 0.0)
        if ym == str(self.election.spec["houses"]["house_of_councillors"].get("next_election", "")):
            r = self.election.run_upper_house(shares)
            jp.seats["house_of_councillors"] = dict(r["composition"])
            jp.record(m, "election", "house_of_councillors", {"elected": r["elected"], "composition": r["composition"]}, "art. 46: half the house every three years")
            self.chronicle.add(self.field.day, "election", "JPN", "house_of_councillors", {"elected": r["elected"], "composition": r["composition"], "approval_change": d_ap}, "the half election; the governing share swung by the retrospective rule (T)")
            self.last_election_month = m
        lower_by = str(self.status.data["JPN"].get("indicators", {}).get("next_lower_house_election_by", {}).get("value", ""))
        if ym == lower_by:
            r2 = self.election.run_lower_house(shares)
            jp.seats["house_of_representatives"] = dict(r2["seats"])
            jp.record(m, "election", "house_of_representatives", {"seats": r2["seats"]}, "the general election")
            self.chronicle.add(self.field.day, "election", "JPN", "house_of_representatives", {"seats": r2["seats"], "approval_change": d_ap}, "the general election; the governing share swung by the retrospective rule (T)")
            self.last_election_month = m

    def _month(self):
        field = self.field
        self.actors.begin_month(field)
        for e in range(field.E):
            who = "rule"
            acts = []
            if e in self.seats:
                got = self.seats[e].actions(self, e)
                why = ""
                if isinstance(got, dict):
                    acts = got["actions"]
                    why = str(got["error"])
                else:
                    acts = got
                if why == "":
                    why = self.check_actions(e, acts)
                if why == "":
                    who = "seat"
                else:
                    self.log.append([field.day, self.data.keys[e], "refused", why])
                    acts = []
            if who == "rule":
                acts = self.actors.rule_actions(field, e)
                if e in self.brains and self.params["rules"] != "none":
                    thought = self.brains[e].think(self.brain_observation(e), self.status.catalog, self.status.menu(self.data.keys[e]), self.calendar(), field.day // 30)
                    for la in thought["actions"]:
                        why_not = self.check_actions(e, [la])
                        if why_not == "":
                            acts.append(la)
                        else:
                            self.brains[e].note_refused(str(la["id"]), field.day // 30)
                            self.chronicle.add(field.day, "lever_refused", self.data.keys[e], "rule brain", {"lever": str(la["id"]), "value": float(la["value"])}, why_not)
                    self.chronicle.add(field.day, "decision", self.data.keys[e], "rule brain", {"actions": deep(thought["actions"]), "order": thought["order"]},
                                       "; ".join(thought["why"]))
            if self.check_actions(e, acts) != "":
                self.log.append([field.day, self.data.keys[e], "refused", "rule: " + self.check_actions(e, acts)])
                continue
            self._apply(e, acts, who)

    def check_actions(self, e, acts):
        lever_changes = 0
        for a in acts:
            if not isinstance(a, dict) or "act" not in a:
                return "not an action"
            act = a
            kind_act = str(act["act"])
            if kind_act == "build":
                kind = str(act.get("kind", ""))
                if kind not in PROJECT_KINDS:
                    return "unknown project kind " + kind
                size = float(act.get("size", 0.0))
                if not is_finite(size) or size <= 0.0 or size > self.build_cap(e, kind):
                    return "size out of bounds for " + kind
                if kind == "transmission" and self.link_between(e, int(act.get("link_to", -1))) < 0:
                    return "transmission to an entity with no land border"
            elif kind_act == "order":
                if str(act.get("first", "")) not in ("dc", "fab"):
                    return "order first must be dc or fab"
            elif kind_act == "licence":
                g = str(act.get("good", ""))
                to = int(act.get("to", -1))
                if g not in GOODS_LICENSED:
                    return "unknown good " + g
                if to < 0 or to >= self.field.E or to == e:
                    return "no such destination"
                if type(act.get("open")) is not bool:
                    return "open must be true or false"
            elif kind_act == "lever":
                if not self.status.has(self.data.keys[e]):
                    return "no status file for this entity"
                lever_changes += 1
                why = self.status.check_lever(self.data.keys[e], str(act.get("id", "")), float(act.get("value", NAN)), lever_changes - 1)
                if why != "":
                    return why
            else:
                return "unknown act " + kind_act
        return ""

    def brain_observation(self, e):
        k = self.data.keys[e]
        own = dict(self.status.ind[k])
        own["unserved_share"] = self.field.unserved[e] / gd.maxf(1.0, self.field.demand[e])
        own["chip_short"] = 1.0 if self.field.chip_short else 0.0
        closed = 0.0
        for row in self.field.chain.closed_rows():
            if int(row[2]) == e:
                closed += 1.0
        own["licences_closed_against"] = closed
        return {"own_statuses": own}

    def calendar(self):
        out = {}
        for k in self.status.entities:
            row = self.status.data[k].get("indicators", {}).get("next_lower_house_election_by", {})
            by = str(row.get("value", ""))
            if len(by) >= 7:
                y = int(by[0:4])
                m = int(by[5:7])
                d = self.field.day
                now_m = (self.data.base_year + d // 365) * 12 + (d % 365) // 30 + 1
                out["months_to_lower_house_election"] = float(y * 12 + m - now_m)
        return out

    def build_cap(self, e, kind):
        f = self.field
        if kind == "fab":
            return gd.maxf(FAB_BUILD_CAP, 2.0 * f.fab_cap[e])
        mw = gd.maxf(MIN_BUILD_CAP_MW, f.base_demand(e) + f.dc_load(e) + f.fab_load(e))
        return mw * 24.0 if kind == "storage" else mw

    def link_between(self, a, b):
        f = self.field
        if b < 0 or b >= f.E:
            return -1
        for l in f.links_of[a]:
            if f.link_a[l] == b or f.link_b[l] == b:
                return l
        return -1

    def _apply(self, e, acts, who):
        f = self.field
        for act in acts:
            if str(act["act"]) == "build":
                kind = str(act["kind"])
                f.add_project(e, kind, float(act["size"]), self.link_between(e, int(act.get("link_to", -1))) if kind == "transmission" else -1)
            elif str(act["act"]) == "order":
                f.fab_first[e] = 1 if str(act["first"]) == "fab" else 0
            elif str(act["act"]) == "lever":
                self.status.set_lever(self.data.keys[e], str(act["id"]), float(act["value"]))
                self.chronicle.add(f.day, "lever_set", self.data.keys[e], who, {"lever": str(act["id"]), "value": float(act["value"])}, "applies after its lead time")
            else:
                f.chain.set_licence(e, str(act["good"]), int(act["to"]), bool(act["open"]))
                self.chronicle.add(f.day, "licence", self.data.keys[e], who, {"good": str(act["good"]), "to": self.data.keys[int(act["to"])], "open": bool(act["open"])}, "")
            self.log.append([f.day, self.data.keys[e], who, dict(act)])
        self.actors.note_applied(e, acts, who == "rule")

    def make_view(self, view_key):
        v = View()
        v.load_view(view_key, self.data, self.view_salt)
        return v

    def population(self, e, at_day=-1):
        d = self.field.day if at_day < 0 else at_day
        return self.data.population[e] * DM.pow(1.0 + self.data.pop_growth[e], float(d - 182 + 365 * (self.data.base_year - self.data.data_year)) / 365.0)

    def to_dict(self):
        br = {str(e): self.brains[e].to_dict() for e in self.brains}
        pol = {k: self.polity[k].to_dict() for k in self.polity}
        out = {"year": self.data.base_year, "params": dict(self.params), "field": self.field.to_dict(), "actors": self.actors.to_dict(), "register": self.register.to_dict(),
               "log": deep(self.log), "status": self.status.to_dict(), "brains": br, "chronicle": self.chronicle.to_dict(), "polity": pol,
               "cabinet": self.cabinet.to_dict() if self.cabinet is not None else {}, "econ": self.econ.to_dict() if self.econ is not None else {},
               "enforcement": self.enforcement.to_dict() if self.enforcement is not None else {}, "public": self.public.to_dict() if self.public is not None else {},
               "s4": {"unemp_prev": self.unemp_prev, "last_election_month": self.last_election_month}, "run": {"view_salt": self.view_salt.hex()}}
        return out

    @staticmethod
    def from_dict(st, iface=None):
        w = World()
        p = dict(st["params"])
        p["view_salt"] = str(st.get("run", {}).get("view_salt", ""))
        if w.create(int(st["year"]), p, iface) != "":
            return w
        w.field.from_dict(st["field"])
        w.actors.from_dict(st["actors"])
        w.register.from_dict(st["register"])
        w.log = deep(st["log"])
        if "status" in st:
            w.status.from_dict(st["status"])
            for es in st.get("brains", {}):
                if int(es) in w.brains:
                    w.brains[int(es)].from_dict(st["brains"][es])
            w.chronicle.from_dict(st.get("chronicle", {}))
            for k in st.get("polity", {}):
                if k in w.polity:
                    w.polity[k].from_dict(st["polity"][k])
            if w.cabinet is not None and "cabinet" in st:
                w.cabinet.from_dict(st["cabinet"])
            if w.econ is not None and "econ" in st and st["econ"]:
                w.econ.from_dict(st["econ"])
            if w.enforcement is not None and "enforcement" in st:
                w.enforcement.from_dict(st["enforcement"])
                w.public.from_dict(st.get("public", {}))
                w.unemp_prev = float(st.get("s4", {}).get("unemp_prev", NAN))
                w.last_election_month = int(st.get("s4", {}).get("last_election_month", 0))
        return w

    def tree(self):
        st = self.to_dict()
        for k in DROP:
            st.pop(k, None)
        sd = st["status"]
        sd["ind"] = {k: dict(self.status.ind[k]) for k in self.status.entities}
        sd["cohort"] = {k: F64(self.status.cohort[k]) for k in self.status.entities}
        out = {}
        for k in st:
            if k in SPLIT:
                for k2 in st[k]:
                    out[k + "." + k2] = _strip(st[k][k2])
            else:
                out[k] = _strip(st[k])
        return out


def _strip(v):
    t = type(v)
    if isinstance(v, dict):
        return {k: _strip(x) for k, x in v.items() if not (isinstance(k, str) and k in FREE_TEXT)}
    if t is list:
        return [_strip(x) for x in v]
    return v
