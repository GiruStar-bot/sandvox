extends RefCounted
## The modern mode's data (MODERN_PLAN 1.3), loaded and checked: every file's sha256 against data/modern/MANIFEST.json, then per entity the
## figures of the year before the base year (the start's state: a run starting on 1 January knows last year's figures only, R56 section 0),
## from the base year's vintage file where there is one (stats_v<base>.json), by the stated fill rules:
##   a figure missing in that year takes its latest earlier year (held; "held_from" records the year); none at all is 0 with no_data set
##   growth a year = the figure's last observed yearly change (the year before that -> that year, or the latest pair before it), 0 without a
##   pair; real GDP growth from constant-price GDP (Taiwan: DGBAS's growth rate)
##   electricity demand's growth by demand_rule: "cagr5" (rule v2, PM ruling 2026-10-29 00:30, the default) the compound average yearly
##   change from the earliest year with a figure at most DEMAND_SPAN_YR before the latest one to that latest one, 0 without a pair; "last"
##   (rule v1) the last observed yearly change as above
##   electricity: average MW = TWh a year x 1e6 / 8760 per source; demand likewise; net imports as recorded; all three carried from the data
##   year's middle to the start by the demand's growth (x (1 + growth)^0.5)
##   compute chain: a macro region's share of a good goes to its members by GDP share inside the region (by population where the region has no
##   GDP figure, e.g. Taiwan's); a remainder R53 leaves open is placed
##   by its row's rule (compute_chain.json "rest"); ROW's neon goes to its named entity alone
## Data centres (R55 Q5): the base year's block of dc_history.json gives the start (world TWh and its split, where the vintage differs from
## the compute chain's) and each macro region's persistence growth (a base year with no block of its own takes its data year's block). R58's block of r58.json for the base year (2022 only) gives each macro
## region's PUE and the DC lead time published by then, in place of the compute chain's (dated 2024-25); else every entity takes its PUE.
## No look-ahead (PM ruling 2026-10-28): every compute-chain input carries its data year; those dated after the base year are listed in
## look_ahead and those with none in undated, so a run says what it used from after its start.
## Entity order is entities.json's (sorted by key); the index is internal and never leaves the field.
const DM = preload("res://sim/api/det_math.gd")
const CANON = preload("res://sim/modern/canon.gd")
const DIR := "res://data/modern/"
const SOURCES: Array[String] = ["coal", "gas", "oil", "nuclear", "hydro", "wind", "solar", "bioenergy", "other_renewable"]
const MACROS: Array[String] = ["CN", "TW", "JP", "KR", "US", "EU", "ROW"]
const GOODS: Array[String] = ["fab_capacity", "logic_lt10nm", "atp", "lithography", "photoresist", "silicon_wafers", "gallium", "neon", "dc_electricity"]
const HOURS := 8760.0
const START_CARRY_YR := 0.5               # the data year's middle to 1 January of the base year
const DEMAND_SPAN_YR := 5

