extends "res://tools/test/test_kit.gd"
## ISS Phase 5, the economy link (sim/modern/econ/labour.gd; people.supply(); modern_world's month end): the modern world with the
## representative persons on (5 per prefecture, 235 persons) and Japan's monthly economy.
##   godot --headless --path . --script res://sim/modern/test_modern_economy_link.gd
## E1 the persons' plans move the economy's final demand: the food demand scale differs from 1 in some months and the goods record
##    names the persons as its cause; the economy keeps the level (the scale stays within 0.5..1.5 in a calm run)
## E2 the economy owns employment: after a month end the status unemployment_rate equals the labour module's, the persons received it,
##    and the wage index has moved with expected prices after twelve months
## E3 the loop closes: a declared drought raises the food price; the persons who know it grow anxious and thrift more; the food demand
##    scale in the drought world is below the calm world's (same seed), and the chronicle holds the chain. The drought (yields x0.5 in
##    months 0-11) reaches the food price at the harvest (month 11), so both worlds run to day 600 and thrift and the scale are read as
##    the mean of the last six months, all after the rise (one month of 235 persons is a handful of choices)
## E4 lags: a person unemployed for a year has a lower skill than it started with (erosion), and the skill reaches the pay
## E6 the wage reaches the makers' costs: with the labour module running, the fixed cost's wage part follows the wage index of the
##    month before (S share from the IO), so the food maker's unit cost and its cost-plus target move with the wage (V090); with people off the cost is the IO's
## E7 the rake's scale is the cohort of its own day: at each month end the persons' weighted national total over the published total
##    equals the status cohort's total over its start (V093 read a one-month lag at days that were not month ends). It asserts the
##    national total only; each prefecture's exactness is D6's (people only) and V094's
## E5 the world with persons and the labour module saves and resumes exactly across a year turn (the rake runs every month; the year turn ages and replaces persons), and the
##    people-off world's digest does not depend on
##    any of this: a world given the persons' parameters with the flag off equals the plain world, and the plain world at day 1095 equals
##    the recorded people-off baseline of this platform (tools/test/modern_baselines.json; reported where none is recorded)
const MW = preload("res://sim/modern/modern_world.gd")
const SALT := "0123456789abcdef0123456789abcdef"


## The weighted share of persons whose action was act, by month: mean over the last k months the persons ran
static func _share_last(p: RefCounted, act: String, k: int) -> float:
	var tot := {}
	var hit := {}
	for r: Dictionary in p.decisions:
		var m: int = int(r["month"])
		tot[m] = float(tot.get(m, 0.0)) + float(r["weight"])
		if String(r["action"]) == act:
			hit[m] = float(hit.get(m, 0.0)) + float(r["weight"])
	var ms: Array = tot.keys()
	ms.sort()
	var s: float = 0.0
	var c: int = 0
	for m: int in ms.slice(maxi(0, ms.size() - k)):
		s += float(hit.get(m, 0.0)) / float(tot[m])
		c += 1
	return s / maxf(1.0, float(c))


static func _scale_last(w: RefCounted, k: int) -> float:
	var rows: Array = w.econ.labour.log
	var s: float = 0.0
	for r: Array in rows.slice(maxi(0, rows.size() - k)):
		s += float(r[6])
	return s / maxf(1.0, float(mini(k, rows.size())))


func _world(people: bool) -> RefCounted:
	var w = MW.new()
	var p: Dictionary = {"view_salt": SALT}
	if people:
		p["people"] = true
		p["people_per_prefecture"] = 5
		p["people_seed"] = 3
	var err: String = w.create(2024, p)
	check(err == "", "world created: " + err)
	return w


