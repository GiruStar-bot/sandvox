extends RefCounted
## Relations, interaction and information between the representative persons (ISS Phase 3; survey 1.2, 1.5, 3.3). Each person holds at
## most C contacts (family, friend, colleague, neighbour), drawn from its own prefecture's sample; a mover keeps its kin and about half
## of the rest (people.move_to), and with households on its household's members are its family; trust 0..100 (household_layer.gd's
## scale and starts: family 80, friend 50, colleague 40, neighbour 30) and a last-seen month; trust decays -2 a month after six months
## unseen and a contact below 5 is forgotten (household_layer.gd :798), except kin, who stay at 5. Interaction: the socialize action picks one partner by trust (one
## keyed draw) and both move (loneliness, belonging, joy, trust +3); a person short of money asks its most trusted contact for help, who
## gives by cooperativeness x trust or refuses (asked when the economic-security deficit is above 0.6, T) (trust +3 / -4, household_layer.gd :1263); support_family reaches a family contact.
## Information: a catalogue of public facts (the food price's yearly change, the unemployment rate) that a person knows only through a
## channel: the register (read with probability = political interest, the published value carries the publication error), a contact
## (last month's belief of the contact, weighted by kin credibility 0.8 or rumour 0.3 x trust, with transmission noise), or own experience.
## What a person feels about prices is read from its BELIEF, not from the true value: the same event reaches people late, wrong or not at all.
const C := 12
const KINDS := ["family", "friend", "colleague", "neighbour"]
const K_FAMILY := 0          # the indices of KINDS
const K_FRIEND := 1
const K_COLLEAGUE := 2
const K_NEIGHBOUR := 3
const TRUST0 := [80.0, 50.0, 40.0, 30.0]
const FACTS := ["food_price_yoy", "unemployment_rate"]
const NF := 2
const CRED_KIN := 0.8      # migration_ties.gd CRED_KIN
const CRED_RUMOUR := 0.3   # migration_ties.gd CRED_RUMOR
## The register's error per fact, in the fact's own units (M002 G3): the food price's yearly change at the CPI's published rounding
## (0.1 pt, S), the unemployment rate at the labour force survey's order of sampling error (0.1 pt, T until its 標準誤差 is sourced)
## Why not one +-1 pt for both: it is 40% of a 2.5% unemployment rate, and with one draw for every reader it moved them all together
const PUBLISH_ERR_BY_FACT := [0.0005, 0.001]
const RUMOUR_NOISE := 0.02 # T: noise added at each hand-over
const HELP_SUM := 5.0      # 万円 (T)
const DECAY_AFTER := 6
const FORGET_BELOW := 5.0


## Contacts at the start: each kind filled up to the person's targets, counting the links it already holds (a link made by someone
## earlier counts on both sides), partners found in the same prefecture by keyed draws (bounded tries), links symmetric. Why the links
## already held count: the build added every want on top of them, so each adult began near twice its targets (about 10 contacts) while
## the yearly renewal, which counts them, settled at the targets (about 6): the network thinned for ten years (V089)
static func build(p: RefCounted) -> void:
	var by: Dictionary = {}
	for i: int in p.n:
		if not by.has(p.pref[i]):
			by[p.pref[i]] = []
		by[p.pref[i]].append(i)
	for i: int in p.n:
		var pool: Array = by[p.pref[i]]
		var want: PackedInt32Array = targets(p, i)
		var have := PackedInt32Array([0, 0, 0, 0])
		for c: int in C:
			if p.contact_idx[i * C + c] >= 0:
				have[p.contact_kind[i * C + c]] += 1
		var tries: int = 0
		for kind: int in 4:
			while have[kind] < want[kind] and tries < 40:
				var found: int = -1
				while tries < 40 and found < 0:
					var j: int = pool[KEYED_below(p, pool.size(), "contact", i, tries)]
					tries += 1
					if j == i or has_contact(p, i, j) or p.contact_count(j) >= C:
						continue
					# a friend is near in age, a colleague employed; family any age (a parent or child)
					if kind == K_FRIEND and absi(p.age[j] - p.age[i]) > 8:
						continue
					if kind == K_COLLEAGUE and not (p.employment[j] == p.EMP_REGULAR or p.employment[j] == p.EMP_NONREGULAR):
						continue
					found = j
				if found < 0:
					break
				if add(p, i, found, kind):
					# symmetric or not at all: the reverse link only when the forward one fit
					if add(p, found, i, kind):
						have[kind] += 1
					else:
						p.contact_idx[i * C + slot(p, i, found)] = -1
				else:
					break


