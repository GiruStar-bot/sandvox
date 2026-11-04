extends "res://tools/test/test_kit.gd"
## ISS life course (sim/modern/people/life_course.gd; ISS_HOUSEHOLD_REDESIGN.md §10.2): the mechanics expectations of ISS_CHECKS.md,
## declared before this test. All 47 prefectures x 60 persons built by households, seed 1, 60 months in a fixed environment.
##   godot --headless --path . --script res://sim/modern/test_modern_life_course.gd
## H2s-a no slot is reused: every pid belongs to one person, persons at the end = the start + births - deaths, every newborn's mother
##       is a woman of its household at the birth
## H2s-b households stay consistent at every year's end: one household each, partners symmetric of opposite sex in one household, one
##       weight per household, each type the classification of its members' roles
## H2s-c deaths by band (0-64, 65-74, 75-84, 85+) x sex within 3 Poisson SE of the summed yearly hazard
## H2s-d the same seed twice gives the same digest; to_dict at month 12, from_dict and 12 more months give the uninterrupted digest
##       (a 2 x 150 society, 24 months)
## H2s-e every logged event is of a declared kind and its persons were alive at the event
## H2s-f the amendments' guards (§10.6): no one who does not intend to marry has partnered; no woman's births exceed max(her intended
##       number, her births at the start); every move had a reason (households on)
const PEOPLE = preload("res://sim/modern/people/people.gd")
const HH = preload("res://sim/modern/people/households.gd")
const LC = preload("res://sim/modern/people/life_course.gd")
const MS = preload("res://sim/modern/modern_status.gd")
const CANON = preload("res://sim/modern/canon.gd")
const ENV := {"inflation_month": 0.02 / 12.0, "food_price_yoy": 0.0, "unemployment_rate": 0.025, "levers": []}


func _consistent(p) -> String:
	var seen := {}
	for h: int in p.hh_n:
		var ms: PackedInt32Array = p.hh_members[h]
		for i: int in ms:
			if seen.has(i) or p.hh_id[i] != h:
				return "person %d in two households or a stale id" % i
			seen[i] = true
			if p.weight[i] != p.hh_weight[h]:
				return "household %d: member weight %f against %f" % [h, p.weight[i], p.hh_weight[h]]
		var t0: int = p.hh_type[h]
		LC._classify(p, h)
		if p.hh_type[h] != t0:
			return "household %d: type %d, its roles say %d" % [h, t0, p.hh_type[h]]
	if seen.size() != p.n:
		return "%d persons in households of %d" % [seen.size(), p.n]
	for i2: int in p.n:
		var j: int = p.partner[i2]
		if j >= 0 and (p.partner[j] != i2 or p.sex[j] == p.sex[i2] or p.hh_id[j] != p.hh_id[i2]):
			return "partners %d and %d" % [i2, j]
	return ""


func _run(seed: int, prefs: Dictionary, n_per: int, months: int, st) -> Object:
	var p = PEOPLE.new()
	p.households = true
	p.create("JPN", seed, st.cohort["JPN"], st.qx["JPN"], prefs, n_per, 2024)
	for m: int in months:
		p.step(ENV)
	return p


