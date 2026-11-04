extends RefCounted
## The modern field (MODERN_PLAN 2): per entity state and the daily step, in entity order. Day 0 is 1 January of the data's base year.
##   demand = base demand x (1 + its last observed yearly growth)^(day / 365) + DC load (used IT x PUE) + fab load (fab capacity x the
##     semiconductor electricity per unit); base demand is the recorded demand less the start's DC and fab loads
##   supply = per source the start's generation plus the base demand's growth since the start split by the start's mix (floored at 0), plus
##     what finished projects added; an entity with no generation takes that growth on its imports; the start's recorded net imports are
##     held as contracted flows. Only DC and fab loads above the start's, and the actors' projects, move an entity off balance.
##     With pipeline "lead" (R55's rule set) that growth runs only for each source's lead time (the plants committed before the start, in
##     pipe_mix when the world sets one) and the actors build the rest; coal from before the start retires at coal_retire_yr of it a year after the coal pipeline's window.
##   balance: surplus goes to deficit land neighbours in one pass by entity order, shared by want (min of deficit and link capacity); storage
##     then discharges into a deficit or charges from a surplus within its size; what is left of a deficit cuts DC load first, then fab load,
##     then is unserved (fab first where the entity chose so); a surplus left is spilled
##   fab output (world chip-years a day) = fab capacity x fab served share x input availability / 365; chips go through ATP to DCs (chain)
##   servers retire over SERVER_LIFE_DAYS; then the free IT capacity = min(capacity x the start's utilisation, the wanted IT) - servers draws
##   the day's chips, and chips held are installed into it at K_IT IT MW per chip-year; the wanted IT is the start's servers grown at the
##   entity's compute growth a year ("persistence": its macro region's R55 Q5 rate; or one number for every entity)
##   fabs (R57, when the world sets it): output x utilisation / the start's utilisation, at the top utilisation while yesterday some wanted IT
##   found no chip (T: the market runs fabs harder when chips are short); a finished fab ramps up in nine equal steps over fab_ramp_days
##   input stocks (days of the fab's full use per input): a closed share of an input is drawn from the stock while it lasts; with the input
##   open again the stock refills to its target within 30 days (T)
##   projects finish on their day; water used = served DC load x 24 h x the DC water per MWh, a tally only
## Units: MW are average MW, storage MWh, fab capacity and chips world chip-years (the start's world fab capacity is 1).
const DM = preload("res://sim/api/det_math.gd")
const MD = preload("res://sim/modern/modern_data.gd")
const MC = preload("res://sim/modern/modern_chain.gd")
# Why not a sourced server life: R53 gives none; 5 years is the usual accounting life (THEORY)
const SERVER_LIFE_DAYS := 5 * 365
# Why not each source's last observed step: a year's step carries the weather (hydro droughts) and one-off closures (Belgium's nuclear),
# and persisted for years it left 112 entities short within a year of 2024; the ordinary load growth is taken as met by the system's own
# planning at the start's mix (THEORY)
# Why not an interconnector table: none is open in R53; 5% of the smaller side's demand stands in (THEORY) until a source replaces it
const LINK_SHARE := 0.05
const COAL := 0
# Why not a lead time of its own for an entity with no generation: its imports grow as a gas plant would be built for it (T)
const GAS := 1
const PROJECT_KINDS: Array[String] = ["coal", "gas", "oil", "nuclear", "hydro", "wind", "solar", "bioenergy", "other_renewable", "storage", "dc",
	"fab", "transmission"]