## The contacts a person wants of each kind (build's targets): family 1 or 2, friends 1 + 3 x sociability, 2 colleagues when employed,
## one neighbour
static func targets(p: RefCounted, i: int) -> PackedInt32Array:
	var t := PackedInt32Array([2 if p.hh_kind[i] >= p.HK_COUPLE else 1, 1 + int(3.0 * p.pref_social[i] + 0.5), 2 if (p.employment[i] == p.EMP_REGULAR or p.employment[i] == p.EMP_NONREGULAR) else 0, 1])
	return t


## The person's yearly renewal: kinds below their target are refilled from the prefecture's pool (colleagues at a new job, a neighbour
## after a move, friends met), at most ten keyed tries. Why not leave the start's network alone: unseen contacts decay and are
## forgotten, and with no new ones the share without a contact outside the household rose from 0% to 43% in seven years (audit run).
## Family is not refilled: kin are not made by meeting
static func replenish(p: RefCounted, i: int, pool: Array) -> void:
	if p.age[i] < 15 or pool.size() < 2:
		return
	var have := PackedInt32Array([0, 0, 0, 0])
	for c: int in C:
		if p.contact_idx[i * C + c] >= 0:
			have[p.contact_kind[i * C + c]] += 1
	var want: PackedInt32Array = targets(p, i)
	var tries: int = 0
	for kind: int in [K_FRIEND, K_COLLEAGUE, K_NEIGHBOUR]:
		while have[kind] < want[kind] and tries < 10 and p.contact_count(i) < C:
			var j: int = pool[p.KEYED.below(pool.size(), p.seed_v, "replenish", int(p.pid[i] & 0x7FFFFFFFFFFF), p.month * 16 + tries, 0)]
			tries += 1
			if j == i or has_contact(p, i, j) or p.contact_count(j) >= C or p.age[j] < 15:
				continue
			if kind == K_FRIEND and absi(p.age[j] - p.age[i]) > 8:
				continue
			if kind == K_COLLEAGUE and not (p.employment[j] == p.EMP_REGULAR or p.employment[j] == p.EMP_NONREGULAR):
				continue
			if add(p, i, j, kind):
				if add(p, j, i, kind):
					have[kind] += 1
				else:
					p.contact_idx[i * C + slot(p, i, j)] = -1


static func KEYED_below(p: RefCounted, n: int, tag: String, i: int, t: int) -> int:
	return p.KEYED.below(n, p.seed_v, tag, int(p.pid[i] & 0x7FFFFFFFFFFF), t, 0)


static func has_contact(p: RefCounted, i: int, j: int) -> bool:
	for c: int in C:
		if p.contact_idx[i * C + c] == j:
			return true
	return false


static func add(p: RefCounted, i: int, j: int, kind: int) -> bool:
	for c: int in C:
		if p.contact_idx[i * C + c] < 0:
			p.contact_idx[i * C + c] = j
			p.contact_kind[i * C + c] = kind
			p.contact_trust[i * C + c] = TRUST0[kind]
			p.contact_last[i * C + c] = p.month
			return true
	return false


## A slot's trust raised by amount, capped at 100 (a group meeting's +1); why not trust_move: that one also marks the contact seen
static func raise_trust(p: RefCounted, i: int, c: int, amount: float) -> void:
	p.contact_trust[i * C + c] = minf(100.0, p.contact_trust[i * C + c] + amount)


## i's link to j removed (one side), as when the reverse link did not fit
static func unlink(p: RefCounted, i: int, j: int) -> void:
	var c: int = slot(p, i, j)
	if c >= 0:
		p.contact_idx[i * C + c] = -1


## i's slot c removed on both sides (a mover's contact left behind)
static func unlink_slot(p: RefCounted, i: int, c: int) -> void:
	var j: int = p.contact_idx[i * C + c]
	var back: int = slot(p, j, i)
	if back >= 0:
		p.contact_idx[j * C + back] = -1
	p.contact_idx[i * C + c] = -1


## The month's "met someone" mark cleared at the month's end
static func clear_met(p: RefCounted, i: int) -> void:
	p.met[i] = 0


