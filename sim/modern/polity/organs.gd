extends RefCounted
## The state, its organs, offices and powers (BLUEPRINT_v2 4; P0-P2 first cut): the political world state, its events, and the check
## "may this organ do this act, by this procedure?" An act is refused when its organ lacks the power or a required procedure is not met.
## Procedures that depend on the houses' composition (a majority, two thirds) are evaluated on the composition held here; procedures that
## are decisions (a cabinet decision) are recorded as events. The LLM never interprets the constitution: the rules are these records.
## Data: data/modern/polity/<state>_organs.json.
const CANON = preload("res://sim/modern/canon.gd")
var state_key: String = ""
var spec: Dictionary = {}
var seats: Dictionary = {}      # house -> party -> seats
var governing: Array = []       # parties in government
var events: Array = []          # [{month, kind, organ, facts, why}]
var laws: Dictionary = {}       # law id -> record (data/modern/polity/<state>_laws.json)
var error: String = ""


## The law a lever rests on, and what changing it needs (P3): {"law", "needs"} or {} when no law names the lever
func law_for_lever(lever: String) -> Dictionary:
	# Why the strictest: a lever may sit under several laws (the child allowance is in the budget AND in its own act); the act's procedure
	# (enact_law) outranks the budget's (pass_budget), which outranks a cabinet decision, which outranks a ministerial act
	var rank: Dictionary = {"enact_law": 4, "pass_budget": 3, "cabinet_order": 2, "cabinet_decision": 2, "ministerial_ordinance": 1}
	var best: Dictionary = {}
	var best_rank: int = -1
	for lid: String in laws:
		var L: Dictionary = laws[lid]
		if String(L.get("lever", "")) == lever or (L.get("levers", []) as Array).has(lever):
			var needs: String = String(L.get("change_needs", "none"))
			var r: int = int(rank.get(needs, 5 if needs.begins_with("none (") else 0))
			if r > best_rank:
				best_rank = r
				best = {"law": lid, "name": String(L.get("name", lid)), "needs": needs}
	return best


## "" when a lever may be pulled under the law and the organs (P2-P3), given the decisions in `met`; else why not.
## A budget lever is within the budget when its line has room (met carries "within_budget"), else it needs the reserve fund by a
## cabinet decision, else a supplementary budget (pass_budget).
func may_pull_lever(lever: String, met: Array = []) -> String:
	var L: Dictionary = law_for_lever(lever)
	if L.is_empty():
		return ""
	match String(L["needs"]):
		"enact_law":
			var w: String = may("diet", "enact_law", met)
			return "" if w == "" else "%s (%s): %s" % [L["name"], "law", w]
		"pass_budget":
			if met.has("within_budget") or (met.has("cabinet_decision") and met.has("reserve_fund_room")):
				return ""
			var w2: String = may("diet", "pass_budget", met)
			return "" if w2 == "" else "%s (supplementary budget): %s" % [L["name"], w2]
		"cabinet_order", "cabinet_decision":
			return "" if met.has("cabinet_decision") else "%s: a cabinet decision is needed" % L["name"]
		"ministerial_ordinance":
			return ""
		_:
			return "" if not String(L["needs"]).begins_with("none (") else "%s: %s decides, not the Cabinet" % [L["name"], String(L["needs"]).trim_prefix("none (").trim_suffix(")")]


func load_state(key: String) -> String:
	var p: String = "res://data/modern/polity/%s_organs.json" % key.to_lower()
	var d: Variant = CANON.load_json(p)
	if not (d is Dictionary):
		error = "organs: no spec at " + p
		return error
	spec = d
	state_key = key
	var comp: Dictionary = spec.get("composition_2024_12", {})
	for h: String in ["house_of_representatives", "house_of_councillors"]:
		if comp.has(h):
			var row: Dictionary = (comp[h] as Dictionary).duplicate()
			row.erase("source")
			seats[h] = row
	governing = (comp.get("governing", []) as Array).duplicate()
	var lp: String = "res://data/modern/polity/%s_laws.json" % key.to_lower()
	if FileAccess.file_exists(lp):
		var l: Variant = JSON.parse_string(FileAccess.get_file_as_string(lp))
		if l is Dictionary:
			laws = (l as Dictionary)["laws"]
	return ""


func house_total(house: String) -> int:
	return int(spec["organs"][house]["seats"])


func governing_seats(house: String) -> int:
	var n: int = 0
	for party: String in (seats.get(house, {}) as Dictionary):
		if governing.has(party):
			n += int(seats[house][party])
	return n


func has_majority(house: String) -> bool:
	return governing_seats(house) * 2 > house_total(house)


func has_two_thirds(house: String) -> bool:
	return governing_seats(house) * 3 >= house_total(house) * 2


## "" when the organ holds the power and every procedure is met (decisions passed in `met`), else why not
func may(organ: String, power: String, met: Array = []) -> String:
	if not spec["powers"].has(power):
		return "no such power " + power
	var P: Dictionary = spec["powers"][power]
	if String(P["organ"]) != organ and not (String(P["organ"]) == "diet" and ["house_of_representatives", "house_of_councillors"].has(organ)):
		return "%s has no power %s (%s)" % [organ, power, P["basis"]]
	for proc: String in P.get("procedure", []):
		match proc:
			"majority_house_of_representatives":
				if not has_majority("house_of_representatives"):
					return "procedure %s not met: governing %d of %d" % [proc, governing_seats("house_of_representatives"), house_total("house_of_representatives")]
			"majority_house_of_councillors_or_two_thirds_override":
				if not has_majority("house_of_councillors") and not has_two_thirds("house_of_representatives"):
					return "procedure %s not met" % proc
			"two_thirds_house_of_representatives":
				if not has_two_thirds("house_of_representatives"):
					return "procedure %s not met" % proc
			"two_thirds_house_of_councillors":
				if not has_two_thirds("house_of_councillors"):
					return "procedure %s not met" % proc
			"enact_law":
				var w: String = may("diet", "enact_law", met)
				if w != "":
					return w
			"pass_budget":
				var w2: String = may("diet", "pass_budget", met)
				if w2 != "":
					return w2
			_:
				if not met.has(proc):
					return "procedure %s not met (no such decision recorded)" % proc
	return ""


func record(month: int, kind: String, organ: String, facts: Dictionary, why: String) -> void:
	events.append({"month": month, "kind": kind, "organ": organ, "facts": facts.duplicate(true), "why": why})


func to_dict() -> Dictionary:
	return {"seats": seats.duplicate(true), "governing": governing.duplicate(), "events": events.duplicate(true)}


func from_dict(d: Dictionary) -> void:
	seats = (d["seats"] as Dictionary).duplicate(true)
	governing = (d["governing"] as Array).duplicate()
	events = (d["events"] as Array).duplicate(true)
