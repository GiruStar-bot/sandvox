extends "res://tools/test/test_kit.gd"
## ISS tiered population T2.2, the tiers' month (ISS_TIERED_POPULATION.md §14.6 with (1) as built, 749647fc; ISS_CHECKS.md T2s-a, T2s-m,
## T2s-e, T2s-c, T2s-cp, T2s-ms, T2s-phi). The national start, seed 1, twelve months from January. Step 1: ageing and compression only.
##   godot --headless --path . --script res://sim/modern/test_modern_t2_month.gd
## T2s-a  (AMENDED) every person 12 months at each age: after December no cell below 100 holds a mass not yet aged; the tiers' population
##        by single age and sex at month 12 equals the start's one age younger less the cohort's year deaths (the not-yet-aged dead at
##        its start age, the rest at the next; 100 holds 99 and 100; age 0 empty, no births); each month's moved mass against the birth
##        months' due mass, and the cells whose N was raised to O, reported
## T2s-m  every month: Σ over a unit's points of each age's mass = the unit's booked age count; Σ ages = the point's mass; the booked
##        count = Σ its age counts; no mass < 0; no cell's not-yet-aged mass above its mass; (AMENDED, M025 C4) no cell's N below O
## T2s-e  every month: Σ booked counts = Σ point masses = the start's tiers population less the deaths so far (no births or moves
##        yet); the individuals reported apart (the persons layer's)
## T2s-d  (AMENDED, §14.6 (2) as built) the year's deaths by sex x 5-year band against Σ q_m x the masses at risk within 3 binomial SE
##        (horizon band x 1 at year 1); against the rate −ln(1 − q_x(t)) x the person-years reported (TO_E 23:06 (5))
## T2s-d2 the same by single age x sex, reported, the cells beyond 3 SE counted
## T2s-dgq (year 1, DIAGNOSTIC) Mantel-Haenszel rate ratios over single age x sex strata, Robins-Breslow-Greenland variance: grade 3 ÷
##        grade 1 and grade 4 ÷ grade 3 by sex over 65+ against R74's 4 rows; the bottom ÷ top quartile over each of M010's 10
##        observations' sex and ages within ±2 years of its age at risk on the two-group scale (÷ 1.5) against y with τ; 14 at z 2.914
## T2s-dgq (M5 must-fail) one month's deaths by tiers.gd compiled at run time with the death call's grade 0 make the grade rows fail
## T2s-qk (year 1, REPORT, the stop rule) the points' quartile means ÷ the top's against the persons layer's; the bottom ÷ top MH log
##        rate ratio against (RE-DECLARED after the stop, TO_E 23:06 (1)) the MH-weighted ln I_3(a), w_i = d_top,i T_bot,i ÷ T_i: the build
##        stops when it falls short by more than a third (the stop stands until M026)
## T2s-np (M025) every month: no unit above ⌈1.5 K_b⌉ points after the compression; no couple mass left on a dropped point (T2s-c AMENDED,
##        TO_E 23:06 (3)); the household-entry mass on points whose whole mass died reported (T2.3 books deaths' household side);
##        the national points at month 12 against M025's ~230k (at most 1.5 ΣK_b), reported
## T2s-cx (M025) every month: every unit's extensive totals equal before and after its compression
## T2s-cb (M025; AMENDED under §R rules 4 and 5, TO_E 01:14) after months 1, 6 and 12: the married and couple masses by quartile x
##        10-year band moved by the cap's merges, each cell within 3.682 SD of 0 (a 5% family rate over the 216, Bonferroni; the merges'
##        p_i p_k (M_i + M_k)²); C1's lossless merges' mass across quartiles reported (the quartile is
##        re-read from the summed composition)
## M025b (TO_E 01:42; declared at e50da05a): T2s-cb read as (r − μ) ÷ σ with each merge's μ tallied (C2 within one quartile: 0 but
##        the counted cross-quartile merges), Σμ reported a month and accumulated; T2s-cbq and T2s-cbg reported; T2s-ncp every block at most
##        its cap every month, the national entries at months 1 and 12 against ~1.9-2.1 M, the start's density printed; T2s-c5x every
##        point's and block's couples unchanged by C5; T2s-c5b at months 1, 6, 12, C5's change of the couples by wife quartile x husband
##        quartile x the husband's band and the both-earning couples by band within |z| <= 3.593 (a 5% family rate over 153); T2s-r70
##        re-read: the wives at work by the husband's R70 class at month 12 against month 0
## T2s-ncp, T2s-keff (M025, reported) the couple entries at month 12 against ~2.0-2.5 M; the mass-weighted median K_eff ÷ K_b against 0.8-1.0
## T2s-cp (until T2.3, §14.6 (1) as built) every month: Σ couple masses = the start's less the couples a death ended, the widowed made
##        = those couples, none <= 0, every couple's wife point female and husband point male, every point's couple marginal at most its
##        married mass
## T2s-ms every month: every point's four states sum to its mass, none < 0
## T2s-phi every split point still present at the month's end has its source's φ in bits
## V120b (TO_E 12:40): every family covers all the row's reads in the run (§R rule 5): T2s-cb 216 cells x 3 reads, 3.953; T2s-c5b
## 153 x 3, 3.870; T2s-dgq 14 x 1, 2.914; T2s-d 36 x 1, 3.19; each read prints its worst cell
const PEOPLE = preload("res://sim/modern/people/people.gd")
const TR = preload("res://sim/modern/people/tiers.gd")
const LC = preload("res://sim/modern/people/life_course.gd")
const MS = preload("res://sim/modern/modern_status.gd")
const CANON = preload("res://sim/modern/canon.gd")
const ENV := {"inflation_month": 0.02 / 12.0, "food_price_yoy": 0.0, "unemployment_rate": 0.025, "levers": []}


