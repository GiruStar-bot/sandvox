extends SceneTree
## M038's soybean path (and, with --good, any food input: M038b's rice) (math-reports e7673fa7; the PM, TO_E 20:45 item 6): the normal economy for 12 months, printing soybeans' price,
## expected price, landed cost, margin, MARGIN_NEG, the trading houses' order, arrivals, carried stock, demand, traded and food
## manufacturing's soybean fill. With --variant own_need the start's in-transit soybeans are the model's own import need at month 0
## (food manufacturing's planned soybean bid + the held final demand - the domestic crop / 12) instead of the published import flow.
##   godot --headless --path . --script res://tools/modern/soy_path.gd -- [--good rice] [--variant own_need] [--months 12]
const EM = preload("res://sim/modern/econ/econ_month.gd")


func _init() -> void:
	var a := {"variant": "", "months": "12", "good": "soybeans"}
	var args: PackedStringArray = OS.get_cmdline_user_args()
	for i: int in range(0, args.size() - 1, 2):
		a[args[i].trim_prefix("--")] = args[i + 1]
	var e = EM.new()
	if e.create("JPN") != "":
		print("ERROR ", e.error)
		quit(1)
		return
	var G: String = String(a["good"])
	var cf = e.actors[0]
	var fm = e.actors[1]
	var th = e.trading_house()
	var crop_month: float = float(cf.crops[G]["area_ha"]) * float(cf.crops[G]["yield_t_ha"]) / 12.0
	var share: float = float(fm.inputs[G].get("domestic_share", 1.0))
	var planned0: float = float(fm.stocks["capacity_bn_jpy_month"])
	var bid0: float = planned0 * float(fm.inputs[G]["coef"]) * share
	var fd0: float = float(e.final_demand.get(G, 0.0))
	var need: float = maxf(0.0, bid0 + fd0 - crop_month)
	var published: float = float(th.goods_spec[G].get("start_in_transit_t", 0.0)) if th.goods_spec.has(G) else 0.0
	print("SOY start: published in transit %.0f t; own need %.0f t (food bid %.0f at capacity %.1f bn, domestic share %.3f; final demand %.0f; crop / 12 %.0f)" % [published, need, bid0, planned0, share, fd0, crop_month])
	if a["variant"] == "own_need" and th.goods_spec.has(G):
		th.goods_spec[G]["start_in_transit_t"] = need
		for o: Dictionary in th.orders:
			if String(o["commodity"]) == G and int(o["arrive_month"]) == 0:
				o["qty"] = need
				o["cost_bn"] = need * (th.landed_cost_bn_per_t(G) if th.goods_spec.has(G) else NAN)
		print("SOY variant own_need: the start's in transit set to %.0f t" % need)
	var key: String = e.world.gkey(G, "JPN")
	var fills: Array = []
	for m: int in int(a["months"]):
		var g0: Dictionary = e.world.good(G, "JPN")
		var p: float = float(g0["price"])
		e.step()
		var g: Dictionary = e.world.good(G, "JPN")
		var ex: float = float((e.world.env.get("expected_price", {}) as Dictionary).get(key, p))
		var mg: float = float(th.last_margin.get(G, NAN))
		var ordered: float = 0.0
		var arrived: float = 0.0
		var neg: bool = false
		for l: Array in th.log:
			if int(l[0]) != m:
				continue
			if String(l[2]) == "order_" + G:
				ordered += float(l[3])
			elif String(l[2]) == "arrive_" + G:
				arrived += float(l[3])
			elif String(l[2]) == "margin_" + G:
				neg = true
		var fill: float = float(fm.input_fill.get(G, NAN))
		var others: PackedStringArray = PackedStringArray()
		for c2: String in fm.input_fill:
			if float(fm.input_fill[c2]) < 1.0:
				others.append("%s %.4f" % [c2, float(fm.input_fill[c2])])
		fills.append(fill)
		print("SOY M%02d price %.7f exp %.7f landed %.7f margin %+.7f%s | ordered %.0f arrived %.0f carried %.0f in transit %.0f | demanded %.0f traded %.0f unmet %.0f | soy fill %.4f food out/planned %.4f | inputs below 1: %s" % [m, p, ex, (th.landed_cost_bn_per_t(G) if th.goods_spec.has(G) else NAN), mg, " MARGIN_NEG" if neg else "", ordered, arrived, float(th.stocks.get("inv_" + G, 0.0)), float(g.get("in_transit", 0.0)), float(g["demanded_last"]) if g.has("demanded_last") else float(g["demanded"]), float(g["traded_last"]) if g.has("traded_last") else float(g["traded"]), float(g["unmet_last"]), fill, fm.output / maxf(1e-9, fm.planned), ", ".join(others) if others.size() > 0 else "none"])
	var lo: float = 1.0
	var tot: float = 0.0
	for f: float in fills:
		lo = minf(lo, f)
		tot += f
	print("SOY fill min %.4f mean %.4f over %d months" % [lo, tot / maxf(1.0, float(fills.size())), fills.size()])
	quit()
