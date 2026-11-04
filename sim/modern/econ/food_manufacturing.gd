extends "res://sim/modern/econ/actor.gd"
## Food manufacturing (BLUEPRINT_v2 2, E2): one actor per jurisdiction. Inputs: raw materials by commodity (crops, livestock products,
## fish) at the 2020 input-output coefficients (t of each input per bn JPY of output: S, derived from the 産業連関表 value coefficients
## and the commodity prices, D), energy, capacity (bn JPY of output a month at full use), labour, money. Outputs: food products (bn JPY),
## capacity use, input demand, a cut when an input is short (Leontief: the output is bounded by the scarcest input's fill, principle B).
## Rules: planned output = min(capacity, demand expectation) (T: demand expectation = last month's sales, start: the published monthly
## output); input bids = planned output x coefficient; output = planned x min over inputs of the market's fill share. The unit cost is
## published on the good each month for its price (cost and the start's markup, world_state).
## Data: data/modern/econ/food_manufacturing_<jurisdiction>.json.
var inputs: Dictionary = {}      # commodity -> {coef (unit per bn JPY of output), label, source}
var self_use: float = 0.0        # own intermediate use per bn JPY of output (S: the IO diagonal)
var planned: float = 0.0
var output: float = 0.0
var input_fill: Dictionary = {}
var projects: Array = []      # capacity projects under way (E6-2)


func load_spec(path: String) -> String:
	var d: Variant = CANON.load_json(path)
	if not (d is Dictionary):
		return "food_manufacturing: no spec at " + path
	setup(d)
	inputs = (d["inputs"] as Dictionary).duplicate(true)
	self_use = float(d.get("self_use_coef", 0.0))
	return ""


## The unit cost of a unit of net product at this month's prices (ISS_AUDIT.md §9.3): the inputs at their prices, the fixed cost as paid
## (its wage part at the wage index when labour runs) spread over the capacity at normal use (the start's, 1.0), less own use
func unit_cost(world: RefCounted) -> float:
	var inp: float = 0.0
	for c: String in inputs:
		inp += float(inputs[c]["coef"]) * float(world.good(c, jurisdiction)["price"])
	var cap: float = float(stocks["capacity_bn_jpy_month"])
	return (inp + fixed_cost(world) / cap) / (1.0 - self_use)


func plan(world: RefCounted, month: int) -> void:
	world.good("food_products", jurisdiction)["unit_cost"] = unit_cost(world)
	var cap: float = float(stocks["capacity_bn_jpy_month"])
	# the start's expectation is the net sales at full use (gross less own use): the gross figure read as excess supply in month 0
	var expect: float = float(stocks.get("demand_expectation", cap * (1.0 - self_use)))
	# capacity projects finish (S4', E6-2: investment)
	var still: Array = []
	for pr: Dictionary in projects:
		if int(pr["finish_month"]) <= month:
			stocks["capacity_bn_jpy_month"] = float(stocks["capacity_bn_jpy_month"]) + float(pr["add_bn_month"])
			cap = float(stocks["capacity_bn_jpy_month"])
			note(month, "capacity", cap, "project finished", "INVEST done +%.1f" % float(pr["add_bn_month"]))
		else:
			still.append(pr)
	projects = still
	# a bankruptcy procedure (P7) runs the plant at a reduced share
	var proc_factor: float = 0.8 if int(stocks.get("procedure_until", -1)) > month else 1.0
	# the inventory target (E6-2, T): half a month of expected sales; the gap is added to the plan
	var g0: Dictionary = world.good("food_products", jurisdiction)
	var target_inv: float = float(stocks.get("inventory_target_months", 0.5)) * expect
	var gap: float = maxf(0.0, target_inv - float(g0["inventory"]))
	# the industry's own intermediate use (S: the IO's diagonal) stays inside the actor: gross output = final demand / (1 - a_self)
	planned = minf(cap * proc_factor, (expect + gap) / (1.0 - self_use))
	# investment rule (T): three months at or above 95% use with expected gross demand at least 2% above capacity (a balanced start sits at
	# capacity and must not build) -> a project of +5% capacity, 12 months, at the declared cost per unit; the cash goes out at the start
	# (and a loan if the floor is breached)
	var use_hist: Array = stocks.get("use_hist", [])
	if use_hist.size() >= 3 and float(use_hist[-1]) >= 0.95 and float(use_hist[-2]) >= 0.95 and float(use_hist[-3]) >= 0.95 and expect / (1.0 - self_use) > 1.02 * cap and projects.is_empty():
		var add: float = 0.05 * cap
		var cost: float = add * float(stocks.get("capex_per_bn_month_capacity", 18.0))
		projects.append({"add_bn_month": add, "finish_month": month + 12, "cost_bn": cost, "start_month": month})
		world.pay(id, "capital_goods", cost, "capacity project +%.1f bn/month" % add)
		note(month, "invest", cost, "3 months >= 95% use and expected demand above capacity (T)", "INVEST +%.1f bn/month, 12 months" % add)
	for c: String in inputs:
		# only the domestic share is bid for at home (S: the self-sufficiency rate); the imported share is HELD external until E4
		var need: float = planned * float(inputs[c]["coef"]) * float(inputs[c].get("domestic_share", 1.0))
		if need > 0.0:
			world.demand(c, jurisdiction, need, id)
	note(month, "planned_output", planned, "min(capacity, demand expectation) (T)", "capacity %.1f, expectation %.1f" % [cap, expect])
	# the product is offered from the inventory; the target stock is held back (offering it too read as excess supply and pushed the price
	# down in the first build), but never less than the expected sales when they are in stock
	var g: Dictionary = world.good("food_products", jurisdiction)
	var offer_qty: float = maxf(float(g["inventory"]) - target_inv, minf(float(g["inventory"]), expect))
	if offer_qty > 0.0:
		world.offer("food_products", jurisdiction, offer_qty, id)


