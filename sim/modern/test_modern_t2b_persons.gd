extends "res://tools/test/test_kit.gd"
## T2.2b in the persons layer (ISS_TIERED §14.6 (8), (9); TO_E 13:29 (3), 13:47; declared at 11c2632a and 8ba0eefa before this code):
## households on, all prefectures, 2,000 a prefecture, seed 1, 120 months
## T2s-dt (persons) at years 1, 5 and 10: the weighted deaths at the yearly turns against E = Σ w q_x(2022) of the persons at their
##        turns, the 65+, 75+ and 85+ totals by sex within 2% x the horizon band (1 / 1.5 / 2) + 2.991 SE, SE = √(Σ w² q (1 − q)) ÷ E
##        (C 6 x R 3 at 5%); the single ages' worst (D − E) ÷ SE reported
## T2s-gp (persons) each January from month 13: the weighted grade shares by sex x 10-year band after the transitions against Σ π N,
##        z on Σ w² P (1 − P), within 3.953 (C 72 x R 9); the IPF residual under 1e-9
## T2s-gk (persons, M032 §4): the realised stay by class and grade reported; the persons 51-60 at month 13's January, always good and
##        always bad among the survivors at each wave, against R92's paths within 2 points at gaps 1, 5 and 9
##   godot --headless --path . --script res://sim/modern/test_modern_t2b_persons.gd
const PEOPLE = preload("res://sim/modern/people/people.gd")
const LC = preload("res://sim/modern/people/life_course.gd")
const MS = preload("res://sim/modern/modern_status.gd")
const CANON = preload("res://sim/modern/canon.gd")
const ENV := {"inflation_month": 0.02 / 12.0, "food_price_yoy": 0.0, "unemployment_rate": 0.025, "levers": []}
const N_PER := 2000
const Z_TOT := 2.991
const Z_GP := 4.581
const Z_4B := 4.175
const R92_PATHS := {1: [0.729, 0.108], 5: [0.582, 0.043], 9: [0.499, 0.027]}


