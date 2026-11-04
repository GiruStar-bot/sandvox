extends RefCounted
## The monthly economy (BLUEPRINT_v2 1, the order of a month): the world state, the actors, the environment. One step = one month:
## 1 environment (shocks in force, weather factors), 2 every actor plans (production, offers, bids), 3 markets clear, 4-5 actors settle
## (goods, money, inventories; incomes and costs), 6 the political step (S2'+), 7 save and record. Deterministic; the only draws are the
## keyed shock draws (S4'). Households and the rest of final demand are a stated demand per commodity in S1' (T: the published annual
## consumption spread over the months) until the household actors exist (E3/E4).
## Chronicle rows: every record of the world state's ledgers with its cause, plus each actor's log.
const WS = preload("res://sim/modern/econ/world_state.gd")
const CROP = preload("res://sim/modern/econ/crop_farming.gd")
const FOOD = preload("res://sim/modern/econ/food_manufacturing.gd")
const TH = preload("res://sim/modern/econ/trading_house.gd")
const DM = preload("res://sim/api/det_math.gd")
const BANK = preload("res://sim/modern/econ/banks.gd")
const CANON = preload("res://sim/modern/canon.gd")

const DIR := "res://data/modern/econ/"

const KEYED = preload("res://sim/earth_core/keyed.gd")

var world: RefCounted
var actors: Array = []
var bank: RefCounted = null
var core_inflation: float = 0.027   # a held row (S: 2024 +2.7%; M002 G1): the part of the one CPI no modelled price forms yet
var final_demand: Dictionary = {}   # commodity -> t a month (held)
var labour: RefCounted = null       # the labour market (Phase 5), attached when the representative persons run
var shocks: Array = []              # [{"from_month", "to_month", "yield_factor": {crop: factor}, "why"}]
var error: String = ""


## The trading houses' actor (the state's stocks live there), or null
func trading_house() -> RefCounted:
	for a in actors:
		if a.id.begins_with("trading_houses"):
			return a
	return null


## The state releases rice from its MA stock to the market (the rice_stock_release lever, S3'): quantity in t; what the stock holds
func release_state_rice(month: int, qty_t: float) -> float:
	var th = trading_house()
	if th == null:
		return 0.0
	var have: float = float(th.stocks.get("state_stock_rice", 0.0))
	var q: float = minf(have, qty_t)
	if q <= 0.0:
		return 0.0
	th.stocks["state_stock_rice"] = have - q
	th.stocks["inv_rice"] = float(th.stocks.get("inv_rice", 0.0)) + q
	world.produce("rice", th.jurisdiction, q, th.id, "state stock release (食糧法): %.0f t to the market" % q)
	th.note(month, "release_rice", q, "the government's release decision", "RELEASE")
	return q


