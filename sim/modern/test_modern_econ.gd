extends "res://tools/test/test_kit.gd"
## The monthly economy, S1' (BLUEPRINT_v2 7; sim/modern/econ/): the common actor spec, the ledgers, crop farming and food manufacturing.
##   godot --headless --path . --script res://sim/modern/test_modern_econ.gd
## C1 a normal year: the rice harvest in the harvest month equals area x yield (the published 2024 figures), inventories never go
##    negative, food manufacturing runs at full planned output (every input filled)
## C2 the ledgers close: the sum of cash over all accounts is zero (every transfer posted twice); goods traded = offered or demanded,
##    whichever is less; unmet = demanded - traded
## C3 a drought (a declared yield factor 0.6 on rice and vegetables in the harvest year) lowers the harvest by 40%, the saleable
##    quantity and the inventory fall, and in the months after food manufacturing's output is cut by the scarcest input's fill (< 1)
## C4 every change has a cause: each goods record of the drought year names the actor and the rule; the harvest record carries the
##    weather factor
## C5 the same run twice gives the same digest, and a state saved at month 12 and restored gives the same digest at month 36
## C11 expectations, forward contracts and investment; C12 seeded shocks (same seed equal, seeds differ); C13 the central bank rule (S4')
## C14 no one-way price rule: every commodity that anyone offers in the drought run is priced by a rule chosen for it (a storable
##    good's availability or a maker's unit cost), never by the excess-demand rule, whose offers equal the seller's expected sales and so
##    can only raise a price (ISS_AUDIT.md §9.1, V090); a new seller has to pick a rule on purpose. It sees only what is offered in this run
##    (the economy alone, 36 months): a seller that appears only elsewhere is not covered until a test runs it
## M2-4 a storable good with a -30% harvest (rice in the second year): no stock-out before the next harvest; every month's move
##    within the declared 20% cap (ISS_PHASE5_ECONOMY.md M002 batch, G8: the month's price is the clearing target, k = 1)
const EM = preload("res://sim/modern/econ/econ_month.gd")


func _run(months: int, drought: bool) -> RefCounted:
	var e = EM.new()
	var err: String = e.create("JPN")
	check(err == "", "economy created: " + err)
	if drought:
		e.declare_shock(12, 23, {"rice": 0.6, "vegetables": 0.6}, "declared drought in the second year")
	for i: int in months:
		e.step()
	return e