var data: RefCounted
var chain: RefCounted
var E: int = 0
var day: int = 0
var pue := PackedFloat64Array()   # entity -> PUE (data)
var k_it: float = 0.0            # IT MW installed per chip-year
var u_max: float = 0.0           # IT in use / IT capacity at the start, the running ceiling
var cgrow := PackedFloat64Array()       # entity -> compute growth a year
var pipeline: String = "always"
var pipe_mix := PackedFloat64Array()     # entity x SOURCES: the committed pipeline's mix of new plants (empty: the start's mix)
var pipeline_days := PackedInt32Array()  # SOURCES
var coal_retire_yr: float = 0.0
var input_stock := PackedFloat64Array()  # entity x MC.INPUTS, days
var input_target := PackedFloat64Array() # entity x MC.INPUTS, days
var servers0 := PackedFloat64Array()
var fab_mw_per_unit: float = 0.0
var water_l_per_mwh: float = 0.0
var supply0 := PackedFloat64Array()      # entity x SOURCES
var mix := PackedFloat64Array()          # entity x SOURCES: the start's share of each source in the entity's generation
var gen0 := PackedFloat64Array()         # the start's generation
var supply_built := PackedFloat64Array() # entity x SOURCES
var base0 := PackedFloat64Array()
var demand_growth := PackedFloat64Array()
var net_imports := PackedFloat64Array()
var storage_cap := PackedFloat64Array()
var storage := PackedFloat64Array()
var link_a := PackedInt32Array()
var link_b := PackedInt32Array()
var link_cap := PackedFloat64Array()
var links_of: Array = []                 # entity -> PackedInt32Array of link indices
var dc_it := PackedFloat64Array()        # IT capacity, MW
var servers := PackedFloat64Array()      # IT in use, MW
var chips := PackedFloat64Array()        # chip-years held, not yet installed
var fab_cap := PackedFloat64Array()
var atp := PackedFloat64Array()
var water_l := PackedFloat64Array()
var util_base: float = 1.0              # the fabs' utilisation the start's output stands for (R57: 0.86)
var util_top: float = 1.0               # their utilisation while chips are short (R57: 0.95)
var fab_ramp_days: int = 0              # a finished fab ramps up over this many days in nine steps (R57: 274; 0: at once)
var chip_short: bool = false            # yesterday some wanted IT found no chip
var _ramps: Array = []                  # ramp steps of the fabs finishing today, joined to projects after the day's finishing pass
var fab_first := PackedByteArray()       # 1: a deficit cuts fab load before DC load (the entity's choice; DC first by default)
var projects: Array = []                 # [entity, kind, size, start day, finish day, link index or -1], in the order added, until finished
var done_projects: int = 0
# Why not scan the projects every day: a growing world keeps ~1e4 open, and only a few days a year finish any
var _next_finish_day: int = -1
# the last day's figures (recomputed each step, not state)
var demand := PackedFloat64Array()
var link_flow := PackedFloat64Array()    # a -> b positive
var discharge := PackedFloat64Array()    # MW; negative = charging
var dc_served := PackedFloat64Array()
var fab_served := PackedFloat64Array()
var unserved := PackedFloat64Array()
var spilled := PackedFloat64Array()
var fab_out := PackedFloat64Array()
var withheld := PackedFloat64Array()