func _init() -> void:
	var st = MS.new()
	st.load(2024, ["JPN"])
	var prefs: Dictionary = CANON.load_json("res://data/modern/polity/jpn_prefectures.json")["prefectures"]
	var p = PEOPLE.new()
	p.households = true
	p.create("JPN", 1, st.cohort["JPN"], st.qx["JPN"], prefs, 60, 2024)
	var n0: int = p.n
	var born0 := {}
	for i0: int in p.n:
		born0[p.pid[i0]] = p.births_n[i0]
	var life := {}   # pid -> [first month seen at a month's end, last]
	for i: int in p.n:
		life[p.pid[i]] = [-1, -1]
	var dup: String = ""
	var bad_b: String = ""
	var mothers_ok: bool = true
	var bad_part: Array = []
	for m: int in 60:
		var log0: int = p.life_log.size()
		var intent0 := {}
		for i7: int in p.n:
			intent0[p.pid[i7]] = p.intends_marry[i7]
		p.step(ENV)
		for q7: int in range(log0, p.life_log.size()):
			var e7: Array = p.life_log[q7]
			if String(e7[2]) == "partnered" and int(intent0.get(e7[1], -1)) != 1:
				bad_part.append("partnered without intention: %s (intention %d before the month)" % [str(e7), int(intent0.get(e7[1], -1))])
		var now := {}
		for i2: int in p.n:
			if now.has(p.pid[i2]):
				dup = "pid %d twice at month %d" % [p.pid[i2], m]
			now[p.pid[i2]] = i2
			if life.has(p.pid[i2]):
				if int(life[p.pid[i2]][1]) != m - 1:
					dup = "pid %d seen again at month %d after %d" % [p.pid[i2], m, int(life[p.pid[i2]][1])]
				life[p.pid[i2]][1] = m
			else:
				life[p.pid[i2]] = [m, m]
		for e: Array in p.life_log.slice(log0):
			if String(e[2]) == "birth":
				var kid: int = int(now.get(e[1], -1))
				var mo: int = int(now.get(e[3], -1))
				if kid < 0 or mo < 0 or p.sex[mo] != 1 or p.hh_id[mo] != p.hh_id[kid]:
					mothers_ok = false
		if m % 12 == 11 and bad_b == "":
			bad_b = _consistent(p)
	var births: int = p.lc_births.size()
	var deaths: int = 0
	for d: int in p.lc_deaths:
		deaths += d
	check(dup == "" and p.n == n0 + births - deaths and mothers_ok, "H2s-a no slot reused: %s; persons %d = %d + %d births - %d deaths; mothers in the newborns' households %s" % [dup if dup != "" else "every pid one person", p.n, n0, births, deaths, str(mothers_ok)])
	check(bad_b == "", "H2s-b households consistent at every year's end: " + (bad_b if bad_b != "" else "yes") + " (%d households)" % p.hh_n)
	var ok_c: bool = true
	var txt_c: String = ""
	for c: int in 8:
		var ex: float = p.lc_expected[c]
		ok_c = ok_c and absf(float(p.lc_deaths[c]) - ex) <= 3.0 * sqrt(maxf(1.0, ex))
		txt_c += " %s%s %d (%.1f)" % [["0-64", "65-74", "75-84", "85+"][c / 2], "MF"[c % 2], p.lc_deaths[c], ex]
	check(ok_c, "H2s-c deaths against the summed hazard:" + txt_c)
	var ok_e: bool = true
	var txt_e: String = ""
	var kinds := {}
	for e2: Array in p.life_log:
		var k: String = String(e2[2])
		kinds[k] = int(kinds.get(k, 0)) + 1
		var mo2: int = int(e2[0])
		var who: Array = life.get(e2[1], [99, -99])
		var alive: bool = (int(who[0]) == mo2) if k == "birth" else (int(who[0]) <= mo2 - 1 and int(who[1]) >= mo2 - 1)
		if int(e2[3]) >= 0 and k != "death" and k != "widowed":
			var oth: Array = life.get(e2[3], [99, -99])
			alive = alive and int(oth[0]) <= mo2 - 1 and int(oth[1]) >= mo2 - 1 if k != "partnered" and k != "moved_in" else alive and int(oth[0]) <= mo2 - 1
		if not LC.KINDS.has(k) or not alive:
			ok_e = false
			txt_e = " first bad: %s" % str(e2)
	check(ok_e, "H2s-e the life log: %s%s" % [str(kinds), txt_e])
	# Why not the intention at the run's end (the row before H2s-f AMENDED): a union's end redraws it, so a person who partnered
	# intending to and later divorced read as partnered without intention
	var bad_f: Array = bad_part.duplicate()
	for e5: Array in p.life_log:
		var k5: String = String(e5[2])
		if k5 == "moved" and String((e5[4] as Dictionary).get("reason", "")) == "":
			bad_f.append("a move without a reason: %s" % str(e5))
	var over: int = 0
	for i6: int in p.n:
		if p.sex[i6] == p.FEMALE and p.births_n[i6] > maxi(p.intended_kids[i6], int(born0.get(p.pid[i6], 0))):
			over += 1
	check(bad_f.is_empty() and over == 0, "H2s-f AMENDED (the intention held before each month) the amendments' guards: %s; women with births beyond their intention %d; partnered %d, moves %d" % [str(bad_f.slice(0, 2)) if not bad_f.is_empty() else "none", over, int(kinds.get("partnered", 0)), int(kinds.get("moved", 0))])
	var two := {"13": {"pop_thousand": 14178}, "47": {"pop_thousand": 1467}}
	var a = _run(7, two, 150, 24, st)
	var b = _run(7, two, 150, 12, st)
	var c2 = PEOPLE.new()
	c2.from_dict(bytes_to_var(var_to_bytes(b.to_dict())))
	for m2: int in 12:
		c2.step(ENV)
	var a2 = _run(7, two, 150, 24, st)
	check(a.digest() == a2.digest() and a.digest() == c2.digest(), "H2s-d determinism %s, round trip %s (%d persons, %d events)" % [str(a.digest() == a2.digest()), str(a.digest() == c2.digest()), a.n, a.life_log.size()])
	finish()
