extends "res://tools/test/test_kit.gd"
## T2.2's DECADE RUN (TO_E 2026-11-01 10:31; ISS_CHECKS, declared at ffd3d4c7 before this code): the national tiers, seed 1, 120 months
## from January 2024, M025b's compression. Every month: T2s-m (no N < O), T2s-e, T2s-np, T2s-cx, T2s-c5x, T2s-ncp's cap, T2s-cp, T2s-ms,
## T2s-phi. Every year: T2s-a (each January the previous January one age younger less the year's cohort deaths). Years 1, 5 and 10:
## T2s-d within 3 binomial SE x the horizon band (1 / 1.5 / 2), T2s-d2 and the IPSS variants reported, T2s-dgq (14 at z 2.914, each year
## its own family), T2s-cb (3.682) and T2s-c5b (3.593) at the year's months 1, 6 and 12, T2s-qk (the stop rule at year 1, reported
## after), T2s-keff. Every year (REPORT): the cross-quartile merges and their Σμ per quartile x band cell, the year's and accumulated;
## the cost, the points and the couple entries
## T2s-drift (TO_E 10:40, M029; declared at 08b8777f): at years 1, 5 and 10 the worst cell's accumulated Σμ of married mass as a share
## of that cell's married mass, by quartile x 10-year band and by grade x 10-year band; a CHECK at year 10, under 1% in both (T)
## With T2s-drift's fix (TO_E 11:33; its form declared at eb550d08): the cap target max(K_b, quartiles present), so T2s-np's bound is
## ⌈1.5 x the target⌉ and T2s-cbq a CHECK at 0 every month; the grade as ln m_g weighted 4 in C2's z
## T2s-drift in M029b's STOCK form (TO_E 11:37; declared at e4dc2908): each cap merge's μ booked to the kept point, carried through its
## splits, merges and deaths; the year-10 CHECK reads it, the tallied form beside it
## M030 (TO_E 11:40; declared at b2a32fc2): the grade as cells inside each point; this run is the CHECK run for T2s-drift's stock form
## and the grade rows. T2s-c0 at month 0; T2s-gm (the cells' identities) and T2s-gx (the grade tables through C1, C2 and C5) every
## month; T2s-wg (REPORT) at month 0 and the widowings at years 1, 5 and 10; T2s-gc (REPORT) at the read years' months 1, 6 and 12;
## T2s-cost (REPORT) the month by step at months 1 and 12 and each year
##   godot --headless --path . --script res://sim/modern/test_modern_t2_decade.gd
## V120b (TO_E 12:40): every family covers all the row's reads in the run (§R rule 5): T2s-cb 216 cells x 9 reads, 4.208; T2s-c5b
## 153 x 9, 4.130; T2s-dgq 14 x 3, 3.241; T2s-d 36 x 3 at a base of 3.19 x the horizon band; each read prints its worst cell
const PEOPLE = preload("res://sim/modern/people/people.gd")
const TR = preload("res://sim/modern/people/tiers.gd")
const LC = preload("res://sim/modern/people/life_course.gd")
const MS = preload("res://sim/modern/modern_status.gd")
const CANON = preload("res://sim/modern/canon.gd")
const ENV := {"inflation_month": 0.02 / 12.0, "food_price_yoy": 0.0, "unemployment_rate": 0.025, "levers": []}


const Z_DGQ := 3.241
const Z_CB := 4.208
const Z_C5B := 4.130
const Z_D := 3.19
const Z_DT := 3.937
const Z_GP := 4.581
const Z_4B := 4.175
## R92's always-good / always-bad shares of the 51-60 cohort at gaps 1, 5 and 9 years (M032 §2's observed row)
const R92_PATHS := {1: [0.729, 0.108], 5: [0.582, 0.043], 9: [0.499, 0.027]}
const Z95 := 1.959964
## R74's model rows [id, sex (0 men), numerator grade, denominator grade, value, ci lo, ci hi] and M010's main set [id, sex, age at risk,
## y, se], as test_modern_t2_deaths.gd transcribes them (R74, M010 v2 at math-reports 7ac5b83d)
const R74_ROWS := [["R74-0001 AGES 1B M, grade 3 / grade 1", 0, 2, 0, 2.44, 2.14, 2.80], ["R74-0005 AGES 1B F, grade 3 / grade 1", 1, 2, 0, 1.88, 1.44, 2.47],
	["R74-0024 NIPPON DATA90 model 2 M, grade 4 / grade 3", 0, 3, 2, 1.31, 1.00, 1.73], ["R74-0025 NIPPON DATA90 model 2 F, grade 4 / grade 3", 1, 3, 2, 1.43, 1.10, 1.84]]
const M010_OBS := [["R73-009 M", 0, 72.5, 0.19845093872383832, 0.0742863177222006], ["R73-011 M", 0, 82.0, -0.01980262729617973, 0.059713500781834496], ["R73-013 F", 1, 72.5, 0.4942963218147801, 0.12385631052695982], ["R73-015 F", 1, 82.0, -0.17395330712343798, 0.08945492733006984], ["R73-018 M", 0, 67.0, 0.1906203596086497, 0.21707234911538092], ["R73-019 M", 0, 67.0, 0.3852624007906449, 0.1768265095755335], ["R73-020 F", 1, 67.0, 0.11332868530700327, 0.3777484055047742], ["R73-021 F", 1, 67.0, -0.40047756659712525, 0.3216049269135736], ["R73-001/R73-002/R73-003 M", 0, 75.0, 0.3401754717150547, 0.07208801532958557], ["R73-005/R73-006/R73-007 F", 1, 75.0, 0.38236080054220545, 0.21163082095381233]]