func create(d: RefCounted, params: Dictionary = {}) -> void:
	data = d
	chain = MC.new()
	E = d.entity_count()
	var S: int = MD.SOURCES.size()
	var sc: Dictionary = d.scalars
	pue = d.pue.duplicate()
	# Why not the whole nameplate as room for chips: the 2024 table's 100 GW carry 47% of their IT on average (415 TWh), so that load factor
	# is taken as the ceiling (DERIVED) and new chips need new halls
	u_max = float(sc["dc_electricity_twh_2024"]["value"]) * 1e6 / MD.HOURS / (float(sc["dc_capacity_gw_2024"]["value"]) * 1000.0)
	var cg: Variant = params.get("compute_growth", 0.0)
	cgrow = PackedFloat64Array()
	cgrow.resize(E)
	for ce: int in E:
		cgrow[ce] = d.dc_growth[ce] if str(cg) == "persistence" else float(cg)
	pipeline = String(params.get("pipeline", "always"))
	coal_retire_yr = float(params.get("coal_retire_yr", 0.0))
	pipeline_days = PackedInt32Array()
	pipeline_days.resize(S)
	for ps: int in S:
		pipeline_days[ps] = int(d.lead_days[MD.SOURCES[ps]]["days"])
	input_stock = PackedFloat64Array()
	input_stock.resize(E * MC.INPUTS.size())
	input_target = input_stock.duplicate()
	fab_mw_per_unit = float(sc["semi_electricity_twh"]["value"]) * 1e6 / MD.HOURS
	water_l_per_mwh = float(sc["dc_water_bn_l_per_yr"]["value"]) * 1e9 / (float(sc["dc_electricity_twh_2024"]["value"]) * 1e6)
	supply0 = d.supply_mw.duplicate()
	mix = PackedFloat64Array(); mix.resize(E * S)
	gen0 = PackedFloat64Array(); gen0.resize(E)
	for e0: int in E:
		for s0: int in S:
			gen0[e0] += supply0[e0 * S + s0]
		for s1: int in S:
			mix[e0 * S + s1] = supply0[e0 * S + s1] / gen0[e0] if gen0[e0] > 0.0 else 0.0
	supply_built = PackedFloat64Array(); supply_built.resize(E * S)
	for arr: String in ["base0", "demand_growth", "net_imports", "storage_cap", "storage", "dc_it", "servers", "chips", "fab_cap", "atp", "water_l",
			"demand", "discharge", "dc_served", "fab_served", "unserved", "spilled", "fab_out", "withheld"]:
		var a := PackedFloat64Array()
		a.resize(E)
		set(arr, a)
	var no_demand: PackedStringArray = d.no_data.get("demand", PackedStringArray())
	for e: int in E:
		var dc_share: float = d.share_of(e, "dc_electricity")
		servers[e] = d.dc_world_twh * 1e6 / MD.HOURS * dc_share / pue[e]
		dc_it[e] = servers[e] / u_max
		fab_cap[e] = d.share_of(e, "fab_capacity")
		atp[e] = d.share_of(e, "atp")
		var loads: float = servers[e] * pue[e] + fab_cap[e] * fab_mw_per_unit
		net_imports[e] = d.net_imports_mw[e]
		# Why not leave an entity with no electricity record unpowered: its DC and fab shares come by GDP, so it is taken as balanced by
		# imports at the start (THEORY)
		if no_demand.has(d.keys[e]):
			net_imports[e] = loads
		base0[e] = maxf(0.0, d.demand_mw[e] - loads)
		demand_growth[e] = d.demand_growth[e]
		dc_served[e] = 1.0
		fab_served[e] = 1.0
	servers0 = servers.duplicate()
	var used_world: float = 0.0
	for e1: int in E:
		used_world += servers[e1]
	k_it = used_world * 365.0 / float(SERVER_LIFE_DAYS)
	fab_first = PackedByteArray()
	fab_first.resize(E)
	links_of.resize(E)
	for e2: int in E:
		links_of[e2] = PackedInt32Array()
	for b: Array in d.borders:
		var i: int = link_a.size()
		link_a.append(int(b[0]))
		link_b.append(int(b[1]))
		link_cap.append(LINK_SHARE * minf(d.demand_mw[int(b[0])], d.demand_mw[int(b[1])]))
		for side: int in [int(b[0]), int(b[1])]:
			var ls: PackedInt32Array = links_of[side]
			ls.append(i)
			links_of[side] = ls
	link_flow.resize(link_a.size())
	day = 0


func supply_of(e: int, s: int) -> float:
	return supply_at(e, s, day)


## A source's supply on a day (today or ahead) from the start's plants and the pipeline, plus what is built by now
func supply_at(e: int, s: int, at_day: int) -> float:
	var S: int = MD.SOURCES.size()
	var d_at: int = mini(at_day, pipeline_days[s]) if pipeline == "lead" else at_day
	var dg: float = base_demand(e, d_at) - base0[e]
	# Why not the pipeline's mix for a falling load too: a smaller load retires the fleet as it stands, not the plants being built
	var m: float = pipe_mix[e * S + s] if dg > 0.0 and not pipe_mix.is_empty() else mix[e * S + s]
	var grown: float = maxf(0.0, supply0[e * S + s] + dg * m)
	# Why not retire from day 0: in the committed pipeline's window the units retiring are replaced by plants already being built (T); with
	# retirement from day 0 and no replacement before a 5-year lead time, the deficits cut DC load first and the world's DC electricity fell
	# from 270 to 78 TWh in four years
	if s == COAL and coal_retire_yr > 0.0:
		grown *= maxf(0.0, 1.0 - coal_retire_yr * float(maxi(0, at_day - pipeline_days[COAL])) / 365.0)
	return grown + supply_built[e * S + s]


func imports_of(e: int, at_day: int = -1) -> float:
	var d: int = day if at_day < 0 else at_day
	return net_imports[e] + (base_demand(e, mini(d, pipeline_days[GAS]) if pipeline == "lead" else d) - base0[e] if gen0[e] == 0.0 else 0.0)


