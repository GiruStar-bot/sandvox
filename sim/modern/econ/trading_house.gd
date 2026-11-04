extends "res://sim/modern/econ/actor.gd"
## Trading houses (BLUEPRINT_v2 2, E4-2): one aggregate actor per jurisdiction deciding imports by commodity. Each month, for each
## commodity it trades: margin per unit = expected domestic price - (foreign price x FX + freight + tariff) (the owner's formula); when
## the margin is positive it orders the lesser of: its want, the foreign supply capacity a month (S/T), the port and shipping capacity
## (logistics), and what its cash buys. The want is its last sales plus the market's unmet demand, less its stock left from before this
## month's arrivals and what is in transit (T, ISS_AUDIT.md §8.6). Orders arrive after the lead time (one month, T) into its inventory and are
## offered in the domestic market at the domestic price; what does not sell stays in its stock. The quantity in transit is published on
## the good for the market's availability. Foreign prices, FX, freight, tariffs
## and capacities are external conditions (data/modern/econ/trading_house_<j>.json) until the counterparts get profiles (S3').
## Reason codes: MARGIN_NEG (no import), ORDER (quantity and the binding limit), ARRIVE.
var goods_spec: Dictionary = {}   # commodity -> {foreign_price_usd_t, freight_usd_t, tariff_jpy_t, foreign_capacity_t_month, lead_months, label, source}
var fx_jpy_usd: float = 150.0
var orders: Array = []            # [{commodity, qty, arrive_month, cost_bn}]
var last_margin: Dictionary = {}


func load_spec(path: String) -> String:
	var d: Variant = CANON.load_json(path)
	if not (d is Dictionary):
		return "trading_house: no spec at " + path
	setup(d)
	goods_spec = (d["goods"] as Dictionary).duplicate(true)
	fx_jpy_usd = float(d["fx_jpy_usd"]["value"])
	# the first month's arrivals: the published import flow, already on the water at the start (D)
	for c: String in goods_spec:
		var q: float = float(goods_spec[c].get("start_in_transit_t", 0.0))
		if q > 0.0:
			orders.append({"commodity": c, "qty": q, "arrive_month": 0, "order_month": -1, "cost_bn": q * landed_cost_bn_per_t(c)})
	return ""


func landed_cost_bn_per_t(c: String) -> float:
	var g: Dictionary = goods_spec[c]
	return (float(g["foreign_price_usd_t"]) + float(g["freight_usd_t"])) * fx_jpy_usd / 1e9 + float(g["tariff_jpy_t"]) / 1e9


