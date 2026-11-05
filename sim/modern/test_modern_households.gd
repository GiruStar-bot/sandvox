extends "res://tools/test/test_kit.gd"
## ISS households (sim/modern/people/households.gd; ISS_HOUSEHOLD_REDESIGN.md §10): the expectations of ISS_CHECKS.md, declared before
## this test. H1, the start: all 47 prefectures x 60 persons built by households, seed 1, after the start's rake.
##   godot --headless --path . --script res://sim/modern/test_modern_households.gd
## H1s-a household types, weighted by household, each within +-3 pt of the census (38.1 / 20.1 / 25.1 / 9.0 / 7.7%)
## H1s-b mean household size within +-0.1 of 2.21
## H1s-c persons living alone by age band and sex within +-5 pt of 表V-1-3 (R62's twelve cells)
## H1s-d the 65+'s living arrangements within +-5 pt (alone 21.7, couple only 40.7, with a child 33.7%)
## H1s-e the rake: the weighted age band x sex shares within +-0.5 pt of the cohort's, each prefecture within +-0.1% of its population
## H1s-f one weight per household: every member's weight equals its household's
## H1s-g the flag: with households off the test society's 6-month digest is the recorded one (since the review fixes 1a, 1b, 2c)
## H1s-h start consistency (ruling A/D): each prefecture's mean household size within +-0.05 of 表I-5-1, women 85+ in an institution
##       within +-2 pt of 26.1%
## H1s-m start consistency (§10.8 C3): the sample's never-married share by sex and R62's age band within +-2 pt (unweighted: drawn,
##       not weighted); the weighted share and any band the start could not meet are reported
## (H1s-a..c are start-consistency reads since the PM's ruling A: the start's rake holds them; ISS_CHECKS.md, amended 19:15)
const PEOPLE = preload("res://sim/modern/people/people.gd")
const HH = preload("res://sim/modern/people/households.gd")
const MS = preload("res://sim/modern/modern_status.gd")
const CANON = preload("res://sim/modern/canon.gd")
const P5_DIGEST := "4250a82647dd26afa5631f1ea0d2e382cc14e224b2399f46cd70ce41a14efb5f"   # households off, seed 7, 2 x 30, 6 months: since R96's refresh (5699f2e3..fc16477c; 14d051ac before); the D477 purge (711a98df / 276929d7; 9ae891d6 before); since S-year (the persons spec on editions by 2024-01; 8ed60dd8 after SB10; 63d2f2c6 after M002 G1, 84627f4f after the review fixes 1a, 1b, 2c; eaba489f before)
const ALONE := {"men": {"15-24": 0.185, "25-34": 0.288, "35-44": 0.170, "65-74": 0.167, "75-84": 0.127, "85+": 0.146},
	"women": {"15-24": 0.157, "25-34": 0.197, "35-44": 0.094, "65-74": 0.173, "75-84": 0.260, "85+": 0.256}}


func _in_band(a: int, band: String) -> bool:
	if band.ends_with("+"):
		return a >= int(band.trim_suffix("+"))
	var lh: PackedStringArray = band.split("-")
	return a >= int(lh[0]) and a <= int(lh[1])


