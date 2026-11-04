extends "res://tools/test/test_kit.gd"
## M027 §3's persons-layer mimic of §14.7 AMENDED (math-reports c67dc21b; TO_E 00:08 (3); declared at 2d6abb78 before this code): in the
## persons layer (households on, all prefectures, 2,000 a prefecture), each person i whose key group (the tiers' household-bundle key,
## as test_modern_t2_m026) holds at least two households takes 4 conditional households of its own size: its own income in its slot, its
## spouse's own income when the spouse is in the household, every other member's slot drawn by weight, keyed (i, k, slot), from the
## members of that member's role in the group's other households (i's own household left out; where the group's other households hold
## none of the role, any member of them, counted). E_k = Σ incomes ÷ √s; i's assigned quartile mass ¼ at each E_k's quartile against the
## cuts of the true household E in i's 10-year band (weighted, both sexes). The implied bottom ÷ top death ratio by true quartile is
## Σ_j P(q_A = j | q_T) I_j(a), its attenuation 1 − ln(that) ÷ ln I_3(a) at the band's mid age (82 for 80+).
## PASS: every band from 60-69 up under 25% (predicted 8 / 4 / 3%). The bracketing read (the spouse drawn like the other members) reported;
## REPORT (added after the first run's miss, a diagnosis only, the pass unchanged): the real-spouse read split by i's role (head or
## partner, against child, parent and other) and by the household type
##   godot --headless --path . --script res://sim/modern/test_modern_t2_m027.gd
const PEOPLE = preload("res://sim/modern/people/people.gd")
const TR = preload("res://sim/modern/people/tiers.gd")
const LC = preload("res://sim/modern/people/life_course.gd")
const MS = preload("res://sim/modern/modern_status.gd")
const CANON = preload("res://sim/modern/canon.gd")
const KEYED = preload("res://sim/earth_core/keyed.gd")
const N_PER := 2000
const K := 4


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
	var groups: Dictionary = {}   # key -> {"hh": {household: true}, role -> [[person, household, cumulative weight]]}
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
			groups[key] = {"hh": {}, "any": []}
		var g: Dictionary = groups[key]
		g["hh"][hh] = true
		var e: float = LC.equivalized(h, head)
		for j2: int in mem:
			t_of[j2] = e
			key_of[j2] = key
			var r: int = h.hh_role[j2]
			if not g.has(r):
				g[r] = []
			for pool: Array in [g[r], g["any"]]:
				var cum: float = (float(pool[pool.size() - 1][2]) if pool.size() > 0 else 0.0) + h.weight[j2]
				pool.append([j2, hh, cum])
	var cuts: Array = []
	for b10: int in 9:
		cuts.append(_cuts(h, b10, t_of))
	var res: Dictionary = {}
	var fallback: Dictionary = {"real": 0, "drawn": 0, "real hp": 0, "real cpo": 0, "real t0": 0, "real t1": 0, "real t2": 0, "real t3": 0, "real t4": 0}
	for read: String in ["real", "drawn", "real hp", "real cpo", "real t0", "real t1", "real t2", "real t3", "real t4"]:
		var tab: Array = []
		for b: int in 9:
			var z := PackedFloat64Array()
			z.resize(16)
			tab.append(z)
		var used: int = 0
		for i: int in h.n:
			var g2: Dictionary = groups[key_of[i]]
			if (g2["hh"] as Dictionary).size() < 2:
				continue
			if read == "real hp" and h.hh_role[i] > 1:
				continue
			if read == "real cpo" and h.hh_role[i] <= 1:
				continue
			if read.begins_with("real t") and h.hh_type[h.hh_id[i]] != int(read.substr(6)):
				continue
			used += 1
			var own: int = h.hh_id[i]
			var mem2: PackedInt32Array = h.hh_members[own]
			var s: int = mem2.size()
			var b2: int = LC._b10(h.age[i])
			var qt: int = _q(cuts[b2], t_of[i])
			for k: int in K:
				var tot: float = h.income[i]
				for slot: int in s:
					var m: int = mem2[slot]
					if m == i:
						continue
					if read.begins_with("real") and m == h.partner[i]:
						tot += h.income[m]
						continue
					var pool2: Array = g2.get(h.hh_role[m], [])
					var pick: int = _draw(pool2, own, KEYED.u(h.seed_v, "m027_slot", h.pid[i], k, slot))
					if pick < 0:
						fallback[read] = int(fallback[read]) + 1
						pick = _draw(g2["any"], own, KEYED.u(h.seed_v, "m027_any", h.pid[i], k, slot))
					tot += h.income[pick] if pick >= 0 else 0.0
				var ek: float = tot / sqrt(float(s))
				tab[b2][qt * 4 + _q(cuts[b2], ek)] += h.weight[i] / float(K)
		res[read] = [tab, used]
	var worst: Dictionary = {}
	for read2: String in ["real", "drawn", "real hp", "real cpo", "real t0", "real t1", "real t2", "real t3", "real t4"]:
		var txt: String = ""
		var w: float = 0.0
		var tab2: Array = res[read2][0]
		for b3: int in 9:
			var t: PackedFloat64Array = tab2[b3]
			var row0: float = t[0] + t[1] + t[2] + t[3]
			var row3: float = t[12] + t[13] + t[14] + t[15]
			if row0 <= 0.0 or row3 <= 0.0:
				continue
			var a: int = mini(82, b3 * 10 + 5)
			var num: float = 0.0
			var den: float = 0.0
			for j3: int in 4:
				num += t[12 + j3] / row3 * LC.income_factor(h, a, j3)
				den += t[j3] / row0 * LC.income_factor(h, a, j3)
			var ratio: float = num / den
			var att: float = 1.0 - log(ratio) / log(LC.income_factor(h, a, 3))
			txt += " %d-%s at %d: P(q_A=bottom | q_T=bottom) %.3f, ratio %.4f against I_3 %.4f, attenuation %.1f%%;" % [b3 * 10, "" if b3 == 8 else str(b3 * 10 + 9), a, t[15] / row3, ratio, LC.income_factor(h, a, 3), 100.0 * att]
			if b3 >= 6:
				w = maxf(w, att)
		worst[read2] = w
		print("REPORT M027 the mimic (%s spouse; %d persons read, slots with no same-role member in the group's other households %d) by 10-year band:%s" % [read2, int(res[read2][1]), int(fallback[read2]), txt])
	print("REPORT (SUPERSEDED as the pass by the stop's read, TO_E 01:42; test_modern_t2_stop) " + "M027 §3 the mimic (TO_E 00:08 (3)): the attenuation under 25%% in every band from 60-69 up: worst %.1f%% with the real spouse (predicted 8 / 4 / 3%%); the bracketing read with the spouse drawn %.1f%% (reported): %s" % [100.0 * float(worst["real"]), 100.0 * float(worst["drawn"]), "under 25%" if float(worst["real"]) < 0.25 else "not under 25%"])
	finish()


