extends RefCounted
## The publication register (MODERN_PLAN 4; data/modern/visibility.json from R54): yearly figures per entity, kept apart from the truth, and
## what of them another seat may see on a day. Years before the base year come from the recorded statistics (data.history); each
## simulated year is closed on its last day from the field. A figure of year Y is visible from day_of(Y + 1) + its lag; an estimate shows
## truth x (1 + u), u in [-spread, +spread] fixed by a hash of (entity key, figure, year), the same for every viewer (one public estimate).
## A figure not in visibility.json is never published.
const MD = preload("res://sim/modern/modern_data.gd")
const VIS_PATH := "res://data/modern/visibility.json"
const FIGURES: Array[String] = ["population", "gdp", "generation_twh", "generation_by_source_twh", "demand_twh", "fab_capacity", "dc_capacity_mw",
	"dc_twh"]

var vis: Dictionary = {}
var base_year: int = 0
var E: int = 0
var keys: PackedStringArray = PackedStringArray()
var history: Dictionary = {}   # year -> figure -> PackedFloat64Array (entity, or entity x SOURCES for by source); NAN where not recorded
var acc_gen := PackedFloat64Array()     # this year's TWh, entity x SOURCES
var acc_demand := PackedFloat64Array()
var acc_dc := PackedFloat64Array()


func create(data: RefCounted) -> void:
	vis = MD.CANON.load_json_m(VIS_PATH)
	base_year = data.base_year
	E = data.entity_count()
	keys = data.keys
	acc_gen.resize(E * MD.SOURCES.size())
	acc_demand.resize(E)
	acc_dc.resize(E)
	for y: int in data.history:
		var rows: Dictionary = data.history[y]
		var h: Dictionary = {}
		for fig: String in ["population", "gdp", "generation_twh", "demand_twh"]:
			var a := PackedFloat64Array()
			a.resize(E)
			for e: int in E:
				var src: String = {"population": "population", "gdp": "gdp", "generation_twh": "generation", "demand_twh": "demand"}[fig]
				var v: Variant = rows.get(keys[e], {}).get(src)
				a[e] = float(v) if v != null else NAN
			h[fig] = a
		history[y] = h


static func day_of(year: int, base: int) -> int:
	return (year - base) * 365


func observe_day(f: RefCounted, supply_before: PackedFloat64Array) -> void:
	for i: int in supply_before.size():
		acc_gen[i] += supply_before[i] * 24.0 / 1e6
	for e: int in E:
		acc_demand[e] += f.demand[e] * 24.0 / 1e6
		acc_dc[e] += f.dc_load(e) * f.dc_served[e] * 24.0 / 1e6


func close_year(w: RefCounted, year: int) -> void:
	var f = w.field
	var S: int = MD.SOURCES.size()
	var h: Dictionary = {}
	for fig: String in FIGURES:
		var a := PackedFloat64Array()
		a.resize(E * S if fig == "generation_by_source_twh" else E)
		h[fig] = a
	var mid: int = day_of(year, base_year) + 182
	for e: int in E:
		h["population"][e] = w.population(e, mid)
		h["gdp"][e] = w.data.gdp[e] * MD.DM.pow(1.0 + w.data.gdp_growth[e], float(mid - 182) / 365.0)
		var g: float = 0.0
		for s: int in S:
			h["generation_by_source_twh"][e * S + s] = acc_gen[e * S + s]
			g += acc_gen[e * S + s]
		h["generation_twh"][e] = g
		h["demand_twh"][e] = acc_demand[e]
		h["fab_capacity"][e] = f.fab_cap[e]
		h["dc_capacity_mw"][e] = f.dc_it[e]
		h["dc_twh"][e] = acc_dc[e]
	history[year] = h
	acc_gen.fill(0.0)
	acc_demand.fill(0.0)
	acc_dc.fill(0.0)


## What another seat sees of entity e's figure on a day: {"year", "value" (an Array by source for generation_by_source_twh), "basis"}, or
## {} when nothing of it is visible yet
func published(fig: String, e: int, day: int) -> Dictionary:
	var spec: Dictionary = vis["figures"][fig]
	var basis: String = String(spec["basis"])
	var lag: int = int(spec["lag_days"])
	var spread: float = float(spec["spread"])
	var ex: Dictionary = vis["exceptions"].get(keys[e], {})
	if ex.has(fig):
		basis = String(ex[fig][0])
		lag = int(ex[fig][1])
		spread = 0.0
	var years: Array = history.keys()
	years.sort()
	years.reverse()
	for y: int in years:
		if day_of(y + 1, base_year) + lag > day or not (history[y] as Dictionary).has(fig):
			continue
		var a: PackedFloat64Array = history[y][fig]
		var u: float = (_unit(keys[e], fig, y) * 2.0 - 1.0) * spread if basis == "estimate" else 0.0
		if fig == "generation_by_source_twh":
			var S: int = MD.SOURCES.size()
			var row: Array = []
			for s: int in S:
				row.append(a[e * S + s] * (1.0 + u))
			return {"year": y, "value": row, "basis": basis}
		if is_nan(a[e]):
			return {}
		var out := {"year": y, "value": a[e] * (1.0 + u), "basis": basis}
		if basis == "estimate":
			out["spread"] = spread
		return out
	return {}


static func _unit(key: String, fig: String, year: int) -> float:
	var h: PackedByteArray = ("modern-publish|%s|%s|%d" % [key, fig, year]).sha256_buffer()
	return float(h.decode_u32(0)) / 4294967296.0


func to_dict() -> Dictionary:
	var hy := {}
	for y: int in history:
		hy[y] = (history[y] as Dictionary).duplicate(true)
	return {"history": hy, "acc_gen": acc_gen, "acc_demand": acc_demand, "acc_dc": acc_dc}


func from_dict(d: Dictionary) -> void:
	history = {}
	for y: Variant in d["history"]:
		history[int(y)] = (d["history"][y] as Dictionary).duplicate(true)
	acc_gen = (d["acc_gen"] as PackedFloat64Array).duplicate()
	acc_demand = (d["acc_demand"] as PackedFloat64Array).duplicate()
	acc_dc = (d["acc_dc"] as PackedFloat64Array).duplicate()
