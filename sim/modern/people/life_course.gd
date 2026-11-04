extends RefCounted
## The life course (ISS_HOUSEHOLD_REDESIGN.md §10.2, H2), behind people.households: field facts (the four health grades, death by the
## life table) and the actors' choices (partnering, a birth, leaving home, divorce, an elderly parent moving in, an institution), each a
## monthly keyed draw on the person's pid. The dead are removed at the month's end and newborns appended: no slot is reused. Roles index
## ROLES; a household's type is re-read from its members' roles after every event (5 is an institution resident, one record each).
const ROLES := ["head", "partner", "child", "parent", "other"]
const INSTITUTION := 5
const KINDS := ["death", "partnered", "birth", "left_home", "divorce", "moved_in", "institution", "widowed", "moved"]


const NG := 5   # the health states: grades 1, 2, 3, 4a and 4b (T2.2c)


static func _lc(p: RefCounted, k: String) -> Variant:
	return ((p.hh_spec["life_course"] as Dictionary)["value"] as Dictionary)[k]["value"]


static func _b10(a: int) -> int:
	return mini(a / 10, 8)


## The state shares [1, 2, 3, 4a, 4b] of an age and sex: grade 2+ the symptom rate, grade 4 the daily-life limitation rate (R64), grade
## 3 a third of the rest; the medical level divides grades 3 and 4; T2.2c (M034): 4b the LTCI recipients' share, grade 4 raised to it
## where it is the larger (grades 1-3 scaled down), 4a the rest of grade 4; M035: each read at the single age from the spec's smoothed
## prevalence_single_age
## Why raise grade 4: the household survey misses the institutionalised, who are among the recipients (M034 §1)
static func shares(p: RefCounted, a: int, s: int) -> PackedFloat64Array:
	var sa: Dictionary = _lc(p, "prevalence_single_age")
	var sx: String = "men" if s == 0 else "women"
	var a1: int = clampi(a, 0, 100)
	var s2: float = float(sa["g2plus"][sx][a1])
	var med: float = float(_lc(p, "medical_level"))
	var g4: float = float(sa["g4"][sx][a1]) / med
	var g3: float = maxf(0.0, s2 - g4) * float(_lc(p, "poor_share_of_rest")) / med
	var g2: float = maxf(0.0, maxf(s2, g4) - g4 - g3)
	var g1: float = maxf(0.0, 1.0 - g2 - g3 - g4)
	var b4: float = ltci_share(p, a, s)
	if b4 > g4:
		var sc: float = (1.0 - b4) / (1.0 - g4)
		g1 *= sc
		g2 *= sc
		g3 *= sc
		g4 = b4
	return PackedFloat64Array([g1, g2, g3, g4 - b4, b4])


## T2.2c (M034 §1, M035 §3): the LTCI recipients' share at the single age a and sex s, smoothed from the spec's 5-year bands; pure
static func ltci_share(p: RefCounted, a: int, s: int) -> float:
	return float((_lc(p, "prevalence_single_age") as Dictionary)["b4"]["men" if s == 0 else "women"][clampi(a, 0, 100)])


static func draw_grade(p: RefCounted, i: int, tag: String) -> int:
	var sh: PackedFloat64Array = shares(p, p.age[i], p.sex[i])
	var x: float = p.u(tag, i, p.month)
	var acc: float = 0.0
	for g: int in NG:
		acc += sh[g]
		if x < acc:
			return g
	return NG - 1


## The life-course state at the start, after H1's households and the persons' attributes
static func start(p: RefCounted) -> void:
	var nm: Dictionary = _lc(p, "never_married")
	var u0: float = float(_lc(p, "union_start_age"))
	var free: Dictionary = {}      # R62 band x 2 + sex -> the band's one-person adults, whose status the band's need sets (§10.8 C3)
	p.health_class.resize(p.n)
	for i: int in p.n:
		p.health[i] = draw_grade(p, i, "grade0")
		draw_class(p, i, false)
		var r: int = p.hh_role[i]
		var single_adult: bool = r == p.R_HEAD and p.partner[i] < 0 and (p.hh_members[p.hh_id[i]] as PackedInt32Array).size() == 1
		if p.partner[i] >= 0 or r == p.R_PARENT or (r == p.R_HEAD and p.hh_type[p.hh_id[i]] == p.HK_SINGLE_PARENT):
			p.ever_married[i] = 1
		elif single_adult and p.HH._nm_band(p.age[i], nm["ages"]) >= 0:
			var key: int = p.HH._nm_band(p.age[i], nm["ages"]) * 2 + p.sex[i]
			free[key] = (free.get(key, []) as Array) + [i]
		elif single_adult and p.age[i] >= 25:
			var k: int = 0
			for t: int in (nm["ages"] as Array).size():
				if p.age[i] >= int(nm["ages"][t]):
					k = t
			p.ever_married[i] = 1 if p.u("evermar0", i) >= float(nm["men" if p.sex[i] == p.MALE else "women"][k]) else 0
		p.ever_left[i] = 0 if r == p.R_CHILD else 1
		p.last_birth[i] = -999
		if p.sex[i] == p.FEMALE and p.partner[i] >= 0:
			p.union_month[i] = -12 * maxi(0, p.age[i] - int(round(u0)))
			p.union_month[p.partner[i]] = p.union_month[i]
	for h: int in p.hh_n:
		var ms: PackedInt32Array = p.hh_members[h]
		var mother: int = -1
		var kids: int = 0
		for i2: int in ms:
			if p.hh_role[i2] == p.R_CHILD:
				kids += 1
			elif p.hh_role[i2] <= p.R_PARTNER and (p.sex[i2] == p.FEMALE or p.hh_type[h] == p.HK_SINGLE_PARENT):
				mother = i2
		if mother >= 0 and p.sex[mother] == p.FEMALE:
			p.births_n[mother] = kids
	_never_married_start(p, nm, free)
	# A3-1: a woman of 35+ with a partner, or a single parent, starts at her completed parity (JNFS16) when it is above her children at
	# home. Why not the children at home alone: an empty-nest mother counted as childless and wanted a first child at 40-49 (§10.4)
	var cp: Dictionary = _lc(p, "completed_parity")
	for i3: int in p.n:
		if p.sex[i3] == p.FEMALE and p.age[i3] >= 35 and (p.partner[i3] >= 0 or (p.hh_role[i3] == p.R_HEAD and p.hh_type[p.hh_id[i3]] == p.HK_SINGLE_PARENT)):
			var x: float = p.u("parity0", i3)
			var acc: float = 0.0
			var drawn: int = 4
			for k3: int in 5:
				acc += float(cp[str(k3)])
				if x < acc:
					drawn = k3
					break
			p.births_n[i3] = maxi(p.births_n[i3], drawn)
	p.intends_marry.resize(p.n)
	p.intends_marry.fill(-1)
	p.intended_kids.resize(p.n)
	p.intended_kids.fill(-1)
	for i4: int in p.n:
		if p.ever_married[i4] == 1:
			if p.partner[i4] >= 0:
				p.intends_marry[i4] = 1
			else:
				_draw_intention(p, i4, 0)
		elif p.age[i4] >= 18:
			_draw_intention(p, i4)
		if p.sex[i4] == p.FEMALE and p.age[i4] >= 15:
			_draw_kids(p, i4, p.births_n[i4])


