# modern_costs.gd: R56's LCOE per entity at its WACC with Wright learning
from . import canon as CANON
from ._core import DM
from .gdtypes import F64, PStr

R56_PATH = "res://data/modern/r56.json"
_REGION_BY_INCOME = {"high": "HIGH", "upper_middle": "China", "lower_middle": "India", "low": "India"}


class Costs:
    def __init__(self):
        self.r56 = {}
        self.region = PStr()
        self.wacc = F64()
        self.income = PStr()

    def create(self, data):
        self.r56 = CANON.load_json_m(R56_PATH)
        r56 = self.r56
        E = data.entity_count()
        th = r56["income_thresholds_gni_pc"]
        named = {}
        for k in r56["wacc"]:
            row = r56["wacc"][k]
            if row["iso3"] is not None:
                named[str(row["iso3"])] = float(row["value"])
        europe = float(r56["wacc"]["Europe"]["value"])
        prev = data.history.get(data.base_year - 1, {})
        self.region = PStr([""] * E)
        self.wacc = F64([0.0] * E)
        self.income = PStr([""] * E)
        for e in range(E):
            k2 = data.keys[e]
            h = prev.get(k2, {})
            gdp = float(h["gdp"]) if h.get("gdp") is not None else data.gdp[e]
            pop = float(h["population"]) if h.get("population") is not None else data.population[e]
            pc = gdp / pop if pop > 0.0 and gdp > 0.0 else 0.0
            g = "low" if pc <= float(th["low_max"]) else ("lower_middle" if pc <= float(th["lower_middle_max"]) else ("upper_middle"
                if pc <= float(th["upper_middle_max"]) else "high"))
            if pc == 0.0:
                g = "upper_middle"
            self.income[e] = g
            macro = str(data.MACROS[data.macro[e]])
            if k2 == "USA":
                self.region[e] = "US"
            elif macro == "EU":
                self.region[e] = "EU"
            elif k2 == "CHN":
                self.region[e] = "China"
            elif k2 == "IND":
                self.region[e] = "India"
            else:
                self.region[e] = _REGION_BY_INCOME[g]
            if k2 in named:
                self.wacc[e] = named[k2]
            elif macro == "EU":
                self.wacc[e] = europe
            else:
                self.wacc[e] = float(r56["wacc_by_income"][g])

    def _cost(self, reg, src, field):
        if reg == "HIGH":
            return 0.5 * (float(self.r56["costs"]["US"][src][field]) + float(self.r56["costs"]["EU"][src][field]))
        return float(self.r56["costs"][reg][src][field])

    @staticmethod
    def crf(w, years):
        return w / (1.0 - DM.pow(1.0 + w, -years))

    def learning(self, src, ratio):
        if src not in self.r56["learning"] or ratio <= 0.0:
            return 1.0
        b = -DM.log(1.0 - float(self.r56["learning"][src]["rate"])) / DM.log(2.0)
        return DM.pow(ratio, -b)

    def lcoe(self, e, src, learn=1.0):
        reg = self.region[e]
        capex = self._cost(reg, src, "capex_usd_kw")
        life = float(self.r56["life_yr"][src][0])
        cap_now = capex * learn * self.crf(self.wacc[e], life)
        cap_weo = capex * self.crf(float(self.r56["weo_wacc"][src]), life)
        return self._cost(reg, src, "lcoe_pub") + (cap_now - cap_weo) / (8.76 * self._cost(reg, src, "cf"))
