extends "res://sim/modern/econ/actor.gd"
## The banking group and the central bank (BLUEPRINT_v2 2, E5): one aggregate bank per jurisdiction. An actor whose cash would fall
## below its working floor asks for a loan; the bank lends when the borrower's credit score passes, at the policy rate plus a spread by
## score; interest accrues and equal instalments are paid monthly over the term; a borrower that cannot pay defaults: the loan is written
## off, the bank's equity takes the loss, the borrower's score falls and it is cut off for a stated time. The central bank sets the policy
## rate (the published path, S; a rule comes with expectations in S4') and funds the bank without limit (lender of last resort, T): money
## the bank lends beyond its own cash is created by the central bank and recorded as minted (the money ledger stays closed).
## Rules and parameters: data/modern/econ/banks_<j>.json (S where a BoJ figure exists, T otherwise). Reason codes: LOAN, REFUSE, PAY,
## DEFAULT, MINT.
var loans: Array = []          # [{id, borrower, principal, remaining, rate, term, start_month, paid, status}]
var score: Dictionary = {}     # borrower -> {"score": 0..1, "cut_off_until": month}
var policy_rate: float = 0.0025
var policy_path: Array = []    # [[month, rate]] the published path
var spread_by_score: Array = []  # [[min score, spread]]
var term_months: int = 60
var floor_months: float = 1.0  # working cash floor in months of costs (T)
var minted: float = 0.0
var equity0: float = 0.0
var rule: String = "taylor"     # the central bank's rule after the published path (S4')


func load_spec(path: String) -> String:
	var d: Variant = CANON.load_json(path)
	if not (d is Dictionary):
		return "banks: no spec at " + path
	setup(d)
	policy_rate = float(d["policy_rate"]["value"])
	policy_path = (d.get("policy_path", []) as Array).duplicate(true)
	spread_by_score = (d["spread_by_score"] as Array).duplicate(true)
	term_months = int(d["term_months"]["value"])
	floor_months = float(d["floor_months"]["value"])
	equity0 = float(stocks.get("cash_bn_jpy", 0.0))
	return ""


func rate_for(s: float) -> float:
	var spread: float = float(spread_by_score[0][1])
	for row: Array in spread_by_score:
		if s >= float(row[0]):
			spread = float(row[1])
	return policy_rate + spread


func debt_of(borrower: String) -> float:
	var t: float = 0.0
	for L: Dictionary in loans:
		if String(L["borrower"]) == borrower and String(L["status"]) == "open":
			t += float(L["remaining"])
	return t


## Step 1 of the month for the bank: the policy rate follows its published path; after the path's last month a Taylor-type rule (S4',
## T: i = max(0, r* + pi + 0.5 (pi - 2%)), r* = 0 (T), pi the inflation the economy reports; the rule is reviewed monthly, moved by at
## most 0.25 pt a quarter, the BoJ's step size (S: 2024-25 decisions))
func plan(world: RefCounted, month: int) -> void:
	var on_path: bool = false
	var last_path: int = -1
	for row: Array in policy_path:
		last_path = maxi(last_path, int(row[0]))
		if int(row[0]) == month:
			policy_rate = float(row[1])
			on_path = true
			note(month, "policy_rate", policy_rate, "published path (S)", "central bank")
	if not on_path and month > last_path and rule == "taylor" and (month - last_path) % 3 == 0:
		var pi: float = float(world.env.get("inflation", 0.02))
		var target: float = maxf(0.0, pi + 0.5 * (pi - 0.02))
		var step: float = clampf(target - policy_rate, -0.0025, 0.0025)
		if absf(step) >= 0.00125:
			policy_rate += step
			note(month, "policy_rate", policy_rate, "Taylor-type rule on the reported inflation (T), one step a quarter", "central bank pi %.3f target %.4f" % [pi, target])


