extends "res://tools/test/test_kit.gd"
## ISS tiered population, the deaths fix (ISS_TIERED_POPULATION.md §14.4a; ISS_CHECKS.md T2s-gr), declared before its code (ec28adf7).
## The reference ratios are computed here from the sources' rows, apart from the code they check.
##   godot --headless --path . --script res://sim/modern/test_modern_t2_deaths.gd
## M010   transcription (8ac5c606, TO_E 03:53): the spec's income function and health factor equal m010_pooled_inputs.py's output at
##        math-reports 7ac5b83d, v2 (M011; b0, b1, τ² as canon_f of the script's, the spec's load rule; the multipliers at 67, 70, 75, 80, 82 to 4 decimals; health [1, 1.2, 2.317, 3.180])
## T2s-gr (1) each of M010's 10 main-set observations (its two-group log HR y and SE) against the function's y at its age at risk,
##        inside z se ⊕ τ at a 5% family rate over the 10 (Bonferroni, z 2.807); R73's 11 rows by the band averages reported
## T2s-gr (2) the health factor against R74's 4 model rows by sex: m_3 ÷ m_1 (AGES model 1B) and m_4 ÷ m_3 (NIPPON DATA90 model 2)
##        inside the row's CI widened to a 5% family rate over 4 (z 2.498); m_3 ÷ grades 1-2's weighted mean at 65+ reported
## c      the calibration solves what it declares: at the start, Σ_{g,k} s_{g,k} exp(−c m_g I_k μ_a) = 1 − q_x(a, s) within 1e-9 at
##        every single age and sex, s the age's own joint shares or, where the age holds no person, its band's (counted); the ratio of
##        annual probabilities reported
const PEOPLE = preload("res://sim/modern/people/people.gd")
const LC = preload("res://sim/modern/people/life_course.gd")
const MS = preload("res://sim/modern/modern_status.gd")
const CANON = preload("res://sim/modern/canon.gd")
const Z_R73 := 2.8376
const Z_M010 := 2.807034
## m010_pooled_inputs.py v2's output at math-reports 7ac5b83d (M011; python3 -I, R73 and R74 from research-notes), transcribed
const M010_B0 := 0.159550021637047
const M010_B1 := -0.016611385872074697
const M010_TAU2 := 0.02165264764298906
const M010_CHECK := {"67": [1.0, 1.1574514408014211, 1.3396938378132859, 1.5506305628097732], "70": [1.0, 1.128967474352437, 1.2745675581457205, 1.4389453170113269], "75": [1.0, 1.0830433672203092, 1.1729829352799055, 1.270391387917511], "80": [1.0, 1.0389873596249664, 1.0794947334604594, 1.1215813828471397], "82": [1.0, 1.0218708973464525, 1.044220130843644, 1.0670581621324247]}
const M010_HEALTH := [1.0, 1.2, 2.317, 3.18]
## M032b's scale on the log multipliers (math-reports 8eddecd1): the spec's m_g = round(m0^lambda, 3), m0 = M010_HEALTH; with T2.2c's
## 4b, m_4b = m_4a; M032b's solver on the spec's 2023-10-01 cohort and 令和5年 qx (R96's refresh; 1.3964 on the 2022 table)
const M032B_LAMBDA := 1.3972
## [id, age at risk, y, se]
const M010_OBS := [["R73-009 M", 72.5, 0.19845093872383832, 0.0742863177222006], ["R73-011 M", 82.0, -0.01980262729617973, 0.059713500781834496], ["R73-013 F", 72.5, 0.4942963218147801, 0.12385631052695982], ["R73-015 F", 82.0, -0.17395330712343798, 0.08945492733006984], ["R73-018 M", 67.0, 0.1906203596086497, 0.21707234911538092], ["R73-019 M", 67.0, 0.3852624007906449, 0.1768265095755335], ["R73-020 F", 67.0, 0.11332868530700327, 0.3777484055047742], ["R73-021 F", 67.0, -0.40047756659712525, 0.3216049269135736], ["R73-001/R73-002/R73-003 M", 75.0, 0.3401754717150547, 0.07208801532958557], ["R73-005/R73-006/R73-007 F", 75.0, 0.38236080054220545, 0.21163082095381233]]
const Z_R74 := 2.4977
const Z95 := 1.959964
## [id, ages from, ages to, low band [from, to) as income shares from the bottom, reference band, published value, ci lo, ci hi,
## published as the higher group's HR (inverted to low vs high)]
const R73_ROWS := [
	["R73-009 JAGES M 65-74", 65, 74, [0.0, 1.0 / 3.0], [1.0 / 3.0, 1.0], 0.82, 0.71, 0.95, true],
	["R73-011 JAGES M 75+", 75, 89, [0.0, 1.0 / 3.0], [1.0 / 3.0, 1.0], 1.02, 0.91, 1.15, true],
	["R73-013 JAGES F 65-74", 65, 74, [0.0, 1.0 / 3.0], [1.0 / 3.0, 1.0], 0.61, 0.48, 0.78, true],
	["R73-015 JAGES F 75+", 75, 89, [0.0, 1.0 / 3.0], [1.0 / 3.0, 1.0], 1.19, 1.00, 1.42, true],
	["R73-018 Komo-Ise M working", 47, 77, [0.0, 0.175], [0.175, 1.0], 1.21, 0.79, 1.85, false],
	["R73-019 Komo-Ise M retired", 47, 77, [0.0, 0.175], [0.175, 1.0], 1.47, 1.04, 2.08, false],
	["R73-020 Komo-Ise F working", 47, 77, [0.0, 0.175], [0.175, 1.0], 1.12, 0.53, 2.33, false],
	["R73-021 Komo-Ise F retired", 47, 77, [0.0, 0.175], [0.175, 1.0], 0.67, 0.36, 1.27, false],
	["R73-025 JPHC M 40-59", 40, 59, [0.0, 0.2], [0.8, 1.0], 1.30, 1.09, 1.54, false],
	["R73-026 JPHC F 40-59", 40, 59, [0.0, 0.2], [0.8, 1.0], 1.34, 1.02, 1.78, false],
	["R73-024 JPHC T 40-59", 40, 59, [0.0, 0.2], [0.8, 1.0], 1.31, 1.13, 1.51, false]]