## The weighted 25 / 50 / 75% cuts of the true household E in a 10-year band (as LC.quartile_cuts)
func _cuts(h: RefCounted, b10: int, t_of: PackedFloat64Array) -> PackedFloat64Array:
	var rows: Array = []
	for i: int in h.n:
		if LC._b10(h.age[i]) == b10:
			rows.append([t_of[i], h.weight[i]])
	rows.sort_custom(func(x: Array, y: Array) -> bool: return float(x[0]) < float(y[0]))
	var tot: float = 0.0
	for r: Array in rows:
		tot += float(r[1])
	var out := PackedFloat64Array([INF, INF, INF])
	var acc: float = 0.0
	var q: int = 0
	for r2: Array in rows:
		acc += float(r2[1])
		while q < 3 and acc >= tot * float(q + 1) / 4.0:
			out[q] = float(r2[0])
			q += 1
	return out


## The quartile (0 the top .. 3 the bottom) of e against the cuts, as LC.quartile
func _q(c: PackedFloat64Array, e: float) -> int:
	if e < c[0]:
		return 3
	if e < c[1]:
		return 2
	if e < c[2]:
		return 1
	return 0


## A draw by weight from a pool [[person, household, cumulative weight]] at u, skipping the household own (the next entry on); -1 if none
func _draw(pool: Array, own: int, u: float) -> int:
	if pool.is_empty():
		return -1
	var tot: float = float(pool[pool.size() - 1][2])
	var x: float = u * tot
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