func supply_total(e: int) -> float:
	var t: float = 0.0
	for s: int in MD.SOURCES.size():
		t += supply_of(e, s)
	return t


func wanted_it(e: int, at_day: int = -1) -> float:
	return servers0[e] * DM.pow(1.0 + cgrow[e], float(day if at_day < 0 else at_day) / 365.0)


func free_it(e: int) -> float:
	return maxf(0.0, minf(dc_it[e] * u_max, wanted_it(e)) - servers[e])


func dc_load(e: int) -> float:
	return servers[e] * pue[e]


func fab_load(e: int) -> float:
	return fab_cap[e] * fab_mw_per_unit


func base_demand(e: int, at_day: int = -1) -> float:
	return base0[e] * DM.pow(1.0 + demand_growth[e], float(day if at_day < 0 else at_day) / 365.0)


## A project: kind is a source, "storage" (size MWh), "dc" (IT MW), "fab" (chip-years a year) or "transmission" (MW on link); it finishes
## after the kind's lead time. Returns its finish day (-1 for an unknown kind or a transmission project with no link).
func add_project(e: int, kind: String, size: float, link: int = -1) -> int:
	if not PROJECT_KINDS.has(kind) or (kind == "transmission" and link < 0):
		return -1
	var fin: int = day + int(data.lead_days[kind]["days"])
	projects.append([e, kind, size, day, fin, link])
	_next_finish_day = -1
	return fin


## The size of the entity's unfinished projects of a kind, finishing by until_day (-1: all)
func pending(e: int, kind: String, until_day: int = -1) -> float:
	var t: float = 0.0
	for p: Array in projects:
		if int(p[0]) == e and String(p[1]) == kind and (until_day < 0 or int(p[4]) <= until_day):
			t += float(p[2])
	return t


func step() -> void:
	var S: int = MD.SOURCES.size()
	var bal := PackedFloat64Array()
	bal.resize(E)
	for e: int in E:
		demand[e] = base_demand(e) + dc_load(e) + fab_load(e)
		bal[e] = supply_total(e) + imports_of(e) - demand[e]
	link_flow.fill(0.0)
	for a: int in E:
		if bal[a] <= 0.0:
			continue
		var ls: PackedInt32Array = links_of[a]
		var want_all: float = 0.0
		for l: int in ls:
			var o: int = link_b[l] if link_a[l] == a else link_a[l]
			if bal[o] < 0.0:
				want_all += minf(-bal[o], link_cap[l])
		if want_all <= 0.0:
			continue
		var give: float = minf(bal[a], want_all)
		for l2: int in ls:
			var o2: int = link_b[l2] if link_a[l2] == a else link_a[l2]
			if bal[o2] >= 0.0:
				continue
			var x: float = give * minf(-bal[o2], link_cap[l2]) / want_all
			bal[o2] += x
			link_flow[l2] += x if link_a[l2] == a else -x
		bal[a] -= give
	for e2: int in E:
		var dis: float = 0.0
		if bal[e2] < 0.0:
			dis = minf(-bal[e2], storage[e2] / 24.0)
		elif bal[e2] > 0.0:
			dis = -minf(bal[e2], (storage_cap[e2] - storage[e2]) / 24.0)
		storage[e2] -= dis * 24.0
		bal[e2] += dis
		discharge[e2] = dis
		var short: float = maxf(0.0, -bal[e2])
		spilled[e2] = maxf(0.0, bal[e2])
		var dl: float = dc_load(e2)
		var fl: float = fab_load(e2)
		var cut_dc: float = 0.0
		var cut_fab: float = 0.0
		if fab_first[e2] == 1:
			cut_fab = minf(short, fl)
			cut_dc = minf(short - cut_fab, dl)
		else:
			cut_dc = minf(short, dl)
			cut_fab = minf(short - cut_dc, fl)
		dc_served[e2] = 1.0 - cut_dc / dl if dl > 0.0 else 1.0
		fab_served[e2] = 1.0 - cut_fab / fl if fl > 0.0 else 1.0
		unserved[e2] = short - cut_dc - cut_fab
	var by_in: PackedFloat64Array = chain.input_availability_by(data, E)
	var NI: int = MC.INPUTS.size()
	for e3: int in E:
		var av: float = 1.0
		for i: int in NI:
			var k: int = e3 * NI + i
			var a: float = by_in[k]
			if a < 1.0 and input_stock[k] > 0.0:
				var draw: float = minf(input_stock[k], 1.0 - a)
				input_stock[k] -= draw
				a += draw
			elif a >= 1.0 and input_stock[k] < input_target[k]:
				input_stock[k] = minf(input_target[k], input_stock[k] + input_target[k] / 30.0)
			av = minf(av, a)
		fab_out[e3] = fab_cap[e3] * (util_top if chip_short else util_base) / util_base * fab_served[e3] * av / 365.0
	var free := PackedFloat64Array()
	free.resize(E)
	for e4: int in E:
		servers[e4] -= servers[e4] / float(SERVER_LIFE_DAYS)
		free[e4] = free_it(e4)
	withheld.fill(0.0)
	var got: PackedFloat64Array = chain.distribute(fab_out, atp, free, withheld)
	for e5: int in E:
		chips[e5] += got[e5] + withheld[e5]
		var inst: float = minf(chips[e5] * k_it, free_it(e5))
		servers[e5] += inst
		chips[e5] -= inst / k_it
		water_l[e5] += dc_load(e5) * dc_served[e5] * 24.0 * water_l_per_mwh
	var unfilled: float = 0.0
	var installed: float = 0.0
	for e6: int in E:
		unfilled += free_it(e6)
		installed += servers[e6]
	chip_short = unfilled > 1e-6 * installed
	day += 1
	if day < _next_finish():
		return
	var left: Array = []
	_ramps = []
	for p: Array in projects:
		if int(p[4]) == day:
			_finish(p, S)
			done_projects += 1
		else:
			left.append(p)
	left.append_array(_ramps)
	projects = left
	_next_finish_day = -1


