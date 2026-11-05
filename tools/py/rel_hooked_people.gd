extends "res://sim/modern/people/people.gd"
## REL_PORT_PLAN §2: people.gd's step (people.gd:1240-1307 at the frozen oracle, copied by a script, not by hand) with the cuts'
## snapshot calls; row D-hook shows its digest equals the frozen step's every month. hook == null runs the copy alone
## Why a copy and not hooks in people.gd: the GDScript is frozen (D475), and the module calls are static, so no override reaches them
var hook = null


func step(env: Dictionary) -> void:
	var infl: float = float(env.get("inflation_month", 0.02 / 12.0))
	price_index *= 1.0 + infl
	wage_index = float(env.get("wage_index", wage_index))
	_pension_month()
	var ur: float = float(env.get("unemployment_rate", float(spec["unemployment_rate_start"]["value"])))
	var f: float = float(spec["job_finding_rate_month"]["value"])
	var yoy_true: float = float(env.get("food_price_yoy", 0.0))
	var levers: Array = env.get("levers", [])
	var counts: Dictionary = {}
	var dec_counts: Dictionary = {}
	var ref_counts: Dictionary = {}
	if hook != null:
		hook.cut_pre(self)
	# A every person decides on last month's state (candidates -> feasibility -> score -> one keyed draw -> own effects)
	for i: int in n:
		# 0 the decision (Phase 2): candidates -> feasibility -> score -> one keyed softmax draw -> the action's own effects
		var ch: Dictionary = ACT.choose(self, i, month)
		var act: int = int(ch["action"])
		ACT.apply(self, i, act, month)
		if act == ACT.A_FOUND:
			GRP.found_movement(self, i, counts)
		last_action[i] = act
		_count_decision(dec_counts, act, int(ch["top_drive"]), String(ch["modulated_by"]), i)
		for r: Array in ch["refused"]:
			var rk: String = "%d|%s" % [int(r[0]), String(r[1])]
			ref_counts[rk] = int(ref_counts.get(rk, 0)) + 1
		if trace_pids.has(pid[i]):
			trace.append([month, pid[i], "decision", ACT.ACTIONS[act], float(ch["u"]), "top drive %s%s, %d options" % [DRIVES[int(ch["top_drive"])] if int(ch["top_drive"]) >= 0 else "none", (" (" + String(ch["modulated_by"]) + ")") if String(ch["modulated_by"]) != "" else "", int(ch["options"])]])
	# B the month's interactions (socialize partners, family support, help asked), what people come to believe, the groups
	if hook != null:
		hook.cut_a(self, counts, dec_counts, ref_counts)
	REL.interact(self, counts)
	REL.learn(self, {"food_price_yoy": yoy_true, "unemployment_rate": ur}, counts)
	GRP.step(self, counts)
	# Why after the decisions (G7a): they reset and set the search states the finds use; read before them, f̄ took last month's states
	# and the persons' unemployment settled at about 0.75 of u (M2-3's trace)
	if hook != null:
		hook.cut_b(self, counts, {"food_price_yoy": yoy_true, "unemployment_rate": ur})
	var s: float = _mean_finding(f) * ur / maxf(1e-6, 1.0 - ur)
	# C what the month does to each person
	var pools: Dictionary = {}
	for i0: int in n:
		if not pools.has(pref[i0]):
			pools[pref[i0]] = []
		pools[pref[i0]].append(i0)
	for i: int in n:
		# 1 the year turns on the person's own month: age, death (the cohort's hazard), transitions of status, the contacts renewed
		if month % 12 == int(pid[i] % 12):
			_year(i, counts)
			if contact_renewal:
				if hook != null:
					hook.cut_r_pre(self, i, pools[pref[i]])
				REL.replenish(self, i, pools[pref[i]])
				if hook != null:
					hook.cut_r_post(self, i)
		# 2 the economy's labour market decides this person's job this month (labour.gd owns employment: survey 2)
		LAB.person_month(self, i, s, f, counts)
		apply_month_values(i, month_values(SV.new().of_person(self, i), infl, levers), counts)
	if households:
		LC.grade_birthday(self)
		LC.month(self, counts)
	reweight(env.get("cohort", PackedFloat64Array()))
	if households:
		LC.quartile_cuts(self)
	if hook != null:
		hook.cut_w_pre(self)
	GRP.refresh_weights(self)
	if hook != null:
		hook.cut_w_post(self)
	_ranks()
	if hook != null:
		hook.cut_rank_post(self)
		hook.cut_rec_pre(self, counts, dec_counts, ref_counts)
	for key: String in dec_counts:
		decisions.append(dec_counts[key])
	for rk: String in ref_counts:
		var parts: PackedStringArray = rk.split("|")
		refusals.append({"month": month, "action": ACT.ACTIONS[int(parts[0])], "why": parts[1], "count": int(ref_counts[rk])})
	for kind: String in counts:
		var c: Dictionary = counts[kind]
		events.append({"month": month, "kind": kind, "count": int(c["n"]), "weight": float(c["w"]), "mean_move": float(c["move"]) / maxf(1.0, float(c["n"])), "why": String(c["why"])})
	if hook != null:
		hook.cut_rec_post(self)
	if tiers:
		TR.step(self, env)
	month += 1