## The yearly turn's draws (§10.6): the intention to marry at 18 and a woman's intended children at 15, for those not drawn at the start
static func year_turn(p: RefCounted, i: int) -> void:
	if p.age[i] >= 18 and p.intends_marry[i] < 0:
		_draw_intention(p, i)
	if p.sex[i] == p.FEMALE and p.age[i] >= 15 and p.intended_kids[i] < 0:
		_draw_kids(p, i, p.births_n[i])


## The intention to marry (R66, P) by sex and age band; 35+ at 30-34's (T). A union's end redraws it as the intention to remarry
## (§10.7 B2, T: R66 has none, so the never-married's at the same age), keyed by the month it ended (ended > 0)
static func _draw_intention(p: RefCounted, i: int, ended: int = -1) -> void:
	var hi: float = h_intend(p, p.age[i], p.sex[i])
	p.intends_marry[i] = 1 if (p.below("lc_intend", i, 0, 0, hi) if ended < 0 else p.below("lc_reintend", i, ended, 0, hi)) else 0


## The probability that a person of age a and sex s intends to marry (R66's band, P); pure (§14.1)
static func h_intend(p: RefCounted, a: int, s: int) -> float:
	var im: Dictionary = _lc(p, "intend_to_marry")
	var k: int = 0
	for b: int in (im["bands"] as Array).size():
		if a >= int(String(im["bands"][b]).split("-")[0]):
			k = b
	return p.rone_out("h_intend", float(im["men" if s == p.MALE else "women"][k]))


## A woman's intended number of children (R66, P): her age band's distribution (§10.9; under 20 the 20-24 band's, 50+ the 45-49
## band's, T); at least her births so far, after 16 redraws (T)
static func _draw_kids(p: RefCounted, i: int, born: int) -> void:
	var ik: Dictionary = law_kids(p, p.age[i])
	var got: int = born
	for r: int in 16:
		var x: float = p.u("lc_kids", i, r)
		var acc: float = 0.0
		var k: int = 5
		for c: int in 6:
			acc += float(ik[str(c)])
			if x < acc:
				k = c
				break
		if k >= born:
			got = k
			break
	p.intended_kids[i] = got


## A woman's law of intended children at age a: her band's distribution over 0..5 (R66, P); pure (§14.1)
static func law_kids(p: RefCounted, a: int) -> Dictionary:
	var ikd: Dictionary = _lc(p, "intended_children")
	var bands: Array = ikd["bands"]
	var b: int = 0
	for k0: int in bands.size():
		if a >= int(String(bands[k0]).split("-")[0]):
			b = k0
	return ikd["by_age"][b]


## The start's never-married share per sex and R62 band (§10.8 C3): the band needs R62's share of its persons never married; those the
## household fixes (children at home, the unpartnered others) count first, and the band's one-person adults take the rest, each never
## married with probability need / their number (one keyed draw). Why not every person drawn from R62: a partner drawn never married
## would make an unmarried couple of the start's couples; why not the weights: they hid the sample's mismatch (V101)
static func _never_married_start(p: RefCounted, nm: Dictionary, free: Dictionary) -> void:
	var lo: Array = nm["ages"]
	var tot := PackedInt32Array()
	tot.resize(lo.size() * 2)
	var fixed_nm := PackedInt32Array()
	fixed_nm.resize(lo.size() * 2)
	var is_free := {}
	for key: int in free:
		for i0: int in (free[key] as Array):
			is_free[i0] = true
	for i: int in p.n:
		var b: int = p.HH._nm_band(p.age[i], lo)
		if b < 0:
			continue
		tot[b * 2 + p.sex[i]] += 1
		if not is_free.has(i) and p.ever_married[i] == 0:
			fixed_nm[b * 2 + p.sex[i]] += 1
	p.lc_nm_short = PackedFloat64Array()
	p.lc_nm_short.resize(lo.size() * 2)
	for c: int in lo.size() * 2:
		var ms: Array = free.get(c, [])
		var need: float = float(nm["men" if c % 2 == 0 else "women"][c / 2]) * float(tot[c]) - float(fixed_nm[c])
		var q: float = clampf(need / float(ms.size()), 0.0, 1.0) if ms.size() > 0 else 0.0
		p.lc_nm_short[c] = need - q * float(ms.size())
		for i2: int in ms:
			p.ever_married[i2] = 0 if p.u("evermar0", i2) < q else 1


## The household's equivalized income of person i: the members' summed income ÷ √(members), R73's relative-poverty scale (§14.4a)
static func equivalized(p: RefCounted, i: int) -> float:
	var mem: PackedInt32Array = p.hh_members[p.hh_id[i]]
	var s: float = 0.0
	for j: int in mem:
		s += p.income[j]
	return s / sqrt(float(mem.size()))


## The equivalized-income quartile cuts by weight in each 10-year band, both sexes (§14.4a): three cuts a band, at the month's end
static func quartile_cuts(p: RefCounted) -> void:
	var by: Array = []
	for b: int in 9:
		by.append([])
	for i: int in p.n:
		(by[_b10(p.age[i])] as Array).append([equivalized(p, i), p.weight[i]])
	p.lc_qcut.resize(27)
	for b2: int in 9:
		var rows: Array = by[b2]
		rows.sort_custom(func(x: Array, y: Array) -> bool: return float(x[0]) < float(y[0]))
		var tot: float = 0.0
		for r: Array in rows:
			tot += float(r[1])
		var acc: float = 0.0
		var q: int = 0
		for r2: Array in rows:
			acc += float(r2[1])
			while q < 3 and acc >= tot * float(q + 1) / 4.0:
				p.lc_qcut[b2 * 3 + q] = float(r2[0])
				q += 1
		while q < 3:
			p.lc_qcut[b2 * 3 + q] = INF
			q += 1


## Person i's equivalized-income quartile, 0 the top to 3 the bottom, against the last month's cuts
static func quartile(p: RefCounted, i: int) -> int:
	var e: float = equivalized(p, i)
	var c: int = _b10(p.age[i]) * 3
	if e < p.lc_qcut[c]:
		return 3
	if e < p.lc_qcut[c + 1]:
		return 2
	if e < p.lc_qcut[c + 2]:
		return 1
	return 0