## A borrower asks for a loan: amount lent (0 when refused); the money moves bank -> borrower; the bank is funded by the central bank
## when its own cash would go negative (minted money, recorded)
func request_loan(world: RefCounted, month: int, borrower: String, amount: float, monthly_revenue: float) -> float:
	var sc: Dictionary = score.get(borrower, {"score": 1.0, "cut_off_until": -1})
	if int(sc["cut_off_until"]) > month:
		note(month, "refuse_" + borrower, amount, "cut off after a default (T)", "REFUSE")
		return 0.0
	# credit score (T, a declared form until a published scoring rule): 1 - debt service / revenue, floored at 0
	var debt: float = debt_of(borrower) + amount
	var r: float = rate_for(float(sc["score"]))
	var service: float = debt / float(term_months) + debt * r / 12.0
	var s: float = clampf(1.0 - service / maxf(monthly_revenue, 1e-9), 0.0, 1.0)
	if s < 0.2:
		note(month, "refuse_" + borrower, amount, "debt service above 80% of revenue (T)", "REFUSE score %.2f" % s)
		return 0.0
	sc["score"] = s
	score[borrower] = sc
	var L := {"id": loans.size(), "borrower": borrower, "principal": amount, "remaining": amount, "rate": rate_for(s), "term": term_months, "start_month": month, "paid": 0.0, "status": "open"}
	loans.append(L)
	var own: float = float(world.cash.get(id, 0.0))
	if own < amount:
		world.pay("central_bank", id, amount - own, "funding the bank (minted)")
		minted += amount - own
		note(month, "mint", amount - own, "lender of last resort (T)", "MINT")
	world.pay(id, borrower, amount, "loan %d at %.2f%%" % [int(L["id"]), float(L["rate"]) * 100.0])
	note(month, "loan_" + borrower, amount, "min score 0.2 (T); rate = policy + spread by score", "LOAN id %d rate %.4f score %.2f" % [int(L["id"]), float(L["rate"]), s])
	return amount


## Step 5 for the bank: instalments and interest from every open loan; a borrower short of cash defaults
func settle(world: RefCounted, month: int) -> void:
	for L: Dictionary in loans:
		if String(L["status"]) != "open":
			continue
		var b: String = String(L["borrower"])
		var instalment: float = float(L["principal"]) / float(L["term"])
		var interest: float = float(L["remaining"]) * float(L["rate"]) / 12.0
		var due: float = minf(float(L["remaining"]), instalment) + interest
		var cash: float = float(world.cash.get(b, 0.0))
		if cash >= due:
			world.pay(b, id, due, "loan %d instalment + interest" % int(L["id"]))
			L["remaining"] = float(L["remaining"]) - minf(float(L["remaining"]), instalment)
			L["paid"] = float(L["paid"]) + due
			if float(L["remaining"]) <= 1e-9:
				L["status"] = "repaid"
			note(month, "pay_" + b, due, "equal principal + interest", "PAY loan %d" % int(L["id"]))
		else:
			L["status"] = "default"
			var sc: Dictionary = score.get(b, {"score": 1.0, "cut_off_until": -1})
			sc["score"] = 0.0
			sc["cut_off_until"] = month + 12
			score[b] = sc
			stocks["write_offs"] = float(stocks.get("write_offs", 0.0)) + float(L["remaining"])
			note(month, "default_" + b, float(L["remaining"]), "cash below the instalment", "DEFAULT loan %d; cut off 12 months (T)" % int(L["id"]))


func to_dict() -> Dictionary:
	var d: Dictionary = super.to_dict()
	d["loans"] = loans.duplicate(true)
	d["score"] = score.duplicate(true)
	d["policy_rate"] = policy_rate
	d["minted"] = minted
	return d


func from_dict(d: Dictionary) -> void:
	super.from_dict(d)
	loans = (d.get("loans", []) as Array).duplicate(true)
	score = (d.get("score", {}) as Dictionary).duplicate(true)
	policy_rate = float(d.get("policy_rate", policy_rate))
	minted = float(d.get("minted", 0.0))