func settle(world: RefCounted, month: int) -> void:
	# Leontief: the scarcest input bounds the output (principle B: a shortage upstream is a cut here)
	var fill: float = 1.0
	var scarcest: String = ""
	input_fill = {}
	for c: String in inputs:
		# Why not a market fill for an external input: it has no producing actor yet (livestock, fisheries: E1 to come), so it is
		# taken as supplied at the start level, a HELD placeholder named in the spec
		var share: float = float(inputs[c].get("domestic_share", 1.0))
		var f: float = 1.0 if bool(inputs[c].get("external", false)) else share * world.fill_share(c, jurisdiction) + (1.0 - share)
		input_fill[c] = f
		if f < fill:
			fill = f
			scarcest = c
	output = planned * fill
	# the net product (gross less own use) goes to inventory for sale
	world.produce("food_products", jurisdiction, output * (1.0 - self_use), id, "gross %.1f x input fill %.3f, less own use %.3f%s" % [planned, fill, self_use, (" (scarcest: " + scarcest + ")") if scarcest != "" else ""])
	note(month, "output", output, "planned x min input fill (Leontief, S coefficients)", "scarcest input: " + (scarcest if scarcest != "" else "none"))
	for c: String in inputs:
		var g: Dictionary = world.good(c, jurisdiction)
		var bought: float = planned * float(inputs[c]["coef"]) * float(inputs[c].get("domestic_share", 1.0)) * world.fill_share(c, jurisdiction) if not bool(inputs[c].get("external", false)) else planned * float(inputs[c]["coef"])
		if bought > 0.0:
			world.pay(id, "market:" + c, bought * float(g["price"]), "purchase of " + c)
	var gp: Dictionary = world.good("food_products", jurisdiction)
	var sold: float = float(gp["traded"])
	if sold > 0.0:
		world.pay("market:food_products", id, sold * float(gp["price"]), "sales of food products")
	# Why the demand seen and not the sales: sales are capped by what was in stock; planning on sales alone spirals down (seen in the
	# first run); the demand observed is traded + unmet
	var seen: float = sold + float(gp["unmet"])
	stocks["demand_expectation"] = seen if seen > 0.0 else float(stocks.get("demand_expectation", planned))
	stocks["capacity_use"] = output / maxf(1e-9, float(stocks["capacity_bn_jpy_month"]))
	var uh: Array = stocks.get("use_hist", [])
	uh.append(stocks["capacity_use"])
	if uh.size() > 12:
		uh.pop_front()
	stocks["use_hist"] = uh


func to_dict() -> Dictionary:
	var d: Dictionary = super.to_dict()
	d["planned"] = planned
	d["output"] = output
	d["input_fill"] = input_fill.duplicate()
	d["projects"] = projects.duplicate(true)
	return d


func from_dict(d: Dictionary) -> void:
	super.from_dict(d)
	planned = float(d.get("planned", 0.0))
	output = float(d.get("output", 0.0))
	input_fill = (d.get("input_fill", {}) as Dictionary).duplicate()
	projects = (d.get("projects", []) as Array).duplicate(true)