## The income factor I_k(a) (M010, D): exp(0.5 k (b0 + b1 (clamp(a, lo, hi) - a0))), k = 0 the top quartile to 3 the bottom
static func income_factor(p: RefCounted, a: int, k: int) -> float:
	var f: Dictionary = _lc(p, "death_income_factor")
	var x: float = clampf(float(a), float(f["range"][0]), float(f["range"][1])) - float(f["a0"])
	return p.DM.exp(0.5 * float(k) * (float(f["b0"]) + float(f["b1"]) * x))


static func _mu(p: RefCounted, a: int, s: int) -> float:
	var lt: Array = (_lc(p, "qx_2022") as Dictionary)["men" if s == p.MALE else "women"]
	var q: float = float(lt[mini(a, lt.size() - 1)])
	return INF if q >= 1.0 else -p.DM.log(1.0 - q)


## c_{a,s} per single age and sex (§14.4a, CALIBRATED), after the start's rake: bisection on Σ s_{g,k} exp(−c m_g I_k μ_a) = 1 − q_x
## over the age's own joint (grade × quartile) weighted shares (M010 (3)); an age and sex with no person takes its 10-year band's,
## counted in lc_c_band
## Why not the band's shares everywhere (51f0f11e): the band's mix differs across its single ages
static func solve_c(p: RefCounted) -> void:
	quartile_cuts(p)
	var m: Array = _lc(p, "death_multiplier")
	var ages: int = ((_lc(p, "qx_2022") as Dictionary)["men"] as Array).size()
	var w := PackedFloat64Array()
	w.resize(18 * NG * 4)
	var ws := PackedFloat64Array()
	ws.resize(ages * 2 * NG * 4)
	for i: int in p.n:
		var gk: int = p.health[i] * 4 + quartile(p, i)
		w[(_b10(p.age[i]) * 2 + p.sex[i]) * NG * 4 + gk] += p.weight[i]
		ws[(mini(p.age[i], ages - 1) * 2 + p.sex[i]) * NG * 4 + gk] += p.weight[i]
	p.lc_c.resize(ages * 2)
	p.lc_c_band = 0
	for a: int in ages:
		for s: int in 2:
			var src: PackedFloat64Array = ws
			var cell: int = (a * 2 + s) * NG * 4
			var tot: float = 0.0
			for x0: int in NG * 4:
				tot += ws[cell + x0]
			if tot <= 0.0:
				src = w
				cell = (_b10(a) * 2 + s) * NG * 4
				p.lc_c_band += 1
				for x: int in NG * 4:
					tot += w[cell + x]
			var mu: float = _mu(p, a, s)
			if tot <= 0.0 or mu == INF:
				p.lc_c[a * 2 + s] = 1.0
				continue
			var target: float = p.DM.exp(-mu)
			var lo: float = 0.0
			var hi: float = 16.0
			for it: int in 60:
				var c: float = 0.5 * (lo + hi)
				var surv: float = 0.0
				for g: int in NG:
					for k: int in 4:
						surv += src[cell + g * 4 + k] / tot * p.DM.exp(-c * float(m[g]) * income_factor(p, a, k) * mu)
				if surv > target:
					lo = c
				else:
					hi = c
			p.lc_c[a * 2 + s] = 0.5 * (lo + hi)


## The year's death draw at the person's turn (people._year), by h_death. Why not the status cohort's qx: that is a Gompertz shape
## scaled to the published deaths (D), and §2.1 declared the table
static func dies(p: RefCounted, i: int) -> bool:
	var q: float = h_death(p, p.age[i], p.sex[i], p.health[i], quartile(p, i))
	p.lc_expected[_dband(p.age[i]) * 2 + p.sex[i]] += q
	if p.below("death", i, p.month, 0, q):
		p.lc_dying.append(i)
		return true
	return false


## The year's death probability at single age a, sex s, health grade g and income quartile k (§14.4a): 1 − exp(−c_{a,s} m_g r_k(a) μ_a),
## μ_a = −ln(1 − q_x) of the 2022 life table; pure
static func h_death(p: RefCounted, a: int, s: int, g: int, k: int) -> float:
	var mu: float = _mu(p, a, s)
	if mu == INF:
		return p.rone_out("h_death", 1.0)
	var ac: int = mini(a, p.lc_c.size() / 2 - 1)
	return p.rone_out("h_death", death_q(p, p.lc_c[ac * 2 + s], a, g, k, mu, 1.0))


## The death probability over 1 ÷ per of a year at c, single age a, grade g, quartile k and μ (§14.4a's form, one source for the persons
## and the tiers, §14.6 (2) as built); pure
static func death_q(p: RefCounted, c: float, a: int, g: int, k: int, mu: float, per: float) -> float:
	return 1.0 - p.DM.exp(-c * float((_lc(p, "death_multiplier") as Array)[g]) * income_factor(p, a, k) * mu / per)


static func _dband(a: int) -> int:
	return 0 if a < 65 else (1 if a < 75 else (2 if a < 85 else 3))


## A person of 15 outside the labour force becomes a student at its yearly turn (the status and the student's income only: no school
## body exists before H3), in both modes
static func enter_school(p: RefCounted, i: int) -> void:
	p.employment[i] = p.EMP_STUDENT
	p.repay(i)


## The probability that a person of 65 at work or looking for it retires at its yearly turn (T, as Phase 1); pure (§14.1)
static func h_retire(p: RefCounted) -> float:
	return p.rone_out("h_retire", 0.74)


## A person of 65 at work or looking for it retires with probability 0.74 (T, as Phase 1) at its yearly turn
static func retire(p: RefCounted, i: int, counts: Dictionary) -> void:
	if p.below("retire", i, p.month, 0, h_retire(p)):
		p.employment[i] = p.EMP_RETIRED
		p.repay(i)
		p.event(i, "retired", counts)


## T2.2b (M032 §2): the share of a kept side's grade moved to the side's prevalence split in a year, 1 − the within-side stay (T); pure
static func h_regrade(p: RefCounted) -> float:
	return p.rone_out("h_regrade", 1.0 - float((_lc(p, "grade_kernel") as Dictionary)["within_stay"]))


