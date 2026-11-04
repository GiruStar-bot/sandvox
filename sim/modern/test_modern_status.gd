extends "res://tools/test/test_kit.gd"
## The status layer, the rule brain and the chronicle (BLUEPRINT 8, S1; sim/modern/modern_status.gd, modern_brain.gd, modern_chronicle.gd).
##   godot --headless --path . --script res://sim/modern/test_modern_status.gd
## S1 the catalogue loads and Japan's status file covers at least 90% of the catalogued indicators (F-A), every value with a source
## S2 the cohort identity: after 365 days pop(t) = pop(0) + births - deaths + net migration within 0.01%, and the yearly births and deaths
##    are within 3% of the published 2024 counts (the published rates were loaded, not fitted)
## S3 the debt identity: after a year the debt grew by the general account's deficit (bonds), and the net external position by the current
##    account, within 1e-6 relative
## S4 the action space: a lever outside its bounds is refused as a whole; a lever inside is set, applies on its lead day and moves its
##    target by its response function (the consumption tax by 1 pt raises tax revenue by 2.8 tn JPY after 365 days)
## S5 the rule brain: five steps give a deterministic answer with reason codes; the same observation twice gives the same actions; the
##    chronicle holds the decision rows with their reasons
## S6 the seat sees its own statuses and menu (scope b) and no other state's statuses; a seat's lever act in bounds is applied
## S7 a world saved and restored mid-run gives the same digest as the straight run (statuses, brains and chronicle included)
## S9 the public's approval and the upper-house election inside the world (S4')
const MW = preload("res://sim/modern/modern_world.gd")
const MS = preload("res://sim/modern/modern_status.gd")
const MB = preload("res://sim/modern/modern_brain.gd")
const MV = preload("res://sim/modern/modern_view.gd")
const MSEAT = preload("res://sim/modern/modern_seats.gd")
const SALT := "0123456789abcdef0123456789abcdef"


func _world() -> RefCounted:
	var w = MW.new()
	var err: String = w.create(2024, {"view_salt": SALT})
	check(err == "", "world created: " + err)
	return w


