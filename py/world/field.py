# modern_field.gd: the daily field (loads, supply, balance over links and storage, fabs, chips, servers, projects)
from . import data as MD
from . import ledger
from .chain import Chain, INPUTS
from ._core import DM, gd
from .gdtypes import F64, I32, U8, deep

SERVER_LIFE_DAYS = 5 * 365
LINK_SHARE = 0.05
COAL = 0
GAS = 1
PROJECT_KINDS = ["coal", "gas", "oil", "nuclear", "hydro", "wind", "solar", "bioenergy", "other_renewable", "storage", "dc",
                 "fab", "transmission"]
_PER_E = ["base0", "demand_growth", "net_imports", "storage_cap", "storage", "dc_it", "servers", "chips", "fab_cap", "atp", "water_l",
          "demand", "discharge", "dc_served", "fab_served", "unserved", "spilled", "fab_out", "withheld"]


class Field:
    SERVER_LIFE_DAYS = SERVER_LIFE_DAYS
    PROJECT_KINDS = PROJECT_KINDS

    def __init__(self):
        self.data = None
        self.chain = None
        self.E = 0
        self.day = 0
        self.pue = F64()
        self.k_it = 0.0
        self.u_max = 0.0
        self.cgrow = F64()
        self.pipeline = "always"
        self.pipe_mix = F64()
        self.pipeline_days = I32()
        self.coal_retire_yr = 0.0
        self.input_stock = F64()
        self.input_target = F64()
        self.servers0 = F64()
        self.fab_mw_per_unit = 0.0
        self.water_l_per_mwh = 0.0
        self.supply0 = F64()
        self.mix = F64()
        self.gen0 = F64()
        self.supply_built = F64()
        for a in _PER_E:
            setattr(self, a, F64())
        self.link_a = I32()
        self.link_b = I32()
        self.link_cap = F64()
        self.links_of = []
        self.util_base = 1.0
        self.util_top = 1.0
        self.fab_ramp_days = 0
        self.chip_short = False
        self._ramps = []
        self.fab_first = U8()
        self.projects = []
        self.done_projects = 0
        self._next_finish_day = -1
        self.link_flow = F64()

    def create(self, d, params=None):
        params = params or {}
        self.data = d
        self.chain = Chain()
        E = self.E = d.entity_count()
        S = len(MD.SOURCES)
        sc = d.scalars
        self.pue = F64(d.pue)
        self.u_max = float(sc["dc_electricity_twh_2024"]["value"]) * 1e6 / MD.HOURS / (float(sc["dc_capacity_gw_2024"]["value"]) * 1000.0)
        cg = params.get("compute_growth", 0.0)
        self.cgrow = F64([0.0] * E)
        for ce in range(E):
            self.cgrow[ce] = d.dc_growth[ce] if cg == "persistence" else float(cg)
        self.pipeline = str(params.get("pipeline", "always"))
        self.coal_retire_yr = float(params.get("coal_retire_yr", 0.0))
        self.pipeline_days = I32([0] * S)
        for ps in range(S):
            self.pipeline_days[ps] = int(d.lead_days[MD.SOURCES[ps]]["days"])
        self.input_stock = F64([0.0] * (E * len(INPUTS)))
        self.input_target = F64(self.input_stock)
        self.fab_mw_per_unit = float(sc["semi_electricity_twh"]["value"]) * 1e6 / MD.HOURS
        self.water_l_per_mwh = float(sc["dc_water_bn_l_per_yr"]["value"]) * 1e9 / (float(sc["dc_electricity_twh_2024"]["value"]) * 1e6)
        self.supply0 = F64(d.supply_mw)
        self.mix = F64([0.0] * (E * S))
        self.gen0 = F64([0.0] * E)
        for e0 in range(E):
            for s0 in range(S):
                self.gen0[e0] += self.supply0[e0 * S + s0]
            for s1 in range(S):
                self.mix[e0 * S + s1] = self.supply0[e0 * S + s1] / self.gen0[e0] if self.gen0[e0] > 0.0 else 0.0
        self.supply_built = F64([0.0] * (E * S))
        for a in _PER_E:
            setattr(self, a, F64([0.0] * E))
        no_demand = d.no_data.get("demand", [])
        for e in range(E):
            dc_share = d.share_of(e, "dc_electricity")
            self.servers[e] = d.dc_world_twh * 1e6 / MD.HOURS * dc_share / self.pue[e]
            self.dc_it[e] = self.servers[e] / self.u_max
            self.fab_cap[e] = d.share_of(e, "fab_capacity")
            self.atp[e] = d.share_of(e, "atp")
            loads = self.servers[e] * self.pue[e] + self.fab_cap[e] * self.fab_mw_per_unit
            self.net_imports[e] = d.net_imports_mw[e]
            if d.keys[e] in no_demand:
                self.net_imports[e] = loads
            self.base0[e] = gd.maxf(0.0, d.demand_mw[e] - loads)
            self.demand_growth[e] = d.demand_growth[e]
            self.dc_served[e] = 1.0
            self.fab_served[e] = 1.0
        self.servers0 = F64(self.servers)
        used_world = 0.0
        for e1 in range(E):
            used_world += self.servers[e1]
        self.k_it = used_world * 365.0 / float(SERVER_LIFE_DAYS)
        self.fab_first = U8([0] * E)
        self.links_of = [I32() for _ in range(E)]
        for b in d.borders:
            i = len(self.link_a)
            self.link_a.append(int(b[0]))
            self.link_b.append(int(b[1]))
            self.link_cap.append(LINK_SHARE * gd.minf(d.demand_mw[int(b[0])], d.demand_mw[int(b[1])]))
            for side in (int(b[0]), int(b[1])):
                self.links_of[side].append(i)
        self.link_flow = F64([0.0] * len(self.link_a))
        self.day = 0

    def supply_of(self, e, s):
        return self.supply_at(e, s, self.day)

    def supply_at(self, e, s, at_day):
        S = len(MD.SOURCES)
        d_at = gd.mini(at_day, self.pipeline_days[s]) if self.pipeline == "lead" else at_day
        dg = self.base_demand(e, d_at) - self.base0[e]
        m = self.pipe_mix[e * S + s] if dg > 0.0 and len(self.pipe_mix) > 0 else self.mix[e * S + s]
        grown = gd.maxf(0.0, self.supply0[e * S + s] + dg * m)
        if s == COAL and self.coal_retire_yr > 0.0:
            grown *= gd.maxf(0.0, 1.0 - self.coal_retire_yr * float(gd.maxi(0, at_day - self.pipeline_days[COAL])) / 365.0)
        return grown + self.supply_built[e * S + s]

    def imports_of(self, e, at_day=-1):
        d = self.day if at_day < 0 else at_day
        return self.net_imports[e] + (self.base_demand(e, gd.mini(d, self.pipeline_days[GAS]) if self.pipeline == "lead" else d) - self.base0[e] if self.gen0[e] == 0.0 else 0.0)

    def supply_total(self, e):
        t = 0.0
        for s in range(len(MD.SOURCES)):
            t += self.supply_of(e, s)
        return t

    def wanted_it(self, e, at_day=-1):
        return self.servers0[e] * DM.pow(1.0 + self.cgrow[e], float(self.day if at_day < 0 else at_day) / 365.0)

    def free_it(self, e):
        return gd.maxf(0.0, gd.minf(self.dc_it[e] * self.u_max, self.wanted_it(e)) - self.servers[e])

    def dc_load(self, e):
        return self.servers[e] * self.pue[e]

    def fab_load(self, e):
        return self.fab_cap[e] * self.fab_mw_per_unit

    def base_demand(self, e, at_day=-1):
        return self.base0[e] * DM.pow(1.0 + self.demand_growth[e], float(self.day if at_day < 0 else at_day) / 365.0)

    def add_project(self, e, kind, size, link=-1):
        if kind not in PROJECT_KINDS or (kind == "transmission" and link < 0):
            return -1
        fin = self.day + int(self.data.lead_days[kind]["days"])
        self.projects.append([e, kind, size, self.day, fin, link])
        self._next_finish_day = -1
        return fin

    def pending(self, e, kind, until_day=-1):
        t = 0.0
        for p in self.projects:
            if int(p[0]) == e and str(p[1]) == kind and (until_day < 0 or int(p[4]) <= until_day):
                t += float(p[2])
        return t

    def step(self):
        E = self.E
        S = len(MD.SOURCES)
        bal = [0.0] * E
        demand = self.demand
        L = ledger.ACTIVE
        self._bal = bal
        for e in range(E):
            demand[e] = self.base_demand(e) + self.dc_load(e) + self.fab_load(e)
            bal[e] = self.supply_total(e) + self.imports_of(e) - demand[e]
            if L is not None:
                L.start(("bal", e), 0.0)
                t = 0.0
                for s in range(S):
                    y = self.supply_of(e, s)
                    t += y
                    L.add(("bal", e), y, t)
                imp = self.imports_of(e)
                t += imp
                L.add(("bal", e), imp, t)
                L.add(("bal", e), -demand[e], bal[e])
        link_a, link_b, link_cap, link_flow = self.link_a, self.link_b, self.link_cap, self.link_flow
        for i in range(len(link_flow)):
            link_flow[i] = 0.0
            if L is not None:
                L.start(("link_flow", i), 0.0)
        for a in range(E):
            if bal[a] <= 0.0:
                continue
            ls = self.links_of[a]
            want_all = 0.0
            for l in ls:
                o = link_b[l] if link_a[l] == a else link_a[l]
                if bal[o] < 0.0:
                    want_all += gd.minf(-bal[o], link_cap[l])
            if want_all <= 0.0:
                continue
            give = gd.minf(bal[a], want_all)
            for l2 in ls:
                o2 = link_b[l2] if link_a[l2] == a else link_a[l2]
                if bal[o2] >= 0.0:
                    continue
                x = give * gd.minf(-bal[o2], link_cap[l2]) / want_all
                bal[o2] += x
                link_flow[l2] += x if link_a[l2] == a else -x
                if L is not None:
                    L.add(("bal", o2), x, bal[o2])
                    L.gap[a] = L.gap.get(a, 0) + ledger.Fraction(x)
                    L.linkin[o2] = L.linkin.get(o2, 0) + ledger.Fraction(x)
                    L.linkin[a] = L.linkin.get(a, 0) - ledger.Fraction(x)
                    L.add(("link_flow", l2), x if link_a[l2] == a else -x, link_flow[l2])
            bal[a] -= give
            if L is not None:
                L.add(("bal", a), -give, bal[a])
                L.gap[a] = L.gap.get(a, 0) - ledger.Fraction(give)
        for e2 in range(E):
            dis = 0.0
            if bal[e2] < 0.0:
                dis = gd.minf(-bal[e2], self.storage[e2] / 24.0)
            elif bal[e2] > 0.0:
                dis = -gd.minf(bal[e2], (self.storage_cap[e2] - self.storage[e2]) / 24.0)
            self.storage[e2] -= dis * 24.0
            bal[e2] += dis
            if L is not None:
                L.add(("storage", e2), -(dis * 24.0), self.storage[e2])
                L.add(("bal", e2), dis, bal[e2])
            self.discharge[e2] = dis
            short = gd.maxf(0.0, -bal[e2])
            self.spilled[e2] = gd.maxf(0.0, bal[e2])
            dl = self.dc_load(e2)
            fl = self.fab_load(e2)
            if self.fab_first[e2] == 1:
                cut_fab = gd.minf(short, fl)
                cut_dc = gd.minf(short - cut_fab, dl)
            else:
                cut_dc = gd.minf(short, dl)
                cut_fab = gd.minf(short - cut_dc, fl)
            self.dc_served[e2] = 1.0 - cut_dc / dl if dl > 0.0 else 1.0
            self.fab_served[e2] = 1.0 - cut_fab / fl if fl > 0.0 else 1.0
            self.unserved[e2] = short - cut_dc - cut_fab
            if L is not None:
                L.start(("short", e2), short)
                L.add(("short", e2), -cut_dc, short - cut_dc)
                L.add(("short", e2), -cut_fab, self.unserved[e2])
        by_in = self.chain.input_availability_by(self.data, E)
        NI = len(INPUTS)
        for e3 in range(E):
            av = 1.0
            for i in range(NI):
                k = e3 * NI + i
                a = by_in[k]
                if a < 1.0 and self.input_stock[k] > 0.0:
                    draw = gd.minf(self.input_stock[k], 1.0 - a)
                    self.input_stock[k] -= draw
                    a += draw
                    if L is not None:
                        L.add(("input_stock", k), -draw, self.input_stock[k])
                elif a >= 1.0 and self.input_stock[k] < self.input_target[k]:
                    self.input_stock[k] = gd.minf(self.input_target[k], self.input_stock[k] + self.input_target[k] / 30.0)
                    if L is not None:
                        if self.input_stock[k] == self.input_target[k]:
                            L.start(("input_stock", k), self.input_stock[k])
                        else:
                            L.add(("input_stock", k), self.input_target[k] / 30.0, self.input_stock[k])
                av = gd.minf(av, a)
            self.fab_out[e3] = self.fab_cap[e3] * (self.util_top if self.chip_short else self.util_base) / self.util_base * self.fab_served[e3] * av / 365.0
        free = F64([0.0] * E)
        for e4 in range(E):
            ret = self.servers[e4] / float(SERVER_LIFE_DAYS)
            self.servers[e4] -= ret
            free[e4] = self.free_it(e4)
            if L is not None:
                L.add(("servers", e4), -ret, self.servers[e4])
        for i in range(E):
            self.withheld[i] = 0.0
        got = self.chain.distribute(self.fab_out, self.atp, free, self.withheld)
        for e5 in range(E):
            came = got[e5] + self.withheld[e5]
            self.chips[e5] += came
            inst = gd.minf(self.chips[e5] * self.k_it, self.free_it(e5))
            self.servers[e5] += inst
            if L is not None:
                L.add(("chips", e5), came, self.chips[e5])
                L.add(("servers", e5), inst, self.servers[e5])
            used = inst / self.k_it
            self.chips[e5] -= used
            w_ = self.dc_load(e5) * self.dc_served[e5] * 24.0 * self.water_l_per_mwh
            self.water_l[e5] += w_
            if L is not None:
                L.add(("chips", e5), -used, self.chips[e5])
                L.add(("water_l", e5), w_, self.water_l[e5])
        unfilled = 0.0
        installed = 0.0
        for e6 in range(E):
            unfilled += self.free_it(e6)
            installed += self.servers[e6]
        self.chip_short = unfilled > 1e-6 * installed
        self.day += 1
        if self.day < self._next_finish():
            return
        left = []
        self._ramps = []
        for p in self.projects:
            if int(p[4]) == self.day:
                self._finish(p, S)
                self.done_projects += 1
            else:
                left.append(p)
        left.extend(self._ramps)
        self.projects = left
        self._next_finish_day = -1

    def _next_finish(self):
        if self._next_finish_day < 0:
            self._next_finish_day = 1 << 62
            for p in self.projects:
                self._next_finish_day = gd.mini(self._next_finish_day, int(p[4]))
        return self._next_finish_day

    def _finish(self, p, S):
        e = int(p[0])
        kind = str(p[1])
        size = float(p[2])
        s = MD.find(MD.SOURCES, kind)
        L = ledger.ACTIVE
        if s >= 0:
            self.supply_built[e * S + s] += size
            if L is not None:
                L.add(("supply_built", e * S + s), size, self.supply_built[e * S + s])
        elif kind == "storage":
            self.storage_cap[e] += size
            if L is not None:
                L.add(("storage_cap", e), size, self.storage_cap[e])
        elif kind == "dc":
            self.dc_it[e] += size
            if L is not None:
                L.add(("dc_it", e), size, self.dc_it[e])
        elif kind == "fab" and self.fab_ramp_days > 0:
            for k in range(1, 10):
                self._ramps.append([e, "fab_ramp", size / 9.0, self.day, self.day + self.fab_ramp_days * k // 9, -1])
        elif kind == "fab" or kind == "fab_ramp":
            self.fab_cap[e] += size
            if L is not None:
                L.add(("fab_cap", e), size, self.fab_cap[e])
        elif kind == "transmission":
            self.link_cap[int(p[5])] += size
            if L is not None:
                L.add(("link_cap", int(p[5])), size, self.link_cap[int(p[5])])

    def advance(self, days):
        for _ in range(days):
            self.step()

    def to_dict(self):
        return {"base_year": self.data.base_year, "day": self.day, "supply_built": self.supply_built, "storage_cap": self.storage_cap, "storage": self.storage,
                "link_cap": self.link_cap, "fab_first": self.fab_first, "chip_short": self.chip_short, "input_stock": self.input_stock,
                "input_target": self.input_target, "dc_it": self.dc_it, "servers": self.servers, "chips": self.chips, "fab_cap": self.fab_cap,
                "water_l": self.water_l, "projects": deep(self.projects), "done_projects": self.done_projects, "chain": self.chain.to_dict()}

    def from_dict(self, st):
        self.day = int(st["day"])
        for k in ("supply_built", "storage_cap", "storage", "link_cap", "dc_it", "servers", "chips", "fab_cap", "water_l"):
            setattr(self, k, F64(st[k]))
        self.fab_first = U8(st["fab_first"])
        self.chip_short = bool(st.get("chip_short", False))
        self.input_stock = F64(st["input_stock"])
        self.input_target = F64(st["input_target"])
        self.projects = deep(st["projects"])
        self._next_finish_day = -1
        self.done_projects = int(st["done_projects"])
        self.chain.from_dict(st["chain"])