## T2.2b, T2.2c (M032 §2, M034's kernel5): class c's (0 stable, 1 mobile) one-year kernel between the five states at the prevalence
## pi0 (row-major 25): on the four grades (4a and 4b as grade 4) the side kept with the class's good or bad stay, inside a kept side the
## stay and h_regrade's share to the side's prevalence split, a changed side's prevalence split, grade 4's stay the ADL stay × b ÷ the
## one-chain bad stay, at most b, the rest of b to grade 3; the flow into grade 4 split 4a : 4b as π; 4b stays at 1 − e_b and leaves
## to 4a at e_b; pure
static func grade_kernel(p: RefCounted, c: int, pi0: PackedFloat64Array) -> PackedFloat64Array:
	var kp: Dictionary = _lc(p, "grade_kernel")
	var cl: Dictionary = kp["stable" if c == 0 else "mobile"]
	var a: float = float(cl["good_stay"])
	var b: float = float(cl["bad_stay"])
	var r: float = h_regrade(p)
	var p4 := PackedFloat64Array([pi0[0], pi0[1], pi0[2], pi0[3] + pi0[4]])
	var tot := PackedFloat64Array([p4[0] + p4[1], p4[2] + p4[3]])
	var k4 := PackedFloat64Array()
	k4.resize(16)
	for g: int in 4:
		var side_g: int = g / 2
		var p_good: float = a if side_g == 0 else 1.0 - b
		for side: int in 2:
			var p_side: float = p_good if side == 0 else 1.0 - p_good
			if tot[side] <= 0.0:
				continue
			for h: int in [side * 2, side * 2 + 1]:
				var share: float = p4[h] / tot[side]
				if side == side_g:
					share = (1.0 - r) * (1.0 if h == g else 0.0) + r * p4[h] / tot[side]
				k4[g * 4 + h] += p_side * share
	var bad_stay: float = k4[14] + k4[15]
	k4[15] = minf(float(kp["adl_stay"]) * b / float(kp["bad_stay_one_year"]), bad_stay)
	k4[14] = bad_stay - k4[15]
	var k := PackedFloat64Array()
	k.resize(NG * NG)
	for g2: int in 4:
		for h2: int in 3:
			k[g2 * NG + h2] = k4[g2 * 4 + h2]
		if p4[3] > 0.0:
			k[g2 * NG + 3] = k4[g2 * 4 + 3] * pi0[3] / p4[3]
			k[g2 * NG + 4] = k4[g2 * 4 + 3] * pi0[4] / p4[3]
	var eb: float = float(kp["care_exit"])
	k[4 * NG + 4] = 1.0 - eb
	k[4 * NG + 3] = eb
	return p.rone_out("grade_kernel", k)


## T2.2b (M031 §2 with M032's classes): the one-year flows at one age × sex × quartile, rows (class, state) at n (2 x the states,
## class-major), columns the states at π N, the IPF (to 1e-12 of N) of the seed n_{c,g} K_c(g, g′); [P_c(g → g′) row-major, the IPF
## residual ÷ N]
static func grade_flows(p: RefCounted, n: PackedFloat64Array, pi0: PackedFloat64Array) -> Array:
	var ng: int = pi0.size()
	var nr: int = 2 * ng
	var pt: float = 0.0
	for g0: int in ng:
		pt += pi0[g0]
	var nt: float = 0.0
	for x: int in nr:
		nt += n[x]
	var f := PackedFloat64Array()
	f.resize(nr * ng)
	for c: int in 2:
		var k: PackedFloat64Array = grade_kernel(p, c, pi0)
		for g: int in ng:
			for h: int in ng:
				f[(c * ng + g) * ng + h] = n[c * ng + g] * k[g * ng + h]
	var res: float = 0.0
	for it: int in 1000:
		for h2: int in ng:
			var col: float = 0.0
			for rw: int in nr:
				col += f[rw * ng + h2]
			if col > 0.0:
				var sc: float = pi0[h2] / pt * nt / col
				for rw2: int in nr:
					f[rw2 * ng + h2] *= sc
		for rw3: int in nr:
			var row: float = 0.0
			for h6: int in ng:
				row += f[rw3 * ng + h6]
			if row > 0.0:
				var sr: float = n[rw3] / row
				for h3: int in ng:
					f[rw3 * ng + h3] *= sr
		res = 0.0
		for h4: int in ng:
			var col2: float = 0.0
			for rw4: int in nr:
				col2 += f[rw4 * ng + h4]
			res = maxf(res, absf(col2 - pi0[h4] / pt * nt))
		if res <= 1e-12 * nt:
			break
	var pm := PackedFloat64Array()
	pm.resize(nr * ng)
	for rw5: int in nr:
		for h5: int in ng:
			pm[rw5 * ng + h5] = f[rw5 * ng + h5] / n[rw5] if n[rw5] > 0.0 else (1.0 if h5 == rw5 % ng else 0.0)
	return [pm, res / nt if nt > 0.0 else 0.0]