func create(jurisdiction: String = "JPN") -> String:
	world = WS.new()
	error = world.create()
	if error != "":
		return error
	var cf = CROP.new()
	error = cf.load_spec(DIR + "crop_farming_%s.json" % jurisdiction.to_lower())
	if error != "":
		return error
	var fm = FOOD.new()
	error = fm.load_spec(DIR + "food_manufacturing_%s.json" % jurisdiction.to_lower())
	if error != "":
		return error
	actors = [cf, fm]
	var th_path: String = DIR + "trading_house_%s.json" % jurisdiction.to_lower()
	if FileAccess.file_exists(th_path):
		var th = TH.new()
		error = th.load_spec(th_path)
		if error != "":
			return error
		actors.append(th)
	var bk_path: String = DIR + "banks_%s.json" % jurisdiction.to_lower()
	if FileAccess.file_exists(bk_path):
		bank = BANK.new()
		error = bank.load_spec(bk_path)
		if error != "":
			return error
		world.cash[bank.id] = float(bank.stocks.get("cash_bn_jpy", 0.0))
	var lg: Variant = CANON.load_json(DIR + "logistics_%s.json" % jurisdiction.to_lower())
	if lg is Dictionary:
		for c: String in (lg as Dictionary)["cap_t_month"]:
			world.logistics[c] = float((lg as Dictionary)["cap_t_month"][c]["value"])
	var fd: Variant = CANON.load_json(DIR + "final_demand_%s.json" % jurisdiction.to_lower())
	if fd is Dictionary:
		for c: String in (fd as Dictionary)["monthly"]:
			final_demand[c] = float((fd as Dictionary)["monthly"][c]["value"])
	for a in actors:
		world.cash[a.id] = float(a.stocks.get("cash_bn_jpy", 0.0))
	# the storable goods' seasonal normal (ISS_AUDIT.md §8.3, D): the normal harvest and reserve from the crop data, the normal import a
	# month from the published flow; the normal use is what a balanced year sells a month
	for c: String in cf.crops:
		var spec: Dictionary = cf.crops[c]
		var h: float = float(spec["area_ha"]) * float(spec["yield_t_ha"])
		var st := {"harvest_t": h, "reserve_t": h * float(spec.get("reserve_share", 0.0)), "harvest_month": int(spec["harvest_month"]),
			"import_t_month": 0.0, "lead_months": 0}
		var th0 = trading_house()
		if th0 != null and th0.goods_spec.has(c) and not bool(th0.goods_spec[c].get("to_state_stock", false)):
			st["import_t_month"] = float(th0.goods_spec[c].get("start_in_transit_t", 0.0))
			st["lead_months"] = int(th0.goods_spec[c].get("lead_months", 1))
		st["use_t_month"] = (h - float(st["reserve_t"])) / 12.0 + float(st["import_t_month"])
		world.storage[c] = st
	# the manufactured goods with a producer (ISS_AUDIT.md §9.2): the markup is the start price over the unit cost at start prices (D)
	world.cost_plus["food_products"] = {"markup": float(world.commodities["food_products"]["start_price"]) / fm.unit_cost(world) - 1.0}
	# the start's inventories (S: 食料需給表 期首在庫 where given)
	var inv: Variant = CANON.load_json(DIR + "start_inventory_%s.json" % jurisdiction.to_lower())
	if inv is Dictionary:
		for c: String in (inv as Dictionary)["inventory"]:
			var g: Dictionary = world.good(c, jurisdiction)
			g["inventory"] = float((inv as Dictionary)["inventory"][c]["value"])
			if (inv as Dictionary)["inventory"][c].has("last_harvest"):
				cf.last_harvest[c] = float((inv as Dictionary)["inventory"][c]["last_harvest"])
	return ""


func declare_shock(from_month: int, to_month: int, yield_factor: Dictionary, why: String) -> void:
	shocks.append({"from_month": from_month, "to_month": to_month, "yield_factor": yield_factor.duplicate(), "why": why})


## A declared loss of cash for an actor in one month (a disaster, a fine, a write-down: the event kinds of S4'), posted to a sink so the
## money ledger stays closed and the cause is recorded
func declare_cash_loss(month: int, actor_id: String, amount_bn: float, why: String) -> void:
	shocks.append({"from_month": month, "to_month": month, "cash_loss": {actor_id: amount_bn}, "why": why})


