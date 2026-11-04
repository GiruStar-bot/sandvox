extends "res://tools/test/test_kit.gd"
## The actor interface, the placeholder rules (A1-A4) and R55's rule set (A5-A7) (MODERN_PLAN 3; sim/modern/modern_actors.gd), on the 2024
## data.
##   godot --headless --path . --script res://sim/modern/test_modern_actors.gd
## A1 with nothing driving change (compute growth 0) the rules start nothing in a year: every entity is balanced and its servers replaced
## A2 with compute growth, the rules start data centres where the wanted IT outgrows the halls, generation for the new load in the entity's
##    mix (from the next month, when the halls started are known), and fabs in proportion to each fab entity's capacity
## A3 a closed licence is answered once in kind: the USA closes chips to mainland China; China closes to the USA the good it holds most of
##    (gallium, 99%); the USA does not answer the answer
## A4 a seat's actions are checked as a whole: one bad action (a negative size) refuses them all, the refusal is logged, and the entity's
##    rule actions stand in that month
## A5 R55 energy: at the first month end each entity plans a year's builds in its current mix, started in twelfths; no entity's wind or
##    solar plan exceeds R55's Cherp cap (0.8% / 0.6% of its supply a year)
## A6 R55 counter-control: the USA closes chips to mainland China at the end of January; China sees it at the end of February and its
##    answer (gallium to the USA) is in force at the end of March (29 days or more after it was seen), not before
## A7 R55 actors read no other state's unpublished truth: a 50 GW project the USA starts unseen changes no other entity's actions next month
## A9 coalition following (R55, R56 alliances as of the start): the USA closes chips to mainland China at the end of January 2022; Japan
##    (US-Japan treaty, Wassenaar, an ATP share) follows about 309 days later: open at day 365, closed at the end of January 2023; India
##    (no US alliance) does not; China answers Japan's round in kind about a month after that
## A10 a general export restriction (R56 base rate; here made certain for mainland China): China closes each good it holds a share of to
##    every destination at a month end, nobody answers it (it is aimed at no state), and it is lifted at the first month end a year later
## A11 R57's fab spending rule from the entity's own figures: in January 2022 the USA plans a year of fab capacity = 0.21 x 555.6 bn x its
##    output share / (1 - 0.125) / 200k USD per wspm / 25.6 M wspm, started in twelfths; the world's plans add about 3% of capacity a year
## A8 R56's costs: at WEO's own WACC the LCOE is WEO's published one (US: PV 50, onshore wind 35, CCGT 60, coal 95 USD/MWh), and a higher WACC
##    raises PV's more than coal's (capital-heavy); the pipeline's mix keeps each entity's total share (sums to 1) and moves only coal, gas, wind and solar
const MW = preload("res://sim/modern/modern_world.gd")


class FixedSeat:
	extends RefCounted
	var acts: Array = []
	func actions(_w: RefCounted, _e: int) -> Array:
		return acts


func _world(p: Dictionary = {}) -> RefCounted:
	var w = MW.new()
	w.create(2024, p)
	return w