## Every fact the person knew forgotten (a reborn slot)
static func forget(p: RefCounted, i: int) -> void:
	for f: int in NF:
		p.belief_known[i * NF + f] = 0


## Every link of i removed on both sides (a death)
static func drop_all(p: RefCounted, i: int) -> void:
	for c: int in C:
		var j: int = p.contact_idx[i * C + c]
		if j >= 0:
			var back: int = slot(p, j, i)
			if back >= 0:
				p.contact_idx[j * C + back] = -1
		p.contact_idx[i * C + c] = -1


static func slot(p: RefCounted, i: int, j: int) -> int:
	for c: int in C:
		if p.contact_idx[i * C + c] == j:
			return c
	return -1


static func trust_move(p: RefCounted, i: int, j: int, amount: float) -> void:
	var c: int = slot(p, i, j)
	if c >= 0:
		p.contact_trust[i * C + c] = clampf(p.contact_trust[i * C + c] + amount, 0.0, 100.0)
		p.contact_last[i * C + c] = p.month


## One partner by trust (talk.gd: listener weighted by trust), one keyed draw; -1 without contacts
static func pick_partner(p: RefCounted, i: int, tag: String) -> int:
	var tot: float = 0.0
	for c: int in C:
		if p.contact_idx[i * C + c] >= 0:
			tot += p.contact_trust[i * C + c] + 1.0
	if tot <= 0.0:
		return -1
	var x: float = p.u(tag, i, p.month) * tot
	var acc: float = 0.0
	for c: int in C:
		if p.contact_idx[i * C + c] >= 0:
			acc += p.contact_trust[i * C + c] + 1.0
			if x < acc:
				return p.contact_idx[i * C + c]
	return -1


static func most_trusted(p: RefCounted, i: int, kind: int = -1) -> int:
	var best: int = -1
	var bt: float = -1.0
	for c: int in C:
		var j: int = p.contact_idx[i * C + c]
		if j >= 0 and (kind < 0 or p.contact_kind[i * C + c] == kind) and p.contact_trust[i * C + c] > bt:
			bt = p.contact_trust[i * C + c]
			best = j
	return best


## The month's interactions: socialising partners, family support, asking for help; then the decay of unseen contacts
static func interact(p: RefCounted, counts: Dictionary) -> void:
	for i: int in p.n:
		if p.flags[i] & p.F_SOCIALISED:
			var j: int = pick_partner(p, i, "partner")
			if j >= 0:
				p.move_emotion(i, "loneliness", -0.12 * p.pref_social[i], "met_contact", "sociability", counts)
				p.move_emotion(j, "loneliness", -0.08 * p.pref_social[j], "met_contact", "sociability", counts)
				p.move_emotion(i, "joy", 0.06, "met_contact", "", counts)
				p.move_emotion(j, "joy", 0.04, "met_contact", "", counts)
				trust_move(p, i, j, 3.0)
				trust_move(p, j, i, 3.0)
				p.met[i] = 1
				p.met[j] = 1
		if p.flags[i] & p.F_SUPPORTED:
			var f: int = most_trusted(p, i, 0)
			if f >= 0:
				p.add_assets(f, p.ACT.SUPPORT_COST)
				trust_move(p, f, i, 5.0)
				p.move_emotion(f, "trust", 0.03, "supported_by_family", "", counts)
		# asking for help: short of money and no income cover; the most trusted contact decides by cooperativeness x trust
		if p.dd[i * p.ND + p.D_SECURITY] > 0.6 and p.age[i] >= 18:
			var h: int = most_trusted(p, i)
			if h >= 0:
				var c: int = slot(p, h, i)
				var tr: float = p.contact_trust[h * C + c] / 100.0 if c >= 0 else 0.3
				var gives: bool = p.assets[h] >= HELP_SUM and p.u("help", h, p.month) < p.trait_of(h, "cooperativeness") * tr
				if gives:
					p.add_assets(h, -HELP_SUM)
					p.add_assets(i, HELP_SUM)
					trust_move(p, i, h, 3.0)
					p.move_emotion(i, "relief", 0.2, "helped_by_contact", "", counts)
					p.move_emotion(i, "trust", 0.05, "helped_by_contact", "", counts)
					p.count_kind(counts, "help_given", h, HELP_SUM, "cooperativeness x trust (T)")
				else:
					trust_move(p, i, h, -4.0)
					p.move_emotion(i, "sadness", 0.05, "refused_by_contact", "", counts)
					p.count_kind(counts, "help_refused", h, 0.0, "assets or cooperativeness x trust below the draw (T)")
	# decay and forgetting
	for i: int in p.n:
		for c: int in C:
			var j: int = p.contact_idx[i * C + c]
			if j < 0:
				continue
			if p.month - p.contact_last[i * C + c] > DECAY_AFTER:
				p.contact_trust[i * C + c] -= 2.0
			# Why kin are not forgotten: they are never refilled (kin are not made by meeting), and forgetting them unseen took family
			# from 2.2 to 1.2 per adult in ten years (V089); unseen kin only lose trust, down to the forgetting line
			if p.contact_kind[i * C + c] == K_FAMILY:
				p.contact_trust[i * C + c] = maxf(p.contact_trust[i * C + c], FORGET_BELOW)
				continue
			if p.contact_trust[i * C + c] < FORGET_BELOW:
				# Why both sides: a link is symmetric or not at all (build); one-sided forgetting left the other side holding a ghost
				p.contact_idx[i * C + c] = -1
				var back: int = slot(p, j, i)
				if back >= 0:
					p.contact_idx[j * C + back] = -1


