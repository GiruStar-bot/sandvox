extends RefCounted
## The status layer (BLUEPRINT 2, L1): for an entity that has a status file, the ten statuses' indicators, the stocks the field moves by
## identities, the held outcomes carried with their published trend, and the levers the state actor may pull. Generic: the catalogue
## (data/modern/status/catalog.json) names the indicators; the entity's files (data/modern/<key>/status_<year>.json, levers.json,
## links_<year>.json) give the values, their sources and the action space. Japan is the first entity with a status file.
## Daily step (after the field's): the cohort table ages and moves by the published rates; debt accumulates from the deficit; the net
## external position accumulates from the current account; every held indicator follows its trend; a lever that has reached its lead day
## applies its response function once. Every value is a float; the state is saved as its bytes, so a resume is exact.
const DIR := "res://data/modern/"
const CATALOG := DIR + "status/catalog.json"
const DM = preload("res://sim/api/det_math.gd")   # exp, log, pow bit-equal across machines (V081)
const CANON = preload("res://sim/modern/canon.gd")

const AGES := 101            # single ages 0..100+ (the top one open)
const BUDGET_ROOM := 0.10    # T: a spending line may grow a tenth within the budget's room; beyond that the reserve fund, then a supplementary budget
const RESERVE_FUND_BN := 1000.0   # S: FY2024 一般予備費 1兆円 (jpn_laws.json budget_fy2024)
var legal_check: Callable     # (lever id, met decisions) -> "" or why not; set by the world when the state has organs (S2')
const SEXES := 2             # 0 male, 1 female
const YEAR_DAYS := 365.0

var error: String = ""
var catalog: Dictionary = {}
var entities: PackedStringArray = PackedStringArray()   # keys with a status file
var data: Dictionary = {}       # key -> the status file as loaded
var levers: Dictionary = {}     # key -> the levers file
var links: Dictionary = {}      # key -> the links file
var base_year: int = 0
var day: int = 0
# per entity state
var ind: Dictionary = {}        # key -> indicator -> float (current value)
var ind0: Dictionary = {}       # key -> indicator -> float (start value)
var trend: Dictionary = {}      # key -> indicator -> yearly rate (held indicators)
var cohort: Dictionary = {}     # key -> PackedFloat64Array AGES x SEXES, persons
var qx: Dictionary = {}         # key -> PackedFloat64Array AGES x SEXES, yearly death probability (life table, S)
var hazard: Dictionary = {}     # key -> PackedFloat64Array AGES x SEXES, the daily hazard from qx (computed once)
var trend_day: Dictionary = {}  # key -> indicator -> the daily factor (1 + r)^(1/365) (computed once)
var asfr: Dictionary = {}       # key -> PackedFloat64Array AGES, births per woman-year by age (S or D from TFR)
var lever_value: Dictionary = {} # key -> lever id -> value now
var lever_due: Dictionary = {}   # key -> lever id -> [day due, value] pending
var lever_log: Array = []        # [day, key, lever, value, "set" | "applied" | "refused: why"]
var daily_births: Dictionary = {}
var daily_deaths: Dictionary = {}


func load(year: int, keys: PackedStringArray) -> String:
	base_year = year
	var c: Variant = CANON.load_json(CATALOG)
	if not (c is Dictionary):
		error = "status: no catalogue at " + CATALOG
		return error
	catalog = c
	for k: String in keys:
		var p: String = DIR + k.to_lower() + "/status_%d.json" % year
		if not FileAccess.file_exists(p):
			continue
		var d: Variant = CANON.load_json(p)
		if not (d is Dictionary):
			error = "status: bad file " + p
			return error
		entities.append(k)
		data[k] = d
		var lp: String = DIR + k.to_lower() + "/levers.json"
		levers[k] = CANON.load_json(lp) if FileAccess.file_exists(lp) else {"levers": {}}
		var kp: String = DIR + k.to_lower() + "/links_%d.json" % year
		links[k] = CANON.load_json(kp) if FileAccess.file_exists(kp) else {}
		_init_entity(k)
	day = 0
	return ""