## Seeded shocks (S4', BLUEPRINT_v2 6): for each year of the horizon, a yield factor per crop and a loss event per actor drawn by keyed
## deterministic hashes from the sourced frequencies in shocks_<j>.json; the same seed repeats, different seeds spread. The crop or
## actor is part of the draw's tag. Why not String.hash() as a key: it is the engine's own and may change with a build (keyed.gd). A yield factor
## applies to the crop's harvest month of that year; the draws are logged as declared shocks with their cause.
func seed_shocks(seed: int, years: int, path: String = "") -> void:
	var file: String = path if path != "" else DIR + "shocks_%s.json" % actors[0].jurisdiction.to_lower()
	var sp: Variant = CANON.load_json(file)
	# Why loud and not a quiet return (the code review, 2d): a seeded run without its shocks reads as a calm run under its seed
	if not (sp is Dictionary):
		error = "econ: no seeded shocks (%s)" % file
		push_error(error)
		return
	var cf = actors[0]
	for y: int in years:
		var yf: Dictionary = {}
		var why: PackedStringArray = PackedStringArray()
		for c: String in (sp as Dictionary)["yield"]:
			var r: Dictionary = (sp as Dictionary)["yield"][c]
			var z: float = KEYED.normal(seed, "yield:" + c, y, 0, 0)
			var f: float = DM.exp(float(r["sigma"]) * z)
			if KEYED.u(seed, "badyear:" + c, y, 0, 0) < float(r["bad_year_p"]):
				f *= float(r["bad_year_factor"])
				why.append("%s bad year" % c)
			yf[c] = f
		# the harvest months of the year: a yield shock of year y lands on each crop's harvest month of that year
		for c: String in yf:
			if not cf.crops.has(c):
				continue
			var hm: int = y * 12 + int(cf.crops[c]["harvest_month"]) - 1
			shocks.append({"from_month": hm, "to_month": hm, "yield_factor": {c: yf[c]}, "why": "seeded yield draw seed %d year %d: %s x%.3f%s" % [seed, y, c, float(yf[c]), (" (" + ", ".join(why) + ")") if why.size() > 0 else ""]})
		for who: String in (sp as Dictionary).get("cash_loss", {}):
			var r2: Dictionary = (sp as Dictionary)["cash_loss"][who]
			if KEYED.u(seed, "loss:" + who, y, 0, 0) < float(r2["p_per_year"]):
				var m: int = y * 12 + KEYED.below(12, seed, "lossmonth:" + who, y, 0, 0)
				shocks.append({"from_month": m, "to_month": m, "cash_loss": {who: float(r2["size_bn"])}, "why": "seeded loss event seed %d year %d: %s" % [seed, y, who]})


## Expectations (S4', E6-1): each commodity's expected price next month = p + lambda x (p - p_prev) (adaptive trend, T: lambda per
## commodity in commodities.json, 0.5 by default); the actors read world.env.expected_price
func _expectations() -> void:
	var ex: Dictionary = {}
	for k: String in world.goods:
		var g: Dictionary = world.goods[k]
		var c: String = k.split("|")[0]
		var lam: float = float((world.commodities.get(c, {}) as Dictionary).get("forecast_lambda", 0.5))
		var p: float = float(g["price"])
		var pp: float = float(g.get("price_prev", p))
		ex[k] = p + lam * (p - pp)
	world.env["expected_price"] = ex