func _init() -> void:
	var st = MS.new()
	st.load(2024, ["JPN"])
	var prefs: Dictionary = CANON.load_json("res://data/modern/polity/jpn_prefectures.json")["prefectures"]
	var t0: int = Time.get_ticks_msec()
	var p = PEOPLE.new()
	p.tiers = true
	p.create("JPN", 1, st.cohort["JPN"], st.qx["JPN"], prefs, 0, 2024)
	check(p.error == "", "tiers built: '%s' (%d units, %d points, %d couple points, %d ms)" % [p.error, p.tr_units, p.tr_pt_off[p.tr_units], p.tr_cp_n.size(), Time.get_ticks_msec() - t0])
	var tot0: int = _sum(p.tr_count)
	var cp0: int = _sum(p.tr_cp_n)
	var bad: Dictionary = {"m": 0, "e": 0, "c": 0, "cp": 0, "ms": 0, "phi": 0, "lost": 0, "lost_hm": 0, "clamped": 0, "cx": 0, "c5x": 0, "c5_over": 0, "a": 0, "cbq": 0, "gm": 0, "gx": 0, "gp": 0, "gp_reads": 0, "ipf": 0}
	var gp_txt: String = ""
	var paths: Array = _paths_start(p)
	var acc: Dictionary = {}
	var gk_txt: String = ""
	var gk_bad: int = 0
	_t2s_c0(p)
	_t2s_c0c(p)
	_t2s_wg0(p)
	var mix0: PackedFloat64Array = _grade_mix(p)
	print("REPORT the grade mix by age (TO_E 13:23) at month 0, by sex x 10-year band (grade 1 .. 4 shares):%s" % _mix_txt(mix0, mix0))
	var phi_n: int = 0
	var dead: int = 0
	var lost_cp: int = 0
	var cb_acc_m := PackedFloat64Array()
	cb_acc_m.resize(36)
	var cb_acc_c := PackedFloat64Array()
	cb_acc_c.resize(36)
	var cbg_acc := PackedFloat64Array()
	cbg_acc.resize(36)
	var a_txt: String = ""
	var pop_j: PackedInt64Array = _pop(p)
	for y: int in 10:
		var yr: Dictionary = {}
		var y_cb_m := PackedFloat64Array()
		y_cb_m.resize(36)
		var y_cb_c := PackedFloat64Array()
		y_cb_c.resize(36)
		var y_cbq: int = 0
		var y_cbq_mass: int = 0
		var y_usec: int = 0
		var read_year: bool = y == 0 or y == 4 or y == 9
		var y_cbg := PackedFloat64Array()
		y_cbg.resize(36)
		var cb_bad: int = 0
		var cb_txt: String = ""
		var c5b_bad: int = 0
		var c5b_txt: String = ""
		var y_steps: Dictionary = {}
		var y_wg: Dictionary = {}
		var gc_txt: String = ""
		for mm: int in 12:
			var m: int = y * 12 + mm
			var phi_of: Dictionary = {}
			for g: int in p.tr_pt_id.size():
				phi_of[p.tr_pt_id[g]] = p.tr_points["phi"][g]
			p.step(ENV)
			var tl: Dictionary = p.tr_margins["t22"]
			y_usec += int(tl["usec"])
			for sk: String in tl["usec_by_step"]:
				y_steps[sk] = int(y_steps.get(sk, 0)) + int(tl["usec_by_step"][sk])
			if m == 0 or m == 11:
				print("REPORT T2s-cost (month %d) %d s: %s" % [m + 1, int(tl["usec"]) / 1000000, _steps_txt(tl["usec_by_step"], 1)])
			for wk: String in ["wg_n", "wg_x", "wg_e", "wg_v"]:
				if not y_wg.has(wk):
					y_wg[wk] = (tl[wk] as PackedFloat64Array).duplicate()
				else:
					for x8: int in (tl[wk] as PackedFloat64Array).size():
						y_wg[wk][x8] += tl[wk][x8]
			if tl.has("t22b"):
				var gp0: Dictionary = tl["t22b"]
				var gpr: Array = _t2s_gp(gp0, Z_GP)
				bad["gp"] = int(bad["gp"]) + int(gpr[0])
				bad["gp_reads"] = int(bad["gp_reads"]) + 1
				bad["ipf"] = int(bad["ipf"]) + (0 if float(gp0["res"]) < 1e-9 else 1)
				var b4: Array = _t2s_4b(gp0, Z_4B)
				bad["4b"] = int(bad.get("4b", 0)) + int(b4[0])
				_paths_add(gp0, acc)
				if mm == 11:
					gp_txt += " year %d: December's cells beyond %d, worst |z| %.2f, IPF residual %s, re-graded %d;" % [y + 1, int(gpr[0]), float(gpr[1]), String.num_scientific(float(gp0["res"])), int(gp0["moved"])]
					print("REPORT T2s-4b / T2s-4bx (month %d, M035: the month's arrivals) the 4b share by 5-year band x sex against LTCI's, z, and 4b's exit to 4a at the birthday:%s" % [m + 1, String(b4[1])])
					print("REPORT T2s-gp / T2s-gk (month %d, M035: the month's arrivals) by sex x 10-year band, the arrivals' state shares before -> after (target) and the realised stay against the seed's; by class (stable | mobile):%s" % [m + 1, String(gpr[2])])
					var gap: int = _paths_year(p, paths, acc)
					acc = {}
					if R92_PATHS.has(gap):
						var sh: Array = _paths_share(paths)
						var want: Array = R92_PATHS[gap]
						var ok: bool = absf(float(sh[0]) - float(want[0])) <= 0.02 and absf(float(sh[1]) - float(want[1])) <= 0.02
						gk_bad += 0 if ok else 1
						gk_txt += " gap %d: always good %.3f (R92 %.3f), always bad %.3f (R92 %.3f) %s;" % [gap, float(sh[0]), float(want[0]), float(sh[1]), float(want[1]), "in" if ok else "OUT"]
			var gm_bad: int = TR.grade_identity(p)
			bad["gm"] = int(bad["gm"]) + gm_bad
			bad["gx"] = int(bad["gx"]) + int(tl["gx"])
			if gm_bad > 0 or int(tl["gx"]) > 0:
				print("NOTE month %d: T2s-gm violations %d, T2s-gx cells off their ledgers %d by stage %s" % [m + 1, gm_bad, int(tl["gx"]), str(tl["gx_by_stage"])])
			if read_year and (mm == 0 or mm == 5 or mm == 11):
				gc_txt += " month %d %.3f;" % [m + 1, _gc(p)]
			bad["clamped"] = int(bad["clamped"]) + int(tl["clamped"])
			bad["cx"] = int(bad["cx"]) + int(tl["cx_bad"])
			bad["c5x"] = int(bad["c5x"]) + int(tl["c5_x"])
			bad["c5_over"] = int(bad["c5_over"]) + int(tl["c5_over"])
			y_cbq += int(tl["cbq"])
			bad["cbq"] = int(bad["cbq"]) + int(tl["cbq"])
			y_cbq_mass += int(tl["cbq_mass"])
			for x6: int in 36:
				y_cb_m[x6] += float(tl["cb_mm"][x6])
				y_cb_c[x6] += float(tl["cb_cm"][x6])
				cbg_acc[x6] += float(tl["cbg_m"][x6])
				y_cbg[x6] += float(tl["cbg_m"][x6])
			if read_year and (mm == 0 or mm == 5 or mm == 11):
				var worst: float = -1.0
				var wc: String = ""
				for x: int in 36:
					for pr2: Array in [["cb_mr", "cb_mv", "cb_mm"], ["cb_cr", "cb_cv", "cb_cm"]]:
						var r: float = float(tl[pr2[0]][x]) - float(tl[pr2[2]][x])
						var v: float = float(tl[pr2[1]][x])
						var z: float = absf(r) / sqrt(v) if v > 0.0 else (0.0 if absf(r) < 1e-9 else INF)
						if z > worst:
							worst = z
							wc = "%s quartile %d band %d0-: r %.1f, μ %.1f, σ %.1f, z %.2f" % ["married" if pr2[0] == "cb_mr" else "couple", x / 9, x % 9, float(tl[pr2[0]][x]), float(tl[pr2[2]][x]), sqrt(v), z]
						cb_bad += 1 if z > Z_CB else 0
				cb_txt += " month %d worst cell %s;" % [m + 1, wc]
				var w5: float = -1.0
				var wc5: String = ""
				for x5: int in 153:
					var r5: float = float(tl["c5_r"][x5])
					var v5: float = float(tl["c5_v"][x5])
					var z5: float = absf(r5) / sqrt(v5) if v5 > 0.0 else (0.0 if r5 == 0.0 else INF)
					if z5 > w5:
						w5 = z5
						wc5 = ("wife quartile %d husband quartile %d husband band %d0-" % [x5 / 36, (x5 / 9) % 4, x5 % 9] if x5 < 144 else "both-earning band %d0-" % (x5 - 144)) + (": r %.1f, μ 0, σ %.1f, z %.2f" % [r5, sqrt(v5), z5])
					c5b_bad += 1 if z5 > Z_C5B else 0
				c5b_txt += " month %d worst cell %s;" % [m + 1, wc5]
			dead += int(tl["deaths"])
			lost_cp += int(tl["couples_lost"])
			for key: String in ["d_as", "d_old", "x_as", "e_as", "v_as", "d_g", "x_g", "d_k", "x_k"]:
				if not yr.has(key):
					yr[key] = tl[key].duplicate()
				else:
					for x: int in (tl[key] as Array).size():
						yr[key][x] += tl[key][x]
			bad["m"] = int(bad["m"]) + _t2s_m(p)
			var pts: int = _sum(p.tr_pt_mass)
			bad["e"] = int(bad["e"]) + (0 if _sum(p.tr_count) == tot0 - dead and pts == tot0 - dead else 1)
			bad["c"] = int(bad["c"]) + _t2s_c(p)
			bad["lost"] = int(bad["lost"]) + int(tl.get("lost", 0))
			bad["lost_hm"] = int(bad["lost_hm"]) + int(tl.get("lost_hm", 0))
			bad["cp"] = int(bad["cp"]) + _t2s_cp(p, cp0 - lost_cp) + (0 if int(tl["widowed"]) == int(tl["couples_lost"]) else 1)
			bad["ms"] = int(bad["ms"]) + _t2s_ms(p)
			var where: Dictionary = {}
			for g2: int in p.tr_pt_id.size():
				where[p.tr_pt_id[g2]] = g2
			for pr: Array in tl["split_src"]:
				if where.has(int(pr[0])):
					phi_n += 1
					bad["phi"] = int(bad["phi"]) + (0 if float(p.tr_points["phi"][int(where[int(pr[0])])]) == float(phi_of[int(pr[1])]) else 1)
		# T2s-a, the year's cohort identity
		var old_left: int = 0
		for u: int in p.tr_units:
			var b: int = p.tr_key[u * TR.KEY_STRIDE + 1]
			for g3: int in range(p.tr_pt_off[u], p.tr_pt_off[u + 1]):
				for sl: int in TR.AGE_SLOTS:
					if b * 5 + sl < p.AGES - 1:
						old_left += p.tr_pt_old[g3 * TR.AGE_SLOTS + sl]
		var pop_e: PackedInt64Array = _pop(p)
		var d_as: PackedInt64Array = yr["d_as"]
		var d_old: PackedInt64Array = yr["d_old"]
		var off: int = 0
		var top: int = p.AGES - 1
		for s: int in 2:
			for a: int in p.AGES:
				var want: int = 0
				if a == top:
					want = pop_j[(top - 1) * 2 + s] - d_old[(top - 1) * 2 + s] + pop_j[top * 2 + s] - d_as[top * 2 + s]
				elif a > 0:
					want = pop_j[(a - 1) * 2 + s] - d_old[(a - 1) * 2 + s] - (d_as[a * 2 + s] - d_old[a * 2 + s])
				off += 0 if pop_e[a * 2 + s] == want else 1
		bad["a"] = int(bad["a"]) + off + (1 if old_left > 0 else 0)
		a_txt += " year %d: %d cells off, unaged left %d;" % [y + 1, off, old_left]
		pop_j = pop_e
		# the cross-quartile tally (REPORT)
		var ym_txt: String = ""
		var acc_max: float = 0.0
		for x7: int in 36:
			cb_acc_m[x7] += y_cb_m[x7]
			cb_acc_c[x7] += y_cb_c[x7]
			acc_max = maxf(acc_max, absf(cb_acc_m[x7]))
			ym_txt += " %d|%d %.1f/%.1f (acc %.1f/%.1f);" % [x7 / 9, x7 % 9, y_cb_m[x7], y_cb_c[x7], cb_acc_m[x7], cb_acc_c[x7]]
		print("REPORT the cross-quartile tally (TO_E 10:31 (1)) year %d: merges %d, mass %d; Σμ married / couple mass per quartile|band cell (the year's, accumulated):%s" % [y + 1, y_cbq, y_cbq_mass, ym_txt])
		print("REPORT year %d: the tiers' months %d s (%.0f s a month); points %d, couple entries %d, units %d; deaths in the year %d; the largest accumulated |Σμ| married by quartile x band %.1f" % [y + 1, y_usec / 1000000, float(y_usec) / 12e6, p.tr_pt_off[p.tr_units], p.tr_cp_n.size(), p.tr_units, _sum(d_as), acc_max])
		print("REPORT T2s-cost (year %d, a month's mean by step) %s" % [y + 1, _steps_txt(y_steps, 12)])
		if read_year:
			var label: String = "year %d" % (y + 1)
			var h: float = 1.0 if y == 0 else (1.5 if y == 4 else 2.0)
			_t2s_d(p, yr, h, label)
			_t2s_dt(p, yr, h, label)
			print("REPORT T2s-4bx (%s, T2.2c) 4b's yearly death rate by 5-year band x sex (deaths ÷ person-years; LTCI's continuous-recipient loss 22-38%% an upper bound):%s" % [label, _4b_deaths(p, yr)])
			print("REPORT the grade mix by age (TO_E 13:23) at the end of %s, by sex x 10-year band (grade 1 .. 4 shares; month 0's in brackets):%s" % [label, _mix_txt(_grade_mix(p), mix0)])
			var gr: Array = _t2s_dgq(p, yr, label)
			_t2s_qk(p, yr, st, y == 0, label)
			check(cb_bad == 0, "T2s-cb (%s, at %.3f on (r − μ) ÷ σ) the cap's married and couple masses by quartile x 10-year band at the year's months 1, 6, 12: cells beyond %d of 216;%s" % [label, Z_CB, cb_bad, cb_txt])
			check(c5b_bad == 0, "T2s-c5b (%s, at %.3f) C5's change of the couples at the year's months 1, 6, 12: cells beyond %d of 153;%s" % [label, Z_C5B, c5b_bad, c5b_txt])
			print("REPORT T2s-keff (%s) the mass-weighted median K_eff ÷ K_b %.3f" % [label, _keff(p)])
			print("REPORT T2s-gc (%s, M030 §6; predicted 1.0, 1.3-1.8, 1.5-2.5 at months 1, 6, 12 of year 1) the mean non-zero grade cells per (point, age):%s" % [label, gc_txt])
			_t2s_wg(y_wg, label)
			var cm: Array = _married_cells(p)
			var dq: Array = _worst_share(cb_acc_m, cm[0])
			var dg: Array = _worst_share(cbg_acc, cm[1])
			var st_m: Array = _stock_cells(p)
			var sq: Array = _worst_share(st_m[0], cm[0])
			var sg: Array = _worst_share(st_m[1], cm[1])
			var stxt: String = "STOCK form: quartile x band worst cell %d|%d: booked μ %.1f of %.0f married (%.3f%%); grade x band worst cell %d|%d: booked μ %.1f of %.0f married (%.3f%%)" % [int(sq[0]) / 9, int(sq[0]) % 9, float(sq[1]), float(sq[2]), 100.0 * float(sq[3]), int(sg[0]) / 9, int(sg[0]) % 9, float(sg[1]), float(sg[2]), 100.0 * float(sg[3])]
			var dtxt: String = "quartile x band worst cell %d|%d: Σμ %.1f of %.0f married (%.3f%%); grade x band worst cell %d|%d: Σμ %.1f of %.0f married (%.3f%%)" % [int(dq[0]) / 9, int(dq[0]) % 9, float(dq[1]), float(dq[2]), 100.0 * float(dq[3]), int(dg[0]) / 9, int(dg[0]) % 9, float(dg[1]), float(dg[2]), 100.0 * float(dg[3])]
			if y == 9:
				check(float(sq[3]) < 0.01 and float(sg[3]) < 0.01, "T2s-drift (year 10, the STOCK form, TO_E 11:37; the 1%% materiality, T) %s" % stxt)
				print("REPORT T2s-drift (year 10, the TALLIED form beside it) %s" % dtxt)
			else:
				print("REPORT T2s-drift (%s) %s; TALLIED form: %s" % [label, stxt, dtxt])
			var gy: String = ""
			for x9: int in 36:
				gy += " %d|%d %.1f (acc %.1f);" % [x9 / 9, x9 % 9, y_cbg[x9], cbg_acc[x9]]
			print("REPORT T2s-cbg (%s) Σμ married by grade|band (the year's, accumulated):%s" % [label, gy])
	check(int(bad["a"]) == 0, "T2s-a every year: cells off the previous January one age younger less the year's cohort deaths, or unaged mass left after December:%s" % a_txt)
	check(int(bad["m"]) == 0 and int(bad["clamped"]) == 0, "T2s-m every month for 120 months: off its identities %d; cells whose N fell below O %d" % [int(bad["m"]), int(bad["clamped"])])
	check(int(bad["e"]) == 0, "T2s-e every month: months off the start's %d persons less the deaths so far (%d in ten years) %d" % [tot0, dead, int(bad["e"])])
	check(int(bad["c"]) == 0 and int(bad["lost"]) == 0, "T2s-np every month: units above ⌈1.5 K_b⌉ %d; couple mass left on dropped points %d; household-entry mass on fully dead points %d (reported until T2.3)" % [int(bad["c"]), int(bad["lost"]), int(bad["lost_hm"])])
	check(int(bad["cbq"]) == 0, "T2s-cbq (T2s-drift's fix, TO_E 11:33) every month: cross-quartile merges %d" % int(bad["cbq"]))
	var extra: int = 0
	for u9: int in p.tr_units:
		var l9: Array = range(p.tr_pt_off[u9], p.tr_pt_off[u9 + 1])
		extra += maxi(0, l9.size() - int(ceil(1.5 * float(maxi(1, p.tr_kb[u9])))))
	print("REPORT T2s-np (the fix) points above ⌈1.5 K_b⌉ at month 120 %d, of %d points" % [extra, p.tr_pt_off[p.tr_units]])
	check(int(bad["cx"]) == 0, "T2s-cx every month: units whose extensive totals moved in the compression %d" % int(bad["cx"]))
	check(int(bad["c5x"]) == 0 and int(bad["c5_over"]) == 0, "T2s-c5x (marginals only) / T2s-ncp every month: blocks whose couples moved in C5 %d, blocks above their cap %d" % [int(bad["c5x"]), int(bad["c5_over"])])
	check(int(bad["cp"]) == 0, "T2s-cp (until T2.3) every month: off %d (Σ couples against the start's %d less the %d ended)" % [int(bad["cp"]), cp0, lost_cp])
	check(int(bad["ms"]) == 0, "T2s-ms every month: points off %d" % int(bad["ms"]))
	check(int(bad["gm"]) == 0, "T2s-gm (M030 §6, identity) every month for 120 months: the grade cells against the age, January and unaged masses, T's rows against the marital masses and its columns against the grade masses, every cell at least 0: violations %d" % int(bad["gm"]))
	check(int(bad["gx"]) == 0, "T2s-gx (M030 §6, EXTENDED §14.6 (6), exact) every month: cells of the marital masses by grade x sex x 10-year band and the mass by grade x sex x single age off their stage's ledger (the ageing and its splits, the deaths and widowing, C1, C2 and the rebuild, C5) %d" % int(bad["gx"]))
	check(int(bad["phi"]) == 0 and phi_n > 0, "T2s-phi %d split points read, φ off its source's bits %d" % [phi_n, int(bad["phi"])])
	var accg: float = 0.0
	for x8: int in 36:
		accg = maxf(accg, absf(cbg_acc[x8]))
	print("REPORT T2s-cbg the ten years' accumulated Σμ of married mass by grade x band, largest cell %.1f" % accg)
	check(int(bad["gp"]) == 0 and int(bad["gp_reads"]) == 120 and int(bad["ipf"]) == 0, "T2s-gp (AMENDED, M035 §14.6 (14)) every month: the arrivals' state shares by sex x 10-year band against π(a) Σ n within %.3f (C 90 x R 120): cells beyond %d in %d reads; IPF residuals at or above 1e-9 %d;%s" % [Z_GP, int(bad["gp"]), int(bad["gp_reads"]), int(bad["ipf"]), gp_txt])
	check(int(bad.get("4b", 0)) == 0 and int(bad["gp_reads"]) == 120, "T2s-4b (AMENDED, M035 §14.6 (14)) every month: the arrivals' 4b share by 5-year band (65-69 .. 95+) x sex against LTCI's within %.3f (C 14 x R 120): cells beyond %d" % [Z_4B, int(bad.get("4b", 0))])
	check(gk_bad == 0 and gk_txt.count("gap") == 3, "T2s-gk (AMENDED, M032 §4, M035) the 51-60 stock of month 0, by composition of each year's arrivals' realised P_c mass-weighted over the months (no deaths), always good and always bad against R92's paths within 2 points at gaps 1, 5 and 9:%s" % gk_txt)
	_gx_must_fail(p)
	finish()


