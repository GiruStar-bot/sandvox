extends "res://tools/test/test_kit.gd"
## ISS tiered population T2.1 at month 0 (ISS_TIERED_POPULATION.md §14.2c; ISS_CHECKS.md T2s-m, T2s-cp, T2s-r70, T2s-ms), declared
## before its code (f7762c98, 57c1d540; amended for §12.12 f8834ff5, 145c7549, a1173165). The national start, seed 1.
##   godot --headless --path . --script res://sim/modern/test_modern_t2_start.gd
## T2s-m (month 0, by age) Σ over a unit's points of each age's mass = the unit's age count; Σ over a point's ages = its mass; no mass < 0;
##        every (point, age) mass's 12 birth months (birth_months()) sum to it, none < 0
## (3)    Σ over a unit's points of a household-bundle role's mass = the bundle's member count; Σ over a point's entries <= its mass; the
##        persons in no household-bundle reported
## T2s-cp (month 0) every point's couple marginal plus its counted extra (cross-tier wives, partnerless heads) = its partner-role mass,
##        and in the couple types its head-role mass too; in "other" a head's marginal is at most its mass (the heads in no couple)
## T2s-r70 (month 0) on a keyed sample of 200 couple blocks: every 2 x 2 cross-product ratio of the IPF table equals the seed's within
##        1e-9 relative (before the integer step); the wives' employment rate by the husband's class against R70's, reported
## T2s-ms (month 0) every point's four marital states sum to its mass; married wives in couples = married husbands in couples + the
##        cross-tier wives - the partnerless heads; the states against R76 and T1's never married reported
const PEOPLE = preload("res://sim/modern/people/people.gd")
const TR = preload("res://sim/modern/people/tiers.gd")
const MS = preload("res://sim/modern/modern_status.gd")
const CANON = preload("res://sim/modern/canon.gd")
const KEYED = preload("res://sim/earth_core/keyed.gd")


func _init() -> void:
	var st = MS.new()
	st.load(2024, ["JPN"])
	var prefs: Dictionary = CANON.load_json("res://data/modern/polity/jpn_prefectures.json")["prefectures"]
	var t0: int = Time.get_ticks_msec()
	var p = PEOPLE.new()
	p.tiers = true
	p.create("JPN", 1, st.cohort["JPN"], st.qx["JPN"], prefs, 0, 2024)
	check(p.error == "", "tiers built with T2.1: '%s' (%d units, %d points, %d couple points, %d ms)" % [p.error, p.tr_units, p.tr_pt_off[p.tr_units], p.tr_cp_n.size(), Time.get_ticks_msec() - t0])
	_ages(p)
	_roles(p)
	_couples(p)
	_r70(p)
	_ms(p)
	finish()


func _ages(p: RefCounted) -> void:
	var bad_u: int = 0
	var bad_pt: int = 0
	var neg: int = 0
	for u: int in p.tr_units:
		var by := PackedInt64Array()
		by.resize(TR.AGE_SLOTS)
		for j: int in range(p.tr_pt_off[u], p.tr_pt_off[u + 1]):
			var s: int = 0
			for a: int in TR.AGE_SLOTS:
				var m: int = p.tr_pt_age[j * TR.AGE_SLOTS + a]
				neg += 1 if m < 0 else 0
				by[a] += m
				s += m
			bad_pt += 0 if s == p.tr_pt_mass[j] else 1
		for a2: int in TR.AGE_SLOTS:
			if by[a2] != p.tr_age_counts[u * TR.AGE_SLOTS + a2]:
				bad_u += 1
				break
	var bm_bad: int = 0
	var bm_n: int = 0
	for u3: int in p.tr_units:
		for j3: int in range(p.tr_pt_off[u3], p.tr_pt_off[u3 + 1]):
			for a3: int in TR.AGE_SLOTS:
				var m3: int = p.tr_pt_age[j3 * TR.AGE_SLOTS + a3]
				if m3 <= 0:
					continue
				bm_n += 1
				var bm: PackedInt64Array = TR.birth_months(p, j3, p.tr_key[u3 * TR.KEY_STRIDE + 1] * 5 + a3, m3)
				var sb: int = 0
				for k3: int in 12:
					sb += bm[k3]
					bm_bad += 1 if bm[k3] < 0 else 0
				bm_bad += 0 if sb == m3 else 1
	check(bm_bad == 0 and bm_n > 0, "T2s-m (month 0, birth months) %d (point, age) masses split over 12 months by birth_months(): off their mass or < 0 %d" % [bm_n, bm_bad])
	check(bad_u == 0 and bad_pt == 0 and neg == 0 and int(p.tr_margins["t21_age_mismatch"]) == 0, "T2s-m (month 0, by age) units off their age counts %d, points off their mass %d, masses < 0 %d, units whose age counts miss their count %d" % [bad_u, bad_pt, neg, int(p.tr_margins["t21_age_mismatch"])])