## [id, numerator grade, denominator grade (0-based), value, ci lo, ci hi]
const R74_ROWS := [
	["R74-0001 AGES 1B M, grade 3 / grade 1", 2, 0, 2.44, 2.14, 2.80],
	["R74-0005 AGES 1B F, grade 3 / grade 1", 2, 0, 1.88, 1.44, 2.47],
	["R74-0024 NIPPON DATA90 model 2 M, grade 4 / grade 3", 3, 2, 1.31, 1.00, 1.73],
	["R74-0025 NIPPON DATA90 model 2 F, grade 4 / grade 3", 3, 2, 1.43, 1.10, 1.84]]


func _init() -> void:
	var st = MS.new()
	st.load(2024, ["JPN"])
	var p = PEOPLE.new()
	p.households = true
	var err: String = p.create("JPN", 1, st.cohort["JPN"], st.qx["JPN"], {"13": {"pop_thousand": 14178}, "47": {"pop_thousand": 1467}}, 300)
	check(err == "", "households built: " + err)
	var lcv: Dictionary = p.hh_spec["life_course"]["value"]
	_income(p, lcv["death_income_factor"]["value"])
	_health(p, lcv["death_multiplier"]["value"])
	_c(p, lcv)
	finish()


## The reference factor at age a and quartile k (0 top): M010's form on the spec's coefficients
func _r(f: Dictionary, a: int, k: int) -> float:
	return exp(0.5 * float(k) * (float(f["b0"]) + float(f["b1"]) * (clampf(float(a), float(f["range"][0]), float(f["range"][1])) - float(f["a0"]))))


func _band_mean(f: Dictionary, a: int, lo: float, hi: float) -> float:
	var s: float = 0.0
	for k: int in 4:
		var b0: float = float(3 - k) * 0.25
		s += maxf(0.0, minf(hi, b0 + 0.25) - maxf(lo, b0)) * _r(f, a, k)
	return s / (hi - lo)