## The married mass by quartile x 10-year band and by grade x 10-year band (36 each, the grade from the cells' T), at the month's end
func _married_cells(p: RefCounted) -> Array:
	var q := PackedFloat64Array()
	q.resize(36)
	var g := PackedFloat64Array()
	g.resize(9 * TR.NG)
	for u: int in p.tr_units:
		var b10: int = LC._b10(p.tr_key[u * TR.KEY_STRIDE + 1] * 5)
		for j: int in range(p.tr_pt_off[u], p.tr_pt_off[u + 1]):
			var mm: float = float(p.tr_pt_ms[j * 4 + 1])
			q[p.tr_pt_q[j] * 9 + b10] += mm
			for gr: int in TR.NG:
				g[gr * 9 + b10] += float(p.tr_pt_T[j * 4 * TR.NG + TR.NG + gr])
	return [q, g]


## T2s-drift's stock form: the points' booked μ by their current quartile x 10-year band and by the start's grade x 10-year band
## (M030: no μ is booked on the grade lines, so the grade read is 0 whatever the grade it is filed under)
func _stock_cells(p: RefCounted) -> Array:
	var q := PackedFloat64Array()
	q.resize(36)
	var g := PackedFloat64Array()
	g.resize(9 * TR.NG)
	for u: int in p.tr_units:
		var b10: int = LC._b10(p.tr_key[u * TR.KEY_STRIDE + 1] * 5)
		for j: int in range(p.tr_pt_off[u], p.tr_pt_off[u + 1]):
			q[p.tr_pt_q[j] * 9 + b10] += p.tr_pt_muq[j]
			g[int(p.tr_points["health"][j]) * 9 + b10] += p.tr_pt_mug[j]
	return [q, g]


