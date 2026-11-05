extends "res://tools/test/test_kit.gd"
## The code review of sim/modern (pm-notes TO_E 2026-10-29 19:40): each fixed item read over months, not only at the start.
##   godot --headless --path . --script res://sim/modern/test_modern_review.gd
## R1a a job changer's own pay survives its yearly turn: after 13 more months, every person still in the changed job (factor at least
##     3% from 1) is paid nearer the table times its factor than the table (the skill, moved by the year and by training, moves the table
##     a little after the pay is set, so equality is not the reading)
## R1b a move moves the household: over 24 months (households on), every person's prefecture is its household's and partners stay
##     in one household; on and off, no one
##     is a member of a group of another prefecture; movers happened. With households on, ten adults of 13 are also moved to 47 at
##     month 12 through move_to with a job reason: since §10.6 A5 a move needs a reason, and the 2 x 200 society chose none in 24 months
##     (the move path must still be exercised; how often people move is HB12's)
## R1c a newborn takes its household's kind: over 24 months (households on), every person's kind is its household's type (an
##     institution resident's is single), newborns included
## R2a the seeded shocks are keyed by tag, not String.hash(): the seeded economy (seed 7, 36 months) repeats and gives the recorded
##     digest (b1620d1c since R96e's fixes; 1e94d71f since the start's own-flow rule; 7c3f2137 since the D477 purge, 711a98df / 276929d7; b9318555 since the M002 batch G8; 20d3c424 before, the keyed tags since the review fix 2a), and seed 8 differs
const EM = preload("res://sim/modern/econ/econ_month.gd")
const SEEDED_7 := "7f417216b5a5c0cda9449e9a187e33504978332bf6ad2591303eef80c3b75195"
## R2b the household rake's arithmetic is DetMath's: a households-on society (seed 7, 2 x 200, 12 months) gives the recorded digest
##     (005e307d since R96e's fixes (the 2023-10-01 denominators); c68e21c2 since the D477 purge, 711a98df / 276929d7; 9dc03f7d since the T2.2b/c households-on move; 0ab70464: since M011's v2; f2428a8a since M010's pooled inputs; 5eec6b3b since §14.4a's deaths by health x income (R73, R74); 542a6305 before, 05c81404 since §10.9's intended children by the
##     wife's age; before 11e79d51 (§10.8's C3), 4447bf64 (§10.7's
##     B1-B3, B5), cee725bc (§10.6's A1-A5), 399a9442 (V098's A3-1, A3-2, divorce as a choice, the start's size draw)) and repeats
const HH_12 := "30fc0e0c33ecc59fcc8369776bab6cd78bf9be23978f0c97d1b4999d8fab1e38"
## R2c every saved array is in the digest: after 6 months, a change to any one of the twenty arrays the review found outside it moves
##     the digest, and undoing it restores the digest
const ADDED := ["weight", "hh_size", "k_in_pref", "basket", "emo_base", "pref_leisure", "pref_social", "pol_interest", "dream_blocked", "mem_head", "mem_kind", "mem_month", "met", "pressure_prev", "contact_kind", "contact_last", "belief_source", "belief_month", "cohort", "qx"]
## R2d the silent fallbacks are loud: a missing commodities file stops the persons' spec, a missing shocks file is the economy's
##     error, and over months a person of a prefecture without a population is the rake's error
## R1e the mover's contacts (review 1b's rule, read by behaviour, not a digest): after 12 months, every adult of one prefecture is moved
##     to the other; every kin contact and every contact already at the destination is kept; of the other contacts 0.35-0.65 are kept
##     (MOVE_KEEP 0.5, at least 100 of them); every dropped link is gone on both sides
const PEOPLE = preload("res://sim/modern/people/people.gd")
const MS = preload("res://sim/modern/modern_status.gd")
const ENV := {"inflation_month": 0.02 / 12.0, "food_price_yoy": 0.0, "unemployment_rate": 0.025, "levers": []}
const TWO := {"13": {"pop_thousand": 14178}, "47": {"pop_thousand": 1467}}


func _society(st, households: bool = false) -> Object:
	var p = PEOPLE.new()
	p.households = households
	p.create("JPN", 7, st.cohort["JPN"], st.qx["JPN"], TWO, 200)
	return p


