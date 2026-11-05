# modern_brain.gd: the rule brain (appraise, prioritise, choose, think) and its memory
import functools

from ._core import gd
from .gdtypes import NAN, deep, is_finite

MAX_CHANGES = 4
MEMORY_MONTHS = 12


def appraise(own, catalog, calendar):
    out = {}

    def v(id_):
        return float(own.get(id_, NAN))
    tfr = v("tfr")
    if is_finite(tfr):
        goal = float(catalog["statuses"]["population"]["reference_lines"]["tfr"]["target"])
        out["population"] = {"score": gd.maxf(0.0, (goal - tfr) / goal), "direction": 1, "indicator": "tfr", "line": "tfr goal %.2f" % goal}
    econ = 0.0
    ind = ""
    dirn = 0
    cpi = v("cpi_inflation")
    if is_finite(cpi):
        d = abs(cpi - 0.02) / 0.02
        if d > econ:
            econ = d
            ind = "cpi_inflation"
            dirn = -1 if cpi > 0.02 else 1
    u = v("unemployment_rate")
    if is_finite(u) and u > 0.03 and (u - 0.03) / 0.03 > econ:
        econ = (u - 0.03) / 0.03
        ind = "unemployment_rate"
        dirn = -1
    rev = v("gov_revenue_general")
    exp_ = v("gov_expenditure_general")
    bonds = v("new_bond_issuance")
    if is_finite(rev) and is_finite(exp_) and is_finite(bonds) and exp_ > 0.0:
        pb_gap = bonds / exp_
        if pb_gap > econ:
            econ = pb_gap
            ind = "new_bond_issuance"
            dirn = -1
    dg = v("debt_to_gdp")
    if is_finite(dg) and dg > 1.0 and (dg - 1.0) > econ:
        econ = dg - 1.0
        ind = "debt_to_gdp"
        dirn = -1
    out["economy"] = {"score": econ, "direction": dirn, "indicator": ind, "line": "cpi 2%, u 3%, PB, debt fatigue 100%"}
    ap = v("cabinet_approval")
    if is_finite(ap):
        dl = float(catalog["statuses"]["politics"]["reference_lines"]["approval_danger"]["threshold"])
        out["politics"] = {"score": gd.maxf(0.0, (dl - ap) / dl), "direction": 1, "indicator": "cabinet_approval", "line": "approval danger %.2f" % dl}
    ds = v("defence_share_gdp")
    if is_finite(ds):
        t = float(catalog["statuses"]["military"]["reference_lines"]["defence_share_target"]["target"])
        out["military"] = {"score": gd.maxf(0.0, (t - ds) / t), "direction": 1, "indicator": "defence_share_gdp", "line": "defence 2% by 2027"}
    mr = v("physician_maldistribution_ratio")
    if is_finite(mr):
        out["health"] = {"score": gd.maxf(0.0, (mr - 1.5) / 1.5), "direction": -1, "indicator": "physician_maldistribution_ratio", "line": "max/min 1.5 (T)"}
    od = v("oil_stock_days")
    un = v("unserved_share")
    en = 0.0
    ei = ""
    if is_finite(un) and un > 0.0:
        en = un * 100.0
        ei = "unserved_share"
    if is_finite(od) and od < 160.0 and (160.0 - od) / 160.0 > en:
        en = (160.0 - od) / 160.0
        ei = "oil_stock_days"
    out["energy"] = {"score": en, "direction": 1 if ei == "oil_stock_days" else -1, "indicator": ei, "line": "no unserved load; oil stock rule"}
    cs = v("chip_short")
    out["technology"] = {"score": cs if is_finite(cs) else 0.0, "direction": 1, "indicator": "fab_capacity_share", "line": "wanted IT finds chips"}
    ca = v("current_account")
    cl = v("licences_closed_against")
    fo = 0.0
    fi = ""
    if is_finite(cl) and cl > 0.0:
        fo = gd.minf(1.0, cl / 3.0)
        fi = "licences_closed_against"
    if is_finite(ca) and ca < 0.0:
        fo = gd.maxf(fo, 0.5)
        fi = "current_account"
    out["foreign"] = {"score": fo, "direction": -1, "indicator": fi, "line": "no closed licence against us; current account >= 0"}
    fs = v("food_self_sufficiency_calorie")
    if is_finite(fs):
        out["resources"] = {"score": gd.maxf(0.0, (0.45 - fs) / 0.45), "direction": 1, "indicator": "food_self_sufficiency_calorie", "line": "45% by 2030"}
    pv = v("relative_poverty_rate")
    if is_finite(pv):
        out["society"] = {"score": gd.maxf(0.0, (pv - 0.11) / 0.11), "direction": -1, "indicator": "relative_poverty_rate", "line": "OECD average 11% (T)"}
    months_to_election = float(calendar.get("months_to_lower_house_election", 48.0))
    if months_to_election <= 12.0:
        for s in ("economy", "society", "population"):
            if s in out:
                out[s]["score"] = float(out[s]["score"]) * 1.5
                out[s]["calendar"] = "election within 12 months x1.5"
    return out