## [the cell, its |Σμ|, its married mass, the share] of the cell whose |Σμ| ÷ married mass is the largest (cells of at least 1 married)
func _worst_share(acc: PackedFloat64Array, mass: PackedFloat64Array) -> Array:
	var best: Array = [0, 0.0, 0.0, 0.0]
	for x: int in acc.size():
		if mass[x] < 1.0:
			continue
		var sh: float = absf(acc[x]) / mass[x]
		if sh > float(best[3]):
			best = [x, absf(acc[x]), mass[x], sh]
	return best


## The mass-weighted median of K_eff ÷ K_b over units
func _keff(p: RefCounted) -> float:
	var ke: Array = []
	var tot: float = 0.0
	for u: int in p.tr_units:
		var sw: float = 0.0
		var sw2: float = 0.0
		for g: int in range(p.tr_pt_off[u], p.tr_pt_off[u + 1]):
			sw += float(p.tr_pt_mass[g])
			sw2 += float(p.tr_pt_mass[g]) * float(p.tr_pt_mass[g])
		if sw > 0.0:
			ke.append([sw * sw / sw2 / float(maxi(1, p.tr_kb[u])), sw])
			tot += sw
	ke.sort()
	var acc: float = 0.0
	for r: Array in ke:
		acc += float(r[1])
		if acc >= tot * 0.5:
			return float(r[0])
	return 0.0


## T2s-d by sex x 5-year band (checked) and T2s-d2 by single age x sex (reported), the year's deaths against Σ q_m x the masses at risk
func _t2s_d(p: RefCounted, yr: Dictionary, h: float = 1.0, label: String = "year 1") -> void:
	p.month -= 1
	var mu: PackedFloat64Array = TR.mu_path(p)
	var mu_hi: PackedFloat64Array = TR.mu_path(p, "high")
	var mu_lo: PackedFloat64Array = TR.mu_path(p, "low")
	p.month += 1
	var hi_lo: String = ""
	for s0: int in 2:
		var d0: float = 0.0
		var r_m: float = 0.0
		var r_h: float = 0.0
		var r_l: float = 0.0
		for a0: int in range(65, p.AGES):
			var ix0: int = a0 * 2 + s0
			var x0: float = float(yr["x_as"][ix0])
			d0 += float(yr["d_as"][ix0])
			r_m += (mu[ix0] if mu[ix0] != INF else 1.0) * x0
			r_h += (mu_hi[ix0] if mu_hi[ix0] != INF else 1.0) * x0
			r_l += (mu_lo[ix0] if mu_lo[ix0] != INF else 1.0) * x0
		hi_lo += " %s 65+: %d deaths against the rate x person-years %.0f (IPSS medium), %.0f (high), %.0f (low);" % ["m" if s0 == 0 else "f", int(d0), r_m, r_h, r_l]
	print("REPORT T2s-d (%s) the deaths against IPSS 2023's variants (the year's own ratio):%s" % [label, hi_lo])
	var miss: int = 0
	var txt: String = ""
	var rep: String = ""
	for s: int in 2:
		for b: int in TR.BANDS:
			var d: float = 0.0
			var e: float = 0.0
			var v: float = 0.0
			var qx: float = 0.0
			for a: int in range(b * 5, p.AGES if b == TR.BANDS - 1 else b * 5 + 5):
				d += float(yr["d_as"][a * 2 + s])
				e += float(yr["e_as"][a * 2 + s])
				v += float(yr["v_as"][a * 2 + s])
				qx += mu[a * 2 + s] * float(yr["x_as"][a * 2 + s]) if mu[a * 2 + s] != INF else float(yr["x_as"][a * 2 + s])
			var z: float = (d - e) / sqrt(v) if v > 0.0 else 0.0
			if absf(z) > Z_D * h:
				miss += 1
				txt += " %s %d-: %d against %.0f (z %.2f);" % ["m" if s == 0 else "f", b * 5, int(d), e, z]
			if b >= 13:
				rep += " %s %d-: %d against the rate x person-years %.0f;" % ["m" if s == 0 else "f", b * 5, int(d), qx]
	check(miss == 0, "T2s-d (AMENDED, %s; a read-back of the sampler, TO_E 13:23) the year's deaths by sex x 5-year band against Σ q_m x the masses at risk, %.2f binomial SE x the horizon band %.2f: %d of 36 outside;%s" % [label, Z_D, h, miss, txt])
	print("REPORT T2s-d (%s) against the rate −ln(1 − q_x(t)) x the person-years at 65+, t the year's own:%s" % [label, rep])
	var miss2: int = 0
	for ix: int in p.AGES * 2:
		var v2: float = float(yr["v_as"][ix])
		if v2 > 0.0 and absf(float(yr["d_as"][ix]) - float(yr["e_as"][ix])) > 3.0 * sqrt(v2):
			miss2 += 1
	print("REPORT T2s-d2 (%s) the year's deaths by single age x sex: %d of %d cells beyond 3 SE (about %.1f expected by chance)" % [label, miss2, p.AGES * 2, 0.0027 * float(p.AGES * 2)])


## Mantel-Haenszel rate ratio of group n over group r over strata [d_n, T_n, d_r, T_r], with the Robins-Breslow-Greenland variance of its log
func _mh(rows: Array) -> Array:
	var num: float = 0.0
	var den: float = 0.0
	var vn: float = 0.0
	for r: Array in rows:
		var t: float = float(r[1]) + float(r[3])
		if t <= 0.0 or float(r[1]) <= 0.0 or float(r[3]) <= 0.0:
			continue
		num += float(r[0]) * float(r[3]) / t
		den += float(r[2]) * float(r[1]) / t
		vn += (float(r[0]) + float(r[2])) * float(r[1]) * float(r[3]) / (t * t)
	if num <= 0.0 or den <= 0.0:
		return [0.0, INF]
	return [num / den, vn / (num * den)]


## T2s-dgq's 14 comparisons; returns [the grade rows all inside, the income rows all inside]
func _t2s_dgq(p: RefCounted, yr: Dictionary, label: String, as_check: bool = true) -> Array:
	var miss_g: int = 0
	var txt: String = ""
	for row: Array in R74_ROWS:
		var strata: Array = []
		for a: int in range(65, p.AGES):
			var ix: int = a * 2 + int(row[1])
			strata.append([_gsum(yr["d_g"], ix, int(row[2])), _gsum(yr["x_g"], ix, int(row[2])), _gsum(yr["d_g"], ix, int(row[3])), _gsum(yr["x_g"], ix, int(row[3]))])
		var mh: Array = _mh(strata)
		var mgv: Array = LC._lc(p, "death_multiplier")
		var l: float = log(float(mgv[int(row[2])]) / float(mgv[int(row[3])]))
		var lr: float = log(float(mh[0])) if float(mh[0]) > 0.0 else -INF
		var band: float = Z_DGQ * sqrt(float(mh[1]))
		var inside: bool = band < INF and absf(lr - l) <= band
		miss_g += 0 if inside else 1
		txt += " %s model %.3f against the m_g in use %.3f ± %.3f in log %s (source %.2f, beside);" % [row[0], float(mh[0]), exp(l), band, "in" if inside else "OUT", float(row[4])]
	var f: Dictionary = LC._lc(p, "death_income_factor")
	var miss_k: int = 0
	for o: Array in M010_OBS:
		var strata2: Array = []
		var a0: int = int(round(float(o[2])))
		for a2: int in range(a0 - 2, a0 + 3):
			var ix2: int = a2 * 2 + int(o[1])
			strata2.append([yr["d_k"][ix2 * 4 + 3], yr["x_k"][ix2 * 4 + 3], yr["d_k"][ix2 * 4], yr["x_k"][ix2 * 4]])
		var mh2: Array = _mh(strata2)
		var y: float = log(float(mh2[0])) / 1.5 if float(mh2[0]) > 0.0 else -INF
		var band2: float = Z_DGQ * sqrt(float(o[4]) * float(o[4]) + float(mh2[1]) / 2.25 + float(f["tau2"]))
		var inside2: bool = band2 < INF and absf(y - float(o[3])) <= band2
		miss_k += 0 if inside2 else 1
		txt += " %s at %.1f: model y %.3f source %.3f ± %.3f %s;" % [o[0], float(o[2]), y, float(o[3]), band2, "in" if inside2 else "OUT"]
	var line: String = "T2s-dgq (%s; the grade rows a CODE CHECK, current-grade HR against the m_g in use, TO_E 13:50; the income rows against their sources) 14 comparisons at z %.3f: grade misses %d, income misses %d;%s" % [label, Z_DGQ, miss_g, miss_k, txt]
	if as_check:
		check(miss_g + miss_k == 0, line)
	else:
		print("REPORT " + line)
	return [miss_g == 0, miss_k == 0]