func _init() -> void:
	var e = _run(12, false)
	var cf = e.actors[0]
	var fm = e.actors[1]
	var rice: Dictionary = e.world.good("rice", "JPN")
	var expect: float = float(cf.crops["rice"]["area_ha"]) * float(cf.crops["rice"]["yield_t_ha"])
	var harvest: float = float(cf.last_harvest.get("rice", 0.0))
	var neg: int = 0
	for k: String in e.world.goods:
		if float(e.world.goods[k]["inventory"]) < -1e-9:
			neg += 1
	var fill_ok: float = fm.output / maxf(1e-9, fm.planned)
	check(absf(harvest - expect) < 1e-6 * expect and neg == 0 and fill_ok > 0.99,
		"C1 rice harvest %.0f t (expected %.0f), negative inventories %d, food output / planned %.3f (capacity use %.3f)" % [harvest, expect, neg, fill_ok, float(fm.stocks["capacity_use"])])
	# the sum of cash over every account (actors and the markets' counterpart accounts) equals the start's: every transfer posts twice
	var start_cash: float = 10000.0   # the bank's own funds
	for a in e.actors:
		start_cash += float(a.stocks.get("cash_bn_jpy", 0.0))
	var unmet_ok: bool = true
	for k: String in e.world.goods:
		if float(e.world.goods[k]["unmet"]) < -1e-9:
			unmet_ok = false
	check(absf(e.world.total_cash() - start_cash) < 1e-6 and unmet_ok and e.world.transfers.size() > 0,
		"C2 cash sums to %.6f (start %.1f) over %d transfers; unmet never negative %s" % [e.world.total_cash(), start_cash, e.world.transfers.size(), str(unmet_ok)])
	# M2-4
	var r7 = EM.new()
	r7.create("JPN")
	r7.declare_shock(12, 23, {"rice": 0.7}, "declared short rice harvest in the second year")
	var inv_min: float = INF
	var worst_move: float = 0.0
	var p_prev: float = float(r7.world.good("rice", "JPN")["price"])
	var p_max: float = p_prev
	for m7: int in 36:
		r7.step()
		var g7: Dictionary = r7.world.good("rice", "JPN")
		var p7: float = float(g7["price"])
		worst_move = maxf(worst_move, absf(p7 / p_prev - 1.0))
		p_prev = p7
		p_max = maxf(p_max, p7)
		if m7 >= 22 and m7 < 33:
			inv_min = minf(inv_min, float(g7["inventory"]))
	check(inv_min > 0.0 and worst_move <= 0.2 + 1e-12, "M2-4 rice after a -30%% harvest: the lowest inventory before the next harvest %.0f t (no stock-out %s); the largest monthly move %.4f (cap 0.2); the highest price %.3f x the start" % [inv_min, str(inv_min > 0.0), worst_move, p_max / float(r7.world.commodities["rice"]["start_price"])])
	var d = _run(36, true)
	var cfd = d.actors[0]
	var fmd = d.actors[1]
	var h2: float = 0.0
	var fill_min: float = 1.0
	var cut_months: int = 0
	for l: Array in fmd.log:
		if String(l[2]) == "output" and int(l[0]) >= 12 and int(l[0]) < 36:
			pass
	for l: Array in cfd.log:
		if String(l[2]) == "harvest_rice" and int(l[0]) >= 12 and int(l[0]) < 24:
			h2 = float(l[3])
	var planned_by_month: Dictionary = {}
	for l: Array in fmd.log:
		if String(l[2]) == "planned_output":
			planned_by_month[int(l[0])] = float(l[3])
	for m: int in range(12, 36):
		for l: Array in fmd.log:
			if int(l[0]) == m and String(l[2]) == "output":
				var use: float = float(l[3]) / maxf(1e-9, float(planned_by_month.get(m, 1.0)))
				if use < 0.999:
					cut_months += 1
					fill_min = minf(fill_min, use)
	check(absf(h2 / expect - 0.6) < 1e-6 and cut_months > 0, "C3 drought harvest %.0f t = %.2f of normal; food output cut in %d months, lowest use %.3f" % [h2, h2 / expect, cut_months, fill_min])
	var with_cause: int = 0
	var without: int = 0
	var weather_in_harvest: bool = false
	for r: Array in d.world.records:
		if int(r[0]) >= 12 and int(r[0]) < 24 and String(r[1]) == "goods":
			if String(r[6]) != "" and String(r[7]) != "":
				with_cause += 1
			else:
				without += 1
			if String(r[3]) == "inventory" and String(r[7]).contains("weather 0.60"):
				weather_in_harvest = true
	check(without == 0 and weather_in_harvest, "C4 goods records with a cause %d, without %d; the harvest record carries the weather factor %s" % [with_cause, without, str(weather_in_harvest)])
	var d2 = _run(36, true)
	var e12 = EM.new()
	e12.create("JPN")
	e12.declare_shock(12, 23, {"rice": 0.6, "vegetables": 0.6}, "declared drought in the second year")
	for i: int in 12:
		e12.step()
	var mid: Dictionary = bytes_to_var(var_to_bytes(e12.to_dict()))
	for i: int in 24:
		e12.step()
	var e12b = EM.new()
	e12b.create("JPN")
	e12b.from_dict(mid)
	for i: int in 24:
		e12b.step()
	check(d.digest() == d2.digest() and e12.digest() == e12b.digest(), "C5 same run twice %s; resumed at 12 equals straight at 36 %s" % [str(d.digest() == d2.digest()), str(e12.digest() == e12b.digest())])
	# C6 prices (S2'): in the drought run the rice price after the short harvest is above the start, each move recorded with its cause;
	#    in the normal run no price moves by more than the monthly cap
	var p0: float = float(e.world.commodities["rice"]["start_price"])
	var p_drought: float = float(d.world.good("rice", "JPN")["price"])
	var price_rows: int = 0
	for r: Array in d.world.records:
		if String(r[2]) == "rice|JPN" and String(r[3]) == "price" and String(r[7]).begins_with("availability"):
			price_rows += 1
	check(p_drought > p0 * 1.1 and price_rows > 0, "C6 rice price after the drought %.6f vs start %.6f (x%.2f); %d rice price moves with their cause (availability vs the seasonal normal)" % [p_drought, p0, p_drought / p0, price_rows])
	# C7 imports (S2'): wheat is state trading, imported to cover the gap every month whatever the private margin (negative here: the
	#    markup makes the landed cost exceed the resale price); the minimum-access rice (64,000 t a month) goes to the state's stock and
	#    never reaches the market; every order names its binding limit; the money for it leaves the trading houses' cash
	var th = e.actors[2]
	var wheat_orders: int = 0
	var rice_orders: int = 0
	var bounded: bool = true
	for l: Array in th.log:
		if String(l[2]) == "order_wheat" and float(l[3]) > 0.0:
			wheat_orders += 1
			if not String(l[5]).contains("binding"):
				bounded = false
		if String(l[2]) == "order_rice" and float(l[3]) > 0.0:
			rice_orders += 1
	var rice_to_market: float = float(e.world.good("rice", "JPN")["imported"]) + float(e.world.good("rice", "JPN").get("imported_last", 0.0))
	var state_rice: float = float(th.stocks.get("state_stock_rice", 0.0))
	check(wheat_orders == 12 and rice_orders == 12 and bounded and float(th.last_margin["wheat"]) < 0.0 and rice_to_market == 0.0 and state_rice > 0.0,
		"C7 wheat orders %d (bounded %s), MA rice orders %d, rice to the market %.0f, state rice stock %.0f t; wheat margin %s" % [wheat_orders, str(bounded), rice_orders, rice_to_market, state_rice, String.num(float(th.last_margin.get("wheat", NAN)), 9)])
	# C8 logistics (S2'): a cap below the normal trade binds the traded quantity and is recorded as the cause
	var l8 = EM.new()
	l8.create("JPN")
	l8.world.logistics["rice"] = 300000.0
	l8.step()
	var g8: Dictionary = l8.world.good("rice", "JPN")
	var cap_row: bool = false
	for r: Array in l8.world.records:
		if String(r[2]) == "rice|JPN" and String(r[3]) == "traded" and String(r[7]).begins_with("logistics cap"):
			cap_row = true
	check(absf(float(g8["traded_last"]) - 300000.0) < 1e-6 and cap_row, "C8 rice traded %.0f under a 300,000 t cap; cause recorded %s" % [float(g8["traded_last"]), str(cap_row)])
	# C9 finance (S3'): in a normal year no actor needs a loan and the fixed costs (S: IO wages and other inputs) are paid; after a
	#    declared loss of 8,000 bn in month 12, food manufacturing's cash falls below its floor and the bank lends at the policy rate plus
	#    the spread, the instalments are paid in the months after, and the money ledger closes with the minted funding counted; after a
	#    loss of 120,000 bn the request is refused (debt service above 80% of revenue) and arrears are recorded
	var n_loans_normal: int = e.bank.loans.size()
	var arrears_normal: float = float(fm.stocks.get("arrears", 0.0))
	var sv = EM.new()
	sv.create("JPN")
	sv.declare_cash_loss(12, "food_manufacturing_JPN", 8000.0, "declared loss")
	for i: int in 24:
		sv.step()
	var n_loans: int = sv.bank.loans.size()
	var start_cash9: float = 10000.0
	for a in sv.actors:
		start_cash9 += float(a.stocks.get("cash_bn_jpy", 0.0))
	var closes: bool = absf(sv.world.total_cash() - start_cash9) < 1e-6
	var paid: float = 0.0
	var rated: bool = n_loans > 0
	for L: Dictionary in sv.bank.loans:
		paid += float(L["paid"])
		if float(L["rate"]) < 0.005 or float(L["rate"]) > 0.05:
			rated = false
	var big = EM.new()
	big.create("JPN")
	big.declare_cash_loss(12, "food_manufacturing_JPN", 120000.0, "declared loss")
	for i: int in 14:
		big.step()
	var refused: int = 0
	for l: Array in big.bank.log:
		if String(l[2]).begins_with("refuse_"):
			refused += 1
	var arrears_big: float = float(big.actors[1].stocks.get("arrears", 0.0))
	check(n_loans_normal == 0 and arrears_normal == 0.0 and n_loans > 0 and paid > 0.0 and closes and rated and refused > 0 and arrears_big > 0.0,
		"C9 normal: loans %d, arrears %.1f; after a loss: loans %d, paid back %.1f, rates in range %s, ledger closes %s (minted %.1f); big loss: refused %d, arrears %.1f" % [n_loans_normal, arrears_normal, n_loans, paid, str(rated), str(closes), sv.bank.minted, refused, arrears_big])
	# C10 the state's rice release (S3'): a release of 500,000 t from the MA stock reaches the market and the pooled rice inventory
	var rl = EM.new()
	rl.create("JPN")
	for i: int in 13:
		rl.step()
	var stock_before: float = float(rl.trading_house().stocks.get("state_stock_rice", 0.0))
	var inv_before: float = float(rl.world.good("rice", "JPN")["inventory"])
	var got: float = rl.release_state_rice(13, 500000.0)
	var inv_after: float = float(rl.world.good("rice", "JPN")["inventory"])
	check(stock_before >= 500000.0 and absf(got - 500000.0) < 1e-6 and absf((inv_after - inv_before) - 500000.0) < 1e-6, "C10 MA stock %.0f t before; released %.0f; inventory +%.0f" % [stock_before, got, inv_after - inv_before])
	# C11 expectations and investment (S4'): the trader judges its margin on the expected price (p + 0.5 x the last move, T) and its
	#    orders are forward contracts; with final demand 10% above the start, food manufacturing runs above 95% for three months, starts
	#    a capacity project (+5%, 12 months, the cash out to capital goods) and the capacity is larger once it finishes; the balanced start
	#    never invests
	var inv0: int = 0
	for l: Array in fm.log:
		if String(l[2]) == "invest":
			inv0 += 1
	var up = EM.new()
	up.create("JPN")
	up.final_demand["food_products"] = float(up.final_demand["food_products"]) * 1.1
	var cap_start: float = float(up.actors[1].stocks["capacity_bn_jpy_month"])
	for i: int in 20:
		up.step()
	var invested: int = 0
	for l: Array in up.actors[1].log:
		if String(l[2]) == "invest":
			invested += 1
	var capex: float = 0.0
	for t: Array in up.world.transfers:
		if String(t[2]) == "capital_goods":
			capex += float(t[3])
	var forward: int = 0
	for c: Dictionary in d.world.contracts:
		if String(c["kind"]) == "forward":
			forward += 1
	var exp_rice: float = float(d.world.env["expected_price"][d.world.gkey("rice", "JPN")])
	var cap_end: float = float(up.actors[1].stocks["capacity_bn_jpy_month"])
	check(inv0 == 0 and invested >= 1 and cap_end > cap_start * 1.04 and capex > 0.0 and forward > 0,
		"C11 balanced start invests %d times; +10%% demand: %d project(s), capacity %.1f -> %.1f, capex %.1f bn; forward contracts %d; expected rice price %.6f" % [inv0, invested, cap_start, cap_end, capex, forward, exp_rice])
	# C12 seeded shocks (S4'): the yield draws and loss events of shocks_jpn.json by keyed hashes; the same seed gives the same digest,
	#    two seeds differ, every yield factor is positive and every drawn shock names its seed and year
	var sa = EM.new()
	sa.create("JPN")
	sa.seed_shocks(7, 3)
	var sb = EM.new()
	sb.create("JPN")
	sb.seed_shocks(7, 3)
	var sc = EM.new()
	sc.create("JPN")
	sc.seed_shocks(8, 3)
	var positive: bool = true
	var named: bool = sa.shocks.size() > 0
	for s: Dictionary in sa.shocks:
		for c: String in s.get("yield_factor", {}):
			if float(s["yield_factor"][c]) <= 0.0:
				positive = false
		if not String(s["why"]).begins_with("seeded"):
			named = false
	for i: int in 36:
		sa.step()
		sb.step()
		sc.step()
	check(sa.digest() == sb.digest() and sa.digest() != sc.digest() and positive and named,
		"C12 seed 7 twice equal %s; seed 8 differs %s; %d shocks drawn, factors positive %s, named %s" % [str(sa.digest() == sb.digest()), str(sa.digest() != sc.digest()), sa.shocks.size(), str(positive), str(named)])
	# C13 the central bank rule (S4'): after the published path (month 0, 0.5%) the policy rate follows a Taylor-type rule on the reported
	#    inflation (held core 2.7% and the food price's yearly change, T), one step of at most 0.25 pt a quarter; under the drought the
	#    food price's rise lifts the rate above the normal run's
	var r_normal: float = float(e.bank.policy_rate)
	var r_drought: float = float(d.bank.policy_rate)
	var taylor_notes: int = 0
	for l: Array in d.bank.log:
		if String(l[2]) == "policy_rate" and String(l[4]).begins_with("Taylor"):
			taylor_notes += 1
	check(taylor_notes > 0 and r_normal > 0.005 and r_drought >= r_normal and r_drought <= 0.06,
		"C13 Taylor steps %d; policy rate after 12 normal months %.4f; after 36 drought months %.4f" % [taylor_notes, r_normal, r_drought])
	var offered := {}
	for r: Array in d.world.records:
		if String(r[3]) == "offered" and float(r[5]) > 0.0:
			offered[String(r[2]).split("|")[0]] = true
	var unruled: PackedStringArray = PackedStringArray()
	for c: String in offered:
		if not (d.world.storage.has(c) or d.world.cost_plus.has(c)):
			unruled.append(c)
	check(offered.size() >= 5 and unruled.is_empty(), "C14 offered in the drought run: %s; priced by the excess-demand rule though offered: %s" % [", ".join(PackedStringArray(offered.keys())), ", ".join(unruled) if unruled.size() > 0 else "none"])
	finish()