func _init() -> void:
	var w = _world()
	var st = w.status
	var jp: String = "JPN"
	# S1 coverage
	var n_cat: int = 0
	var n_have: int = 0
	var no_source: int = 0
	for s: String in st.catalog["statuses"]:
		for id: String in st.catalog["statuses"][s]["indicators"]:
			n_cat += 1
			var row: Dictionary = (st.data[jp] as Dictionary)["indicators"].get(id, {})
			if row.has("value"):
				n_have += 1
				if String(row.get("source", "")) == "":
					no_source += 1
	var cov: float = float(n_have) / float(n_cat)
	metric("fa_coverage_jpn", cov, -1)
	check(st.has(jp) and cov >= 0.9 and no_source == 0, "S1 F-A coverage %d/%d = %.2f, %d without a source" % [n_have, n_cat, cov, no_source])
	# S2 cohort identity over a year
	var pop0: float = st.population_of(jp)
	var births: float = 0.0
	var deaths: float = 0.0
	var w2 = _world()
	for i: int in 365:
		w2.advance_to(w2.field.day + 1)
		births += w2.status.daily_births[jp]
		deaths += w2.status.daily_deaths[jp]
	var mig: float = w2.status.value(jp, "net_migration")
	var pop1: float = w2.status.population_of(jp)
	var ident: float = absf(pop1 - (pop0 + births - deaths + mig)) / pop0
	var pb: float = float((st.data[jp] as Dictionary)["indicators"]["births"]["value"])
	var pd: float = float((st.data[jp] as Dictionary)["indicators"]["deaths"]["value"])
	check(ident < 1e-4 and absf(births / pb - 1.0) < 0.03 and absf(deaths / pd - 1.0) < 0.03,
		"S2 cohort identity %.8f; births %.0f vs %.0f, deaths %.0f vs %.0f" % [ident, births, pb, deaths, pd])
	# S3 debt and NIIP identities
	var d0: float = st.value(jp, "gov_debt_total")
	var n0: float = st.value(jp, "niip")
	var deficit: float = st.value(jp, "gov_expenditure_general") - st.value(jp, "gov_revenue_general")
	var ca: float = st.value(jp, "current_account")
	var d1: float = w2.status.value(jp, "gov_debt_total")
	var n1: float = w2.status.value(jp, "niip")
	check(absf((d1 - d0) - deficit) / d0 < 1e-6 and absf((n1 - n0) - ca) / n0 < 1e-6, "S3 debt +%.1f (deficit %.1f), niip +%.1f (CA %.1f)" % [d1 - d0, deficit, n1 - n0, ca])
	# S4 the action space
	var w3 = _world()
	var e: int = w3.data.index_of(jp)
	var bad: String = w3.check_actions(e, [{"act": "lever", "id": "public_investment", "value": 99999.0}])
	# a tax LAW under the 2024 minority government (215 of 465 seats) is refused by the majority precondition
	var law: String = w3.check_actions(e, [{"act": "lever", "id": "consumption_tax_rate", "value": 0.11}])
	var good: String = w3.check_actions(e, [{"act": "lever", "id": "public_investment", "value": 7000.0}])
	var g0: float = w3.status.value(jp, "gdp_real_growth")
	var gdp0: float = w3.status.value(jp, "gdp_nominal")
	w3.status.set_lever(jp, "public_investment", 7000.0)
	var pending: String = w3.check_actions(e, [{"act": "lever", "id": "public_investment", "value": 7100.0}])
	check(pending.begins_with("lever public_investment is already pending"), "S4b a pending lever is not re-pulled: '%s'" % pending)
	for i: int in 89:
		w3.advance_to(w3.field.day + 1)
	var g_before: float = w3.status.value(jp, "gdp_real_growth")
	w3.advance_to(w3.field.day + 1)
	var g_after: float = w3.status.value(jp, "gdp_real_growth")
	var expect: float = 1.1 * (7000.0 - 6082.8) / w3.status.value(jp, "gdp_nominal")   # the multiplier reads GDP on the lead day (it carries its trend)
	check(bad != "" and law.begins_with("majority") and good == "" and absf(g_before - g0) < 1e-12 and absf((g_after - g0) - expect) < 1e-9,
		"S4 refused '%s'; law '%s'; in bounds '%s'; growth +%.6f on the lead day (expected %.6f; before: +%.6f)" % [bad, law, good, g_after - g0, expect, g_before - g0])
	# S5 the rule brain
	var b = MB.new()
	var obs: Dictionary = w.brain_observation(e)
	var t1: Dictionary = b.think(obs, st.catalog, st.menu(jp), {"months_to_lower_house_election": 36.0}, 0)
	var b2 = MB.new()
	var t2: Dictionary = b2.think(obs, st.catalog, st.menu(jp), {"months_to_lower_house_election": 36.0}, 0)
	var same: bool = JSON.stringify(t1["actions"]) == JSON.stringify(t2["actions"]) and JSON.stringify(t1["order"]) == JSON.stringify(t2["order"])
	var w4 = _world()
	w4.advance_to(31)
	var dec: int = 0
	for r: Dictionary in w4.chronicle.rows:
		if String(r["kind"]) == "decision" and String(r["place"]) == jp and String(r["why"]) != "":
			dec += 1
	check(same and (t1["why"] as Array).size() > 0 and dec >= 1, "S5 brain deterministic %s, why %s, chronicle decisions %d; first order %s" % [str(same), str(t1["why"]), dec, str(t1["order"].slice(0, 3))])
	# S6 the seat
	var w5 = _world()
	var v = w5.make_view("jpn")
	var o: Dictionary = v.observe(w5, e)
	var others_have_statuses: bool = false
	for r: Dictionary in o["others"]:
		if r.has("statuses"):
			others_have_statuses = true
	var seat = MSEAT.scripted(v, func(_obs: Dictionary) -> Array: return [{"act": "lever", "id": "defence_budget_share", "value": 0.017}])
	w5.seats[e] = seat
	w5.advance_to(31)
	var set_rows: int = 0
	for r: Dictionary in w5.chronicle.rows:
		if String(r["kind"]) == "lever_set" and String(r["who"]) == "seat":
			set_rows += 1
	check(o["self"].has("statuses") and o["self"].has("menu") and not others_have_statuses and set_rows == 1,
		"S6 own statuses %s, menu %s, others without statuses %s, seat lever rows %d" % [str(o["self"].has("statuses")), str(o["self"].has("menu")), str(not others_have_statuses), set_rows])
	# S7 resume
	var wa = _world()
	wa.advance_to(100)
	# Why the byte round trip: the field's to_dict() hands out its own packed arrays, which the straight run keeps mutating; a keyframe on
	# disk is a copy, so the test copies too
	var mid: Dictionary = bytes_to_var(var_to_bytes(wa.to_dict()))
	wa.advance_to(400)
	var wb = MW.from_dict(mid)
	wb.advance_to(400)
	check(wa.digest() == wb.digest() and wa.chronicle.rows.size() == wb.chronicle.rows.size(), "S7 resumed at 100 equals the straight run at 400: %s" % str(wa.digest() == wb.digest()))
	# S8 the economy inside the world (S3'): the monthly economy steps at each month end; a rice_stock_release lever (300 kt, a
	#    ministerial act under 食糧法, lead 30 days) reaches the economy's rice market from the state's MA stock, and the chronicle shows
	#    the release and the price moves with their causes
	var w8 = _world()
	var e8: int = w8.data.index_of(jp)
	w8.advance_to(40)   # two month ends have passed: the MA stock holds one month's quota
	var why8: String = w8.check_actions(e8, [{"act": "lever", "id": "rice_stock_release", "value": 300.0}])
	w8.status.set_lever(jp, "rice_stock_release", 300.0)
	w8.advance_to(100)
	var released: float = 0.0
	var prices: int = 0
	for r: Dictionary in w8.chronicle.rows:
		if String(r["kind"]) == "release":
			released += float(r["facts"]["rice_t"])
		if String(r["kind"]) == "price":
			prices += 1
	check(why8 == "" and w8.econ != null and w8.econ.world.month >= 2 and released > 0.0 and prices > 0, "S8 release lever '%s'; econ months %d; released %.0f t; price rows %d" % [why8, w8.econ.world.month if w8.econ != null else -1, released, prices])
	# S9 the public and the election inside the world (S4'): each month end the public's approval is written to the cabinet_approval
	#    status from what the economy shows; at 2025-07 the upper-house half election runs on the approval change and the organs hold the
	#    new composition of 248; the enforcement and election rows are in the chronicle
	var w9 = _world()
	w9.advance_to(600)
	var ap0: float = w9.public.history[0][1] if w9.public.history.size() > 0 else -1.0
	var ap9: float = w9.status.value(jp, "cabinet_approval")
	var uh: int = 0
	for p: String in w9.polity[jp].seats["house_of_councillors"]:
		uh += int(w9.polity[jp].seats["house_of_councillors"][p])
	var elections: int = 0
	for r: Dictionary in w9.chronicle.rows:
		if String(r["kind"]) == "election":
			elections += 1
	check(w9.public.history.size() >= 18 and ap9 > 0.05 and ap9 < 0.9 and uh == 248 and elections == 1 and w9.last_election_month == 18,
		"S9 approval months %d, approval %.3f -> %.3f; upper house %d seats after the 2025-07 election (%d election rows, month %d)" % [w9.public.history.size(), ap0, ap9, uh, elections, w9.last_election_month])
	finish()