var error: String = ""
var base_year: int = 0
var data_year: int = 0                    # the year whose figures are the start's state: the year before the base year (R56 section 0)
var stats_file: String = ""
var demand_rule: String = ""              # "cagr5" | "last"
var keys: PackedStringArray = PackedStringArray()
var names_en: PackedStringArray = PackedStringArray()
var kind: PackedStringArray = PackedStringArray()
var macro := PackedInt32Array()          # entity -> MACROS index
var population := PackedFloat64Array()
var gdp := PackedFloat64Array()
var pop_growth := PackedFloat64Array()   # a year, fraction
var gdp_growth := PackedFloat64Array()
var gdp_real := PackedFloat64Array()      # constant 2015 US$ (0 where WDI has none)
var gdp_real_growth := PackedFloat64Array()
var demand_mw := PackedFloat64Array()
var demand_growth := PackedFloat64Array()
var net_imports_mw := PackedFloat64Array()
var supply_mw := PackedFloat64Array()     # entity x SOURCES
var no_data: Dictionary = {}              # figure -> PackedStringArray of keys with no value at all
var provisional: Dictionary = {}          # key -> {figures, why}: rows kept but to be replaced (stats.json)
var held: Dictionary = {}                 # "key/figure" -> year the value was held from
var borders: Array = []                   # [a, b] land borders, a < b
var regions: Array = []                   # region -> [[entity, share], ...]
var share := PackedFloat64Array()         # entity x GOODS: share of world
var scalars: Dictionary = {}
var lead_days: Dictionary = {}
var manifest: Dictionary = {}
var history: Dictionary = {}              # year before the base -> key -> {population, gdp, generation, demand} as recorded (TWh; null kept)
var dc_world_twh: float = 0.0                # the start's world data-centre electricity, TWh a year
var dc_growth := PackedFloat64Array()        # entity -> persistence growth of its data-centre demand a year (R55 Q5)
var dc_vintage: String = ""
var pue := PackedFloat64Array()              # entity -> power usage effectiveness of its data centres
var look_ahead: PackedStringArray = PackedStringArray()   # compute-chain inputs dated after the base year ("block/name year")
var undated: PackedStringArray = PackedStringArray()      # compute-chain inputs with no stated data year


static func _json(path: String) -> Variant:
	if not FileAccess.file_exists(path):
		return null
	return CANON.load_json_m(path)


static func _sha(path: String) -> String:
	return FileAccess.get_sha256(path)


func load_year(year: int, rule: String = "cagr5") -> String:
	base_year = year
	demand_rule = rule
	if not ["cagr5", "last"].has(rule):
		return _fail("unknown demand growth rule " + rule)
	data_year = year - 1
	manifest = _json(DIR + "MANIFEST.json")
	if not (manifest is Dictionary):
		return _fail("no data/modern/MANIFEST.json")
	for name: String in (manifest["files"] as Dictionary):
		if _sha(DIR + name) != String(manifest["files"][name]["sha256"]):
			return _fail("data/modern/%s differs from its manifest sha256" % name)
	var ent: Dictionary = _json(DIR + "entities.json")
	# Why not one stats file for every base year: a run may only read the vintage published by its start (R56), so a base year with its own
	# vintage file (stats_v2022.json: Ember's July 2022 release) reads that one
	stats_file = "stats_v%d.json" % base_year if FileAccess.file_exists(DIR + "stats_v%d.json" % base_year) else "stats.json"
	var st: Dictionary = _json(DIR + stats_file)
	var er: Dictionary = _json(DIR + "entity_regions.json")
	var cc: Dictionary = _json(DIR + "compute_chain.json")
	var E: int = (ent["entities"] as Array).size()
	for e: Dictionary in ent["entities"]:
		keys.append(String(e["key"]))
		names_en.append(String(e["name_en"]))
		kind.append(String(e["kind"]))
		macro.append(MACROS.find(String(e["macro"])))
	population.resize(E); gdp.resize(E); pop_growth.resize(E); gdp_growth.resize(E); gdp_real.resize(E); gdp_real_growth.resize(E)
	demand_mw.resize(E); demand_growth.resize(E); net_imports_mw.resize(E)
	supply_mw.resize(E * SOURCES.size())
	var years: Array = st["years"]
	provisional = st.get("provisional", {})
	for i: int in E:
		var rows: Dictionary = st["entities"][keys[i]]
		population[i] = _figure(rows, years, keys[i], "population")
		gdp[i] = _figure(rows, years, keys[i], "gdp")
		demand_mw[i] = _figure(rows, years, keys[i], "demand") * 1e6 / HOURS
		net_imports_mw[i] = _figure(rows, years, keys[i], "net_imports", false) * 1e6 / HOURS
		for s: int in SOURCES.size():
			supply_mw[i * SOURCES.size() + s] = _figure(rows, years, keys[i], SOURCES[s], false) * 1e6 / HOURS
		for y0: Variant in years:
			var ys: String = str(int(y0))
			if int(y0) <= data_year and rows.has(ys):
				var hy: Dictionary = history.get(int(y0), {})
				hy[keys[i]] = {"population": rows[ys].get("population"), "gdp": rows[ys].get("gdp"), "generation": rows[ys].get("generation"),
					"demand": rows[ys].get("demand")}
				history[int(y0)] = hy
		pop_growth[i] = _growth(rows, years, "population")
		gdp_growth[i] = _growth(rows, years, "gdp")
		gdp_real[i] = _figure(rows, years, keys[i], "gdp_real", false)
		gdp_real_growth[i] = _growth(rows, years, "gdp_real")
		var rg: Variant = rows.get(str(data_year), {}).get("gdp_real_growth")
		if rg != null:
			gdp_real_growth[i] = float(rg)
		demand_growth[i] = _growth(rows, years, "demand") if demand_rule == "last" else _cagr(rows, years, "demand", DEMAND_SPAN_YR)
		# Why not the figure as it stands on 1 January: a year's figure is its mid-year level (a year's average MW), half a year before the
		# start; demand, generation and net imports move together, so the start stays balanced
		var carry: float = DM.pow(1.0 + demand_growth[i], START_CARRY_YR)
		demand_mw[i] *= carry
		net_imports_mw[i] *= carry
		for s2: int in SOURCES.size():
			supply_mw[i * SOURCES.size() + s2] *= carry
	for b: Array in er["land_borders"]:
		borders.append([int(b[0]), int(b[1])])
	regions = er["regions"]
	scalars = cc["scalars"]
	lead_days = cc["lead_days"]
	_shares(cc, E)
	var replaced: Array = _dc_history(E) + _r58(E)
	for blk: String in ["shares", "scalars", "lead_days"]:
		var rows: Dictionary = cc[blk]
		var names: Array = rows.keys()
		names.sort()
		for n: String in names:
			var y: Variant = (rows[n] as Dictionary).get("data_year")
			if replaced.has(blk + "/" + n):
				continue
			if y == null:
				undated.append(blk + "/" + n)
			elif int(y) > base_year:
				look_ahead.append("%s/%s %d" % [blk, n, int(y)])
	return ""