## T2.2b in the persons layer with M035 (TO_E 13:29 (3), 13:47, 17:51): each month, the persons whose yearly turn it was and who did
## not die, per their new single age × sex × quartile, moved within their class to the prevalence by grade_flows on their weights,
## each person by one keyed uniform; T2s-gp's, T2s-4b's and T2s-gk's tallies to lc_t22b
## Why not each January: a person who turned a during the year would carry the mix of a − 1 against c(a), half a year on average (M035)
static func grade_birthday(p: RefCounted) -> void:
	var nn: Dictionary = {}
	var key_of := PackedInt32Array()
	key_of.resize(p.n)
	var dying: Dictionary = {}
	for d0: int in p.lc_dying:
		dying[d0] = true
	var turning := PackedInt32Array()
	for i0: int in p.n:
		if p.month % 12 == int(p.pid[i0] % 12) and not dying.has(i0):
			turning.append(i0)
	for i: int in turning:
		var key: int = (p.age[i] * 2 + p.sex[i]) * 4 + quartile(p, i)
		key_of[i] = key
		if not nn.has(key):
			var z := PackedFloat64Array()
			z.resize(2 * NG)
			nn[key] = z
		nn[key][p.health_class[i] * NG + p.health[i]] += p.weight[i]
	var tl: Dictionary = {"res": 0.0}
	for k0: String in ["before", "target", "after", "var", "stay", "stay_seed"]:
		var z2 := PackedFloat64Array()
		z2.resize(18 * NG)
		tl[k0] = z2
	var z3 := PackedFloat64Array()
	z3.resize(36 * NG)
	tl["stay_c"] = z3
	var z4 := PackedFloat64Array()
	z4.resize(36 * NG)
	tl["n_c"] = z4
	for k5: String in ["b4_target", "b4_after", "b4_var", "b4_n", "b4_exit"]:
		var z5 := PackedFloat64Array()
		z5.resize(14)
		tl[k5] = z5
	var pm: Dictionary = {}
	for key2: int in nn:
		var a: int = key2 / 8
		var s: int = (key2 / 4) % 2
		var pi0: PackedFloat64Array = shares(p, a, s)
		var pt: float = 0.0
		for g7: int in NG:
			pt += pi0[g7]
		var n8: PackedFloat64Array = nn[key2]
		var out: Array = grade_flows(p, n8, pi0)
		pm[key2] = out[0]
		tl["res"] = maxf(float(tl["res"]), float(out[1]))
		var row: int = (s * 9 + _b10(a)) * NG
		var nt: float = 0.0
		for x: int in 2 * NG:
			nt += n8[x]
		for g: int in NG:
			tl["target"][row + g] += pi0[g] / pt * nt
		if a >= 65:
			tl["b4_target"][s * 7 + mini((a - 65) / 5, 6)] += pi0[4] / pt * nt
		for c: int in 2:
			var k: PackedFloat64Array = grade_kernel(p, c, pi0)
			for g2: int in NG:
				tl["before"][row + g2] += n8[c * NG + g2]
				tl["stay_seed"][row + g2] += n8[c * NG + g2] * k[g2 * NG + g2]
	for i2: int in turning:
		var pr: PackedFloat64Array = pm[key_of[i2]]
		var rw: int = p.health_class[i2] * NG + p.health[i2]
		var x2: float = p.u("t22b_grade", i2, p.month)
		var acc: float = 0.0
		var g3: int = NG - 1
		for h: int in NG:
			acc += pr[rw * NG + h]
			if x2 < acc:
				g3 = h
				break
		var row2: int = (p.sex[i2] * 9 + _b10(p.age[i2])) * NG
		for h2: int in NG:
			var q: float = pr[rw * NG + h2]
			tl["var"][row2 + h2] += p.weight[i2] * p.weight[i2] * q * (1.0 - q)
		tl["after"][row2 + g3] += p.weight[i2]
		if p.age[i2] >= 65:
			var r5: int = p.sex[i2] * 7 + mini((p.age[i2] - 65) / 5, 6)
			var q4: float = pr[rw * NG + 4]
			tl["b4_var"][r5] += p.weight[i2] * p.weight[i2] * q4 * (1.0 - q4)
			tl["b4_after"][r5] += p.weight[i2] if g3 == 4 else 0.0
			if p.health[i2] == 4:
				tl["b4_n"][r5] += p.weight[i2]
				tl["b4_exit"][r5] += p.weight[i2] if g3 == 3 else 0.0
		var rc: int = p.health_class[i2] * 18 * NG + row2 + p.health[i2]
		tl["n_c"][rc] += p.weight[i2]
		if g3 == p.health[i2]:
			tl["stay"][row2 + g3] += p.weight[i2]
			tl["stay_c"][rc] += p.weight[i2]
		p.health[i2] = g3
	p.lc_t22b = tl


## T2.2b (M032 §2): a person's health class from its grade's side at the start, P(stable | side), or at birth the stable share (T)
static func draw_class(p: RefCounted, i: int, at_birth: bool) -> void:
	var kp: Dictionary = _lc(p, "grade_kernel")
	var ps: float = float(kp["stable_share"]) if at_birth else float(kp["p_stable_given_side"]["good" if p.health[i] < 2 else "bad"])
	p.health_class[i] = 0 if p.u("grade_class0", i) < ps else 1


static func _log(p: RefCounted, i: int, kind: String, j: int, detail: Variant) -> void:
	p.life_log.append([p.month, p.pid[i], kind, p.pid[j] if j >= 0 else -1, detail, p.weight[i], p.sex[i]])


static func _hh_remove(p: RefCounted, i: int) -> void:
	var h: int = p.hh_id[i]
	var ms: PackedInt32Array = p.hh_members[h]
	var k: int = ms.find(i)
	if k >= 0:
		ms.remove_at(k)
	p.hh_members[h] = ms
	if p.hh_role[i] == p.R_HEAD and not ms.is_empty():
		var nh: int = -1
		for j: int in ms:
			if p.hh_role[j] == p.R_PARTNER:
				nh = j
		if nh < 0:
			nh = ms[0]
			for j2: int in ms:
				if p.age[j2] > p.age[nh]:
					nh = j2
		p.hh_role[nh] = p.R_HEAD
	_classify(p, h)


static func _hh_add(p: RefCounted, i: int, h: int, role: int) -> void:
	var ms: PackedInt32Array = p.hh_members[h]
	ms.append(i)
	p.hh_members[h] = ms
	p.hh_id[i] = h
	p.hh_role[i] = role
	p.set_pref(i, p.hh_pref[h])


static func _new_household(p: RefCounted, pref: int, w: float, kind: int = 0) -> int:
	p.hh_type.append(kind)
	p.hh_pref.append(pref)
	p.HH.add_household_weight(p, w)
	p.hh_members.append(PackedInt32Array())
	p.hh_n += 1
	return p.hh_n - 1


## A household's type from its members' roles (§10.2); an institution record stays one
static func _classify(p: RefCounted, h: int) -> void:
	if p.hh_type[h] == INSTITUTION:
		return
	var ms: PackedInt32Array = p.hh_members[h]
	if ms.size() <= 1:
		p.hh_type[h] = p.HK_SINGLE
		return
	var cnt := PackedInt32Array([0, 0, 0, 0, 0])
	for i: int in ms:
		cnt[p.hh_role[i]] += 1
	if cnt[p.R_PARENT] + cnt[p.R_OTHER] > 0:
		p.hh_type[h] = p.HK_OTHER
	elif cnt[p.R_CHILD] == 0:
		p.hh_type[h] = p.HK_COUPLE if cnt[p.R_PARTNER] == 1 else p.HK_OTHER
	else:
		p.hh_type[h] = p.HK_COUPLE_CHILDREN if cnt[p.R_PARTNER] == 1 else p.HK_SINGLE_PARENT


static func _move_out(p: RefCounted, i: int, h_new: int, role: int) -> void:
	_hh_remove(p, i)
	_hh_add(p, i, h_new, role)


static func _children_of(p: RefCounted, i: int) -> Array:
	var out: Array = []
	if p.hh_role[i] > p.R_PARTNER:
		return out
	for j: int in (p.hh_members[p.hh_id[i]] as PackedInt32Array):
		if p.hh_role[j] == p.R_CHILD:
			out.append(j)
	return out


static func _window(w: Dictionary, a: int) -> float:
	var v: float = 0.0
	for k: String in w:
		if a >= int(k):
			v = float(w[k])
	return v


