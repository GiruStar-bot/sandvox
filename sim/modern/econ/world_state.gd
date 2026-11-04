extends RefCounted
## The economy's world state (BLUEPRINT_v2 1; E-Phase 0): the one store every actor reads and the ledgers through which goods, money and
## contracts move. Three ledgers, never mixed (principle C):
##   goods: per commodity, per jurisdiction: produced, inventory, offered, demanded, traded, unmet, price (this month)
##   money: per actor: cash; every transfer is posted twice (payer -, payee +) so the sum of cash is conserved
##   contracts: rows {id, buyer, seller, commodity, quantity, price, due month, kind (spot | forward)}
## Markets clear in clear_markets(): trades are min(offered, demanded) pro rata over the sellers. A storable good (storage[c] set) is
## priced on its availability against the seasonal normal, through the inverse of its demand curve (ISS_AUDIT.md §8); a manufactured
## good with a producer on its unit cost and the start's markup (§9); any other good on the month's excess demand (S2').
## Units: quantities in the commodity's unit (tonnes for crops, index units for manufactures), money in bn JPY, prices in bn JPY per unit.
## The chronicle reads the per-month records (records_of) to say what moved and why.
const COMMODITIES_PATH := "res://data/modern/econ/commodities.json"
const CANON = preload("res://sim/modern/canon.gd")
const DM = preload("res://sim/api/det_math.gd")


var commodities: Dictionary = {}   # key -> {name, unit, kind (primary | manufactured | service | energy), start_price, source}
var goods: Dictionary = {}         # "commodity|jurisdiction" -> {produced, inventory, offered, demanded, traded, unmet, price, imported}
var cash: Dictionary = {}          # actor id -> bn JPY
var contracts: Array = []
var month: int = 0                 # months since the start (0 = the first month)
var logistics: Dictionary = {}     # commodity -> t a month the ports and carriers can move (E3, S2'; empty: no cap)
var storage: Dictionary = {}       # storable commodity -> {harvest_t, reserve_t, harvest_month, import_t_month, lead_months, use_t_month}
var cost_plus: Dictionary = {}     # manufactured commodity with a producer -> {markup}; its producer publishes unit_cost on the good
var env: Dictionary = {}           # the external environment this month: weather by region, foreign prices, shocks in force, laws
var transfers: Array = []          # [month, payer, payee, amount, why]
var records: Array = []            # [month, "goods"|"money"|"contract", key, field, before, after, by, why]
var error: String = ""


func create() -> String:
	var c: Variant = CANON.load_json(COMMODITIES_PATH)
	if not (c is Dictionary):
		error = "world_state: no commodities at " + COMMODITIES_PATH
		return error
	commodities = (c as Dictionary)["commodities"]
	return ""


static func gkey(commodity: String, jurisdiction: String) -> String:
	return commodity + "|" + jurisdiction


func good(commodity: String, jurisdiction: String) -> Dictionary:
	var k: String = gkey(commodity, jurisdiction)
	if not goods.has(k):
		goods[k] = {"produced": 0.0, "inventory": 0.0, "offered": 0.0, "demanded": 0.0, "traded": 0.0, "unmet": 0.0, "imported": 0.0,
			"produced_last": 0.0, "traded_last": 0.0, "unmet_last": 0.0, "offered_by": {}, "traded_by": {}, "held_by": {},
			"price": float((commodities.get(commodity, {}) as Dictionary).get("start_price", 0.0))}
	return goods[k]


func _rec(ledger: String, key: String, field: String, before: float, after: float, by: String, why: String) -> void:
	records.append([month, ledger, key, field, before, after, by, why])


## An actor adds what it produced to the inventory (goods ledger); the pooled inventory also records who holds what (held_by), so a
## seller offers only its own
func produce(commodity: String, jurisdiction: String, qty: float, by: String, why: String) -> void:
	var g: Dictionary = good(commodity, jurisdiction)
	_rec("goods", gkey(commodity, jurisdiction), "inventory", g["inventory"], g["inventory"] + qty, by, why)
	g["produced"] += qty
	g["inventory"] += qty
	var hb: Dictionary = g.get("held_by", {})
	hb[by] = float(hb.get(by, 0.0)) + qty
	g["held_by"] = hb


