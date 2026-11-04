extends "res://tools/test/test_kit.gd"
## THE STOP'S READ (TO_E 01:42, after V118 ade3af33; ISS_CHECKS, declared at 67c22f52 before this code), on M027's rule B: the persons
## layer (households on, all prefectures, 2,000 a prefecture), every person in a key group (the tiers' household-bundle key, as
## test_modern_t2_m026) of 2+ households, per 10-year band:
##   B  4 conditional households per person: own and real spouse's incomes, every other slot drawn by weight, keyed (i, k, slot), from
##      the members of that slot's role in the group's other households (any member of them where none holds the role, counted)
##   A  the control: the group's mean true E over its other households (leave-one-household-out)
##   D  the floor of R1: one matched donor, the same-role person of the group's other households with the nearest own income (ties by
##      index), its household's members filling i's other slots by role (a role the donor household lacks drawn as B), i's spouse kept
## R2 the bottom ÷ top death ratio by the person's OWN-income quartile (ranked by weight in the band), Σ_j P(q = j | q_own) I_j(a) at the
##    band's mid age (82 for 80+), q the rule's assigned quartile on the RULE'S OWN cuts against q the true household quartile; the
##    attenuation 1 − ln R_rule ÷ ln R_true; also on the persons layer's (the true E's) cuts, reported
## the joint distance: the mean over the four own-income rows of the TV between P(q_rule | q_own) and P(q_true | q_own)
## R1 (M027 §3's read, the persons layer's cuts) for B, reported with D beside it
## PASS: |R2| < 25% in every band 60-69, 70-79, 80+ AND the joint distance <= 0.020 in each (AMENDED from 0.035, TO_E 03:14, V119:
## the 0.035 was set on mismatched cuts), for B; A must fail (reported)
##   godot --headless --path . --script res://sim/modern/test_modern_t2_stop.gd
const PEOPLE = preload("res://sim/modern/people/people.gd")
const TR = preload("res://sim/modern/people/tiers.gd")
const LC = preload("res://sim/modern/people/life_course.gd")
const MS = preload("res://sim/modern/modern_status.gd")
const CANON = preload("res://sim/modern/canon.gd")
const KEYED = preload("res://sim/earth_core/keyed.gd")
const N_PER := 2000
const K := 4
const R2_MAX := 0.25
const TV_MAX := 0.020


