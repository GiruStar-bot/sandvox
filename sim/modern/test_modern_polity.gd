extends "res://tools/test/test_kit.gd"
## The state, organs and powers (BLUEPRINT_v2 4, P1-P2 first cut; sim/modern/polity/organs.gd).
##   godot --headless --path . --script res://sim/modern/test_modern_polity.gd
## P1 the organs load: the lower house has 465 seats, the governing parties 215 after the 2024 election, no majority (233)
## P2 powers: the Cabinet may submit a bill with a cabinet decision and not without; the Diet may not enact a law (no majority in the lower
##    house); the Supreme Court has no power to enact; a tax-rate change needs enact_law, so it is refused under this composition
## P3 with a majority composition (a declared test change) the same tax-rate act passes; an amendment still fails (two thirds)
## P4 events are recorded and the state saves and restores exactly
## P9 the upper-house half election; P10 enforcement (late charges, procedure); P11 the public's approval (S4')
const ORG = preload("res://sim/modern/polity/organs.gd")
const CAB = preload("res://sim/modern/polity/cabinet.gd")
const EL = preload("res://sim/modern/polity/election.gd")
const ENF = preload("res://sim/modern/polity/enforcement.gd")
const PUB = preload("res://sim/modern/polity/public.gd")
const EM = preload("res://sim/modern/econ/econ_month.gd")


