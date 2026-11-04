extends SceneTree
## The hindcast (MODERN_PLAN 3): start on 1 January of the base year from the year before's data, run to 31 March 2026 (the end of Japan's
## FY2025), and print each declared check (data/modern/checks.json, R54, declared before any run) with the simulated value next to the
## published one, for the published years from the base year on. Pass or fail only by the declared bounds; a check with no machine bound is
## printed as not computed.
##   godot --headless --path . --script res://tools/modern/hindcast.gd -- [--base 2022 | 2025] [--demand_growth cagr5 | last]
##       [--growth persistence | <a year>] [--rules r55 | placeholder | none] [--pipeline_mix logit | start] [--fab_cost low | ref | high]
## The year before the first simulated one (growth bounds) is the data year as recorded: the start's own figures, population from the
## world's mid-year rule, DC electricity the start's. Japan's fiscal-year change needs two simulated fiscal years.
## Metrics a calendar year (365 days): sums of the daily field (TWh = MW x 24 h / 1e6); population at mid-year (day 182) and 1 October (273).
## Japan's fiscal year Y runs from 1 April Y (day 90) to 31 March Y+1.
const MW = preload("res://sim/modern/modern_world.gd")
const MD = preload("res://sim/modern/modern_data.gd")
const LAST_YEAR := 2025
const FY_START := 90
const S_STATS := ["coal", "gas", "oil", "nuclear", "hydro", "wind", "solar", "bioenergy", "other_renewable"]

var BASE: int = 2022
var YEARS: Array[int] = []

var m: Dictionary = {}   # metric -> {year string: value}


func _add(metric: String, year: int, v: float) -> void:
	var d: Dictionary = m.get(metric, {})
	d[str(year)] = float(d.get(str(year), 0.0)) + v
	m[metric] = d