func _init() -> void:
	var st = MS.new()
	st.load(2024, ["JPN"])
	var prefs: Dictionary = CANON.load_json("res://data/modern/polity/jpn_prefectures.json")["prefectures"]
	var tp = PEOPLE.new()
	tp.tiers = true
	tp.create("JPN", 1, st.cohort["JPN"], st.qx["JPN"], prefs, 0, 2024)
	var lines: PackedFloat64Array = tp.tr_class_lines.duplicate()
	tp = null
	var h = PEOPLE.new()
	h.households = true
	var err: String = h.create("JPN", 1, st.cohort["JPN"], st.qx["JPN"], prefs, N_PER)
	check(err == "" and lines.size() > 0, "the persons layer built (households on, %d persons, %d households); the tiers' %d class lines" % [h.n, h.hh_members.size(), lines.size()])
	var t_of := PackedFloat64Array()
	t_of.resize(h.n)
	var key_of: Array = []
	key_of.resize(h.n)
	var groups: Dictionary = {}
	for hh: int in h.hh_members.size():
		var mem: PackedInt32Array = h.hh_members[hh]
		if mem.is_empty():
			continue
		var head: int = mem[0]
		for j: int in mem:
			if h.hh_role[j] == h.R_HEAD:
				head = j
		var cl: int = TR.class_of_income(lines, h.income[head]) if h.age[head] >= TR.ADULT_FROM else TR.CLASS_NONE
		var key: String = "%d|%d|%d|%d|%d" % [h.hh_pref[hh], h.hh_type[hh], TR.band_of(h.age[head]), mini(mem.size(), 5), cl]
		if not groups.has(key):
			groups[key] = {"hh": {}, "any": [], "sum": [0.0, 0.0], "byrole": {}}
		var g: Dictionary = groups[key]
		var e: float = LC.equivalized(h, head)
		var hw: float = 0.0
		for j2: int in mem:
			t_of[j2] = e
			key_of[j2] = key
			hw += h.weight[j2]
			var r: int = h.hh_role[j2]
			if not g.has(r):
				g[r] = []
				g["byrole"][r] = []
			for pool: Array in [g[r], g["any"]]:
				var cum: float = (float(pool[pool.size() - 1][2]) if pool.size() > 0 else 0.0) + h.weight[j2]
				pool.append([j2, hh, cum])
			(g["byrole"][r] as Array).append([h.income[j2], j2, hh])
		g["hh"][hh] = [e, hw]
		g["sum"][0] += e * hw
		g["sum"][1] += hw
	for key2: String in groups:
		for r2 in groups[key2]["byrole"]:
			(groups[key2]["byrole"][r2] as Array).sort()
	# the rules' E per person: B's 4 samples, A's one, D's one
	var read: Array = []
	var eb: Array = []
	var ea := PackedFloat64Array()
	var ed := PackedFloat64Array()
	var fb: int = 0
	var fd: int = 0
	for i: int in h.n:
		var g2: Dictionary = groups[key_of[i]]
		if (g2["hh"] as Dictionary).size() < 2:
			continue
		var own: int = h.hh_id[i]
		var mem2: PackedInt32Array = h.hh_members[own]
		var s: int = mem2.size()
		read.append(i)
		var ks := PackedFloat64Array()
		for k: int in K:
			var tot: float = h.income[i]
			for slot: int in s:
				var m: int = mem2[slot]
				if m == i:
					continue
				if m == h.partner[i]:
					tot += h.income[m]
					continue
				var pick: int = _draw(g2.get(h.hh_role[m], []), own, KEYED.u(h.seed_v, "m027_slot", h.pid[i], k, slot))
				if pick < 0:
					fb += 1
					pick = _draw(g2["any"], own, KEYED.u(h.seed_v, "m027_any", h.pid[i], k, slot))
				tot += h.income[pick] if pick >= 0 else 0.0
			ks.append(tot / sqrt(float(s)))
		eb.append(ks)
		var self_hh: Array = g2["hh"][own]
		ea.append((float(g2["sum"][0]) - float(self_hh[0]) * float(self_hh[1])) / (float(g2["sum"][1]) - float(self_hh[1])))
		var donor: int = _nearest(g2["byrole"].get(h.hh_role[i], []), h.income[i], own)
		var totd: float = h.income[i]
		var used: Dictionary = {}
		if donor >= 0:
			used[donor] = true
		var dm: PackedInt32Array = h.hh_members[h.hh_id[donor]] if donor >= 0 else PackedInt32Array()
		for slot2: int in s:
			var m2: int = mem2[slot2]
			if m2 == i:
				continue
			if m2 == h.partner[i]:
				totd += h.income[m2]
				continue
			var got: int = -1
			for x: int in dm:
				if not used.has(x) and h.hh_role[x] == h.hh_role[m2] and x != h.partner[donor]:
					got = x
					break
			if got < 0:
				fd += 1
				got = _draw(g2.get(h.hh_role[m2], []), own, KEYED.u(h.seed_v, "stop_d", h.pid[i], 0, slot2))
				if got < 0:
					got = _draw(g2["any"], own, KEYED.u(h.seed_v, "stop_d_any", h.pid[i], 0, slot2))
			if got >= 0:
				used[got] = true
				totd += h.income[got]
		ed.append(totd / sqrt(float(s)))
	print("REPORT the stop's read: %d persons read (key groups of 2+ households); B's slots with no same-role member in the group's other households %d; D's slots its donor household could not fill %d" % [read.size(), fb, fd])
	# per band: own-income quartiles, the true E's cuts, each rule's own cuts
	var by_band: Array = []
	for b: int in 9:
		by_band.append([])
	for x2: int in read.size():
		(by_band[LC._b10(h.age[read[x2]])] as Array).append(x2)
	var pass_ok: bool = true
	var a_fails: bool = true
	var lines_out: Array = []
	for b2: int in 9:
		var idx: Array = by_band[b2]
		if idx.size() < 40:
			continue
		var w := PackedFloat64Array()
		var own_v := PackedFloat64Array()
		var t_v := PackedFloat64Array()
		var a_v := PackedFloat64Array()
		var d_v := PackedFloat64Array()
		var bs_v := PackedFloat64Array()
		var bs_w := PackedFloat64Array()
		for x3: int in idx:
			var i2: int = read[x3]
			w.append(h.weight[i2])
			own_v.append(h.income[i2])
			t_v.append(t_of[i2])
			a_v.append(ea[x3])
			d_v.append(ed[x3])
			for e2: float in eb[x3]:
				bs_v.append(e2)
				bs_w.append(h.weight[i2] / float(K))
		var q_own: PackedInt32Array = _quart(own_v, w)
		var c_true: PackedFloat64Array = _cuts(t_v, w)
		var c_b: PackedFloat64Array = _cuts(bs_v, bs_w)
		var c_a: PackedFloat64Array = _cuts(a_v, w)
		var c_d: PackedFloat64Array = _cuts(d_v, w)
		var jt := _z16()
		var jb := _z16()
		var jb_pl := _z16()
		var ja := _z16()
		var jd := _z16()
		var r1b := _z16()
		var r1d := _z16()
		for y: int in idx.size():
			var x4: int = idx[y]
			var qo: int = q_own[y]
			var qt: int = _q(c_true, t_v[y])
			jt[qo * 4 + qt] += w[y]
			ja[qo * 4 + _q(c_a, a_v[y])] += w[y]
			jd[qo * 4 + _q(c_d, d_v[y])] += w[y]
			r1d[qt * 4 + _q(c_true, d_v[y])] += w[y]
			for e3: float in eb[x4]:
				jb[qo * 4 + _q(c_b, e3)] += w[y] / float(K)
				jb_pl[qo * 4 + _q(c_true, e3)] += w[y] / float(K)
				r1b[qt * 4 + _q(c_true, e3)] += w[y] / float(K)
		var a: int = mini(82, b2 * 10 + 5)
		var rt: float = _ratio(h, jt, a)
		var r2b: float = 1.0 - log(_ratio(h, jb, a)) / log(rt)
		var r2b_pl: float = 1.0 - log(_ratio(h, jb_pl, a)) / log(rt)
		var r2a: float = 1.0 - log(_ratio(h, ja, a)) / log(rt)
		var r2d: float = 1.0 - log(_ratio(h, jd, a)) / log(rt)
		var tvb: Array = _tv(jb, jt)
		var tva: Array = _tv(ja, jt)
		var tvd: Array = _tv(jd, jt)
		var i3: float = log(LC.income_factor(h, a, 3))
		var r1_b: float = 1.0 - log(_ratio(h, r1b, a)) / i3
		var r1_d: float = 1.0 - log(_ratio(h, r1d, a)) / i3
		var lab: String = "%d-%s" % [b2 * 10, "" if b2 == 8 else str(b2 * 10 + 9)]
		lines_out.append(" %s: R2 B %.1f%% (persons' cuts %.1f%%), A %.1f%%, D %.1f%%; joint TV B %.3f (largest cell %.3f), A %.3f, D %.3f; R1 B %.1f%%, floor D %.1f%%; the true ratio by own income %.4f (%d persons)" % [lab, 100.0 * r2b, 100.0 * r2b_pl, 100.0 * r2a, 100.0 * r2d, float(tvb[0]), float(tvb[1]), float(tva[0]), float(tvd[0]), 100.0 * r1_b, 100.0 * r1_d, rt, idx.size()])
		if b2 >= 6:
			pass_ok = pass_ok and absf(r2b) < R2_MAX and float(tvb[0]) <= TV_MAX
			a_fails = a_fails and not (absf(r2a) < R2_MAX and float(tva[0]) <= TV_MAX)
	print("REPORT the stop's read by 10-year band:%s" % ";".join(PackedStringArray(lines_out)))
	print("REPORT the control A (the bundle mean) fails the read in every band from 60-69: %s" % str(a_fails))
	check(pass_ok, "THE STOP'S READ (TO_E 01:42) on rule B: |R2| < 25%% and the joint distance <= %.3f in every band 60-69, 70-79, 80+: %s" % [TV_MAX, "PASS: T2.2 resumes" if pass_ok else "FAIL: the stop stays"])
	finish()