func _init() -> void:
	var o = ORG.new()
	var err: String = o.load_state("JPN")
	check(err == "" and o.house_total("house_of_representatives") == 465 and o.governing_seats("house_of_representatives") == 215 and not o.has_majority("house_of_representatives"),
		"P1 loaded '%s'; seats 465, governing %d, majority %s" % [err, o.governing_seats("house_of_representatives"), str(o.has_majority("house_of_representatives"))])
	var a: String = o.may("cabinet", "submit_bill", ["cabinet_decision"])
	var b: String = o.may("cabinet", "submit_bill", [])
	var c: String = o.may("diet", "enact_law")
	var d: String = o.may("supreme_court", "enact_law")
	var e: String = o.may("diet", "set_tax_rate")
	check(a == "" and b != "" and c != "" and d != "" and e != "", "P2 submit with decision '%s'; without '%s'; enact '%s'; court '%s'; tax '%s'" % [a, b, c, d, e])
	o.seats["house_of_representatives"]["LDP"] = 250
	o.seats["house_of_councillors"] = {"LDP": 130, "Komeito": 20, "CDP": 98}
	var f: String = o.may("diet", "set_tax_rate")
	var g: String = o.may("diet", "amend_constitution", ["referendum_majority"])
	check(f == "" and g != "", "P3 with a majority: tax '%s'; amendment '%s'" % [f, g])
	# P5 laws as data (S2'): the consumption tax needs enact_law (refused without the majority); a rice stock release is a ministerial
	# act (allowed); a nuclear restart is the NRA's, not the Cabinet's (refused); a budget lever within its room passes, beyond the room it
	# needs the reserve fund by a cabinet decision, beyond that a supplementary budget (refused without the majority)
	var o3 = ORG.new()
	o3.load_state("JPN")
	var t1: String = o3.may_pull_lever("consumption_tax_rate", ["cabinet_decision", "within_budget"])
	var t2: String = o3.may_pull_lever("rice_stock_release", ["cabinet_decision"])
	var t3: String = o3.may_pull_lever("nuclear_restart", ["cabinet_decision"])
	var t4: String = o3.may_pull_lever("public_investment", ["cabinet_decision", "within_budget"])
	var t5: String = o3.may_pull_lever("public_investment", ["cabinet_decision", "reserve_fund_room"])
	var t6: String = o3.may_pull_lever("public_investment", ["cabinet_decision"])
	check(t1 != "" and t2 == "" and t3 != "" and t4 == "" and t5 == "" and t6 != "", "P5 tax '%s'; rice release '%s'; restart '%s'; within budget '%s'; reserve '%s'; supplementary '%s'" % [t1, t2, t3, t4, t5, t6])
	# P6 the Cabinet's structured policy (S3'): a spending policy within the budget's room is verified and executed; a tax rise needs a
	#    law, so a bill is submitted; a malformed policy is refused with the missing field named
	var o6 = ORG.new()
	o6.load_state("JPN")
	var cab = CAB.new()
	cab.setup(o6)
	var set_: Array = []
	var setter: Callable = func(lid: String, v: float) -> void: set_.append([lid, v])
	var r1: Dictionary = cab.propose(0, {"purpose": "support demand", "target": "gdp_real_growth", "instrument": "public_investment", "value": 7000.0, "budget_bn": 200.0, "period_months": 12, "expected_effect": "+0.04 pt", "legal_basis": "budget_fy2024"}, ["cabinet_decision", "within_budget"], setter)
	var r2: Dictionary = cab.propose(0, {"purpose": "fiscal consolidation", "target": "debt_to_gdp", "instrument": "consumption_tax_rate", "value": 0.11, "budget_bn": 0.0, "period_months": 12, "expected_effect": "+2.8 tn revenue", "legal_basis": "consumption_tax_act"}, ["cabinet_decision"], setter)
	var r3: Dictionary = cab.propose(0, {"purpose": "x", "instrument": "public_investment"}, ["cabinet_decision"], setter)
	check(String(r1["status"]) == "executed" and set_.size() == 1 and String(r2["status"]).begins_with("bill") and String(r3["status"]) == "refused" and String(r3["verdict"]["why"]).begins_with("policy lacks"),
		"P6 spending '%s' (set %d); tax '%s'; malformed '%s'" % [r1["status"], set_.size(), r2["status"], r3["verdict"]["why"]])
	# P7 the Diet's vote (S3'): the tax-rise bill is voted after the session; every opposition party is against it (party_positions),
	#    the governing 215 are short of 233: rejected; a child-allowance bill backed by CDP, DPFP and Komeito passes
	cab.vote_due(4, setter)
	var b0_before: String = String(cab.bills[0]["status"])
	cab.vote_due(5, setter)
	var b0: String = String(cab.bills[0]["status"])
	cab.propose(5, {"purpose": "fertility", "target": "tfr", "instrument": "child_allowance", "value": 4000.0, "budget_bn": 400.0, "period_months": 12, "expected_effect": "small", "legal_basis": "child_allowance_act"}, ["cabinet_decision"], setter)
	cab.vote_due(10, setter)
	var b1: String = String(cab.bills[1]["status"])
	check(b0_before == "submitted" and b0 == "rejected" and b1 == "enacted" and set_.size() == 2, "P7 tax bill before the session %s, after %s (%d parties voted; the yes is 215 of 465); child allowance bill %s; levers set %d" % [b0_before, b0, int(cab.bills[0]["votes"].size()), b1, set_.size()])
	# P8 the election at the prefecture grain (S3'): the seats sum to 465; with no swing the governing bloc's share is the 2024 vote; with
	#    a fall in approval of 0.2 the governing bloc loses seats and the largest party governs with its partner, or alone as a minority
	var el = EL.new()
	el.load_state("JPN")
	var s0: Dictionary = el.vote_shares(["LDP", "Komeito"], 0.0, 0.0, 0.0)
	var e0: Dictionary = el.run_lower_house(s0)
	var sum0: int = 0
	for p: String in e0["seats"]:
		sum0 += int(e0["seats"][p])
	var s1: Dictionary = el.vote_shares(["LDP", "Komeito"], -0.2, 0.0, 0.0)
	var e1: Dictionary = el.run_lower_house(s1)
	var gov0: int = int(e0["seats"]["LDP"]) + int(e0["seats"]["Komeito"])
	var gov1: int = int(e1["seats"]["LDP"]) + int(e1["seats"]["Komeito"])
	var des: Dictionary = EL.designate(e1["seats"], ["LDP", "Komeito"], 465, o6.spec["partners"])
	check(sum0 == 465 and gov1 < gov0 and (des["governing"] as Array).size() >= 1, "P8 seats sum %d; governing %d -> %d after approval -0.2; designation %s (%s)" % [sum0, gov0, gov1, str(des["governing"]), des["why"]])
	# P9 the upper-house half election (S4'): 74 district seats and 50 proportional seats elected, 124 in all; with the continuing half
	#    the composition is 248; a fall in approval of 0.2 costs the governing bloc elected seats
	var u0: Dictionary = el.run_upper_house(s0)
	var u1: Dictionary = el.run_upper_house(s1)
	var el0: int = 0
	var comp0: int = 0
	for p: String in u0["elected"]:
		el0 += int(u0["elected"][p])
		comp0 += int(u0["composition"][p])
	var ugov0: int = int(u0["elected"]["LDP"]) + int(u0["elected"]["Komeito"])
	var ugov1: int = int(u1["elected"]["LDP"]) + int(u1["elected"]["Komeito"])
	check(el0 == 124 and comp0 == 248 and ugov1 < ugov0, "P9 elected %d, composition %d; governing elected %d -> %d after approval -0.2" % [el0, comp0, ugov0, ugov1])
	# P10 enforcement (S4'): after a loss that leaves food manufacturing in arrears, the statutory late rate is charged on the arrears
	#    each month (an event with its basis) and after three months a procedure opens that cuts the plant to 80%
	var ec = EM.new()
	ec.create("JPN")
	ec.declare_cash_loss(12, "food_manufacturing_JPN", 120000.0, "declared loss")
	var enf = ENF.new()
	for i: int in 18:
		ec.step()
		enf.step(i, ec)
	var late: int = 0
	var opened: int = 0
	for ev: Dictionary in enf.events:
		if String(ev["kind"]) == "late_charge":
			late += 1
		if String(ev["kind"]) == "procedure_opened":
			opened += 1
	var fm10 = ec.actors[1]
	check(late >= 3 and opened >= 1 and int(fm10.stocks.get("procedure_until", -1)) > 0, "P10 late charges %d, procedures opened %d, procedure until month %d, arrears %.1f" % [late, opened, int(fm10.stocks.get("procedure_until", -1)), float(fm10.stocks.get("arrears", 0.0))])
	# P11 the public (S4'): approval falls with a 10% food price rise (-1.5 points, T), with a tax rise (-5 points, T) and is clamped;
	#    the change since a month is read for the election's swing
	var pub = PUB.new()
	pub.load_state("JPN", 0.4)
	var a1: float = pub.step(0, 0.10, 0.0, [])
	var a2: float = pub.step(1, 0.0, 0.0, ["consumption_tax_rate"])
	var a3: float = pub.step(2, 0.0, 1.0, [])
	for i: int in 30:
		pub.step(3 + i, 0.5, 0.0, [])
	check(absf(a1 - 0.385) < 1e-9 and absf(a2 - 0.335) < 1e-9 and absf(a3 - 0.315) < 1e-9 and pub.approval >= 0.05 and absf(pub.change_since(1) - (pub.approval - 0.335)) < 1e-9 and pub.prefectures.size() == 47,
		"P11 approval 0.4 -> %.3f (food +10%%) -> %.3f (tax rise) -> %.3f (unemployment +1 pt); floor %.3f; 47 prefectures loaded %s" % [a1, a2, a3, pub.approval, str(pub.prefectures.size() == 47)])
	o.record(0, "cabinet_decision", "cabinet", {"bill": "budget FY2025"}, "art. 73")
	var st: Dictionary = bytes_to_var(var_to_bytes(o.to_dict()))
	var o2 = ORG.new()
	o2.load_state("JPN")
	o2.from_dict(st)
	check(o2.events.size() == 1 and o2.governing_seats("house_of_representatives") == 274, "P4 events %d; restored governing seats %d" % [o2.events.size(), o2.governing_seats("house_of_representatives")])
	finish()