const Z_DGQ := 2.914
const Z_CB := 3.953
const Z_C5B := 3.870
const Z_D := 3.19
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
	check(p.error == "", "tiers built: '%s' (%d units, %d points, %d couple points, %d ms; c from the 10-year band at %d ages x sex)" % [p.error, p.tr_units, p.tr_pt_off[p.tr_units], p.tr_cp_n.size(), Time.get_ticks_msec() - t0, int(p.tr_margins.get("t22_c_band", -1))])
	var pop0: PackedInt64Array = _pop(p)
	var tot0: int = _sum(p.tr_count)
	var cp0: int = _sum(p.tr_cp_n)
	var cp_n0: int = p.tr_cp_n.size()
	var bad: Dictionary = {"m": 0, "e": 0, "c": 0, "cp": 0, "ms": 0, "phi": 0, "lost": 0, "lost_hm": 0}
	var phi_n: int = 0
	var usec: int = 0
	var dead: int = 0
	var lost_cp: int = 0
	var yr: Dictionary = {}
	var clamped: int = 0
	var cx: int = 0
	var cb_bad: int = 0
	var cb_txt: String = ""
	var cb_acc := PackedFloat64Array()
	cb_acc.resize(36)
	var cbg_acc := PackedFloat64Array()
	cbg_acc.resize(36)
	var c5x: int = 0
	var c5_over: int = 0
	var c5b_bad: int = 0
	var c5b_txt: String = ""
	var r70_0: Array = _r70_rates(p)
	var dens: Array = _cp_density(p)
	print("REPORT T2s-ncp (M025b) the start's couple tables: %d entries in %d blocks against Σ P_w P_h %d (density %.3f)" % [int(dens[0]), int(dens[1]), int(dens[2]), float(dens[0]) / maxf(1.0, float(dens[2]))])
	for m: int in 12:
		var phi_of: Dictionary = {}
		for g: int in p.tr_pt_id.size():
			phi_of[p.tr_pt_id[g]] = p.tr_points["phi"][g]
		var t1: int = Time.get_ticks_usec()
		p.step(ENV)
		var tl: Dictionary = p.tr_margins["t22"]
		usec += int(tl["usec"])
		clamped += int(tl["clamped"])
		cx += int(tl["cx_bad"])
		print("REPORT M025 month %d: C1 merges %d (mass across quartiles %d), C2 merges %d, points %d, couple entries %d" % [m, int(tl["c1"]), int(tl["c1_q_moved"]), int(tl["c2"]), p.tr_pt_off[p.tr_units], p.tr_cp_n.size()])
		if m == 0 or m == 5 or m == 11:
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
		var mu_max: float = 0.0
		var g_max: float = 0.0
		for x6: int in 36:
			cb_acc[x6] += float(tl["cb_mm"][x6])
			cbg_acc[x6] += float(tl["cbg_m"][x6])
			mu_max = maxf(mu_max, absf(float(tl["cb_mm"][x6])))
			g_max = maxf(g_max, absf(float(tl["cbg_m"][x6])))
		c5x += int(tl["c5_x"])
		c5_over += int(tl["c5_over"])
		print("REPORT M025b month %d: cross-quartile merges %d (mass %d), the month's largest |Σμ| married by quartile x band %.1f, by grade x band %.1f; C5 moves %d in %d blocks over their cap" % [m, int(tl["cbq"]), int(tl["cbq_mass"]), mu_max, g_max, int(tl["c5_moves"]), int(tl["cp_blocks_capped"])])
		dead += int(tl["deaths"])
		lost_cp += int(tl["couples_lost"])
		for key: String in ["d_as", "d_old", "x_as", "e_as", "v_as", "d_g", "x_g", "d_k", "x_k"]:
			if not yr.has(key):
				yr[key] = tl[key].duplicate()
			else:
				for x: int in (tl[key] as Array).size():
					yr[key][x] += tl[key][x]
		print("REPORT T2s-a month %d: moved %d, due by the birth months %d, cells with N raised to O %d; splits %d, new units %d, class entered at 20 %d; merges %d, empty points dropped %d; deaths %d, couples ended %d, widowed %d; the tiers' month %d ms, the whole month %d ms; individuals %d" % [m, int(tl["moved"]), int(tl["due"]), int(tl["clamped"]), int(tl["splits"]), int(tl["new_units"]), int(tl["class_entered"]), int(tl["merges"]), int(tl["dropped"]), int(tl["deaths"]), int(tl["couples_lost"]), int(tl["widowed"]), int(tl["usec"]) / 1000, (Time.get_ticks_usec() - t1) / 1000, p.n])
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
	var old_left: int = 0
	for u: int in p.tr_units:
		var b: int = p.tr_key[u * TR.KEY_STRIDE + 1]
		for g3: int in range(p.tr_pt_off[u], p.tr_pt_off[u + 1]):
			for sl: int in TR.AGE_SLOTS:
				if b * 5 + sl < p.AGES - 1:
					old_left += p.tr_pt_old[g3 * TR.AGE_SLOTS + sl]
	var pop12: PackedInt64Array = _pop(p)
	var d_as: PackedInt64Array = yr["d_as"]
	var d_old: PackedInt64Array = yr["d_old"]
	var off: int = 0
	var worst: String = ""
	var top: int = p.AGES - 1
	for s: int in 2:
		for a: int in p.AGES:
			var want: int = 0
			if a == top:
				want = pop0[(top - 1) * 2 + s] - d_old[(top - 1) * 2 + s] + pop0[top * 2 + s] - d_as[top * 2 + s]
			elif a > 0:
				want = pop0[(a - 1) * 2 + s] - d_old[(a - 1) * 2 + s] - (d_as[a * 2 + s] - d_old[a * 2 + s])
			if pop12[a * 2 + s] != want:
				off += 1
				if worst == "":
					worst = " first: age %d sex %d %d against %d" % [a, s, pop12[a * 2 + s], want]
	check(old_left == 0 and off == 0, "T2s-a (AMENDED) after twelve months: mass not yet aged left below 100 %d; single ages x sex off the start's one age younger less the cohort's deaths %d of %d%s" % [old_left, off, p.AGES * 2, worst])
	check(int(bad["m"]) == 0 and clamped == 0, "T2s-m every month: units, points or cells off their identities %d (summed over the 12 months); cells whose N fell below O %d (M025 C4: 0)" % [int(bad["m"]), clamped])
	check(cx == 0, "T2s-cx (M025) every month: units whose extensive totals moved in the compression %d" % cx)
	check(cb_bad == 0, "T2s-cb (M025, AMENDED: a 5%% family rate over 216, |z| <= %.3f; M025b: (r − μ) ÷ σ) the cap's married and couple masses by quartile x 10-year band at months 1, 6, 12: cells beyond %d of 216;%s" % [Z_CB, cb_bad, cb_txt])
	var acc_max: float = 0.0
	var accg_max: float = 0.0
	for x7: int in 36:
		acc_max = maxf(acc_max, absf(cb_acc[x7]))
		accg_max = maxf(accg_max, absf(cbg_acc[x7]))
	print("REPORT T2s-cb / T2s-cbg (M025b) the accumulated Σμ of married mass over the year: largest cell by quartile x band %.1f, by grade x band %.1f" % [acc_max, accg_max])
	check(c5x == 0, "T2s-c5x (M025b) every month: blocks whose points' or total couples moved in C5 %d" % c5x)
	check(c5_over == 0, "T2s-ncp (M025b) every month: blocks above their cap after C5 %d" % c5_over)
	check(c5b_bad == 0, "T2s-c5b (M025b) C5's change of the couples by wife x husband quartile x band and both-earning by band within |z| <= %.3f at months 1, 6, 12: cells beyond %d of 153;%s" % [Z_C5B, c5b_bad, c5b_txt])
	var r70_12: Array = _r70_rates(p)
	var r70t: String = ""
	for k8: int in 16:
		r70t += " %d: %.3f -> %.3f (%d -> %d);" % [k8, float(r70_0[0][k8]), float(r70_12[0][k8]), int(r70_0[1][k8]), int(r70_12[1][k8])]
	print("REPORT T2s-r70 (M025b re-read) the wives at work by the husband's R70 class, month 0 -> month 12 (couples):%s" % r70t)
	check(int(bad["e"]) == 0, "T2s-e every month: months whose booked counts or point masses are off the start's %d tiers persons less the deaths so far (%d in the year) %d" % [tot0, dead, int(bad["e"])])
	var kb_sum: int = 0
	for u5: int in p.tr_units:
		kb_sum += maxi(1, p.tr_kb[u5]) if p.tr_count[u5] > 0 else 0
	check(int(bad["c"]) == 0 and int(bad["lost"]) == 0, "T2s-np (M025) every month: units above ⌈1.5 K_b⌉ points %d; couple mass left on dropped points %d; household-entry mass on points whose whole mass died %d (reported until T2.3); points at month 12 %d (M025 ~230k; 1.5 ΣK_b %d)" % [int(bad["c"]), int(bad["lost"]), int(bad["lost_hm"]), p.tr_pt_off[p.tr_units], int(1.5 * float(kb_sum))])
	var ke: Array = []
	var ke_tot: float = 0.0
	for u6: int in p.tr_units:
		var sw: float = 0.0
		var sw2: float = 0.0
		for g6: int in range(p.tr_pt_off[u6], p.tr_pt_off[u6 + 1]):
			sw += float(p.tr_pt_mass[g6])
			sw2 += float(p.tr_pt_mass[g6]) * float(p.tr_pt_mass[g6])
		if sw > 0.0:
			ke.append([sw * sw / sw2 / float(maxi(1, p.tr_kb[u6])), sw])
			ke_tot += sw
	ke.sort()
	var acc_k: float = 0.0
	var med: float = 0.0
	for r6: Array in ke:
		acc_k += float(r6[1])
		if acc_k >= ke_tot * 0.5:
			med = float(r6[0])
			break
	print("REPORT T2s-ncp (M025) couple entries at month 12 %d against %d at the start (M025 ~2.0-2.5 M); T2s-keff the mass-weighted median K_eff ÷ K_b %.3f (M025 0.8-1.0)" % [p.tr_cp_n.size(), cp_n0, med])
	check(int(bad["cp"]) == 0, "T2s-cp (until T2.3) every month: off (Σ couples against the start's %d less the %d a death ended, the widowed against those, a couple <= 0, a wife not female or a husband not male, a marginal above the married mass) %d" % [cp0, lost_cp, int(bad["cp"])])
	check(int(bad["ms"]) == 0, "T2s-ms every month: points whose four states do not sum to their mass or are < 0: %d" % int(bad["ms"]))
	check(int(bad["phi"]) == 0 and phi_n > 0, "T2s-phi %d split points read, φ off its source's bits %d" % [phi_n, int(bad["phi"])])
	_t2s_d(p, yr)
	var grade_ok: Array = _t2s_dgq(p, yr, "year 1")
	_t2s_qk(p, yr, st)
	print("REPORT the cost (§14.5 ruling 12): the tiers' twelve months %d ms, %d units, %d points, %d couple points at month 12" % [usec / 1000, p.tr_units, p.tr_pt_off[p.tr_units], p.tr_cp_n.size()])
	_must_fail(p, bool(grade_ok[0]))
	finish()