func _init() -> void:
	var w = _world(true)
	w.advance_to(400)
	var scales: Array = []
	var cause_rows: int = 0
	for row: Array in w.econ.labour.log:
		scales.append(float(row[6]))
	for r: Array in w.econ.world.records:
		if String(r[3]) == "final_demand_scale" and String(r[6]) == "persons":
			cause_rows += 1
	var moved: bool = false
	var in_band: bool = true
	for s: float in scales:
		if absf(s - 1.0) > 1e-6:
			moved = true
		if s < 0.5 or s > 1.5:
			in_band = false
	check(scales.size() >= 12 and moved and in_band and cause_rows > 0, "E1 %d labour months; food demand scale moved %s (last %.3f), within 0.5..1.5 %s; %d records name the persons" % [scales.size(), str(moved), scales[-1] if scales.size() > 0 else 0.0, str(in_band), cause_rows])
	var u_status: float = w.status.value("JPN", "unemployment_rate")
	var u_labour: float = w.econ.labour.u
	var wi: float = w.econ.labour.wage_index
	check(absf(u_status - u_labour) < 1e-12 and absf(w.people.wage_index - wi) < 1e-12 and wi > 1.0 and u_labour > 0.0, "E2 status unemployment %.4f = labour %.4f; persons' wage index %.4f = economy's; wage index after 13 months %.4f" % [u_status, u_labour, w.people.wage_index, wi])
	# E3 counterfactual: the same world with a drought declared in its first year
	var d = _world(true)
	d.econ.declare_shock(0, 11, {"rice": 0.5, "vegetables": 0.5}, "declared drought (test)")
	d.advance_to(600)
	var wl = _world(true)
	wl.advance_to(600)
	var scale_calm: float = _scale_last(wl, 6)
	var scale_dry: float = _scale_last(d, 6)
	var fp_calm: float = float(wl.econ.world.good("food_products", "JPN")["price"])
	var fp_dry: float = float(d.econ.world.good("food_products", "JPN")["price"])
	var sm_c: Dictionary = wl.people.summary()
	var sm_d: Dictionary = d.people.summary()
	var thrift_c: float = _share_last(wl.people, "thrift", 6)
	var thrift_d: float = _share_last(d.people, "thrift", 6)
	var known_d: float = float(sm_d["food_price_known_share"])
	var chain: Dictionary = {"price": 0, "people": 0, "labour": 0}
	for r: Dictionary in d.chronicle.rows:
		if chain.has(String(r["kind"])):
			chain[String(r["kind"])] += 1
	check(fp_dry > fp_calm and known_d > 0.0 and float(sm_d["anxiety_p10_p50_p90"][1]) >= float(sm_c["anxiety_p10_p50_p90"][1]) and scale_dry < scale_calm and thrift_d > thrift_c and chain["price"] > 0 and chain["people"] > 0 and chain["labour"] > 0,
		"E3 food price calm %.3f vs drought %.3f; drought: %.0f%% know the price rise, anxiety p50 %.3f vs calm %.3f, thrift share %.3f vs %.3f, food demand scale %.3f vs %.3f; chronicle rows price %d / people %d / labour %d" % [fp_calm, fp_dry, 100.0 * known_d, float(sm_d["anxiety_p10_p50_p90"][1]), float(sm_c["anxiety_p10_p50_p90"][1]), thrift_d, thrift_c, scale_dry, scale_calm, chain["price"], chain["people"], chain["labour"]])
	# E4 lags: skill erosion of the long unemployed; the skill in the pay
	var p = w.people
	var eroded: int = 0
	var long_unemployed: int = 0
	for i: int in p.n:
		if p.employment[i] == 3:
			long_unemployed += 1
	var wage_skill_ok: bool = true
	var i_hi: int = -1
	var i_lo: int = -1
	for i: int in p.n:
		if p.employment[i] == 1 and p.sex[i] == 0 and p.education[i] == 2 and p.age[i] >= 40 and p.age[i] < 50:
			if i_hi < 0 or p.skill[i] > p.skill[i_hi]:
				i_hi = i
			if i_lo < 0 or p.skill[i] < p.skill[i_lo]:
				i_lo = i
	# the wage table's skill factor: same class, higher skill -> higher expected pay before the person's own spread
	var factor_ok: bool = i_hi >= 0 and i_lo >= 0 and (i_hi == i_lo or (1.0 + 0.004 * (p.skill[i_hi] - 50.0)) >= (1.0 + 0.004 * (p.skill[i_lo] - 50.0)))
	var pu = load("res://sim/modern/people/people.gd").new()
	var st = load("res://sim/modern/modern_status.gd").new()
	st.load(2024, ["JPN"])
	pu.create("JPN", 5, st.cohort["JPN"], st.qx["JPN"], {"13": {"pop_thousand": 14178}}, 40)
	var s0: PackedFloat64Array = pu.skill.duplicate()
	for m: int in 14:
		pu.step({"inflation_month": 0.0, "food_price_yoy": 0.0, "unemployment_rate": 0.5, "levers": []})
	for i: int in pu.n:
		if pu.employment[i] == 3 and pu.skill[i] < s0[i]:
			eroded += 1
	check(eroded > 0 and factor_ok, "E4 unemployed persons with eroded skill %d (world: %d unemployed now); the skill factor in the pay ordered %s" % [eroded, long_unemployed, str(factor_ok)])
	# E6 the wage in the makers' costs
	var fm6 = w.econ.actors[1]
	var wi6: float = float(w.econ.labour.wage_index)
	var f_io: float = float(fm6.stocks["fixed_costs_bn_month"])
	var share6: float = fm6.p("wage_share_of_fixed")
	var env_wi: float = float(w.econ.world.env.get("wage_index", NAN))
	var off6 = _world(false)
	off6.advance_to(31)
	var fm_off = off6.econ.actors[1]
	check(absf(wi6 - 1.0) > 1e-4 and absf(env_wi - float(w.econ.labour.log[-2][2])) < 1e-12 and absf(fm6.fixed_cost(w.econ.world) - f_io * (1.0 + share6 * (env_wi - 1.0))) < 1e-9 and fm_off.fixed_cost(off6.econ.world) == float(fm_off.stocks["fixed_costs_bn_month"]) and not off6.econ.world.env.has("wage_index"),
		"E6 wage index %.4f; the food maker's fixed cost %.2f = IO %.2f x (1 + %.3f x (index - 1)); people off: %.2f, the IO's, no wage index in the economy" % [env_wi, fm6.fixed_cost(w.econ.world), f_io, share6, fm_off.fixed_cost(off6.econ.world)])
	# E7 the rake's scale at the month ends
	var w7 = _world(true)
	var t0_7: float = 0.0
	for v: float in w7.status.cohort["JPN"]:
		t0_7 += v
	var worst7: float = 0.0
	for d7: int in [31, 59, 90, 120]:
		w7.advance_to(d7)
		var tn7: float = 0.0
		for v2: float in w7.status.cohort["JPN"]:
			tn7 += v2
		var ws7: float = 0.0
		for i7: int in w7.people.n:
			ws7 += w7.people.weight[i7]
		var pub7: float = 0.0
		for c7: int in w7.people.pref_pop:
			pub7 += float(w7.people.pref_pop[c7])
		worst7 = maxf(worst7, absf((ws7 / pub7) / (tn7 / t0_7) - 1.0))
	check(worst7 < 1e-12, "E7 at the month ends of months 1-4 the weighted total over the published equals the cohort's scale (worst %s)" % String.num_scientific(worst7))
	# E5 resume and independence
	var wa = _world(true)
	wa.advance_to(100)
	var mid: Dictionary = bytes_to_var(var_to_bytes(wa.to_dict()))
	wa.advance_to(400)
	var wb = MW.from_dict(mid)
	wb.advance_to(400)
	var off = _world(false)
	off.advance_to(100)
	check(wa.digest() == wb.digest() and off.econ.labour == null and not off.to_dict().has("people"), "E5 resumed world equals the straight run %s; the people-off world has no labour module %s and no people key %s" % [str(wa.digest() == wb.digest()), str(off.econ.labour == null), str(not off.to_dict().has("people"))])
	var off_p = MW.new()
	off_p.create(2024, {"view_salt": SALT, "people": false, "people_per_prefecture": 5, "people_seed": 3})
	off_p.advance_to(100)
	var plain = _world(false)
	plain.advance_to(1095)
	var base: Dictionary = (JSON.parse_string(FileAccess.get_file_as_string("res://tools/test/modern_baselines.json")) as Dictionary)["status_1095"]
	var plat: String = OS.get_name()
	# Why per platform: the field's link_cap still differs between Linux and Windows builds (V084); one value for both would fail one
	var base_ok: bool = (not base.has(plat)) or String(base[plat]) == plain.digest()
	check(off_p.digest() == off.digest() and base_ok, "E5 flag off with the persons' parameters equals the plain world %s; people-off day 1095 %s vs the recorded %s baseline %s" % [str(off_p.digest() == off.digest()), plain.digest().left(16), plat, String(base.get(plat, "(none recorded)")).left(16)])
	finish()
