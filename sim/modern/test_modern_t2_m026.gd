extends "res://tools/test/test_kit.gd"
## M026 §3's decisive check (math-reports f22d60ac; TO_E 23:38 (1)), declared there before this code: in the persons layer (households
## on, all prefectures), each person's TRUE equivalized household income T (LC.equivalized) against A, the mean of T over the persons
## of its household-bundle key as the tiers key it (prefecture x type x householder band x size class x the householder's class by the
## tiers' class lines). Both are ranked into quartiles by weight within the 10-year band, both sexes (as T2.2 ranks them). The implied
## bottom ÷ top death ratio by true quartile is Σ_j P(q_A = j | q_T) I_j(a), and its attenuation is 1 − ln(that) ÷ ln I_3(a), per band
## at the band's mid age (82 for 85+, the function's range). RESUME when it is under a third in every band of 65+; under 65 reported.
## A finite sample's group mean includes the person itself, which raises corr(A, T); A is also read leave-one-out (lowers it), and both
## are reported, with the persons' group sizes. The decision reads the leave-one-HOUSEHOLD-out A (a household's members share T and the
## key, so leaving out only the person keeps its household's income in A), the side that cannot hide attenuation
##   godot --headless --path . --script res://sim/modern/test_modern_t2_m026.gd
const PEOPLE = preload("res://sim/modern/people/people.gd")
const TR = preload("res://sim/modern/people/tiers.gd")
const LC = preload("res://sim/modern/people/life_course.gd")
const MS = preload("res://sim/modern/modern_status.gd")
const CANON = preload("res://sim/modern/canon.gd")
const N_PER := 2000


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
	var sums: Dictionary = {}
	for hh: int in h.hh_members.size():
		var mem: PackedInt32Array = h.hh_members[hh]
		if mem.is_empty():
			continue
		var head: int = mem[0]
		for j: int in mem:
			if h.hh_role[j] == h.R_HEAD:
				head = j
		var hb: int = TR.band_of(h.age[head])
		var cl: int = TR.class_of_income(lines, h.income[head]) if h.age[head] >= TR.ADULT_FROM else TR.CLASS_NONE
		var key: String = "%d|%d|%d|%d|%d" % [h.hh_pref[hh], h.hh_type[hh], hb, mini(mem.size(), 5), cl]
		var e: float = LC.equivalized(h, head)
		for j2: int in mem:
			t_of[j2] = e
			key_of[j2] = key
			if not sums.has(key):
				sums[key] = [0.0, 0.0, 0]
			sums[key][0] += e * h.weight[j2]
			sums[key][1] += h.weight[j2]
			sums[key][2] += 1
	var a_in := PackedFloat64Array()
	var a_loo := PackedFloat64Array()
	var a_hoo := PackedFloat64Array()
	a_in.resize(h.n)
	a_loo.resize(h.n)
	a_hoo.resize(h.n)
	for hh2: int in h.hh_members.size():
		var mem2: PackedInt32Array = h.hh_members[hh2]
		if mem2.is_empty():
			continue
		var sw: float = 0.0
		for j4: int in mem2:
			sw += h.weight[j4]
		var s2: Array = sums[key_of[mem2[0]]]
		var rest: float = float(s2[1]) - sw
		for j5: int in mem2:
			a_hoo[j5] = (float(s2[0]) - t_of[j5] * sw) / rest if rest > 1e-9 else NAN
	var single: int = 0
	var size_txt: Dictionary = {}
	for i: int in h.n:
		var s: Array = sums[key_of[i]]
		a_in[i] = float(s[0]) / float(s[1])
		if int(s[2]) > 1 and float(s[1]) - h.weight[i] > 0.0:
			a_loo[i] = (float(s[0]) - t_of[i] * h.weight[i]) / (float(s[1]) - h.weight[i])
		else:
			a_loo[i] = NAN
			single += 1
		var gs: int = int(s[2])
		var bin: String = "1" if gs == 1 else ("2-4" if gs < 5 else ("5-19" if gs < 20 else "20+"))
		size_txt[bin] = int(size_txt.get(bin, 0)) + 1
	print("REPORT M026 the persons by their key's group size %s; persons alone in their key (no leave-one-out A, left out of that read) %d" % [str(size_txt), single])
	var worst: Dictionary = {}
	var alone_h: int = 0
	for i6: int in h.n:
		alone_h += 1 if is_nan(a_hoo[i6]) else 0
	print("REPORT M026 persons whose household is alone in its key (no leave-one-household-out A) %d" % alone_h)
	for read: Array in [["inclusive", a_in], ["leave-one-person-out", a_loo], ["leave-one-household-out", a_hoo]]:
		var txt: String = ""
		var w65: float = 0.0
		for b10: int in 9:
			var res: Array = _band(h, b10, t_of, read[1])
			if res.is_empty():
				continue
			var a: int = mini(82, b10 * 10 + 5) if b10 < 8 else 82
			var num: float = 0.0
			var den: float = 0.0
			var pt: PackedFloat64Array = res[0]
			for j3: int in 4:
				num += pt[3 * 4 + j3] * LC.income_factor(h, a, j3)
				den += pt[0 * 4 + j3] * LC.income_factor(h, a, j3)
			var r: float = num / den
			var att: float = 1.0 - log(r) / log(LC.income_factor(h, a, 3))
			txt += " %d-%s at %d: P(q_A=bottom | q_T=bottom) %.3f, ratio by true quartile %.4f against I_3 %.4f, attenuation %.1f%% (%d persons);" % [b10 * 10, "" if b10 == 8 else str(b10 * 10 + 9), a, pt[15], r, LC.income_factor(h, a, 3), 100.0 * att, int(res[1])]
			if b10 >= 6:
				w65 = maxf(w65, att)
		print("REPORT M026 (%s A) by 10-year band:%s" % [read[0], txt])
		worst[read[0]] = w65
	var dec: float = float(worst["leave-one-household-out"])
	check(dec < 1.0 / 3.0, "M026 §3 the decisive check (TO_E 23:38 (1)): the attenuation under a third in every band from 60-69 up, worst %.1f%% leave-one-household-out (person-out %.1f%%, inclusive %.1f%%): %s" % [100.0 * dec, 100.0 * float(worst["leave-one-person-out"]), 100.0 * float(worst["inclusive"]), "RESUME" if dec < 1.0 / 3.0 else "the stop STAYS (T2.3's household income points first)"])
	finish()