## T2s-qk (REPORT with the stop rule): the quartile spread, points against the persons layer's; the bottom ÷ top death ratio against the input
func _t2s_qk(p: RefCounted, yr: Dictionary, st: RefCounted, as_check: bool = true, label: String = "year 1") -> void:
	var qm: PackedFloat64Array = p.tr_margins["t22_q_means"]
	var pts: String = ""
	for k: int in 4:
		pts += " %.3f" % ((qm[k] / qm[4 + k]) / (qm[0] / qm[4]))
	var h = PEOPLE.new()
	h.households = true
	h.create("JPN", 1, st.cohort["JPN"], st.qx["JPN"], {"13": {"pop_thousand": 14178}, "47": {"pop_thousand": 1467}}, 300)
	LC.quartile_cuts(h)
	var sm := PackedFloat64Array([0.0, 0.0, 0.0, 0.0])
	var sw := PackedFloat64Array([0.0, 0.0, 0.0, 0.0])
	for i: int in h.n:
		var k2: int = LC.quartile(h, i)
		sm[k2] += LC.equivalized(h, i) * h.weight[i]
		sw[k2] += h.weight[i]
	var per: String = ""
	for k3: int in 4:
		per += " %.3f" % ((sm[k3] / sw[k3]) / (sm[0] / sw[0]))
	var strata: Array = []
	var li: float = 0.0
	var lw: float = 0.0
	for ix: int in p.AGES * 2:
		strata.append([yr["d_k"][ix * 4 + 3], yr["x_k"][ix * 4 + 3], yr["d_k"][ix * 4], yr["x_k"][ix * 4]])
		var t: float = float(yr["x_k"][ix * 4 + 3]) + float(yr["x_k"][ix * 4])
		var wi: float = float(yr["d_k"][ix * 4]) * float(yr["x_k"][ix * 4 + 3]) / t if t > 0.0 else 0.0
		li += wi * log(LC.income_factor(p, ix / 2, 3))
		lw += wi
	var mh: Array = _mh(strata)
	var lm: float = log(float(mh[0]))
	var lin: float = li / lw
	print("REPORT T2s-qk (%s) each quartile's mean equivalized income ÷ the top's (top .. bottom): the points%s, the persons layer%s; the bottom ÷ top death ratio %.4f (log %.4f) against the input's MH-weighted I_3 %.4f (log %.4f)" % [label, pts, per, float(mh[0]), lm, exp(lin), lin])
	if not as_check:
		print("REPORT T2s-qk (a later year, reported) the model's log bottom ÷ top ratio %.4f against the input's %.4f" % [lm, lin])
		return
	check(lm >= lin * 2.0 / 3.0, "T2s-qk (the stop rule, TO_E 22:04; RE-DECLARED on MH weights after the stop, 23:06; the stop stands until M026) the model's log bottom ÷ top ratio %.4f at least two thirds of the input's %.4f" % [lm, lin])


## M5 (V112, TO_E 07:35): tiers.gd compiled at run time with the death call's grade 0; one month's deaths on this state must fail the grade rows
func _must_fail(p: RefCounted, clean_ok: bool) -> void:
	var src: String = FileAccess.get_file_as_string("res://sim/modern/people/tiers.gd")
	var line: String = "LC.death_q(p, p.tr_c[ix], a, gr, k, mu[ix], 12.0)"
	var gs := GDScript.new()
	gs.source_code = src.replace(line, "LC.death_q(p, p.tr_c[ix], a, 0, k, mu[ix], 12.0)")
	var ok: bool = src.count(line) == 1 and gs.reload() == OK
	var miss: bool = false
	if ok:
		var w: Dictionary = gs.call("_t22_work", p)
		gs.call("_t22_deaths", p, w)
		var tl: Dictionary = w["tally"]
		var grade: Array = _t2s_dgq(p, tl, "M5 must-fail, one month, expected to FAIL", false)
		miss = not bool(grade[0])
	check(clean_ok and ok and miss, "T2s-dgq (M5 must-fail) the death call with grade 0, compiled at run time: compiled %s, the grade rows fail %s (and pass unmutated %s)" % [str(ok), str(miss), str(clean_ok)])


## The wives at work by the husband's R70 class (16) over the couple entries: [rates, couples]
func _r70_rates(p: RefCounted) -> Array:
	var ce: Dictionary = TR._v(p, "couple_wife_employment")
	var emp := PackedFloat64Array()
	emp.resize(16)
	var all := PackedFloat64Array()
	all.resize(16)
	for c: int in p.tr_cp_n.size():
		var cl: int = TR._r70_class(p, p.tr_cp_h[c], ce["class_from_man_yen_year"])
		all[cl] += float(p.tr_cp_n[c])
		emp[cl] += float(p.tr_cp_n[c]) if TR._at_work(p, p.tr_cp_w[c]) else 0.0
	var rate := PackedFloat64Array()
	for k: int in 16:
		rate.append(emp[k] / maxf(1.0, all[k]))
	return [rate, all]


## The couple tables: [entries, blocks, Σ over blocks of wife points x husband points]
func _cp_density(p: RefCounted) -> Array:
	var bw: Dictionary = {}
	var bh: Dictionary = {}
	for c: int in p.tr_cp_n.size():
		var b: int = p.tr_cp_hh[c]
		if not bw.has(b):
			bw[b] = {}
			bh[b] = {}
		bw[b][p.tr_cp_w[c]] = true
		bh[b][p.tr_cp_h[c]] = true
	var prod: int = 0
	for b2 in bw:
		prod += (bw[b2] as Dictionary).size() * (bh[b2] as Dictionary).size()
	return [p.tr_cp_n.size(), bw.size(), prod]


func _sum(a) -> int:
	var s: int = 0
	for x: int in a:
		s += x
	return s


## The tiers' persons by single age x sex from the points' masses
func _pop(p: RefCounted) -> PackedInt64Array:
	var out := PackedInt64Array()
	out.resize(p.AGES * 2)
	for u: int in p.tr_units:
		var b: int = p.tr_key[u * TR.KEY_STRIDE + 1]
		var s: int = p.tr_key[u * TR.KEY_STRIDE + 2]
		for g: int in range(p.tr_pt_off[u], p.tr_pt_off[u + 1]):
			for sl: int in TR.AGE_SLOTS:
				var m: int = p.tr_pt_age[g * TR.AGE_SLOTS + sl]
				if m != 0:
					out[mini(b * 5 + sl, p.AGES - 1) * 2 + s] += m
	return out


func _t2s_m(p: RefCounted) -> int:
	var bad: int = 0
	for u: int in p.tr_units:
		var by := PackedInt64Array()
		by.resize(TR.AGE_SLOTS)
		var cnt: int = 0
		for sl: int in TR.AGE_SLOTS:
			cnt += p.tr_age_counts[u * TR.AGE_SLOTS + sl]
		bad += 0 if cnt == p.tr_count[u] else 1
		for g: int in range(p.tr_pt_off[u], p.tr_pt_off[u + 1]):
			var s: int = 0
			for sl2: int in TR.AGE_SLOTS:
				var m: int = p.tr_pt_age[g * TR.AGE_SLOTS + sl2]
				var o: int = p.tr_pt_old[g * TR.AGE_SLOTS + sl2]
				bad += 1 if m < 0 or o < 0 or o > m else 0
				by[sl2] += m
				s += m
			bad += 0 if s == p.tr_pt_mass[g] else 1
		for sl3: int in TR.AGE_SLOTS:
			bad += 0 if by[sl3] == p.tr_age_counts[u * TR.AGE_SLOTS + sl3] else 1
	return bad


func _t2s_c(p: RefCounted) -> int:
	var bad: int = 0
	for u: int in p.tr_units:
		var l: Array = range(p.tr_pt_off[u], p.tr_pt_off[u + 1])
		bad += 1 if l.size() > int(ceil(1.5 * float(TR.cap_target(p, u, l)))) else 0
	return bad