func _init_entity(k: String) -> void:
	var d: Dictionary = data[k]
	var vals: Dictionary = d.get("indicators", {})
	var iv: Dictionary = {}
	var tr: Dictionary = {}
	for id: String in vals:
		var row: Dictionary = vals[id]
		if row.has("value") and (row["value"] is float or row["value"] is int):
			iv[id] = float(row["value"])
			tr[id] = float(row.get("trend", 0.0))
	ind[k] = iv
	ind0[k] = iv.duplicate()
	trend[k] = tr
	var td: Dictionary = {}
	for id: String in tr:
		if float(tr[id]) != 0.0:
			td[id] = DM.pow(1.0 + float(tr[id]), 1.0 / YEAR_DAYS)
	trend_day[k] = td
	# cohort table from the single-age table (persons)
	var co := PackedFloat64Array()
	co.resize(AGES * SEXES)
	var ages: Array = d.get("cohort", {}).get("ages", [])
	var unit: float = float(d.get("cohort", {}).get("unit_persons", 1.0))
	for a: Dictionary in ages:
		var age: int = mini(int(a["age"]), AGES - 1)
		co[age * SEXES] += float(a["male"]) * unit
		co[age * SEXES + 1] += float(a["female"]) * unit
	cohort[k] = co
	# yearly death probabilities: from the file's life table if given, else from the published crude rates by age band (D)
	var q := PackedFloat64Array()
	q.resize(AGES * SEXES)
	var lt: Dictionary = d.get("life_table", {})
	if lt.has("qx_male") and lt.has("qx_female"):
		for age: int in AGES:
			q[age * SEXES] = float(lt["qx_male"][mini(age, (lt["qx_male"] as Array).size() - 1)])
			q[age * SEXES + 1] = float(lt["qx_female"][mini(age, (lt["qx_female"] as Array).size() - 1)])
	else:
		# Why not one crude rate for every age: deaths are concentrated above 75; the Gompertz shape with the published e0 keeps the
		# count of deaths at the published total (D: fitted to the published deaths, not to any check)
		var deaths_pub: float = float(vals.get("deaths", {}).get("value", 0.0))
		var shape := PackedFloat64Array()
		shape.resize(AGES * SEXES)
		var tot: float = 0.0
		for age: int in AGES:
			for s: int in SEXES:
				var g: float = 0.00008 * DM.exp(0.095 * float(age)) * (1.0 if s == 0 else 0.6)
				g = minf(0.6, g + (0.0018 if age == 0 else 0.0))
				shape[age * SEXES + s] = g
				tot += g * co[age * SEXES + s]
		var scale: float = deaths_pub / tot if tot > 0.0 and deaths_pub > 0.0 else 1.0
		for i: int in AGES * SEXES:
			q[i] = minf(0.95, shape[i] * scale)
	qx[k] = q
	# the daily hazard per cell, once (DetMath exp and log are slow per call; the same value every day)
	var hz := PackedFloat64Array()
	hz.resize(AGES * SEXES)
	for i: int in AGES * SEXES:
		hz[i] = 1.0 - DM.exp(DM.log(1.0 - minf(q[i], 0.999)) / YEAR_DAYS)
	hazard[k] = hz
	# age-specific fertility: published if given, else the TFR spread on a published-shaped curve (D)
	var f := PackedFloat64Array()
	f.resize(AGES)
	var fert: Dictionary = d.get("fertility", {})
	if fert.has("asfr"):
		for age: int in AGES:
			f[age] = float(fert["asfr"][mini(age, (fert["asfr"] as Array).size() - 1)])
	elif fert.has("births_by_mother_age5"):
		# Why not the TFR on a curve: the published births by the mother's five-year age group over the women of those ages give rates
		# that return the published births exactly on the start cohort (D from S); each age in a group gets the group's rate
		for g: String in fert["births_by_mother_age5"]:
			var lo: int = int(g.split("-")[0])
			var hi: int = int(g.split("-")[1])
			var women: float = 0.0
			for age: int in range(lo, hi + 1):
				women += co[age * SEXES + 1]
			var rate: float = float(fert["births_by_mother_age5"][g]) / women if women > 0.0 else 0.0
			for age: int in range(lo, hi + 1):
				f[age] = rate
	else:
		var tfr: float = float(vals.get("tfr", {}).get("value", 0.0))
		var w := PackedFloat64Array()
		w.resize(AGES)
		var sw: float = 0.0
		for age: int in range(15, 50):
			var x: float = (float(age) - 31.0) / 5.0
			w[age] = DM.exp(-0.5 * x * x)
			sw += w[age]
		for age: int in range(15, 50):
			f[age] = tfr * w[age] / sw
	asfr[k] = f
	lever_value[k] = {}
	lever_due[k] = {}
	for lid: String in (levers[k] as Dictionary).get("levers", {}):
		lever_value[k][lid] = float(levers[k]["levers"][lid].get("current", 0.0))
	daily_births[k] = 0.0
	daily_deaths[k] = 0.0


