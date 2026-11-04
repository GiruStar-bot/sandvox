extends "res://tools/test/test_kit.gd"
## T2s-dgb-h (HELD OUT) and T2s-dgb (a read-back) (ISS_TIERED §14.6 (9)-(11); TO_E 13:47, 13:50, R93; declared at 8ba0eefa, 0193287c
## and b1074afe before this code): the model's hazard ratios by BASELINE grade, computed deterministically from the spec (no draws,
## no national build). A closed cohort per baseline single age × sex at the prevalence and the class mix P(stable | side); each month
## the hazard 1 − exp(−c m_g μ ÷ 12) on the current grade, μ the 2022 table's at the attained age, c per attained age on the prevalence
## (the start's form, the income factor left out as M032b); each January from the second the two-class IPF (LC.grade_flows) to the
## attained age's prevalence, the baseline groups moved by the whole cohort's rates; the HR the Mantel-Haenszel rate ratio over
## baseline single age × sex strata
## T2s-dgb-h  (RE-SPECIFIED, §14.6 (12), V121: consistency, not held out) grade 4 ÷ grades 1-3 at baseline over 12.2 years (146 months), baseline ages 65-90 on a normal truncated to them with its
##            weights' mean 72.5 and SD 5.9 (R93; the cohort 65+),
##            by sex, against NIPPON DATA90 (R74-0024 M 1.31, 1.00-1.73; R74-0025 F 1.43, 1.10-1.84), |ln HR − ln source| ≤ 2.241 ×
##            the source's log SE (C 2 x R 1)
## T2s-dgb    (read-back) bad (3-4) ÷ good (1-2) at baseline over 4 years at 65-100, weighted by the start's 2024 cohort, both sexes
##            against AGES 1B's pooled 2.317 (M032b's fit), by sex beside AGES's 2.44 (2.14-2.80) and 1.88 (1.44-2.47)
##   godot --headless --path . --script res://sim/modern/test_modern_t2_dgb.gd
const PEOPLE = preload("res://sim/modern/people/people.gd")
const HH = preload("res://sim/modern/people/households.gd")
const LC = preload("res://sim/modern/people/life_course.gd")
const MS = preload("res://sim/modern/modern_status.gd")
const Z95 := 1.959964
const Z_H := 2.241
const TOSA := [["Tosa Town M (ADL dependence, 4 years)", 0, 3.09, 1.67, 5.70], ["Tosa Town F (ADL dependence, 4 years)", 1, 1.82, 0.94, 3.53]]
const NIPPON := [["R74-0024 NIPPON DATA90 model 2 M", 0, 1.31, 1.00, 1.73], ["R74-0025 NIPPON DATA90 model 2 F", 1, 1.43, 1.10, 1.84]]