func _z16() -> PackedFloat64Array:
	var z := PackedFloat64Array()
	z.resize(16)
	return z


## Σ_j P(q = j | row 3) I_j(a) ÷ Σ_j P(q = j | row 0) I_j(a) over a 4 x 4 table (rows the conditioning quartile, 0 the top)
func _ratio(h: RefCounted, t: PackedFloat64Array, a: int) -> float:
	var r0: float = t[0] + t[1] + t[2] + t[3]
	var r3: float = t[12] + t[13] + t[14] + t[15]
	var num: float = 0.0
	var den: float = 0.0
	for j: int in 4:
		num += t[12 + j] / r3 * LC.income_factor(h, a, j)
		den += t[j] / r0 * LC.income_factor(h, a, j)
	return num / den


## [the mean over the four rows of the total variation between the row-conditional distributions, the largest conditional cell gap]
func _tv(x: PackedFloat64Array, t: PackedFloat64Array) -> Array:
	var tot: float = 0.0
	var mx: float = 0.0
	for r: int in 4:
		var sx: float = x[r * 4] + x[r * 4 + 1] + x[r * 4 + 2] + x[r * 4 + 3]
		var st: float = t[r * 4] + t[r * 4 + 1] + t[r * 4 + 2] + t[r * 4 + 3]
		var tv: float = 0.0
		for j: int in 4:
			var d: float = absf(x[r * 4 + j] / sx - t[r * 4 + j] / st)
			tv += 0.5 * d
			mx = maxf(mx, d)
		tot += tv
	return [tot / 4.0, mx]