## T2s-d by sex x 5-year band (checked) and T2s-d2 by single age x sex (reported), the year's deaths against Σ q_m x the masses at risk
func _t2s_d(p: RefCounted, yr: Dictionary) -> void:
	var mu: PackedFloat64Array = TR.mu_path(p)
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
			if absf(z) > Z_D:
				miss += 1
				txt += " %s %d-: %d against %.0f (z %.2f);" % ["m" if s == 0 else "f", b * 5, int(d), e, z]
			if b >= 13:
				rep += " %s %d-: %d against the rate x person-years %.0f;" % ["m" if s == 0 else "f", b * 5, int(d), qx]
	check(miss == 0, "T2s-d (AMENDED) the year's deaths by sex x 5-year band against Σ q_m x the masses at risk, %.2f binomial SE (year 1): %d of 36 outside;%s" % [Z_D, miss, txt])
	print("REPORT T2s-d against the rate −ln(1 − q_x(2024)) x the person-years at 65+:%s" % rep)
	var miss2: int = 0
	for ix: int in p.AGES * 2:
		var v2: float = float(yr["v_as"][ix])
		if v2 > 0.0 and absf(float(yr["d_as"][ix]) - float(yr["e_as"][ix])) > 3.0 * sqrt(v2):
			miss2 += 1
	print("REPORT T2s-d2 the year's deaths by single age x sex: %d of %d cells beyond 3 SE (about %.1f expected by chance)" % [miss2, p.AGES * 2, 0.0027 * float(p.AGES * 2)])


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
func _t2s_qk(p: RefCounted, yr: Dictionary, st: RefCounted) -> void:
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
	print("REPORT T2s-qk (year 1) each quartile's mean equivalized income ÷ the top's (top .. bottom): the points%s, the persons layer%s; the bottom ÷ top death ratio %.4f (log %.4f) against the input's MH-weighted I_3 %.4f (log %.4f)" % [pts, per, float(mh[0]), lm, exp(lin), lin])
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


## A grade's tally at age x sex ix; grade 4 (index 3) is 4a and 4b together (T2.2c)
func _gsum(t: Array, ix: int, g: int) -> float:
	var v: float = float(t[ix * TR.NG + g])
	if g == 3:
		v += float(t[ix * TR.NG + 4])
	return v