## What people come to believe this month: readers take the register's figure (with its error), the rest hear last month's beliefs of
## their contacts (weighted by credibility x trust, with noise), the unemployed know unemployment from their own case
static func learn(p: RefCounted, truth: Dictionary, counts: Dictionary) -> void:
	var prev := PackedFloat64Array(p.belief)
	var prev_known := PackedInt32Array(p.belief_known)
	var readers: int = 0
	var heard: int = 0
	for i: int in p.n:
		if p.age[i] < 15:
			continue
		var reads: bool = p.u("reads", i, p.month) < p.pol_interest[i]
		for f: int in NF:
			var k: int = i * NF + f
			var tv: float = float(truth.get(FACTS[f], 0.0))
			if reads:
				# the register's figure: the true value with the publication's fixed error (modern_publish: estimate error by hash)
				var err: float = float(PUBLISH_ERR_BY_FACT[f]) * (2.0 * p.KEYED.u(p.seed_v, "puberr", f, p.month, 0) - 1.0)
				p.belief[k] = tv + err
				p.belief_known[k] = 1
				p.belief_source[k] = 0
				p.belief_month[k] = p.month
				if f == 0:
					readers += 1
			elif p.contact_news:
				# contacts: last month's beliefs, those who knew
				var acc: float = 0.0
				var wsum: float = 0.0
				for c: int in C:
					var j: int = p.contact_idx[i * C + c]
					if j < 0 or prev_known[j * NF + f] == 0:
						continue
					var cred: float = CRED_KIN if p.contact_kind[i * C + c] == K_FAMILY else CRED_RUMOUR
					var w: float = cred * p.contact_trust[i * C + c] / 100.0
					acc += w * (prev[j * NF + f] + RUMOUR_NOISE * p.normal("rumour", i, p.month, c))
					wsum += w
				if wsum > 0.0:
					var told: float = acc / wsum
					var cw: float = minf(1.0, wsum)
					p.belief[k] = told if p.belief_known[k] == 0 else (1.0 - cw) * p.belief[k] + cw * told
					p.belief_known[k] = 1
					p.belief_source[k] = 1
					p.belief_month[k] = p.month
					if f == 0:
						heard += 1
			if f == 1 and p.employment[i] == p.EMP_UNEMPLOYED:
				# own experience: the unemployed read the labour market from their own case (T: +0.05 over what they believe)
				p.belief[k] = maxf(p.belief[k], tv) + 0.05
				p.belief_known[k] = 1
				p.belief_source[k] = 2
				p.belief_month[k] = p.month
	if readers > 0:
		p.count_kind(counts, "read_register", 0, float(readers), "political interest x one keyed draw")
	if heard > 0:
		p.count_kind(counts, "heard_from_contacts", 0, float(heard), "credibility kin 0.8 / rumour 0.3 x trust, with noise")


## The share of a person's contacts whose last action was a given one (conformity, choice.gd with_conformity)
static func contact_action_share(p: RefCounted, i: int, action: int) -> float:
	var n: int = 0
	var m: int = 0
	for c: int in C:
		var j: int = p.contact_idx[i * C + c]
		if j >= 0:
			n += 1
			if p.last_action[j] == action:
				m += 1
	return float(m) / float(n) if n > 0 else 0.0