def prioritise(pressures):
    def cmp(a, b):
        sa = float(pressures[a]["score"])
        sb = float(pressures[b]["score"])
        if sa != sb:
            return -1 if sa > sb else 1
        return -1 if a < b else (1 if a > b else 0)
    return sorted(pressures.keys(), key=functools.cmp_to_key(cmp))


def choose(status, p, menu, own):
    def lv(id_):
        return float(menu[id_]["value"]) if id_ in menu else NAN

    def step_up(id_, frac):
        if id_ not in menu:
            return []
        cur = lv(id_)
        nv = gd.minf(float(menu[id_]["max"]), cur + frac * gd.maxf(abs(cur), 1.0))
        return [id_, nv] if nv != cur else []
    if status == "population":
        return step_up("child_allowance", 0.1)
    if status == "economy":
        ind = str(p["indicator"])
        if ind == "cpi_inflation":
            return step_up("fuel_subsidy", 0.2) if int(p["direction"]) < 0 else step_up("public_investment", 0.05)
        if ind == "unemployment_rate":
            return step_up("public_investment", 0.05)
        if ind in ("new_bond_issuance", "debt_to_gdp"):
            if "consumption_tax_rate" in menu:
                cur = lv("consumption_tax_rate")
                return ["consumption_tax_rate", gd.minf(float(menu["consumption_tax_rate"]["max"]), cur + 0.01)]
            return []
        return []
    if status == "politics":
        return step_up("public_investment", 0.05)
    if status == "military":
        if "defence_budget_share" in menu:
            cur = lv("defence_budget_share")
            return ["defence_budget_share", gd.minf(float(menu["defence_budget_share"]["max"]), cur + 0.001)]
        return []
    if status == "health":
        return step_up("health_fee_schedule", 0.01) if "health_fee_schedule" in menu else []
    if status == "energy":
        if str(p["indicator"]) == "oil_stock_days":
            return []
        return step_up("nuclear_restart", 1.0)
    if status == "technology":
        return step_up("semiconductor_subsidy", 0.2)
    if status == "society":
        return step_up("education_budget", 0.05)
    return []


class Brain:
    def __init__(self):
        self.memory = []
        self.refused = {}
        self.keyed_seed = 0

    def note_refused(self, lever, month):
        self.refused[lever] = month

    def think(self, obs, catalog, menu, calendar, month):
        own = obs.get("own_statuses", {})
        pressures = appraise(own, catalog, calendar)
        order = prioritise(pressures)
        actions = []
        why = []
        changed = 0
        for s in order:
            if changed >= MAX_CHANGES:
                why.append("CAP")
                break
            p = pressures[s]
            if float(p["score"]) <= 0.0:
                break
            pick = choose(s, p, menu, own)
            if not pick:
                why.append("PRESSURE_%s:no_lever" % s)
                continue
            if str(pick[0]) in self.refused and month - int(self.refused[str(pick[0])]) < MEMORY_MONTHS:
                why.append("REFUSED_BEFORE:%s" % pick[0])
                continue
            if self._repeated_without_effect(s, str(pick[0]), own):
                why.append("REPEAT_AVOID:%s" % pick[0])
                continue
            actions.append({"act": "lever", "id": pick[0], "value": pick[1]})
            why.append("PRESSURE_%s:%s=%.3f -> LEVER_%s" % (s, p["indicator"], float(p["score"]), pick[0]))
            changed += 1
        if not actions and not why:
            why.append("HOLD")
        self.memory.append({"month": month, "pressures": deep(pressures), "actions": deep(actions), "why": list(why), "own": {}})
        for s in pressures:
            self.memory[-1]["own"][str(pressures[s]["indicator"])] = own.get(str(pressures[s]["indicator"]), NAN)
        if len(self.memory) > MEMORY_MONTHS:
            self.memory.pop(0)
        return {"actions": actions, "why": why, "pressures": pressures, "order": order}

    def _repeated_without_effect(self, status, lever, own):
        for m in self.memory:
            for a in m["actions"]:
                if str(a["id"]) != lever:
                    continue
                p = m["pressures"].get(status, {})
                id_ = str(p.get("indicator", ""))
                then = float(m["own"].get(id_, NAN))
                now = float(own.get(id_, NAN))
                if not is_finite(then) or not is_finite(now):
                    return False
                moved = (now - then) * float(p.get("direction", 0))
                if moved <= 0.0:
                    return True
        return False

    def to_dict(self):
        return {"memory": deep(self.memory), "refused": dict(self.refused)}

    def from_dict(self, d):
        self.memory = deep(d.get("memory", []))
        self.refused = dict(d.get("refused", {}))
