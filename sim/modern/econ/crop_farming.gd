extends "res://sim/modern/econ/actor.gd"
## Crop farming (BLUEPRINT_v2 2, E1): one actor per jurisdiction. Inputs: land by crop (ha), yield (t/ha, the published normal), the
## calendar (sowing and harvest months), weather (a yield factor from the environment: 1.0 normal; a drought is a declared factor on
## declared crops and months), labour and inputs (fertiliser, fuel: a stated requirement per ha), money. Outputs: harvest by crop added
## to inventory in the harvest month, cost, input demand (bids for fertiliser and fuel), saleable quantity (inventory above the seed and
## on-farm use reserve) offered each month at a stated pace. Rules (T unless said): yield x area x weather factor; input demand per ha
## (S: MAFF 農業経営統計 per-ha costs); offers = inventory above the reserve, sold evenly over the months to the next harvest; the
## reserve of the last harvest is used on the farm when the next one is in.
## Data: data/modern/econ/crop_farming_<jurisdiction>.json (MAFF 作物統計; label per field).
var crops: Dictionary = {}       # crop -> {area_ha, yield_t_ha, harvest_month (1-12), sow_month, reserve_share, source}
var inputs_per_ha: Dictionary = {}   # input commodity -> {value (unit per ha), label, source}
var last_harvest: Dictionary = {}    # crop -> t harvested at the last harvest (for the chronicle)


func load_spec(path: String) -> String:
	var d: Variant = CANON.load_json(path)
	if not (d is Dictionary):
		return "crop_farming: no spec at " + path
	setup(d)
	crops = (d["crops"] as Dictionary).duplicate(true)
	inputs_per_ha = (d.get("inputs_per_ha", {}) as Dictionary).duplicate(true)
	return ""


func total_area() -> float:
	var a: float = 0.0
	for c: String in crops:
		a += float(crops[c]["area_ha"])
	return a


func plan(world: RefCounted, month: int) -> void:
	var cal_month: int = month % 12 + 1   # month 0 = January of the base year
	for c: String in crops:
		var spec: Dictionary = crops[c]
		# the harvest lands in the inventory in the harvest month
		if int(spec["harvest_month"]) == cal_month:
			var weather: float = float((world.env.get("yield_factor", {}) as Dictionary).get(c, 1.0))
			var harvest: float = float(spec["area_ha"]) * float(spec["yield_t_ha"]) * weather
			# Why the old reserve is used when the new crop is in, not sold: final demand was derived as (harvest - reserve) / 12, so a
			# reserve released to the market each year was a surplus the market never had (ISS_AUDIT.md §8.6)
			var used: float = float(last_harvest.get(c, 0.0)) * float(spec.get("reserve_share", 0.0))
			if used > 0.0:
				world.use_own(c, jurisdiction, used, id, "seed and own use: the reserve of the last harvest (%.0f t)" % used)
			world.produce(c, jurisdiction, harvest, id, "harvest: area %.0f ha x yield %.2f t/ha x weather %.2f" % [float(spec["area_ha"]), float(spec["yield_t_ha"]), weather])
			last_harvest[c] = harvest
			note(month, "harvest_" + c, harvest, "area x yield x weather (S yield, T factor)", "harvest month")
		# the saleable quantity above the reserve is offered evenly over the months until the next harvest
		var g: Dictionary = world.good(c, jurisdiction)
		var reserve: float = float(last_harvest.get(c, 0.0)) * float(spec.get("reserve_share", 0.0))
		var months_left: int = (int(spec["harvest_month"]) - cal_month + 12) % 12
		months_left = 12 if months_left == 0 else months_left
		# the farmers' own stock is the pooled inventory less what other sellers hold (the trading houses' imports)
		var others: float = 0.0
		for ob_id: String in (g.get("held_by", {}) as Dictionary):
			if ob_id != id:
				others += float(g["held_by"][ob_id])
		var saleable: float = maxf(0.0, float(g["inventory"]) - others - reserve)
		var offer: float = saleable / float(months_left)
		if offer > 0.0:
			world.offer(c, jurisdiction, offer, id)
			note(month, "offer_" + c, offer, "saleable / months to the next harvest (T)", "inventory %.0f, reserve %.0f" % [float(g["inventory"]), reserve])
		# inputs for the sowing month are bought the month before
		if (int(spec["sow_month"]) - 1 + 12) % 12 + 1 == cal_month or (int(spec["sow_month"]) == 1 and cal_month == 12):
			for inp: String in inputs_per_ha:
				var need: float = float(spec["area_ha"]) * float(inputs_per_ha[inp]["value"])
				world.demand(inp, jurisdiction, need, id)
				note(month, "demand_" + inp + "_" + c, need, "area x requirement per ha (" + String(inputs_per_ha[inp]["label"]) + ")", "before sowing " + c)


func to_dict() -> Dictionary:
	var d: Dictionary = super.to_dict()
	d["last_harvest"] = last_harvest.duplicate()
	return d


func from_dict(d: Dictionary) -> void:
	super.from_dict(d)
	last_harvest = (d.get("last_harvest", {}) as Dictionary).duplicate()


func settle(world: RefCounted, month: int) -> void:
	# sales income at the held price; input purchases at their prices (money ledger closes against the buyers' and sellers' cash)
	for c: String in crops:
		var g: Dictionary = world.good(c, jurisdiction)
		var sold: float = float((g.get("traded_by", {}) as Dictionary).get(id, 0.0))
		if sold > 0.0:
			world.pay("market:" + c, id, sold * float(g["price"]), "sales of " + c)
			note(month, "sold_" + c, sold, "market clearing", "at the held price")
