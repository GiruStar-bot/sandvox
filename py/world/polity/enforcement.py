# polity/enforcement.gd: late charges on the econ actors' arrears and the procedure after three months
from ..gdtypes import deep

LATE_RATE = 0.087
PROCEDURE_MONTHS = 6
PROCEDURE_CAPACITY = 0.8
ARREARS_MONTHS_TO_PROCEDURE = 3


class Enforcement:
    def __init__(self):
        self.events = []
        self.arrears_months = {}

    def step(self, month, econ):
        if econ is None:
            return
        for a in econ.actors:
            ar = float(a.stocks.get("arrears", 0.0))
            if ar > 0.0:
                charge = ar * LATE_RATE / 12.0
                a.stocks["arrears"] = ar + charge
                self.arrears_months[a.id] = int(self.arrears_months.get(a.id, 0)) + 1
                self.events.append({"month": month, "kind": "late_charge", "actor": a.id, "facts": {"arrears": ar, "charge": charge}, "why": "延滞税率 8.7%/yr (S) on the arrears (T: applied to every arrear)"})
                if int(self.arrears_months[a.id]) >= ARREARS_MONTHS_TO_PROCEDURE and int(a.stocks.get("procedure_until", -1)) < month:
                    a.stocks["procedure_until"] = month + PROCEDURE_MONTHS
                    self.events.append({"month": month, "kind": "procedure_opened", "actor": a.id, "facts": {"until_month": month + PROCEDURE_MONTHS, "capacity_factor": PROCEDURE_CAPACITY}, "why": "three months in arrears (T): 民事再生 procedure, six months at 80% (T)"})
            else:
                self.arrears_months[a.id] = 0

    def to_dict(self):
        return {"events": deep(self.events), "arrears_months": dict(self.arrears_months)}

    def from_dict(self, d):
        self.events = deep(d.get("events", []))
        self.arrears_months = dict(d.get("arrears_months", {}))