## An actor uses a quantity of its own stock off the market (the farmers' seed and own use), recorded like a production
func use_own(commodity: String, jurisdiction: String, qty: float, by: String, why: String) -> void:
	var g: Dictionary = good(commodity, jurisdiction)
	var hb: Dictionary = g.get("held_by", {})
	# Why the inventory less the others' holdings and not held_by[by]: the start stock was never produced, so it is in no holder's row
	var others: float = 0.0
	for h: String in hb:
		if h != by:
			others += float(hb[h])
	var q: float = minf(qty, float(g["inventory"]) - others)
	if q <= 0.0:
		return
	_rec("goods", gkey(commodity, jurisdiction), "inventory", g["inventory"], g["inventory"] - q, by, why)
	g["inventory"] -= q
	hb[by] = float(hb.get(by, 0.0)) - q
	g["held_by"] = hb


## An actor offers a quantity from its inventory for sale this month (not moved until the market clears); offers are kept by seller so
## the sales and the money go back to the right one
func offer(commodity: String, jurisdiction: String, qty: float, by: String) -> void:
	var g: Dictionary = good(commodity, jurisdiction)
	var room: float = float(g["inventory"]) - float(g["offered"])
	var q: float = minf(qty, room) if room > 0.0 else 0.0
	if q <= 0.0:
		return
	g["offered"] += q
	var ob: Dictionary = g.get("offered_by", {})
	ob[by] = float(ob.get(by, 0.0)) + q
	g["offered_by"] = ob
	_rec("goods", gkey(commodity, jurisdiction), "offered", 0.0, g["offered"], by, "offer")


## An actor bids for a quantity this month
func demand(commodity: String, jurisdiction: String, qty: float, by: String) -> void:
	var g: Dictionary = good(commodity, jurisdiction)
	g["demanded"] += qty
	_rec("goods", gkey(commodity, jurisdiction), "demanded", 0.0, g["demanded"], by, "demand")