func _init() -> void:
	var st = MS.new()
	st.load(2024, ["JPN"])
	var p = _society(st)
	for m: int in 12:
		p.step(ENV)
	var changers: Dictionary = {}
	for i: int in p.n:
		if (p.employment[i] == 1 or p.employment[i] == 2) and p.pay_factor[i] != 1.0:
			changers[p.pid[i]] = [p.pay_factor[i], p.age[i]]
	for m2: int in 13:
		p.step(ENV)
	var kept: int = 0
	var turned: int = 0
	var bad: String = ""
	for i2: int in p.n:
		if not changers.has(p.pid[i2]) or not (p.employment[i2] == 1 or p.employment[i2] == 2) or p.pay_factor[i2] != float(changers[p.pid[i2]][0]) or absf(p.pay_factor[i2] - 1.0) < 0.03:
			continue
		if p.age[i2] > int(changers[p.pid[i2]][1]):
			turned += 1
		var f: float = p.pay_factor[i2]
		p.pay_factor[i2] = 1.0
		var table: float = p.wage(i2)
		p.pay_factor[i2] = f
		var r: float = p.income[i2] / table
		if absf(r / f - 1.0) < absf(r - 1.0):
			kept += 1
		elif bad == "":
			bad = " first not kept: pid %d income %.3f table %.3f factor %.4f" % [p.pid[i2], p.income[i2], table, f]
	check(turned > 0 and bad == "", "R1a job changers' own pay kept through the yearly turn: %d changers at month 12; of those still in that job after 13 months, %d past their turn, %d paid nearer table x factor than the table%s" % [changers.size(), turned, kept, bad])
	for hh: bool in [true, false]:
		var q = _society(st, hh)
		var moves: int = 0
		var half: int = 0
		var foreign: int = 0
		for m3: int in 24:
			q.step(ENV)
			if hh and m3 == 11:
				var forced: int = 0
				for i7: int in q.n:
					if forced < 10 and q.pref[i7] == 13 and q.age[i7] >= 18 and q.hh_type[q.hh_id[i7]] != q.LC.INSTITUTION:
						q.move_to(i7, 47, "job")
						forced += 1
						moves += 1
			for i3: int in q.n:
				if q.last_action[i3] == q.ACT.A_MOVE:
					moves += 1
				if hh and (q.pref[i3] != q.hh_pref[q.hh_id[i3]] or (q.partner[i3] >= 0 and q.hh_id[q.partner[i3]] != q.hh_id[i3])):
					half += 1
				for g: int in q.GRP.M:
					var gid: int = q.member_of[i3 * q.GRP.M + g]
					if gid >= 0 and int(q.groups[gid]["pref"]) != q.pref[i3]:
						foreign += 1
		check(moves > 0 and half == 0 and foreign == 0, "R1b households %s: %d moves in 24 months; person-months in another prefecture than their household or apart from their partner %d; memberships in another prefecture's group %d" % [str(hh), moves, half, foreign])
	var r = _society(st, true)
	var wrong: int = 0
	var newborns: int = 0
	for m4: int in 24:
		r.step(ENV)
		for i4: int in r.n:
			var t: int = r.hh_type[r.hh_id[i4]]
			if r.hh_kind[i4] != (0 if t == r.LC.INSTITUTION else t):
				wrong += 1
			if r.age[i4] == 0:
				newborns += 1
	check(newborns > 0 and wrong == 0, "R1c household kinds: %d person-months of age 0 seen; persons whose kind is not their household's %d" % [newborns, wrong])
	var dg: Array = []
	for sd: int in [7, 7, 8]:
		var e = EM.new()
		e.create("JPN")
		e.seed_shocks(sd, 4)
		for m5: int in 36:
			e.step()
		dg.append(e.digest())
	check(dg[0] == SEEDED_7 and dg[1] == dg[0] and dg[2] != dg[0], "R2a seeded shocks: seed 7 %s (recorded %s), repeats %s, seed 8 differs %s" % [String(dg[0]).left(8), SEEDED_7.left(8), str(dg[1] == dg[0]), str(dg[2] != dg[0])])
	var hd: Array = []
	for k6: int in 2:
		var h = _society(st, true)
		for m6: int in 12:
			h.step(ENV)
		hd.append(h.digest())
	check(hd[0] == HH_12 and hd[1] == hd[0], "R2b households-on 12 months: %s (recorded %s), repeats %s" % [String(hd[0]).left(8), HH_12.left(8), str(hd[1] == hd[0])])
	var c7 = _society(st)
	for m7: int in 6:
		c7.step(ENV)
	var d0: String = c7.digest()
	var silent: Array = []
	for f7: String in ADDED:
		var arr = c7.get(f7)
		var old = arr[0]
		arr[0] = old + 1
		var moved: bool = c7.digest() != d0
		arr[0] = old
		if not moved or c7.digest() != d0:
			silent.append(f7)
	check(silent.is_empty(), "R2c the digest reads every saved array: %d checked, not read %s" % [ADDED.size(), str(silent)])
	var p8 = PEOPLE.new()
	var e8: String = p8.load_spec("JPN", "res://data/modern/econ/no_such_commodities.json")
	var em8 = EM.new()
	em8.create("JPN")
	em8.seed_shocks(7, 1, "res://data/modern/econ/no_such_shocks.json")
	var r8 = _society(st)
	for m8: int in 3:
		r8.step(ENV)
	var clean: bool = r8.error == ""
	r8.pref[0] = 99
	r8.step(ENV)
	check(e8 != "" and em8.error != "" and clean and r8.error.contains("99"), "R2d loud fallbacks: commodities '%s'; shocks '%s'; three clean months %s, then '%s'" % [e8, em8.error, str(clean), r8.error])
	var mv = _society(st)
	for m9: int in 12:
		mv.step(ENV)
	var kin_lost: int = 0
	var dest_lost: int = 0
	var other_n: int = 0
	var other_kept: int = 0
	var one_sided: int = 0
	for i9: int in mv.n:
		if mv.pref[i9] != 13 or mv.age[i9] < 18:
			continue
		var before: Array = []
		for c9: int in mv.REL.C:
			var j9: int = mv.contact_idx[i9 * mv.REL.C + c9]
			if j9 >= 0:
				before.append([j9, mv.contact_kind[i9 * mv.REL.C + c9], mv.pref[j9]])
		mv.move_to(i9, 47)
		for b: Array in before:
			var still: bool = mv.REL.has_contact(mv, i9, int(b[0]))
			if int(b[1]) == mv.REL.K_FAMILY:
				kin_lost += 0 if still else 1
			elif int(b[2]) == 47:
				dest_lost += 0 if still else 1
			else:
				other_n += 1
				other_kept += 1 if still else 0
				if not still and mv.REL.has_contact(mv, int(b[0]), i9):
					one_sided += 1
	var share: float = float(other_kept) / maxf(1.0, float(other_n))
	check(kin_lost == 0 and dest_lost == 0 and other_n >= 100 and share >= 0.35 and share <= 0.65 and one_sided == 0, "R1e movers' contacts: kin lost %d, destination contacts lost %d, other contacts kept %d of %d (%.2f), one-sided links left %d" % [kin_lost, dest_lost, other_kept, other_n, share, one_sided])
	finish()
