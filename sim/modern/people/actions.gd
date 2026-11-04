extends RefCounted
## Decisions and actions of a person (ISS Phase 2; ISS_PHASE0_SURVEY.md 1.7 "one generic pipeline"). Four separated steps, each a
## function: candidates(p, i) lists what a person could try; feasible(p, i, a) says why not (law, age, money: guards, never scores);
## score(p, i, a) is the expected relief of the drives (weights x expected deficit change, T table) modulated by emotions and traits, the
## person's own experience of the action (q_act, learned from outcomes) and loss aversion on money and risk; choose(p, i) picks by softmax
## with ONE keyed uniform (temperature T); apply(p, i, a) changes only what the person owns (hours, plan, search, skill, assets, place,
## the dream) — wages, jobs and prices stay the economy's, which answers through rates. Every decision records its top-scoring drive and
## the emotion that modulated it; a refused candidate records the guard that refused it.
const ACTIONS := ["keep_course", "search_job", "change_job", "train", "thrift", "splurge", "rest", "socialize", "support_family", "move", "pursue_dream", "join_group", "found_group", "leave_group"]
const NA := 14
const A_KEEP := 0            # the indices of ACTIONS
const A_SEARCH := 1
const A_CHANGE := 2
const A_TRAIN := 3
const A_THRIFT := 4
const A_SPLURGE := 5
const A_REST := 6
const A_SOCIALIZE := 7
const A_SUPPORT := 8
const A_MOVE := 9
const A_DREAM := 10
const A_JOIN := 11
const A_FOUND := 12
const A_LEAVE := 13
const TAU := 0.03          # T: softmax temperature on utilities of order 0.01-0.1 (choice.gd's 0.1 sits on utilities of order 1); at
                           # 0.12 the choice was nearly uniform and no tilt reached the actions (found in the Phase 5 counterfactual)
const TRAIN_COST := 3.0     # 万円 a month (T)
const MOVE_COST := 50.0     # 万円 (T: 引越し費用 + 敷金)
const SOCIAL_COST := 1.0
const SUPPORT_COST := 2.0
const CHANGE_P := 0.25      # T: a job change found in a month of looking
const SEARCH_BOOST := 1.6   # T: searchers find at 1.6 x the economy's rate, the rest at 0.6 x
const NO_SEARCH := 0.6


## The drive a dream kind serves (DREAMS order: start_business, have_family, become_expert, financial_freedom, contribute_locally,
## become_known, stable_life, change_society). Why a function and not a const list: the drive constants are people.gd's, and a const
## here cannot read them without a preload cycle
static func dream_drive(p: RefCounted, k: int) -> int:
	return [p.D_AUTONOMY, p.D_FAMILY, p.D_GROWTH, p.D_SECURITY, p.D_CONTRIBUTION, p.D_RECOGNITION, p.D_SECURITY, p.D_CHANGE][k]


static func candidates(p: RefCounted, i: int) -> Array:
	var out: Array = [A_KEEP]
	var a: int = p.age[i]
	var e: int = p.employment[i]
	if a < 15:
		return [A_KEEP, A_REST, A_SOCIALIZE]
	if e == p.EMP_UNEMPLOYED:
		out.append(A_SEARCH)
	if e == p.EMP_REGULAR or e == p.EMP_NONREGULAR:
		out.append(A_CHANGE)
	if a < 60 and e != p.EMP_RETIRED:
		out.append(A_TRAIN)
	out.append_array([A_THRIFT, A_SPLURGE, A_REST, A_SOCIALIZE, A_SUPPORT])
	if a >= 18 and a < 60:
		out.append(A_MOVE)
	if p.dream_kind[i] >= 0 and p.dream_status[i] == 0:
		out.append(A_DREAM)
	if a >= 18:
		out.append_array([A_JOIN, A_FOUND, A_LEAVE])
	return out