func _t2s_cp(p: RefCounted, cp0: int) -> int:
	var bad: int = 0 if _sum(p.tr_cp_n) == cp0 else 1
	var marg := PackedInt64Array()
	marg.resize(p.tr_pt_mass.size())
	for c: int in p.tr_cp_n.size():
		bad += 1 if p.tr_cp_n[c] <= 0 else 0
		bad += 0 if int(p.tr_points["sex"][p.tr_cp_w[c]]) == p.FEMALE and int(p.tr_points["sex"][p.tr_cp_h[c]]) == p.MALE else 1
		marg[p.tr_cp_w[c]] += p.tr_cp_n[c]
		marg[p.tr_cp_h[c]] += p.tr_cp_n[c]
	for g: int in marg.size():
		bad += 1 if marg[g] > p.tr_pt_ms[g * 4 + 1] else 0
	return bad


func _t2s_ms(p: RefCounted) -> int:
	var bad: int = 0
	for g: int in p.tr_pt_mass.size():
		var s: int = 0
		for k: int in 4:
			s += p.tr_pt_ms[g * 4 + k]
			bad += 1 if p.tr_pt_ms[g * 4 + k] < 0 else 0
		bad += 0 if s == p.tr_pt_mass[g] else 1
	return bad


## T2s-c0 AMENDED (M036, §14.6 (16), §R rule 4; exact): at month 0, every point and slot: its cells (Σ over the classes) sum to the slot's
## mass and each lies within 1 of m pi(a, s) (strictly); the January and unaged cells equal them; T's rows equal the marital masses and
## its columns the state masses; every cell at least 0
func _t2s_c0(p: RefCounted) -> void:
	var off: int = 0
	for u: int in p.tr_units:
		var b: int = p.tr_key[u * TR.KEY_STRIDE + 1]
		var s: int = p.tr_key[u * TR.KEY_STRIDE + 2]
		for g: int in range(p.tr_pt_off[u], p.tr_pt_off[u + 1]):
			var colm := PackedInt64Array()
			colm.resize(TR.NG)
			for sl: int in TR.AGE_SLOTS:
				var m: int = p.tr_pt_age[g * TR.AGE_SLOTS + sl]
				var sh: PackedFloat64Array = LC.shares(p, b * 5 + sl, s)
				var tot: float = 0.0
				for gq: int in TR.NG:
					tot += sh[gq]
				var sum: int = 0
				for gr: int in TR.NG:
					var cx: int = (g * TR.AGE_SLOTS + sl) * TR.NS + gr * TR.NK
					var n: int = p.tr_pt_ag[cx] + p.tr_pt_ag[cx + 1]
					sum += n
					colm[gr] += n
					var bad: bool = p.tr_pt_ag[cx] < 0 or p.tr_pt_ag[cx + 1] < 0
					bad = bad or p.tr_pt_jg[cx] != p.tr_pt_ag[cx] or p.tr_pt_jg[cx + 1] != p.tr_pt_ag[cx + 1] or p.tr_pt_og[cx] != p.tr_pt_ag[cx] or p.tr_pt_og[cx + 1] != p.tr_pt_ag[cx + 1]
					bad = bad or (m > 0 and absf(float(n) - float(m) * sh[gr] / tot) >= 1.0)
					off += 1 if bad else 0
				off += 0 if sum == m else 1
			for k: int in 4:
				var row: int = 0
				for gr2: int in TR.NG:
					row += p.tr_pt_T[g * 4 * TR.NG + k * TR.NG + gr2]
					off += 1 if p.tr_pt_T[g * 4 * TR.NG + k * TR.NG + gr2] < 0 else 0
				off += 0 if row == p.tr_pt_ms[g * 4 + k] else 1
			for gr3: int in TR.NG:
				var col: int = 0
				for k2: int in 4:
					col += p.tr_pt_T[g * 4 * TR.NG + k2 * TR.NG + gr3]
				off += 0 if col == colm[gr3] else 1
	check(off == 0, "T2s-c0 AMENDED (M036, §14.6 (16), exact; checks less than the rule, V122: T read by margins only, the rounding order not bit for bit) at month 0: point-slot cells off the slot's mass, beyond 1 of m pi(a, s), January or unaged cells unequal, T off its marital rows or state columns, or below 0: %d" % off)


## T2s-c0c (declared at 9c8d2980): each age and sex at month 0, tr_c against c* solved by the same bisection on each point's unrounded
## m pi(a, s) at its quartile, within tau = (S / 2)(e_max - e_min) / (mu sum w m_g I_k e), S = 4 P / N (the largest remainder's
## absolute errors at most 4 per point and slot), first order
func _t2s_c0c(p: RefCounted) -> void:
	var DM = preload("res://sim/api/det_math.gd")
	var m: Array = LC._lc(p, "death_multiplier")
	var lt: Dictionary = LC._lc(p, "qx_2022")
	var w := PackedFloat64Array()
	w.resize(p.AGES * 2 * TR.NG * 4)
	var pts := PackedInt64Array()
	pts.resize(p.AGES * 2)
	var mass := PackedFloat64Array()
	mass.resize(p.AGES * 2)
	for u: int in p.tr_units:
		var b: int = p.tr_key[u * TR.KEY_STRIDE + 1]
		var s: int = p.tr_key[u * TR.KEY_STRIDE + 2]
		for g: int in range(p.tr_pt_off[u], p.tr_pt_off[u + 1]):
			for sl: int in TR.AGE_SLOTS:
				var mm: int = p.tr_pt_age[g * TR.AGE_SLOTS + sl]
				if mm <= 0:
					continue
				var a: int = b * 5 + sl
				var sh: PackedFloat64Array = LC.shares(p, a, s)
				var tot: float = 0.0
				for gq: int in TR.NG:
					tot += sh[gq]
				for gr: int in TR.NG:
					w[(a * 2 + s) * TR.NG * 4 + gr * 4 + p.tr_pt_q[g]] += float(mm) * sh[gr] / tot
				pts[a * 2 + s] += 1
				mass[a * 2 + s] += float(mm)
	var worst: float = 0.0
	var worst_at: String = ""
	var out: int = 0
	var skipped: int = 0
	for a2: int in p.AGES:
		for s2: int in 2:
			var cell: int = (a2 * 2 + s2) * TR.NG * 4
			var tab: Array = lt["men" if s2 == p.MALE else "women"]
			var q: float = float(tab[mini(a2, tab.size() - 1)])
			if mass[a2 * 2 + s2] <= 0.0 or q >= 1.0:
				skipped += 1
				continue
			var mu: float = -DM.log(1.0 - q)
			var target: float = DM.exp(-mu)
			var lo: float = 0.0
			var hi: float = 16.0
			for it: int in 60:
				var c: float = 0.5 * (lo + hi)
				var surv: float = 0.0
				for g2: int in TR.NG:
					for k: int in 4:
						surv += w[cell + g2 * 4 + k] / mass[a2 * 2 + s2] * DM.exp(-c * float(m[g2]) * LC.income_factor(p, a2, k) * mu)
				if surv > target:
					lo = c
				else:
					hi = c
			var cs: float = 0.5 * (lo + hi)
			var emax: float = 0.0
			var emin: float = 1.0
			var dF: float = 0.0
			for g3: int in TR.NG:
				for k2: int in 4:
					var f: float = float(m[g3]) * LC.income_factor(p, a2, k2)
					var e: float = DM.exp(-cs * f * mu)
					emax = maxf(emax, e)
					emin = minf(emin, e)
					dF += w[cell + g3 * 4 + k2] / mass[a2 * 2 + s2] * mu * f * e
			var tau: float = (2.0 * float(pts[a2 * 2 + s2]) / mass[a2 * 2 + s2]) * (emax - emin) / dF if dF > 0.0 else INF
			var d: float = absf(p.tr_c[a2 * 2 + s2] - cs)
			if d > tau:
				out += 1
			var r: float = d / tau if tau > 0.0 else (0.0 if d == 0.0 else INF)
			if r > worst:
				worst = r
				worst_at = "%s %d: |dc| %s against tau %s" % ["men" if s2 == p.MALE else "women", a2, String.num_scientific(d), String.num_scientific(tau)]
	check(out == 0, "T2s-c0c (declared at 9c8d2980) at month 0: ages x sex with tr_c beyond tau of c* on the unrounded m pi(a, s): %d (skipped with no mass %d); worst |dc| / tau %.4f (%s)" % [out, skipped, worst, worst_at])


## T2s-wg (REPORT, M030 §6) at month 0: the couple entries' wife grade x husband grade against independence (the table, Σ (O − E)² ÷ E
## on (NG − 1)² degrees of freedom, Cramér's V)
func _t2s_wg0(p: RefCounted) -> void:
	var ng: int = TR.NG
	var t := PackedFloat64Array()
	t.resize(ng * ng)
	var tot: float = 0.0
	for c: int in p.tr_cp_n.size():
		t[int(p.tr_points["health"][p.tr_cp_w[c]]) * ng + int(p.tr_points["health"][p.tr_cp_h[c]])] += float(p.tr_cp_n[c])
		tot += float(p.tr_cp_n[c])
	var chi: float = 0.0
	var txt: String = ""
	for i: int in ng:
		for j: int in ng:
			var ri: float = 0.0
			var cj: float = 0.0
			for k: int in ng:
				ri += t[i * ng + k]
				cj += t[k * ng + j]
			var e: float = ri * cj / tot
			chi += (t[i * ng + j] - e) * (t[i * ng + j] - e) / e if e > 0.0 else 0.0
			txt += " w%d|h%d %.0f (indep. %.0f);" % [i + 1, j + 1, t[i * ng + j], e]
	print("REPORT T2s-wg (month 0) the couple entries' wife grade x husband grade (the T: independent given the points; predicted near independence): %.0f couples, chi-square %.1f on %d df, Cramér's V %.4f;%s" % [tot, chi, (ng - 1) * (ng - 1), sqrt(chi / (tot * float(ng - 1))), txt])


