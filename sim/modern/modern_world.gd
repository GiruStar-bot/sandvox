extends RefCounted
## The modern world (MODERN_PLAN 3): the data of a base year, the field, the actors and the seats. Each day the field steps; on the last day of
## each month every entity decides in entity order: a seated entity's occupant (M5) or else the rule set. A seat's actions that fail the
## check are refused as a whole, logged, and that month the entity's rule actions stand in. No step draws a random number. The publication
## register (modern_publish.gd) is fed each day and closes each simulated year on its last day.
## params: demand_growth ("cagr5", the default: rule v2; "last": rule v1; see modern_data.gd); rules ("r55", the default: R55 Q4's set;
## "placeholder", the M4 THEORY rules; "none"); compute_growth ("persistence", the default:
## R55 Q5's rate per macro region; or one number for every entity). With "r55" the field's supply growth runs only for the committed
## pipeline (each source's lead time), the start's coal retires over COAL_AGE_YR, and Japan holds JOGMEC_DAYS of gallium (all R55);
## pipeline_mix "logit" (default: the pipeline's new plants chosen by the actors' cost logit at the start's costs) or "start" (the start's
## mix of plants); fab_cost "low" | "ref" (default) | "high": R56's cost per wspm band for R57's fab growth rule, which runs when r57.json has
## the base year (2022 only).
## view_salt (hex, at least 16 bytes): the run's secret salt for the views' tokens. It is a run setting, not world state: kept in to_dict()
## under "run" so a resumed or replayed run makes the same tokens, left out of digest() (the world does not depend on it), and never put in
## an observation or a transcript. Without it no view can be made.
const DM = preload("res://sim/api/det_math.gd")
const MD = preload("res://sim/modern/modern_data.gd")
const MF = preload("res://sim/modern/modern_field.gd")
const MC = preload("res://sim/modern/modern_chain.gd")
const MA = preload("res://sim/modern/modern_actors.gd")
const MP = preload("res://sim/modern/modern_publish.gd")
const MCOST = preload("res://sim/modern/modern_costs.gd")
const MV = preload("res://sim/modern/modern_view.gd")
const MS = preload("res://sim/modern/modern_status.gd")
const MB = preload("res://sim/modern/modern_brain.gd")
const MCH = preload("res://sim/modern/modern_chronicle.gd")
const MORG = preload("res://sim/modern/polity/organs.gd")
const MCAB = preload("res://sim/modern/polity/cabinet.gd")
const MECON = preload("res://sim/modern/econ/econ_month.gd")
const MENF = preload("res://sim/modern/polity/enforcement.gd")
const MPUB = preload("res://sim/modern/polity/public.gd")
const MEL = preload("res://sim/modern/polity/election.gd")
const MPEOPLE = preload("res://sim/modern/people/people.gd")
const MLABOUR = preload("res://sim/modern/econ/labour.gd")
const CANON = preload("res://sim/modern/canon.gd")

# Why not leave a build's size open: a seat could start a project larger than any state builds; a month's build is held to the entity's
# demand (MW kinds, at least 1 GW), a day of it (storage, MWh) or, for fabs, twice the entity's capacity and at least a tenth of the world's
# start capacity (THEORY: a check, not a rule)
const MIN_BUILD_CAP_MW := 1000.0
const FAB_BUILD_CAP := 0.1