## "" when the person can do it this month, else the guard that refuses it (feasibility is never a score)
static func feasible(p: RefCounted, i: int, a: int) -> String:
	match a:
		A_SEARCH:
			return "" if p.employment[i] == p.EMP_UNEMPLOYED else "not unemployed"
		A_CHANGE:
			return "" if (p.employment[i] == p.EMP_REGULAR or p.employment[i] == p.EMP_NONREGULAR) else "no job to leave"
		A_TRAIN:
			if p.assets[i] < TRAIN_COST:
				return "assets below the training cost"
			return "" if p.employment[i] != p.EMP_RETIRED else "retired"
		A_SPLURGE:
			return "" if p.income[i] > 0.0 or p.assets[i] > 10.0 else "no money to spend"
		A_SOCIALIZE:
			return "" if p.assets[i] >= SOCIAL_COST or p.age[i] < 15 else "no money for it"
		A_SUPPORT:
			if p.hh_kind[i] == p.HK_SINGLE and p.age[i] > 60:
				return "no family household"
			return "" if p.income[i] > SUPPORT_COST else "no income to give"
		A_MOVE:
			if p.assets[i] < MOVE_COST:
				return "assets below the moving cost"
			if p.households and p.move_reason(i) == "":
				return "no reason to move"
			return "" if p.age[i] >= 18 and p.age[i] < 60 else "age"
		A_DREAM:
			return "" if (p.dream_kind[i] >= 0 and p.dream_status[i] == 0) else "no active dream"
		A_JOIN:
			if p.GRP.memberships(p, i) >= p.GRP.M:
				return "no room for another membership"
			return "" if p.GRP.pick_group(p, i) >= 0 else "no group to join here"
		A_FOUND:
			if p.GRP.find_group(p, p.GRP.G_MOVEMENT, p.pref[i]) >= 0:
				return "a movement exists here already"
			if p.GRP.memberships(p, i) >= p.GRP.M:
				return "no room for another membership"
			return "" if p.GRP.discontented_contacts(p, i) >= 2 else "fewer than two discontented contacts"
		A_LEAVE:
			return "" if p.GRP.memberships(p, i) > 0 else "no membership to leave"
	return ""


## Expected deficit change per drive for the action (negative = relief), T table; context scales it
static func delta(p: RefCounted, i: int, a: int) -> PackedFloat64Array:
	var d := PackedFloat64Array()
	d.resize(10)
	var e: int = p.employment[i]
	match a:
		A_SEARCH:
			d[p.D_SECURITY] = -0.45
			d[p.D_AUTONOMY] = -0.1
			d[p.D_RECOGNITION] = -0.1
		A_CHANGE:
			d[p.D_SECURITY] = -0.2 if e == p.EMP_NONREGULAR else -0.05
			d[p.D_RECOGNITION] = -0.15
			d[p.D_AUTONOMY] = -0.1
			d[p.D_BELONGING] = 0.05
		A_TRAIN:
			d[p.D_GROWTH] = -0.3
			d[p.D_SECURITY] = -0.15 * (0.5 + p.trait_of(i, "future_orientation"))
			d[p.D_ENJOYMENT] = 0.1
		A_THRIFT:
			# Why scaled by the believed rise of the cost of living: thrift answers what the person thinks prices do to its budget; a flat
			# relief left the drought's anxiety without an outlet (Phase 5 E3); x4 = a believed rise of a quarter doubles it (T)
			d[p.D_SECURITY] = -0.15 * (1.0 + 4.0 * p.believed_cost_rise(i))
			d[p.D_ENJOYMENT] = 0.15
		A_SPLURGE:
			d[p.D_ENJOYMENT] = -0.3
			d[p.D_SECURITY] = 0.15
			d[p.D_RECOGNITION] = -0.05
		A_REST:
			d[p.D_ENJOYMENT] = -0.2
			d[p.D_SURVIVAL] = -0.05
			d[p.D_RECOGNITION] = 0.05
		A_SOCIALIZE:
			d[p.D_BELONGING] = -0.25 * (0.5 + p.pref_social[i])
			d[p.D_ENJOYMENT] = -0.1
		A_SUPPORT:
			d[p.D_FAMILY] = -0.3
			d[p.D_SECURITY] = 0.1
			d[p.D_CONTRIBUTION] = -0.1
		A_MOVE:
			d[p.D_SECURITY] = -0.25 if e == p.EMP_UNEMPLOYED else -0.08
			d[p.D_BELONGING] = 0.2
			d[p.D_AUTONOMY] = -0.05
		A_DREAM:
			d[dream_drive(p, p.dream_kind[i])] = -0.3 * p.dream_importance[i]
			d[p.D_ENJOYMENT] = 0.1
		A_JOIN:
			d[p.D_BELONGING] = -0.25
			d[p.D_CONTRIBUTION] = -0.1
			d[p.D_CHANGE] = -0.1 if p.emotion(i, "discontent") > 0.4 else 0.0
			d[p.D_ENJOYMENT] = 0.05
		A_FOUND:
			d[p.D_CHANGE] = -0.4
			d[p.D_RECOGNITION] = -0.15
			d[p.D_CONTRIBUTION] = -0.1
			d[p.D_ENJOYMENT] = 0.15
		A_LEAVE:
			d[p.D_ENJOYMENT] = -0.05
			d[p.D_BELONGING] = 0.1
	return d