func _fail(msg: String) -> String:
	error = "modern data: " + msg
	return error


## The base year's value, else the latest earlier year's (held), else 0 and the key in no_data (when strict)
func _figure(rows: Dictionary, years: Array, key: String, fig: String, strict: bool = true) -> float:
	var best: int = -1
	for y: Variant in years:
		var yy: int = int(y)
		if yy <= data_year and rows.has(str(yy)) and rows[str(yy)].get(fig) != null and yy > best:
			best = yy
	if best < 0:
		if strict:
			var ks: PackedStringArray = no_data.get(fig, PackedStringArray())
			ks.append(key)
			no_data[fig] = ks
		return 0.0
	if best != data_year:
		held[key + "/" + fig] = best
	return float(rows[str(best)][fig])


## The compound average yearly change from the earliest year with a figure at most span years before the latest one at or before the data
## year to that latest one (fraction a year), 0 without a pair of years
func _cagr(rows: Dictionary, years: Array, fig: String, span: int) -> float:
	var last: int = -1
	for y: int in range(data_year, int(years[0]) - 1, -1):
		var v: Variant = rows.get(str(y), {}).get(fig)
		if v != null and float(v) > 0.0:
			last = y
			break
	if last < 0:
		return 0.0
	for y0: int in range(maxi(last - span, int(years[0])), last):
		var a: Variant = rows.get(str(y0), {}).get(fig)
		if a != null and float(a) > 0.0:
			return DM.pow(float(rows[str(last)][fig]) / float(a), 1.0 / float(last - y0)) - 1.0
	return 0.0