var data: RefCounted
var field: RefCounted
var actors: RefCounted
var register: RefCounted
var params: Dictionary = {}
var seats: Dictionary = {}    # entity -> occupant with actions(world, entity) -> Array
var status: RefCounted        # the status layer (BLUEPRINT L1): entities with a status file (Japan first)
var brains: Dictionary = {}   # entity -> rule brain (BLUEPRINT 2b) for entities with a status file and no seat
var chronicle: RefCounted     # the record (BLUEPRINT L4)
var polity: Dictionary = {}   # state key -> organs and laws (BLUEPRINT_v2 P1-P3), for states with a polity file
var cabinet: RefCounted = null   # the Cabinet's policies and the Diet's bills (P4-P5), Japan
var econ: RefCounted = null      # the monthly economy (E1-E5), Japan
var enforcement: RefCounted = null   # late charges and procedures in the economic areas (P7), Japan
var public: RefCounted = null        # the public's approval by what it feels (P8), Japan
var election: RefCounted = null      # the election system (P6), Japan
var people: RefCounted = null    # the representative persons (ISS Phase 1), only with params.people
var unemp_prev: float = NAN
var last_election_month: int = 0
var log: Array = []           # [day, entity key, "rule" | "seat" | "refused", action or reason]
var error: String = ""
var view_salt := PackedByteArray()


func create(year: int, p: Dictionary = {}) -> String:
	var cg: Variant = p.get("compute_growth", "persistence")
	params = {"compute_growth": "persistence" if str(cg) == "persistence" else float(cg), "rules": String(p.get("rules", "r55")),
		"demand_growth": String(p.get("demand_growth", "cagr5"))}
	if params["rules"] == "r55":
		params["pipeline"] = "lead"
		params["pipeline_mix"] = String(p.get("pipeline_mix", "logit"))
		params["fab_cost"] = String(p.get("fab_cost", "ref"))
		params["coal_retire_yr"] = 1.0 / MA.COAL_AGE_YR
	view_salt = String(p.get("view_salt", "")).hex_decode()
	# ISS Phase 1: the persons are a run setting (off by default: no existing digest moves); seed and N per prefecture with them
	if bool(p.get("people", false)):
		params["people"] = true
		params["people_seed"] = int(p.get("people_seed", 1))
		params["people_per_prefecture"] = int(p.get("people_per_prefecture", 0))
		if bool(p.get("people_households", false)):
			params["people_households"] = true
	if not MA.RULE_SETS.has(params["rules"]):
		error = "modern world: unknown rule set " + params["rules"]
		return error
	data = MD.new()
	error = data.load_year(year, params["demand_growth"])
	if error != "":
		return error
	field = MF.new()
	field.create(data, params)
	actors = MA.new()
	actors.rule_set = params["rules"]
	if params["rules"] == "r55":
		actors.costs = MCOST.new()
		actors.costs.create(data)
		actors.load_alliances(data, actors.costs.r56["alliances"])
		var r57: Dictionary = CANON.load_json_m("res://data/modern/r57.json")
		var y: String = str(data.base_year)
		if (r57["world_wspm_start"] as Dictionary).has(y):
			var cost_key: String = String(params["fab_cost"])
			actors.fab = {"kappa": float(r57["kappa"]["value"]), "revenue": float(r57["revenue_usd_start"][y]["value"]),
				"world_wspm": float(r57["world_wspm_start"][y]["value"]), "cost_per_wspm": float(r57["cost_per_wspm"][cost_key]),
				"public_share": r57["public_share"]}
			field.util_base = float(r57["utilisation"]["base"])
			field.util_top = float(r57["utilisation"]["top"])
			field.fab_ramp_days = int(r57["ramp_days"]["value"])
		for g20: Variant in actors.costs.r56["restrictions"]["g20"]:
			actors.restrict_p[data.index_of(String(g20))] = float(actors.costs.r56["restrictions"]["per_state_good_yr"])
		if params["pipeline_mix"] == "logit":
			field.pipe_mix = actors.pipeline_mix(field)
		var k: int = data.index_of("JPN") * MC.INPUTS.size() + MC.INPUTS.find("gallium")
		field.input_target[k] = MA.JOGMEC_DAYS
		field.input_stock[k] = MA.JOGMEC_DAYS
	register = MP.new()
	register.create(data)
	status = MS.new()
	error = status.load(year, data.keys)
	if error != "":
		return error
	chronicle = MCH.new()
	chronicle.create(year)
	for k: String in status.entities:
		brains[data.index_of(k)] = MB.new()
		# the state's organs and laws (S2'): the levers go through them
		var org = MORG.new()
		if org.load_state(k) == "":
			polity[k] = org
	if polity.has("JPN"):
		status.legal_check = func(lid: String, met: Array) -> String: return polity["JPN"].may_pull_lever(lid, met)
		# the Cabinet's structured policy and the Diet's bills (S3')
		cabinet = MCAB.new()
		cabinet.setup(polity["JPN"])
		# the monthly economy of Japan (S1'-S3'), stepped at each month end; the state's rice stock answers the release lever
		if FileAccess.file_exists("res://data/modern/econ/crop_farming_jpn.json"):
			econ = MECON.new()
			if econ.create("JPN") != "":
				error = econ.error
				return error
			# Why the weather draws only on request: the S1'-S4' worlds ran without them, and a default draw would move every digest; the
			# audit needs them to split the seed spread into the persons' part and the weather's (ISS_AUDIT_BRIEF.md 2)
			if p.has("shock_seed"):
				params["shock_seed"] = int(p["shock_seed"])
				params["shock_years"] = int(p.get("shock_years", 10))
				econ.seed_shocks(int(params["shock_seed"]), int(params["shock_years"]))
			# S4': enforcement, the public's approval and the elections
			enforcement = MENF.new()
			public = MPUB.new()
			public.load_state("JPN", status.value("JPN", "cabinet_approval"))
			election = MEL.new()
			if election.load_state("JPN") != "":
				election = null
			if bool(params.get("people", false)):
				people = MPEOPLE.new()
				people.households = bool(params.get("people_households", false))
				var prefs: Variant = CANON.load_json("res://data/modern/polity/jpn_prefectures.json")
				error = people.create("JPN", int(params["people_seed"]), status.cohort["JPN"], status.qx["JPN"], (prefs as Dictionary)["prefectures"], int(params["people_per_prefecture"]), data.base_year)
				if error != "":
					return error
				# Phase 5: the economy's labour market runs when the persons supply labour
				econ.labour = MLABOUR.new()
				error = econ.labour.load_state("JPN")
				if error != "":
					return error
	return ""