func step() -> void:
	var m: int = world.month
	# 1 environment
	var yf: Dictionary = {}
	for s: Dictionary in shocks:
		if m >= int(s["from_month"]) and m <= int(s["to_month"]):
			for c: String in s.get("yield_factor", {}):
				yf[c] = float(yf.get(c, 1.0)) * float(s["yield_factor"][c])
			for who: String in s.get("cash_loss", {}):
				world.pay(who, "losses", float(s["cash_loss"][who]), "declared loss: " + String(s["why"]))
	world.env = {"yield_factor": yf}
	# the wage index the payers of wages read (labour owns it); absent with people off, so their digests do not carry it
	if labour != null:
		world.env["wage_index"] = labour.wage_index
	_expectations()
	# the inflation the central bank sees (S4', T): the held core rate and the food price index's yearly change, weighted by food's
	# share of the CPI (S: 食料 ウエイト 約25%, 総務省 CPI 2020基準)
	var fp: Dictionary = world.good("food_products", actors[0].jurisdiction)
	var yoy: float = float(fp["price"]) / maxf(1e-9, float(fp.get("price_12m", fp["price"]))) - 1.0
	world.env["inflation"] = 0.75 * core_inflation + 0.25 * yoy
	world.env["food_price_yoy"] = yoy
	# 2 plans (the bank first: the policy rate of the month)
	if bank != null:
		bank.plan(world, m)
	for a in actors:
		a.plan(world, m)
	for c: String in final_demand:
		# final demand answers the price with a published elasticity (S2'): q = q0 x (p / p0)^e
		var g: Dictionary = world.good(c, actors[0].jurisdiction)
		var e: float = float((world.commodities.get(c, {}) as Dictionary).get("demand_elasticity", 0.0))
		# Why no elasticity where the persons scale the demand: each person applies it to the price it believes (Phase 5), and the
		# price response is counted once
		if labour != null and labour.demand_scale.has(c):
			e = 0.0
		var p0: float = float((world.commodities.get(c, {}) as Dictionary).get("start_price", g["price"]))
		# Why DetMath: pow differs in the last bits between libm builds (V081: a Linux digest differed from the Windows one)
		var q: float = final_demand[c] * (DM.pow(float(g["price"]) / p0, e) if e != 0.0 and p0 > 0.0 else 1.0)
		# Phase 5: the persons' consumption plans scale the held series (the economy keeps the level, the persons move it)
		if labour != null and labour.demand_scale.has(c):
			var sc: float = float(labour.demand_scale[c])
			if absf(sc - 1.0) > 1e-9:
				world.record_note("goods", world.gkey(c, actors[0].jurisdiction), "final_demand_scale", 1.0, sc, "persons", "the persons' weighted consumption plan of %s against the start's" % c)
			q *= sc
		world.demand(c, actors[0].jurisdiction, q, "final_demand")
	# 3 markets
	world.clear_markets()
	# 3b the labour market (Phase 5): reads the sectors' use and the expected prices, writes unemployment and the wage index
	if labour != null:
		labour.step(m, float(actors[1].stocks.get("capacity_use", 1.0)), float(world.env.get("inflation", 0.02)))
	# 4-5 settle, then the fixed costs and the bank (E5)
	for a in actors:
		a.settle(world, m)
	for a in actors:
		if a != bank:
			a.pay_fixed_and_finance(world, m, bank, revenue_of(a))
	if bank != null:
		bank.settle(world, m)
	# 7 next month
	world.next_month()


## The month's sales of an actor (the money ledger's transfers into it from the markets)
func revenue_of(a: RefCounted) -> float:
	var r: float = 0.0
	for t: Array in world.transfers:
		if int(t[0]) == world.month and String(t[2]) == a.id and String(t[1]).begins_with("market:"):
			r += float(t[3])
	return r


func chronicle_rows(base_year: int, m: int) -> Array:
	var out: Array = []
	for r: Array in world.records_of(m):
		out.append({"month": m, "date": "%04d-%02d" % [base_year + m / 12, m % 12 + 1], "ledger": r[1], "key": r[2], "field": r[3], "before": r[4], "after": r[5], "by": r[6], "why": r[7]})
	for a in actors:
		for l: Array in a.log:
			if int(l[0]) == m:
				out.append({"month": m, "date": "%04d-%02d" % [base_year + m / 12, m % 12 + 1], "ledger": "actor", "key": l[1], "field": l[2], "before": NAN, "after": l[3], "by": l[4], "why": l[5]})
	return out


func digest() -> String:
	var ctx := HashingContext.new()
	ctx.start(HashingContext.HASH_SHA256)
	# Why numeric only (V082): a "%.0f" in a reason text rounds ties differently per build; the state is the numbers
	ctx.update(var_to_bytes(CANON.numeric_only(to_dict())))
	return ctx.finish().hex_encode()


func to_dict() -> Dictionary:
	var acts: Array = []
	for a in actors:
		acts.append(a.to_dict())
	var d: Dictionary = {"world": world.to_dict(), "actors": acts, "shocks": shocks.duplicate(true), "bank": bank.to_dict() if bank != null else {}}
	if labour != null:
		d["labour"] = labour.to_dict()
	return d


func from_dict(d: Dictionary) -> void:
	world.from_dict(d["world"])
	for i: int in actors.size():
		actors[i].from_dict(d["actors"][i])
	shocks = (d["shocks"] as Array).duplicate(true)
	if labour != null and d.has("labour"):
		labour.from_dict(d["labour"])
	if bank != null and d.has("bank") and not (d["bank"] as Dictionary).is_empty():
		bank.from_dict(d["bank"])