## Step 3: every commodity market clears. Quantity: traded = min(offered, demanded, the logistics cap), pro rata over sellers (S2').
## Price (S2', E4-1): next month's price moves by the adjustment speed k toward its target, capped per month (both declared per
## commodity in commodities.json, T). A storable good's target is the price that clears its availability (storable_target); a
## manufactured good with a producer, its unit cost times the start's markup (cost_plus); any other good's move is k x (demanded -
## offered) / offered. Every move is recorded with its cause (principle D).
func clear_markets() -> void:
	for k: String in goods:
		var g: Dictionary = goods[k]
		var c: String = k.split("|")[0]
		var cap_l: float = float(logistics.get(c, INF))
		var traded: float = minf(minf(float(g["offered"]), float(g["demanded"])), cap_l)
		var why: String = "min(offered, demanded)"
		if traded == cap_l and cap_l < minf(float(g["offered"]), float(g["demanded"])):
			why = "logistics cap %.0f binds" % cap_l
		g["traded"] = traded
		g["unmet"] = maxf(0.0, float(g["demanded"]) - traded)
		_rec("goods", k, "traded", 0.0, traded, "market", why)
		var tb: Dictionary = {}
		var ob: Dictionary = g.get("offered_by", {})
		for seller: String in ob:
			tb[seller] = traded * float(ob[seller]) / float(g["offered"]) if float(g["offered"]) > 0.0 else 0.0
		g["traded_by"] = tb
		g["inventory"] -= traded
		var hb: Dictionary = g.get("held_by", {})
		for seller: String in tb:
			if hb.has(seller):
				hb[seller] = float(hb[seller]) - float(tb[seller])
		g["held_by"] = hb
		# price formation, with the month's drivers named (S4', E6-4: the cause of a move is recorded, not only the move)
		var spec: Dictionary = commodities.get(c, {})
		var speed: float = float(spec.get("adjust_speed", 0.0))
		g["offered_month"] = float(g["offered"])
		g["demanded_month"] = float(g["demanded"])
		if speed > 0.0 and storage.has(c):
			var t: Dictionary = storable_target(c, float(g["inventory"]) + traded + float(g.get("in_transit", 0.0)))
			var cap_s: float = float(spec.get("move_cap", 0.2))
			var p0s: float = float(g["price"])
			var move_s: float = clampf(speed * (float(t["target"]) / p0s - 1.0), -cap_s, cap_s)
			g["price"] = p0s * (1.0 + move_s)
			if absf(move_s) > 1e-12:
				_rec("goods", k, "price", p0s, g["price"], "market", "availability %.0f vs seasonal normal %.0f (%d months to harvest): x %.4f over %d months; clearing price p0 x x^(1/%.2f) = %s; speed %.2f (cap %.2f)" % [float(t["available"]), float(t["normal"]), int(t["months_left"]), float(t["x"]), int(t["horizon"]), float(t["elasticity"]), String.num(float(t["target"]), 9), speed, cap_s])
		elif speed > 0.0 and cost_plus.has(c) and g.has("unit_cost"):
			# Why not the excess demand: the maker offers what it expects to sell and plans to the demand it saw, so offers never exceed
			# demand and that rule could only raise the price (ISS_AUDIT.md §9.1)
			var m_up: float = float(cost_plus[c]["markup"])
			var target_c: float = (1.0 + m_up) * float(g["unit_cost"])
			var cap_c: float = float(spec.get("move_cap", 0.2))
			var p0c: float = float(g["price"])
			var move_c: float = clampf(speed * (target_c / p0c - 1.0), -cap_c, cap_c)
			g["price"] = p0c * (1.0 + move_c)
			if absf(move_c) > 1e-12:
				_rec("goods", k, "price", p0c, g["price"], "market", "unit cost %s x (1 + markup %.4f) = %s; speed %.2f (cap %.2f)" % [String.num(float(g["unit_cost"]), 9), m_up, String.num(target_c, 9), speed, cap_c])
		elif speed > 0.0 and float(g["offered"]) > 0.0:
			var excess: float = (float(g["demanded"]) - float(g["offered"])) / float(g["offered"])
			var move: float = clampf(speed * excess, -float(spec.get("move_cap", 0.2)), float(spec.get("move_cap", 0.2)))
			var p0: float = float(g["price"])
			g["price"] = p0 * (1.0 + move)
			if absf(move) > 1e-12:
				var ol: float = float(g.get("offered_last", 0.0))
				var dl: float = float(g.get("demanded_last", 0.0))
				var drivers: PackedStringArray = PackedStringArray()
				if ol > 0.0:
					drivers.append("supply %+.1f%%" % (100.0 * (float(g["offered"]) / ol - 1.0)))
				if dl > 0.0:
					drivers.append("demand %+.1f%%" % (100.0 * (float(g["demanded"]) / dl - 1.0)))
				if float(g["imported"]) > 0.0:
					drivers.append("imports %.0f" % float(g["imported"]))
				if why.begins_with("logistics"):
					drivers.append("logistics cap")
				_rec("goods", k, "price", p0, g["price"], "market", "excess demand %.3f x speed %.2f (cap %.2f); drivers vs last month: %s" % [excess, speed, float(spec.get("move_cap", 0.2)), ", ".join(drivers) if drivers.size() > 0 else "first month"])
		g["offered"] = 0.0
		g["demanded"] = 0.0
		g["offered_by"] = {}