func _income(p: RefCounted, f: Dictionary) -> void:
	var miss: int = 0
	var miss95: int = 0
	var txt: String = ""
	var same: bool = true
	for a: int in 106:
		for k: int in 4:
			same = same and absf(LC.income_factor(p, a, k) - _r(f, a, k)) < 1e-12
	for row: Array in R73_ROWS:
		var r: float = 0.0
		for a: int in range(int(row[1]), int(row[2]) + 1):
			r += _band_mean(f, a, float(row[3][0]), float(row[3][1])) / _band_mean(f, a, float(row[4][0]), float(row[4][1]))
		r /= float(int(row[2]) - int(row[1]) + 1)
		var l: float = log(float(row[5]))
		var se: float = (log(float(row[7])) - log(float(row[6]))) / (2.0 * Z95)
		if bool(row[8]):
			l = -l
		var lr: float = log(r)
		if absf(lr - l) > Z_R73 * se:
			miss += 1
			txt += " %s OUT (model %.3f, source %.3f, band %.3f-%.3f);" % [row[0], r, exp(l), exp(l - Z_R73 * se), exp(l + Z_R73 * se)]
		if absf(lr - l) > Z95 * se:
			miss95 += 1
	check(same, "T2s-gr (1) life_course.income_factor equals M010's form on the spec's coefficients at every age and quartile (1e-12)")
	var tr_ok: bool = float(f["b0"]) == CANON.canon_f(M010_B0) and float(f["b1"]) == CANON.canon_f(M010_B1) and float(f["tau2"]) == CANON.canon_f(M010_TAU2)
	var tr_txt: String = ""
	for ak: String in M010_CHECK:
		for k2: int in 4:
			var v: float = LC.income_factor(p, int(ak), k2)
			if absf(v - float(M010_CHECK[ak][k2])) >= 0.5e-4:
				tr_ok = false
				tr_txt += " age %s q%d %.6f against %.6f;" % [ak, k2, v, float(M010_CHECK[ak][k2])]
	check(tr_ok, "M010 transcription: b0, b1, tau2 equal the script's as the spec loads them (canon_f of its exact output, which the file holds), the multipliers at 67, 70, 75, 80, 82 to 4 decimals;%s" % tr_txt)
	var om: int = 0
	var otxt: String = ""
	for o: Array in M010_OBS:
		var ym: float = float(f["b0"]) + float(f["b1"]) * (clampf(float(o[1]), float(f["range"][0]), float(f["range"][1])) - float(f["a0"]))
		var band: float = Z_M010 * sqrt(float(o[3]) * float(o[3]) + float(f["tau2"]))
		var inside: bool = absf(float(o[2]) - ym) <= band
		om += 0 if inside else 1
		otxt += " %s at %.1f: y %.3f model %.3f ± %.3f %s;" % [o[0], float(o[1]), float(o[2]), ym, band, "in" if inside else "OUT"]
	check(om == 0, "T2s-gr (1) M010's 10 observations against the function at their ages, z se ⊕ τ at a 5%% family rate: %d misses;%s" % [om, otxt])
	print("REPORT T2s-gr (1, reported) R73's 11 rows by the band averages: %d outside at the 5%% family rate (z 2.838), %d at plain 95%%;%s" % [miss, miss95, txt])