func advance_to(day: int) -> void:
	var S: int = MD.SOURCES.size()
	var sup := PackedFloat64Array()
	sup.resize(field.E * S)
	while field.day < day:
		for e: int in field.E:
			for s: int in S:
				sup[e * S + s] = field.supply_of(e, s)
		field.step()
		register.observe_day(field, sup)
		var logged: int = status.lever_log.size()
		status.step()
		for i: int in range(logged, status.lever_log.size()):
			var row: Array = status.lever_log[i]
			if String(row[4]) == "applied":
				chronicle.add(field.day, "lever_applied", String(row[1]), "field", {"lever": String(row[2]), "value": float(row[3])}, "lead time over; the response function ran")
				# the rice release reaches the economy's market from the state's MA stock (S3')
				if String(row[2]) == "rice_stock_release" and econ != null and float(row[3]) > 0.0:
					var got: float = econ.release_state_rice(field.day / 30, float(row[3]) * 1000.0)
					chronicle.add(field.day, "release", "JPN", "state", {"rice_t": got, "asked_kt": float(row[3])}, "食糧法: the MA stock to the market")
		if econ != null and MA.is_month_end(field.day):
			if people != null:
				var psup: Dictionary = people.supply()
				econ.labour.receive(float(psup["search_share"]), float(psup["wage_demand_share"]), psup["scales"])
			econ.step()
			if people != null:
				# the economy's figures reach the status layer (the economy owns employment: survey 2)
				status.ind["JPN"]["unemployment_rate"] = econ.labour.u
				var lf: float = status.value("JPN", "employed") + status.value("JPN", "unemployed")
				status.ind["JPN"]["unemployed"] = lf * econ.labour.u
				status.ind["JPN"]["employed"] = lf * (1.0 - econ.labour.u)
			for r: Dictionary in econ.chronicle_rows(data.base_year, econ.world.month - 1):
				if String(r["ledger"]) == "goods" and String(r["field"]) == "price":
					chronicle.add(field.day, "price", "JPN", "market", {"commodity": String(r["key"]).split("|")[0], "before": r["before"], "after": r["after"]}, String(r["why"]))
			if people != null:
				# the persons receive what the economy and the state show this month (ownership: survey 2); they write nothing back yet
				var applied_ids: Array = []
				for i: int in range(logged, status.lever_log.size()):
					if String(status.lever_log[i][4]) == "applied":
						applied_ids.append(String(status.lever_log[i][2]))
				people.step({"inflation_month": float(econ.world.env.get("inflation", 0.02)) / 12.0, "food_price_yoy": float(econ.world.env.get("food_price_yoy", 0.0)), "unemployment_rate": econ.labour.u, "wage_index": econ.labour.wage_index, "levers": applied_ids, "cohort": status.cohort["JPN"]})
				var sm: Dictionary = people.summary()
				chronicle.add(field.day, "people", "JPN", "persons", {"anxiety_p50": float(sm["anxiety_p10_p50_p90"][1]), "discontent_p50": float(sm["discontent_p10_p50_p90"][1]), "real_income_p50": float(sm["real_income_p10_p50_p90"][1]), "pressure_mean": float(sm["pressure_mean"]), "unemployment_rate": float(sm["unemployment_rate"])}, "weighted quantiles over the representative persons")
				chronicle.add(field.day, "labour", "JPN", "economy", {"unemployment_rate": econ.labour.u, "wage_index": econ.labour.wage_index, "food_demand_scale": float(econ.labour.demand_scale.get("food_products", 1.0)), "search_share": econ.labour.search_share}, "the labour market's month (T rules): the persons' supply in, unemployment and the wage index out")
			_s4_month(logged)
		chronicle.observe_field(field, data.keys)
		if field.day % 365 == 0:
			register.close_year(self, data.base_year + field.day / 365 - 1)
			for k: String in status.entities:
				chronicle.add(field.day, "year_close", k, "field", {"pop_total": status.value(k, "pop_total"), "gov_debt_total": status.value(k, "gov_debt_total"),
					"niip": status.value(k, "niip"), "debt_to_gdp": status.value(k, "debt_to_gdp")}, "the year's statuses")
		if MA.is_month_end(field.day):
			_month()


