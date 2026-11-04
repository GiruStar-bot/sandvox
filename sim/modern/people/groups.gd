extends RefCounted
## Groups and the population structure (ISS Phase 4; survey 1.5, ISS 4.1-4.5). Two different things: a CLASS is a tag read from the
## attributes (age band, employment status, income tercile, education, prefecture) that a person is in without choosing; a GROUP is a
## body of members with a purpose, resources, trust and influence that a person joins, founds or leaves (an action of actions.gd).
## Start groups per prefecture from published rates (union membership 16.1%: 労働組合基礎調査 2024 S; 自治会 and circles T); a MOVEMENT
## is never seeded: it is founded by a discontented person who has discontented contacts, grows through contacts, acts (a petition) when
## large and angry enough, and dissolves when small for long. Members feel the group (belonging, contribution, change relief; dues),
## the group reads its members (mean trust, discontent, deficits), and groups relate to one another by their kinds (cooperate, compete,
## oppose: T table). Aggregates per class and per group keep distributions (weighted quantiles), never means only.
const KINDS := ["union", "community", "circle", "association", "party_group", "movement"]
const G_UNION := 0           # the indices of KINDS
const G_COMMUNITY := 1
const G_CIRCLE := 2
const G_ASSOCIATION := 3
const G_PARTY := 4
const G_MOVEMENT := 5
const PURPOSE := [1, 2, 6, 5, 9, 9]   # the drive each kind serves (DRIVES index)
const DUES := [0.15, 0.03, 0.1, 0.1, 0.05, 0.0]   # 万円 a month (T; union dues ~1,500 yen)
const M := 3                           # memberships per person at most
const RELATION := {"union|association": -0.3, "union|party_group": 0.3, "movement|party_group": -0.5, "movement|union": 0.3, "movement|community": 0.1, "circle|community": 0.3, "association|party_group": 0.2}
const PETITION_SHARE := 0.05   # T: a movement acts when its members are 5% of the prefecture's sample
const PETITION_DISCONTENT := 0.5
const PETITION_EVERY := 12     # T: a movement petitions at most once a year (a petition is an act, not a monthly state: V088)
const WAGE_DEMAND_DEFICIT := 0.5
const DISSOLVE_BELOW := 3
const DISSOLVE_MONTHS := 6
const UNION_COVER := 1.3   # T: employees whose workplace has a union, per member (some covered employees do not join)
const START_RATES := {"union": 0.161, "community": 0.30, "circle": 0.20, "association": 0.10, "party_group": 0.01}   # S / T (see header)


static func kind_id(name: String) -> int:
	return KINDS.find(name)


## The classes a person is in (several at once: ISS 4.1)
static func classes(p: RefCounted, i: int) -> Dictionary:
	var a: int = p.age[i]
	return {"age_band": "child" if a < 15 else ("young" if a < 30 else ("middle" if a < 60 else "older")),
		"employment": p.EMPLOYMENT[p.employment[i]],
		"income_tercile": "low" if p.rank[i] < 0.3333 else ("mid" if p.rank[i] < 0.6667 else "high"),
		"education": p.EDUCATION[p.education[i]],
		"prefecture": str(p.pref[i])}


## Start groups per prefecture, members drawn by the published rates (one keyed draw per person and kind)
static func seed_groups(p: RefCounted) -> void:
	for code: Variant in p.pref_codes:
		for kind: int in 5:
			_new_group(p, kind, int(code), -1)
	for i: int in p.n:
		if p.age[i] < 15:
			continue
		draw_cover(p, i, 0)
		for kind: int in 5:
			var rate: float = float(START_RATES[KINDS[kind]])
			if kind == G_UNION:
				# a covered employee is a member with 1 / UNION_COVER, so the start's share is the published rate
				if p.union_cover[i] == 0:
					continue
				rate = 1.0 / UNION_COVER
			if kind == G_COMMUNITY and p.age[i] < 25:
				rate *= 0.3
			if kind == G_CIRCLE:
				rate = 0.1 + 0.3 * p.pref_leisure[i]
			if kind == G_ASSOCIATION and p.education[i] < 2:
				rate *= 0.3
			if kind == G_PARTY:
				rate *= 0.5 + p.pol_interest[i]
			if p.u("groupstart", i, kind) < rate:
				var g: int = find_group(p, kind, p.pref[i])
				if g >= 0:
					join(p, i, g)


