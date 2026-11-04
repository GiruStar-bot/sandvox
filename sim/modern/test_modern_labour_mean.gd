extends "res://tools/test/test_kit.gd"
## M2-3 over replicate seeds (ISS_CHECKS.md M2-3 AMENDED, §R rule 4; ISS_PHASE5_ECONOMY.md G7, G7a): the persons' unemployment share
## after 24 months against the economy's u, at u = 2.5% and 4.0%, the search share the persons' own, read as the mean gap over the fresh
## seeds 12-21 of the same society (2 prefectures x 1,500 persons), each seed reported
##   godot --headless --path . --script res://sim/modern/test_modern_labour_mean.gd
## M2-3 the mean gap within 0.5 pt at each u
const PEOPLE = preload("res://sim/modern/people/people.gd")
const MS = preload("res://sim/modern/modern_status.gd")
const ENV := {"inflation_month": 0.02 / 12.0, "food_price_yoy": 0.0, "unemployment_rate": 0.025, "levers": []}
const SEEDS := [12, 13, 14, 15, 16, 17, 18, 19, 20, 21]
const BAND := 0.005


func _init() -> void:
	var st = MS.new()
	st.load(2024, ["JPN"])
	var ok: bool = true
	var txt: String = ""
	for ur: float in [0.025, 0.04]:
		var gaps := PackedFloat64Array()
		var each: String = ""
		for sd: int in SEEDS:
			var q = PEOPLE.new()
			q.create("JPN", sd, st.cohort["JPN"], st.qx["JPN"], {"13": {"pop_thousand": 14178}, "47": {"pop_thousand": 1467}}, 1500)
			var env: Dictionary = ENV.duplicate()
			env["unemployment_rate"] = ur
			for m: int in 24:
				q.step(env)
			var wl: float = 0.0
			var wu: float = 0.0
			for i: int in q.n:
				if q.employment[i] == q.EMP_REGULAR or q.employment[i] == q.EMP_NONREGULAR or q.employment[i] == q.EMP_UNEMPLOYED:
					wl += q.weight[i]
					if q.employment[i] == q.EMP_UNEMPLOYED:
						wu += q.weight[i]
			var share: float = wu / maxf(1e-9, wl)
			gaps.append(share - ur)
			each += " %d %.4f" % [sd, share]
		var mean: float = 0.0
		for g: float in gaps:
			mean += g
		mean /= float(gaps.size())
		var var_s: float = 0.0
		for g2: float in gaps:
			var_s += (g2 - mean) * (g2 - mean)
		var se: float = sqrt(var_s / float(gaps.size() - 1) / float(gaps.size()))
		ok = ok and absf(mean) <= BAND
		txt += " u %.3f: mean gap %+.4f (SE %.4f), seeds%s;" % [ur, mean, se, each]
	check(ok, "M2-3 (AMENDED, §R rule 4) the persons' unemployment share after 24 months over seeds 12-21:%s the mean within %.1f pt" % [txt, 100.0 * BAND])
	finish()