func has(k: String) -> bool:
	return data.has(k)


func population_of(k: String) -> float:
	var co: PackedFloat64Array = cohort[k]
	var p: float = 0.0
	for v: float in co:
		p += v
	return p


func value(k: String, id: String) -> float:
	return float((ind[k] as Dictionary).get(id, NAN))


## One day for every entity with a status file: cohort flows, identities, held trends, due levers
func step() -> void:
	day += 1
	for k: String in entities:
		_step_cohort(k)
		_step_identities(k)
		_step_held(k)
		_apply_due(k)
	if day % 365 == 0:
		for k: String in entities:
			_age_cohort(k)


func _step_cohort(k: String) -> void:
	var co: PackedFloat64Array = cohort[k]
	var hz: PackedFloat64Array = hazard[k]
	var f: PackedFloat64Array = asfr[k]
	var deaths: float = 0.0
	var births: float = 0.0
	for age: int in AGES:
		for s: int in SEXES:
			var i: int = age * SEXES + s
			# Why a hazard and not q/365: q is the year's probability; applied daily on a shrinking cohort it undercounts the old (q = 0.5
			# gives 0.39), so the daily hazard -ln(1 - q)/365 returns exactly q over the year
			var dd: float = co[i] * hz[i]
			co[i] -= dd
			deaths += dd
		births += co[age * SEXES + 1] * f[age] / YEAR_DAYS
	# Why not add births to age 0 at once: the newborn join the 0 cohort through the year; the sex ratio at birth 1.05 (S, vital statistics)
	co[0] += births * 1.05 / 2.05
	co[1] += births * 1.0 / 2.05
	var mig: float = float((ind[k] as Dictionary).get("net_migration", 0.0)) / YEAR_DAYS
	# Why not spread migration by the cohort's shape: migrants are young adults (S: ISA, most residents 20-39); 20-39 by equal shares
	for age: int in range(20, 40):
		for s: int in SEXES:
			co[age * SEXES + s] += mig / 40.0
	cohort[k] = co
	daily_births[k] = births
	daily_deaths[k] = deaths
	var iv: Dictionary = ind[k]
	iv["pop_total"] = population_of(k)
	var old: float = 0.0
	for age: int in range(65, AGES):
		old += co[age * SEXES] + co[age * SEXES + 1]
	iv["share_65plus"] = old / maxf(1.0, iv["pop_total"])
	if iv.has("foreign_residents"):
		iv["foreign_residents"] += mig


func _age_cohort(k: String) -> void:
	var co: PackedFloat64Array = cohort[k]
	for s: int in SEXES:
		co[(AGES - 1) * SEXES + s] += co[(AGES - 2) * SEXES + s]
		for age: int in range(AGES - 2, 0, -1):
			co[age * SEXES + s] = co[(age - 1) * SEXES + s]
		co[s] = 0.0
	cohort[k] = co


