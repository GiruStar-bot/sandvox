extends RefCounted
## The Cabinet's structured policy and the Diet's bills (BLUEPRINT_v2 4; P4-P5). A policy is {purpose, target, instrument (a lever),
## value, budget_bn, period_months, expected_effect, legal_basis}; verify() asks the organs and the laws (may_pull_lever) with the
## decisions the Cabinet makes itself, and the budget room; what passes is executed (the lever is set); what needs a law becomes a bill.
## A bill is {id, law, change, submitted_month, status}: submitted -> voted at the end of the session (T: 5 months, the ordinary session's
## 150 days) by the parties' positions (data: party_positions; T until the parties' platforms are loaded) -> enacted (the lever is set)
## or rejected. Every step is an event in the organs' record (P0). The LLM proposes policies in this form; it never sets a lever itself.
const SESSION_MONTHS := 5

var organs: RefCounted
var policies: Array = []   # [{id, month, policy, verdict, status}]
var bills: Array = []      # [{id, month, law, lever, value, status, votes}]
var party_positions: Dictionary = {}


func setup(org: RefCounted) -> void:
	organs = org
	party_positions = (org.spec.get("party_positions", {}) as Dictionary).duplicate(true)


## "" when the policy is well formed, else why not
static func well_formed(p: Dictionary) -> String:
	for k: String in ["purpose", "target", "instrument", "value", "budget_bn", "period_months", "expected_effect", "legal_basis"]:
		if not p.has(k):
			return "policy lacks " + k
	if not (p["value"] is float or p["value"] is int):
		return "value must be a number"
	return ""


## Verify a policy: {"ok": bool, "why": str, "needs_bill": bool}. met: the decisions the Cabinet has made (a cabinet decision is its own)
func verify(p: Dictionary, met: Array) -> Dictionary:
	var w: String = well_formed(p)
	if w != "":
		return {"ok": false, "why": w, "needs_bill": false}
	var L: Dictionary = organs.law_for_lever(String(p["instrument"]))
	if not L.is_empty() and String(L["needs"]) == "enact_law":
		return {"ok": false, "why": "%s needs a law: a bill is submitted" % L["name"], "needs_bill": true}
	var why: String = organs.may_pull_lever(String(p["instrument"]), met)
	return {"ok": why == "", "why": why, "needs_bill": false}


## Propose: verify, then execute (set the lever through `set_lever`) or submit a bill; records the event
func propose(month: int, p: Dictionary, met: Array, set_lever: Callable) -> Dictionary:
	var v: Dictionary = verify(p, met)
	var row := {"id": policies.size(), "month": month, "policy": p.duplicate(true), "verdict": v, "status": ""}
	if v["ok"]:
		set_lever.call(String(p["instrument"]), float(p["value"]))
		row["status"] = "executed"
		organs.record(month, "policy", "cabinet", {"instrument": p["instrument"], "value": p["value"], "purpose": p["purpose"]}, "verified: power, law and budget")
	elif v["needs_bill"]:
		var b := {"id": bills.size(), "month": month, "law": organs.law_for_lever(String(p["instrument"]))["law"], "lever": String(p["instrument"]), "value": float(p["value"]), "status": "submitted", "votes": {}}
		bills.append(b)
		row["status"] = "bill %d" % int(b["id"])
		organs.record(month, "bill", "cabinet", {"bill": b["id"], "law": b["law"], "lever": b["lever"], "value": b["value"]}, "submitted (Cabinet Act art. 5)")
	else:
		row["status"] = "refused"
		organs.record(month, "policy_refused", "cabinet", {"instrument": p.get("instrument", ""), "value": p.get("value", null)}, String(v["why"]))
	policies.append(row)
	return row


## The Diet's vote on the bills whose session is over: yes if the parties for it hold a majority of the lower house (art. 59; the upper
## house is taken as following the lower house's majority or the override, T until it is modelled)
func vote_due(month: int, set_lever: Callable) -> void:
	for b: Dictionary in bills:
		if String(b["status"]) != "submitted" or month < int(b["month"]) + SESSION_MONTHS:
			continue
		var pos: Dictionary = party_positions.get(String(b["lever"]), {})
		var yes: int = 0
		var votes: Dictionary = {}
		var seats: Dictionary = organs.seats.get("house_of_representatives", {})
		for party: String in seats:
			var stance: String = String(pos.get(party, "yes" if organs.governing.has(party) else "no"))
			votes[party] = stance
			if stance == "yes":
				yes += int(seats[party])
		b["votes"] = votes
		var total: int = organs.house_total("house_of_representatives")
		if yes * 2 > total:
			b["status"] = "enacted"
			set_lever.call(String(b["lever"]), float(b["value"]))
			organs.record(month, "enacted", "diet", {"bill": b["id"], "law": b["law"], "yes": yes, "of": total}, "art. 59: majority in the lower house")
		else:
			b["status"] = "rejected"
			organs.record(month, "rejected", "diet", {"bill": b["id"], "law": b["law"], "yes": yes, "of": total}, "no majority for it")


func to_dict() -> Dictionary:
	return {"policies": policies.duplicate(true), "bills": bills.duplicate(true)}


func from_dict(d: Dictionary) -> void:
	policies = (d.get("policies", []) as Array).duplicate(true)
	bills = (d.get("bills", []) as Array).duplicate(true)