func _init() -> void:
	var st = MS.new()
	st.load(2024, ["JPN"])
	var prefs: Dictionary = CANON.load_json("res://data/modern/polity/jpn_prefectures.json")["prefectures"]
	var t0: int = Time.get_ticks_msec()
	var h = PEOPLE.new()
	h.households = true
	var err: String = h.create("JPN", 1, st.cohort["JPN"], st.qx["JPN"], prefs, N_PER)
	check(err == "", "the persons layer built (households on, %d persons, %d ms)" % [h.n, Time.get_ticks_msec() - t0])
	var ages: int = ((LC._lc(h, "qx_2022") as Dictionary)["men"] as Array).size()
	var gp_bad: int = 0
	var gp_reads: int = 0
	var ipf_bad: int = 0
	var gp_txt: String = ""
	var b4_bad: int = 0
	var cohort: Dictionary = {}
	var gap: int = 0
	var gk_bad: int = 0
	var gk_txt: String = ""
	for y: int in 10:
		var d := PackedFloat64Array()
		d.resize(ages * 2)
		var e := PackedFloat64Array()
		e.resize(ages * 2)
		var v := PackedFloat64Array()
		v.resize(ages * 2)
		var t1: int = Time.get_ticks_msec()
		for mm: int in 12:
			if h.month == 0 and cohort.is_empty():
				for i0: int in h.n:
					if h.age[i0] >= 51 and h.age[i0] <= 60:
						cohort[h.pid[i0]] = [h.weight[i0], h.health[i0] < 2, h.health[i0] >= 2]
			var turn: Dictionary = {}
			for i: int in h.n:
				if h.month % 12 == int(h.pid[i] % 12):
					var a: int = mini(h.age[i], ages - 1)
					var mu: float = LC._mu(h, a, h.sex[i])
					turn[h.pid[i]] = [a * 2 + h.sex[i], h.weight[i], 1.0 if mu == INF else 1.0 - h.DM.exp(-mu)]
			h.step(ENV)
			var where: Dictionary = {}
			for i2: int in h.n:
				where[h.pid[i2]] = i2
			for pid in turn:
				var r: Array = turn[pid]
				var ix: int = int(r[0])
				var w: float = float(r[1])
				var q: float = float(r[2])
				e[ix] += w * q
				v[ix] += w * w * q * (1.0 - q)
				if not where.has(pid):
					d[ix] += w
			if not h.lc_t22b.is_empty():
				var tl: Dictionary = h.lc_t22b
				var gpr: Array = _gp(tl)
				gp_bad += int(gpr[0])
				gp_reads += 1
				for r4: int in 14:
					var v4: float = float(tl["b4_var"][r4])
					var z4: float = (float(tl["b4_after"][r4]) - float(tl["b4_target"][r4])) / sqrt(v4) if v4 > 0.0 else 0.0
					b4_bad += 1 if absf(z4) > Z_4B else 0
				ipf_bad += 0 if float(tl["res"]) < 1e-9 else 1
				if mm == 11:
					gp_txt += " year %d: December's cells beyond %d, worst |z| %.2f, IPF residual %s;" % [y + 1, int(gpr[0]), float(gpr[1]), String.num_scientific(float(tl["res"]))]
					print("REPORT T2s-gp / T2s-gk (persons, month %d, M035: the month's turning survivors) by sex x 10-year band, the grade shares before -> after (target) and the realised stay against the seed's; by class (stable | mobile):%s" % [h.month, String(gpr[2])])
			if mm == 11:
				gap += 1
				var alive_w: float = 0.0
				var good_w: float = 0.0
				var bad_w: float = 0.0
				for pid2 in cohort:
					var c: Array = cohort[pid2]
					if not where.has(pid2):
						continue
					var g: int = h.health[int(where[pid2])]
					c[1] = bool(c[1]) and g < 2
					c[2] = bool(c[2]) and g >= 2
					alive_w += float(c[0])
					good_w += float(c[0]) if bool(c[1]) else 0.0
					bad_w += float(c[0]) if bool(c[2]) else 0.0
				if R92_PATHS.has(gap) and alive_w > 0.0:
					var want: Array = R92_PATHS[gap]
					var ok: bool = absf(good_w / alive_w - float(want[0])) <= 0.02 and absf(bad_w / alive_w - float(want[1])) <= 0.02
					gk_bad += 0 if ok else 1
					gk_txt += " gap %d: always good %.3f (R92 %.3f), always bad %.3f (R92 %.3f) %s;" % [gap, good_w / alive_w, float(want[0]), bad_w / alive_w, float(want[1]), "in" if ok else "OUT"]
		print("REPORT year %d (persons): %d persons, %.0f s" % [y + 1, h.n, float(Time.get_ticks_msec() - t1) / 1000.0])
		if y == 0 or y == 4 or y == 9:
			var hb: float = 1.0 if y == 0 else (1.5 if y == 4 else 2.0)
			var bad: int = 0
			var txt: String = ""
			for s: int in 2:
				for lo: int in [65, 75, 85]:
					var dd: float = 0.0
					var ee: float = 0.0
					var vv: float = 0.0
					for a2: int in range(lo, ages):
						dd += d[a2 * 2 + s]
						ee += e[a2 * 2 + s]
						vv += v[a2 * 2 + s]
					var dev: float = dd / ee - 1.0 if ee > 0.0 else 0.0
					var se: float = sqrt(vv) / ee if ee > 0.0 else 0.0
					var lim: float = 0.02 * hb + Z_TOT * se
					bad += 1 if absf(dev) > lim else 0
					txt += " %s %d+: %.0f against %.0f (%+.2f%%, bound %.2f%%);" % ["men" if s == 0 else "women", lo, dd, ee, 100.0 * dev, 100.0 * lim]
			var worst: float = 0.0
			var wtxt: String = ""
			for ix2: int in ages * 2:
				if v[ix2] <= 0.0:
					continue
				var z: float = (d[ix2] - e[ix2]) / sqrt(v[ix2])
				if absf(z) > worst:
					worst = absf(z)
					wtxt = "%s age %d: %.0f against %.0f (z %.2f)" % ["men" if ix2 % 2 == 0 else "women", ix2 / 2, d[ix2], e[ix2], z]
			check(bad == 0, "T2s-dt (persons, year %d, §14.6 (8)) the weighted deaths at the yearly turns against Σ w q_x(2022): totals beyond 2%% x %.2f + %.3f SE %d of 6;%s the single ages' worst %s (reported)" % [y + 1, hb, Z_TOT, bad, txt, wtxt])
	check(gp_bad == 0 and gp_reads == 120 and ipf_bad == 0, "T2s-gp (persons, AMENDED, M035) every month, the turning survivors, within %.3f (C 90 x R 120): cells beyond %d in %d reads; IPF residuals at or above 1e-9 %d;%s" % [Z_GP, gp_bad, gp_reads, ipf_bad, gp_txt])
	check(b4_bad == 0 and gp_reads == 120, "T2s-4b (persons, AMENDED, M035) every month, the turning survivors' weighted 4b share by 5-year band x sex against LTCI's within %.3f (C 14 x R 120): cells beyond %d" % [Z_4B, b4_bad])
	check(gk_bad == 0 and gk_txt.count("gap") == 3, "T2s-gk (persons, M032 §4, M035) the persons 51-60 at month 0, always good and always bad among the survivors at each December, against R92's paths within 2 points at gaps 1, 5 and 9:%s" % gk_txt)
	finish()


func _gp(gp: Dictionary) -> Array:
	var beyond: int = 0
	var worst: float = 0.0
	var txt: String = ""
	var ng: int = 5
	for r: int in 18:
		var nb: float = 0.0
		for g0: int in ng:
			nb += float(gp["before"][r * ng + g0])
		if nb <= 0.0:
			continue
		var row: String = ""
		for g: int in ng:
			var x: int = r * ng + g
			var vv: float = float(gp["var"][x])
			var z: float = (float(gp["after"][x]) - float(gp["target"][x])) / sqrt(vv) if vv > 0.0 else 0.0
			beyond += 1 if absf(z) > Z_GP else 0
			worst = maxf(worst, absf(z))
			var bg: float = float(gp["before"][x])
			var cs: String = ""
			for c: int in 2:
				var nc: float = float(gp["n_c"][c * 18 * ng + x])
				cs += "%s%.3f" % ["" if c == 0 else "|", float(gp["stay_c"][c * 18 * ng + x]) / nc if nc > 0.0 else 0.0]
			row += " g%d %.3f -> %.3f (%.3f) stay %.3f (%.3f) %s" % [g + 1, bg / nb, float(gp["after"][x]) / nb, float(gp["target"][x]) / nb, float(gp["stay"][x]) / bg if bg > 0.0 else 0.0, float(gp["stay_seed"][x]) / bg if bg > 0.0 else 0.0, cs]
		txt += " %s %d-:%s;" % ["men" if r < 9 else "women", (r % 9) * 10, row]
	return [beyond, worst, txt]