func _step_identities(k: String) -> void:
	var iv: Dictionary = ind[k]
	# public debt: the general account's deficit financed by bonds accrues daily (identity)
	if iv.has("gov_debt_total") and iv.has("gov_expenditure_general") and iv.has("gov_revenue_general"):
		var deficit: float = iv["gov_expenditure_general"] - iv["gov_revenue_general"]
		iv["gov_debt_total"] += deficit / YEAR_DAYS
		if iv.has("ordinary_jgb"):
			iv["ordinary_jgb"] += deficit / YEAR_DAYS
		if iv.has("gdp_nominal") and iv["gdp_nominal"] > 0.0:
			iv["debt_to_gdp"] = iv["gov_debt_total"] / iv["gdp_nominal"]
	# external position: the current account accrues to the net position and to assets (identity; valuation HELD at 0 in S1)
	if iv.has("niip") and iv.has("current_account"):
		iv["niip"] += iv["current_account"] / YEAR_DAYS
		if iv.has("external_assets"):
			iv["external_assets"] += iv["current_account"] / YEAR_DAYS
	if iv.has("defence_budget") and iv.has("gdp_nominal") and iv["gdp_nominal"] > 0.0:
		iv["defence_share_gdp"] = iv["defence_budget"] / iv["gdp_nominal"]
	if iv.has("physicians") and iv.has("pop_total"):
		iv["physicians_per_100k"] = iv["physicians"] / iv["pop_total"] * 100000.0


func _step_held(k: String) -> void:
	var iv: Dictionary = ind[k]
	var td: Dictionary = trend_day[k]
	for id: String in td:
		if iv.has(id):
			iv[id] *= float(td[id])


## The state actor's menu: every lever of this entity with its bounds; empty when the entity has no status file
func menu(k: String) -> Dictionary:
	if not levers.has(k):
		return {}
	var out: Dictionary = {}
	for lid: String in levers[k]["levers"]:
		var L: Dictionary = levers[k]["levers"][lid]
		out[lid] = {"status": L["status"], "unit": L["unit"], "value": lever_value[k][lid], "min": float(L["min"]), "max": float(L["max"]),
			"lead_days": int(L["lead_days"]), "legal": L.get("legal", "")}
	return out


## "" when the lever act is within its bounds and preconditions, else why not
func check_lever(k: String, lid: String, v: float, changes_this_month: int) -> String:
	if not levers.has(k) or not levers[k]["levers"].has(lid):
		return "no such lever " + lid
	var L: Dictionary = levers[k]["levers"][lid]
	if not is_finite(v) or v < float(L["min"]) or v > float(L["max"]):
		return "lever %s out of bounds" % lid
	# Why refuse a lever already pending (V080): a new set overwrote the due day, so a lever re-pulled every year with a two-year lead
	# never applied; a pending lever is left to apply before it can be pulled again
	if (lever_due[k] as Dictionary).has(lid):
		return "lever %s is already pending until day %d" % [lid, int(lever_due[k][lid][0])]
	var pre: Dictionary = levers[k].get("preconditions", {})
	if changes_this_month >= 4 and pre.has("capacity"):
		return "capacity: more than 4 lever changes this month"
	var iv: Dictionary = ind[k]
	# The law and the organs decide (S2', BLUEPRINT_v2 P2-P3): the polity's check is asked with the decisions the Cabinet itself can
	# make (a cabinet decision) and the budget room; without a polity the old rule (a tax law needs the majority) stands
	if legal_check.is_valid():
		var met: Array = ["cabinet_decision"]
		var r0: Dictionary = L.get("response", {})
		var adds_spending: bool = String(r0.get("target", "")) == "gov_expenditure_general" or String(r0.get("form", "")) == "share"
		var dv: float = v - lever_value[k][lid]
		if not adds_spending or dv <= 0.0 or dv <= BUDGET_ROOM * maxf(absf(lever_value[k][lid]), 1.0):
			met.append("within_budget")
		elif dv <= RESERVE_FUND_BN:
			met.append("reserve_fund_room")
		var why_law: String = legal_check.call(lid, met)
		if why_law != "":
			return "majority: " + why_law if why_law.containsn("majority") else why_law
	elif String(L.get("legal", "")).containsn("law") and iv.has("lower_house_seats_governing") and iv.has("lower_house_seats_total"):
		if iv["lower_house_seats_governing"] * 2.0 < iv["lower_house_seats_total"]:
			return "majority: the governing seats are below half"
	var r: Dictionary = L.get("response", {})
	if String(r.get("target", "")) == "gov_expenditure_general" and iv.has("new_bond_issuance") and iv.has("gov_expenditure_general"):
		var extra: float = v - lever_value[k][lid]
		if extra > 0.0 and (iv["new_bond_issuance"] + extra) / (iv["gov_expenditure_general"] + extra) > 0.45:
			return "fiscal space: bonds would exceed 45% of spending"
	return ""