## Removes the dying (collected by people._year): the partner widowed, contacts and memberships cleared, the household re-read
static func _deaths(p: RefCounted, counts: Dictionary) -> PackedByteArray:
	var dead := PackedByteArray()
	dead.resize(p.n)
	for i: int in p.lc_dying:
		if dead[i] == 1:
			continue
		dead[i] = 1
		p.lc_deaths[_dband(p.age[i]) * 2 + p.sex[i]] += 1
		p.count_kind(counts, "death", i, 0.0, "the life table's qx x the grade multiplier (S/T)")
		_log(p, i, "death", p.partner[i], {"age": p.age[i], "grade": p.health[i] + 1})
		var pt: int = p.partner[i]
		if pt >= 0:
			p.partner[pt] = -1
			_draw_intention(p, pt, p.month + 1)
			_log(p, pt, "widowed", i, {"age": p.age[pt]})
		p.partner[i] = -1
		p.REL.drop_all(p, i)
		for m: int in p.GRP.M:
			if p.member_of[i * p.GRP.M + m] >= 0:
				p.GRP.leave(p, i, p.member_of[i * p.GRP.M + m])
		_hh_remove(p, i)
	p.lc_dying = PackedInt32Array()
	return dead


## The month of the life course, after the persons' month (people.step C) and before the rake
static func month(p: RefCounted, counts: Dictionary) -> void:
	var dead: PackedByteArray = _deaths(p, counts)
	var n0: int = p.n
	var acted := PackedByteArray()
	acted.resize(n0)
	for i0: int in n0:
		acted[i0] = dead[i0]
	var fam: int = p.D_FAMILY
	var aut: int = p.D_AUTONOMY
	var dws := 0.0
	var dwa := 0.0
	var na := 0.0
	for i: int in n0:
		if dead[i] == 1 or p.age[i] < 18:
			continue
		dws += p.dw[i * p.ND + fam]
		dwa += p.dw[i * p.ND + aut]
		na += 1.0
	var fam_mean: float = dws / maxf(1.0, na)
	var aut_mean: float = dwa / maxf(1.0, na)
	var pa: Dictionary = _lc(p, "partnering")
	var births: Array = []
	var bi: Dictionary = _lc(p, "birth")
	var lh: Dictionary = _lc(p, "leaving_home")
	var dv: Dictionary = _lc(p, "divorce_choice")
	var mi: Dictionary = _lc(p, "moving_in")
	var ins: Dictionary = _lc(p, "institution")
	for i: int in n0:
		if acted[i] == 1:
			continue
		var a: int = p.age[i]
		var h: int = p.hh_id[i]
		if p.hh_type[h] == INSTITUTION:
			continue
		var size: int = (p.hh_members[h] as PackedInt32Array).size()
		var hi: float = h_institution(ins, p, i, a, size)
		if hi > 0.0 and p.below("lc_inst", i, p.month, 0, hi):
			e_institution(p, i, h, counts)
			acted[i] = 1
			continue
		var hm: float = h_move_in(mi, p, i, a, size)
		if hm > 0.0 and p.below("lc_movein", i, p.month, 0, hm):
			var to: int = _move_in_to(mi, p, i, a)
			if to >= 0:
				e_move_in(p, i, to, counts)
				acted[i] = 1
				continue
		var pt: int = p.partner[i]
		# divorce and a birth: decided once per couple, on the wife
		if pt >= 0 and p.sex[i] == p.FEMALE and p.hh_id[pt] == h and acted[pt] == 0:
			if p.below("lc_divorce", i, p.month, 0, h_divorce(dv, p, i, pt, h)):
				e_divorce(p, i, pt, h, counts)
				acted[i] = 1
				acted[pt] = 1
				continue
			var hb: float = h_birth(bi, p, i, pt, a)
			if hb > 0.0 and p.below("lc_birth", i, p.month, 0, hb):
				births.append(i)
				acted[i] = 1
				continue
		var hl: float = h_leave(lh, p, i, a, pt, aut_mean)
		if hl > 0.0 and p.below("lc_leave", i, p.month, 0, hl):
			e_leave(p, i, h, counts)
			acted[i] = 1
			continue
		# partnering (§10.6 A1): one who intends to marry looks; the two decide independently; the pair's income must carry a household
		var hp: float = h_look(pa, p, i, a, pt)
		if hp > 0.0 and p.below("lc_partner", i, p.month, 0, hp):
			var pool: Array = _met(p, i, dead)
			# one encounter with one person (§10.7 B1). Why not several tries: a person who met surveyed up to 20 of its two-step
			# contacts a month, and that survey made the couples (V100 §2)
			var found: int = -1
			if not pool.is_empty():
				var j2: int = pool[p.KEYED.below(pool.size(), p.seed_v, "lc_partnerpick", int(p.pid[i] & 0x7FFFFFFFFFFF), p.month * 32, 0)]
				if acted[j2] == 0 and _can_pair(pa, p, i, j2, a, h):
					var c: float = _compat(p, i, j2, float(pa["trait_compat"]))
					if p.below("lc_accept", i, p.month * 32, 0, h_accept(p, i, c, fam_mean, 1.0)) and p.below("lc_agree", j2, p.month * 32, 0, h_accept(p, j2, c, fam_mean, _window(pa["window"], p.age[j2]))):
						found = j2
			if found >= 0 and not p.below("lc_econ", i, p.month, 0, h_carry(p, i, found)):
				found = -1
			if found >= 0:
				_partner(p, i, found)
				acted[i] = 1
				acted[found] = 1
				p.count_kind(counts, "partnered", i, 0.0, "two independent decisions (drive, security, traits), both intending to marry, the pair's income (P/T)")
	for m2: int in births:
		_birth(p, m2, counts)
	p.remove_persons(dead)
	for h2: int in p.hh_n:
		_classify(p, h2)
	for i3: int in p.n:
		var h3: int = p.hh_id[i3]
		p.hh_kind[i3] = p.HK_SINGLE if p.hh_type[h3] == INSTITUTION else p.hh_type[h3]
		p.hh_size[i3] = float((p.hh_members[h3] as PackedInt32Array).size())

## The month's rates of the life course's rules for person i (§14.1, T2.R): each 0 where its rule does not apply, read on the state at
## the call; pure. A person draws its keyed u against them, a point (T2) its binomial
static func h_institution(ins: Dictionary, p: RefCounted, i: int, a: int, size: int) -> float:
	if a < int(ins["from_age"]) or p.health[i] < p.GRADE_LIMITED:
		return p.rone_out("h_institution", 0.0)
	return p.rone_out("h_institution", float(ins["kappa"]) * (float(ins["alone"]) if size == 1 else float(ins["with_others"])))


static func h_move_in(mi: Dictionary, p: RefCounted, i: int, a: int, size: int) -> float:
	if a < 65 or size != 1 or p.health[i] < p.GRADE_POOR:
		return p.rone_out("h_move_in", 0.0)
	return p.rone_out("h_move_in", float(mi["kappa"]) * (float(mi["grade4"]) if p.health[i] >= p.GRADE_LIMITED else 1.0))