func _roles(p: RefCounted) -> void:
	var got: Dictionary = {}
	var per_pt := PackedInt64Array()
	per_pt.resize(p.tr_pt_off[p.tr_units])
	var unit_of := PackedInt32Array()
	unit_of.resize(p.tr_pt_off[p.tr_units])
	for u: int in p.tr_units:
		for j: int in range(p.tr_pt_off[u], p.tr_pt_off[u + 1]):
			unit_of[j] = u
	for h: int in p.tr_hh_keys.size():
		for k: int in range(p.tr_hm_off[h], p.tr_hm_off[h + 1]):
			var key: String = "%d|%d|%d" % [h, unit_of[p.tr_hm_pt[k]], p.tr_hm_role[k]]
			got[key] = int(got.get(key, 0)) + p.tr_hm_n[k]
			per_pt[p.tr_hm_pt[k]] += p.tr_hm_n[k]
	var bad: int = 0
	var want_n: int = 0
	for h2: int in p.tr_hh_keys.size():
		var mem: Dictionary = p.tr_hh[p.tr_hh_keys[h2]]["members"]
		for u2 in mem:
			for r in mem[u2]:
				want_n += 1
				if int(got.get("%d|%d|%d" % [h2, int(u2), int(r)], 0)) != int(mem[u2][r]):
					bad += 1
	var over: int = 0
	for j2: int in per_pt.size():
		over += 1 if per_pt[j2] > p.tr_pt_mass[j2] else 0
	check(bad == 0 and over == 0, "(3) household-bundle roles off their member count %d of %d, points over their mass %d; persons in no household-bundle %d (reported)" % [bad, want_n, over, int(p.tr_margins["t21_role_rest"])])