func _init() -> void:
	var w = _world({"rules": "placeholder", "compute_growth": 0.0})
	w.advance_to(365)
	# the status layer's lever acts (Japan's rule brain answers its debt and fertility pressures, S1) are not field actions
	var field_acts: int = 0
	for r: Array in w.log:
		if not (r[3] is Dictionary and String((r[3] as Dictionary).get("act", "")) == "lever"):
			field_acts += 1
	check(w.field.projects.size() == 0 and w.field.done_projects == 0 and field_acts == 0, "A1 a year with no growth: %d projects, %d actions"
		% [w.field.projects.size(), w.log.size()])

	var g = _world({"rules": "placeholder", "compute_growth": 0.15})
	g.advance_to(59)
	var kinds := {}
	var jpn: int = g.data.index_of("JPN")
	var jp_gen: float = 0.0
	var jp_dc: float = 0.0
	var fab_ok: bool = true
	var tw: int = g.data.index_of("TWN")
	var kr: int = g.data.index_of("KOR")
	var fab := {}
	for p: Array in g.field.projects:
		kinds[String(p[1])] = true
		if int(p[0]) == jpn and String(p[1]) == "dc":
			jp_dc += float(p[2])
		elif int(p[0]) == jpn and g.data.SOURCES.has(String(p[1])):
			jp_gen += float(p[2])
		if String(p[1]) == "fab":
			fab[int(p[0])] = float(p[2])
	fab_ok = fab.has(tw) and fab.has(kr) and absf(fab[tw] / fab[kr] - g.field.fab_cap[tw] / g.field.fab_cap[kr]) < 1e-9
	check(kinds.has("dc") and kinds.has("fab") and jp_dc > 0.0 and jp_gen > 0.0 and fab_ok,
		"A2 two months at 15%%/yr: kinds started %s; Japan DC %.0f MW, generation %.0f MW; fabs Taiwan/Korea in their capacity ratio" % [str(kinds.keys()),
		jp_dc, jp_gen])

	var l = _world({"rules": "placeholder", "compute_growth": 0.0})
	var usa: int = l.data.index_of("USA")
	var chn: int = l.data.index_of("CHN")
	var s := FixedSeat.new()
	s.acts = [{"act": "licence", "good": "chips", "to": chn, "open": false}]
	l.seats[usa] = s
	l.advance_to(31)
	l.seats.erase(usa)
	l.advance_to(59)
	var rows: Array = l.field.chain.closed_rows()
	var want: Array = [[chn, "gallium", usa], [usa, "chips", chn]]
	check(rows.size() == 2 and rows.has(want[0]) and rows.has(want[1]), "A3 closed after two months: %s" % str(rows))

	var r = _world({"rules": "placeholder", "compute_growth": 0.15})
	var bad := FixedSeat.new()
	bad.acts = [{"act": "build", "kind": "solar", "size": 100.0}, {"act": "build", "kind": "dc", "size": -1.0}]
	r.seats[jpn] = bad
	r.advance_to(31)
	var refused: int = 0
	var seat_n: int = 0
	var rule_n: int = 0
	for row: Array in r.log:
		if String(row[1]) == "JPN":
			refused += 1 if String(row[2]) == "refused" else 0
			seat_n += 1 if String(row[2]) == "seat" else 0
			rule_n += 1 if String(row[2]) == "rule" else 0
	check(refused == 1 and seat_n == 0 and rule_n > 0, "A4 Japan's seat refused %d time(s); %d seat actions applied, %d rule actions instead" % [refused, seat_n,
		rule_n])

	var q = _world()
	q.advance_to(31)
	var S: int = q.data.SOURCES.size()
	var capped: bool = true
	var planned: int = 0
	for e: int in q.field.E:
		var p: Dictionary = q.actors.plan.get(e, {})
		planned += 1 if not p.is_empty() else 0
		var sup: float = 0.0
		for si: int in S:
			sup += q.field.supply_of(e, si)
		for src: String in ["wind", "solar"]:
			capped = capped and float(p.get(src, 0.0)) * 12.0 <= q.actors.CHERP_CAP[src] * sup * (1.0 + 1e-9)
	var jp_plan: Dictionary = q.actors.plan.get(jpn, {})
	var jp_started: float = 0.0
	for p2: Array in q.field.projects:
		if int(p2[0]) == jpn and String(p2[1]) == "solar":
			jp_started += float(p2[2])
	check(planned > 0 and capped and absf(jp_started - float(jp_plan.get("solar", 0.0))) < 1e-9,
		"A5 %d entities planned; wind and solar within the caps: %s; Japan's solar a month %.1f MW" % [planned, str(capped), jp_started])

	var c = _world()
	var u2: int = c.data.index_of("USA")
	var c2: int = c.data.index_of("CHN")
	var seat2 := FixedSeat.new()
	seat2.acts = [{"act": "licence", "good": "chips", "to": c2, "open": false}]
	c.seats[u2] = seat2
	c.advance_to(31)
	c.seats.erase(u2)
	c.advance_to(59)
	var open59: bool = c.field.chain.is_open(c2, "gallium", u2)
	c.advance_to(90)
	check(open59 and not c.field.chain.is_open(c2, "gallium", u2), "A6 China's gallium to the USA open at day 59: %s; closed at day 90: %s" % [str(open59),
		str(not c.field.chain.is_open(c2, "gallium", u2))])

	var a1 = _world()
	var a2 = _world()
	a1.advance_to(31)
	a2.advance_to(31)
	a2.field.add_project(a2.data.index_of("USA"), "nuclear", 50000.0)
	a1.advance_to(59)
	a2.advance_to(59)
	var same: bool = true
	var n: int = 0
	var rows1: Array = a1.log.filter(func(r: Array) -> bool: return int(r[0]) == 59 and String(r[1]) != "USA")
	var rows2: Array = a2.log.filter(func(r: Array) -> bool: return int(r[0]) == 59 and String(r[1]) != "USA")
	same = rows1.size() == rows2.size() and JSON.stringify(rows1, "", true, true) == JSON.stringify(rows2, "", true, true)
	n = rows1.size()
	check(same and n > 0, "A7 day 59: %d actions of the other entities, the same with and without the USA's unseen 50 GW: %s" % [n, str(same)])

	var cf = _world()
	var u9: int = cf.data.index_of("USA")
	var c9: int = cf.data.index_of("CHN")
	var j9: int = cf.data.index_of("JPN")
	var i9: int = cf.data.index_of("IND")
	var seat9 := FixedSeat.new()
	seat9.acts = [{"act": "licence", "good": "chips", "to": c9, "open": false}]
	cf.seats[u9] = seat9
	cf.advance_to(31)
	cf.seats.erase(u9)
	cf.advance_to(365)
	var jp365: bool = cf.field.chain.is_open(j9, "chips", c9)
	cf.advance_to(396)
	var jp396: bool = cf.field.chain.is_open(j9, "chips", c9)
	var in396: bool = cf.field.chain.is_open(i9, "chips", c9)
	var cn396: bool = cf.field.chain.is_open(c9, "gallium", j9)
	cf.advance_to(455)
	var cn455: bool = cf.field.chain.is_open(c9, "gallium", j9)
	check(jp365 and not jp396 and in396 and cn396 and not cn455, "A9 Japan's chips to China open at day 365 %s, at day 396 %s; India's at 396 %s; China's gallium to Japan open at 396 %s, at 455 %s"
		% [str(jp365), str(jp396), str(in396), str(cn396), str(cn455)])

	var rx = _world()
	var cx: int = rx.data.index_of("CHN")
	rx.actors.restrict_p[cx] = 12.0
	rx.advance_to(31)
	var closed_all: bool = true
	for d: int in rx.field.E:
		if d != cx:
			closed_all = closed_all and not rx.field.chain.is_open(cx, "gallium", d)
	rx.actors.restrict_p[cx] = 0.0
	rx.advance_to(120)
	var answered: int = rx.actors.queued.filter(func(qq: Array) -> bool: return String(qq[4]) == "answer").size()
	rx.advance_to(396)
	var lifted: bool = true
	for d2: int in rx.field.E:
		if d2 != cx:
			lifted = lifted and rx.field.chain.is_open(cx, "gallium", d2)
	check(closed_all and answered == 0 and lifted, "A10 China's gallium closed to all at day 31: %s; answers queued %d; lifted by day 396: %s" % [str(closed_all),
		answered, str(lifted)])

	var fw = MW.new()
	fw.create(2022)
	fw.advance_to(31)
	var uf: int = fw.data.index_of("USA")
	var want_us: float = 0.21 * (153.9e9 / 0.277) * fw.field.fab_out[uf] * 365.0 / (1.0 - 0.125) / 200e3 / 25.6e6 / 12.0
	var world_yr: float = 0.0
	for ef: int in fw.field.E:
		world_yr += float(fw.actors.plan.get(ef, {}).get("fab", 0.0)) * 12.0
	check(absf(float(fw.actors.plan[uf]["fab"]) - want_us) < 1e-12 and world_yr > 0.025 and world_yr < 0.035,
		"A11 the USA's fab plan %.6f a month (by hand %.6f); the world's %.4f of capacity a year" % [float(fw.actors.plan[uf]["fab"]), want_us, world_yr])

	var costs = preload("res://sim/modern/modern_costs.gd").new()
	costs.create(q.data)
	var usa3: int = q.data.index_of("USA")
	var pub := {"solar": 50.0, "wind": 35.0, "gas": 60.0, "coal": 95.0}
	var weo := {"solar": 0.045, "wind": 0.045, "gas": 0.075, "coal": 0.075}
	var lc_ok: bool = true
	var got := {}
	for src3: String in pub:
		costs.wacc[usa3] = float(weo[src3])
		got[src3] = snappedf(costs.lcoe(usa3, src3), 0.1)
		lc_ok = lc_ok and absf(costs.lcoe(usa3, src3) - float(pub[src3])) < 1e-9
	costs.wacc[usa3] = 0.10
	var d_pv: float = costs.lcoe(usa3, "solar") / 50.0
	var d_coal: float = costs.lcoe(usa3, "coal") / 95.0
	lc_ok = lc_ok and d_pv > d_coal and d_coal > 1.0
	var pm: PackedFloat64Array = q.actors.pipeline_mix(q.field)
	var sums_ok: bool = true
	var fixed_ok: bool = true
	for e9: int in q.field.E:
		var t9: float = 0.0
		for s9: int in S:
			t9 += pm[e9 * S + s9]
			if ["nuclear", "hydro", "oil", "bioenergy", "other_renewable"].has(q.data.SOURCES[s9]):
				fixed_ok = fixed_ok and pm[e9 * S + s9] == q.field.mix[e9 * S + s9]
		sums_ok = sums_ok and (q.field.gen0[e9] == 0.0 or absf(t9 - 1.0) < 1e-9)
	check(lc_ok and sums_ok and fixed_ok, "A8 US LCOE at WEO's WACC %s; at 10%%: PV x%.2f, coal x%.2f; pipeline mix sums to 1: %s; other sources unmoved: %s" % [str(got),
		d_pv, d_coal, str(sums_ok), str(fixed_ok)])
	finish()