static func h_divorce(dv: Dictionary, p: RefCounted, i: int, pt: int, h: int) -> float:
	var dmax: float = maxf(p.emotion(i, "discontent"), p.emotion(pt, "discontent"))
	var pd: float = float(dv["kappa"]) * dmax * dmax
	# the early mismatch (§10.6 A3): revealed in the first years together, fading as the marriage lasts
	pd *= 1.0 + float(dv["early_m0"]) * p.DM.exp(-float(p.month - p.union_month[i]) / 12.0 / float(dv["early_tau_years"]))
	if 0.5 * (p.dd[i * p.ND + p.D_SECURITY] + p.dd[pt * p.ND + p.D_SECURITY]) > float(dv["money_line"]):
		pd *= float(dv["money"])
	for y: int in (p.hh_members[h] as PackedInt32Array):
		if p.age[y] < int(dv["young_child_age"]):
			pd *= float(dv["young_child"])
			break
	return p.rone_out("h_divorce", pd)


## A birth needs her intended number not yet met (§10.6 A2). Why not the want weights by parity: they were T, and the persons' own
## intentions are R66's start values
static func h_birth(bi: Dictionary, p: RefCounted, i: int, pt: int, a: int) -> float:
	if a < 15 or a > 49 or p.month - p.last_birth[i] < int(bi["gap_months"]) or p.births_n[i] >= p.intended_kids[i]:
		return p.rone_out("h_birth", 0.0)
	var pw: float = float(bi["kappa"]) * _window(bi["fecundity"], a)
	pw *= 1.0 - 0.25 * (p.dd[i * p.ND + p.D_SECURITY] + p.dd[pt * p.ND + p.D_SECURITY])
	return p.rone_out("h_birth", pw)


static func h_leave(lh: Dictionary, p: RefCounted, i: int, a: int, pt: int, aut_mean: float) -> float:
	if p.hh_role[i] != p.R_CHILD or a < 18 or pt >= 0:
		return p.rone_out("h_leave", 0.0)
	var pl: float = float(lh["kappa"]) * p.dw[i * p.ND + p.D_AUTONOMY] / maxf(1e-9, aut_mean)
	pl *= float(lh["earner"]) if p.income[i] >= float(lh["earner_man_yen"]) else float(lh["not_earner"])
	if a == 18 and p.employment[i] == p.EMP_STUDENT and p.month % 12 == int(p.pid[i] % 12):
		pl *= float(lh["student_at_18"])
	return p.rone_out("h_leave", pl)


static func h_look(pa: Dictionary, p: RefCounted, i: int, a: int, pt: int) -> float:
	if pt >= 0 or a < 18 or a >= 75 or p.intends_marry[i] != 1:
		return p.rone_out("h_look", 0.0)
	return p.rone_out("h_look", float(pa["kappa"]) * _window(pa["window"], a))


## x's acceptance of a partner of compatibility c; w is x's own age window, 1 for the one who looked (its window is in h_look)
static func h_accept(p: RefCounted, x: int, c: float, fam_mean: float, w: float) -> float:
	return p.rone_out("h_accept", minf(1.0, p.dw[x * p.ND + p.D_FAMILY] / maxf(1e-9, fam_mean) * (1.0 - 0.5 * p.dd[x * p.ND + p.D_SECURITY]) * w * c))


static func h_carry(p: RefCounted, i: int, j: int) -> float:
	return p.rone_out("h_carry", minf(1.0, (p.income[i] + p.income[j]) / float((p.spec["consumption_man_yen_month"] as Dictionary)["two_plus"])))


static func _can_pair(pa: Dictionary, p: RefCounted, i: int, j: int, a: int, h: int) -> bool:
	var gap: int = (a - p.age[j]) if p.sex[i] == p.MALE else (p.age[j] - a)
	return not (p.partner[j] >= 0 or p.hh_id[j] == h or gap < int(pa["gap"][0]) or gap > int(pa["gap"][1]) or p.age[j] < 18 or p.age[j] >= 75 or p.intends_marry[j] != 1)


static func _move_in_to(mi: Dictionary, p: RefCounted, i: int, a: int) -> int:
	for c: int in p.REL.C:
		var j: int = p.contact_idx[i * p.REL.C + c]
		if j >= 0 and p.contact_kind[i * p.REL.C + c] == p.REL.K_FAMILY:
			var gap: int = a - p.age[j]
			var hj: int = p.hh_id[j]
			if gap >= int(mi["gap"][0]) and gap <= int(mi["gap"][1]) and p.hh_role[j] <= p.R_PARTNER and p.pref[j] == p.pref[i] and p.hh_type[hj] != INSTITUTION and (p.hh_members[hj] as PackedInt32Array).size() >= 2:
				return j
	return -1


## The rules' effects on the persons layer, each event's one writer (§14.1, T2.R)
static func e_institution(p: RefCounted, i: int, h: int, counts: Dictionary) -> void:
	var pt0: int = p.partner[i]
	if pt0 >= 0:
		p.partner[pt0] = -1
		_draw_intention(p, pt0, p.month + 1)
		p.partner[i] = -1
	_move_out(p, i, _new_household(p, p.pref[i], p.hh_weight[h], INSTITUTION), 0)
	_log(p, i, "institution", pt0, {"age": p.age[i]})
	p.count_kind(counts, "institution", i, 0.0, "grade 4 at 75+ (T)")


static func e_move_in(p: RefCounted, i: int, to: int, counts: Dictionary) -> void:
	_move_out(p, i, p.hh_id[to], p.R_PARENT)
	_classify(p, p.hh_id[to])
	_log(p, i, "moved_in", to, {"age": p.age[i]})
	p.count_kind(counts, "moved_in", i, 0.0, "65+ at grade 3-4 with a child's household (T)")


## The probability that the children stay with the mother at a divorce; pure (§14.1)
static func h_custody(p: RefCounted) -> float:
	return p.rone_out("h_custody", float(_lc(p, "divorce_children_with_mother")))


static func e_divorce(p: RefCounted, i: int, pt: int, h: int, counts: Dictionary) -> void:
	var kids: Array = _children_of(p, i)
	var with_mother: bool = p.below("lc_custody", i, p.month, 0, h_custody(p))
	var leaver: int = pt if with_mother else i
	p.partner[i] = -1
	p.partner[pt] = -1
	_draw_intention(p, i, p.month + 1)
	_draw_intention(p, pt, p.month + 1)
	_move_out(p, leaver, _new_household(p, p.pref[leaver], p.hh_weight[h]), 0)
	_classify(p, h)
	_log(p, i, "divorce", pt, {"years": float(p.month - p.union_month[i]) / 12.0, "children": kids.size(), "with_mother": with_mother, "wife_age": p.age[i]})
	p.count_kind(counts, "divorce", i, 0.0, "the partners' discontent, money and a young child (T)")


