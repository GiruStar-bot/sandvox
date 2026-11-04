extends RefCounted
## Enforcement and the courts in the economic areas (BLUEPRINT_v2 4, P7 first cut). Each month: (1) an actor in arrears on its fixed
## costs (wages, suppliers) is charged the statutory late-payment rate on the arrears (S: 国税通則法 延滞税 8.7% a year, 2024, as the
## standard rate for public money; applied here to every arrear, T) and after three months of arrears a bankruptcy procedure opens (民事
## 再生, T: six months at 80% of capacity); (2) an act an organ had no power for was already refused at the gate (organs.may); it is
## counted here as a violation attempt. Every step is an event with its legal basis. Courts for disputes between actors are S5'+.
const LATE_RATE := 0.087       # S: 延滞税 2024 (納期限の翌日から2月を経過した日以後)
const PROCEDURE_MONTHS := 6    # T
const PROCEDURE_CAPACITY := 0.8   # T
const ARREARS_MONTHS_TO_PROCEDURE := 3   # T

var events: Array = []
var arrears_months: Dictionary = {}   # actor id -> consecutive months in arrears


func step(month: int, econ: RefCounted) -> void:
	if econ == null:
		return
	for a in econ.actors:
		var ar: float = float(a.stocks.get("arrears", 0.0))
		if ar > 0.0:
			var charge: float = ar * LATE_RATE / 12.0
			a.stocks["arrears"] = ar + charge
			arrears_months[a.id] = int(arrears_months.get(a.id, 0)) + 1
			events.append({"month": month, "kind": "late_charge", "actor": a.id, "facts": {"arrears": ar, "charge": charge}, "why": "延滞税率 8.7%/yr (S) on the arrears (T: applied to every arrear)"})
			if int(arrears_months[a.id]) >= ARREARS_MONTHS_TO_PROCEDURE and int(a.stocks.get("procedure_until", -1)) < month:
				a.stocks["procedure_until"] = month + PROCEDURE_MONTHS
				events.append({"month": month, "kind": "procedure_opened", "actor": a.id, "facts": {"until_month": month + PROCEDURE_MONTHS, "capacity_factor": PROCEDURE_CAPACITY}, "why": "three months in arrears (T): 民事再生 procedure, six months at 80% (T)"})
		else:
			arrears_months[a.id] = 0


func to_dict() -> Dictionary:
	return {"events": events.duplicate(true), "arrears_months": arrears_months.duplicate()}


func from_dict(d: Dictionary) -> void:
	events = (d.get("events", []) as Array).duplicate(true)
	arrears_months = (d.get("arrears_months", {}) as Dictionary).duplicate()
