# modern_data.gd: the base year's figures, growth, the compute chain's shares, the data-centre start and R58's PUE
import hashlib
import os

from . import canon as CANON
from ._core import DM
from .gdtypes import F64, I32, PStr

DIR = "res://data/modern/"
SOURCES = ["coal", "gas", "oil", "nuclear", "hydro", "wind", "solar", "bioenergy", "other_renewable"]
MACROS = ["CN", "TW", "JP", "KR", "US", "EU", "ROW"]
GOODS = ["fab_capacity", "logic_lt10nm", "atp", "lithography", "photoresist", "silicon_wafers", "gallium", "neon", "dc_electricity"]
HOURS = 8760.0
START_CARRY_YR = 0.5
DEMAND_SPAN_YR = 5


def find(a, x):
    try:
        return a.index(x)
    except ValueError:
        return -1


def exists(path):
    return os.path.isfile(CANON.res(path))


def _json(path):
    if not exists(path):
        return None
    return CANON.load_json_m(path)


def _sha(path):
    with open(CANON.res(path), "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


class ModernData:
    def __init__(self):
        self.error = ""
        self.base_year = 0
        self.data_year = 0
        self.stats_file = ""
        self.demand_rule = ""
        self.keys = PStr()
        self.names_en = PStr()
        self.kind = PStr()
        self.macro = I32()
        self.population = F64()
        self.gdp = F64()
        self.pop_growth = F64()
        self.gdp_growth = F64()
        self.gdp_real = F64()
        self.gdp_real_growth = F64()
        self.demand_mw = F64()
        self.demand_growth = F64()
        self.net_imports_mw = F64()
        self.supply_mw = F64()
        self.no_data = {}
        self.provisional = {}
        self.held = {}
        self.borders = []
        self.regions = []
        self.share = F64()
        self.scalars = {}
        self.lead_days = {}
        self.manifest = {}
        self.history = {}
        self.dc_world_twh = 0.0
        self.dc_growth = F64()
        self.dc_vintage = ""
        self.pue = F64()
        self.look_ahead = PStr()
        self.undated = PStr()

    MACROS = MACROS
    SOURCES = SOURCES
    GOODS = GOODS

    def load_year(self, year, rule="cagr5"):
        self.base_year = year
        self.demand_rule = rule
        if rule not in ("cagr5", "last"):
            return self._fail("unknown demand growth rule " + rule)
        self.data_year = year - 1
        self.manifest = _json(DIR + "MANIFEST.json")
        if not isinstance(self.manifest, dict):
            return self._fail("no data/modern/MANIFEST.json")
        for name in self.manifest["files"]:
            if _sha(DIR + name) != str(self.manifest["files"][name]["sha256"]):
                return self._fail("data/modern/%s differs from its manifest sha256" % name)
        ent = _json(DIR + "entities.json")
        self.stats_file = "stats_v%d.json" % self.base_year if exists(DIR + "stats_v%d.json" % self.base_year) else "stats.json"
        st = _json(DIR + self.stats_file)
        er = _json(DIR + "entity_regions.json")
        cc = _json(DIR + "compute_chain.json")
        E = len(ent["entities"])
        for e in ent["entities"]:
            self.keys.append(str(e["key"]))
            self.names_en.append(str(e["name_en"]))
            self.kind.append(str(e["kind"]))
            self.macro.append(find(MACROS, str(e["macro"])))
        for a in ("population", "gdp", "pop_growth", "gdp_growth", "gdp_real", "gdp_real_growth", "demand_mw", "demand_growth", "net_imports_mw"):
            setattr(self, a, F64([0.0] * E))
        self.supply_mw = F64([0.0] * (E * len(SOURCES)))
        years = st["years"]
        self.provisional = st.get("provisional", {})
        S = len(SOURCES)
        for i in range(E):
            k = self.keys[i]
            rows = st["entities"][k]
            self.population[i] = self._figure(rows, years, k, "population")
            self.gdp[i] = self._figure(rows, years, k, "gdp")
            self.demand_mw[i] = self._figure(rows, years, k, "demand") * 1e6 / HOURS
            self.net_imports_mw[i] = self._figure(rows, years, k, "net_imports", False) * 1e6 / HOURS
            for s in range(S):
                self.supply_mw[i * S + s] = self._figure(rows, years, k, SOURCES[s], False) * 1e6 / HOURS
            for y0 in years:
                ys = str(int(y0))
                if int(y0) <= self.data_year and ys in rows:
                    hy = self.history.get(int(y0), {})
                    r = rows[ys]
                    hy[k] = {"population": r.get("population"), "gdp": r.get("gdp"), "generation": r.get("generation"), "demand": r.get("demand")}
                    self.history[int(y0)] = hy
            self.pop_growth[i] = self._growth(rows, years, "population")
            self.gdp_growth[i] = self._growth(rows, years, "gdp")
            self.gdp_real[i] = self._figure(rows, years, k, "gdp_real", False)
            self.gdp_real_growth[i] = self._growth(rows, years, "gdp_real")
            rg = rows.get(str(self.data_year), {}).get("gdp_real_growth")
            if rg is not None:
                self.gdp_real_growth[i] = float(rg)
            self.demand_growth[i] = self._growth(rows, years, "demand") if self.demand_rule == "last" else self._cagr(rows, years, "demand", DEMAND_SPAN_YR)
            carry = DM.pow(1.0 + self.demand_growth[i], START_CARRY_YR)
            self.demand_mw[i] *= carry
            self.net_imports_mw[i] *= carry
            for s2 in range(S):
                self.supply_mw[i * S + s2] *= carry
        for b in er["land_borders"]:
            self.borders.append([int(b[0]), int(b[1])])
        self.regions = er["regions"]
        self.scalars = cc["scalars"]
        self.lead_days = cc["lead_days"]
        self._shares(cc, E)
        replaced = self._dc_history(E) + self._r58(E)
        for blk in ("shares", "scalars", "lead_days"):
            rows = cc[blk]
            for n in sorted(rows.keys()):
                y = rows[n].get("data_year")
                if (blk + "/" + n) in replaced:
                    continue
                if y is None:
                    self.undated.append(blk + "/" + n)
                elif int(y) > self.base_year:
                    self.look_ahead.append("%s/%s %d" % (blk, n, int(y)))
        return ""

    def _fail(self, msg):
        self.error = "modern data: " + msg
        return self.error

    def _figure(self, rows, years, key, fig, strict=True):
        best = -1
        for y in years:
            yy = int(y)
            if yy <= self.data_year and str(yy) in rows and rows[str(yy)].get(fig) is not None and yy > best:
                best = yy
        if best < 0:
            if strict:
                ks = self.no_data.get(fig, PStr())
                ks.append(key)
                self.no_data[fig] = ks
            return 0.0
        if best != self.data_year:
            self.held[key + "/" + fig] = best
        return float(rows[str(best)][fig])

    def _cagr(self, rows, years, fig, span):
        last = -1
        for y in range(self.data_year, int(years[0]) - 1, -1):
            v = rows.get(str(y), {}).get(fig)
            if v is not None and float(v) > 0.0:
                last = y
                break
        if last < 0:
            return 0.0
        for y0 in range(max(last - span, int(years[0])), last):
            a = rows.get(str(y0), {}).get(fig)
            if a is not None and float(a) > 0.0:
                return DM.pow(float(rows[str(last)][fig]) / float(a), 1.0 / float(last - y0)) - 1.0
        return 0.0

    def _growth(self, rows, years, fig):
        for y in range(self.data_year, int(years[0]), -1):
            a = rows.get(str(y - 1), {}).get(fig)
            b = rows.get(str(y), {}).get(fig)
            if a is not None and b is not None and float(a) > 0.0:
                return float(b) / float(a) - 1.0
        return 0.0

    def _shares(self, cc, E):
        self.share = F64([0.0] * (E * len(GOODS)))
        gdp_in = [0.0] * len(MACROS)
        for i in range(E):
            gdp_in[self.macro[i]] += self.gdp[i]
        fab = cc["shares"]["fab_capacity"]["given"]
        for g in range(len(GOODS)):
            row = cc["shares"][GOODS[g]]
            m_share = F64([0.0] * len(MACROS))
            given = row["given"]
            gsum = 0.0
            for m0 in given:
                gsum += float(given[m0])
            scale = 1.0 / gsum if gsum > 1.0 or (row["rest"] is None and gsum > 0.0) else 1.0
            left = 1.0
            for m in given:
                m_share[find(MACROS, m)] = float(given[m]) * scale
                left -= float(given[m]) * scale
            self._rest(m_share, left, str(row["rest"]) if row["rest"] is not None else "", fab, given, gdp_in)
            self._hand_down(g, m_share, str(cc["named_in_row"].get(GOODS[g], "")))

    def _hand_down(self, g, m_share, named):
        gdp_in = [0.0] * len(MACROS)
        pop_in = [0.0] * len(MACROS)
        for i in range(len(self.keys)):
            gdp_in[self.macro[i]] += self.gdp[i]
            pop_in[self.macro[i]] += self.population[i]
        for i2 in range(len(self.keys)):
            m2 = self.macro[i2]
            v = 0.0
            if named != "" and MACROS[m2] == "ROW":
                v = m_share[m2] if self.keys[i2] == named else 0.0
            elif gdp_in[m2] > 0.0:
                v = m_share[m2] * self.gdp[i2] / gdp_in[m2]
            elif pop_in[m2] > 0.0:
                v = m_share[m2] * self.population[i2] / pop_in[m2]
            self.share[i2 * len(GOODS) + g] = v

    def _r58(self, E):
        self.pue = F64([float(self.scalars["pue"]["value"])] * E)
        h = _json(DIR + "r58.json")
        blk = h["years"].get(str(self.base_year), {}) if isinstance(h, dict) else {}
        out = []
        by = blk.get("pue", {})
        if len(by) == len(MACROS) and all(int(r["published"]) <= self.base_year for r in by.values()):
            for i in range(E):
                self.pue[i] = float(by[MACROS[self.macro[i]]]["value"])
            out.append("scalars/pue")
        ld = blk.get("lead_days_dc", {})
        if ld and int(ld["published"]) <= self.base_year:
            dc = dict(self.lead_days["dc"])
            dc["days"] = int(ld["value"])
            dc["data_year"] = int(ld["data_year"])
            self.lead_days["dc"] = dc
            out.append("lead_days/dc")
        return out

    def _dc_history(self, E):
        self.dc_world_twh = float(self.scalars["dc_electricity_twh_2024"]["value"])
        self.dc_growth = F64([0.0] * E)
        h = _json(DIR + "dc_history.json")
        blk = {}
        if isinstance(h, dict):
            blk = h["years"].get(str(self.base_year), h["years"].get(str(self.data_year), {}))
        if not blk:
            self.dc_vintage = "none for %d: no growth" % self.base_year
            return []
        self.dc_vintage = str(blk["vintage"])
        for i in range(E):
            gm = blk["growth"].get(MACROS[self.macro[i]], blk["growth"]["world"])
            self.dc_growth[i] = float(gm["value"])
        if "world_twh" not in blk:
            return []
        self.dc_world_twh = float(blk["world_twh"]["value"])
        m_share = F64([0.0] * len(MACROS))
        left = self.dc_world_twh
        for m in blk["given_twh"]:
            m_share[find(MACROS, m)] = float(blk["given_twh"][m]["value"]) / self.dc_world_twh
            left -= float(blk["given_twh"][m]["value"])
        gdp_m = [0.0] * len(MACROS)
        for i2 in range(E):
            gdp_m[self.macro[i2]] += self.gdp[i2]
        tot = 0.0
        for m2 in blk["rest_over"]:
            tot += gdp_m[find(MACROS, m2)]
        for m3 in blk["rest_over"]:
            m_share[find(MACROS, m3)] += left / self.dc_world_twh * gdp_m[find(MACROS, m3)] / tot
        self._hand_down(find(GOODS, "dc_electricity"), m_share, "")
        return ["shares/dc_electricity", "scalars/dc_electricity_twh_2024", "scalars/jp_dc_twh"]

    def _rest(self, m_share, left, rule, fab, given, gdp_in):
        if left <= 1e-12 or rule == "":
            return
        if rule.startswith("JP 19 TWh"):
            jp = float(self.scalars.get("jp_dc_twh", {}).get("value", 19.0)) / float(self.scalars.get("dc_electricity_twh_2024", {}).get("value", 415.0))
            m_share[find(MACROS, "JP")] += jp
            rest_m = ["TW", "KR", "ROW"]
            tot = 0.0
            for m in rest_m:
                tot += gdp_in[find(MACROS, m)]
            for m2 in rest_m:
                m_share[find(MACROS, m2)] += (left - jp) * gdp_in[find(MACROS, m2)] / tot
            return
        if rule.startswith("JP"):
            m_share[find(MACROS, "JP")] += left
            return
        if rule == "ROW":
            m_share[find(MACROS, "ROW")] += left
            return
        over = []
        for m3 in MACROS:
            if "over JP, KR, US, EU" in rule and m3 not in ("JP", "KR", "US", "EU"):
                continue
            if "all but ROW" in rule and m3 == "ROW":
                continue
            if m3 not in given:
                over.append(m3)
        t2 = 0.0
        for m4 in over:
            t2 += float(fab[m4])
        for m5 in over:
            m_share[find(MACROS, m5)] += left * float(fab[m5]) / t2

    def entity_count(self):
        return len(self.keys)

    def index_of(self, key):
        return find(self.keys, key)

    def share_of(self, e, good):
        return self.share[e * len(GOODS) + find(GOODS, good)]
