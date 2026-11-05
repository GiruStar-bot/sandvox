# polity/organs.gd: the state's organs and powers, may / may_pull_lever, and the record
from .. import canon as CANON
from ..data import exists
from ..gdtypes import deep

_RANK = {"enact_law": 4, "pass_budget": 3, "cabinet_order": 2, "cabinet_decision": 2, "ministerial_ordinance": 1}


def _trim_prefix(s, p):
    return s[len(p):] if s.startswith(p) else s


def _trim_suffix(s, p):
    return s[:-len(p)] if p and s.endswith(p) else s


class Organs:
    def __init__(self):
        self.state_key = ""
        self.spec = {}
        self.seats = {}
        self.governing = []
        self.events = []
        self.laws = {}
        self.error = ""

    def law_for_lever(self, lever):
        best = {}
        best_rank = -1
        for lid in self.laws:
            L = self.laws[lid]
            if str(L.get("lever", "")) == lever or lever in L.get("levers", []):
                needs = str(L.get("change_needs", "none"))
                r = int(_RANK.get(needs, 5 if needs.startswith("none (") else 0))
                if r > best_rank:
                    best_rank = r
                    best = {"law": lid, "name": str(L.get("name", lid)), "needs": needs}
        return best

    def may_pull_lever(self, lever, met=()):
        L = self.law_for_lever(lever)
        if not L:
            return ""
        n = str(L["needs"])
        if n == "enact_law":
            w = self.may("diet", "enact_law", met)
            return "" if w == "" else "%s (%s): %s" % (L["name"], "law", w)
        if n == "pass_budget":
            if "within_budget" in met or ("cabinet_decision" in met and "reserve_fund_room" in met):
                return ""
            w2 = self.may("diet", "pass_budget", met)
            return "" if w2 == "" else "%s (supplementary budget): %s" % (L["name"], w2)
        if n in ("cabinet_order", "cabinet_decision"):
            return "" if "cabinet_decision" in met else "%s: a cabinet decision is needed" % L["name"]
        if n == "ministerial_ordinance":
            return ""
        return "" if not n.startswith("none (") else "%s: %s decides, not the Cabinet" % (L["name"], _trim_suffix(_trim_prefix(n, "none ("), ")"))

    def load_state(self, key):
        p = "res://data/modern/polity/%s_organs.json" % key.lower()
        d = CANON.load_json(p) if exists(p) else None
        if not isinstance(d, dict):
            self.error = "organs: no spec at " + p
            return self.error
        self.spec = d
        self.state_key = key
        comp = self.spec.get("composition_2024_12", {})
        for h in ("house_of_representatives", "house_of_councillors"):
            if h in comp:
                row = dict(comp[h])
                row.pop("source", None)
                self.seats[h] = row
        self.governing = list(comp.get("governing", []))
        lp = "res://data/modern/polity/%s_laws.json" % key.lower()
        if exists(lp):
            # Why no canon: organs.gd parses the laws with JSON.parse_string alone
            l = CANON.parse_file(lp)
            if isinstance(l, dict):
                self.laws = l["laws"]
        return ""

    def house_total(self, house):
        return int(self.spec["organs"][house]["seats"])

    def governing_seats(self, house):
        n = 0
        for party in self.seats.get(house, {}):
            if party in self.governing:
                n += int(self.seats[house][party])
        return n

    def has_majority(self, house):
        return self.governing_seats(house) * 2 > self.house_total(house)

    def has_two_thirds(self, house):
        return self.governing_seats(house) * 3 >= self.house_total(house) * 2

    def may(self, organ, power, met=()):
        if power not in self.spec["powers"]:
            return "no such power " + power
        P = self.spec["powers"][power]
        if str(P["organ"]) != organ and not (str(P["organ"]) == "diet" and organ in ("house_of_representatives", "house_of_councillors")):
            return "%s has no power %s (%s)" % (organ, power, P["basis"])
        for proc in P.get("procedure", []):
            if proc == "majority_house_of_representatives":
                if not self.has_majority("house_of_representatives"):
                    return "procedure %s not met: governing %d of %d" % (proc, self.governing_seats("house_of_representatives"), self.house_total("house_of_representatives"))
            elif proc == "majority_house_of_councillors_or_two_thirds_override":
                if not self.has_majority("house_of_councillors") and not self.has_two_thirds("house_of_representatives"):
                    return "procedure %s not met" % proc
            elif proc == "two_thirds_house_of_representatives":
                if not self.has_two_thirds("house_of_representatives"):
                    return "procedure %s not met" % proc
            elif proc == "two_thirds_house_of_councillors":
                if not self.has_two_thirds("house_of_councillors"):
                    return "procedure %s not met" % proc
            elif proc == "enact_law":
                w = self.may("diet", "enact_law", met)
                if w != "":
                    return w
            elif proc == "pass_budget":
                w2 = self.may("diet", "pass_budget", met)
                if w2 != "":
                    return w2
            elif proc not in met:
                return "procedure %s not met (no such decision recorded)" % proc
        return ""

    def record(self, month, kind, organ, facts, why):
        self.events.append({"month": month, "kind": kind, "organ": organ, "facts": deep(facts), "why": why})

    def to_dict(self):
        return {"seats": deep(self.seats), "governing": list(self.governing), "events": deep(self.events)}

    def from_dict(self, d):
        self.seats = deep(d["seats"])
        self.governing = list(d["governing"])
        self.events = deep(d["events"])