func _couples(p: RefCounted) -> void:
	var cm: Dictionary = (p.tr_margins["cp_extra"] as Dictionary).duplicate()
	var tot: int = 0
	for c: int in int(p.tr_margins["cp_nh_from"]):
		for j: int in [p.tr_cp_w[c], p.tr_cp_h[c]]:
			cm[j] = int(cm.get(j, 0)) + p.tr_cp_n[c]
		tot += p.tr_cp_n[c]
	var want: Dictionary = {}
	var want_h4: Dictionary = {}
	for h: int in p.tr_hh_keys.size():
		var t: int = int(p.tr_hh_keys[h].split("|")[1])
		if t != 1 and t != 2 and t != 4:
			continue
		for k: int in range(p.tr_hm_off[h], p.tr_hm_off[h + 1]):
			var j2: int = p.tr_hm_pt[k]
			var fem: bool = int(p.tr_points["sex"][j2]) == p.FEMALE
			if (fem and p.tr_hm_role[k] == 1) or (not fem and p.tr_hm_role[k] == 0 and t != 4):
				want[j2] = int(want.get(j2, 0)) + p.tr_hm_n[k]
			elif not fem and p.tr_hm_role[k] == 0:
				want_h4[j2] = int(want_h4.get(j2, 0)) + p.tr_hm_n[k]
	var off: int = 0
	var over4: int = 0
	for j3 in want:
		var got: int = int(cm.get(j3, 0))
		var w4: int = int(want_h4.get(j3, 0))
		if w4 > 0:
			off += 1 if got < int(want[j3]) or got > int(want[j3]) + w4 else 0
		else:
			off += 0 if got == int(want[j3]) else 1
	for j4 in want_h4:
		if not want.has(j4):
			over4 += 1 if int(cm.get(j4, 0)) > int(want_h4[j4]) else 0
	print("REPORT T2s-cp the wives above their group's male heads by type x householder band (TO_E 11:27): %s" % str(p.tr_margins.get("cp_cross_by", {})))
	var rec_n: int = 0
	for rk: String in p.tr_nh_hh:
		for rec: Array in p.tr_nh_hh[rk]:
			rec_n += int(rec[3])
	var nh_made: int = 0
	for c2: int in range(int(p.tr_margins["cp_nh_from"]), p.tr_cp_n.size()):
		nh_made += p.tr_cp_n[c2]
	check(nh_made == int(p.tr_margins["cp_nh"]) and nh_made + int(p.tr_margins["cp_nh_short"]) == rec_n, "T2s-cp (c) (§12.12 (9), restored as a subset) the non-head couples' points: %d couples made of %d recorded in T1's households, %d short (their points' masses not found)" % [nh_made, rec_n, int(p.tr_margins["cp_nh_short"])])
	check(off == 0 and over4 == 0, "T2s-cp (month 0, AMENDED for §12.12) %d couples in %d couple points; points whose couple marginal (with the counted extra) is off their role mass %d, 'other' heads above their mass %d; wives above their group's male heads %d (the cross-tier wives among them, §12.12 (7); the rest wives placed by all heads' classes where 'other' holds female heads), partnerless heads %d" % [tot, p.tr_cp_n.size(), off, over4, int(p.tr_margins["cp_cross"]), int(p.tr_margins["cp_nopartner"])])


func _r70(p: RefCounted) -> void:
	var ranks: Dictionary = p.tr_margins["cp_ranks"]
	var blocks: Array = []
	for h: int in p.tr_hh_keys.size():
		var t: int = int(p.tr_hh_keys[h].split("|")[1])
		if t == 1 or t == 2 or t == 4:
			blocks.append(h)
	var worst: float = 0.0
	var read: int = 0
	var sampled: int = 0
	for s: int in 200:
		var h2: int = blocks[KEYED.below(blocks.size(), 1, "t2s_r70_sample", s, 0, 0)]
		var w: Array = []
		var wn: Array = []
		var hu: Array = []
		var hn: Array = []
		for k: int in range(p.tr_hm_off[h2], p.tr_hm_off[h2 + 1]):
			var j: int = p.tr_hm_pt[k]
			var fem: bool = int(p.tr_points["sex"][j]) == p.FEMALE
			if fem and p.tr_hm_role[k] == 1:
				w.append(j)
				wn.append(p.tr_hm_n[k])
			elif not fem and p.tr_hm_role[k] == 0:
				hu.append(j)
				hn.append(p.tr_hm_n[k])
		var sw: int = 0
		var sh: int = 0
		for x: int in wn:
			sw += x
		for y: int in hn:
			sh += y
		if w.size() < 2 or hu.size() < 2 or sw != sh:
			continue
		sampled += 1
		var seed := PackedFloat64Array()
		seed.resize(w.size() * hu.size())
		for a: int in w.size():
			for b: int in hu.size():
				seed[a * hu.size() + b] = TR.couple_seed(p, int(w[a]), int(hu[b]), ranks)
		var xt: PackedFloat64Array = TR.ipf2(seed, wn, hn)
		var nc: int = hu.size()
		for a1: int in w.size():
			for a2: int in range(a1 + 1, w.size()):
				for b1: int in nc:
					for b2: int in range(b1 + 1, nc):
						var den: float = xt[a1 * nc + b2] * xt[a2 * nc + b1]
						var sden: float = seed[a1 * nc + b2] * seed[a2 * nc + b1]
						if den <= 1e-300 or sden <= 0.0 or xt[a1 * nc + b1] <= 1e-300 or xt[a2 * nc + b2] <= 1e-300:
							continue
						var rx: float = xt[a1 * nc + b1] * xt[a2 * nc + b2] / den
						var rs: float = seed[a1 * nc + b1] * seed[a2 * nc + b2] / sden
						worst = maxf(worst, absf(rx / rs - 1.0))
						read += 1
	check(read > 0 and worst < 1e-9, "T2s-r70 (month 0) the IPF keeps the seed's cross-product ratios: %d ratios over %d sampled blocks, worst relative gap %s" % [read, sampled, str(worst)])
	var ce: Dictionary = TR._v(p, "couple_wife_employment")
	var emp := PackedFloat64Array()
	emp.resize(16)
	var all := PackedFloat64Array()
	all.resize(16)
	for c: int in p.tr_cp_n.size():
		var cl: int = TR._r70_class(p, p.tr_cp_h[c], ce["class_from_man_yen_year"])
		all[cl] += float(p.tr_cp_n[c])
		emp[cl] += float(p.tr_cp_n[c]) if TR._at_work(p, p.tr_cp_w[c]) else 0.0
	var txt: String = ""
	for k2: int in 16:
		var rc: float = 0.0
		var re: float = 0.0
		for b3: int in 6:
			rc += float(ce["couples"][b3][k2])
			re += float(ce["wife_employed"][b3][k2])
		txt += " %d: %.3f (R70 %.3f, %d);" % [k2, emp[k2] / maxf(1.0, all[k2]), re / rc, int(all[k2])]
	print("REPORT T2s-r70 (month 0) the wives at work by the husband's class, the start against R70 (the start's own employment margins hold, M008):%s" % txt)