## An employee's published membership rate: 16.1% (S: 労働組合基礎調査 2024) for the regular, half for the non-regular (D: パート組合員)
static func union_rate(p: RefCounted, i: int) -> float:
	if p.employment[i] == p.EMP_REGULAR:
		return float(START_RATES["union"])
	return 0.5 * float(START_RATES["union"]) if p.employment[i] == p.EMP_NONREGULAR else 0.0


## Whether the person's workplace has a union, one keyed draw per job (k: the job's draw index). Why not let every employee join: a
## union is a workplace's, and with the union open to all the share rose from 16% to 61% in the first year (audit run)
static func draw_cover(p: RefCounted, i: int, k: int) -> void:
	p.union_cover[i] = 1 if p.u("unioncover", i, k) < UNION_COVER * union_rate(p, i) else 0


## A job ends or a new one starts: the union of the old workplace is left, the new workplace's cover drawn, and a covered hire becomes a
## member with 1 / UNION_COVER as at the start (S-ish: ユニオン・ショップ協定 make membership come with the job in most unionised firms)
static func new_job(p: RefCounted, i: int) -> void:
	for m: int in M:
		var g: int = p.member_of[i * M + m]
		if g >= 0 and int(p.groups[g]["kind"]) == G_UNION:
			leave(p, i, g)
	draw_cover(p, i, p.month + 1)
	if p.union_cover[i] == 1 and memberships(p, i) < M and p.u("unionhire", i, p.month) < 1.0 / UNION_COVER:
		var gu: int = find_group(p, G_UNION, p.pref[i])
		if gu >= 0:
			join(p, i, gu)


static func _new_group(p: RefCounted, kind: int, pref: int, founder: int) -> int:
	var gid: int = p.groups.size()
	p.groups.append({"id": gid, "kind": kind, "pref": pref, "purpose": PURPOSE[kind], "members": 0, "weight": 0.0, "resources": 0.0, "influence": 0.0, "trust_mean": 0.0, "discontent_mean": 0.0, "deficit_mean": 0.0, "founded": p.month, "founder": founder, "status": 0, "small_months": 0, "actions": 0})
	return gid


static func find_group(p: RefCounted, kind: int, pref: int) -> int:
	for g: Dictionary in p.groups:
		if int(g["kind"]) == kind and int(g["pref"]) == pref and int(g["status"]) == 0:
			return int(g["id"])
	return -1


static func is_member(p: RefCounted, i: int, gid: int) -> bool:
	for m: int in M:
		if p.member_of[i * M + m] == gid:
			return true
	return false


static func memberships(p: RefCounted, i: int) -> int:
	var k: int = 0
	for m: int in M:
		if p.member_of[i * M + m] >= 0:
			k += 1
	return k


## The person's workplace union cover cleared (a reborn slot)
static func clear_cover(p: RefCounted, i: int) -> void:
	p.union_cover[i] = 0


static func join(p: RefCounted, i: int, gid: int) -> bool:
	if is_member(p, i, gid):
		return false
	for m: int in M:
		if p.member_of[i * M + m] < 0:
			p.member_of[i * M + m] = gid
			var g: Dictionary = p.groups[gid]
			g["members"] = int(g["members"]) + 1
			g["weight"] = float(g["weight"]) + p.weight[i]
			return true
	return false


static func leave(p: RefCounted, i: int, gid: int) -> void:
	for m: int in M:
		if p.member_of[i * M + m] == gid:
			p.member_of[i * M + m] = -1
			var g: Dictionary = p.groups[gid]
			g["members"] = int(g["members"]) - 1
			g["weight"] = float(g["weight"]) - p.weight[i]


## Each group's weight from its members' weights now, and its influence from that weight and its resources. Why after every rake and not
## only at join and leave: the rake moves the members' weights, and the weight cached at join drifted up to 0.42 from the members' sum
## within a year (V093); why influence here and not in the month's group step: there it was one rake behind the weight (V094)
static func refresh_weights(p: RefCounted) -> void:
	for g: Dictionary in p.groups:
		g["weight"] = 0.0
	for i: int in p.n:
		for m: int in M:
			var gid: int = p.member_of[i * M + m]
			if gid >= 0:
				p.groups[gid]["weight"] = float(p.groups[gid]["weight"]) + p.weight[i]
	for g2: Dictionary in p.groups:
		if int(g2["status"]) == 0:
			g2["influence"] = float(g2["weight"]) / 1e6 * (1.0 + minf(1.0, float(g2["resources"]) / 100.0))