## P(q_A = j | q_T = k) by weight among band b10's persons, both quartiles by weight within the band; [the 4 x 4 table row-normalised
## (row k = the true quartile, 0 the top), the persons read]
func _band(h: RefCounted, b10: int, t_of: PackedFloat64Array, a_of: PackedFloat64Array) -> Array:
	var rows: Array = []
	for i: int in h.n:
		if LC._b10(h.age[i]) == b10 and not is_nan(a_of[i]):
			rows.append(i)
	if rows.size() < 40:
		return []
	var qt: Dictionary = _quart(h, rows, t_of)
	var qa: Dictionary = _quart(h, rows, a_of)
	var tab := PackedFloat64Array()
	tab.resize(16)
	var rs := PackedFloat64Array([0.0, 0.0, 0.0, 0.0])
	for i2: int in rows:
		tab[int(qt[i2]) * 4 + int(qa[i2])] += h.weight[i2]
		rs[int(qt[i2])] += h.weight[i2]
	for k: int in 4:
		for j: int in 4:
			tab[k * 4 + j] = tab[k * 4 + j] / rs[k] if rs[k] > 0.0 else 0.0
	return [tab, rows.size()]


## Quartiles by weight (0 the top .. 3 the bottom) at each person's weight midpoint, ties in index order
func _quart(h: RefCounted, rows: Array, v: PackedFloat64Array) -> Dictionary:
	var srt: Array = rows.duplicate()
	srt.sort_custom(func(x: int, y: int) -> bool: return v[x] < v[y] if v[x] != v[y] else x < y)
	var tot: float = 0.0
	for i: int in srt:
		tot += h.weight[i]
	var out: Dictionary = {}
	var acc: float = 0.0
	for i2: int in srt:
		var pos: float = (acc + 0.5 * h.weight[i2]) / tot
		out[i2] = 3 if pos < 0.25 else (2 if pos < 0.5 else (1 if pos < 0.75 else 0))
		acc += h.weight[i2]
	return out
