# modern_status.gd: the status layer (cohort flows, identities, held trends, levers and their response functions)
import base64
import struct

from . import canon as CANON
from . import ledger
from .data import exists
from ._core import DM, gd
from .gdtypes import F64, PStr, NAN, deep, is_finite

DIR = "res://data/modern/"
CATALOG = DIR + "status/catalog.json"
AGES = 101
BUDGET_ROOM = 0.10
RESERVE_FUND_BN = 1000.0
SEXES = 2
YEAR_DAYS = 365.0

# Declared (T) conversions for lever responses whose sourced specs give
# physical units rather than shares (see data/modern/jpn/levers.json).
NUCLEAR_SHARE_PER_REACTOR = 0.006  # one ~1 GW reactor at ~70% CF ~ 6 TWh/yr of ~1,000 TWh
FAB_SHARE_PER_BN = 2.0e-6          # 1 tn JPY/yr of sustained fab support ~ +0.2 pt of world share
REN_SOURCES = ("solar", "wind", "hydro", "bioenergy", "other_renewable")
# Declared (T) operational emission intensities, kg CO2 per kWh generated
# (IPCC-consistent medians for the fuel technologies), and electricity's
# share of primary energy supply, for the derived energy indicators.
EMISSION_INTENSITY = {"coal": 0.90, "gas": 0.45, "oil": 0.70}
ELEC_PRIMARY_SHARE = 0.45


def _mix_emission_factor(mix):
    e = 0.0
    for s, inten in EMISSION_INTENSITY.items():
        e += float(mix.get(s, 0.0)) * inten
    return e


def _mix_domestic(mix):
    d = float(mix.get("nuclear", 0.0))
    for s in REN_SOURCES:
        d += float(mix.get(s, 0.0))
    return d
FOSSIL_SOURCES = ("coal", "gas", "oil")


def _shift_mix(mix, target_ren):
    """Move an electricity mix dict toward a renewable share, taking the
    difference from (or returning it to) fossil sources pro-rata."""
    ren = sum(float(mix.get(s, 0.0)) for s in REN_SOURCES)
    fos = sum(float(mix.get(s, 0.0)) for s in FOSSIL_SOURCES)
    shift = float(target_ren) - ren
    if abs(shift) < 1e-12:
        return
    if shift > 0.0:
        take = gd.minf(shift, fos)
        if fos > 0.0:
            for s in FOSSIL_SOURCES:
                mix[s] = float(mix.get(s, 0.0)) * (fos - take) / fos
        if ren > 1e-12:
            for s in REN_SOURCES:
                mix[s] = float(mix.get(s, 0.0)) * (ren + take) / ren
        else:
            mix["solar"] = float(mix.get("solar", 0.0)) + take
    else:
        give = gd.minf(-shift, ren)
        if ren > 0.0:
            for s in REN_SOURCES:
                mix[s] = float(mix.get(s, 0.0)) * (ren - give) / ren
        if fos > 1e-12:
            for s in FOSSIL_SOURCES:
                mix[s] = float(mix.get(s, 0.0)) * (fos + give) / fos
        else:
            mix["gas"] = float(mix.get("gas", 0.0)) + give


def _add_nuclear(mix, dshare):
    """Add (or retire) nuclear share in an electricity mix dict, balanced
    against fossil sources pro-rata."""
    fos = sum(float(mix.get(s, 0.0)) for s in FOSSIL_SOURCES)
    nuc = float(mix.get("nuclear", 0.0))
    if dshare > 0.0:
        take = gd.minf(dshare, fos)
        if fos > 0.0:
            for s in FOSSIL_SOURCES:
                mix[s] = float(mix.get(s, 0.0)) * (fos - take) / fos
        mix["nuclear"] = nuc + take
    elif dshare < 0.0:
        cut = gd.minf(-dshare, nuc)
        mix["nuclear"] = nuc - cut
        if fos > 1e-12:
            for s in FOSSIL_SOURCES:
                mix[s] = float(mix.get(s, 0.0)) * (fos + cut) / fos
        else:
            mix["gas"] = float(mix.get("gas", 0.0)) + cut