## A storable good's target price (ISS_AUDIT.md §8.2): the availability A against its seasonal normal A_n, read as a share x of the
## normal use over the months it must last, then the published demand curve inverted at x. Why a shortfall over this season only and a
## surplus over the next one too: a stock can be carried forward, not borrowed from a harvest not yet in (competitive storage).
func storable_target(c: String, available: float) -> Dictionary:
	var st: Dictionary = storage[c]
	var hm: int = int(st["harvest_month"])
	var ml: int = (hm - (month % 12 + 1) + 12) % 12
	ml = 12 if ml == 0 else ml
	var r: float = float(st["reserve_t"])
	var normal: float = r + (float(st["harvest_t"]) - r) * ml / 12.0 + float(st["import_t_month"]) * (1.0 + float(st["lead_months"]))
	var delta: float = available - normal
	var h: int = ml if delta < 0.0 else ml + 12
	var x: float = maxf(0.05, 1.0 + delta / (float(st["use_t_month"]) * h))
	var spec: Dictionary = commodities[c]
	var e: float = float(spec["demand_elasticity"])
	var target: float = float(spec["start_price"]) * DM.pow(x, 1.0 / e)
	return {"available": available, "normal": normal, "months_left": ml, "horizon": h, "x": x, "elasticity": e, "target": target}


## The share of its bid a buyer got this month (pro rata when the market was short)
func fill_share(commodity: String, jurisdiction: String) -> float:
	var g: Dictionary = good(commodity, jurisdiction)
	var d: float = g["traded"] + g["unmet"]
	return g["traded"] / d if d > 0.0 else 1.0


## Money ledger: a transfer is posted twice; the sum of cash never changes except by mint (the central bank, S3')
func pay(payer: String, payee: String, amount: float, why: String) -> void:
	if amount <= 0.0:
		return
	cash[payer] = float(cash.get(payer, 0.0)) - amount
	cash[payee] = float(cash.get(payee, 0.0)) + amount
	transfers.append([month, payer, payee, amount, why])
	_rec("money", payer + ">" + payee, "cash", 0.0, amount, payer, why)


func total_cash() -> float:
	var t: float = 0.0
	for k: String in cash:
		t += float(cash[k])
	return t


func add_contract(buyer: String, seller: String, commodity: String, qty: float, price: float, due_month: int, kind: String) -> int:
	var cid: int = contracts.size()
	contracts.append({"id": cid, "buyer": buyer, "seller": seller, "commodity": commodity, "quantity": qty, "price": price, "due": due_month, "kind": kind, "settled": false})
	_rec("contract", str(cid), "made", 0.0, qty, buyer, kind)
	return cid


## A recorded note from outside the market (Phase 5: the persons' demand scale), through the same record format
func record_note(ledger: String, key: String, field: String, before: float, after: float, by: String, why: String) -> void:
	_rec(ledger, key, field, before, after, by, why)


func next_month() -> void:
	month += 1
	for k: String in goods:
		var g: Dictionary = goods[k]
		# the price path for expectations and the yearly change (S4')
		var hist: Array = g.get("price_hist", [])
		hist.append(g["price"])
		if hist.size() > 13:
			hist.pop_front()
		g["price_hist"] = hist
		g["price_prev"] = hist[hist.size() - 2] if hist.size() >= 2 else g["price"]
		g["price_12m"] = hist[0] if hist.size() >= 13 else hist[0]
		g["offered_last"] = g.get("offered_month", 0.0)
		g["demanded_last"] = g.get("demanded_month", 0.0)
		g["produced_last"] = g["produced"]
		g["traded_last"] = g["traded"]
		g["unmet_last"] = g["unmet"]
		g["imported_last"] = g["imported"]
		g["produced"] = 0.0
		g["traded"] = 0.0
		g["unmet"] = 0.0
		g["imported"] = 0.0


func records_of(m: int) -> Array:
	var out: Array = []
	for r: Array in records:
		if int(r[0]) == m:
			out.append(r)
	return out


func to_dict() -> Dictionary:
	return {"goods": goods.duplicate(true), "cash": cash.duplicate(), "contracts": contracts.duplicate(true), "month": month, "env": env.duplicate(true),
		"transfers": transfers.duplicate(true), "records": records.duplicate(true)}


func from_dict(d: Dictionary) -> void:
	goods = (d["goods"] as Dictionary).duplicate(true)
	cash = (d["cash"] as Dictionary).duplicate()
	contracts = (d["contracts"] as Array).duplicate(true)
	month = int(d["month"])
	env = (d.get("env", {}) as Dictionary).duplicate(true)
	transfers = (d.get("transfers", []) as Array).duplicate(true)
	records = (d.get("records", []) as Array).duplicate(true)