func _health(p: RefCounted, m: Array) -> void:
	var miss: int = 0
	var txt: String = ""
	for row: Array in R74_ROWS:
		var r: float = float(M010_HEALTH[int(row[1])]) / float(M010_HEALTH[int(row[2])])
		var l: float = log(float(row[3]))
		var se: float = (log(float(row[5])) - log(float(row[4]))) / (2.0 * Z95)
		var inside: bool = absf(log(r) - l) <= Z_R74 * se
		miss += 0 if inside else 1
		txt += " %s model %.3f source %.2f band %.3f-%.3f %s;" % [row[0], r, row[3], exp(l - Z_R74 * se), exp(l + Z_R74 * se), "in" if inside else "OUT"]
	check(miss == 0, "T2s-gr (2, AMENDED for M032b; LABEL: input shape against R74, not a check of the model's deaths) the health factor's shape m0 inside R74's 4 rows at a 5%% family rate: %d misses;%s (the current-grade m_g %s beside, not compared)" % [miss, txt, str(m)])
	var hm_ok: bool = m.size() >= 4
	for g0: int in m.size():
		var want: float = snappedf(pow(float(M010_HEALTH[mini(g0, 3)]), M032B_LAMBDA), 0.001)
		hm_ok = hm_ok and absf(float(m[g0]) - want) < 1e-9
	check(hm_ok, "M010 transcription (AMENDED for M032b): the health factor %s equals round(m0^%.4f, 3) with m0 = M010 §3's %s" % [str(m), M032B_LAMBDA, str(M010_HEALTH)])
	var w12: float = 0.0
	var m12: float = 0.0
	for i: int in p.n:
		if p.age[i] >= 65 and p.health[i] <= 1:
			w12 += p.weight[i]
			m12 += p.weight[i] * float(m[p.health[i]])
	print("REPORT T2s-gr (2, reported) m_3 ÷ the weighted mean of grades 1-2 at 65+ (AGES's excellent/good reference) %.3f" % [float(m[2]) / (m12 / maxf(1e-9, w12))])


func _c(p: RefCounted, lcv: Dictionary) -> void:
	var m: Array = lcv["death_multiplier"]["value"]
	var ng: int = m.size()
	var nc: int = ng * 4
	var f: Dictionary = lcv["death_income_factor"]["value"]
	var w := PackedFloat64Array()
	w.resize(18 * nc)
	var ws := PackedFloat64Array()
	ws.resize(106 * 2 * nc)
	for i: int in p.n:
		w[(mini(p.age[i] / 10, 8) * 2 + p.sex[i]) * nc + p.health[i] * 4 + LC.quartile(p, i)] += p.weight[i]
		ws[(mini(p.age[i], 105) * 2 + p.sex[i]) * nc + p.health[i] * 4 + LC.quartile(p, i)] += p.weight[i]
	var fell: int = 0
	var worst: float = 0.0
	var cells: int = 0
	var lt: Dictionary = lcv["qx_2022"]["value"]
	var txt: String = ""
	for s: int in 2:
		var col: Array = lt["men" if s == p.MALE else "women"]
		for a: int in col.size():
			var q: float = float(col[a])
			var src: PackedFloat64Array = ws
			var cell: int = (a * 2 + s) * nc
			var tot: float = 0.0
			for x0: int in nc:
				tot += ws[cell + x0]
			if tot <= 0.0:
				src = w
				cell = (mini(a / 10, 8) * 2 + s) * nc
				fell += 1
				for x: int in nc:
					tot += w[cell + x]
			if tot <= 0.0 or q >= 1.0:
				continue
			var mu: float = -log(1.0 - q)
			var surv: float = 0.0
			for g: int in ng:
				for k: int in 4:
					surv += src[cell + g * 4 + k] / tot * exp(-p.lc_c[a * 2 + s] * float(m[g]) * _r(f, a, k) * mu)
			worst = maxf(worst, absf(surv - (1.0 - q)))
			cells += 1
		if s == 0:
			for a2: int in [30, 50, 70, 85]:
				txt += " age %d: grade 4 / grade 1 %.3f, bottom / top %.3f;" % [a2, LC.h_death(p, a2, s, 3, 0) / LC.h_death(p, a2, s, 0, 0), LC.h_death(p, a2, s, 0, 3) / LC.h_death(p, a2, s, 0, 0)]
	check(cells > 150 and worst < 1e-9 and fell == p.lc_c_band, "c: the start's mix reproduces the life table at %d single ages x sexes, worst |survival − (1 − q_x)| %s; ages x sexes on their band's shares %d (the code's %d)" % [cells, str(worst), fell, p.lc_c_band])
	print("REPORT c (reported) the ratio of annual probabilities, men:%s" % txt)