func _init() -> void:
	var st = MS.new()
	st.load(2024, ["JPN"])
	var prefs: Dictionary = CANON.load_json("res://data/modern/polity/jpn_prefectures.json")["prefectures"]
	var p = PEOPLE.new()
	p.households = true
	var err: String = p.create("JPN", 1, st.cohort["JPN"], st.qx["JPN"], prefs, 300, 2024)
	check(err == "", "households built: " + err)
	# H1s-a, H1s-b
	var ts: Dictionary = HH.type_shares(p)
	var want := {"one_person": 0.381, "couple_only": 0.201, "couple_children": 0.251, "single_parent": 0.090, "other": 0.077}
	var ok_a: bool = true
	var txt_a: String = ""
	for t: String in want:
		ok_a = ok_a and absf(float(ts[t]) - float(want[t])) <= 0.03
		txt_a += " %s %.3f (%.3f)" % [t, ts[t], want[t]]
	check(ok_a, "H1s-a household types:%s; %d households, %d persons" % [txt_a, p.hh_n, p.n])
	check(absf(float(ts["mean_size"]) - 2.21) <= 0.1, "H1s-b mean household size %.3f (2.21 +- 0.1)" % ts["mean_size"])
	# H1s-c
	var ok_c: bool = true
	var txt_c: String = ""
	for sx: String in ALONE:
		var s: int = 0 if sx == "men" else 1
		for band: String in ALONE[sx]:
			var w: float = 0.0
			var a: float = 0.0
			for i: int in p.n:
				if p.sex[i] == s and _in_band(p.age[i], band):
					w += p.weight[i]
					if p.hh_type[p.hh_id[i]] == 0:
						a += p.weight[i]
			var sh: float = a / maxf(1e-9, w)
			ok_c = ok_c and absf(sh - float(ALONE[sx][band])) <= 0.05
			txt_c += " %s %s %.3f (%.3f)" % [sx, band, sh, ALONE[sx][band]]
	check(ok_c, "H1s-c living alone:" + txt_c)
	# H1s-d
	var w65: float = 0.0
	var arr := {"alone": 0.0, "couple_only": 0.0, "with_child": 0.0}
	for i2: int in p.n:
		if p.age[i2] < 65:
			continue
		w65 += p.weight[i2]
		var t2: int = p.hh_type[p.hh_id[i2]]
		if t2 == 0:
			arr["alone"] += p.weight[i2]
		elif t2 == 1:
			arr["couple_only"] += p.weight[i2]
		else:
			arr["with_child"] += p.weight[i2]
	var want65: Dictionary = p.hh_spec["checks"]["value"]["alive_65plus"]
	var ok_d: bool = true
	var txt_d: String = ""
	for k: String in ["alone", "couple_only", "with_child"]:
		var v: float = float(arr[k]) / maxf(1e-9, w65)
		ok_d = ok_d and absf(v - float(want65[k])) <= float(want65["tolerance"])
		txt_d += " %s %.3f (%.3f)" % [k, v, want65[k]]
	check(ok_d, "H1s-d the 65+:" + txt_d)
	# H1s-e
	var cells := PackedFloat64Array()
	cells.resize(10)
	var tw: float = 0.0
	for i3: int in p.n:
		cells[p.band_of(p.age[i3]) * 2 + p.sex[i3]] += p.weight[i3]
		tw += p.weight[i3]
	var ct := PackedFloat64Array()
	ct.resize(10)
	var ctt: float = 0.0
	for a2: int in p.AGES:
		for s2: int in 2:
			ct[p.band_of(a2) * 2 + s2] += p.cohort[a2 * 2 + s2]
			ctt += p.cohort[a2 * 2 + s2]
	var worst_cell: float = 0.0
	for c: int in 10:
		worst_cell = maxf(worst_cell, absf(cells[c] / tw - ct[c] / ctt))
	var worst_pref: float = 0.0
	var by := {}
	for i4: int in p.n:
		by[p.pref[i4]] = float(by.get(p.pref[i4], 0.0)) + p.weight[i4]
	for code: int in by:
		worst_pref = maxf(worst_pref, absf(float(by[code]) / float(p.pref_pop[code]) - 1.0))
	check(worst_cell <= 0.005 and worst_pref <= 0.001, "H1s-e the rake: worst age-sex cell %.4f pt, worst prefecture %.5f" % [100.0 * worst_cell, worst_pref])
	# H1s-f
	var same: bool = true
	for i5: int in p.n:
		same = same and p.weight[i5] == p.hh_weight[p.hh_id[i5]]
	check(same, "H1s-f one weight per household %s" % str(same))
	# H1s-h
	var sizes: Dictionary = HH._v(p, "mean_size_by_prefecture")
	var pw := {}
	var pp := {}
	for h: int in p.hh_n:
		if HH._private(p, h):
			pw[p.hh_pref[h]] = float(pw.get(p.hh_pref[h], 0.0)) + p.hh_weight[h]
			pp[p.hh_pref[h]] = float(pp.get(p.hh_pref[h], 0.0)) + p.hh_weight[h] * float((p.hh_members[h] as PackedInt32Array).size())
	var worst_size: float = 0.0
	var worst_code: int = 0
	for code3: int in pw:
		var d: float = absf(float(pp[code3]) / float(pw[code3]) - float(sizes["%02d" % code3]))
		if d > worst_size:
			worst_size = d
			worst_code = code3
	var w85: float = 0.0
	var i85: float = 0.0
	for i6: int in p.n:
		if p.sex[i6] == 1 and p.age[i6] >= 85:
			w85 += p.weight[i6]
			if p.hh_type[p.hh_id[i6]] == HH.INSTITUTION:
				i85 += p.weight[i6]
	check(worst_size <= 0.05 and absf(i85 / maxf(1e-9, w85) - 0.261) <= 0.02, "H1s-h prefecture mean size worst %.3f off (pref %d), women 85+ in an institution %.3f (0.261)" % [worst_size, worst_code, i85 / maxf(1e-9, w85)])
	# the effective sample size (reported, §10.4 ruling 4)
	var ks: Dictionary = HH.kish(p)
	var nmv: Dictionary = p.hh_spec["life_course"]["value"]["never_married"]["value"]
	var nlo: Array = nmv["ages"]
	var nw := PackedFloat64Array()
	nw.resize(nlo.size() * 2)
	var nn := PackedFloat64Array()
	nn.resize(nlo.size() * 2)
	var uw := PackedFloat64Array()
	uw.resize(nlo.size() * 2)
	var un := PackedFloat64Array()
	un.resize(nlo.size() * 2)
	for i9: int in p.n:
		var b9: int = p.HH._nm_band(p.age[i9], nlo)
		if b9 >= 0:
			nw[b9 * 2 + p.sex[i9]] += p.weight[i9]
			nn[b9 * 2 + p.sex[i9]] += p.weight[i9] if p.ever_married[i9] == 0 else 0.0
			uw[b9 * 2 + p.sex[i9]] += 1.0
			un[b9 * 2 + p.sex[i9]] += 1.0 if p.ever_married[i9] == 0 else 0.0
	var ok_m: bool = true
	var txt_m: String = ""
	for c9: int in nlo.size() * 2:
		var u9: float = un[c9] / maxf(1e-9, uw[c9])
		var t9: float = float(nmv["men" if c9 % 2 == 0 else "women"][c9 / 2])
		ok_m = ok_m and absf(u9 - t9) <= 0.02
		txt_m += " %s%d %.3f / wt %.3f (%.3f; short %.0f)" % ["MF"[c9 % 2], int(nlo[c9 / 2]), u9, nn[c9] / maxf(1e-9, nw[c9]), t9, p.lc_nm_short[c9]]
	check(ok_m, "H1s-m never married at the start, sample / weighted (R62; persons the start could not place):" + txt_m)
	check(true, "H1s-k (reported) Kish effective households within the prefectures %.0f of %d (%.0f%%); nationally %.0f (%.0f%%) and persons %.0f of %d (%.0f%%), both set by the uniform sample per prefecture" % [ks["households_eff_within"], ks["households"], 100.0 * ks["households_eff_within"] / ks["households"], ks["households_eff"], 100.0 * ks["households_eff"] / ks["households"], ks["persons_eff"], ks["persons"], 100.0 * ks["persons_eff"] / ks["persons"]])
	# H1s-g
	var q = PEOPLE.new()
	q.create("JPN", 7, st.cohort["JPN"], st.qx["JPN"], {"13": {"pop_thousand": 14178}, "47": {"pop_thousand": 1467}}, 30)
	for m: int in 6:
		q.step({"inflation_month": 0.02 / 12.0, "food_price_yoy": 0.0, "unemployment_rate": 0.025, "levers": []})
	check(q.digest() == P5_DIGEST and not q.to_dict().has("households"), "H1s-g households off: the recorded digest %s, no household key %s" % [str(q.digest() == P5_DIGEST), str(not q.to_dict().has("households"))])
	finish()