## The last observed yearly change at or before the data year (fraction a year), 0 without a pair of years
func _growth(rows: Dictionary, years: Array, fig: String) -> float:
	for y: int in range(data_year, int(years[0]), -1):
		var a: Variant = rows.get(str(y - 1), {}).get(fig)
		var b: Variant = rows.get(str(y), {}).get(fig)
		if a != null and b != null and float(a) > 0.0:
			return float(b) / float(a) - 1.0
	return 0.0


func _shares(cc: Dictionary, E: int) -> void:
	share.resize(E * GOODS.size())
	var gdp_in := PackedFloat64Array()
	gdp_in.resize(MACROS.size())
	for i: int in E:
		gdp_in[macro[i]] += gdp[i]
	var fab: Dictionary = cc["shares"]["fab_capacity"]["given"]
	for g: int in GOODS.size():
		var row: Dictionary = cc["shares"][GOODS[g]]
		var m_share := PackedFloat64Array()
		m_share.resize(MACROS.size())
		var given: Dictionary = row["given"]
		var gsum: float = 0.0
		for m0: String in given:
			gsum += float(given[m0])
		# Why not the rounded shares as they are: SIA/BCG's fab capacity sums to 101% and its ATP to 99%, so a row with no remainder rule (every
		# region given), or one above 1, is scaled to 1
		var scale: float = 1.0 / gsum if gsum > 1.0 or (row["rest"] == null and gsum > 0.0) else 1.0
		var left: float = 1.0
		for m: String in given:
			m_share[MACROS.find(m)] = float(given[m]) * scale
			left -= float(given[m]) * scale
		_rest(m_share, left, String(row["rest"]) if row["rest"] != null else "", fab, given, gdp_in)
		_hand_down(g, m_share, String(cc["named_in_row"].get(GOODS[g], "")))


## A good's macro shares to the member entities (see the header)
func _hand_down(g: int, m_share: PackedFloat64Array, named: String) -> void:
	var gdp_in := PackedFloat64Array()
	gdp_in.resize(MACROS.size())
	var pop_in := PackedFloat64Array()
	pop_in.resize(MACROS.size())
	for i: int in keys.size():
		gdp_in[macro[i]] += gdp[i]
		pop_in[macro[i]] += population[i]
	for i2: int in keys.size():
		var m2: int = macro[i2]
		var v: float = 0.0
		if named != "" and MACROS[m2] == "ROW":
			v = m_share[m2] if keys[i2] == named else 0.0
		elif gdp_in[m2] > 0.0:
			v = m_share[m2] * gdp[i2] / gdp_in[m2]
		elif pop_in[m2] > 0.0:
			v = m_share[m2] * population[i2] / pop_in[m2]
		share[i2 * GOODS.size() + g] = v


## PUE per entity and the DC lead time from r58.json's block for the base year, values published after it skipped; returns the compute-chain
## inputs it replaces
func _r58(E: int) -> Array:
	pue.resize(E)
	pue.fill(float(scalars["pue"]["value"]))
	var h: Variant = _json(DIR + "r58.json")
	var blk: Dictionary = (h["years"] as Dictionary).get(str(base_year), {}) if h is Dictionary else {}
	var out: Array = []
	var by: Dictionary = blk.get("pue", {})
	if by.size() == MACROS.size() and by.values().all(func(r: Dictionary) -> bool: return int(r["published"]) <= base_year):
		for i: int in E:
			pue[i] = float(by[MACROS[macro[i]]]["value"])
		out.append("scalars/pue")
	var ld: Dictionary = blk.get("lead_days_dc", {})
	if not ld.is_empty() and int(ld["published"]) <= base_year:
		var dc: Dictionary = (lead_days["dc"] as Dictionary).duplicate()
		dc["days"] = int(ld["value"])
		dc["data_year"] = int(ld["data_year"])
		lead_days["dc"] = dc
		out.append("lead_days/dc")
	return out


