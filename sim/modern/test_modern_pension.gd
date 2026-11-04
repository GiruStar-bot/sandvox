extends "res://tools/test/test_kit.gd"
## The M002 batch's checks on iss-hh (ISS_PHASE5_ECONOMY.md "M002 batch"): the pensions' indexation (G1; R68: 国民年金法 Art 27-27-5 as
## of 2024-01), one unemployment rate (G7), the whole saving booked (SB10), the believed cost rise (G2).
##   godot --headless --path . --script res://sim/modern/test_modern_pension.gd
## M2-1 the rule replays FY2021-FY2024 from R68's inputs (CPI, wage, slide by year): revisions -0.1, -0.4, +2.2 new / +1.9 existing,
##      +2.7; the carry -0.1, -0.3, 0, 0
## M2-2 at the start's first April (2024-04) every pension rises by 2.7% (the published FY2024 revision)
## M2-6 the believed cost rise is symmetric about zero (a believed food fall lowers it as a rise raises it)
## M2-7 every register reader's belief of a fact lies within that fact's own error of the truth (G3)
## M2-5 a month's saving is booked in full: Δ assets - Δ debt = the saving, for a surplus, a shortfall within the assets and one beyond
## M2-3 is read over replicate seeds in test_modern_labour_mean.gd (§R rule 4: one seed's noise is wider than its band)
const PEOPLE = preload("res://sim/modern/people/people.gd")
const MS = preload("res://sim/modern/modern_status.gd")
const ENV := {"inflation_month": 0.02 / 12.0, "food_price_yoy": 0.0, "unemployment_rate": 0.025, "levers": []}
const R68 := [
	["FY2021", 0.000, -0.001, -0.001, -0.001, -0.001, -0.001],
	["FY2022", -0.002, -0.004, -0.002, -0.004, -0.004, -0.003],
	["FY2023", 0.025, 0.028, -0.003, 0.022, 0.019, 0.0],
	["FY2024", 0.032, 0.031, -0.004, 0.027, 0.027, 0.0],
]


func _init() -> void:
	var carry: float = 0.0
	var bad: Array = []
	for row: Array in R68:
		var r: Array = PEOPLE.pension_revision(float(row[1]), float(row[2]), float(row[3]), carry)
		carry = float(r[2])
		if absf(float(r[0]) - float(row[4])) > 5e-4 or absf(float(r[1]) - float(row[5])) > 5e-4 or absf(carry - float(row[6])) > 5e-4:
			bad.append("%s new %.4f old %.4f carry %.4f" % [row[0], r[0], r[1], carry])
	check(bad.is_empty(), "M2-1 the rule replays R68's FY2021-FY2024 revisions and carry at 0.1 pt: %s" % ("all four" if bad.is_empty() else str(bad)))
	var st = MS.new()
	st.load(2024, ["JPN"])
	var p = PEOPLE.new()
	p.create("JPN", 7, st.cohort["JPN"], st.qx["JPN"], {"13": {"pop_thousand": 14178}, "47": {"pop_thousand": 1467}}, 60)
	var before := {}
	for m: int in 4:
		if m == 3:
			for i: int in p.n:
				if p.employment[i] == p.EMP_RETIRED:
					before[p.pid[i]] = p.income[i]
		p.step(ENV)
	var worst: float = 0.0
	var seen: int = 0
	for i2: int in p.n:
		if p.employment[i2] == p.EMP_RETIRED and before.has(p.pid[i2]):
			worst = maxf(worst, absf(p.income[i2] / float(before[p.pid[i2]]) - 1.027))
			seen += 1
	check(seen > 0 and worst < 1e-12, "M2-2 at 2024-04 the pensions of %d retired persons rose by 2.7%% (worst gap %s); the indices new %.4f, existing %.4f" % [seen, str(worst), float(p.pension["new"]), float(p.pension["old"])])
	# M2-5
	var bad5: int = 0
	for case: Array in [[100.0, 0.0, 25.0], [100.0, 0.0, -40.0], [10.0, 5.0, -25.0]]:
		p.assets[0] = float(case[0])
		p.debt[0] = float(case[1])
		var a0: float = p.assets[0] - p.debt[0]
		p.book_saving(0, float(case[2]))
		if absf((p.assets[0] - p.debt[0]) - a0 - float(case[2])) > 1e-9 or p.assets[0] < 0.0:
			bad5 += 1
	check(bad5 == 0, "M2-5 the saving booked in full (assets less debt moves by the saving; assets never negative): %d of 3 cases off" % bad5)
	# M2-6
	var k6: int = 0 * p.REL.NF
	p.belief_known[k6] = 1
	p.belief[k6] = 0.05
	var up: float = p.believed_cost_rise(0)
	p.belief[k6] = -0.05
	var down: float = p.believed_cost_rise(0)
	check(up > 0.0 and absf(up + down) < 1e-15, "M2-6 the believed cost rise at a believed food change of +5%% %.5f and -5%% %.5f (symmetric)" % [up, down])
	# M2-7
	var r7 = PEOPLE.new()
	r7.create("JPN", 7, st.cohort["JPN"], st.qx["JPN"], {"13": {"pop_thousand": 14178}, "47": {"pop_thousand": 1467}}, 200)
	var env7: Dictionary = ENV.duplicate()
	env7["food_price_yoy"] = 0.15
	var readers7: int = 0
	var off7: int = 0
	for m7: int in 3:
		r7.step(env7)
		var truth7 := [0.15, 0.025]
		for i7: int in r7.n:
			for f7: int in r7.REL.NF:
				var k7: int = i7 * r7.REL.NF + f7
				if r7.belief_known[k7] == 1 and r7.belief_source[k7] == 0 and r7.belief_month[k7] == r7.month - 1:
					readers7 += 1
					if absf(r7.belief[k7] - float(truth7[f7])) > float(r7.REL.PUBLISH_ERR_BY_FACT[f7]) + 1e-12:
						off7 += 1
	check(readers7 > 0 and off7 == 0, "M2-7 register readings within each fact's error (food +-0.0005, unemployment +-0.001): %d readings, %d off" % [readers7, off7])
	finish()
