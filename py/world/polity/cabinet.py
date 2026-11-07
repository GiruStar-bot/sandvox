# polity/cabinet.gd: the Cabinet's verified policies and the Diet's bills
from ..gdtypes import deep

SESSION_MONTHS = 5


class Cabinet:
    def __init__(self):
        self.organs = None
        self.policies = []
        self.bills = []
        self.party_positions = {}

    def setup(self, org):
        self.organs = org
        self.party_positions = deep(org.spec.get("party_positions", {}))

    @staticmethod
    def well_formed(p):
        for k in ("purpose", "target", "instrument", "value", "budget_bn", "period_months", "expected_effect", "legal_basis"):
            if k not in p:
                return "policy lacks " + k
        if type(p["value"]) not in (float, int):
            return "value must be a number"
        return ""

    def verify(self, p, met):
        w = self.well_formed(p)
        if w != "":
            return {"ok": False, "why": w, "needs_bill": False}
        L = self.organs.law_for_lever(str(p["instrument"]))
        if L and str(L["needs"]) == "enact_law":
            return {"ok": False, "why": "%s needs a law: a bill is submitted" % L["name"], "needs_bill": True}
        why = self.organs.may_pull_lever(str(p["instrument"]), met)
        return {"ok": why == "", "why": why, "needs_bill": False}

    def propose(self, month, p, met, set_lever):
        v = self.verify(p, met)
        row = {"id": len(self.policies), "month": month, "policy": deep(p), "verdict": v, "status": ""}
        if v["ok"]:
            set_lever(str(p["instrument"]), float(p["value"]))
            row["status"] = "executed"
            self.organs.record(month, "policy", "cabinet", {"instrument": p["instrument"], "value": p["value"], "purpose": p["purpose"]}, "verified: power, law and budget")
        elif v["needs_bill"]:
            b = {"id": len(self.bills), "month": month, "law": self.organs.law_for_lever(str(p["instrument"]))["law"], "lever": str(p["instrument"]), "value": float(p["value"]), "status": "submitted", "votes": {}}
            self.bills.append(b)
            row["status"] = "bill %d" % int(b["id"])
            self.organs.record(month, "bill", "cabinet", {"bill": b["id"], "law": b["law"], "lever": b["lever"], "value": b["value"]}, "submitted (Cabinet Act art. 5)")
        else:
            row["status"] = "refused"
            self.organs.record(month, "policy_refused", "cabinet", {"instrument": p.get("instrument", ""), "value": p.get("value", None)}, str(v["why"]))
        self.policies.append(row)
        return row

    def vote_due(self, month, set_lever, get_lever=None):
        for b in self.bills:
            if str(b["status"]) != "submitted" or month < int(b["month"]) + SESSION_MONTHS:
                continue
            lever = str(b["lever"])
            pos = self.party_positions.get(lever, {})
            # Direction matters for tax levers: party_positions carries
            # a separate "<lever>_cut" stance for bills that lower the
            # lever (e.g. a consumption-tax cut). Before the fix round
            # (independent review D-2) the _cut table was never read.
            if get_lever is not None:
                cut_pos = self.party_positions.get(lever + "_cut")
                if cut_pos is not None and float(b["value"]) < float(get_lever(lever)):
                    pos = cut_pos
            yes = 0
            votes = {}
            seats = self.organs.seats.get("house_of_representatives", {})
            for party in seats:
                # Bills reach the Diet only through Cabinet.propose, so
                # they are the government's own bills: governing parties
                # support them. Before the fix, a stance recorded in
                # party_positions (written for the party's opposition
                # days) overrode governing status, and a governing bloc
                # voted its own platform bills down 0-465 (D-2).
                if party in self.organs.governing:
                    stance = "yes"
                else:
                    stance = str(pos.get(party, "no"))
                votes[party] = stance
                if stance == "yes":
                    yes += int(seats[party])
            b["votes"] = votes
            total = self.organs.house_total("house_of_representatives")
            if yes * 2 > total:
                b["status"] = "enacted"
                set_lever(str(b["lever"]), float(b["value"]))
                self.organs.record(month, "enacted", "diet", {"bill": b["id"], "law": b["law"], "yes": yes, "of": total}, "art. 59: majority in the lower house")
            else:
                b["status"] = "rejected"
                self.organs.record(month, "rejected", "diet", {"bill": b["id"], "law": b["law"], "yes": yes, "of": total}, "no majority for it")

    def to_dict(self):
        return {"policies": deep(self.policies), "bills": deep(self.bills)}

    def from_dict(self, d):
        self.policies = deep(d.get("policies", []))
        self.bills = deep(d.get("bills", []))