## The data-centre start and growth of the base year from dc_history.json (R55 Q5); returns the compute-chain inputs it replaces
func _dc_history(E: int) -> Array:
	dc_world_twh = float(scalars["dc_electricity_twh_2024"]["value"])
	dc_growth.resize(E)
	var h: Variant = _json(DIR + "dc_history.json")
	var blk: Dictionary = {}
	if h is Dictionary:
		blk = (h["years"] as Dictionary).get(str(base_year), (h["years"] as Dictionary).get(str(data_year), {}))
	if blk.is_empty():
		dc_vintage = "none for %d: no growth" % base_year
		return []
	dc_vintage = String(blk["vintage"])
	for i: int in E:
		var gm: Dictionary = blk["growth"].get(MACROS[macro[i]], blk["growth"]["world"])
		dc_growth[i] = float(gm["value"])
	if not blk.has("world_twh"):
		return []
	dc_world_twh = float(blk["world_twh"]["value"])
	var m_share := PackedFloat64Array()
	m_share.resize(MACROS.size())
	var left: float = dc_world_twh
	for m: String in blk["given_twh"]:
		m_share[MACROS.find(m)] = float(blk["given_twh"][m]["value"]) / dc_world_twh
		left -= float(blk["given_twh"][m]["value"])
	var gdp_m := PackedFloat64Array()
	gdp_m.resize(MACROS.size())
	for i2: int in E:
		gdp_m[macro[i2]] += gdp[i2]
	var tot: float = 0.0
	for m2: String in blk["rest_over"]:
		tot += gdp_m[MACROS.find(m2)]
	for m3: String in blk["rest_over"]:
		m_share[MACROS.find(m3)] += left / dc_world_twh * gdp_m[MACROS.find(m3)] / tot
	_hand_down(GOODS.find("dc_electricity"), m_share, "")
	return ["shares/dc_electricity", "scalars/dc_electricity_twh_2024", "scalars/jp_dc_twh"]


## A remainder by its row's stated rule (compute_chain.json "rest"): to JP, to ROW, by fab capacity over the macro regions not given, or
## (dc_electricity) JP's 19 TWh first and then by GDP over TW, KR and ROW
func _rest(m_share: PackedFloat64Array, left: float, rule: String, fab: Dictionary, given: Dictionary, gdp_in: PackedFloat64Array) -> void:
	if left <= 1e-12 or rule == "":
		return
	if rule.begins_with("JP 19 TWh"):
		var jp: float = float(scalars.get("jp_dc_twh", {}).get("value", 19.0)) / float(scalars.get("dc_electricity_twh_2024", {}).get("value", 415.0))
		m_share[MACROS.find("JP")] += jp
		var rest_m: Array[String] = ["TW", "KR", "ROW"]
		var tot: float = 0.0
		for m: String in rest_m:
			tot += gdp_in[MACROS.find(m)]
		for m2: String in rest_m:
			m_share[MACROS.find(m2)] += (left - jp) * gdp_in[MACROS.find(m2)] / tot
		return
	if rule.begins_with("JP"):
		m_share[MACROS.find("JP")] += left
		return
	if rule == "ROW":
		m_share[MACROS.find("ROW")] += left
		return
	var over: Array[String] = []
	for m3: String in MACROS:
		if rule.contains("over JP, KR, US, EU") and not ["JP", "KR", "US", "EU"].has(m3):
			continue
		if rule.contains("all but ROW") and m3 == "ROW":
			continue
		if not given.has(m3):
			over.append(m3)
	var t2: float = 0.0
	for m4: String in over:
		t2 += float(fab[m4])
	for m5: String in over:
		m_share[MACROS.find(m5)] += left * float(fab[m5]) / t2


func entity_count() -> int:
	return keys.size()


func index_of(key: String) -> int:
	return keys.find(key)


func share_of(e: int, good: String) -> float:
	return share[e * GOODS.size() + GOODS.find(good)]