## The weighted 25 / 50 / 75% cuts of v (as LC.quartile_cuts)
func _cuts(v: PackedFloat64Array, w: PackedFloat64Array) -> PackedFloat64Array:
	var idx: Array = range(v.size())
	idx.sort_custom(func(a: int, b: int) -> bool: return v[a] < v[b] if v[a] != v[b] else a < b)
	var tot: float = 0.0
	for x: float in w:
		tot += x
	var out := PackedFloat64Array([INF, INF, INF])
	var acc: float = 0.0
	var q: int = 0
	for i: int in idx:
		acc += w[i]
		while q < 3 and acc >= tot * float(q + 1) / 4.0:
			out[q] = v[i]
			q += 1
	return out


func _q(c: PackedFloat64Array, e: float) -> int:
	if e < c[0]:
		return 3
	if e < c[1]:
		return 2
	if e < c[2]:
		return 1
	return 0


## Quartiles by weight (0 the top) at each entry's weight midpoint, ties in index order
func _quart(v: PackedFloat64Array, w: PackedFloat64Array) -> PackedInt32Array:
	var idx: Array = range(v.size())
	idx.sort_custom(func(a: int, b: int) -> bool: return v[a] < v[b] if v[a] != v[b] else a < b)
	var tot: float = 0.0
	for x: float in w:
		tot += x
	var out := PackedInt32Array()
	out.resize(v.size())
	var acc: float = 0.0
	for i: int in idx:
		var pos: float = (acc + 0.5 * w[i]) / tot
		out[i] = 3 if pos < 0.25 else (2 if pos < 0.5 else (1 if pos < 0.75 else 0))
		acc += w[i]
	return out


## A draw by weight from a pool [[person, household, cumulative weight]] at u, skipping the household own; -1 if none
func _draw(pool: Array, own: int, u: float) -> int:
	if pool.is_empty():
		return -1
	var x: float = u * float(pool[pool.size() - 1][2])
	var lo: int = 0
	var hi: int = pool.size() - 1
	while lo < hi:
		var mid: int = (lo + hi) / 2
		if float(pool[mid][2]) > x:
			hi = mid
		else:
			lo = mid + 1
	for step: int in pool.size():
		var e: Array = pool[(lo + step) % pool.size()]
		if int(e[1]) != own:
			return int(e[0])
	return -1


## The person of a sorted [[income, person, household]] list nearest to y outside the household own (ties to the lower index); -1 if none
func _nearest(lst: Array, y: float, own: int) -> int:
	var best: int = -1
	var bd: float = INF
	for e: Array in lst:
		if int(e[2]) == own:
			continue
		var d: float = absf(float(e[0]) - y)
		if d < bd or (d == bd and int(e[1]) < best):
			bd = d
			best = int(e[1])
	return best