func _next_finish() -> int:
	if _next_finish_day < 0:
		_next_finish_day = 1 << 62
		for p: Array in projects:
			_next_finish_day = mini(_next_finish_day, int(p[4]))
	return _next_finish_day


func _finish(p: Array, S: int) -> void:
	var e: int = int(p[0])
	var kind: String = String(p[1])
	var size: float = float(p[2])
	var s: int = MD.SOURCES.find(kind)
	if s >= 0:
		supply_built[e * S + s] += size
	elif kind == "storage":
		storage_cap[e] += size
	elif kind == "dc":
		dc_it[e] += size
	elif kind == "fab" and fab_ramp_days > 0:
		for k: int in range(1, 10):
			_ramps.append([e, "fab_ramp", size / 9.0, day, day + fab_ramp_days * k / 9, -1])
	elif kind == "fab" or kind == "fab_ramp":
		fab_cap[e] += size
	elif kind == "transmission":
		link_cap[int(p[5])] += size


func advance(days: int) -> void:
	for i: int in days:
		step()


func to_dict() -> Dictionary:
	return {"base_year": data.base_year, "day": day, "supply_built": supply_built, "storage_cap": storage_cap, "storage": storage,
		"link_cap": link_cap, "fab_first": fab_first, "chip_short": chip_short, "input_stock": input_stock, "input_target": input_target, "dc_it": dc_it, "servers": servers, "chips": chips, "fab_cap": fab_cap, "water_l": water_l,
		"projects": projects.duplicate(true), "done_projects": done_projects, "chain": chain.to_dict()}


## Restores a saved state onto a field created from the same data year
func from_dict(st: Dictionary) -> void:
	day = int(st["day"])
	for k: String in ["supply_built", "storage_cap", "storage", "link_cap", "dc_it", "servers", "chips", "fab_cap", "water_l"]:
		set(k, (st[k] as PackedFloat64Array).duplicate())
	fab_first = (st["fab_first"] as PackedByteArray).duplicate()
	chip_short = bool(st.get("chip_short", false))
	input_stock = (st["input_stock"] as PackedFloat64Array).duplicate()
	input_target = (st["input_target"] as PackedFloat64Array).duplicate()
	projects = (st["projects"] as Array).duplicate(true)
	_next_finish_day = -1
	done_projects = int(st["done_projects"])
	chain.from_dict(st["chain"])


func digest() -> String:
	var ctx := HashingContext.new()
	ctx.start(HashingContext.HASH_SHA256)
	ctx.update(var_to_bytes(to_dict()))
	return ctx.finish().hex_encode()