func _init() -> void:
	var a := {"base": "2022", "demand_growth": "cagr5", "growth": "persistence", "rules": "r55", "pipeline_mix": "logit", "fab_cost": "ref"}
	var args: PackedStringArray = OS.get_cmdline_user_args()
	for i: int in range(0, args.size() - 1, 2):
		a[args[i].trim_prefix("--")] = args[i + 1]
	BASE = int(a["base"])
	for yy: int in range(BASE, LAST_YEAR + 1):
		YEARS.append(yy)
	var w = MW.new()
	if w.create(BASE, {"compute_growth": a["growth"] if a["growth"] == "persistence" else float(a["growth"]), "rules": a["rules"],
			"pipeline_mix": a["pipeline_mix"], "fab_cost": a["fab_cost"], "demand_growth": a["demand_growth"]}) != "":
		print("ERROR ", w.error)
		quit(1)
		return
	var f = w.field
	var d = w.data
	var chn: int = d.index_of("CHN")
	var jpn: int = d.index_of("JPN")
	var S: int = MD.SOURCES.size()
	var coal: int = MD.SOURCES.find("coal")
	var wind: int = MD.SOURCES.find("wind")
	var solar: int = MD.SOURCES.find("solar")
	var end: int = YEARS.size() * 365 + FY_START
	var gen := {}
	var ws := {}
	while f.day < end:
		var day0: int = f.day
		var y: int = BASE + day0 / 365
		var doy: int = day0 % 365
		if doy == 182 or doy == 273:
			var p: float = 0.0
			for e: int in f.E:
				p += w.population(e, day0)
			if doy == 182:
				_add("world_population_m", y, p / 1e6)
			else:
				_add("japan_population_oct1_m", y, w.population(jpn, day0) / 1e6)
		var sup := PackedFloat64Array()
		sup.resize(S)
		for e2: int in f.E:
			for s: int in S:
				sup[s] += f.supply_of(e2, s)
		w.advance_to(day0 + 1)
		var dem: float = 0.0
		var dc: float = 0.0
		for e3: int in f.E:
			dem += f.demand[e3]
			dc += f.dc_load(e3) * f.dc_served[e3]
		var fy: int = y if doy >= FY_START else y - 1
		_add("japan_demand_fy_twh", fy, f.demand[jpn] * 24.0 / 1e6)
		if y > YEARS[-1]:
			continue
		_add("world_demand_twh", y, dem * 24.0 / 1e6)
		_add("china_demand_twh", y, f.demand[chn] * 24.0 / 1e6)
		_add("world_dc_twh", y, dc * 24.0 / 1e6)
		_add("world_coal_twh", y, sup[coal] * 24.0 / 1e6)
		var all: float = 0.0
		for s2: int in S:
			all += sup[s2]
		gen[str(y)] = float(gen.get(str(y), 0.0)) + all * 24.0 / 1e6
		ws[str(y)] = float(ws.get(str(y), 0.0)) + (sup[wind] + sup[solar]) * 24.0 / 1e6
	(m["japan_demand_fy_twh"] as Dictionary).erase(str(BASE - 1))
	for ys: String in gen:
		_add("world_wind_solar_share", int(ys), float(ws[ys]) / float(gen[ys]))
		_add("world_coal_share", int(ys), float(m["world_coal_twh"][ys]) / float(gen[ys]))
	_recorded(w, d.data_year)
	print("HINDCAST start %d, data year %d, demand growth %s, growth %s, rules %s, pipeline mix %s, fab cost %s, %d days; world %s" % [BASE,
		d.data_year, a["demand_growth"], a["growth"], a["rules"], a["pipeline_mix"], a["fab_cost"], f.day, w.digest().left(16)])
	print("LOOKAHEAD inputs dated after %d (not independent of checks on them): %s" % [BASE, ", ".join(d.look_ahead)])
	print("START-YEAR inputs dated %d, published during the first checked year: %s; DC growth block: %s" % [BASE, ", ".join(_dated(d, BASE)),
		d.dc_vintage])
	print("UNDATED inputs: %s" % ", ".join(d.undated))
	for k: String in m:
		print("METRIC %s %s" % [k, JSON.stringify(m[k])])
	var ch: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://data/modern/checks.json"))
	var n_pass: int = 0
	var n_fail: int = 0
	for c: Dictionary in ch["checks"]:
		if c.has("not_testable"):
			print("CHECK %s NOT TESTED (%s): %s | declared before the run: %s" % [c["id"], c["kind"], c["check"], c["not_testable"]])
			continue
		if c["metric"] == null:
			print("CHECK %s not computed (%s): %s" % [c["id"], c["kind"], c["check"]])
			continue
		if String(c["metric"]) == "japan_demand_fy_twh" and (m["japan_demand_fy_twh"] as Dictionary).size() < 2:
			print("CHECK %s not computed (%s): %s | one simulated fiscal year: the change needs FY%d, which began before the start" % [c["id"],
				c["kind"], c["check"], LAST_YEAR - 1])
			continue
		var res: Array = _judge(c)
		var dc_after: PackedStringArray = PackedStringArray(Array(d.look_ahead).filter(_feeds_dc))
		if String(c["metric"]) == "world_dc_twh" and not dc_after.is_empty():
			res[1] = "NOT INDEPENDENT for the build rule: %s dated after %d (R58: no world DC capacity published by then) | " % [", ".join(dc_after), BASE] + String(res[1])
		var ok: bool = res[0]
		n_pass += 1 if ok else 0
		n_fail += 0 if ok else 1
		print("CHECK %s %s (%s): %s | bound %s | %s" % [c["id"], "PASS" if ok else "FAIL", c["kind"], c["check"], c["bound_text"], res[1]])
	var n_nt: int = (ch["checks"] as Array).filter(func(c2: Dictionary) -> bool: return c2.has("not_testable")).size()
	print("HINDCAST checks pass %d fail %d not tested %d not computed %d" % [n_pass, n_fail, n_nt, (ch["checks"] as Array).size() - n_pass - n_fail - n_nt])
	print("DC start %.1f TWh a year, vintage %s" % [d.dc_world_twh, d.dc_vintage])
	print("PROVISIONAL rows: %s" % JSON.stringify(d.provisional))
	quit(0)


## The data year as recorded, for the growth of the first simulated year: the stats file's own rows, the world's population rule on that
## year's mid-year (and Japan's on its 1 October), the start's DC electricity
func _recorded(w: RefCounted, y: int) -> void:
	var d = w.data
	var st: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://data/modern/" + d.stats_file))
	var dem: float = 0.0
	var chn: float = 0.0
	var gen: float = 0.0
	var coal: float = 0.0
	var ws: float = 0.0
	for k: String in st["entities"]:
		var r: Dictionary = st["entities"][k].get(str(y), {})
		var dv: float = float(r.get("demand")) if r.get("demand") != null else 0.0
		dem += dv
		chn += dv if k == "CHN" else 0.0
		for s: String in S_STATS:
			var v: float = float(r.get(s)) if r.get(s) != null else 0.0
			gen += v
			coal += v if s == "coal" else 0.0
			ws += v if s == "wind" or s == "solar" else 0.0
	# Why not world.population() on a day before the start: a negative day means today there; the recorded year's mid-year is the figure
	# itself, and 1 October is 91 days on at the same rate
	var p: float = 0.0
	for e: int in w.field.E:
		p += d.population[e]
	var jp: int = d.index_of("JPN")
	var jp_oct: float = d.population[jp] * pow(1.0 + d.pop_growth[jp], 91.0 / 365.0)
	for pair: Array in [["world_demand_twh", dem], ["china_demand_twh", chn], ["world_coal_twh", coal], ["world_wind_solar_share", ws / gen],
			["world_coal_share", coal / gen], ["world_dc_twh", d.dc_world_twh], ["world_population_m", p / 1e6],
			["japan_population_oct1_m", jp_oct / 1e6]]:
		var ser: Dictionary = m.get(pair[0], {})
		if not ser.has(str(y)):
			ser[str(y)] = pair[1]
			m[pair[0]] = ser