## S4' at a month end: late charges and procedures on the economy's actors; the public's approval from the food price's yearly change,
## the unemployment change and the levers applied this month, written to the cabinet_approval status; a due election run on the approval
## change since the last one and handed to the organs
func _s4_month(logged_before: int) -> void:
	var m: int = econ.world.month - 1
	enforcement.step(m, econ)
	for ev: Dictionary in enforcement.events:
		if int(ev["month"]) == m:
			chronicle.add(field.day, String(ev["kind"]), "JPN", "enforcement", ev["facts"], String(ev["why"]))
	var u: float = status.value("JPN", "unemployment_rate")
	var du: float = 0.0 if is_nan(unemp_prev) else (u - unemp_prev) * 100.0
	unemp_prev = u
	var applied: Array = []
	for i: int in range(logged_before, status.lever_log.size()):
		if String(status.lever_log[i][4]) == "applied":
			applied.append(String(status.lever_log[i][2]))
	var ap: float = public.step(m, float(econ.world.env.get("food_price_yoy", 0.0)), du, applied)
	status.ind["JPN"]["cabinet_approval"] = ap
	if election == null:
		return
	var ym: String = "%04d-%02d" % [data.base_year + m / 12, m % 12 + 1]
	var gov: Array = polity["JPN"].governing.duplicate()
	var d_ap: float = public.change_since(last_election_month)
	var shares: Dictionary = election.vote_shares(gov, d_ap, du, 0.0)
	if ym == String(election.spec["houses"]["house_of_councillors"].get("next_election", "")):
		var r: Dictionary = election.run_upper_house(shares)
		polity["JPN"].seats["house_of_councillors"] = (r["composition"] as Dictionary).duplicate()
		polity["JPN"].record(m, "election", "house_of_councillors", {"elected": r["elected"], "composition": r["composition"]}, "art. 46: half the house every three years")
		chronicle.add(field.day, "election", "JPN", "house_of_councillors", {"elected": r["elected"], "composition": r["composition"], "approval_change": d_ap}, "the half election; the governing share swung by the retrospective rule (T)")
		last_election_month = m
	var lower_by: String = String((status.data["JPN"] as Dictionary).get("indicators", {}).get("next_lower_house_election_by", {}).get("value", ""))
	if ym == lower_by:
		var r2: Dictionary = election.run_lower_house(shares)
		polity["JPN"].seats["house_of_representatives"] = (r2["seats"] as Dictionary).duplicate()
		polity["JPN"].record(m, "election", "house_of_representatives", {"seats": r2["seats"]}, "the general election")
		chronicle.add(field.day, "election", "JPN", "house_of_representatives", {"seats": r2["seats"], "approval_change": d_ap}, "the general election; the governing share swung by the retrospective rule (T)")
		last_election_month = m