## The group a joiner picks: the kind its situation points to, in its prefecture (T rule)
static func pick_group(p: RefCounted, i: int) -> int:
	var order: Array = []
	var mv: int = find_group(p, G_MOVEMENT, p.pref[i])
	if mv >= 0 and p.emotion(i, "discontent") > 0.4:
		order.append(mv)
	if (p.employment[i] == p.EMP_REGULAR or p.employment[i] == p.EMP_NONREGULAR) and p.union_cover[i] == 1:
		order.append(find_group(p, G_UNION, p.pref[i]))
	if p.pref_social[i] > 0.5:
		order.append(find_group(p, G_CIRCLE, p.pref[i]))
	if p.education[i] == 2:
		order.append(find_group(p, G_ASSOCIATION, p.pref[i]))
	if p.pol_interest[i] > 0.5:
		order.append(find_group(p, G_PARTY, p.pref[i]))
	order.append(find_group(p, G_COMMUNITY, p.pref[i]))
	for g: int in order:
		if g >= 0 and not is_member(p, i, g):
			return g
	return -1


## Discontented contacts of a person (the seed of a movement)
static func discontented_contacts(p: RefCounted, i: int) -> int:
	var k: int = 0
	for c: int in p.REL.C:
		var j: int = p.contact_idx[i * p.REL.C + c]
		if j >= 0 and p.emotion(j, "discontent") > 0.5:
			k += 1
	return k


static func found_movement(p: RefCounted, i: int, counts: Dictionary) -> int:
	if find_group(p, G_MOVEMENT, p.pref[i]) >= 0:
		return -1
	var gid: int = _new_group(p, G_MOVEMENT, p.pref[i], i)
	join(p, i, gid)
	# the discontented contacts come along (the grievance is shared through the contacts, not announced)
	for c: int in p.REL.C:
		var j: int = p.contact_idx[i * p.REL.C + c]
		if j >= 0 and p.emotion(j, "discontent") > 0.5 and memberships(p, j) < M:
			join(p, j, gid)
	p.count_kind(counts, "movement_founded", i, float(p.groups[gid]["members"]), "a discontented person with discontented contacts (T: change deficit and 2+ such contacts)")
	p.group_log.append({"month": p.month, "group": gid, "kind": "founded", "pref": p.pref[i], "members": int(p.groups[gid]["members"]), "why": "founder's discontent %.2f, %d discontented contacts" % [p.emotion(i, "discontent"), discontented_contacts(p, i)]})
	return gid