func _ms(p: RefCounted) -> void:
	var bad: int = 0
	var tot := PackedInt64Array([0, 0, 0, 0])
	var by_sex := PackedInt64Array([0, 0])
	for u: int in p.tr_units:
		for j: int in range(p.tr_pt_off[u], p.tr_pt_off[u + 1]):
			var s: int = 0
			for k: int in 4:
				s += p.tr_pt_ms[j * 4 + k]
				bad += 1 if p.tr_pt_ms[j * 4 + k] < 0 else 0
				tot[k] += p.tr_pt_ms[j * 4 + k]
			bad += 0 if s == p.tr_pt_mass[j] else 1
	var wives: int = 0
	var husbands: int = 0
	for c: int in p.tr_cp_n.size():
		wives += p.tr_cp_n[c]
		husbands += p.tr_cp_n[c]
	var ex: Dictionary = p.tr_margins["cp_extra"]
	for j2 in ex:
		if int(p.tr_points["sex"][int(j2)]) == p.FEMALE:
			wives += int(ex[j2])
		else:
			husbands += int(ex[j2])
	var bal: bool = wives == husbands + int(p.tr_margins["cp_cross"]) - int(p.tr_margins["cp_nopartner"])
	var r77: int = 0
	for src: Dictionary in [p.tr_couples, p.tr_nh_couples]:
		for k: String in src:
			r77 += int(src[k])
	check(bad == 0 and bal, "T2s-ms (month 0) points whose four states do not sum to their mass, or < 0: %d; wives in couples %d = husbands in couples %d + the wives above their group's male heads %d - partnerless heads %d: %s; against R77's couples (head + non-head) %d the wives are %+d (V114 (5): the unplaced non-head couples %d and the partnerless heads)" % [bad, wives, husbands, int(p.tr_margins["cp_cross"]), int(p.tr_margins["cp_nopartner"]), str(bal), r77, wives - r77, int(p.tr_margins.get("nh_unplaced", 0))])
	var nm_t1: float = 0.0
	for u2: int in p.tr_units:
		nm_t1 += p.tr_never_married[u2] * float(p.tr_count[u2])
	var ms: Dictionary = p.tr_margins["ms"]
	print("REPORT T2s-ms the points' states (never, married, widowed, divorced) %s; never married against T1's (R62) %.0f; cells %d, never married capped in %d, married-apart above the persons in no couple in %d" % [str(tot), nm_t1, int(ms["cells"]), int(ms["capped"]), int(ms["ma_over"])])