func _month() -> void:
	actors.begin_month(field)
	for e: int in field.E:
		var who: String = "rule"
		var acts: Array = []
		if seats.has(e):
			var got: Variant = seats[e].actions(self, e)
			var why: String = ""
			if got is Dictionary:
				acts = got["actions"]
				why = String(got["error"])
			else:
				acts = got
			if why == "":
				why = check_actions(e, acts)
			if why == "":
				who = "seat"
			else:
				log.append([field.day, data.keys[e], "refused", why])
				acts = []
		if who == "rule":
			acts = actors.rule_actions(field, e)
			if brains.has(e) and params["rules"] != "none":
				var thought: Dictionary = brains[e].think(brain_observation(e), status.catalog, status.menu(data.keys[e]), calendar(), field.day / 30)
				# Why not refuse the brain's set as a whole like a seat's: the rule brain is the fallback itself; a lever it may not pull
				# (a tax law without a majority) is dropped and recorded, the rest stands
				for la: Dictionary in thought["actions"]:
					var why_not: String = check_actions(e, [la])
					if why_not == "":
						acts.append(la)
					else:
						brains[e].note_refused(String(la["id"]), field.day / 30)
						chronicle.add(field.day, "lever_refused", data.keys[e], "rule brain", {"lever": String(la["id"]), "value": float(la["value"])}, why_not)
				chronicle.add(field.day, "decision", data.keys[e], "rule brain", {"actions": (thought["actions"] as Array).duplicate(true), "order": thought["order"]},
					"; ".join(PackedStringArray(thought["why"])))
		if check_actions(e, acts) != "":
			log.append([field.day, data.keys[e], "refused", "rule: " + check_actions(e, acts)])
			continue
		_apply(e, acts, who)


## "" when every action is well formed and within bounds, else why not (the first fault)
func check_actions(e: int, acts: Array) -> String:
	var lever_changes: int = 0
	for a: Variant in acts:
		if not (a is Dictionary) or not (a as Dictionary).has("act"):
			return "not an action"
		var act: Dictionary = a
		match String(act["act"]):
			"build":
				var kind: String = String(act.get("kind", ""))
				if not MF.PROJECT_KINDS.has(kind):
					return "unknown project kind " + kind
				var size: float = float(act.get("size", 0.0))
				if not is_finite(size) or size <= 0.0 or size > build_cap(e, kind):
					return "size out of bounds for " + kind
				if kind == "transmission" and link_between(e, int(act.get("link_to", -1))) < 0:
					return "transmission to an entity with no land border"
			"order":
				if not ["dc", "fab"].has(String(act.get("first", ""))):
					return "order first must be dc or fab"
			"licence":
				var g: String = String(act.get("good", ""))
				var to: int = int(act.get("to", -1))
				if not MC.GOODS_LICENSED.has(g):
					return "unknown good " + g
				if to < 0 or to >= field.E or to == e:
					return "no such destination"
				if not (act.get("open") is bool):
					return "open must be true or false"
			"lever":
				if not status.has(data.keys[e]):
					return "no status file for this entity"
				lever_changes += 1
				var why: String = status.check_lever(data.keys[e], String(act.get("id", "")), float(act.get("value", NAN)), lever_changes - 1)
				if why != "":
					return why
			_:
				return "unknown act " + String(act["act"])
	return ""