## T2s-wg (REPORT) a read year's widowings: the survivors' grades against their points' married grade mix (z per sex x 10-year band x
## grade, the hypergeometric variance), and the deceased's grade x the survivor's grade summed over bands
func _t2s_wg(y_wg: Dictionary, label: String) -> void:
	if y_wg.is_empty():
		return
	var ng: int = TR.NG
	var worst: float = 0.0
	var txt: String = ""
	var beyond: int = 0
	var cells: int = 0
	var ds := PackedFloat64Array()
	ds.resize(2 * ng * ng)
	for sx: int in 2:
		for b10: int in 9:
			var row: String = ""
			for gr: int in ng:
				var ix: int = (sx * 9 + b10) * ng + gr
				for dg: int in ng:
					ds[(sx * ng + dg) * ng + gr] += float(y_wg["wg_n"][((sx * 9 + b10) * ng + dg) * ng + gr])
				var v: float = float(y_wg["wg_v"][ix])
				if v <= 0.0:
					continue
				var z: float = (float(y_wg["wg_x"][ix]) - float(y_wg["wg_e"][ix])) / sqrt(v)
				cells += 1
				beyond += 1 if absf(z) > 3.0 else 0
				worst = maxf(worst, absf(z))
				row += " g%d %.0f/%.1f (z %.2f)" % [gr + 1, float(y_wg["wg_x"][ix]), float(y_wg["wg_e"][ix]), z]
			if row != "":
				txt += " %s %d-:%s;" % ["men" if sx == 0 else "women", b10 * 10, row]
	var dtxt: String = ""
	for sx2: int in 2:
		for dg2: int in ng:
			for gr2: int in ng:
				dtxt += " %s d%d|s%d %.0f" % ["men" if sx2 == 0 else "women", dg2 + 1, gr2 + 1, ds[(sx2 * ng + dg2) * ng + gr2]]
	print("REPORT T2s-wg (%s) the year's widowings, survivors by sex x 10-year band x grade, observed / expected from their points' married grade mix: %d cells, %d beyond 3 SE, worst |z| %.2f;%s the deceased's grade x the survivor's grade (by the survivor's sex):%s" % [label, cells, beyond, worst, txt, dtxt])


## T2s-gc (REPORT): the mean non-zero grade cells per (point, age) with mass
func _gc(p: RefCounted) -> float:
	var n: int = 0
	var nz: int = 0
	for g: int in p.tr_pt_off[p.tr_units]:
		for sl: int in TR.AGE_SLOTS:
			if p.tr_pt_age[g * TR.AGE_SLOTS + sl] <= 0:
				continue
			n += 1
			for gr: int in TR.NG:
				var cx: int = (g * TR.AGE_SLOTS + sl) * TR.NS + gr * TR.NK
				nz += 1 if p.tr_pt_ag[cx] + p.tr_pt_ag[cx + 1] > 0 else 0
	return float(nz) / float(maxi(1, n))


func _steps_txt(st: Dictionary, months: int) -> String:
	var keys: Array = st.keys()
	keys.sort()
	var out: String = ""
	for k: String in keys:
		out += " %s %.1f s;" % [k, float(st[k]) / 1e6 / float(months)]
	return out


## T2s-gx's must-fail (§14.6 (6), V120 §3): the coherent grade crossing in _t22_merge, the dropped point's grade-0 cells (both classes) and T column
## summed into the kept point's grade 1, compiled at run time and run for one month at the test's end
func _gx_must_fail(p: RefCounted) -> void:
	var src: String = FileAccess.get_file_as_string("res://sim/modern/people/tiers.gd")
	var ok: bool = true
	for arr: String in ["tr_pt_ag", "tr_pt_jg", "tr_pt_og"]:
		var line: String = "p.%s[i * AGE_SLOTS * NS + x] += p.%s[k * AGE_SLOTS * NS + x]" % [arr, arr]
		ok = ok and src.count(line) == 1
		src = src.replace(line, "p.%s[i * AGE_SLOTS * NS + x + (NK if x %% NS < NK else 0)] += p.%s[k * AGE_SLOTS * NS + x]" % [arr, arr])
	var line_t: String = "p.tr_pt_T[i * 4 * NG + x2] += p.tr_pt_T[k * 4 * NG + x2]"
	ok = ok and src.count(line_t) == 1
	src = src.replace(line_t, "p.tr_pt_T[i * 4 * NG + x2 + (1 if x2 % NG == 0 else 0)] += p.tr_pt_T[k * 4 * NG + x2]")
	var gs := GDScript.new()
	gs.source_code = src
	ok = ok and gs.reload() == OK
	var gm: int = -1
	var gx_m: int = -1
	if ok:
		gs.call("step", p, ENV)
		var tl: Dictionary = p.tr_margins["t22"]
		gm = int(gs.call("grade_identity", p))
		gx_m = int(tl["gx_by_stage"]["C1, C2 and the rebuild"])
	check(ok and gm == 0 and gx_m > 0, "T2s-gx (must-fail, V120's coherent grade crossing in the merge, compiled at run time, one month): compiled %s; T2s-gm violations %d (expected 0); T2s-gx cells off at C1, C2 and the rebuild %d (expected above 0)" % [str(ok), gm, gx_m])


## T2s-dt (§14.6 (7), TO_E 13:23): the year's deaths against the IPSS medium rate of the year read × the model's person-years at risk;
## the 65+, 75+ and 85+ totals by sex within 2% × the horizon band (T), the single age × sex cells within Z_DT × the band on (D − E) ÷ √E
func _t2s_dt(p: RefCounted, yr: Dictionary, h: float, label: String) -> void:
	p.month -= 1
	var mu: PackedFloat64Array = TR.mu_path(p)
	p.month += 1
	var tot_bad: int = 0
	var ttxt: String = ""
	for s: int in 2:
		for lo: int in [65, 75, 85]:
			var d: float = 0.0
			var e: float = 0.0
			for a: int in range(lo, p.AGES):
				var ix: int = a * 2 + s
				if mu[ix] == INF:
					continue
				d += float(yr["d_as"][ix])
				e += mu[ix] * float(yr["x_as"][ix])
			var dev: float = d / e - 1.0 if e > 0.0 else 0.0
			tot_bad += 1 if absf(dev) > 0.02 * h else 0
			ttxt += " %s %d+: %d against %.0f (%+.2f%%);" % ["men" if s == 0 else "women", lo, int(d), e, 100.0 * dev]
	var miss: int = 0
	var cells: int = 0
	var worst: float = 0.0
	var wtxt: String = ""
	var btxt: String = ""
	var c100: String = ""
	for ix2: int in p.AGES * 2:
		if mu[ix2] == INF:
			continue
		var e2: float = mu[ix2] * float(yr["x_as"][ix2])
		if e2 <= 0.0:
			continue
		cells += 1
		var z: float = (float(yr["d_as"][ix2]) - e2) / sqrt(e2)
		miss += 1 if absf(z) > Z_DT * h else 0
		if absf(z) > Z_DT * h:
			btxt += " %s age %d: z %.2f, expected %.0f, observed %d;" % ["men" if ix2 % 2 == 0 else "women", ix2 / 2, z, e2, int(yr["d_as"][ix2])]
		if ix2 / 2 == 100:
			c100 += " %s: expected %.0f, observed %d (z %.2f);" % ["men" if ix2 % 2 == 0 else "women", e2, int(yr["d_as"][ix2]), z]
		if absf(z) > worst:
			worst = absf(z)
			wtxt = "%s age %d: %d against %.0f (z %.2f)" % ["men" if ix2 % 2 == 0 else "women", ix2 / 2, int(yr["d_as"][ix2]), e2, z]
	print("REPORT T2s-dt (%s, TO_E 08:49, label only) every cell beyond %.3f x %.2f:%s the cells at 100 (M036's comparison):%s" % [label, Z_DT, h, btxt if btxt != "" else " none;", c100])
	check(tot_bad == 0 and miss == 0, "T2s-dt (%s, TO_E 13:23) the deaths against the IPSS medium rate x the person-years: totals beyond 2%% x %.2f %d of 6;%s cells beyond %.3f x %.2f %d of %d, worst %s" % [label, h, tot_bad, ttxt, Z_DT, h, miss, cells, wtxt])