## The utility and its reasons: drive relief (weights boosted by the emotions that fit), experience, money and risk with loss aversion
static func score(p: RefCounted, i: int, a: int) -> Dictionary:
	var d: PackedFloat64Array = delta(p, i, a)
	var anx: float = p.emotion(i, "anxiety")
	var dis: float = p.emotion(i, "discontent") + p.emotion(i, "anger")
	var hope: float = p.emotion(i, "hope")
	var lone: float = p.emotion(i, "loneliness")
	var u: float = 0.0
	var top: int = -1
	var top_v: float = 0.0
	var mod: String = ""
	for k: int in 10:
		var w: float = p.dw[i * 10 + k]
		# emotions tilt the weights: anxiety toward security, discontent toward change and autonomy, loneliness toward belonging
		if k == 1:
			w *= 1.0 + anx
		elif k == 9 or k == 4:
			w *= 1.0 + 0.8 * dis
		elif k == 2:
			w *= 1.0 + lone
		# the deficit still unmet scales the relief: nothing to gain where the deficit is 0
		var v: float = -w * d[k] * (0.3 + p.dd[i * 10 + k])
		u += v
		if v > top_v:
			top_v = v
			top = k
	if top == p.D_SECURITY and anx > 0.4:
		mod = "anxiety"
	elif (top == p.D_CHANGE or top == p.D_AUTONOMY) and dis > 0.5:
		mod = "discontent"
	elif top == p.D_BELONGING and lone > 0.4:
		mod = "loneliness"
	# money: a cost is a loss (λ) against the month's income
	var cost: float = [0.0, 0.0, 0.0, TRAIN_COST, 0.0, 0.2 * p.income[i], 0.0, SOCIAL_COST, SUPPORT_COST, MOVE_COST / 12.0, 0.1 * p.income[i], 0.1, 0.0, 0.0][a]
	if cost > 0.0:
		u -= 0.3 * p.lam[i] * cost / maxf(5.0, p.income[i] + 0.2 * p.assets[i] / 12.0) * p.dw[i * p.ND + p.D_SECURITY]
	# risk: uncertain actions cost more to the risk-averse, less to the hopeful
	if a == A_CHANGE or a == A_MOVE or (a == A_DREAM and p.dream_kind[i] == 0):
		u -= 0.12 * p.lam[i] * (1.0 - p.trait_of(i, "risk_tolerance")) * (1.2 - 0.6 * hope)
	# founding is the act of the open and the competitive; the deferential found nothing (T)
	if a == A_FOUND:
		u *= 0.4 + 0.6 * p.trait_of(i, "openness") + 0.4 * (0.5 - p.trait_of(i, "authority_attitude"))
	# delayed payoffs by future orientation
	if a == A_TRAIN or a == A_DREAM or a == A_MOVE:
		u *= 0.5 + p.trait_of(i, "future_orientation")
	# experience: what this action did for the person before (learned from outcomes)
	u += 0.3 * p.q_act[i * NA + a]
	# conformity (choice.gd with_conformity, kappa 0.06): the share of the person's contacts who did this last month, by sociability
	if a == A_THRIFT or a == A_SPLURGE or a == A_SOCIALIZE:
		u += 0.06 * p.pref_social[i] * p.REL.contact_action_share(p, i, a)
	return {"u": u, "top_drive": top, "modulated_by": mod}