static func e_leave(p: RefCounted, i: int, h: int, counts: Dictionary) -> void:
	_move_out(p, i, _new_household(p, p.pref[i], p.hh_weight[h]), 0)
	p.ever_left[i] = 1
	_log(p, i, "left_home", -1, {"age": p.age[i]})
	p.count_kind(counts, "left_home", i, 0.0, "the autonomy drive x earning (T)")


## A move (people.move_to): a head or partner takes its household (every member's prefecture and the household's); a child or other
## member leaves into a new one-person household in the destination, with its partner when the two live in one household (a married
## child of a three-generation household; their children stay); an institution resident stays. Returns the persons who moved
static func move_household(p: RefCounted, i: int, dest: int, reason: String = "") -> Array:
	var h: int = p.hh_id[i]
	if p.hh_type[h] == INSTITUTION:
		return []
	if p.hh_role[i] <= p.R_PARTNER:
		var ms: Array = Array(p.hh_members[h] as PackedInt32Array)
		p.hh_pref[h] = dest
		for j: int in ms:
			p.set_pref(j, dest)
		_log(p, i, "moved", -1, {"to": dest, "members": ms.size(), "reason": reason})
		return ms
	var pt: int = p.partner[i]
	var hn: int = _new_household(p, dest, p.hh_weight[h])
	if pt >= 0 and p.hh_id[pt] == h:
		var man: int = i if p.sex[i] == p.MALE else pt
		_move_out(p, man, hn, p.R_HEAD)
		_move_out(p, pt if man == i else i, hn, p.R_PARTNER)
		_classify(p, hn)
		_log(p, i, "moved", pt, {"to": dest, "members": 2, "reason": reason})
		return [i, pt]
	_move_out(p, i, hn, p.R_HEAD)
	p.ever_left[i] = 1
	_log(p, i, "moved", -1, {"to": dest, "members": 1, "reason": reason})
	return [i]


## The singles one meets (A3-2, the design's §2.2 "who meet"): the person's contacts and their contacts, of the other sex, single, alive,
## not in an institution, in contact order. Why not the prefecture's singles: any two of a prefecture could pair (22 per 1,000 a year)
## The trait compatibility (§10.6 A1, T): 1 - k x the mean absolute difference of the two persons' traits
static func _compat(p: RefCounted, i: int, j: int, k: float) -> float:
	var d: float = 0.0
	for t: int in p.NT:
		d += absf(p.traits[i * p.NT + t] - p.traits[j * p.NT + t])
	return 1.0 - k * d / float(p.NT)


static func _met(p: RefCounted, i: int, dead: PackedByteArray) -> Array:
	var out: Array = []
	var seen := {i: true}
	var front: Array = []
	for c: int in p.REL.C:
		var j: int = p.contact_idx[i * p.REL.C + c]
		if j >= 0 and not seen.has(j):
			seen[j] = true
			front.append(j)
	var second: Array = []
	for j2: int in front:
		for c2: int in p.REL.C:
			var k: int = p.contact_idx[j2 * p.REL.C + c2]
			if k >= 0 and not seen.has(k):
				seen[k] = true
				second.append(k)
	for x: int in front + second:
		if (x >= dead.size() or dead[x] == 0) and p.sex[x] != p.sex[i] and p.partner[x] < 0 and p.hh_type[p.hh_id[x]] != INSTITUTION:
			out.append(x)
	return out


## Two singles form a new couple household; a single-parent head brings its children
static func _partner(p: RefCounted, i: int, j: int) -> void:
	var man: int = i if p.sex[i] == p.MALE else j
	var woman: int = j if man == i else i
	var hn: int = _new_household(p, p.pref[man], 0.5 * (p.hh_weight[p.hh_id[man]] + p.hh_weight[p.hh_id[woman]]))
	var kids: Array = []
	for x: int in [man, woman]:
		if p.hh_role[x] == p.R_HEAD and p.hh_type[p.hh_id[x]] == p.HK_SINGLE_PARENT:
			kids.append_array(_children_of(p, x))
	_move_out(p, man, hn, p.R_HEAD)
	_move_out(p, woman, hn, p.R_PARTNER)
	for k: int in kids:
		_move_out(p, k, hn, p.R_CHILD)
	_classify(p, hn)
	p.partner[man] = woman
	p.partner[woman] = man
	for x2: int in [man, woman]:
		_log(p, x2, "partnered", man if x2 == woman else woman, {"age": p.age[x2], "first": p.ever_married[x2] == 0})
		p.ever_married[x2] = 1
		p.ever_left[x2] = 1
		p.union_month[x2] = p.month
	if not p.REL.has_contact(p, man, woman) and p.REL.add(p, man, woman, p.REL.K_FAMILY):
		if not p.REL.add(p, woman, man, p.REL.K_FAMILY):
			p.REL.unlink(p, man, woman)


## A newborn appended to its mother's household: a new index and pid, drawn as a person of age 0, its household as family
static func _birth(p: RefCounted, mother: int, counts: Dictionary) -> void:
	var h: int = p.hh_id[mother]
	var code: int = p.pref[mother]
	var k: int = int(p.next_k.get(code, 0))
	p.next_k[code] = k + 1
	var j: int = p.new_person(code, k)
	p.partner[j] = -1
	p.intends_marry[j] = -1
	p.intended_kids[j] = -1
	p.last_birth[j] = -999
	p.union_month[j] = 0
	_hh_add(p, j, h, p.R_CHILD)
	p.HH.set_member_weight(p, j)
	p.hh_kind[j] = p.hh_type[h]
	p.hh_size[j] = float((p.hh_members[h] as PackedInt32Array).size())
	p.draw_person(j)
	p.health[j] = draw_grade(p, j, "grade0")
	draw_class(p, j, true)
	p.finish_person(j)
	for x: int in (p.hh_members[h] as PackedInt32Array):
		if x != j and p.contact_count(x) < p.REL.C and p.REL.add(p, j, x, p.REL.K_FAMILY):
			if not p.REL.add(p, x, j, p.REL.K_FAMILY):
				p.REL.unlink(p, j, x)
	p.births_n[mother] += 1
	p.last_birth[mother] = p.month
	p.lc_births.append([p.month, p.age[mother], p.weight[mother]])
	_classify(p, h)
	_log(p, j, "birth", mother, {"mother_age": p.age[mother], "order": p.births_n[mother]})
	p.count_kind(counts, "birth", mother, 0.0, "a couple's family drive x fecundity x budget (T)")
