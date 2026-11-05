# modern_publish.gd: the publication register (recorded years, the simulated years closed on their last day, the hashed estimate)
from . import canon as CANON
from . import data as MD
from . import hashes
from ._core import DM
from .gdtypes import F64, NAN, deep

VIS_PATH = "res://data/modern/visibility.json"
FIGURES = ["population", "gdp", "generation_twh", "generation_by_source_twh", "demand_twh", "fab_capacity", "dc_capacity_mw", "dc_twh"]
_HIST_SRC = {"population": "population", "gdp": "gdp", "generation_twh": "generation", "demand_twh": "demand"}


def day_of(year, base):
    return (year - base) * 365


def _unit(key, fig, year):
    return hashes.unit("modern-publish|%s|%s|%d" % (key, fig, year))


class Register:
    FIGURES = FIGURES

    def __init__(self):
        self.vis = {}
        self.base_year = 0
        self.E = 0
        self.keys = []
        self.history = {}
        self.acc_gen = F64()
        self.acc_demand = F64()
        self.acc_dc = F64()

    def create(self, data):
        self.vis = CANON.load_json_m(VIS_PATH)
        self.base_year = data.base_year
        E = self.E = data.entity_count()
        self.keys = data.keys
        self.acc_gen = F64([0.0] * (E * len(MD.SOURCES)))
        self.acc_demand = F64([0.0] * E)
        self.acc_dc = F64([0.0] * E)
        for y in data.history:
            rows = data.history[y]
            h = {}
            for fig in ("population", "gdp", "generation_twh", "demand_twh"):
                a = F64([0.0] * E)
                for e in range(E):
                    v = rows.get(self.keys[e], {}).get(_HIST_SRC[fig])
                    a[e] = float(v) if v is not None else NAN
                h[fig] = a
            self.history[y] = h

    def observe_day(self, f, supply_before):
        for i in range(len(supply_before)):
            self.acc_gen[i] += supply_before[i] * 24.0 / 1e6
        for e in range(self.E):
            self.acc_demand[e] += f.demand[e] * 24.0 / 1e6
            self.acc_dc[e] += f.dc_load(e) * f.dc_served[e] * 24.0 / 1e6

    def close_year(self, w, year):
        f = w.field
        S = len(MD.SOURCES)
        E = self.E
        h = {}
        for fig in FIGURES:
            h[fig] = F64([0.0] * (E * S if fig == "generation_by_source_twh" else E))
        mid = day_of(year, self.base_year) + 182
        for e in range(E):
            h["population"][e] = w.population(e, mid)
            h["gdp"][e] = w.data.gdp[e] * DM.pow(1.0 + w.data.gdp_growth[e], float(mid - 182) / 365.0)
            g = 0.0
            for s in range(S):
                h["generation_by_source_twh"][e * S + s] = self.acc_gen[e * S + s]
                g += self.acc_gen[e * S + s]
            h["generation_twh"][e] = g
            h["demand_twh"][e] = self.acc_demand[e]
            h["fab_capacity"][e] = f.fab_cap[e]
            h["dc_capacity_mw"][e] = f.dc_it[e]
            h["dc_twh"][e] = self.acc_dc[e]
        self.history[year] = h
        for a in (self.acc_gen, self.acc_demand, self.acc_dc):
            for i in range(len(a)):
                a[i] = 0.0

    def published(self, fig, e, day):
        spec = self.vis["figures"][fig]
        basis = str(spec["basis"])
        lag = int(spec["lag_days"])
        spread = float(spec["spread"])
        ex = self.vis["exceptions"].get(self.keys[e], {})
        if fig in ex:
            basis = str(ex[fig][0])
            lag = int(ex[fig][1])
            spread = 0.0
        for y in sorted(self.history.keys(), reverse=True):
            if day_of(y + 1, self.base_year) + lag > day or fig not in self.history[y]:
                continue
            a = self.history[y][fig]
            u = (_unit(self.keys[e], fig, y) * 2.0 - 1.0) * spread if basis == "estimate" else 0.0
            if fig == "generation_by_source_twh":
                S = len(MD.SOURCES)
                return {"year": y, "value": [a[e * S + s] * (1.0 + u) for s in range(S)], "basis": basis}
            if a[e] != a[e]:
                return {}
            out = {"year": y, "value": a[e] * (1.0 + u), "basis": basis}
            if basis == "estimate":
                out["spread"] = spread
            return out
        return {}

    def to_dict(self):
        hy = {y: deep(self.history[y]) for y in self.history}
        return {"history": hy, "acc_gen": self.acc_gen, "acc_demand": self.acc_demand, "acc_dc": self.acc_dc}

    def from_dict(self, d):
        self.history = {int(y): deep(d["history"][y]) for y in d["history"]}
        self.acc_gen = F64(d["acc_gen"])
        self.acc_demand = F64(d["acc_demand"])
        self.acc_dc = F64(d["acc_dc"])
