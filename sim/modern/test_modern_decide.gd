extends "res://tools/test/test_kit.gd"
## ISS Phase 2, decisions (sim/modern/people/actions.gd): the same small society as test_modern_people (2 prefectures x 30, seed 7,
## 24 months, a lay-off wave in months 6-8, food +15% from month 12).
##   godot --headless --path . --script res://sim/modern/test_modern_decide.gd
## D1 the same situation, different actions: in every situation class (prefecture x employment status x age band) with at least ten
##    person-months, at least two different actions are taken, and every decision row names its top drive (and the emotion that tilted
##    it where one did); the unemployed's actions are reported (most search: 労働力調査 counts a person as unemployed by the search)
## D2 feasibility is separate from the score: candidates refused by a guard are recorded with the guard's words (assets below the
##    moving cost, no active dream ...), and a refused action is never the one taken that month
## D3 outcomes feed back and are learned: searchers find jobs more often than non-searchers over the run; a person who trained has a
##    higher skill than at the start; q_act moves from 0 for the actions taken
## D4 drives and dreams steer: persons with an active dream take pursue_dream, persons without never do; thrift's top drive is
##    economic security in most of its rows, and anxiety tilts decisions; thrift is reported per decision-month for the anxious and the
##    calm at the start (a rate, since the two groups have different numbers of decision-months: V086), not asserted in 60 persons
## D5 seed: same seed equal, another seed differs, a resume at month 12 equals the straight run (decisions included)
## D6 moves and deaths keep the population the cohort's: a mover lands in another prefecture (drawn by population), and after every
##    month's raking every prefecture's weighted population equals its published total (V086: the map drifted, Tokyo x2.5 in 24 months) and the
##    weighted shares of 0-14, 15-64 and 65+ are within 2 points of the cohort's (the sample grew young, audit run)
const PEOPLE = preload("res://sim/modern/people/people.gd")
const ACT = preload("res://sim/modern/people/actions.gd")
const MS = preload("res://sim/modern/modern_status.gd")


func _make(seed: int) -> RefCounted:
	var st = MS.new()
	st.load(2024, ["JPN"])
	var prefs: Dictionary = {"13": {"pop_thousand": 14178}, "47": {"pop_thousand": 1467}}
	var p = PEOPLE.new()
	var err: String = p.create("JPN", seed, st.cohort["JPN"], st.qx["JPN"], prefs, 30)
	check(err == "", "people created: " + err)
	return p


func _env(m: int) -> Dictionary:
	return {"inflation_month": 0.027 / 12.0, "food_price_yoy": 0.15 if m >= 12 else 0.0, "unemployment_rate": 0.12 if (m >= 6 and m < 9) else 0.025, "levers": []}