## The month of the groups: dues, meetings (trust between member contacts), the group's reading of its members, its actions, dissolution
static func step(p: RefCounted, counts: Dictionary) -> void:
	var sum_t: PackedFloat64Array = PackedFloat64Array()
	var sum_d: PackedFloat64Array = PackedFloat64Array()
	var sum_def: PackedFloat64Array = PackedFloat64Array()
	var cnt: PackedInt32Array = PackedInt32Array()
	var G: int = p.groups.size()
	sum_t.resize(G)
	sum_d.resize(G)
	sum_def.resize(G)
	cnt.resize(G)
	var pref_n: Dictionary = {}
	for i: int in p.n:
		pref_n[p.pref[i]] = int(pref_n.get(p.pref[i], 0)) + 1
		for m: int in M:
			var gid: int = p.member_of[i * M + m]
			if gid < 0:
				continue
			var g: Dictionary = p.groups[gid]
			var kind: int = int(g["kind"])
			var due: float = DUES[kind]
			if p.assets[i] >= due:
				p.add_assets(i, -due)
				g["resources"] = float(g["resources"]) + due
			sum_t[gid] += p.trait_of(i, "trust_in_others")
			sum_d[gid] += p.emotion(i, "discontent")
			sum_def[gid] += p.dd[i * 10 + int(g["purpose"])]
			cnt[gid] += 1
			# meetings: contacts in the same group grow trust (+1 a month, T)
			for c: int in p.REL.C:
				var j: int = p.contact_idx[i * p.REL.C + c]
				if j >= 0 and is_member(p, j, gid):
					p.REL.raise_trust(p, i, c, 1.0)
	for g: Dictionary in p.groups:
		if int(g["status"]) != 0:
			continue
		var gid: int = int(g["id"])
		var n: int = cnt[gid]
		g["trust_mean"] = sum_t[gid] / n if n > 0 else 0.0
		g["discontent_mean"] = sum_d[gid] / n if n > 0 else 0.0
		g["deficit_mean"] = sum_def[gid] / n if n > 0 else 0.0
		var kind: int = int(g["kind"])
		var share: float = float(n) / maxf(1.0, float(pref_n.get(int(g["pref"]), 1)))
		# group actions: a petition by a large, angry movement; a wage demand by a union whose members are pressed (recorded for Phase 6)
		if kind == G_MOVEMENT and share >= PETITION_SHARE and float(g["discontent_mean"]) >= PETITION_DISCONTENT and p.month - int(g.get("last_petition", -PETITION_EVERY)) >= PETITION_EVERY:
			g["last_petition"] = p.month
			g["actions"] = int(g["actions"]) + 1
			p.group_log.append({"month": p.month, "group": gid, "kind": "petition", "pref": int(g["pref"]), "members": n, "why": "members %.1f%% of the prefecture's sample, discontent %.2f (T thresholds 5%%, 0.5)" % [100.0 * share, float(g["discontent_mean"])]})
			p.count_kind(counts, "petition", 0, float(n), "a movement above the size and discontent lines (T)")
		if kind == G_UNION and n > 0 and float(g["deficit_mean"]) >= WAGE_DEMAND_DEFICIT:
			g["actions"] = int(g["actions"]) + 1
			p.group_log.append({"month": p.month, "group": gid, "kind": "wage_demand", "pref": int(g["pref"]), "members": n, "why": "members' economic-security deficit %.2f (T line 0.5)" % float(g["deficit_mean"])})
			p.count_kind(counts, "wage_demand", 0, float(n), "a union whose members are pressed (T)")
		# a movement dissolves when small for long
		if kind == G_MOVEMENT:
			g["small_months"] = int(g["small_months"]) + 1 if n < DISSOLVE_BELOW else 0
			if int(g["small_months"]) >= DISSOLVE_MONTHS:
				g["status"] = 1
				for i: int in p.n:
					if is_member(p, i, gid):
						leave(p, i, gid)
				p.group_log.append({"month": p.month, "group": gid, "kind": "dissolved", "pref": int(g["pref"]), "members": n, "why": "fewer than %d members for %d months" % [DISSOLVE_BELOW, DISSOLVE_MONTHS]})
	# members converge a little toward their group's discontent (the group influences the individual, κ 0.05 T)
	if not p.group_influence:
		return
	for i: int in p.n:
		for m: int in M:
			var gid: int = p.member_of[i * M + m]
			if gid >= 0 and int(p.groups[gid]["kind"]) == G_MOVEMENT:
				var k: int = i * p.NE + p.EMOTIONS.find("discontent")
				p.pull_emotion(k, float(p.groups[gid]["discontent_mean"]), 0.05)


static func relation(kind_a: int, kind_b: int) -> float:
	if kind_a == kind_b:
		return 0.5
	var k1: String = KINDS[mini(kind_a, kind_b)] + "|" + KINDS[maxi(kind_a, kind_b)]
	var k2: String = KINDS[maxi(kind_a, kind_b)] + "|" + KINDS[mini(kind_a, kind_b)]
	return float(RELATION.get(k1, RELATION.get(k2, 0.0)))


## Weighted quantiles of a value by class (the aggregate that keeps the distribution, ISS 4.5)
static func summary_by_class(p: RefCounted, class_key: String, values: PackedFloat64Array) -> Dictionary:
	var by: Dictionary = {}
	for i: int in p.n:
		var c: String = String(classes(p, i)[class_key])
		if not by.has(c):
			by[c] = []
		by[c].append(i)
	var out: Dictionary = {}
	var ks: Array = by.keys()
	ks.sort()
	for c: String in ks:
		var w: float = 0.0
		for i: int in by[c]:
			w += p.weight[i]
		out[c] = {"persons": (by[c] as Array).size(), "weight": w, "p10_p50_p90": p.quantiles(values, by[c])}
	return out


static func group_summary(p: RefCounted) -> Array:
	var out: Array = []
	for g: Dictionary in p.groups:
		if int(g["status"]) == 0 and int(g["members"]) > 0:
			out.append({"id": int(g["id"]), "kind": KINDS[int(g["kind"])], "pref": int(g["pref"]), "members": int(g["members"]), "weight": float(g["weight"]), "resources": float(g["resources"]), "discontent_mean": float(g["discontent_mean"]), "actions": int(g["actions"])})
	return out