## compute-chain inputs dated exactly year y
func _dated(d: RefCounted, y: int) -> PackedStringArray:
	var cc: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://data/modern/compute_chain.json"))
	var out := PackedStringArray()
	for blk: String in ["shares", "scalars", "lead_days"]:
		var names: Array = (cc[blk] as Dictionary).keys()
		names.sort()
		for n: String in names:
			var dy: Variant = cc[blk][n].get("data_year")
			if dy != null and int(dy) == y:
				out.append(blk + "/" + n)
	return out


## a look-ahead input the data centres' electricity is computed from (capacity, electricity, PUE, lead time, shares), not their water
func _feeds_dc(n: String) -> bool:
	for pre: String in ["scalars/dc_capacity", "scalars/dc_electricity", "scalars/pue ", "lead_days/dc ", "shares/dc_"]:
		if n.begins_with(pre):
			return true
	return false


func _growth(series: Dictionary, y: String) -> Variant:
	var prev: String = str(int(y) - 1)
	if not series.has(y) or not series.has(prev) or float(series[prev]) == 0.0:
		return null
	return float(series[y]) / float(series[prev]) - 1.0


## [ok, text]: every part of the declared bound, each year it names
func _judge(c: Dictionary) -> Array:
	var sim: Dictionary = m[c["metric"]]
	var pub: Dictionary = c["published"]
	var b: Dictionary = c["bounds"]
	var ok: bool = true
	var parts: PackedStringArray = []
	for y: String in pub:
		if int(y) < BASE:
			continue
		var v: float = float(sim.get(y, NAN))
		var p: float = float(pub[y])
		var line: String = "%s sim %s pub %s" % [y, String.num(v, 4), String.num(p, 4)]
		if b.has("level_rel") and b.has("level_not_applicable"):
			line += " level %+.2f%% not applicable" % [(v / p - 1.0) * 100.0]
		elif b.has("level_rel"):
			var good: bool = absf(v / p - 1.0) <= float(b["level_rel"])
			ok = ok and good
			line += " level %+.2f%% %s" % [(v / p - 1.0) * 100.0, "ok" if good else "OUT"]
		if b.has("level_abs"):
			var good2: bool = absf(v - p) <= float(b["level_abs"])
			ok = ok and good2
			line += " level %+.2f pt %s" % [(v - p) * 100.0, "ok" if good2 else "OUT"]
		var g: Variant = _growth(sim, y)
		if g != null:
			line += " growth %+.2f%%" % (float(g) * 100.0)
			if b.has("growth") and b["growth"] is Array:
				var good3: bool = float(g) >= float(b["growth"][0]) and float(g) <= float(b["growth"][1])
				ok = ok and good3
				line += " " + ("ok" if good3 else "OUT")
			if b.has("growth") and b["growth"] is Dictionary and (b["growth"] as Dictionary).has(y):
				var r: Array = b["growth"][y]
				var good4: bool = float(g) >= float(r[0]) and float(g) <= float(r[1])
				ok = ok and good4
				line += " " + ("ok" if good4 else "OUT")
			if b.has("growth_pub") and (b["growth_pub"] as Dictionary).has(y):
				var r2: Array = b["growth_pub"][y]
				var pt: float = float(b["growth_pt"])
				var good5: bool = float(g) >= float(r2[0]) - pt and float(g) <= float(r2[1]) + pt
				ok = ok and good5
				line += " vs pub %+.1f..%+.1f%% %s" % [float(r2[0]) * 100.0, float(r2[1]) * 100.0, "ok" if good5 else "OUT"]
			if b.get("positive", false):
				ok = ok and float(g) > 0.0
			if b.get("rises", false):
				ok = ok and float(g) > 0.0
		if b.has("range") and (b["range"] as Dictionary).has(y):
			var r3: Array = b["range"][y]
			var good6: bool = v >= float(r3[0]) and v <= float(r3[1])
			ok = ok and good6
			line += " in [%s, %s] %s" % [r3[0], r3[1], "ok" if good6 else "OUT"]
		if b.has("share") and (b["share"] as Dictionary).has(y):
			var sv: float = float(m[b["share_metric"]].get(y, NAN))
			var good7: bool = absf(sv - float(b["share"][y])) <= float(b["share_abs"])
			ok = ok and good7
			line += " share %.3f pub %.3f %s" % [sv, float(b["share"][y]), "ok" if good7 else "OUT"]
		parts.append(line)
	return [ok, "; ".join(parts)]