func _init() -> void:
	var p = PEOPLE.new()
	p.state = "JPN"
	var err: String = HH.load_spec(p)
	check(err == "", "the households spec loaded: '%s'" % err)
	var st = MS.new()
	st.load(2024, ["JPN"])
	var co: PackedFloat64Array = st.cohort["JPN"]
	var mg: Array = LC._lc(p, "death_multiplier")
	var bad: int = 0
	var nrm: Array = _truncated_normal(72.5, 5.9)
	var r43: String = ""
	var txt: String = " the baseline ages 65-90 on a normal (%.3f, %.3f) truncated to them, its weights' mean %.3f and SD %.3f;" % [float(nrm[0]), float(nrm[1]), float(nrm[2]), float(nrm[3])]
	for row: Array in NIPPON:
		var s: int = int(row[1])
		var strata: Array = []
		var strata43: Array = []
		for a: int in range(65, 91):
			var w: float = exp(-0.5 * pow((float(a) - float(nrm[0])) / float(nrm[1]), 2.0))
			strata.append(_cohort(p, a, s, w, [3, 4], [0, 1, 2], 146))
			strata43.append(_cohort(p, a, s, w, [3, 4], [2], 146))
		var mh: float = _mh(strata)
		r43 += " %s %.3f;" % ["men" if s == 0 else "women", _mh(strata43)]
		var se: float = (log(float(row[4])) - log(float(row[3]))) / (2.0 * Z95)
		var inside: bool = mh > 0.0 and absf(log(mh) - log(float(row[2]))) <= Z_H * se
		bad += 0 if inside else 1
		txt += " %s: model %.3f against %.2f (%.2f-%.2f), |ln| %.3f against %.3f %s;" % [row[0], mh, float(row[2]), float(row[3]), float(row[4]), absf(log(mh) - log(float(row[2]))) if mh > 0.0 else INF, Z_H * se, "in" if inside else "OUT"]
	check(bad == 0, "T2s-dgb-h (§14.6 (12), V121: CONSISTENCY with a source that shaped the input, the groups differ, 12.7%% vs 23-26%%; not held out) the grade 4 (4a and 4b) ÷ grades 1-3 HR by baseline grade over 12.2 years at NIPPON DATA90's baseline ages, by sex, m_g %s:%s" % [str(mg), txt])
	print("REPORT T2s-dgb-h's grade 4 ÷ grade 3 read (the first read's form, FAIL recorded at d52d1185; the kernel's dilution of the 1.556 shape):%s" % r43)
	var both: Array = []
	var by: Array = [[], []]
	for s2: int in 2:
		for a2: int in range(65, 101):
			var r: Array = _cohort(p, a2, s2, co[mini(a2, co.size() / 2 - 1) * 2 + s2], [2, 3, 4], [0, 1], 48)
			both.append(r)
			(by[s2] as Array).append(r)
	var hb: float = _mh(both)
	print("REPORT T2s-dgb (a READ-BACK of M032b's fit) the bad ÷ good HR by baseline grade over 4 years at 65+, both sexes, %.3f against AGES 1B's pooled 2.317; men %.3f (AGES 2.44, 2.14-2.80), women %.3f (AGES 1.88, 1.44-2.47)" % [hb, _mh(by[0]), _mh(by[1])])
	var bt: int = 0
	var ttxt: String = ""
	for row2: Array in TOSA:
		var s3: int = int(row2[1])
		var st3: Array = []
		for a3: int in range(65, 101):
			st3.append(_cohort(p, a3, s3, co[mini(a3, co.size() / 2 - 1) * 2 + s3], [4], [0, 1, 2, 3], 48))
		var mh3: float = _mh(st3)
		var se3: float = (log(float(row2[4])) - log(float(row2[3]))) / (2.0 * Z95)
		var in3: bool = mh3 > 0.0 and absf(log(mh3) - log(float(row2[2]))) <= Z_H * se3
		bt += 0 if in3 else 1
		ttxt += " %s: model %.3f against %.2f (%.2f-%.2f), |ln| %.3f against %.3f %s;" % [row2[0], mh3, float(row2[2]), float(row2[3]), float(row2[4]), absf(log(mh3) - log(float(row2[2]))) if mh3 > 0.0 else INF, Z_H * se3, "in" if in3 else "OUT"]
	check(bt == 0, "T2s-dgb-t (HELD OUT, §14.6 (13), T2.2c) the 4b ÷ (grades 1-3 and 4a) HR by baseline state over 4 years at 65-100 on the start's 2024 cohort, by sex, against Tosa (the abstract's values; the women's interval is wide, so a pass there is the weaker evidence):%s" % ttxt)
	finish()


## The underlying normal's [mean, SD] whose weights on single ages 65-90 have mean m and SD sd, by Newton's method on the two
## moments (finite-difference Jacobian), with the weights' own [mean, SD] beside
func _truncated_normal(m: float, sd: float) -> Array:
	var mu: float = m
	var sg: float = sd
	for it: int in 200:
		var f0: Array = _wmom(mu, sg)
		var f1: Array = _wmom(mu + 1e-6, sg)
		var f2: Array = _wmom(mu, sg + 1e-6)
		var j00: float = (float(f1[0]) - float(f0[0])) / 1e-6
		var j01: float = (float(f2[0]) - float(f0[0])) / 1e-6
		var j10: float = (float(f1[1]) - float(f0[1])) / 1e-6
		var j11: float = (float(f2[1]) - float(f0[1])) / 1e-6
		var r0: float = m - float(f0[0])
		var r1: float = sd - float(f0[1])
		var det: float = j00 * j11 - j01 * j10
		var dmu: float = (j11 * r0 - j01 * r1) / det
		var dsg: float = (-j10 * r0 + j00 * r1) / det
		mu += dmu
		sg += dsg
		if absf(dmu) + absf(dsg) < 1e-12:
			break
	var fm: Array = _wmom(mu, sg)
	return [mu, sg, fm[0], fm[1]]