## What the rule brain perceives: the entity's own statuses in full plus the field's own-side figures it needs (BLUEPRINT 2b step 1)
func brain_observation(e: int) -> Dictionary:
	var k: String = data.keys[e]
	var own: Dictionary = (status.ind[k] as Dictionary).duplicate()
	own["unserved_share"] = field.unserved[e] / maxf(1.0, field.demand[e])
	own["chip_short"] = 1.0 if field.chip_short else 0.0
	var closed: float = 0.0
	for row: Array in field.chain.closed_rows():
		if int(row[2]) == e:
			closed += 1.0
	own["licences_closed_against"] = closed
	return {"own_statuses": own}


## The political calendar for the brains (BLUEPRINT 2b step 3): months to the next lower-house election, from the status file's date
func calendar() -> Dictionary:
	var out: Dictionary = {}
	for k: String in status.entities:
		var row: Dictionary = (status.data[k] as Dictionary).get("indicators", {}).get("next_lower_house_election_by", {})
		var by: String = String(row.get("value", ""))
		if by.length() >= 7:
			var y: int = int(by.substr(0, 4))
			var m: int = int(by.substr(5, 2))
			var now_m: int = (data.base_year + field.day / 365) * 12 + (field.day % 365) / 30 + 1
			out["months_to_lower_house_election"] = float(y * 12 + m - now_m)
	return out


func build_cap(e: int, kind: String) -> float:
	if kind == "fab":
		return maxf(FAB_BUILD_CAP, 2.0 * field.fab_cap[e])
	var mw: float = maxf(MIN_BUILD_CAP_MW, field.base_demand(e) + field.dc_load(e) + field.fab_load(e))
	return mw * 24.0 if kind == "storage" else mw


func link_between(a: int, b: int) -> int:
	if b < 0 or b >= field.E:
		return -1
	for l: int in field.links_of[a]:
		if field.link_a[l] == b or field.link_b[l] == b:
			return l
	return -1


func _apply(e: int, acts: Array, who: String) -> void:
	for act: Dictionary in acts:
		if String(act["act"]) == "build":
			var kind: String = String(act["kind"])
			field.add_project(e, kind, float(act["size"]), link_between(e, int(act.get("link_to", -1))) if kind == "transmission" else -1)
		elif String(act["act"]) == "order":
			field.fab_first[e] = 1 if String(act["first"]) == "fab" else 0
		elif String(act["act"]) == "lever":
			status.set_lever(data.keys[e], String(act["id"]), float(act["value"]))
			chronicle.add(field.day, "lever_set", data.keys[e], who, {"lever": String(act["id"]), "value": float(act["value"])}, "applies after its lead time")
		else:
			field.chain.set_licence(e, String(act["good"]), int(act["to"]), bool(act["open"]))
			chronicle.add(field.day, "licence", data.keys[e], who, {"good": String(act["good"]), "to": data.keys[int(act["to"])], "open": bool(act["open"])}, "")
		log.append([field.day, data.keys[e], who, act.duplicate()])
	actors.note_applied(e, acts, who == "rule")


## The view view_key under this run's salt (its error set when it cannot be made)
func make_view(view_key: String) -> RefCounted:
	var v = MV.new()
	v.load_view(view_key, data, view_salt)
	return v


func population(e: int, at_day: int = -1) -> float:
	var d: int = field.day if at_day < 0 else at_day
	# Why not day 0: WDI's yearly figure is the mid-year population, taken at day 182 of the data year (a year before the base year)
	return data.population[e] * DM.pow(1.0 + data.pop_growth[e], float(d - 182 + 365 * (data.base_year - data.data_year)) / 365.0)