func _init() -> void:
	var p = _make(7)
	var skill0: PackedFloat64Array = p.skill.duplicate()
	var anx0: PackedFloat64Array = p.emotion_column("anxiety")
	var dream0: PackedInt32Array = p.dream_kind.duplicate()
	var searched: Dictionary = {}
	var found_search: int = 0
	var found_nosearch: int = 0
	var unemp_actions: Dictionary = {}
	var by_class: Dictionary = {}   # "pref|employment|age band" -> {action: person-months}
	var thrift_anx: int = 0
	var thrift_calm: int = 0
	var months_anx: int = 0
	var months_calm: int = 0
	var pursue_with: int = 0
	var pursue_without: int = 0
	var trained: Dictionary = {}
	var med_anx: float = p.quantiles(anx0, range(p.n))[1]
	var moves: int = 0
	var moved_away: int = 0
	var pop_ok: bool = true
	var age_gap: float = 0.0
	for m: int in 24:
		var emp_before: PackedInt32Array = p.employment.duplicate()
		var pref_before: PackedInt32Array = p.pref.duplicate()
		p.step(_env(m))
		for i4: int in p.n:
			if p.last_action[i4] == 9:
				moves += 1
				moved_away += 1 if p.pref[i4] != pref_before[i4] else 0
		var sums: Dictionary = {}
		for i5: int in p.n:
			sums[p.pref[i5]] = float(sums.get(p.pref[i5], 0.0)) + p.weight[i5]
		for code: int in p.pref_pop:
			pop_ok = pop_ok and absf(float(sums.get(code, 0.0)) / float(p.pref_pop[code]) - 1.0) < 1e-9
		var sb := [0.0, 0.0, 0.0]
		var cb := [0.0, 0.0, 0.0]
		var tw: float = 0.0
		var ct: float = 0.0
		for i6: int in p.n:
			sb[0 if p.age[i6] < 15 else (1 if p.age[i6] < 65 else 2)] += p.weight[i6]
			tw += p.weight[i6]
		for ag: int in 101:
			for sx: int in 2:
				cb[0 if ag < 15 else (1 if ag < 65 else 2)] += p.cohort[ag * 2 + sx]
				ct += p.cohort[ag * 2 + sx]
		for b: int in 3:
			age_gap = maxf(age_gap, absf(sb[b] / tw - cb[b] / ct))
		for i: int in p.n:
			var a: int = p.last_action[i]
			if emp_before[i] == 3:
				unemp_actions[ACT.ACTIONS[a]] = int(unemp_actions.get(ACT.ACTIONS[a], 0)) + 1
			var ck: String = "%d|%d|%s" % [p.pref[i], emp_before[i], PEOPLE.age_band(p.age[i])]
			var cd: Dictionary = by_class.get(ck, {})
			cd[a] = int(cd.get(a, 0)) + 1
			by_class[ck] = cd
			if emp_before[i] == 3 and (p.employment[i] == 1 or p.employment[i] == 2):
				if a == 1:
					found_search += 1
				else:
					found_nosearch += 1
			if a == 1:
				searched[i] = true
			if a == 3:
				trained[i] = true
			if anx0[i] > med_anx:
				months_anx += 1
			else:
				months_calm += 1
			if a == 4:
				if anx0[i] > med_anx:
					thrift_anx += 1
				else:
					thrift_calm += 1
			if a == 10:
				if dream0[i] >= 0:
					pursue_with += 1
				else:
					pursue_without += 1
	var named: bool = p.decisions.size() > 0
	var tilted: int = 0
	for row: Dictionary in p.decisions:
		if (row["top_drives"] as Dictionary).is_empty():
			named = false
		if not (row["modulated"] as Dictionary).is_empty():
			tilted += 1
	var classes: int = 0
	var uniform: Array = []
	var fewest: int = 99
	for ck: String in by_class:
		var tot: int = 0
		for a3: int in by_class[ck]:
			tot += int(by_class[ck][a3])
		if tot < 10:
			continue
		classes += 1
		fewest = mini(fewest, (by_class[ck] as Dictionary).size())
		if (by_class[ck] as Dictionary).size() < 2:
			uniform.append(ck)
	# Why not "the unemployed spread over three actions" (the Phase 2 form): at the temperature 0.03 the unemployed mostly search, as the
	# survey's definition says they do; the ISS question is whether persons in the same situation still differ, asked of every class
	check(classes > 0 and uniform.is_empty() and named, "D1 %d situation classes with 10+ person-months, all with 2+ different actions %s (fewest %d); unemployed persons' actions %s; decision rows %d, all with a top drive %s, %d rows tilted by an emotion" % [classes, str(uniform.is_empty()), fewest, str(unemp_actions), p.decisions.size(), str(named), tilted])
	var guards: Dictionary = {}
	for r: Dictionary in p.refusals:
		guards[String(r["why"])] = int(guards.get(String(r["why"]), 0)) + int(r["count"])
	var took_refused: bool = false
	for r: Dictionary in p.refusals:
		for row: Dictionary in p.decisions:
			if int(row["month"]) == int(r["month"]) and String(row["action"]) == String(r["action"]) and String(r["why"]) == "no active dream":
				took_refused = true
	check(guards.has("assets below the moving cost") and guards.size() >= 2 and not took_refused, "D2 guards recorded: %s" % str(guards))
	var skill_up: int = 0
	for i: int in trained:
		if p.skill[i] > skill0[i]:
			skill_up += 1
	var q_moved: int = 0
	for i: int in p.n:
		for a: int in ACT.NA:
			if absf(p.q_act[i * ACT.NA + a]) > 1e-9:
				q_moved += 1
	check(found_search >= found_nosearch and skill_up == trained.size() and trained.size() > 0 and q_moved > 0,
		"D3 jobs found by searchers %d vs others %d; trained %d, skill up for %d; q_act entries moved %d" % [found_search, found_nosearch, trained.size(), skill_up, q_moved])
	var thrift_security: int = 0
	var thrift_rows: int = 0
	var anxiety_tilts: int = 0
	for row: Dictionary in p.decisions:
		if String(row["action"]) == "thrift":
			thrift_rows += int(row["count"])
			thrift_security += int((row["top_drives"] as Dictionary).get("economic_security", 0))
		anxiety_tilts += int((row["modulated"] as Dictionary).get("anxiety", 0))
	# Why not "the anxious thrift more" as an assertion: the rule tilts the security weight by anxiety, and V086 found the anxious thrift
	# more per decision in 6 of 8 seeds of 200 persons; in 60 persons the difference is within the noise, so it is reported as a rate
	check(pursue_with > 0 and pursue_without == 0 and thrift_rows > 0 and thrift_security * 2 > thrift_rows and anxiety_tilts > 0,
		"D4 pursue_dream with a dream %d, without %d; thrift rows %d with economic security on top in %d; decisions tilted by anxiety %d (thrift per decision-month: anxious at the start %d / %d = %.3f, calm %d / %d = %.3f)" % [pursue_with, pursue_without, thrift_rows, thrift_security, anxiety_tilts, thrift_anx, months_anx, float(thrift_anx) / maxf(1.0, months_anx), thrift_calm, months_calm, float(thrift_calm) / maxf(1.0, months_calm)])
	check(moves > 0 and moved_away == moves and pop_ok and age_gap <= 0.02, "D6 %d moves, %d to another prefecture; weighted populations equal the published totals after every month %s; largest age-band gap to the cohort %.4f" % [moves, moved_away, str(pop_ok), age_gap])
	var a2 = _make(7)
	var b2 = _make(7)
	var c2 = _make(8)
	var mid: Dictionary = {}
	for m: int in 24:
		a2.step(_env(m))
		b2.step(_env(m))
		c2.step(_env(m))
		if m == 11:
			mid = bytes_to_var(var_to_bytes(a2.to_dict()))
	var r2 = PEOPLE.new()
	r2.from_dict(mid)
	for m: int in range(12, 24):
		r2.step(_env(m))
	check(a2.digest() == b2.digest() and a2.digest() != c2.digest() and r2.digest() == a2.digest() and a2.decisions.size() == r2.decisions.size(),
		"D5 seed 7 twice equal %s; seed 8 differs %s; resume equals %s (%d decision rows)" % [str(a2.digest() == b2.digest()), str(a2.digest() != c2.digest()), str(r2.digest() == a2.digest()), a2.decisions.size()])
	finish()