## The choice: softmax over the feasible candidates with one keyed uniform; refusals recorded
static func choose(p: RefCounted, i: int, month: int) -> Dictionary:
	var law: Dictionary = action_law(p, i)
	var ok: Array = law["actions"]
	var ws: PackedFloat64Array = law["weights"]
	var scores: Array = law["scores"]
	var x: float = p.u("choose", i, month) * float(law["total"])
	var pick: int = ok.size() - 1
	var acc: float = 0.0
	for j: int in ok.size():
		acc += ws[j]
		if x < acc:
			pick = j
			break
	var chosen: Dictionary = scores[pick]
	return {"action": int(ok[pick]), "top_drive": int(chosen["top_drive"]), "modulated_by": String(chosen["modulated_by"]), "u": float(chosen["u"]), "refused": law["refused"], "options": ok.size()}


## The month's decision as a law over the feasible actions (§14.1, T2.R): the actions in candidate order, their softmax weights at TAU
## and the weights' total (an action's probability is its weight ÷ the total), the scores and the refusals; pure, so a person draws one
## keyed u against the cumulative weights and a point the conditional binomials of §14.1
static func action_law(p: RefCounted, i: int) -> Dictionary:
	var cands: Array = candidates(p, i)
	var ok: Array = []
	var refused: Array = []
	var scores: Array = []
	for a: int in cands:
		var why: String = feasible(p, i, a)
		if why == "":
			ok.append(a)
			scores.append(score(p, i, a))
		else:
			refused.append([a, why])
	var best: float = -INF
	for s: Dictionary in scores:
		best = maxf(best, float(s["u"]))
	var ws: PackedFloat64Array = PackedFloat64Array()
	var tot: float = 0.0
	for s: Dictionary in scores:
		var w: float = p.DM.exp((float(s["u"]) - best) / TAU)
		ws.append(w)
		tot += w
	return {"actions": ok, "weights": ws, "total": tot, "scores": scores, "refused": refused}


## The action's effects on what the person owns; the economy answers job actions through its rates (in people.step)
static func apply(p: RefCounted, i: int, a: int, month: int) -> void:
	p.reset_choices(i)
	match a:
		A_SEARCH:
			p.set_search(i, 1)
		A_CHANGE:
			p.set_search(i, 2)
		A_TRAIN:
			p.spend(i, TRAIN_COST)
			p.add_skill(i, 2.0 * (0.5 + p.trait_of(i, "openness")))
		A_THRIFT:
			p.set_plan(i, 0)
		A_SPLURGE:
			p.set_plan(i, 2)
		A_REST:
			p.add_flag(i, p.F_REST)
		A_SOCIALIZE:
			p.spend(i, SOCIAL_COST)
			p.add_flag(i, p.F_SOCIALISED)
		A_SUPPORT:
			p.spend(i, SUPPORT_COST)
			p.add_flag(i, p.F_SUPPORTED)
		A_MOVE:
			p.spend(i, MOVE_COST)
			p.move_to(i, p.move_destination(i, month), p.move_reason(i) if p.households else "")
			p.add_flag(i, p.F_MOVED)
		A_DREAM:
			p.set_plan(i, 0)
			p.add_flag(i, p.F_DREAM)
		A_JOIN:
			var g: int = p.GRP.pick_group(p, i)
			if g >= 0:
				p.GRP.join(p, i, g)
				p.add_flag(i, p.F_JOINED)
		A_FOUND:
			p.add_flag(i, p.F_FOUNDED)
		A_LEAVE:
			# leaves the membership that relieves least: the held group whose purpose drive has the smallest deficit (V088: the code took
			# the first held, which is the union for most, so leaving stripped the unions)
			var pick: int = -1
			var low: float = INF
			for m: int in p.GRP.M:
				var g: int = p.member_of[i * p.GRP.M + m]
				if g >= 0:
					var dv: float = p.dd[i * 10 + p.GRP.PURPOSE[int(p.groups[g]["kind"])]]
					if dv < low:
						low = dv
						pick = g
			if pick >= 0:
				p.GRP.leave(p, i, pick)