class Status:
    def __init__(self):
        self.legal_check = None
        self.error = ""
        self.catalog = {}
        self.entities = PStr()
        self.data = {}
        self.levers = {}
        self.links = {}
        self.base_year = 0
        self.day = 0
        self.ind = {}
        self.ind0 = {}
        self.aux = {}
        self.derived = {}
        self.trend = {}
        self.cohort = {}
        self.qx = {}
        self.hazard = {}
        self.trend_day = {}
        self.asfr = {}
        self.lever_value = {}
        self.lever_due = {}
        self.lever_log = []
        self.daily_births = {}
        self.daily_deaths = {}

    def load(self, year, keys):
        self.base_year = year
        c = CANON.load_json(CATALOG) if exists(CATALOG) else None
        if not isinstance(c, dict):
            self.error = "status: no catalogue at " + CATALOG
            return self.error
        self.catalog = c
        for k in keys:
            p = DIR + k.lower() + "/status_%d.json" % year
            if not exists(p):
                continue
            d = CANON.load_json(p)
            if not isinstance(d, dict):
                self.error = "status: bad file " + p
                return self.error
            self.entities.append(k)
            self.data[k] = d
            lp = DIR + k.lower() + "/levers.json"
            self.levers[k] = CANON.load_json(lp) if exists(lp) else {"levers": {}}
            kp = DIR + k.lower() + "/links_%d.json" % year
            self.links[k] = CANON.load_json(kp) if exists(kp) else {}
            self._init_entity(k)
        self.day = 0
        return ""

    def _init_entity(self, k):
        d = self.data[k]
        vals = d.get("indicators", {})
        iv = {}
        tr = {}
        for id_ in vals:
            row = vals[id_]
            if "value" in row and type(row["value"]) in (float, int):
                iv[id_] = float(row["value"])
                tr[id_] = float(row.get("trend", 0.0))
            elif "value" in row and type(row["value"]) is dict:
                self.aux.setdefault(k, {})[id_] = deep(row["value"])
        self.ind[k] = iv
        self.ind0[k] = dict(iv)
        self.trend[k] = tr
        td = {}
        for id_ in tr:
            if float(tr[id_]) != 0.0:
                td[id_] = DM.pow(1.0 + float(tr[id_]), 1.0 / YEAR_DAYS)
        self.trend_day[k] = td
        co = F64([0.0] * (AGES * SEXES))
        ages = d.get("cohort", {}).get("ages", [])
        unit = float(d.get("cohort", {}).get("unit_persons", 1.0))
        for a in ages:
            age = gd.mini(int(a["age"]), AGES - 1)
            co[age * SEXES] += float(a["male"]) * unit
            co[age * SEXES + 1] += float(a["female"]) * unit
        self.cohort[k] = co
        q = F64([0.0] * (AGES * SEXES))
        lt = d.get("life_table", {})
        if "qx_male" in lt and "qx_female" in lt:
            for age in range(AGES):
                q[age * SEXES] = float(lt["qx_male"][gd.mini(age, len(lt["qx_male"]) - 1)])
                q[age * SEXES + 1] = float(lt["qx_female"][gd.mini(age, len(lt["qx_female"]) - 1)])
        else:
            deaths_pub = float(vals.get("deaths", {}).get("value", 0.0))
            shape = [0.0] * (AGES * SEXES)
            tot = 0.0
            for age in range(AGES):
                for s in range(SEXES):
                    g = 0.00008 * DM.exp(0.095 * float(age)) * (1.0 if s == 0 else 0.6)
                    g = gd.minf(0.6, g + (0.0018 if age == 0 else 0.0))
                    shape[age * SEXES + s] = g
                    tot += g * co[age * SEXES + s]
            scale = deaths_pub / tot if tot > 0.0 and deaths_pub > 0.0 else 1.0
            for i in range(AGES * SEXES):
                q[i] = gd.minf(0.95, shape[i] * scale)
        self.qx[k] = q
        hz = F64([0.0] * (AGES * SEXES))
        for i in range(AGES * SEXES):
            hz[i] = 1.0 - DM.exp(DM.log(1.0 - gd.minf(q[i], 0.999)) / YEAR_DAYS)
        self.hazard[k] = hz
        f = F64([0.0] * AGES)
        fert = d.get("fertility", {})
        if "asfr" in fert:
            for age in range(AGES):
                f[age] = float(fert["asfr"][gd.mini(age, len(fert["asfr"]) - 1)])
        elif "births_by_mother_age5" in fert:
            for g in fert["births_by_mother_age5"]:
                lo = int(g.split("-")[0])
                hi = int(g.split("-")[1])
                women = 0.0
                for age in range(lo, hi + 1):
                    women += co[age * SEXES + 1]
                rate = float(fert["births_by_mother_age5"][g]) / women if women > 0.0 else 0.0
                for age in range(lo, hi + 1):
                    f[age] = rate
        else:
            tfr = float(vals.get("tfr", {}).get("value", 0.0))
            w = [0.0] * AGES
            sw = 0.0
            for age in range(15, 50):
                x = (float(age) - 31.0) / 5.0
                w[age] = DM.exp(-0.5 * x * x)
                sw += w[age]
            for age in range(15, 50):
                f[age] = tfr * w[age] / sw
        self.asfr[k] = f
        mix0 = self.aux.get(k, {}).get("electricity_by_source")
        if mix0 is not None and "ghg_emissions" in iv and "electricity_generation_twh" in iv:
            elec_ghg0 = float(iv["electricity_generation_twh"]) * _mix_emission_factor(mix0)
            self.derived[k] = {
                "ghg_non_elec": float(iv["ghg_emissions"]) - elec_ghg0,
                "ghg_sink": float(iv["ghg_emissions"]) - float(iv.get("ghg_net", iv["ghg_emissions"])),
                "dom0": _mix_domestic(mix0),
                "ss0": float(iv.get("energy_self_sufficiency", 0.0)),
            }
        self.lever_value[k] = {}
        self.lever_due[k] = {}
        for lid in self.levers[k].get("levers", {}):
            self.lever_value[k][lid] = float(self.levers[k]["levers"][lid].get("current", 0.0))
        self.daily_births[k] = 0.0
        self.daily_deaths[k] = 0.0

    def has(self, k):
        return k in self.data

    def population_of(self, k):
        p = 0.0
        for v in self.cohort[k]:
            p += v
        return p

    def value(self, k, id_):
        return float(self.ind[k].get(id_, NAN))

    def step(self):
        self.day += 1
        for k in self.entities:
            self._step_cohort(k)
            self._step_identities(k)
            self._step_held(k)
            self._apply_due(k)
        if self.day % 365 == 0:
            for k in self.entities:
                self._age_cohort(k)

    def _step_cohort(self, k):
        co = self.cohort[k]
        hz = self.hazard[k]
        f = self.asfr[k]
        L = ledger.ACTIVE
        deaths = 0.0
        births = 0.0
        for age in range(AGES):
            for s in range(SEXES):
                i = age * SEXES + s
                dd = co[i] * hz[i]
                co[i] -= dd
                deaths += dd
                if L is not None:
                    L.add(("co", k, i), -dd, co[i])
                    L.add(("deaths", k), dd, 0.0)
            births += co[age * SEXES + 1] * f[age] / YEAR_DAYS
        bm = births * 1.05 / 2.05
        bf = births * 1.0 / 2.05
        co[0] += bm
        co[1] += bf
        mig = float(self.ind[k].get("net_migration", 0.0)) / YEAR_DAYS
        if L is not None:
            L.add(("co", k, 0), bm, co[0])
            L.add(("co", k, 1), bf, co[1])
            L.add(("born", k), bm, 0.0)
            L.add(("born", k), bf, 0.0)
        for age in range(20, 40):
            for s in range(SEXES):
                co[age * SEXES + s] += mig / 40.0
                if L is not None:
                    L.add(("co", k, age * SEXES + s), mig / 40.0, co[age * SEXES + s])
                    L.add(("migrated", k), mig / 40.0, 0.0)
        self.daily_births[k] = births
        self.daily_deaths[k] = deaths
        iv = self.ind[k]
        iv["pop_total"] = self.population_of(k)
        old = 0.0
        for age in range(65, AGES):
            old += co[age * SEXES] + co[age * SEXES + 1]
        iv["share_65plus"] = old / gd.maxf(1.0, iv["pop_total"])
        if "foreign_residents" in iv:
            iv["foreign_residents"] += mig
            if L is not None:
                L.add(("ind", k, "foreign_residents"), mig, iv["foreign_residents"])

    def _age_cohort(self, k):
        co = self.cohort[k]
        L = ledger.ACTIVE
        for s in range(SEXES):
            co[(AGES - 1) * SEXES + s] += co[(AGES - 2) * SEXES + s]
            if L is not None:
                L.merge(("co", k, (AGES - 1) * SEXES + s), ("co", k, (AGES - 2) * SEXES + s), co[(AGES - 1) * SEXES + s])
            for age in range(AGES - 2, 0, -1):
                co[age * SEXES + s] = co[(age - 1) * SEXES + s]
                if L is not None:
                    L.move(("co", k, age * SEXES + s), ("co", k, (age - 1) * SEXES + s))
            co[s] = 0.0
            if L is not None:
                L.start(("co", k, s), 0.0)

    def _step_identities(self, k):
        iv = self.ind[k]
        L = ledger.ACTIVE
        if "gov_debt_total" in iv and "gov_expenditure_general" in iv and "gov_revenue_general" in iv:
            deficit = iv["gov_expenditure_general"] - iv["gov_revenue_general"]
            iv["gov_debt_total"] += deficit / YEAR_DAYS
            if L is not None:
                L.add(("ind", k, "gov_debt_total"), deficit / YEAR_DAYS, iv["gov_debt_total"])
            if "ordinary_jgb" in iv:
                iv["ordinary_jgb"] += deficit / YEAR_DAYS
                if L is not None:
                    L.add(("ind", k, "ordinary_jgb"), deficit / YEAR_DAYS, iv["ordinary_jgb"])
            if "gdp_nominal" in iv and iv["gdp_nominal"] > 0.0:
                iv["debt_to_gdp"] = iv["gov_debt_total"] / iv["gdp_nominal"]
        if "niip" in iv and "current_account" in iv:
            iv["niip"] += iv["current_account"] / YEAR_DAYS
            if L is not None:
                L.add(("ind", k, "niip"), iv["current_account"] / YEAR_DAYS, iv["niip"])
            if "external_assets" in iv:
                iv["external_assets"] += iv["current_account"] / YEAR_DAYS
                if L is not None:
                    L.add(("ind", k, "external_assets"), iv["current_account"] / YEAR_DAYS, iv["external_assets"])
        if "defence_budget" in iv and "gdp_nominal" in iv and iv["gdp_nominal"] > 0.0:
            iv["defence_share_gdp"] = iv["defence_budget"] / iv["gdp_nominal"]
        if "physicians" in iv and "pop_total" in iv:
            iv["physicians_per_100k"] = iv["physicians"] / iv["pop_total"] * 100000.0
        d = self.derived.get(k)
        if d is not None:
            mix = self.aux.get(k, {}).get("electricity_by_source")
            if mix is not None and "electricity_generation_twh" in iv:
                ghg = d["ghg_non_elec"] + float(iv["electricity_generation_twh"]) * _mix_emission_factor(mix)
                iv["ghg_emissions"] = ghg
                if "ghg_net" in iv:
                    iv["ghg_net"] = ghg - d["ghg_sink"]
                if "energy_self_sufficiency" in iv:
                    iv["energy_self_sufficiency"] = gd.minf(1.0, gd.maxf(0.0,
                        d["ss0"] + ELEC_PRIMARY_SHARE * (_mix_domestic(mix) - d["dom0"])))

    def _step_held(self, k):
        iv = self.ind[k]
        td = self.trend_day[k]
        L = ledger.ACTIVE
        for id_ in td:
            if id_ in iv:
                iv[id_] *= float(td[id_])
                if L is not None:
                    L.mul(("ind", k, id_), float(td[id_]), iv[id_])

    def menu(self, k):
        if k not in self.levers:
            return {}
        out = {}
        for lid in self.levers[k]["levers"]:
            L = self.levers[k]["levers"][lid]
            out[lid] = {"status": L["status"], "unit": L["unit"], "value": self.lever_value[k][lid], "min": float(L["min"]), "max": float(L["max"]),
                        "lead_days": int(L["lead_days"]), "legal": L.get("legal", "")}
        return out

    def check_lever(self, k, lid, v, changes_this_month):
        if k not in self.levers or lid not in self.levers[k]["levers"]:
            return "no such lever " + lid
        L = self.levers[k]["levers"][lid]
        if not is_finite(v) or v < float(L["min"]) or v > float(L["max"]):
            return "lever %s out of bounds" % lid
        if lid in self.lever_due[k]:
            return "lever %s is already pending until day %d" % (lid, int(self.lever_due[k][lid][0]))
        pre = self.levers[k].get("preconditions", {})
        if changes_this_month >= 4 and "capacity" in pre:
            return "capacity: more than 4 lever changes this month"
        iv = self.ind[k]
        if self.legal_check is not None:
            met = ["cabinet_decision"]
            r0 = L.get("response", {})
            adds_spending = str(r0.get("target", "")) == "gov_expenditure_general" or str(r0.get("form", "")) == "share"
            dv = v - self.lever_value[k][lid]
            if not adds_spending or dv <= 0.0 or dv <= BUDGET_ROOM * gd.maxf(abs(self.lever_value[k][lid]), 1.0):
                met.append("within_budget")
            elif dv <= RESERVE_FUND_BN:
                met.append("reserve_fund_room")
            why_law = self.legal_check(lid, met)
            if why_law != "":
                return "majority: " + why_law if "majority" in why_law.lower() else why_law
        elif "law" in str(L.get("legal", "")).lower() and "lower_house_seats_governing" in iv and "lower_house_seats_total" in iv:
            if iv["lower_house_seats_governing"] * 2.0 < iv["lower_house_seats_total"]:
                return "majority: the governing seats are below half"
        r = L.get("response", {})
        if str(r.get("target", "")) == "gov_expenditure_general" and "new_bond_issuance" in iv and "gov_expenditure_general" in iv:
            extra = v - self.lever_value[k][lid]
            if extra > 0.0 and (iv["new_bond_issuance"] + extra) / (iv["gov_expenditure_general"] + extra) > 0.45:
                return "fiscal space: bonds would exceed 45% of spending"
        return ""

    def set_lever(self, k, lid, v):
        L = self.levers[k]["levers"][lid]
        self.lever_due[k][lid] = [self.day + int(L["lead_days"]), v]
        self.lever_log.append([self.day, k, lid, v, "set"])

    def _apply_due(self, k):
        due = self.lever_due[k]
        for lid in list(due.keys()):
            if int(due[lid][0]) > self.day:
                continue
            v = float(due[lid][1])
            old = self.lever_value[k][lid]
            self.lever_value[k][lid] = v
            del due[lid]
            self._respond(k, lid, old, v)
            self.lever_log.append([self.day, k, lid, v, "applied"])

    def _respond(self, k, lid, old, v):
        L = self.levers[k]["levers"][lid]
        r = L.get("response", {})
        target = str(r.get("target", ""))
        iv = self.ind[k]
        if target == "":
            return
        if target not in iv and target not in self.aux.get(k, {}):
            return
        kk = float(r.get("k", 0.0))
        dv = v - old
        form = str(r.get("form", ""))
        lg = ledger.ACTIVE
        key = ("ind", k, target)
        if form == "multiplier":
            y = kk * dv * (100.0 if str(L["unit"]) == "share" else 1.0)
            iv[target] += y
            if lg is not None:
                lg.add(key, y, iv[target])
        elif form == "multiplier_share":
            if target == "gdp_real_growth" and "gdp_nominal" in iv and iv["gdp_nominal"] > 0.0:
                y = kk * dv / iv["gdp_nominal"]
            else:
                y = kk * dv
            iv[target] += y
            if lg is not None:
                lg.add(key, y, iv[target])
        elif form == "elasticity":
            if old > 0.0 and v > 0.0:
                f = DM.pow(v / old, kk)
                iv[target] *= f
                if lg is not None:
                    lg.mul(key, f, iv[target])
        elif form == "rate":
            iv[target] = kk * v
            if lg is not None and key in lg.sh:
                lg.start(key, iv[target])
        elif form == "share":
            if "gdp_nominal" in iv:
                iv[target] = v * iv["gdp_nominal"]
                if lg is not None and key in lg.sh:
                    lg.start(key, iv[target])
        elif form == "share_of_spending":
            y = iv[target] * kk * dv
            iv[target] += y
            if lg is not None:
                lg.add(key, y, iv[target])
        elif form == "multiplier_pt":
            # k is declared in percentage points per unit of lever change.
            y = kk * dv / 100.0
            iv[target] += y
            if lg is not None:
                lg.add(key, y, iv[target])
        elif form == "fab_spending":
            y = FAB_SHARE_PER_BN * dv
            iv[target] = gd.minf(1.0, gd.maxf(0.0, iv[target] + y))
            if lg is not None:
                lg.add(key, y, iv[target])
        elif form == "build_plan":
            mix = self.aux.get(k, {}).get(target)
            if type(mix) is dict:
                _shift_mix(mix, v)
        elif form == "build":
            mix = self.aux.get(k, {}).get(target)
            if type(mix) is dict:
                _add_nuclear(mix, dv * NUCLEAR_SHARE_PER_REACTOR)

    def to_dict(self):
        st = {"day": self.day, "ind": {}, "cohort": {}, "lever_value": {}, "lever_due": {}, "lever_log": deep(self.lever_log), "aux": deep(self.aux), "derived": deep(self.derived)}
        for k in self.entities:
            iv = self.ind[k]
            names = PStr(sorted(iv.keys()))
            packed = [float(iv[i]) for i in names]
            st["ind"][k] = {"names": names, "bytes": base64.b64encode(struct.pack("<%dd" % len(packed), *packed)).decode()}
            co = self.cohort[k]
            st["cohort"][k] = base64.b64encode(struct.pack("<%dd" % len(co), *co)).decode()
            st["lever_value"][k] = dict(self.lever_value[k])
            st["lever_due"][k] = deep(self.lever_due[k])
        return st

    def from_dict(self, st):
        self.day = int(st["day"])
        for k in self.entities:
            row = st["ind"][k]
            raw = base64.b64decode(str(row["bytes"]))
            packed = struct.unpack("<%dd" % (len(raw) // 8), raw)
            names = row["names"]
            self.ind[k] = {names[i]: packed[i] for i in range(len(names))}
            raw2 = base64.b64decode(str(st["cohort"][k]))
            self.cohort[k] = F64(struct.unpack("<%dd" % (len(raw2) // 8), raw2))
            self.lever_value[k] = dict(st["lever_value"][k])
            self.lever_due[k] = deep(st["lever_due"][k])
        self.lever_log = deep(st["lever_log"])
        self.aux = deep(st.get("aux", {}))
        self.derived = deep(st.get("derived", {}))
