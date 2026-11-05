# The labour market's half of sim/modern/econ/labour.gd (receive, step): u and the wage index from the persons' supply and the sectors' use
# Why not the per-person half (person_month, rates, apply): it is the persons' and is ported with them (ECON_PORT_PLAN §1)
import copy

from core.gd import clampf

from .data import load_json


class Labour:
    def __init__(self):
        self.spec = {}
        self.u = float("nan")
        self.wage_index = 1.0
        self.use_start = float("nan")
        self.search_share = 0.0
        self.wage_demand_share = 0.0
        self.demand_scale = {}
        self.log = []

    def var_names(self):
        return ["spec", "u", "wage_index", "use_start", "search_share", "wage_demand_share", "demand_scale", "log"]

    def load_state(self, key):
        d = load_json("labour_%s.json" % key.lower())
        if not isinstance(d, dict):
            return "labour: no spec for " + key
        self.spec = d
        self.u = self._p("u_star")
        return ""

    def _p(self, name):
        return float(self.spec[name]["value"])

    def receive(self, search, wage_demands, scales):
        self.search_share = float(search)
        self.wage_demand_share = float(wage_demands)
        self.demand_scale = copy.copy(scales)

    def step(self, month, capacity_use, expected_inflation):
        if self.use_start != self.use_start:
            self.use_start = capacity_use
        gap = float(self.spec["sector_employment_share"]["food_manufacturing"]["value"]) * (capacity_use - self.use_start)
        rho = self._p("rho")
        self.u = clampf(rho * self.u + (1.0 - rho) * (self._p("u_star") - self._p("okun_k") * gap), self._p("u_min"), self._p("u_max"))
        self.wage_index *= 1.0 + (self._p("w_pi") * expected_inflation + self._p("w_u") * (self._p("u_star") - self.u) + self._p("w_demand") * self.wage_demand_share) / 12.0
        self.log.append([month, self.u, self.wage_index, gap, self.search_share, self.wage_demand_share, float(self.demand_scale.get("food_products", 1.0))])