func to_dict() -> Dictionary:
	var br: Dictionary = {}
	for e: int in brains:
		br[str(e)] = brains[e].to_dict()
	var pol: Dictionary = {}
	for k: String in polity:
		pol[k] = polity[k].to_dict()
	var out: Dictionary = {"year": data.base_year, "params": params.duplicate(), "field": field.to_dict(), "actors": actors.to_dict(), "register": register.to_dict(), "log": log.duplicate(true),
		"status": status.to_dict(), "brains": br, "chronicle": chronicle.to_dict(), "polity": pol, "cabinet": cabinet.to_dict() if cabinet != null else {},
		"econ": econ.to_dict() if econ != null else {}, "enforcement": enforcement.to_dict() if enforcement != null else {}, "public": public.to_dict() if public != null else {},
		"s4": {"unemp_prev": unemp_prev, "last_election_month": last_election_month}, "run": {"view_salt": view_salt.hex_encode()}}
	# the persons only when the run has them (people off: no key, so the digests of S1'-S4' stand)
	if people != null:
		out["people"] = people.to_dict()
	return out


## A world restored from to_dict(): created from the same base year and params, then the saved state laid over it
static func from_dict(st: Dictionary) -> RefCounted:
	var w = load("res://sim/modern/modern_world.gd").new()
	var p: Dictionary = (st["params"] as Dictionary).duplicate()
	p["view_salt"] = String(st.get("run", {}).get("view_salt", ""))
	if w.create(int(st["year"]), p) != "":
		return w
	w.field.from_dict(st["field"])
	w.actors.from_dict(st["actors"])
	w.register.from_dict(st["register"])
	w.log = (st["log"] as Array).duplicate(true)
	if st.has("status"):
		w.status.from_dict(st["status"])
		for es: String in st.get("brains", {}):
			if w.brains.has(int(es)):
				w.brains[int(es)].from_dict(st["brains"][es])
		w.chronicle.from_dict(st.get("chronicle", {}))
		for k: String in st.get("polity", {}):
			if w.polity.has(k):
				w.polity[k].from_dict(st["polity"][k])
		if w.cabinet != null and st.has("cabinet"):
			w.cabinet.from_dict(st["cabinet"])
		if w.econ != null and st.has("econ") and not (st["econ"] as Dictionary).is_empty():
			w.econ.from_dict(st["econ"])
		if w.enforcement != null and st.has("enforcement"):
			w.enforcement.from_dict(st["enforcement"])
			w.public.from_dict(st.get("public", {}))
			w.unemp_prev = float(st.get("s4", {}).get("unemp_prev", NAN))
			w.last_election_month = int(st.get("s4", {}).get("last_election_month", 0))
		if w.people != null and st.has("people") and not (st["people"] as Dictionary).is_empty():
			w.people.from_dict(st["people"])
	return w


func digest() -> String:
	var ctx := HashingContext.new()
	ctx.start(HashingContext.HASH_SHA256)
	var st: Dictionary = to_dict()
	st.erase("run")
	# Why drop the chronicle and every string (V082): formatted numbers in reason texts round ties differently per build; the state is
	# the numbers
	st.erase("chronicle")
	# Why re-lay the statuses and the cohort: to_dict() packs them as base64 strings for the save, and numeric_only drops strings, so the
	# digest was blind to them (V083); here they go in as numbers
	var sd: Dictionary = st["status"]
	var indn: Dictionary = {}
	var coh: Dictionary = {}
	for k: String in status.entities:
		indn[k] = (status.ind[k] as Dictionary).duplicate()
		coh[k] = Array(status.cohort[k] as PackedFloat64Array)
	sd["ind"] = indn
	sd["cohort"] = coh
	if people != null:
		st["people"] = people.digest_dict()
	ctx.update(var_to_bytes(CANON.numeric_only(st)))
	return ctx.finish().hex_encode()