## Set a lever: it applies after its lead time (the response function runs once on the due day)
func set_lever(k: String, lid: String, v: float) -> void:
	var L: Dictionary = levers[k]["levers"][lid]
	lever_due[k][lid] = [day + int(L["lead_days"]), v]
	lever_log.append([day, k, lid, v, "set"])


func _apply_due(k: String) -> void:
	var due: Dictionary = lever_due[k]
	for lid: String in due.keys():
		if int(due[lid][0]) > day:
			continue
		var v: float = float(due[lid][1])
		var old: float = lever_value[k][lid]
		lever_value[k][lid] = v
		due.erase(lid)
		_respond(k, lid, old, v)
		lever_log.append([day, k, lid, v, "applied"])


## The response function (levers.json): how a lever's change moves its target indicator
func _respond(k: String, lid: String, old: float, v: float) -> void:
	var L: Dictionary = levers[k]["levers"][lid]
	var r: Dictionary = L.get("response", {})
	var target: String = String(r.get("target", ""))
	var iv: Dictionary = ind[k]
	if target == "" or not iv.has(target):
		return
	var kk: float = float(r.get("k", 0.0))
	var dv: float = v - old
	match String(r.get("form", "")):
		"multiplier":
			iv[target] += kk * dv * (100.0 if String(L["unit"]) == "share" else 1.0)
		"multiplier_share":
			# a spending change of dv moves a flow target by k x dv (bn JPY), or a rate target by k x dv / GDP
			if target == "gdp_real_growth" and iv.has("gdp_nominal") and iv["gdp_nominal"] > 0.0:
				iv[target] += kk * dv / iv["gdp_nominal"]
			else:
				iv[target] += kk * dv
		"elasticity":
			if old > 0.0 and v > 0.0:
				iv[target] *= DM.pow(v / old, kk)
		"rate":
			iv[target] = kk * v
		"share":
			if iv.has("gdp_nominal"):
				iv[target] = v * iv["gdp_nominal"]
		_:
			pass   # build_plan, build, licence, fab_spending, election: carried by the field or the actors, not by an indicator


func to_dict() -> Dictionary:
	var st: Dictionary = {"day": day, "ind": {}, "cohort": {}, "lever_value": {}, "lever_due": {}, "lever_log": lever_log.duplicate(true)}
	for k: String in entities:
		var packed := PackedFloat64Array()
		var names: PackedStringArray = PackedStringArray()
		var iv: Dictionary = ind[k]
		var ks: Array = iv.keys()
		ks.sort()
		for id: String in ks:
			names.append(id)
			packed.append(float(iv[id]))
		st["ind"][k] = {"names": names, "bytes": Marshalls.raw_to_base64(packed.to_byte_array())}
		st["cohort"][k] = Marshalls.raw_to_base64((cohort[k] as PackedFloat64Array).to_byte_array())
		st["lever_value"][k] = (lever_value[k] as Dictionary).duplicate()
		st["lever_due"][k] = (lever_due[k] as Dictionary).duplicate(true)
	return st


func from_dict(st: Dictionary) -> void:
	day = int(st["day"])
	for k: String in entities:
		var row: Dictionary = st["ind"][k]
		var packed: PackedFloat64Array = Marshalls.base64_to_raw(String(row["bytes"])).to_float64_array()
		var iv: Dictionary = {}
		var names: PackedStringArray = row["names"]
		for i: int in names.size():
			iv[names[i]] = packed[i]
		ind[k] = iv
		cohort[k] = Marshalls.base64_to_raw(String(st["cohort"][k])).to_float64_array()
		lever_value[k] = (st["lever_value"][k] as Dictionary).duplicate()
		lever_due[k] = (st["lever_due"][k] as Dictionary).duplicate(true)
	lever_log = (st["lever_log"] as Array).duplicate(true)