func _wmom(mu: float, sg: float) -> Array:
	var tw: float = 0.0
	var tm: float = 0.0
	for a: int in range(65, 91):
		var w: float = exp(-0.5 * pow((float(a) - mu) / sg, 2.0))
		tw += w
		tm += w * float(a)
	var mean: float = tm / tw
	var tv: float = 0.0
	for a2: int in range(65, 91):
		tv += exp(-0.5 * pow((float(a2) - mu) / sg, 2.0)) * (float(a2) - mean) * (float(a2) - mean)
	return [mean, sqrt(tv / tw)]


## One stratum: [deaths, person-years] of the baseline grades num and den, the cohort at baseline age a0 and sex s weighted w
func _cohort(p: RefCounted, a0: int, s: int, w: float, num: Array, den: Array, months: int) -> Array:
	var mg: Array = LC._lc(p, "death_multiplier")
	var kp: Dictionary = LC._lc(p, "grade_kernel")
	var ps: Dictionary = kp["p_stable_given_side"]
	var pi0: PackedFloat64Array = LC.shares(p, a0, s)
	var pt: float = 0.0
	for g0: int in pi0.size():
		pt += pi0[g0]
	var ng: int = pi0.size()
	var whole := PackedFloat64Array()
	whole.resize(2 * ng)
	var gn := PackedFloat64Array()
	gn.resize(2 * ng)
	var gd := PackedFloat64Array()
	gd.resize(2 * ng)
	for g: int in ng:
		var st: float = float(ps["good" if g < 2 else "bad"])
		for c: int in 2:
			var x: float = w * pi0[g] / pt * (st if c == 0 else 1.0 - st)
			whole[c * ng + g] = x
			if num.has(g):
				gn[c * ng + g] = x
			if den.has(g):
				gd[c * ng + g] = x
	var dn: float = 0.0
	var tn: float = 0.0
	var dd: float = 0.0
	var td: float = 0.0
	var cache: Dictionary = {}
	for t: int in months:
		var a: int = mini(a0 + t / 12, 100)
		if t > 0 and t % 12 == 0:
			var pr: PackedFloat64Array = LC.grade_flows(p, whole, LC.shares(p, a, s))[0]
			whole = _move(whole, pr)
			gn = _move(gn, pr)
			gd = _move(gd, pr)
		if not cache.has(a):
			cache[a] = _c_at(p, a, s)
		var cmu: float = float(cache[a])
		for x2: int in 2 * ng:
			var q: float = 1.0 - exp(-cmu * float(mg[x2 % ng]) / 12.0) if cmu < INF else 1.0
			tn += gn[x2] / 12.0
			td += gd[x2] / 12.0
			dn += gn[x2] * q
			dd += gd[x2] * q
			whole[x2] -= whole[x2] * q
			gn[x2] -= gn[x2] * q
			gd[x2] -= gd[x2] * q
	return [dn, tn, dd, td]


func _move(v: PackedFloat64Array, pr: PackedFloat64Array) -> PackedFloat64Array:
	var ng: int = v.size() / 2
	var out := PackedFloat64Array()
	out.resize(2 * ng)
	for rw: int in 2 * ng:
		for h: int in ng:
			out[(rw / ng) * ng + h] += v[rw] * pr[rw * ng + h]
	return out


## c × μ at age a and sex s: c by bisection (on [0, 16], 60 halvings) of Σ π_g exp(−c m_g μ) = exp(−μ) at the prevalence
func _c_at(p: RefCounted, a: int, s: int) -> float:
	var mu: float = LC._mu(p, a, s)
	if mu == INF:
		return INF
	var mg: Array = LC._lc(p, "death_multiplier")
	var pi0: PackedFloat64Array = LC.shares(p, a, s)
	var pt: float = 0.0
	for g0: int in pi0.size():
		pt += pi0[g0]
	var lo: float = 0.0
	var hi: float = 16.0
	for it: int in 60:
		var c: float = 0.5 * (lo + hi)
		var surv: float = 0.0
		for g: int in pi0.size():
			surv += pi0[g] / pt * exp(-c * float(mg[g]) * mu)
		if surv > exp(-mu):
			lo = c
		else:
			hi = c
	return 0.5 * (lo + hi) * mu


func _mh(rows: Array) -> float:
	var num: float = 0.0
	var den: float = 0.0
	for r: Array in rows:
		var t: float = float(r[1]) + float(r[3])
		if t <= 0.0:
			continue
		num += float(r[0]) * float(r[3]) / t
		den += float(r[2]) * float(r[1]) / t
	return num / den if den > 0.0 else 0.0