## The mass shares by state per sex x 10-year band (2 x 9 x NG), from the cells
func _grade_mix(p: RefCounted) -> PackedFloat64Array:
	var ng: int = TR.NG
	var out := PackedFloat64Array()
	out.resize(2 * 9 * ng)
	for u: int in p.tr_units:
		var b: int = p.tr_key[u * TR.KEY_STRIDE + 1]
		var row: int = (p.tr_key[u * TR.KEY_STRIDE + 2] * 9 + LC._b10(b * 5)) * ng
		for g: int in range(p.tr_pt_off[u], p.tr_pt_off[u + 1]):
			for sl: int in TR.AGE_SLOTS:
				for sb: int in TR.NS:
					out[row + sb / TR.NK] += float(p.tr_pt_ag[(g * TR.AGE_SLOTS + sl) * TR.NS + sb])
	for r: int in 18:
		var t: float = 0.0
		for g2: int in ng:
			t += out[r * ng + g2]
		for g3: int in ng:
			out[r * ng + g3] = out[r * ng + g3] / t if t > 0.0 else 0.0
	return out


func _mix_txt(mix: PackedFloat64Array, mix0: PackedFloat64Array) -> String:
	var ng: int = TR.NG
	var out: String = ""
	for r: int in 18:
		out += " %s %d-:" % ["men" if r < 9 else "women", (r % 9) * 10]
		for gr: int in ng:
			out += " %.3f (%.3f)" % [mix[r * ng + gr], mix0[r * ng + gr]]
		out += ";"
	return out


## T2s-gp's cells of one January's transitions (sex x 10-year band x state): [beyond z, the worst |z|, the shares' text]
func _t2s_gp(gp: Dictionary, z_max: float) -> Array:
	var ng: int = TR.NG
	var beyond: int = 0
	var worst: float = 0.0
	var txt: String = ""
	for r: int in 18:
		var nb: float = 0.0
		for g0: int in ng:
			nb += float(gp["before"][r * ng + g0])
		if nb <= 0.0:
			continue
		var row: String = ""
		for g: int in ng:
			var x: int = r * ng + g
			var v: float = float(gp["var"][x])
			var z: float = (float(gp["after"][x]) - float(gp["target"][x])) / sqrt(v) if v > 0.0 else 0.0
			beyond += 1 if absf(z) > z_max else 0
			worst = maxf(worst, absf(z))
			var bg: float = float(gp["before"][x])
			var cs: String = ""
			for c: int in 2:
				var nc: float = float(gp["n_c"][c * 18 * ng + x])
				cs += "%s%.3f" % ["" if c == 0 else "|", float(gp["stay_c"][c * 18 * ng + x]) / nc if nc > 0.0 else 0.0]
			row += " g%d %.3f -> %.3f (%.3f) stay %.3f (%.3f) %s" % [g + 1, bg / nb, float(gp["after"][x]) / nb, float(gp["target"][x]) / nb, float(gp["stay"][x]) / bg if bg > 0.0 else 0.0, float(gp["stay_seed"][x]) / bg if bg > 0.0 else 0.0, cs]
		txt += " %s %d-:%s;" % ["men" if r < 9 else "women", (r % 9) * 10, row]
	return [beyond, worst, txt]


## T2s-gk's cohort (M035): the stock by (class, state) at ages 51-60 at month 0, per (age, sex, quartile), with the always-good and
## always-bad masses; [[age, sex, quartile, start, good, bad], ...] and the years composed in [0]
func _paths_start(p: RefCounted) -> Array:
	var ng: int = TR.NG
	var st: Dictionary = {}
	for u: int in p.tr_units:
		var b: int = p.tr_key[u * TR.KEY_STRIDE + 1]
		var s: int = p.tr_key[u * TR.KEY_STRIDE + 2]
		for g: int in range(p.tr_pt_off[u], p.tr_pt_off[u + 1]):
			for sl: int in 5:
				var a: int = b * 5 + sl
				if a < 51 or a > 60:
					continue
				var key: int = (a * 2 + s) * 4 + p.tr_pt_q[g]
				if not st.has(key):
					var z := PackedFloat64Array()
					z.resize(2 * ng)
					st[key] = z
				for sb: int in TR.NS:
					st[key][(sb % TR.NK) * ng + sb / TR.NK] += float(p.tr_pt_ag[(g * TR.AGE_SLOTS + sl) * TR.NS + sb])
	var out: Array = [0]
	for key2: int in st:
		var v: PackedFloat64Array = st[key2]
		var gd := PackedFloat64Array()
		gd.resize(2 * ng)
		var bd := PackedFloat64Array()
		bd.resize(2 * ng)
		for x: int in 2 * ng:
			if x % ng < 2:
				gd[x] = v[x]
			else:
				bd[x] = v[x]
		out.append([key2 / 8, (key2 / 4) % 2, key2 % 4, v, gd, bd])
	return out


## The month's arrivals' realised P_c, mass-weighted by their row masses, into the year's sums
func _paths_add(gp: Dictionary, acc: Dictionary) -> void:
	var nn: PackedFloat64Array = gp["nn"]
	var pm: PackedFloat64Array = gp["pm"]
	var ng: int = TR.NG
	if acc.is_empty():
		var z1 := PackedFloat64Array()
		z1.resize(nn.size())
		var z2 := PackedFloat64Array()
		z2.resize(pm.size())
		acc["n"] = z1
		acc["pw"] = z2
	for r: int in nn.size():
		if nn[r] <= 0.0:
			continue
		acc["n"][r] += nn[r]
		for h: int in ng:
			acc["pw"][r * ng + h] += nn[r] * pm[r * ng + h]


## One year of the cohort: each (age, sex, quartile) cell's always-good and always-bad masses moved by that year's mean P_c at the
## cohort's new age; returns the gap reached
func _paths_year(p: RefCounted, paths: Array, acc: Dictionary) -> int:
	var ng: int = TR.NG
	var acc_pw: PackedFloat64Array = acc.get("pw", PackedFloat64Array())
	var acc_n: PackedFloat64Array = acc.get("n", PackedFloat64Array())
	var t: int = int(paths[0])
	for i: int in range(1, paths.size()):
		var e: Array = paths[i]
		var a: int = mini(int(e[0]) + t + 1, p.AGES - 1)
		var cell: int = (a * 2 + int(e[1])) * 4 + int(e[2])
		for side: int in 2:
			var lo: int = 0 if side == 0 else 2
			var hi: int = 2 if side == 0 else ng
			var v: PackedFloat64Array = e[4 + side]
			var nv := PackedFloat64Array()
			nv.resize(2 * ng)
			for c: int in 2:
				for g: int in range(lo, hi):
					var r: int = cell * 2 * ng + c * ng + g
					if v[c * ng + g] <= 0.0:
						continue
					for h: int in range(lo, hi):
						var pr: float = acc_pw[r * ng + h] / acc_n[r] if acc_n.size() > r and acc_n[r] > 0.0 else (1.0 if h == g else 0.0)
						nv[c * ng + h] += v[c * ng + g] * pr
			e[4 + side] = nv
	paths[0] = t + 1
	return t + 1


func _paths_share(paths: Array) -> Array:
	var n0: float = 0.0
	var gd: float = 0.0
	var bd: float = 0.0
	for i: int in range(1, paths.size()):
		var e: Array = paths[i]
		for x: int in (e[3] as PackedFloat64Array).size():
			n0 += float(e[3][x])
			gd += float(e[4][x])
			bd += float(e[5][x])
	return [gd / n0 if n0 > 0.0 else 0.0, bd / n0 if n0 > 0.0 else 0.0]


## A grade's tally at age x sex ix; grade 4 (index 3) is 4a and 4b together (T2.2c)
func _gsum(t: Array, ix: int, g: int) -> float:
	var v: float = float(t[ix * TR.NG + g])
	if g == 3:
		v += float(t[ix * TR.NG + 4])
	return v


## T2s-4b (T2.2c): one January's 4b share by 5-year band (65-69 .. 95+) x sex against LTCI's target, z on the moves' variance, with
## 4b's realised yearly exit to 4a (T2s-4bx); [beyond z_max, the text]
func _t2s_4b(gp: Dictionary, z_max: float) -> Array:
	var beyond: int = 0
	var txt: String = ""
	for r: int in 14:
		var v: float = float(gp["b4_var"][r])
		var z: float = (float(gp["b4_after"][r]) - float(gp["b4_target"][r])) / sqrt(v) if v > 0.0 else 0.0
		beyond += 1 if absf(z) > z_max else 0
		var n4: float = float(gp["b4_n"][r])
		txt += " %s %d%s: %.0f (LTCI %.0f, z %.2f), exit %.4f;" % ["men" if r < 7 else "women", 65 + (r % 7) * 5, "+" if r % 7 == 6 else "", float(gp["b4_after"][r]), float(gp["b4_target"][r]), z, float(gp["b4_exit"][r]) / n4 if n4 > 0.0 else 0.0]
	return [beyond, txt]


## T2s-4bx's yearly death rate of 4b by 5-year band x sex from the year's tallies (deaths ÷ person-years)
func _4b_deaths(p: RefCounted, yr: Dictionary) -> String:
	var txt: String = ""
	for s: int in 2:
		for b: int in 7:
			var d: float = 0.0
			var x: float = 0.0
			for a: int in range(65 + b * 5, p.AGES if b == 6 else 70 + b * 5):
				d += float(yr["d_g"][(a * 2 + s) * TR.NG + 4])
				x += float(yr["x_g"][(a * 2 + s) * TR.NG + 4])
			txt += " %s %d%s %.3f;" % ["men" if s == 0 else "women", 65 + b * 5, "+" if b == 6 else "", d / x if x > 0.0 else 0.0]
	return txt