func plan(world: RefCounted, month: int) -> void:
	# arrivals first: orders due this month land in the inventory and are offered
	var still: Array = []
	var arrived := {}
	for o: Dictionary in orders:
		if int(o["arrive_month"]) <= month:
			var oc: String = String(o["commodity"])
			if bool(goods_spec[oc].get("to_state_stock", false)):
				# the state's quota imports (MA rice) go to the state's stock, not the market (S); released by the stock lever (S3')
				stocks["state_stock_" + oc] = float(stocks.get("state_stock_" + oc, 0.0)) + float(o["qty"])
				note(month, "state_stock_" + oc, float(stocks["state_stock_" + oc]), "quota import to the state's stock", "ARRIVE state stock")
				continue
			world.produce(oc, jurisdiction, float(o["qty"]), id, "import arrived: ordered month %d" % int(o["order_month"]))
			var g0: Dictionary = world.good(oc, jurisdiction)
			g0["imported"] += float(o["qty"])
			# Why an own stock beside the pooled ledger (first S2' run): offering the pooled inventory offered the farmers' rice too, and
			# the price fell 20% a month; a seller offers only what it holds
			stocks["inv_" + oc] = float(stocks.get("inv_" + oc, 0.0)) + float(o["qty"])
			arrived[oc] = float(arrived.get(oc, 0.0)) + float(o["qty"])
			note(month, "arrive_" + oc, float(o["qty"]), "lead time over", "ARRIVE")
		else:
			still.append(o)
	orders = still
	for c: String in goods_spec:
		var g: Dictionary = world.good(c, jurisdiction)
		var own: float = float(stocks.get("inv_" + c, 0.0))
		if own > 0.0:
			world.offer(c, jurisdiction, own, id)
		var cost: float = landed_cost_bn_per_t(c)
		# Why the expected and not the current price (S4', E6): the cargo sells next month; the trader's forecast is the world's
		# adaptive expectation (p + lambda x the last move, T)
		var p_exp: float = float((world.env.get("expected_price", {}) as Dictionary).get(world.gkey(c, jurisdiction), g["price"]))
		var margin: float = p_exp - cost
		# the order is a forward contract at today's landed cost (E6-3): the price is fixed now, the cargo comes later
		last_margin[c] = margin
		# Why state trading ignores the margin: wheat and the minimum-access rice are imported by the state to cover the gap, up to the
		# quota, whatever a private trader would earn (S: 国家貿易)
		if margin <= 0.0 and not bool(goods_spec[c].get("state_trading", false)):
			note(month, "margin_" + c, margin, "domestic price - landed cost", "MARGIN_NEG")
			continue
		# Why the sales and unmet demand seen and not a forecast: expectations are E6 (S4'); until then the trading houses answer the
		# market they saw (T). Why the unsold stock counts against the want: re-importing the arrivals' flow whatever stayed unsold piled
		# stock up and drove the price down. Why not a cover of (1 + lead) months: it doubled each month's gap and the imports swung
		# (ISS_AUDIT.md §8.6).
		var in_transit: float = _in_transit(c)
		var sold_last: float = float((g.get("traded_by", {}) as Dictionary).get(id, goods_spec[c].get("start_in_transit_t", 0.0)))
		var carried: float = maxf(0.0, own - float(arrived.get(c, 0.0)))
		var want: float = maxf(0.0, sold_last + float(g["unmet_last"]) - carried - in_transit)
		if bool(goods_spec[c].get("to_state_stock", false)):
			want = float(goods_spec[c]["foreign_capacity_t_month"])   # the quota is filled every month (S: MA)
		var cap_f: float = float(goods_spec[c]["foreign_capacity_t_month"])
		var cap_l: float = float(world.logistics.get(c, INF)) if world.get("logistics") != null else INF
		var cash: float = float(world.cash.get(id, 0.0))
		var afford: float = cash / cost if cost > 0.0 else INF
		var qty: float = minf(minf(want, cap_f), minf(cap_l, afford))
		var binding: String = "want"
		if qty == cap_f:
			binding = "foreign capacity"
		elif qty == cap_l:
			binding = "logistics"
		elif qty == afford:
			binding = "cash"
		if qty <= 0.0:
			note(month, "order_" + c, 0.0, "nothing wanted", "ORDER none")
			continue
		var lead: int = int(goods_spec[c].get("lead_months", 1))
		orders.append({"commodity": c, "qty": qty, "arrive_month": month + lead, "order_month": month, "cost_bn": qty * cost})
		world.pay(id, "foreign:" + c, qty * cost, "import order of %s (%.0f t at %.6f bn/t)" % [c, qty, cost])
		world.add_contract(id, "foreign:" + c, c, qty, cost, month + lead, "forward")
		note(month, "order_" + c, qty, "min(want, foreign cap, logistics, cash)", "ORDER margin %s bn/t, binding %s" % [String.num(margin, 9), binding])
	for c: String in goods_spec:
		if not bool(goods_spec[c].get("to_state_stock", false)):
			world.good(c, jurisdiction)["in_transit"] = _in_transit(c)


func _in_transit(c: String) -> float:
	var q: float = 0.0
	for o: Dictionary in orders:
		if String(o["commodity"]) == c:
			q += float(o["qty"])
	return q


func settle(world: RefCounted, month: int) -> void:
	for c: String in goods_spec:
		var g: Dictionary = world.good(c, jurisdiction)
		var sold: float = float(g.get("traded_by", {}).get(id, 0.0))
		if sold > 0.0:
			stocks["inv_" + c] = float(stocks.get("inv_" + c, 0.0)) - sold
			world.pay("market:" + c, id, sold * float(g["price"]), "sales of imported " + c)
			note(month, "sold_" + c, sold, "market clearing", "")


func to_dict() -> Dictionary:
	var d: Dictionary = super.to_dict()
	d["orders"] = orders.duplicate(true)
	d["last_margin"] = last_margin.duplicate()
	return d


func from_dict(d: Dictionary) -> void:
	super.from_dict(d)
	orders = (d.get("orders", []) as Array).duplicate(true)
	last_margin = (d.get("last_margin", {}) as Dictionary).duplicate()
