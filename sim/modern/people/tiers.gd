extends RefCounted
## The tiered full-coverage population, T1: the units and their counts at the start (ISS_TIERED_POPULATION.md §12; declared before this
## code). Behind people.tiers (default off: nothing allocated, no key in the save or the digest). Every real person is in exactly one
## unit: a bundle (a cell of the key with an integer count and K sample persons) or an individual (a person of the persons layer, the
## top 0.01% by income: the owner's about 3,000). The counts sum to the population by construction; the start is one fit of integer
## counts to the published marginals (an IPF at month 0 only, §11.6), each marginal's residual reported. No month step (T2).
const SPEC := "res://data/modern/people/%s_tiers_2024.json"
const BANDS := 18          # five-year bands, 85+ open
const NTYPE := 6           # people.HOUSEHOLD's five + the institution
const NEMP := 6            # people.EMPLOYMENT
const NCLASS := 7          # the spec's classes: four top tiers, middle 40, bottom 50, none (under 18)
const CLASS_NONE := 6
const EMP_KEY_UNTIL_BAND := 14 # persons 70+ (and under 20) keyed without employment, carried in the mix (§12.7)
const CLASS_REST := 4         # the key's class of the merged middle 40% and bottom 50% at E (their mix keeps 4 and 5)
const ADULT_FROM := 20      # R67a's adults (DINA: 20 and over), a band edge
const KEY_STRIDE := 6      # pref code, band, sex, class, type, employment
const PHI_ZMIN := -37.0     # the Φ table's lower end (Φ ~ 6e-300)
const PHI_STEP := 1.0 / 128.0
const TAIL_GRID := 512       # the generator's survival read on this many log-spaced incomes from its median to 1e5 万円 a month
const DM = preload("res://sim/api/det_math.gd")
const SIZE_MIN := [0, 1, 2, 1, 1, 0]   # per type the smallest and largest size class (0 = 1 person .. 4 = 5+): one-person 1, couple
const SIZE_MAX := [0, 1, 4, 4, 4, 0]   # only 2, couple + children 3+, single parent 2+, other 2+, institution 1
const NH_CHILD := 10        # §12.12 (9): the non-head couples' kinds in _r77_couples' cells, child then parent
const NH_PARENT := 11
const AGE_SLOTS := 16      # single ages per unit: a band's five, the 85+ band's 85..100 (the cohort's open end)
## The per-person arrays a sample point carries (every registry array but the links and the groups, which are T4's)
const PEN_NONE := 0          # the 65+'s public pension kinds (§12.9 M1)
const PEN_BASIC := 1
const PEN_BASIC_SHORT := 2
const PEN_EMPLOYEE := 3
const PEN_EMPLOYEE_SHORT := 4
const LC = preload("res://sim/modern/people/life_course.gd")
const BINOM_SWITCH := 12.0   # n p q (and the hypergeometric's variance) below which the draws are the exact inversion (§13.2, §14.2)
const NG := 5                # M030, T2.2c: the health states held as cells inside each point: grades 1, 2, 3, 4a and 4b (care need)
const NK := 2                # T2.2b (M032): the health classes, 0 stable, 1 mobile, a cell index beside the grade
const NS := NG * NK          # the cells of a (point, age): grade x NK + class
const KEYED = preload("res://sim/earth_core/keyed.gd")
const POINT_PID := 10000000   # the points' person ids (the individuals' are 3,000,000 + i)
const POINT_SKIP := ["contact_idx", "contact_kind", "contact_last", "contact_trust", "met", "belief", "belief_known", "belief_source", "belief_month", "member_of", "union_cover", "cohort", "qx", "pid", "k_in_pref"]


static func load_spec(p: RefCounted) -> String:
	var d: Variant = p.CANON.load_json(SPEC % p.state.to_lower())
	if not (d is Dictionary):
		return "tiers: no spec for " + p.state
	p.tr_spec = d
	return ""


static func _v(p: RefCounted, k: String) -> Variant:
	return (p.tr_spec[k] as Dictionary)["value"]


static func band_of(a: int) -> int:
	return mini(a / 5, BANDS - 1)


## The start: the cell counts from the cohort, the prefectures and the conditional shares (§12.2), the fit, the integer rounding,
## the individuals, the sample points, the household-bundles and the instruments
static func build_start(p: RefCounted, prefectures: Dictionary) -> void:
	var K: int = p.tier_k if p.tier_k > 0 else int(_v(p, "k_points"))
	p.tr_k = K
	var cls: Dictionary = _v(p, "classes")
	var emp_bs: Array = _v(p, "employment_by_band_sex")
	var adult_shares: Array = cls["adult_shares"]
	var ctot: float = 0.0
	for a0: int in p.cohort.size():
		ctot += p.cohort[a0]
	# the band x sex shape of the cohort (S), applied to every prefecture (T: by prefecture NF)
	var band_share := PackedFloat64Array()
	band_share.resize(BANDS * 2)
	for a: int in p.AGES:
		for s: int in 2:
			band_share[band_of(a) * 2 + s] += p.cohort[a * p.SEXES + s] / ctot
	var age_in_band := PackedFloat64Array()   # the share of each single age within its band, for the single-year counts
	age_in_band.resize(p.AGES * 2)
	for a2: int in p.AGES:
		for s2: int in 2:
			var bs: float = band_share[band_of(a2) * 2 + s2]
			age_in_band[a2 * 2 + s2] = (p.cohort[a2 * p.SEXES + s2] / ctot) / bs if bs > 0.0 else 0.0
	# the seed on (prefecture, band x sex, type): pop x shape x P(type | band, sex) (T, stated); employment and class are factors
	# inside each cell
	var codes: Array = []
	for code: String in prefectures:
		codes.append(int(code))
	codes.sort()
	var nc: int = codes.size()
	var nbs: int = BANDS * 2
	var base: PackedFloat64Array = _base(p, codes, prefectures, band_share)
	var emp_c: Array = _employment(p, base, codes, emp_bs)
	# the couples first (§12.12): integer couples by (prefecture, husband band, wife band, type), their persons fixed cells; the seed
	# is the persons in no couple, P(type | band, sex) less the couples' share of the cell, floored at 0 and renormalised; the
	# couple-only type holds couples only, so its seed is 0
	var cp: Dictionary = _r77_couples(p, codes, base)
	var fixed: PackedInt64Array = cp["fixed"]
	p.tr_couples = cp["couples"]
	p.tr_nh_couples = cp["nonhead"]
	p.tr_margins["h4s"] = cp["h4s"]
	var five: Array = _completed_shares(p, _five_shares(p), base, nc)
	var sd: Array = _seed(nc, base, fixed, five)
	var y: PackedFloat64Array = sd[0]
	p.tr_residual = _fit(p, y, codes, prefectures, fixed, base, five)
	# §12.13 (c), TO_E 14:10: type 2's head couples at most the prefecture's type-2 persons in no couple (its children), the excess to
	# type 4 and the fit once more
	var moved: Dictionary = _type2_cap(p, codes, y, fixed)
	if not moved.is_empty():
		sd = _seed(nc, base, fixed, five)
		y = sd[0]
		p.tr_residual = _fit(p, y, codes, prefectures, fixed, base, five)
	var floor_moved: Dictionary = _size_floor(p, codes, y, fixed)
	var floor_excess: float = sd[1]
	var ten_shift: float = float(p.tr_margins.get("ten_shift", 0.0))
	var one_rake: Array = p.tr_margins.get("one_rake", [])
	var yi: PackedInt64Array = _round(p, y, codes, prefectures, base, fixed)
	p.tr_margins["ten_shift"] = ten_shift
	p.tr_margins["one_rake"] = one_rake
	p.tr_margins["t2_clip"] = cp["t2_clip"]
	p.tr_margins["c24_clip"] = cp["c24_clip"]
	p.tr_margins["h4s"] = cp["h4s"]
	p.tr_margins["floor_moved"] = floor_moved
	p.tr_margins["r77_floor_excess"] = floor_excess
	p.tr_margins["r77_couples"] = cp["total"]
	p.tr_margins["r77_rake"] = cp["rake"]
	p.tr_margins["n4"] = cp["n4"]
	p.tr_margins["n4_cap"] = moved
	p.tr_margins["nh_clip"] = cp["nh_clip"]
	# the class of an adult from the generator's own income law (§12.8 item 3): the national class lines solved over the adults'
	# laws weighted by their counts, then P(class | band, sex, employment) for the cell split
	var tab: PackedFloat64Array = _phi_table()
	var mass: Dictionary = {}
	for ci7: int in nc:
		for bs7: int in nbs:
			if bs7 / 2 * 5 < ADULT_FROM:
				continue
			var n7: float = 0.0
			for t7: int in NTYPE:
				n7 += float(yi[(ci7 * nbs + bs7) * NTYPE + t7])
			var er7: PackedFloat64Array = emp_c[ci7][bs7 % 2][bs7 / 2]
			var et7: float = 0.0
			for e7: int in NEMP:
				et7 += maxf(0.0, er7[e7])
			for e8: int in NEMP:
				if et7 > 0.0 and er7[e8] > 0.0:
					mass[bs7 * NEMP + e8] = float(mass.get(bs7 * NEMP + e8, 0.0)) + n7 * er7[e8] / et7
	var laws: Dictionary = {}
	for kl: int in mass:
		laws[kl] = _income_law(p, kl / NEMP / 2, (kl / NEMP) % 2, kl % NEMP, age_in_band)
	var lines: PackedFloat64Array = _class_lines(tab, laws, mass, adult_shares)
	var pk: Dictionary = {}
	for kl2: int in laws:
		pk[kl2] = _class_probs(tab, laws[kl2], lines)
	p.tr_margins["class_lines"] = lines
	var tm: Dictionary = _tail_map(p, tab, laws, mass, lines, adult_shares)
	# each integer (prefecture, band, sex, type) cell split over employment x class by keyed systematic rounding
	var cells: Dictionary = {}   # key string -> [pref, band, sex, class, type, emp, count]
	var top_real: float = 0.0
	var top_cand: Array = []
	for ci2: int in nc:
		for bs2: int in nbs:
			var b: int = bs2 / 2
			var s3: int = bs2 % 2
			var adult: bool = b * 5 + 4 >= ADULT_FROM
			for t3: int in NTYPE:
				var n0: int = yi[(ci2 * nbs + bs2) * NTYPE + t3]
				if n0 <= 0:
					continue
				var sub := PackedFloat64Array()
				var tags: Array = []
				var erow: PackedFloat64Array = emp_c[ci2][s3][b]
				var etot: float = 0.0
				for e: int in NEMP:
					etot += maxf(0.0, erow[e])
				for e2: int in NEMP:
					var pe: float = maxf(0.0, erow[e2]) / etot if etot > 0.0 else (1.0 if e2 == 0 else 0.0)
					if pe <= 0.0:
						continue
					if not adult:
						sub.append(float(n0) * pe)
						tags.append([CLASS_NONE, e2])
					else:
						for k: int in NCLASS - 1:
							sub.append(float(n0) * pe * float(pk.get(bs2 * NEMP + e2, PackedFloat64Array([0.0, 0.0, 0.0, 0.0, 0.0, 1.0]))[k]))
							tags.append([k, e2])
				var ints: PackedInt64Array = _systematic(sub, n0, p.seed_v, "tier_cell", (ci2 * nbs + bs2) * NTYPE + t3)
				for q: int in ints.size():
					if ints[q] > 0:
						_cell_add(cells, codes[ci2], b, s3, int(tags[q][0]), t3, int(tags[q][1]), float(ints[q]))
					if adult and int(tags[q][0]) == 0:
						top_real += sub[q]
						top_cand.append([sub[q], codes[ci2], b, s3, t3, int(tags[q][1])])
	_hold_top(p, cells, top_real, top_cand)
	# the units at E (§12.7): the top tiers keyed (pref, band, sex, class), the rest 90% one class, persons under 20 without employment;
	# each unit's mix holds the integer counts of the (class, type, employment) combinations its key merges
	var groups: Dictionary = {}
	for ks: String in cells:
		var cell: Array = cells[ks]
		var n: int = int(cell[6])
		if n <= 0:
			continue
		var k: int = int(cell[3])
		var t: int = int(cell[4])
		var e: int = int(cell[5])
		var gk: int = k
		var gt: int = t
		var ge: int = e
		if k < CLASS_REST:
			gt = -1
			ge = -1
		elif k < CLASS_NONE:
			gk = CLASS_REST
			if int(cell[1]) >= EMP_KEY_UNTIL_BAND:
				ge = -1
		else:
			ge = -1
		var gs: String = "%02d|%02d|%d|%d|%d|%d" % [int(cell[0]), int(cell[1]), int(cell[2]), gk, gt + 1, ge + 1]
		if not groups.has(gs):
			groups[gs] = [int(cell[0]), int(cell[1]), int(cell[2]), gk, gt, ge, {}]
		var mix: Dictionary = groups[gs][6]
		var code: int = (k * NTYPE + t) * NEMP + e
		mix[code] = int(mix.get(code, 0)) + n
	var keys: Array = groups.keys()
	keys.sort()
	p.tr_units = 0
	p.tr_key = PackedInt32Array()
	p.tr_count = PackedInt64Array()
	p.tr_age_counts = PackedInt64Array()
	p.tr_never_married = PackedFloat64Array()
	p.tr_married_apart = PackedFloat64Array()
	p.tr_tier_size = PackedInt32Array()
	p.tr_mix_off = PackedInt64Array()
	p.tr_mix_code = PackedInt32Array()
	p.tr_mix_n = PackedInt64Array()
	var unit_size: Array = cls["unit_size"]
	for gi: int in keys.size():
		var g: Array = groups[keys[gi]]
		var mixg: Dictionary = g[6]
		var mcodes: Array = mixg.keys()
		mcodes.sort()
		var n2: int = 0
		for mc: int in mcodes:
			n2 += int(mixg[mc])
		var us: int = int(unit_size[int(g[3])])
		var parts: int = 1 if us <= 0 else maxi(1, int(round(float(n2) / float(us))))
		# a top tier's merged cell splits into sub-bundles of the ladder's size: each combination dealt evenly over the parts, the
		# remainders laid round the parts from a keyed start, so the parts' totals differ by one at most
		var split: Array = []
		for q: int in parts:
			split.append({})
		var off: int = p.KEYED.below(parts, p.seed_v, "tier_part", gi, 0, 0)
		for mc2: int in mcodes:
			var nc2: int = int(mixg[mc2])
			var r: int = nc2 % parts
			for q2: int in parts:
				var add: int = nc2 / parts + (1 if (q2 - off + parts) % parts < r else 0)
				if add > 0:
					split[q2][mc2] = add
			off = (off + r) % parts
		for q3: int in parts:
			var sm: Dictionary = split[q3]
			var share: int = 0
			for mc3 in sm:
				share += int(sm[mc3])
			if share <= 0:
				continue
			for f: int in KEY_STRIDE:
				p.tr_key.append(int(g[f]))
			p.tr_count.append(share)
			p.tr_tier_size.append(us)
			p.tr_mix_off.append(p.tr_mix_code.size())
			var sk: Array = sm.keys()
			sk.sort()
			for mc4: int in sk:
				p.tr_mix_code.append(mc4)
				p.tr_mix_n.append(int(sm[mc4]))
			var b2: int = int(g[1])
			var s4: int = int(g[2])
			var av := PackedFloat64Array()
			av.resize(AGE_SLOTS)
			for a3: int in range(b2 * 5, p.AGES if b2 == BANDS - 1 else b2 * 5 + 5):
				av[a3 - b2 * 5] += float(share) * age_in_band[a3 * 2 + s4]
			# Why not the last age taking the rounding: it went to -1 in 390 of 239,480 slots (V104)
			# Why not the largest remainder: like units (same count, same shares) gave the +1 to the same ages, 1,148 persons at age 52
			# nationally and 47 of 101 ages beyond an unbiased rounding's bound (§12.10 V3)
			p.tr_age_counts.append_array(_systematic(av, share, p.seed_v, "tier_age_split", p.tr_units))
			p.tr_units += 1
	p.tr_mix_off.append(p.tr_mix_code.size())
	_individuals(p, lines, tab)
	_drop_empty(p)
	p.tr_residual.append(_class_residual(p, adult_shares))
	_points(p, lines, tab, tm)
	_transfers(p)
	_households(p)
	_never_married(p)
	_married_apart(p)
	_instruments(p)
	build_t21(p)


## The top 0.01% tier's national total held at the integer nearest its real total (§12.7): one person at a time between the tier's
## sub-cell and the bottom 50%'s sub-cell of the same cell and employment, in keyed order, each tier sub-cell kept at its floor or ceiling
static func _hold_top(p: RefCounted, cells: Dictionary, top_real: float, cand: Array) -> void:
	var want: int = int(floor(top_real + 0.5))
	var have: int = 0
	for c: Array in cand:
		have += int(cells.get("%02d|%02d|%d|%d|%d|%d" % [c[1], c[2], c[3], 0, c[4], c[5]], [0, 0, 0, 0, 0, 0, 0.0])[6])
	var order: Array = range(cand.size())
	order.sort_custom(func(i: int, j: int) -> bool: return p.KEYED.raw(p.seed_v, "tier_hold", i, 0, 0) < p.KEYED.raw(p.seed_v, "tier_hold", j, 0, 0))
	for i2: int in order:
		if have == want:
			break
		var c2: Array = cand[i2]
		var k0: String = "%02d|%02d|%d|%d|%d|%d" % [c2[1], c2[2], c2[3], 0, c2[4], c2[5]]
		var k5: String = "%02d|%02d|%d|%d|%d|%d" % [c2[1], c2[2], c2[3], 5, c2[4], c2[5]]
		var n0: int = int(cells.get(k0, [0, 0, 0, 0, 0, 0, 0.0])[6])
		var x: float = float(c2[0])
		if have > want and n0 > int(floor(x)):
			cells[k0][6] = float(n0 - 1)
			_cell_add(cells, int(c2[1]), int(c2[2]), int(c2[3]), 5, int(c2[4]), int(c2[5]), 1.0)
			have -= 1
		elif have < want and n0 < int(ceil(x)) and cells.has(k5) and int(cells[k5][6]) > 0:
			cells[k5][6] = float(int(cells[k5][6]) - 1)
			_cell_add(cells, int(c2[1]), int(c2[2]), int(c2[3]), 0, int(c2[4]), int(c2[5]), 1.0)
			have += 1
	p.tr_residual.append(float(have - want))


## The units the individuals' subtraction emptied are removed (§12.8 item 8): the registry's unit arrays compacted in order, a mix
## entry emptied the same way dropped, an individual whose unit is gone reading -1 (it keeps its own prefecture, age and sex)
## Why not keeping them at count 0: a unit with no person and no point is a registry row T2's flows would have to skip (V104 3)
static func _drop_empty(p: RefCounted) -> void:
	var remap := PackedInt32Array()
	remap.resize(p.tr_units)
	var key := PackedInt32Array()
	var count := PackedInt64Array()
	var ages := PackedInt64Array()
	var size := PackedInt32Array()
	var moff := PackedInt64Array()
	var mcode := PackedInt32Array()
	var mn := PackedInt64Array()
	var kept: int = 0
	for u: int in p.tr_units:
		if p.tr_count[u] <= 0:
			remap[u] = -1
			continue
		remap[u] = kept
		kept += 1
		for f: int in KEY_STRIDE:
			key.append(p.tr_key[u * KEY_STRIDE + f])
		count.append(p.tr_count[u])
		for y: int in AGE_SLOTS:
			ages.append(p.tr_age_counts[u * AGE_SLOTS + y])
		size.append(p.tr_tier_size[u])
		moff.append(mcode.size())
		for m: int in range(p.tr_mix_off[u], p.tr_mix_off[u + 1]):
			if p.tr_mix_n[m] > 0:
				mcode.append(p.tr_mix_code[m])
				mn.append(p.tr_mix_n[m])
	moff.append(mcode.size())
	p.tr_margins["dropped_units"] = p.tr_units - kept
	p.tr_units = kept
	p.tr_key = key
	p.tr_count = count
	p.tr_age_counts = ages
	p.tr_tier_size = size
	p.tr_mix_off = moff
	p.tr_mix_code = mcode
	p.tr_mix_n = mn
	for i: int in p.tr_indiv_unit.size():
		p.tr_indiv_unit[i] = remap[p.tr_indiv_unit[i]]


## The combination of unit u drawn by a keyed index below the unit's count (the mix's cumulative counts in code order)
static func mix_draw(p: RefCounted, u: int, x: int) -> int:
	var acc: int = 0
	for m: int in range(p.tr_mix_off[u], p.tr_mix_off[u + 1]):
		acc += p.tr_mix_n[m]
		if x < acc:
			return m
	return p.tr_mix_off[u + 1] - 1


## The class marginal after the rounding (T1s-h): the worst relative gap of a class's persons (bundles + individuals) against its
## share of the adults
static func _class_residual(p: RefCounted, adult_shares: Array) -> float:
	var by := PackedFloat64Array()
	by.resize(NCLASS)
	for m: int in p.tr_mix_code.size():
		by[p.tr_mix_code[m] / (NTYPE * NEMP)] += float(p.tr_mix_n[m])
	by[0] += float(p.n)
	var adults: float = 0.0
	for k: int in NCLASS - 1:
		adults += by[k]
	var worst: float = 0.0
	for k2: int in NCLASS - 1:
		var want: float = adults * float(adult_shares[k2])
		worst = maxf(worst, absf(by[k2] - want) / maxf(1.0, want))
	return worst


static func _cell_add(cells: Dictionary, c: int, b: int, s: int, k: int, t: int, e: int, x: float) -> void:
	var ks: String = "%02d|%02d|%d|%d|%d|%d" % [c, b, s, k, t, e]
	if cells.has(ks):
		cells[ks][6] += x
	else:
		cells[ks] = [c, b, s, k, t, e, x]


## The never-married share of each bundle (§12.13 step 6, M016 rank 2; §12.16 M021): per prefecture x band x sex the start's never
## married from _marital_cells (the cohort identity and its residual share), read by household role from the compositions: the members of
## a recorded child couple married; a child otherwise at 第49-2表's never-married share among the not-married living with a parent
## (sex x band, T); a couple's head and partner and a parent ever married, a single parent's head at 0.1 (T); the free persons (heads
## of one-person, other and institution households, and the role "other") take one share per prefecture x band x sex set so the cell
## is R76's, held in [0, 1]; under 15 every person is never married. The rows [code, band, sex, R76, free share, gap] go to
## tr_margins["nm"] for T1s-n
## Why not R62's national share by band x sex (before step 6): R76 is the same census by prefecture, and R62's 45+ row stood in for
## every older band (§12.10 V5)
## Why not R76's 2020 share (before §12.16): with R77c's couples 1.5 M fewer than 2020's shares imply, 3 M married persons had no
## couple and no married-apart source (M021)
static func _never_married(p: RefCounted) -> void:
	var cm: Dictionary = _v(p, "coresident_marital")
	var nu := PackedFloat64Array()   # the child role's never-married share by band x sex
	nu.resize(BANDS * 2)
	for bs: int in BANDS * 2:
		var b: int = bs / 2
		if b < 3:
			nu[bs] = 1.0
			continue
		var rows: Array = cm["men" if bs % 2 == 0 else "women"][mini(b - 3, 14)]
		var nv: float = float(rows[0][0]) + float(rows[0][1])
		var other: float = float(rows[2][0]) + float(rows[2][1]) + float(rows[3][0]) + float(rows[3][1])
		nu[bs] = nv / (nv + other) if nv + other > 0.0 else 1.0
	var married_child := PackedFloat64Array()
	married_child.resize(p.tr_units)
	for rk: String in p.tr_nh_hh:
		for rec: Array in p.tr_nh_hh[rk]:
			if int(rec[2]) == 0:
				married_child[int(rec[0])] += float(rec[3])
				married_child[int(rec[1])] += float(rec[3])
	var fixed := PackedFloat64Array()
	fixed.resize(p.tr_units)
	var free := PackedFloat64Array()
	free.resize(p.tr_units)
	for hk: String in p.tr_hh:
		var t: int = int(hk.split("|")[1])
		var mem: Dictionary = p.tr_hh[hk]["members"]
		for u in mem:
			var bs2: int = p.tr_key[int(u) * KEY_STRIDE + 1] * 2 + p.tr_key[int(u) * KEY_STRIDE + 2]
			for r in mem[u]:
				var x: float = float(mem[u][r])
				if int(r) == 2:
					var mc: float = minf(x, married_child[int(u)])
					married_child[int(u)] -= mc
					fixed[int(u)] += (x - mc) * nu[bs2]
					continue
				var f: float = _role_never_married(t, int(r))
				if f < 0.0:
					free[int(u)] += x
				else:
					fixed[int(u)] += x * f
	var cells: Dictionary = {}   # "code|band|sex" -> [persons, R76 never married, fixed, free]
	for u2: int in p.tr_units:
		var b2: int = p.tr_key[u2 * KEY_STRIDE + 1]
		if b2 < 3:
			continue
		var c: int = p.tr_key[u2 * KEY_STRIDE]
		var s: int = p.tr_key[u2 * KEY_STRIDE + 2]
		var ck: String = "%d|%d|%d" % [c, b2, s]
		if not cells.has(ck):
			cells[ck] = [0.0, 0.0, 0.0, 0.0]
		var e: Array = cells[ck]
		e[0] = float(e[0]) + float(p.tr_count[u2])
		e[2] = float(e[2]) + fixed[u2]
		e[3] = float(e[3]) + free[u2]
	var persons: Dictionary = {}
	for ck0: String in cells:
		persons[ck0] = float(cells[ck0][0])
	var m21: Dictionary = _marital_cells(p, persons)
	for ck1: String in cells:
		cells[ck1][1] = float(m21[ck1][3])
	var share: Dictionary = {}
	p.tr_margins["nm"] = []
	var keys: Array = cells.keys()
	keys.sort()
	for ck2: String in keys:
		var e2: Array = cells[ck2]
		var sh: float = clampf((float(e2[1]) - float(e2[2])) / float(e2[3]), 0.0, 1.0) if float(e2[3]) > 0.0 else 1.0
		share[ck2] = sh
		var kk: PackedStringArray = ck2.split("|")
		p.tr_margins["nm"].append([int(kk[0]), int(kk[1]), int(kk[2]), float(e2[1]) / float(e2[0]), sh, (float(e2[2]) + sh * float(e2[3]) - float(e2[1])) / float(e2[0])])
	p.tr_never_married = PackedFloat64Array()
	p.tr_never_married.resize(p.tr_units)
	for u3: int in p.tr_units:
		var b3: int = p.tr_key[u3 * KEY_STRIDE + 1]
		if b3 < 3 or p.tr_count[u3] <= 0:
			p.tr_never_married[u3] = 1.0
			continue
		var ck3: String = "%d|%d|%d" % [p.tr_key[u3 * KEY_STRIDE], b3, p.tr_key[u3 * KEY_STRIDE + 2]]
		p.tr_never_married[u3] = minf(1.0, (fixed[u3] + float(share.get(ck3, 1.0)) * free[u3]) / float(p.tr_count[u3]))


## Married but living apart (§12.12 (6); §12.16 M021): per prefecture x band (15+) x sex the couple persons held in the units
## (tr_couples: the husband's band for men, the wife's for women; less the cross-tier spouses, who are individuals) x 2020's married-apart
## ratio (marital_2024); each unit holds its cell's share of its persons. The reports go to tr_margins["ma"]
## Why not R76's 2020 married share less the couple persons (before §12.16): it held 2020's married share against R77c's fewer couples,
## and put the difference into married-apart (M021)
## Why not a share by class: no source splits married-apart by class
static func _married_apart(p: RefCounted) -> void:
	var mar: Dictionary = (_v(p, "marital_by_pref_sex_band") as Dictionary)["by_pref"]
	var pop20: Dictionary = (_v(p, "population_2020_by_pref_sex_band") as Dictionary)["by_pref"]
	var cba: Dictionary = (_v(p, "couples_by_age") as Dictionary)["by_pref"]
	var cells: Dictionary = {}   # "code|band|sex" -> [N, M, never married, the 85+ persons by 85-89, 90-94, 95-99, 100+]
	for u: int in p.tr_units:
		var b: int = p.tr_key[u * KEY_STRIDE + 1]
		if b * 5 < 15:
			continue
		var c: int = p.tr_key[u * KEY_STRIDE]
		var sx: int = p.tr_key[u * KEY_STRIDE + 2]
		var ck: String = "%d|%d|%d" % [c, b, sx]
		if not cells.has(ck):
			cells[ck] = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
		var row: Array = mar[str(c)][sx]
		var e: Array = cells[ck]
		e[0] = float(e[0]) + float(p.tr_count[u])
		e[2] = float(e[2]) + p.tr_never_married[u] * float(p.tr_count[u])
		for y: int in AGE_SLOTS:
			var n: int = p.tr_age_counts[u * AGE_SLOTS + y]
			if n == 0:
				continue
			var mb: int = mini((b * 5 + y - 15) / 5, row.size() - 1)
			e[1] = float(e[1]) + float(n) * float(row[mb][1])
			if b == BANDS - 1:
				e[3 + mini(y / 5, 3)] = float(e[3 + mini(y / 5, 3)]) + float(n)
	var m21: Dictionary = p.tr_margins["m21"]
	var ma: Dictionary = {}
	var nat := PackedFloat64Array()
	nat.resize(BANDS * 2 * 4)   # [MA, M, MA 2020, M 2020] by band x sex
	var over1: int = 0
	var keys: Array = cells.keys()
	keys.sort()
	for ck2: String in keys:
		var e2: Array = cells[ck2]
		var kk: PackedStringArray = ck2.split("|")
		var b2: int = int(kk[1])
		var s2: int = int(kk[2])
		var x: float = float(m21[ck2][1]) - float(m21[ck2][2]) if m21.has(ck2) else 0.0
		e2[1] = float(m21[ck2][1]) if m21.has(ck2) else 0.0
		ma[ck2] = x
		if b2 * 5 >= ADULT_FROM and float(e2[1]) + float(e2[2]) > float(e2[0]) + 1e-6:
			over1 += 1
		var row2: Array = mar[kk[0]][s2]
		var n20: float = float(pop20[kk[0]][s2][b2 - 3])
		var m20: float = n20 * float(row2[b2 - 3][1])
		if b2 == BANDS - 1:
			var wt: float = float(e2[3]) + float(e2[4]) + float(e2[5]) + float(e2[6])
			m20 = 0.0
			for j: int in 4:
				m20 += n20 * (float(e2[3 + j]) / wt if wt > 0.0 else 0.25) * float(row2[mini(b2 - 3 + j, row2.size() - 1)][1])
		var c20: float = 0.0
		var tab: Array = cba[kk[0]]
		for o: int in tab.size():
			c20 += float(tab[b2 - 3][o]) if s2 == 0 else float(tab[o][b2 - 3])
		var at: int = (b2 * 2 + s2) * 4
		nat[at] += x
		nat[at + 1] += float(e2[1])
		nat[at + 2] += m20 - c20
		nat[at + 3] += m20
	p.tr_married_apart = PackedFloat64Array()
	p.tr_married_apart.resize(p.tr_units)
	for u2: int in p.tr_units:
		var ck3: String = "%d|%d|%d" % [p.tr_key[u2 * KEY_STRIDE], p.tr_key[u2 * KEY_STRIDE + 1], p.tr_key[u2 * KEY_STRIDE + 2]]
		if ma.has(ck3) and float(cells[ck3][0]) > 0.0:
			p.tr_married_apart[u2] = float(ma[ck3]) / float(cells[ck3][0])
	p.tr_margins["ma"] = {"cells": ma, "national": nat, "over1": over1}


## The couple persons per "code|band|sex" (tr_couples and the non-head couples; men by the husband's band, women by the wife's), less
## the cross-tier spouses, who are individuals
static func _couple_cells(p: RefCounted) -> Dictionary:
	var cpc: Dictionary = {}
	for src: Dictionary in [p.tr_couples, p.tr_nh_couples]:
		for key: String in src:
			var k: PackedStringArray = key.split("|")
			var n2: float = float(src[key])
			cpc["%s|%d|0" % [k[0], int(k[1]) + 3]] = float(cpc.get("%s|%d|0" % [k[0], int(k[1]) + 3], 0.0)) + n2
			cpc["%s|%d|1" % [k[0], int(k[2]) + 3]] = float(cpc.get("%s|%d|1" % [k[0], int(k[2]) + 3], 0.0)) + n2
	var cross: Dictionary = p.tr_margins.get("r77_cross_cells", {})
	for ck0: String in cross:
		cpc[ck0] = float(cpc.get(ck0, 0.0)) - float(cross[ck0])
	return cpc


## §12.16 (M021): per "code|band|sex" (15+) the start's [persons, married, couple persons, never married, widowed, divorced, residual,
## shortfall, immigrants]: married = the couple persons x (1 + 2020's married-apart ratio); never married by the cohort identity (15-19
## the remainder); the residual = the persons less the four. Its immigration part (R90, §12.16 (4)), at most the positive residual,
## takes the foreigners' marital shares, its married to married-apart; the rest goes to the non-married states in proportion to them
## (taken from them in proportion when negative, each held at >= 0, the shortfall kept). Into tr_margins["m21"]
## Why not all of the residual to never married: at 70+ the non-married are mostly widowed (M021 §2)
static func _marital_cells(p: RefCounted, persons: Dictionary) -> Dictionary:
	var m24: Dictionary = (_v(p, "marital_2024") as Dictionary)["by_pref"]
	var imm: Dictionary = _v(p, "immigration_2020_2023")
	var cpc: Dictionary = _couple_cells(p)
	var out: Dictionary = {}
	for ck: String in persons:
		var kk: PackedStringArray = ck.split("|")
		var b: int = int(kk[1])
		var row: Array = m24[kk[0]][int(kk[2])][mini(b - 3, 14)]
		var n: float = float(persons[ck])
		var c: float = maxf(0.0, float(cpc.get(ck, 0.0)))
		var mar: float = minf(n, c * (1.0 + float(row[1])))
		var w: float = float(row[3])
		var d: float = float(row[4])
		var nv: float = maxf(0.0, n - mar - w - d) if float(row[2]) < 0.0 else float(row[2])
		var res: float = n - mar - nv - w - d
		var sx: int = int(kk[2])
		var iv: float = minf(maxf(0.0, float(imm["by_pref"][kk[0]][sx][mini(b - 3, 14)])), maxf(0.0, res))
		var ish: Array = imm["marital_shares"][sx][mini(b - 3, 14)]
		var res2: float = res - iv
		var nonm: float = nv + w + d
		var short: float = 0.0
		if nonm > 0.0:
			var f: float = maxf(0.0, 1.0 + res2 / nonm)
			short = maxf(0.0, -(res2 + nonm))
			nv *= f
			w *= f
			d *= f
		else:
			nv = maxf(0.0, res2)
		out[ck] = [n, mar + iv * float(ish[1]), c, nv + iv * float(ish[0]), w + iv * float(ish[2]), d + iv * float(ish[3]), res, short, iv]
	p.tr_margins["m21"] = out
	return out


## The never-married share a household role fixes (roles: head, partner, child, parent, other), or -1 for a free person
static func _role_never_married(t: int, r: int) -> float:
	if r == 2:
		return 1.0
	if r == 1 or r == 3:
		return 0.0
	if r == 0 and (t == 1 or t == 2):
		return 0.0
	if r == 0 and t == 3:
		return 0.1
	return -1.0


## (0) in reals (§12.6, §12.12 TO_E 05:53, R81's swap TO_E 05:55): each prefecture's seed is 人口推計 2022-10-01's band x sex shape (R81,
## total population, every band); then raked to the prefectures' populations (rows) and the cohort's band x sex counts scaled to the
## total (columns). Returns [prefecture][band x sex]
## Why not 国勢調査 2020's 15+ bands at the census's group shares (before): two years further from the start, and under 15 took the
## national shape (T)
## Why not the national shape inside every group (before): R77's couple shares are each prefecture's, and the national shape inside
## 15-64, 65-74 and 75+ put 197 prefecture x band cells of T1s-w (ii) beyond 6.6%
static func _base(p: RefCounted, codes: Array, prefectures: Dictionary, band_share: PackedFloat64Array) -> PackedFloat64Array:
	var pop22: Dictionary = (_v(p, "population_2022_by_pref_sex_band") as Dictionary)["by_pref"]
	var nc: int = codes.size()
	var nbs: int = BANDS * 2
	var x := PackedFloat64Array()
	x.resize(nc * nbs)
	var rows := PackedFloat64Array()
	rows.resize(nc)
	var total: float = 0.0
	for ci: int in nc:
		var code: String = "%02d" % codes[ci]
		rows[ci] = float(prefectures[code]["pop_thousand"]) * 1000.0
		total += rows[ci]
		var est: Array = pop22[str(codes[ci])]
		var est_tot: float = 0.0
		for s0: int in 2:
			for b0: int in BANDS:
				est_tot += float(est[s0][b0])
		for bs2: int in nbs:
			x[ci * nbs + bs2] = rows[ci] * float(est[bs2 % 2][bs2 / 2]) / est_tot
	var cols := PackedFloat64Array()
	cols.resize(nbs)
	for bs3: int in nbs:
		cols[bs3] = total * band_share[bs3]
	var fit: Dictionary = _v(p, "fit")
	_rake2(x, rows, cols, nc, nbs, int(fit["max_rounds"]), float(fit["tol"]))
	return x


static func _age_group(b: int) -> int:
	return 0 if b < 3 else (1 if b < 13 else (2 if b < 15 else 3))


## Employment by prefecture (§12.6): the national P(employment | band, sex) scaled once per prefecture so its 15+ labour-force rate and
## its unemployment rate are the census's (both sexes, one factor); the labour force capped below the students' complement, the rest
## of the persons outside the labour force rescaled to fill. Returns [prefecture][sex][band] -> PackedFloat64Array of NEMP
static func _employment(p: RefCounted, base: PackedFloat64Array, codes: Array, emp_bs: Array) -> Array:
	var lab: Dictionary = _v(p, "labour_by_prefecture")
	var pl: Dictionary = lab["prefectures"]
	var nbs: int = BANDS * 2
	var out: Array = []
	for ci: int in codes.size():
		var code: String = "%02d" % codes[ci]
		var lf_n: float = 0.0
		var u_n: float = 0.0
		var pop15: float = 0.0
		for bs: int in nbs:
			if bs / 2 < 3:
				continue
			var r: Array = emp_bs[bs % 2][bs / 2]
			var w: float = base[ci * nbs + bs]
			pop15 += w
			lf_n += w * (float(r[1]) + float(r[2]) + float(r[3]))
			u_n += w * float(r[3])
		var f_lf: float = 1.0
		var f_u: float = 1.0
		if pl.has(code) and lf_n > 0.0 and u_n > 0.0:
			f_lf = float(pl[code]["labour force rate"]) / (lf_n / pop15)
			f_u = float(pl[code]["unemployment rate"]) / (u_n / lf_n)
		var by_sex: Array = []
		for s: int in 2:
			var by_band: Array = []
			for b: int in BANDS:
				var r2: Array = emp_bs[s][b]
				var v := PackedFloat64Array()
				v.resize(NEMP)
				for e: int in NEMP:
					v[e] = float(r2[e])
				var lf: float = v[1] + v[2] + v[3]
				if b >= 3 and lf > 0.0:
					var lf2: float = minf(lf * f_lf, 1.0 - v[4])
					var un2: float = minf(lf2, lf2 * v[3] / lf * f_u)
					var em: float = v[1] + v[2]
					var em2: float = lf2 - un2
					var out_lf: float = v[0] + v[4] + v[5]
					var out2: float = 1.0 - lf2
					v[1] = v[1] / em * em2 if em > 0.0 else 0.0
					v[2] = v[2] / em * em2 if em > 0.0 else 0.0
					v[3] = un2
					for e2: int in [0, 4, 5]:
						v[e2] = v[e2] / out_lf * out2 if out_lf > 0.0 else 0.0
				by_band.append(v)
			by_sex.append(by_band)
		out.append(by_sex)
	return out


## The start fit (§12.5 F6, §12.12 (4) as amended TO_E 05:34) of the persons in no couple: (0) prefecture x band x sex held exact, and
## R64's persons by type and prefecture (households x the mean size of each type, D) less the couples' persons as (2*); (1), band x sex
## x type, is an outcome, reported. Returns [R64's worst share gap to (2*), the IPF's worst relative margin error, the IPF rounds]; the
## class residual is appended after the rounding
## Why not (1) held as the seed's margin (§12.12's first run): the couples' excess over 表V-1-3's couple-type share then came out of
## every type in proportion, and the one-person heads fell 0.94 M further below R64
## The fit's seed (§12.12): per (prefecture, band x sex) the persons in no couple, P(type | band, sex) less the couples' fixed persons,
## floored at 0 and renormalised; the couple-only type holds couples only, so its seed is 0. Returns [y, the couples above the share]
static func _seed(nc: int, base: PackedFloat64Array, fixed: PackedInt64Array, five: Array) -> Array:
	var nbs: int = BANDS * 2
	var y := PackedFloat64Array()
	y.resize(nc * nbs * NTYPE)
	var floor_excess: float = 0.0
	for ci: int in nc:
		for bs: int in nbs:
			var row: Array = five[bs % 2][bs / 2]
			var tot: float = 0.0
			for t: int in NTYPE:
				tot += maxf(0.0, float(row[t]))
			if tot <= 0.0:
				continue
			var fsum: float = 0.0
			var v := PackedFloat64Array()
			v.resize(NTYPE)
			var vt: float = 0.0
			for t2: int in NTYPE:
				var f: float = float(fixed[(ci * nbs + bs) * NTYPE + t2])
				fsum += f
				var want: float = base[ci * nbs + bs] * maxf(0.0, float(row[t2])) / tot
				v[t2] = 0.0 if t2 == 1 else maxf(0.0, want - f)
				floor_excess += maxf(0.0, f - want)
				vt += v[t2]
			var nnc: float = maxf(0.0, base[ci * nbs + bs] - fsum)
			for t3: int in NTYPE:
				if vt > 0.0:
					y[(ci * nbs + bs) * NTYPE + t3] = v[t3] / vt * nnc
	return [y, floor_excess]


## §12.14 size floor (TO_E 14:45): per prefecture, type 2's persons in no couple at least its head couples (one child each), types 3
## and 4 at least 2 x the target's households (type 4 less its couples' persons); a short type takes persons from the other types in no
## couple (2-5, not the floored ones) of the same prefecture and band, in proportion, spread over the bands by its own persons there,
## so (0) holds and the national type totals give way. Returns {"type|band": persons moved in}
## Why not a floor margin in the IPF: per-prefecture floors on some types and not others are not consistent with (1)'s national type
## totals, and the IPF would not converge
static func _size_floor(p: RefCounted, codes: Array, y: PackedFloat64Array, fixed: PackedInt64Array) -> Dictionary:
	var tgt: Dictionary = (_v(p, "household_target") as Dictionary)["by_pref"]
	var heads: Dictionary = _head_targets(p)
	var nbs: int = BANDS * 2
	var moved: Dictionary = {}
	for ci: int in codes.size():
		var tc: Array = tgt[str(codes[ci])]
		var have := PackedFloat64Array()
		have.resize(NTYPE)
		var h2: float = 0.0
		var f4: float = 0.0
		for bs: int in nbs:
			for t: int in NTYPE:
				have[t] += y[(ci * nbs + bs) * NTYPE + t]
			if bs % 2 == 0:
				h2 += float(fixed[(ci * nbs + bs) * NTYPE + 2])
			f4 += float(fixed[(ci * nbs + bs) * NTYPE + 4])
		var need := PackedFloat64Array([0.0, 0.0, h2, 2.0 * float(tc[3]), maxf(0.0, 2.0 * float(heads["%02d|4" % codes[ci]]) - f4), 0.0])
		var short := PackedFloat64Array()
		short.resize(NTYPE)
		for t2: int in [2, 3, 4]:
			short[t2] = maxf(0.0, need[t2] - have[t2])
		for t3: int in [2, 3, 4]:
			if short[t3] <= 0.0 or have[t3] <= 0.0:
				continue
			for bs2: int in nbs:
				var at: int = (ci * nbs + bs2) * NTYPE
				var want: float = short[t3] * y[at + t3] / have[t3]
				var pool: float = 0.0
				for u: int in range(2, NTYPE):
					if short[u] <= 0.0 and u != t3:
						pool += y[at + u]
				var take: float = minf(want, pool)
				if take <= 0.0:
					continue
				for u2: int in range(2, NTYPE):
					if short[u2] <= 0.0 and u2 != t3:
						y[at + u2] -= take * y[at + u2] / pool
				y[at + t3] += take
				var mk: String = "%d|%d" % [t3, bs2 / 2]
				moved[mk] = float(moved.get(mk, 0.0)) + take
	return moved


## §12.13 (c) (TO_E 14:10): per prefecture, the type-2 head couples above the fit's type-2 persons in no couple (in 表V-1-3's couple +
## children type every one of them a child) move to type 4, spread over the prefecture's type-2 couple cells in proportion to their
## counts by keyed systematic rounding; tr_couples and fixed are rewritten. Returns {code: moved}
static func _type2_cap(p: RefCounted, codes: Array, y: PackedFloat64Array, fixed: PackedInt64Array) -> Dictionary:
	var nbs: int = BANDS * 2
	var by_c: Dictionary = {}
	var keys: Array = p.tr_couples.keys()
	keys.sort()
	for k: String in keys:
		if k.ends_with("|2"):
			var c: int = int(k.get_slice("|", 0))
			if not by_c.has(c):
				by_c[c] = []
			by_c[c].append(k)
	var moved: Dictionary = {}
	for ci: int in codes.size():
		var c2: int = codes[ci]
		if not by_c.has(c2):
			continue
		var kids: float = 0.0
		for bs: int in nbs:
			kids += y[(ci * nbs + bs) * NTYPE + 2]
		var h: int = 0
		var w := PackedFloat64Array()
		for k2: String in by_c[c2]:
			h += int(p.tr_couples[k2])
			w.append(float(p.tr_couples[k2]))
		var ex: int = h - int(floor(kids))
		if ex <= 0:
			continue
		var mv: PackedInt64Array = _systematic(w, ex, p.seed_v, "tier_cap2", c2)
		for q: int in mv.size():
			if mv[q] <= 0:
				continue
			var k3: String = by_c[c2][q]
			var hb: int = int(k3.get_slice("|", 1))
			var wb: int = int(k3.get_slice("|", 2))
			var n: int = mini(mv[q], int(p.tr_couples[k3]))
			p.tr_couples[k3] = int(p.tr_couples[k3]) - n
			var k4: String = "%d|%d|%d|4" % [c2, hb, wb]
			p.tr_couples[k4] = int(p.tr_couples.get(k4, 0)) + n
			if int(p.tr_couples[k3]) == 0:
				p.tr_couples.erase(k3)
			for side: Array in [[(hb + 3) * 2], [(wb + 3) * 2 + 1]]:
				var at: int = (ci * nbs + int(side[0])) * NTYPE
				fixed[at + 2] -= n
				fixed[at + 4] += n
			moved[c2] = int(moved.get(c2, 0)) + n
	return moved


## The 10-year band of 表V-1-3 (§12.13): 0 under 15, 1 15-24 .. 7 75-84, 8 85+
static func _ten_band(b: int) -> int:
	return 0 if b < 3 else mini((b - 3) / 2 + 1, 8)


## 表V-1-3's type shares by sex x 10-year band (S, the spec's s_cells): [sex][10-year band] -> six shares
static func _ten_shares(p: RefCounted) -> Array:
	var labels: Array = ["<15", "15-24", "25-34", "35-44", "45-54", "55-64", "65-74", "75-84", "85+"]
	var out: Array = []
	for s: int in 2:
		var rows: Array = []
		for g: int in 9:
			rows.append([0.0, 0.0, 0.0, 0.0, 0.0, 0.0])
		out.append(rows)
	for c: Array in (p.tr_spec["type_by_band_sex"] as Dictionary)["s_cells"]:
		out[int(c[0])][labels.find(String(c[1]))][int(c[2])] = float(c[3])
	return out


## 表V-1-3's type shares split into 5-year bands by 第13-2表's 2020 shape (§12.13, TO_E 13:37; S): share(t, b) = the 10-year
## share(t, g) x q_k(b) / q_k(g), k = nuclear (types 1-3), non-nuclear (4), the rest of the private households (0), R76 less the
## private households (5; flat under 15, T), each 5-year band normalised: [sex][band] -> six shares
static func _five_shares(p: RefCounted) -> Array:
	var ten: Array = _ten_shares(p)
	var cr: Dictionary = (_v(p, "child_role") as Dictionary)["by_pref"]["0"]
	var pop: Array = (_v(p, "population_2020_by_pref_sex_band") as Dictionary)["by_pref"]["0"]
	var kind := [2, 0, 0, 0, 1, 3]
	var out: Array = []
	for s: int in 2:
		var q := PackedFloat64Array()   # band x [nuclear, non-nuclear, rest, institutions, persons]
		q.resize(BANDS * 5)
		for b: int in BANDS:
			var e: Array = cr["m" if s == 0 else "f"][b]
			var den: float = float(e[2]) if b < 3 else float(pop[s][b - 3])
			q[b * 5] = float(e[3])
			q[b * 5 + 1] = float(e[4])
			q[b * 5 + 2] = float(e[2]) - float(e[3]) - float(e[4])
			q[b * 5 + 3] = maxf(0.0, den - float(e[2])) if b >= 3 else 0.0
			q[b * 5 + 4] = den
		var rows: Array = []
		for b2: int in BANDS:
			var g: int = _ten_band(b2)
			var qg := PackedFloat64Array([0.0, 0.0, 0.0, 0.0, 0.0])
			for b3: int in BANDS:
				if _ten_band(b3) == g:
					for k: int in 5:
						qg[k] += q[b3 * 5 + k]
			var v: Array = []
			var vt: float = 0.0
			for t: int in NTYPE:
				var k2: int = kind[t]
				var qb: float = q[b2 * 5 + k2] / q[b2 * 5 + 4] if q[b2 * 5 + 4] > 0.0 else 0.0
				var qgk: float = qg[k2] / qg[4] if qg[4] > 0.0 else 0.0
				var r: float = qb / qgk if qgk > 0.0 and not (k2 == 3 and b2 < 3) else 1.0
				v.append(float(ten[s][g][t]) * r)
				vt += float(v[t])
			for t2: int in NTYPE:
				v[t2] = float(v[t2]) / vt if vt > 0.0 else 0.0
			rows.append(v)
		out.append(rows)
	return out


## M017b (§12.14 (3), R87 case 2): per prefecture x sex one IPF of the age-unknown, rows where they live (one-person, family type
## unknown, institutions; R87's raw counts), columns the 5-year bands with the persons the imputation added (imputed - raw, a negative
## band 0 and the bands rescaled to the rows), seeded by the age-known shape: 第13-2表's persons outside nuclear and non-nuclear
## households, national, for the first two rows (one-person 0 under 15), flat for institutions (T). Returns [sex] -> national
## allocated persons by row x band (3 x BANDS)
static func _age_unknown(p: RefCounted) -> Array:
	var au: Dictionary = (_v(p, "age_unknown") as Dictionary)["by_pref"]
	var cr: Dictionary = (_v(p, "child_role") as Dictionary)["by_pref"]["0"]
	var out: Array = []
	for s: int in 2:
		var sk: String = "m" if s == 0 else "f"
		var shape := PackedFloat64Array()
		shape.resize(BANDS)
		for b: int in BANDS:
			var e: Array = cr[sk][b]
			shape[b] = maxf(0.0, float(e[2]) - float(e[3]) - float(e[4]))
		var nat := PackedFloat64Array()
		nat.resize(3 * BANDS)
		for c: String in au:
			if c == "0":
				continue
			var a: Dictionary = au[c][sk]
			var rows := PackedFloat64Array([float(a["rows"][0]), float(a["rows"][1]), float(a["rows"][2])])
			var cols := PackedFloat64Array()
			cols.resize(BANDS)
			var ct: float = 0.0
			for b2: int in BANDS:
				cols[b2] = maxf(0.0, float(a["imputed"][b2]) - float(a["raw"][b2]))
				ct += cols[b2]
			var rt: float = rows[0] + rows[1] + rows[2]
			if ct <= 0.0 or rt <= 0.0:
				continue
			for b3: int in BANDS:
				cols[b3] *= rt / ct
			var x := PackedFloat64Array()
			x.resize(3 * BANDS)
			for b4: int in BANDS:
				x[b4] = shape[b4] if b4 >= 3 else 0.0
				x[BANDS + b4] = shape[b4]
				x[2 * BANDS + b4] = 1.0
			_rake2(x, rows, cols, 3, BANDS, 500, 1e-12)
			for q: int in 3 * BANDS:
				nat[q] += x[q]
		out.append(nat)
	return out


## The completed 2020 shares (M017b §2): the age-known count of each type (the 5-year shares x R87's raw persons), plus the
## allocated age-unknown (one-person to type 0, institutions to type 5, family type unknown over types 0-4 in proportion to the
## cell, T), over the imputed persons; then type 0 raked by one factor to the household target's one-person total over the start's
## persons (base), the other types giving way in each band (§12.14 (1), (3)). Returns [sex][band] -> six shares
static func _completed_shares(p: RefCounted, five: Array, base: PackedFloat64Array, nc: int) -> Array:
	var au: Dictionary = (_v(p, "age_unknown") as Dictionary)["by_pref"]["0"]
	var alloc: Array = _age_unknown(p)
	var nbs: int = BANDS * 2
	var out: Array = []
	for s: int in 2:
		var a: Dictionary = au["m" if s == 0 else "f"]
		var rows: Array = []
		for b: int in BANDS:
			var raw: float = float(a["raw"][b])
			var imp: float = float(a["imputed"][b])
			var cnt := PackedFloat64Array()
			cnt.resize(NTYPE)
			var rel: float = 0.0
			for t: int in NTYPE:
				cnt[t] = float(five[s][b][t]) * raw
				rel += cnt[t] if t < 5 else 0.0
			var unk: float = (alloc[s] as PackedFloat64Array)[BANDS + b]
			for t2: int in 5:
				cnt[t2] += unk * cnt[t2] / rel if rel > 0.0 else 0.0
			cnt[0] += (alloc[s] as PackedFloat64Array)[b]
			cnt[5] += (alloc[s] as PackedFloat64Array)[2 * BANDS + b]
			var v: Array = []
			for t3: int in NTYPE:
				v.append(cnt[t3] / imp if imp > 0.0 else float(five[s][b][t3]))
			rows.append(v)
		out.append(rows)
	var want: float = float((_v(p, "household_target") as Dictionary)["by_pref"]["0"][0])
	var have: float = 0.0
	for ci: int in nc:
		for bs: int in nbs:
			have += float(out[bs % 2][bs / 2][0]) * base[ci * nbs + bs]
	var f: float = want / have if have > 0.0 else 1.0
	p.tr_margins["one_rake"] = [have, want, f]
	for s2: int in 2:
		for b2: int in BANDS:
			var r: Array = out[s2][b2]
			var s0: float = float(r[0])
			var n0: float = minf(1.0, s0 * f)
			for t4: int in NTYPE:
				r[t4] = n0 if t4 == 0 else (float(r[t4]) * (1.0 - n0) / (1.0 - s0) if s0 < 1.0 else 0.0)
	return out


## (1) at 5-year band x sex x type (§12.13): the share x the start's persons less the couples' fixed persons, floored at 0 (type 1
## holds couples only), type 0 held and the rest scaled to the cell's persons in no couple (§12.14); returns [targets, half the L1 shift of the projection]
static func _type_targets(y: PackedFloat64Array, nc: int, pop_bs: PackedFloat64Array, fixed: PackedInt64Array, five: Array) -> Array:
	var nbs: int = BANDS * 2
	var n := PackedFloat64Array()
	n.resize(nbs)
	var f := PackedFloat64Array()
	f.resize(nbs * NTYPE)
	var yc := PackedFloat64Array()
	yc.resize(nbs)
	for ci: int in nc:
		for bs: int in nbs:
			n[bs] += pop_bs[ci * nbs + bs]
			for t: int in NTYPE:
				f[bs * NTYPE + t] += float(fixed[(ci * nbs + bs) * NTYPE + t])
				yc[bs] += y[(ci * nbs + bs) * NTYPE + t]
	var tg := PackedFloat64Array()
	tg.resize(nbs * NTYPE)
	var shift: float = 0.0
	for g2: int in nbs:
		var raw := PackedFloat64Array()
		raw.resize(NTYPE)
		var rt: float = 0.0
		for t2: int in NTYPE:
			raw[t2] = 0.0 if t2 == 1 else maxf(0.0, float(five[g2 % 2][g2 / 2][t2]) * n[g2] - f[g2 * NTYPE + t2])
			rt += raw[t2]
		# §12.14 (1): type 0 holds its target share; the other types give way inside the cell's persons in no couple
		var r0: float = minf(raw[0], yc[g2])
		for t3: int in NTYPE:
			if t3 == 0:
				tg[g2 * NTYPE] = r0
			else:
				tg[g2 * NTYPE + t3] = raw[t3] / (rt - raw[0]) * (yc[g2] - r0) if rt - raw[0] > 0.0 else 0.0
			shift += absf(tg[g2 * NTYPE + t3] + f[g2 * NTYPE + t3] - float(five[g2 % 2][g2 / 2][t3]) * n[g2]) * 0.5
	return [tg, shift]


static func _fit(p: RefCounted, y: PackedFloat64Array, codes: Array, prefectures: Dictionary, fixed: PackedInt64Array, pop_bs: PackedFloat64Array, five: Array) -> PackedFloat64Array:
	var by_pref: Dictionary = _v(p, "type_by_prefecture")
	var fit: Dictionary = _v(p, "fit")
	var max_rounds: int = int(fit["max_rounds"])
	var tol: float = float(fit["tol"])
	var mean_size := PackedFloat64Array([1.0, 2.0, 3.6, 2.5, 4.2, 1.0])
	var nc: int = codes.size()
	var nbs: int = BANDS * 2
	var base := PackedFloat64Array()
	base.resize(nc * nbs)
	var m := PackedFloat64Array()
	m.resize(nc * NTYPE)
	for ci: int in nc:
		for bs: int in nbs:
			for t: int in NTYPE:
				var v: float = y[(ci * nbs + bs) * NTYPE + t]
				base[ci * nbs + bs] += v
				m[ci * NTYPE + t] += v
	var rows := PackedFloat64Array()
	rows.resize(nc)
	var r64 := PackedFloat64Array()
	r64.resize(nc * NTYPE)
	for ci2: int in nc:
		for t2: int in NTYPE:
			rows[ci2] += m[ci2 * NTYPE + t2]
		var code: String = "%02d" % codes[ci2]
		if by_pref.has(code):
			var hs: Array = by_pref[code]
			var tot_w: float = 0.0
			for t3: int in 5:
				tot_w += float(hs[t3]) * mean_size[t3]
			var fpt := PackedFloat64Array()
			fpt.resize(NTYPE)
			for bs8: int in nbs:
				for t8: int in NTYPE:
					fpt[t8] += float(fixed[(ci2 * nbs + bs8) * NTYPE + t8])
			var priv: float = rows[ci2] - m[ci2 * NTYPE + 5]
			var priv_all: float = priv + fpt[0] + fpt[1] + fpt[2] + fpt[3] + fpt[4]
			var mt := PackedFloat64Array()
			mt.resize(5)
			var mtot: float = 0.0
			for t4: int in 5:
				var room: bool = t4 != 1 and m[ci2 * NTYPE + t4] > 0.0
				mt[t4] = maxf(0.0, float(hs[t4]) * mean_size[t4] / tot_w * priv_all - fpt[t4]) if room else 0.0
				mtot += mt[t4]
			for t9: int in 5:
				m[ci2 * NTYPE + t9] = mt[t9] / mtot * priv if mtot > 0.0 else 0.0
		for t5: int in NTYPE:
			r64[ci2 * NTYPE + t5] = m[ci2 * NTYPE + t5] / rows[ci2]
	# §12.14 (1): the household-type target first, here its one-person persons per prefecture (households = persons) against the rest;
	# R64's types are read as a report (gap) after the fit
	# Why not R64's (2*) raked to (1) (§12.13, d9d95443): R64 holds 2020's composition on 2024 with the age-unknown inside, M017
	var tt: Array = _type_targets(y, nc, pop_bs, fixed, five)
	var tg: PackedFloat64Array = tt[0]
	p.tr_margins["ten_shift"] = tt[1]
	var t0: Dictionary = (_v(p, "household_target") as Dictionary)["by_pref"]
	var m2 := PackedFloat64Array()
	m2.resize(nc * 2)
	var n0: float = 0.0
	for g0: int in nbs:
		n0 += tg[g0 * NTYPE]
	var s0: float = 0.0
	for ci4: int in nc:
		s0 += float(t0[str(codes[ci4])][0])
	for ci5: int in nc:
		m2[ci5 * 2] = float(t0[str(codes[ci5])][0]) * n0 / s0
		m2[ci5 * 2 + 1] = rows[ci5] - m2[ci5 * 2]
	var err: float = 0.0
	var used: int = 0
	var sm := PackedFloat64Array()
	var sb := PackedFloat64Array()
	var sg := PackedFloat64Array()
	for r: int in max_rounds:
		used = r + 1
		sm.resize(0)
		sm.resize(nc * 2)
		for i: int in y.size():
			sm[(i / (nbs * NTYPE)) * 2 + (0 if i % NTYPE == 0 else 1)] += y[i]
		for i2: int in y.size():
			var mi: int = (i2 / (nbs * NTYPE)) * 2 + (0 if i2 % NTYPE == 0 else 1)
			if sm[mi] > 0.0:
				y[i2] *= m2[mi] / sm[mi]
		sg.resize(0)
		sg.resize(nbs * NTYPE)
		for i3: int in y.size():
			sg[i3 % (nbs * NTYPE)] += y[i3]
		for i4: int in y.size():
			var gi: int = i4 % (nbs * NTYPE)
			if sg[gi] > 0.0:
				y[i4] *= tg[gi] / sg[gi]
		sb.resize(0)
		sb.resize(nc * nbs)
		for i5: int in y.size():
			sb[i5 / NTYPE] += y[i5]
		for i6: int in y.size():
			if sb[i6 / NTYPE] > 0.0:
				y[i6] *= base[i6 / NTYPE] / sb[i6 / NTYPE]
		err = 0.0
		sm.resize(0)
		sm.resize(nc * 2)
		for i7: int in y.size():
			sm[(i7 / (nbs * NTYPE)) * 2 + (0 if i7 % NTYPE == 0 else 1)] += y[i7]
		for j: int in sm.size():
			if m2[j] > 0.0:
				err = maxf(err, absf(sm[j] - m2[j]) / m2[j])
		sg.resize(0)
		sg.resize(nbs * NTYPE)
		for i8: int in y.size():
			sg[i8 % (nbs * NTYPE)] += y[i8]
		for j2: int in sg.size():
			if tg[j2] > 0.0:
				err = maxf(err, absf(sg[j2] - tg[j2]) / tg[j2])
		if err < tol:
			break
	var gap: float = 0.0
	var sf := PackedFloat64Array()
	sf.resize(nc * NTYPE)
	for i9: int in y.size():
		sf[(i9 / (nbs * NTYPE)) * NTYPE + i9 % NTYPE] += y[i9]
	for ci3: int in nc:
		for t7: int in NTYPE:
			gap = maxf(gap, absf(sf[ci3 * NTYPE + t7] / rows[ci3] - r64[ci3 * NTYPE + t7]))
	return PackedFloat64Array([gap, err, float(used)])


## The integer targets of (0) and (1) as the rounding set them (T1s-l reads the units against them)
static func rounded_margins(p: RefCounted, _prefectures: Dictionary) -> Dictionary:
	return p.tr_margins


## A two-way table x (nr x nk) raked to row and column totals (equal grand totals)
static func _rake2(x: PackedFloat64Array, rows: PackedFloat64Array, cols: PackedFloat64Array, nr: int, nk: int, rounds: int, tol: float) -> void:
	for r: int in rounds:
		for i: int in nr:
			var s: float = 0.0
			for k: int in nk:
				s += x[i * nk + k]
			if s > 0.0:
				for k2: int in nk:
					x[i * nk + k2] *= rows[i] / s
		var worst: float = 0.0
		for k3: int in nk:
			var s2: float = 0.0
			for i2: int in nr:
				s2 += x[i2 * nk + k3]
			if s2 > 0.0:
				worst = maxf(worst, absf(s2 - cols[k3]) / maxf(1.0, cols[k3]))
				for i3: int in nr:
					x[i3 * nk + k3] *= cols[k3] / s2
		if worst < tol:
			break


## The integer step (§12.5 F6): the prefectures' populations split over band x sex by the largest remainder ((0): the prefectures exact, the cohort's shape within rounding); per band x sex,
## (1)'s national type totals to integers by the largest remainder; the slice (prefecture x type) raked in reals to those integer rows
## and columns, each row rounded by keyed systematic rounding, then the columns repaired along alternating paths (each cell at its floor
## or ceiling). Returns the integer (prefecture, band x sex, type) counts; the moves and the out-of-bound moves go to the residuals
static func _round(p: RefCounted, y: PackedFloat64Array, codes: Array, prefectures: Dictionary, base: PackedFloat64Array, fixed: PackedInt64Array) -> PackedInt64Array:
	var nc: int = codes.size()
	var nbs: int = BANDS * 2
	var R := PackedInt64Array()
	R.resize(nc * nbs)
	for ci: int in nc:
		var pop: int = int(prefectures["%02d" % codes[ci]]["pop_thousand"]) * 1000
		var v := PackedFloat64Array()
		v.resize(nbs)
		for bs: int in nbs:
			v[bs] = base[ci * nbs + bs]
		var ints: PackedInt64Array = _largest(v, pop)
		for bs2: int in nbs:
			R[ci * nbs + bs2] = ints[bs2]
	p.tr_margins = {"pbs": {}, "bst": {}, "bs_real": {}, "bst_real": {}}
	for ci6: int in nc:
		for bs6: int in nbs:
			p.tr_margins["pbs"]["%d|%d|%d" % [codes[ci6], bs6 / 2, bs6 % 2]] = R[ci6 * nbs + bs6]
			var kr: String = "%d|%d" % [bs6 / 2, bs6 % 2]
			p.tr_margins["bs_real"][kr] = float(p.tr_margins["bs_real"].get(kr, 0.0)) + base[ci6 * nbs + bs6]
	var out := PackedInt64Array()
	out.resize(y.size())
	var moves: int = 0
	var oob: int = 0
	var over: int = 0
	for bs3: int in nbs:
		var ntot: int = 0
		var rows := PackedFloat64Array()
		rows.resize(nc)
		var Rn := PackedInt64Array()
		Rn.resize(nc)
		var fcol := PackedInt64Array()
		fcol.resize(NTYPE)
		for ci2: int in nc:
			var fs: int = 0
			for t0: int in NTYPE:
				fs += fixed[(ci2 * nbs + bs3) * NTYPE + t0]
				fcol[t0] += fixed[(ci2 * nbs + bs3) * NTYPE + t0]
			over += maxi(0, fs - R[ci2 * nbs + bs3])
			Rn[ci2] = maxi(0, R[ci2 * nbs + bs3] - fs)
			ntot += Rn[ci2]
			rows[ci2] = float(Rn[ci2])
		var ct := PackedFloat64Array()
		ct.resize(NTYPE)
		var x := PackedFloat64Array()
		x.resize(nc * NTYPE)
		for ci3: int in nc:
			for t: int in NTYPE:
				x[ci3 * NTYPE + t] = y[(ci3 * nbs + bs3) * NTYPE + t]
				ct[t] += x[ci3 * NTYPE + t]
		var C: PackedInt64Array = _largest(ct, ntot)
		for t6: int in NTYPE:
			p.tr_margins["bst"]["%d|%d|%d" % [bs3 / 2, bs3 % 2, t6]] = C[t6] + fcol[t6]
			p.tr_margins["bst_real"]["%d|%d|%d" % [bs3 / 2, bs3 % 2, t6]] = ct[t6] + float(fcol[t6])
		var cf := PackedFloat64Array()
		cf.resize(NTYPE)
		for t2: int in NTYPE:
			cf[t2] = float(C[t2])
		_rake2(x, rows, cf, nc, NTYPE, 500, 1e-13)
		var z := PackedInt64Array()
		z.resize(nc * NTYPE)
		for ci4: int in nc:
			var rv := PackedFloat64Array()
			rv.resize(NTYPE)
			for t3: int in NTYPE:
				rv[t3] = x[ci4 * NTYPE + t3]
			var ri: PackedInt64Array = _systematic(rv, Rn[ci4], p.seed_v, "tier_row", ci4 * nbs + bs3)
			for t4: int in NTYPE:
				z[ci4 * NTYPE + t4] = ri[t4]
		var mv: Array = _repair(z, x, C, nc)
		moves += int(mv[0])
		oob += int(mv[1])
		var to4: int = 0
		for ci9: int in nc:
			to4 += z[ci9 * NTYPE + 1]
			z[ci9 * NTYPE + 4] += z[ci9 * NTYPE + 1]
			z[ci9 * NTYPE + 1] = 0
		p.tr_margins["bst"]["%d|%d|1" % [bs3 / 2, bs3 % 2]] = int(p.tr_margins["bst"]["%d|%d|1" % [bs3 / 2, bs3 % 2]]) - to4
		p.tr_margins["bst"]["%d|%d|4" % [bs3 / 2, bs3 % 2]] = int(p.tr_margins["bst"]["%d|%d|4" % [bs3 / 2, bs3 % 2]]) + to4
		p.tr_margins["r77_type1_to4"] = int(p.tr_margins.get("r77_type1_to4", 0)) + to4
		for ci5: int in nc:
			for t5: int in NTYPE:
				out[(ci5 * nbs + bs3) * NTYPE + t5] = z[ci5 * NTYPE + t5] + fixed[(ci5 * nbs + bs3) * NTYPE + t5]
	p.tr_residual.append(float(moves))
	p.tr_residual.append(float(oob))
	p.tr_margins["r77_over"] = over
	return out


## v to integers summing to total: the floors, then the remainder to the largest fractional parts (ties by index)
static func _largest(v: PackedFloat64Array, total: int) -> PackedInt64Array:
	var out := PackedInt64Array()
	out.resize(v.size())
	var used: int = 0
	for i: int in v.size():
		out[i] = int(floor(v[i]))
		used += out[i]
	var order: Array = range(v.size())
	order.sort_custom(func(i: int, j: int) -> bool: return (v[i] - floor(v[i])) > (v[j] - floor(v[j])) if (v[i] - floor(v[i])) != (v[j] - floor(v[j])) else i < j)
	var q: int = 0
	while used < total:
		out[order[q % v.size()]] += 1
		used += 1
		q += 1
	while used > total:
		var i2: int = order[v.size() - 1 - (q % v.size())]
		if out[i2] > 0:
			out[i2] -= 1
			used -= 1
		q += 1
	return out


## A binomial draw of n persons at probability p from one keyed u (§13.2, §14.2): below n p q = 12 the exact inversion by the pmf
## recurrence from f(0) = q^n, the terms in index order, stopped at the support's cap; at 12 and above the continuity-corrected normal,
## clipped to [0, n]; a p above 1/2 through n - X
## Why the switch at 12 and not 9: the normal's total variation is 0.041-0.042 at n p q = 9 for p <= 0.01, above DM-b's 0.04 (M006 P7)
## Why the cap: a u within rounding of 1 would otherwise run the sum to n, every person drawn (M006 P9)
static func binomial(n: int, p: float, u: float) -> int:
	if n <= 0 or p <= 0.0:
		return 0
	if p >= 1.0:
		return n
	if p > 0.5:
		return n - binomial(n, 1.0 - p, 1.0 - u)
	var q: float = 1.0 - p
	var npq: float = float(n) * p * q
	if npq < BINOM_SWITCH:
		var cap: int = mini(n, int(float(n) * p + 40.0 * sqrt(npq) + 40.0))
		var f: float = DM.pow(q, float(n))
		var acc: float = f
		var k: int = 0
		while acc < u and k < cap:
			f *= float(n - k) * p / (float(k + 1) * q)
			if f <= 0.0:
				break
			k += 1
			acc += f
		return k
	return clampi(int(ceil(float(n) * p + sqrt(npq) * DM.inv_normal(u) - 0.5)), 0, n)


## The persons drawn from each of the holders: d draws without replacement from Σ holds, allocated by sequential conditional
## hypergeometric draws in index order, one keyed u per holder (§13.3, §14.2a); never more than a holder holds
## Why not conditional binomials: a binomial step can exceed a holder's count
static func hypergeometric_split(holds: PackedInt64Array, d: int, seed_v: int, tag: String, key: int) -> PackedInt64Array:
	var out := PackedInt64Array()
	out.resize(holds.size())
	var n_rem: int = 0
	for h: int in holds:
		n_rem += h
	var d_rem: int = mini(d, n_rem)
	for i: int in holds.size():
		if d_rem <= 0:
			break
		var k: int = holds[i]
		var x: int = d_rem if k >= n_rem else hypergeometric(n_rem, k, d_rem, KEYED.u(seed_v, tag, key, i, 0))
		out[i] = x
		d_rem -= x
		n_rem -= k
	return out


## One hypergeometric draw: x of d drawn from n holding k, from one keyed u. The complement (k > n ÷ 2) and the draws' complement
## (d > n ÷ 2) bring the inversion's start f(0) away from underflow; below a variance of 12 the exact inversion by the pmf recurrence,
## at 12 and above the continuity-corrected normal, clipped to the support (§14.2a)
## Why the switch: f(0) is about (1 - k ÷ n)^d, 2^-10,000 at n = 20,000 with k and d near 10,000, even after the complements
static func hypergeometric(n: int, k: int, d: int, u: float) -> int:
	if d <= 0 or k <= 0:
		return 0
	if k >= n:
		return d
	if 2 * k > n:
		return d - hypergeometric(n, n - k, d, 1.0 - u)
	if 2 * d > n:
		return k - hypergeometric(n, k, n - d, 1.0 - u)
	var mean: float = float(d) * float(k) / float(n)
	var var_x: float = mean * (1.0 - float(k) / float(n)) * float(n - d) / float(maxi(1, n - 1))
	var hi: int = mini(d, k)
	if var_x < BINOM_SWITCH:
		var f: float = 1.0
		for i: int in d:
			f *= float(n - k - i) / float(n - i)
		var acc: float = f
		var x: int = 0
		while acc < u and x < hi:
			f *= float(k - x) * float(d - x) / (float(x + 1) * float(n - k - d + x + 1))
			if f <= 0.0:
				break
			x += 1
			acc += f
		return x
	return clampi(int(ceil(mean + sqrt(var_x) * DM.inv_normal(u) - 0.5)), 0, hi)


## The keyed merge of the pair with the least added variance w_i w_k (x_i - x_k)² (§14.6 (4) under M025, ties to the lower pair): the
## lower index kept with probability w_lo ÷ (w_lo + w_hi), taking the summed mass; returns [the masses, the states] without the dropped
## Why not the two lightest (§13.1, T2.0): it merges whatever is light however different, +24% bias in a state x marital cross-moment (M025 §2)
static func merge_least(w: PackedInt64Array, x: PackedFloat64Array, seed_v: int, tag: String, key: int) -> Array:
	var lo: int = 0
	var hi: int = 1
	var best: float = INF
	for a: int in w.size():
		for b: int in range(a + 1, w.size()):
			var c: float = float(w[a]) * float(w[b]) * (x[a] - x[b]) * (x[a] - x[b])
			if c < best:
				best = c
				lo = a
				hi = b
	var keep_lo: bool = KEYED.u(seed_v, tag, key, 0, 0) * float(w[lo] + w[hi]) < float(w[lo])
	var kept: int = lo if keep_lo else hi
	var drop: int = hi if keep_lo else lo
	var w2: PackedInt64Array = w.duplicate()
	var x2: PackedFloat64Array = x.duplicate()
	w2[kept] = w[kept] + w[drop]
	w2.remove_at(drop)
	x2.remove_at(drop)
	return [w2, x2]


## v to integers summing to total by keyed systematic rounding: the floors, then one keyed u places the remainder over the fractional
## parts in index order, so each entry's expected integer is its real value
## Why not the largest remainder: it never gives a unit to a small fractional part, and the top 0.01% tier came out 16% short (§11.1a)
static func _systematic(v: PackedFloat64Array, total: int, seed_v: int, tag: String, key: int) -> PackedInt64Array:
	var out := PackedInt64Array()
	out.resize(v.size())
	var used: int = 0
	var fr := PackedFloat64Array()
	fr.resize(v.size())
	var sf: float = 0.0
	for i: int in v.size():
		var x: float = maxf(0.0, v[i])
		out[i] = int(floor(x))
		fr[i] = x - float(out[i])
		used += out[i]
		sf += fr[i]
	var left: int = total - used
	if left > 0 and sf > 0.0:
		var step: float = sf / float(left)
		var at: float = preload("res://sim/earth_core/keyed.gd").u(seed_v, tag, key, 0, 0) * step
		var acc: float = 0.0
		var placed: int = 0
		for i2: int in v.size():
			acc += fr[i2]
			while placed < left and at < acc:
				out[i2] += 1
				placed += 1
				at += step
		used += placed
	return _largest_fix(out, v, total, used)


static func _largest_fix(out: PackedInt64Array, v: PackedFloat64Array, total: int, used: int) -> PackedInt64Array:
	var i: int = 0
	while used < total and v.size() > 0:
		var best: int = 0
		for j: int in v.size():
			if v[j] - float(out[j]) > v[best] - float(out[best]):
				best = j
		out[best] += 1
		used += 1
		i += 1
	while used > total:
		var worst: int = -1
		for j2: int in v.size():
			if out[j2] > 0 and (worst < 0 or float(out[j2]) - v[j2] > float(out[worst]) - v[worst]):
				worst = j2
		out[worst] -= 1
		used -= 1
	return out


## The columns of an integer slice z (rows exact) brought to their totals C: one person at a time along a path of columns, each step a
## row whose cell can go down (above its floor) to one whose cell can go up (below its ceiling); a column with no such path takes an
## out-of-bound move (counted). Returns [moves, out-of-bound moves]
static func _repair(z: PackedInt64Array, x: PackedFloat64Array, C: PackedInt64Array, nc: int, nk: int = NTYPE) -> Array:
	var moves: int = 0
	var oob: int = 0
	for guard: int in 100000:
		var d := PackedInt64Array()
		d.resize(nk)
		for t: int in nk:
			d[t] = -C[t]
		for ci: int in nc:
			for t2: int in nk:
				d[t2] += z[ci * nk + t2]
		var src: int = -1
		for t3: int in nk:
			if d[t3] > 0:
				src = t3
				break
		if src < 0:
			break
		# BFS over columns from src; prev[t] = [from column, row]
		var prev: Dictionary = {src: [-1, -1]}
		var queue: Array = [src]
		var dst: int = -1
		while not queue.is_empty() and dst < 0:
			var a: int = queue.pop_front()
			for ci2: int in nc:
				if float(z[ci2 * nk + a]) <= floor(x[ci2 * nk + a]) + 1e-9:
					continue
				for b: int in nk:
					if prev.has(b) or float(z[ci2 * nk + b]) >= ceil(x[ci2 * nk + b] - 1e-9):
						continue
					prev[b] = [a, ci2]
					queue.append(b)
					if d[b] < 0:
						dst = b
						break
				if dst >= 0:
					break
		if dst >= 0:
			var at: int = dst
			while at != src:
				var pv: Array = prev[at]
				z[int(pv[1]) * nk + int(pv[0])] -= 1
				z[int(pv[1]) * nk + at] += 1
				moves += 1
				at = int(pv[0])
		else:
			var dn: int = -1
			for t4: int in nk:
				if d[t4] < 0:
					dn = t4
					break
			for ci3: int in nc:
				if z[ci3 * nk + src] > 0:
					z[ci3 * nk + src] -= 1
					z[ci3 * nk + dn] += 1
					oob += 1
					break
	return [moves, oob]


## The top 0.01%'s individuals (the owner's about 3,000): drawn from the top class's cells in proportion to their counts (keyed), each
## subtracted from its bundle and placed as a person of the persons layer with the top income (D) and assets (T)
static func _individuals(p: RefCounted, lines: PackedFloat64Array, tab: PackedFloat64Array) -> void:
	var cls: Dictionary = _v(p, "classes")
	var want: int = int(cls["individuals_top"])
	var top: Array = []
	var tot: int = 0
	p.tr_indiv_code = PackedInt32Array()
	for u: int in p.tr_units:
		if p.tr_key[u * KEY_STRIDE + 3] == 0 and p.tr_count[u] > 0:
			top.append(u)
			tot += p.tr_count[u]
	# V114 (4): a type-4 cell keeps at least its head and non-head couples' fixed persons, so no couple loses a person to the individuals
	var free4: Dictionary = {}   # "code|band|sex" -> type-4 persons above the couples' persons
	for u0: int in p.tr_units:
		for m0: int in range(p.tr_mix_off[u0], p.tr_mix_off[u0 + 1]):
			if (p.tr_mix_code[m0] / NEMP) % NTYPE == 4:
				var k0: String = "%d|%d|%d" % [p.tr_key[u0 * KEY_STRIDE], p.tr_key[u0 * KEY_STRIDE + 1], p.tr_key[u0 * KEY_STRIDE + 2]]
				free4[k0] = int(free4.get(k0, 0)) + p.tr_mix_n[m0]
	for src: Dictionary in [p.tr_couples, p.tr_nh_couples]:
		for kc: String in src:
			var f: PackedStringArray = kc.split("|")
			if src == p.tr_couples and int(f[3]) != 4:
				continue
			for side: Array in [[int(f[1]) + 3, 0], [int(f[2]) + 3, 1]]:
				var k1: String = "%s|%d|%d" % [f[0], int(side[0]), int(side[1])]
				free4[k1] = int(free4.get(k1, 0)) - int(src[kc])
	var draws: Array = []
	var dcodes: Array = []
	var redrawn: int = 0
	for q: int in want:
		if tot <= 0:
			break
		for attempt: int in 64:
			var x: int = p.KEYED.below(tot, p.seed_v, "tier_indiv", q, attempt, 0)
			var acc: int = 0
			var done: bool = false
			for u2: int in top:
				acc += p.tr_count[u2]
				if x < acc:
					if p.tr_count[u2] > 0:
						var m: int = mix_draw(p, u2, p.KEYED.below(p.tr_count[u2], p.seed_v, "tier_indiv_mix", q, attempt, 0))
						var k2: String = "%d|%d|%d" % [p.tr_key[u2 * KEY_STRIDE], p.tr_key[u2 * KEY_STRIDE + 1], p.tr_key[u2 * KEY_STRIDE + 2]]
						var t4: bool = (p.tr_mix_code[m] / NEMP) % NTYPE == 4
						if t4 and int(free4.get(k2, 0)) <= 0:
							redrawn += 1
							break
						if t4:
							free4[k2] = int(free4[k2]) - 1
						draws.append(u2)
						dcodes.append(p.tr_mix_code[m])
						p.tr_mix_n[m] -= 1
						p.tr_count[u2] -= 1
						tot -= 1
					done = true
					break
			if done:
				break
	p.tr_margins["indiv_redrawn"] = redrawn
	p.place_persons(draws.size())
	for i: int in draws.size():
		var u3: int = draws[i]
		var b: int = p.tr_key[u3 * KEY_STRIDE + 1]
		var na: int = 0
		for y0: int in AGE_SLOTS:
			na += p.tr_age_counts[u3 * AGE_SLOTS + y0]
		var y: int = age_draw(p, u3, p.KEYED.below(na, p.seed_v, "tier_age", i, 0, 0))
		p.tr_age_counts[u3 * AGE_SLOTS + y] -= 1
		var a: int = b * 5 + y
		p.place_person(i, p.tr_key[u3 * KEY_STRIDE], 3000000 + i, a, p.tr_key[u3 * KEY_STRIDE + 2])
	for i2: int in p.n:
		p.draw_person(i2)
		p.finish_person(i2)
		var u4: int = draws[i2]
		var dc: int = dcodes[i2]
		p.tier_person(i2, dc % NEMP, mini((dc / NEMP) % NTYPE, 4), -1.0, -1.0)
		_class_draw(p, i2, dc / (NTYPE * NEMP), lines, tab, "tier_inc_i", i2)
		p.tr_indiv_unit.append(u4)
		p.tr_indiv_code.append(dc)


static func a_slot(p: RefCounted, u: int, a: int) -> int:
	var b: int = p.tr_key[u * KEY_STRIDE + 1]
	return clampi(a - b * 5, 0, AGE_SLOTS - 1 if b == BANDS - 1 else 4)


## The single-age slot of unit u at a keyed index below the unit's age counts (their cumulative counts in slot order)
static func age_draw(p: RefCounted, u: int, x: int) -> int:
	var acc: int = 0
	for y: int in AGE_SLOTS:
		acc += p.tr_age_counts[u * AGE_SLOTS + y]
		if x < acc:
			return y
	return AGE_SLOTS - 1


## The K sample persons of every bundle (§11.2): each a notional person drawn with the persons' own generators into a scratch slot,
## keyed by the bundle and the point, then copied into the point arrays. Why a scratch slot: the generators write the persons' arrays
## by index, and reusing them keeps the point's draw identical to a person's
static func _points(p: RefCounted, lines: PackedFloat64Array, tab: PackedFloat64Array, tm: Dictionary) -> void:
	_point_counts(p)
	var n_pts: int = p.tr_pt_off[p.tr_units]
	var n_ind: int = p.n
	p.place_persons(n_ind + 1)
	var scratch: int = n_ind
	p.tr_points = {}
	var rows: Array = point_rows(p)
	for r: Array in rows:
		var arr = (PackedInt32Array() if String(r[1]) == "i32" else PackedFloat64Array())
		arr.resize(n_pts * int(r[2]))
		p.tr_points[String(r[0])] = arr
	var phi := PackedFloat64Array()
	phi.resize(n_pts)
	var pen := PackedFloat64Array()
	pen.resize(n_pts)
	var kind := PackedInt32Array()
	kind.resize(n_pts)
	p.tr_pt_code = PackedInt32Array()
	p.tr_pt_code.resize(n_pts)
	for u: int in p.tr_units:
		var c: int = p.tr_key[u * KEY_STRIDE]
		var b: int = p.tr_key[u * KEY_STRIDE + 1]
		var s: int = p.tr_key[u * KEY_STRIDE + 2]
		var stt: Array = _point_states(p, u)
		for g: int in range(p.tr_pt_off[u], p.tr_pt_off[u + 1]):
			var code: int = stt[0][g - p.tr_pt_off[u]]
			p.tr_pt_code[g] = code
			var a: int = b * 5 + int(stt[1][g - p.tr_pt_off[u]])
			p.place_person(scratch, c, POINT_PID + g, a, s)
			p.draw_person(scratch)
			p.finish_person(scratch)
			p.tier_person(scratch, code % NEMP, mini((code / NEMP) % NTYPE, 4), -1.0, -1.0)
			if code / (NTYPE * NEMP) < CLASS_NONE:
				_class_draw(p, scratch, code / (NTYPE * NEMP), lines, tab, "tier_inc", g)
			else:
				p.tier_income(scratch, p.income[scratch], -1.0)
			for r2: Array in rows:
				var name: String = String(r2[0])
				var st: int = int(r2[2])
				var src = p.get(name)
				var dst = p.tr_points[name]
				for k: int in st:
					dst[g * st + k] = src[scratch * st + k]
			# Why not the households-off draw's grade: it holds grades 0-2 only, so the limitation grade's deaths were missing (TO_E 23:06 (2))
			p.tr_points["health"][g] = LC.draw_grade(p, scratch, "grade0")
			phi[g] = float(p.tr_phi.get(p.pid[scratch], 1.0))
			pen[g] = float(p.tr_pension.get(p.pid[scratch], 0.0))
			kind[g] = int(p.tr_pension_kind.get(p.pid[scratch], -1))
			p.tr_phi.erase(p.pid[scratch])
			p.tr_pension.erase(p.pid[scratch])
			p.tr_pension_kind.erase(p.pid[scratch])
	p.tr_points["phi"] = phi
	p.tr_points["pension_own"] = pen
	p.tr_points["pension_kind"] = kind
	# the scratch slot is dropped: the persons layer holds the individuals only (place_persons truncates; remove_persons would touch the
	# household arrays, empty with households off)
	p.place_persons(n_ind)
	_class_factors(p, tm)


## Each unit's point target K_b by §12.5 F2's rule on the current counts (the start's, then each January's, §14.6 (1))
static func _targets(p: RefCounted) -> PackedInt64Array:
	var U: int = p.tr_units
	var by_pref: Dictionary = {}
	for u: int in U:
		var c: int = p.tr_key[u * KEY_STRIDE]
		if not by_pref.has(c):
			by_pref[c] = []
		by_pref[c].append(u)
	var kb := PackedInt64Array()
	kb.resize(U)
	for c2: int in by_pref:
		var us: Array = by_pref[c2]
		var total_n: int = 0
		for u2: int in us:
			total_n += p.tr_count[u2]
		var P: int = p.tr_k * us.size()
		var worth: float = float(total_n) / float(maxi(1, P))
		var n_one: int = 0
		var rest_n: int = 0
		for u3: int in us:
			if p.tr_count[u3] <= 0:
				kb[u3] = 0
			elif float(p.tr_count[u3]) < worth:
				kb[u3] = 1
				n_one += 1
			else:
				kb[u3] = -1
				rest_n += p.tr_count[u3]
		var share := PackedFloat64Array()
		share.resize(us.size())
		var p_rest: int = maxi(0, P - n_one)
		for j: int in us.size():
			if kb[us[j]] < 0:
				share[j] = float(p_rest) * float(p.tr_count[us[j]]) / float(maxi(1, rest_n))
		var ints: PackedInt64Array = _largest(share, p_rest)
		for j2: int in us.size():
			if kb[us[j2]] < 0:
				kb[us[j2]] = maxi(2, ints[j2])
	return kb


## The points per bundle (§12.5 F2, §12.8 item 5): each prefecture's budget P_c = K x its units; within it a bundle below one point's
## worth (count < N_c / P_c) has one point, every other max(2, its share of the rest of P_c by count, largest remainder in unit
## order); each point an integer mass, the count split over the points with the remainder from a keyed first point. Writes tr_pt_off
## (U + 1 offsets) and tr_pt_mass
## Why not K points per bundle: the aggregate variance Σ N_b² p(1 - p) / K_b is least at K_b ∝ N_b (M001 F2)
## Why not one national budget: Tottori's bundles took points by the national worth, so a prefecture's points did not follow its units
static func _point_counts(p: RefCounted) -> void:
	var U: int = p.tr_units
	var kb: PackedInt64Array = _targets(p)
	p.tr_kb = kb.duplicate()
	p.tr_pt_off = PackedInt64Array()
	p.tr_pt_off.resize(U + 1)
	p.tr_pt_mass = PackedInt64Array()
	var at: int = 0
	for u4: int in U:
		p.tr_pt_off[u4] = at
		var k: int = kb[u4]
		if k > 0:
			var base: int = p.tr_count[u4] / k
			var extra: int = p.tr_count[u4] % k
			var first: int = p.KEYED.below(k, p.seed_v, "tier_pt_mass", u4, 0, 0)
			for j3: int in k:
				p.tr_pt_mass.append(base + (1 if (j3 - first + k) % k < extra else 0))
		at += k
	p.tr_pt_off[U] = at


## The entry of a cumulative count list (counts read from off for n entries) at the real position x
static func _at_cum(arr: PackedInt64Array, off: int, n: int, x: float) -> int:
	var acc: int = 0
	for m: int in n:
		acc += arr[off + m]
		if x < float(acc):
			return m
	return n - 1


## Each point's code and single age by keyed systematic rounding over its bundle's cumulative mix and age counts: point j sits at
## M_j + u m_j of the cumulative count (M_j the masses before it, m_j its own), one u per bundle for the codes and another for the
## ages, so each code's and each age's point mass is within one point mass of its count. The age pass visits the points in a keyed
## permutation, so a point's code and its age are independent
## Why not an independent draw per point: a code's point mass then strays by the binomial's spread, K_b^(1/2) point masses
## Why not both passes in the point order: the j-th lowest code took the j-th youngest age, so the top class got the youngest points
## and the 85+ institution the oldest (M004 W5)
static func _point_states(p: RefCounted, u: int) -> Array:
	var codes := PackedInt32Array()
	var slots := PackedInt32Array()
	var uc: float = p.KEYED.u(p.seed_v, "tier_pt_mix", u, 0, 0)
	var ua: float = p.KEYED.u(p.seed_v, "tier_pt_age", u, 0, 0)
	var off: int = p.tr_mix_off[u]
	var nm: int = p.tr_mix_off[u + 1] - off
	var g0: int = p.tr_pt_off[u]
	var k: int = p.tr_pt_off[u + 1] - g0
	slots.resize(k)
	var acc: float = 0.0
	for g: int in range(g0, g0 + k):
		var m: float = float(p.tr_pt_mass[g])
		codes.append(p.tr_mix_code[off + _at_cum(p.tr_mix_n, off, nm, acc + uc * m)])
		acc += m
	var order: Array = range(k)
	order.sort_custom(func(i: int, j: int) -> bool: return p.KEYED.raw(p.seed_v, "tier_pt_perm", g0 + i, 0, 0) < p.KEYED.raw(p.seed_v, "tier_pt_perm", g0 + j, 0, 0))
	var acc2: float = 0.0
	for j2: int in order:
		var m2: float = float(p.tr_pt_mass[g0 + j2])
		slots[j2] = _at_cum(p.tr_age_counts, u * AGE_SLOTS, AGE_SLOTS, acc2 + ua * m2)
		acc2 += m2
	return [codes, slots]


## log Φ(z) for z in [PHI_ZMIN, 0] at steps of PHI_STEP, each by bisection of log p on DetMath.inv_normal (§12.8 item 3)
## Why not a Φ function of its own: it would need its own C++ twin and recorded bits; the inverse has both (DM-n)
static func _phi_table() -> PackedFloat64Array:
	var n: int = int(round(-PHI_ZMIN / PHI_STEP)) + 1
	var out := PackedFloat64Array()
	out.resize(n)
	for i: int in n:
		var z: float = PHI_ZMIN + float(i) * PHI_STEP
		var lo: float = -700.0
		var hi: float = DM.log(0.5)
		for it: int in 64:
			var mid: float = 0.5 * (lo + hi)
			if DM.inv_normal(DM.exp(mid)) < z:
				lo = mid
			else:
				hi = mid
		out[i] = 0.5 * (lo + hi)
	return out


static func _log_phi(tab: PackedFloat64Array, z: float) -> float:
	if z <= PHI_ZMIN:
		return -800.0
	var x: float = (minf(z, 0.0) - PHI_ZMIN) / PHI_STEP
	var i: int = mini(int(floor(x)), tab.size() - 2)
	return tab[i] + (tab[i + 1] - tab[i]) * (x - float(i))


## Φ(z) and its upper tail Q(z) = Φ(-z), each read from the side that keeps its relative precision
static func _phi(tab: PackedFloat64Array, z: float) -> float:
	if z <= 0.0:
		return DM.exp(_log_phi(tab, z))
	return 1.0 - DM.exp(_log_phi(tab, -z))


static func _q(tab: PackedFloat64Array, z: float) -> float:
	return _phi(tab, -z)


## A standard normal draw inside [zl, zh] at the keyed u, by inversion through the side of 0 the interval lies on
static func _trunc_normal(tab: PackedFloat64Array, zl: float, zh: float, u: float) -> float:
	var z: float
	if zl >= 0.0:
		var ql: float = _q(tab, zl)
		var qh: float = _q(tab, zh) if zh < INF else 0.0
		var t: float = qh + (1.0 - u) * (ql - qh)
		z = -DM.inv_normal(t) if t > 0.0 else zl
	else:
		var pl: float = _phi(tab, zl) if zl > -INF else 0.0
		var ph: float = _phi(tab, zh) if zh < INF else 1.0
		var t2: float = pl + u * (ph - pl)
		if t2 <= 0.0:
			z = zl
		elif t2 <= 0.5:
			z = DM.inv_normal(t2)
		else:
			z = -DM.inv_normal(1.0 - t2)
	return clampf(z, zl, zh)


## The generator's income law for adults of band b, sex s, employment e (people.wage() in closed form, §12.8 item 3): a list of
## [weight, kind, a, b] with kind 0 a lognormal (mu a, sigma b), 1 a uniform on [a, b], 2 an atom at a. The ages within the band by the
## cohort's shape; education by the generator's shares at that age; the skill term at its mean (T)
static func _income_law(p: RefCounted, b: int, s: int, e: int, age_in_band: PackedFloat64Array) -> Array:
	var sp: Dictionary = p.spec
	var out: Array = []
	if e == p.EMP_NONE and b * 5 < p.PENSION_AGE:
		return [[1.0, 2, 0.0, 0.0]]
	if e == p.EMP_STUDENT:
		return [[1.0, 2, float(sp["student_income_man_yen"]["value"]), 0.0]]
	var sigma: float = float(sp["wage_sigma"]["value"])
	var pr: Dictionary = sp["pension_rule"]["value"]
	var top: int = p.AGES if b == BANDS - 1 else b * 5 + 5
	var wsum: float = 0.0
	for a0: int in range(b * 5, top):
		wsum += age_in_band[a0 * 2 + s]
	for a: int in range(b * 5, top):
		var wa: float = age_in_band[a * 2 + s] / wsum if wsum > 0.0 else 1.0 / float(top - b * 5)
		if wa <= 0.0:
			continue
		if a >= p.PENSION_AGE and (e == p.EMP_RETIRED or e == p.EMP_NONE):
			for r: Array in _pension_law(p, a, s):
				out.append([wa * float(r[0]), 2, 0.0, 0.0] if int(r[3]) == PEN_NONE else [wa * float(r[0]), 1, float(r[1]), float(r[2])])
			continue
		if e == p.EMP_RETIRED:
			var idx: float = float(p.pension["new"]) if a <= int(pr["new_until_age"]) else float(p.pension["old"])
			var p0: float = float(sp["pension_man_yen"]["value"]) * idx
			out.append([wa, 1, 0.7 * p0, 1.3 * p0])
			continue
		for d: int in p.EDUCATION.size():
			var sh: float = _edu_share(p, a, d)
			if sh <= 0.0:
				continue
			var lm: float = DM.log(_component_m(p, a, s, e, d))
			if a < p.PENSION_AGE:
				out.append([wa * sh, 0, lm, sigma])
				continue
			for r2: Array in _pension_law(p, a, s):
				out.append([wa * sh * float(r2[0]), 3, lm, sigma, 0.5 * (float(r2[1]) + float(r2[2]))])
	return out


## The public pension's law at 65+ for age a and sex s (§12.9 M1, R70): rows [weight, lo, hi, kind], one per monthly amount class (万円,
## at R68's index for the age) of each kind's 25-year+ and short-record tables, the none share as one row at 0
static func _pension_law(p: RefCounted, a: int, s: int) -> Array:
	var pe: Dictionary = _v(p, "pension_entitlement")
	var sx: String = "male" if s == p.MALE else "female"
	var bi: int = clampi((a - p.PENSION_AGE) / 5, 0, 3)
	var none: float = float(pe["none_share"][sx][bi])
	var basic: float = float(pe["basic_only_share"][sx][bi])
	var sb: float = float(pe["short_record_share"][sx]["basic_only"])
	var se: float = float(pe["short_record_share"][sx]["employee"])
	var idx: float = p.pension_index_at(a)
	var out: Array = [[none, 0.0, 0.0, PEN_NONE]]
	for row: Array in [[PEN_BASIC, "basic_only_classes", basic * (1.0 - sb)], [PEN_BASIC_SHORT, "basic_only_short_classes", basic * sb],
			[PEN_EMPLOYEE, "employee_classes", (1.0 - basic) * (1.0 - se)], [PEN_EMPLOYEE_SHORT, "employee_short_classes", (1.0 - basic) * se]]:
		var t: Dictionary = pe[String(row[1])][sx]
		var c: Array = t["counts"]
		var n: float = 0.0
		for x: Variant in c:
			n += float(x)
		for k: int in c.size():
			var hi: float = float(k + 1) if k < c.size() - 1 else float(k) + float(t["top_width"])
			out.append([(1.0 - none) * float(row[2]) * float(c[k]) / n, float(k) * idx, hi * idx, int(row[0])])
	return out


## The persons layer's education share at single age a (complete at 22)
static func _edu_share(p: RefCounted, a: int, d: int) -> float:
	if a < 22:
		return 1.0 if d == 0 else 0.0
	var eb: String = "22_34" if a < 35 else ("35_54" if a < 55 else "55_plus")
	return float(p.spec["education_shares_by_age"][eb][p.EDUCATION[d]])


## A lognormal component's median pay: wage()'s terms at single age a, sex s, status e, education d and the skill's mean at them, the
## cash ratio (§12.9 M2) included
static func _component_m(p: RefCounted, a: int, s: int, e: int, d: int) -> float:
	var sp: Dictionary = p.spec
	var w: Dictionary = sp["wage_regular_man_yen"]
	var base: float = float(w["male"]) if s == p.MALE else float(w["female"])
	base *= float(sp["wage_age_curve"][str(clampi(a / 10 * 10, 20, 70))])
	base *= p.wage_index
	if e == p.EMP_NONREGULAR:
		base *= float(sp["non_regular_wage_factor"]["value"])
	elif e == p.EMP_UNEMPLOYED:
		base *= float(sp["unemployment_benefit_factor"]["value"])
	if e == p.EMP_REGULAR or e == p.EMP_NONREGULAR:
		var cr: Dictionary = _v(p, "wage_cash_ratio")
		base *= float(cr["regular" if e == p.EMP_REGULAR else "non_regular"]["male" if s == p.MALE else "female"][0 if a < 20 else mini(11, (a - 20) / 5 + 1)])
	var skill: float = clampf(20.0 + 15.0 * d + 0.8 * maxf(0.0, a - 22), 0.0, 100.0)
	return base * float(sp["wage_education_factor"][p.EDUCATION[d]]) * (1.0 + 0.004 * (skill - 50.0))


## A worker's or the unemployed's education given its class (§12.10 V1b): P(d | age, sex, status, class) ∝ the share of d x the mass
## of d's component inside the class's interval, keyed; the person's skill and pay then follow from it
## Why not the persons layer's draw: it is independent of the class, so the top 0.01% held the population's education mix and sat
## low in the fitted tail (V1's first run)
static func _edu_given_class(p: RefCounted, i: int, lo: float, hi: float, tab: PackedFloat64Array, tag: String, key: int) -> void:
	var a: int = p.age[i]
	if a < 22:
		return
	var sigma: float = float(p.spec["wage_sigma"]["value"])
	var wts := PackedFloat64Array()
	var tot: float = 0.0
	var rows: Array = _pension_law(p, a, p.sex[i]) if a >= p.PENSION_AGE else [[1.0, 0.0, 0.0, PEN_NONE]]
	for d: int in p.EDUCATION.size():
		var lm: float = DM.log(_component_m(p, a, p.sex[i], p.employment[i], d))
		var m: float = 0.0
		for r: Array in rows:
			var cm: float = 0.5 * (float(r[1]) + float(r[2]))
			m += float(r[0]) * _shifted_mass(tab, lm, sigma, lo - cm, hi - cm)
		wts.append(_edu_share(p, a, d) * m)
		tot += wts[d]
	if tot <= 0.0:
		return
	var x: float = p.KEYED.u(p.seed_v, tag, key, 1, 0) * tot
	var acc: float = 0.0
	for d2: int in wts.size():
		acc += wts[d2]
		if x < acc or d2 == wts.size() - 1:
			p.tier_education(i, d2)
			return


## P(income > line) under a law of _income_law
static func _above(tab: PackedFloat64Array, law: Array, line: float) -> float:
	var s: float = 0.0
	for c: Array in law:
		var w: float = float(c[0])
		match int(c[1]):
			0:
				s += w * _q(tab, (DM.log(line) - float(c[2])) / float(c[3]))
			1:
				s += w * clampf((float(c[3]) - line) / (float(c[3]) - float(c[2])), 0.0, 1.0)
			3:
				var t: float = line - float(c[4])
				s += w * (_q(tab, (DM.log(t) - float(c[2])) / float(c[3])) if t > 0.0 else 1.0)
			_:
				s += w * (1.0 if float(c[2]) > line else 0.0)
	return s


## The national class lines (monthly 万円): each the income above which R67a's cumulative share of the adults lies, by bisection on
## the log line over the adults' laws weighted by their national counts. Returns [lines (top 0.01% .. bottom 50%'s upper edge)]
static func _class_lines(tab: PackedFloat64Array, laws: Dictionary, mass: Dictionary, adult_shares: Array) -> PackedFloat64Array:
	var adults: float = 0.0
	for k: Variant in mass:
		adults += float(mass[k])
	var lines := PackedFloat64Array()
	var cum: float = 0.0
	for c: int in adult_shares.size() - 1:
		cum += float(adult_shares[c])
		var lo: float = DM.log(1e-3)
		var hi: float = DM.log(1e7)
		for it: int in 80:
			var mid: float = 0.5 * (lo + hi)
			var g: float = 0.0
			for k2: Variant in mass:
				g += float(mass[k2]) * _above(tab, laws[k2], DM.exp(mid))
			if g > cum * adults:
				lo = mid
			else:
				hi = mid
		lines.append(DM.exp(0.5 * (lo + hi)))
	return lines


## P(class | the law): the mass between consecutive lines, the top class above the first, the bottom class below the last
static func _class_probs(tab: PackedFloat64Array, law: Array, lines: PackedFloat64Array) -> PackedFloat64Array:
	var out := PackedFloat64Array()
	var prev: float = 0.0
	for c: int in lines.size():
		var a: float = _above(tab, law, lines[c])
		out.append(maxf(0.0, a - prev))
		prev = a
	out.append(maxf(0.0, 1.0 - prev))
	return out


## A person's income drawn inside class k's interval given its other states (§12.8 item 3): a worker's or the unemployed's wage
## normal term by inversion inside the interval, a pensioner's uniform inside it; the student's and the outsider's fixed incomes
## stand. The person's own level carries the drawn term (tier_income, §12.8 10.1), so wage() gives the same income
## Why not F^-1 at a keyed quantile of the drawn points (T1): the class then held whatever the points' own incomes were, so the
## class was not joint with employment and age as the generator makes it (M003 T2)
static func _class_draw(p: RefCounted, i: int, k: int, lines: PackedFloat64Array, tab: PackedFloat64Array, tag: String, key: int) -> void:
	var hi: float = INF if k == 0 else lines[k - 1]
	var lo: float = lines[k] if k < lines.size() else 0.0
	var e: int = p.employment[i]
	var a: int = p.age[i]
	if a >= p.PENSION_AGE and (e == p.EMP_RETIRED or e == p.EMP_NONE):
		_pension_draw(p, i, lo, hi, tag, key)
		return
	if (e == p.EMP_REGULAR or e == p.EMP_NONREGULAR or e == p.EMP_UNEMPLOYED) and p.income[i] > 0.0:
		_edu_given_class(p, i, lo, hi, tab, tag, key)
	var w: float = p.income[i]
	var u: float = p.KEYED.u(p.seed_v, tag, key, 0, 0)
	if (e == p.EMP_REGULAR or e == p.EMP_NONREGULAR or e == p.EMP_UNEMPLOYED) and w > 0.0:
		var sigma: float = float(p.spec["wage_sigma"]["value"])
		var z0: float = p.normal("wage", i)
		var c: float = 0.0
		if a >= p.PENSION_AGE:
			# a worker of 65+: its pension's class row given the class, by each row's mass of pay + the row's midpoint inside it, then
			# the pay inside the class less the pension (the law's form, so the class holds)
			var rows: Array = _pension_law(p, a, p.sex[i])
			var wts := PackedFloat64Array()
			var tot: float = 0.0
			for r: Array in rows:
				var cm: float = 0.5 * (float(r[1]) + float(r[2]))
				wts.append(float(r[0]) * _shifted_mass(tab, DM.log(w) - sigma * z0, sigma, lo - cm, hi - cm))
				tot += wts[wts.size() - 1]
			if tot > 0.0:
				var x: float = p.KEYED.u(p.seed_v, tag, key, 2, 0) * tot
				var acc: float = 0.0
				for j: int in rows.size():
					acc += wts[j]
					if x < acc or j == rows.size() - 1:
						c = 0.5 * (float(rows[j][1]) + float(rows[j][2]))
						p.tier_pension(i, c, int(rows[j][3]))
						break
		var lo2: float = lo - c
		var hi2: float = hi - c
		var zl: float = z0 + DM.log(lo2 / w) / sigma if lo2 > 0.0 else -INF
		var zh: float = z0 + DM.log(hi2 / w) / sigma if hi2 < INF else INF
		var f: float = DM.exp(sigma * (_trunc_normal(tab, zl, zh, u) - z0))
		p.tier_income(i, w * f + c, -1.0)
	elif e == p.EMP_RETIRED and w > 0.0:
		var p0: float = w / (0.7 + 0.6 * p.u("pension", i))
		var ul: float = clampf((lo / p0 - 0.7) / 0.6, 0.0, 1.0)
		var uh: float = clampf((hi / p0 - 0.7) / 0.6, 0.0, 1.0) if hi < INF else 1.0
		p.tier_income(i, p0 * (0.7 + 0.6 * (ul + u * (uh - ul))), -1.0)
	else:
		p.tier_income(i, w, -1.0)


## A lognormal's mass inside (lo, hi) (lo <= 0 is the whole lower side)
static func _shifted_mass(tab: PackedFloat64Array, lm: float, sigma: float, lo: float, hi: float) -> float:
	if hi <= 0.0:
		return 0.0
	var ql: float = _q(tab, (DM.log(lo) - lm) / sigma) if lo > 0.0 else 1.0
	var qh: float = _q(tab, (DM.log(hi) - lm) / sigma) if hi < INF else 0.0
	return maxf(0.0, ql - qh)


## A pensioner's or an outsider's pension at 65+ given its class (§12.9 M1): a row of the law by its mass inside the class's interval
## (the none row's atom at 0 in the bottom class), then uniform inside the row's part of it, keyed; the kind and the amount kept
static func _pension_draw(p: RefCounted, i: int, lo: float, hi: float, tag: String, key: int) -> void:
	var rows: Array = _pension_law(p, p.age[i], p.sex[i])
	var wts := PackedFloat64Array()
	var tot: float = 0.0
	for r: Array in rows:
		var m: float = 0.0
		if int(r[3]) == PEN_NONE:
			m = float(r[0]) if lo <= 0.0 else 0.0
		else:
			m = float(r[0]) * maxf(0.0, minf(hi, float(r[2])) - maxf(lo, float(r[1]))) / (float(r[2]) - float(r[1]))
		wts.append(m)
		tot += m
	if tot <= 0.0:
		p.tier_income(i, p.income[i], -1.0)
		return
	var x: float = p.KEYED.u(p.seed_v, tag, key, 0, 0) * tot
	var acc: float = 0.0
	for j: int in rows.size():
		acc += wts[j]
		if x < acc or j == rows.size() - 1:
			var amount: float = 0.0
			if int(rows[j][3]) != PEN_NONE:
				var a0: float = maxf(lo, float(rows[j][1]))
				amount = a0 + p.KEYED.u(p.seed_v, tag, key, 3, 0) * (minf(hi, float(rows[j][2])) - a0)
			p.tier_pension(i, amount, int(rows[j][3]))
			p.tier_income(i, amount, -1.0)
			return


## The income tail's map (§12.8 item 9, 10.2): the generator's national survival S_gen on a log grid from its median up (the closed
## form of item 3 over the adults' laws, the five class lines added as exact knots with their shares), and the target: the generalized
## Pareto interpolation through the median and the cash lines (the PM's option A, _gpi_fit). Returns what _tail_of reads
## Why not log-linear segments between the lines (item 9's first build): they set the class means before any run, the middle 40% 25-31%
## low, and made the density jump x2.3-2.6 at the 10% line (M004 W2, W3)
static func _tail_map(p: RefCounted, tab: PackedFloat64Array, laws: Dictionary, mass: Dictionary, lines: PackedFloat64Array, adult_shares: Array) -> Dictionary:
	var tl: Dictionary = _v(p, "income_tail")
	var adults: float = 0.0
	for k: Variant in mass:
		adults += float(mass[k])
	var med: float = lines[lines.size() - 1]
	var knots: Array = []
	var cum: float = 0.0
	for c: int in lines.size():
		cum += float(adult_shares[c])
		knots.append([DM.log(lines[c]), DM.log(cum)])
	var lo: float = DM.log(med)
	var hi: float = DM.log(1e5)
	for i: int in TAIL_GRID:
		var ly: float = lo + (hi - lo) * float(i) / float(TAIL_GRID - 1)
		var g: float = 0.0
		for k2: Variant in mass:
			g += float(mass[k2]) * _above(tab, laws[k2], DM.exp(ly))
		if i > 0 and g > 0.0:
			knots.append([ly, DM.log(g / adults)])
	knots.sort_custom(func(a: Array, b: Array) -> bool: return float(a[0]) < float(b[0]))
	var gy := PackedFloat64Array()
	var gs := PackedFloat64Array()
	for q: Array in knots:
		if float(q[0]) >= lo - 1e-12:
			gy.append(float(q[0]))
			gs.append(float(q[1]))
	var gpi: Dictionary = _gpi_fit(med, _below_mean(tab, laws, mass, med), tl)
	var ty := PackedFloat64Array([lo])
	for p0: float in [0.9, 0.99, 0.999, 0.9999]:
		ty.append(DM.log(_gpi_q(gpi, p0)))
	return {"gy": gy, "gs": gs, "gpi": gpi, "ty": ty, "median": med}


## An income above the generator's median mapped by its national rank: log S_gen read off the grid (linear in log y, the last slope
## beyond it), then the target's quantile at that rank
static func _tail_of(tm: Dictionary, y: float) -> float:
	if y <= float(tm["median"]):
		return y
	var gy: PackedFloat64Array = tm["gy"]
	var gs: PackedFloat64Array = tm["gs"]
	var ly: float = DM.log(y)
	var at: int = clampi(gy.bsearch(ly) - 1, 0, gy.size() - 2)
	var ls: float = gs[at] + (gs[at + 1] - gs[at]) * (ly - gy[at]) / (gy[at + 1] - gy[at])
	return maxf(float(tm["median"]), _gpi_q(tm["gpi"], maxf(0.5, 1.0 - DM.exp(ls))))


## The generator's bottom half's income per adult (closed form over the adults' laws): Σ mass E[y; y ≤ the median] ÷ the adults, the
## lognormal's partial mean through Φ (shifted by a pension, §12.9 M1), the uniform's and the atoms' exactly
static func _below_mean(tab: PackedFloat64Array, laws: Dictionary, mass: Dictionary, med: float) -> float:
	var tot: float = 0.0
	var adults: float = 0.0
	for k: Variant in mass:
		adults += float(mass[k])
		var s: float = 0.0
		for c: Array in laws[k]:
			var w: float = float(c[0])
			match int(c[1]):
				0:
					var mu: float = float(c[2])
					var sg: float = float(c[3])
					s += w * DM.exp(mu + 0.5 * sg * sg) * _phi(tab, (DM.log(med) - mu - sg * sg) / sg)
				1:
					var a: float = float(c[2])
					var b: float = float(c[3])
					if med >= b:
						s += w * 0.5 * (a + b)
					elif med > a:
						s += w * (med * med - a * a) / (2.0 * (b - a))
				3:
					var mu3: float = float(c[2])
					var sg3: float = float(c[3])
					var t3: float = med - float(c[4])
					if t3 > 0.0:
						s += w * (DM.exp(mu3 + 0.5 * sg3 * sg3) * _phi(tab, (DM.log(t3) - mu3 - sg3 * sg3) / sg3) + float(c[4]) * _phi(tab, (DM.log(t3) - mu3) / sg3))
				_:
					if float(c[2]) <= med:
						s += w * float(c[2])
		tot += float(mass[k]) * s
	return tot / adults


## A quintic on [0, h] from (f, f', f'') at both ends: its six coefficients in u (the closed form of the Hermite conditions)
static func _quintic(h: float, f0: float, f1: float, d0: float, d1: float, s0: float, s1: float) -> PackedFloat64Array:
	var c2: float = 0.5 * s0
	var a: float = f1 - (f0 + d0 * h + c2 * h * h)
	var bd: float = d1 - (d0 + 2.0 * c2 * h)
	var cc: float = s1 - 2.0 * c2
	return PackedFloat64Array([f0, d0, c2, (10.0 * a - 4.0 * bd * h + 0.5 * cc * h * h) / (h * h * h),
		(-15.0 * a + 7.0 * bd * h - cc * h * h) / (h * h * h * h), (6.0 * a - 3.0 * bd * h + 0.5 * cc * h * h) / (h * h * h * h * h)])


static func _third(c: PackedFloat64Array, u: float) -> float:
	return 6.0 * c[3] + 24.0 * c[4] * u + 60.0 * c[5] * u * u


## The generalized Pareto interpolation (§12.8 10.2, BFP 2017) through the knots [x, φ, φ'] (x = -log(1 - p), φ = -log I): φ'' at
## each knot chosen so φ''' is continuous at the interior knots and 0 at both ends (a 3 x 3 solve for the three knots), one quintic a
## segment. Returns the segments' coefficients
static func _gpi_spline(kn: Array) -> Array:
	var n: int = kn.size()
	var m: Array = []
	var r := PackedFloat64Array()
	for i: int in n:
		var row := PackedFloat64Array()
		row.resize(n)
		m.append(row)
		r.append(0.0)
	var lin := func(i: int, at_end: bool) -> PackedFloat64Array:
		var h: float = float(kn[i + 1][0]) - float(kn[i][0])
		var u: float = h if at_end else 0.0
		var base: float = _third(_quintic(h, kn[i][1], kn[i + 1][1], kn[i][2], kn[i + 1][2], 0.0, 0.0), u)
		var a: float = _third(_quintic(h, kn[i][1], kn[i + 1][1], kn[i][2], kn[i + 1][2], 1.0, 0.0), u) - base
		var b: float = _third(_quintic(h, kn[i][1], kn[i + 1][1], kn[i][2], kn[i + 1][2], 0.0, 1.0), u) - base
		return PackedFloat64Array([a, b, base])
	var e0: PackedFloat64Array = lin.call(0, false)
	m[0][0] = e0[0]
	m[0][1] = e0[1]
	r[0] = -e0[2]
	for k: int in range(1, n - 1):
		var l1: PackedFloat64Array = lin.call(k - 1, true)
		var l2: PackedFloat64Array = lin.call(k, false)
		m[k][k - 1] += l1[0]
		m[k][k] += l1[1] - l2[0]
		m[k][k + 1] -= l2[1]
		r[k] = l2[2] - l1[2]
	var en: PackedFloat64Array = lin.call(n - 2, true)
	m[n - 1][n - 2] = en[0]
	m[n - 1][n - 1] = en[1]
	r[n - 1] = -en[2]
	var s: PackedFloat64Array = _solve(m, r)
	var out: Array = []
	for i2: int in n - 1:
		out.append(_quintic(float(kn[i2 + 1][0]) - float(kn[i2][0]), kn[i2][1], kn[i2 + 1][1], kn[i2][2], kn[i2 + 1][2], s[i2], s[i2 + 1]))
	return out


## A small dense solve by Gaussian elimination with partial pivoting (rows in index order on ties)
static func _solve(m: Array, r: PackedFloat64Array) -> PackedFloat64Array:
	var n: int = r.size()
	var a: Array = []
	for i: int in n:
		a.append((m[i] as PackedFloat64Array).duplicate())
	var b := r.duplicate()
	for c: int in n:
		var piv: int = c
		for i2: int in range(c + 1, n):
			if absf(a[i2][c]) > absf(a[piv][c]):
				piv = i2
		var t = a[c]
		a[c] = a[piv]
		a[piv] = t
		var tb: float = b[c]
		b[c] = b[piv]
		b[piv] = tb
		for i3: int in range(c + 1, n):
			var f: float = a[i3][c] / a[c][c]
			for j: int in range(c, n):
				a[i3][j] -= f * a[c][j]
			b[i3] -= f * b[c]
	var x := PackedFloat64Array()
	x.resize(n)
	for i4: int in range(n - 1, -1, -1):
		var acc: float = b[i4]
		for j2: int in range(i4 + 1, n):
			acc -= a[i4][j2] * x[j2]
		x[i4] = acc / a[i4][i4]
	return x


## Q at rank p from the interpolation: below the last knot φ' e^(-φ) e^x on its segment; above it the Pareto of the last knot's b
static func _gpi_q(g: Dictionary, p: float) -> float:
	var kn: Array = g["knots"]
	var last: Array = kn[kn.size() - 1]
	var x: float = -DM.log(1.0 - p)
	if x >= float(last[0]):
		var b: float = 1.0 / float(last[2])
		var alpha: float = b / (b - 1.0)
		var q_last: float = float(last[2]) * DM.exp(-float(last[1])) * DM.exp(float(last[0]))
		return q_last * DM.exp((x - float(last[0])) / alpha)
	var seg: Array = g["segments"]
	var i: int = 0
	while i < kn.size() - 2 and x > float(kn[i + 1][0]):
		i += 1
	var c: PackedFloat64Array = seg[i]
	var u: float = x - float(kn[i][0])
	var f: float = c[0] + u * (c[1] + u * (c[2] + u * (c[3] + u * (c[4] + u * c[5]))))
	var d: float = c[1] + u * (2.0 * c[2] + u * (3.0 * c[3] + u * (4.0 * c[4] + u * 5.0 * c[5])))
	return d * DM.exp(x - f)


## The interpolation's knots for a cash mean per adult mu (monthly 万円): the median at its own threshold with I = mu - B, the 1% and
## the 0.1% at their thresholds and shares
static func _gpi_knots(med: float, b_half: float, mu: float, q1: float, s1: float, q01: float, s01: float) -> Array:
	var out: Array = []
	for row: Array in [[0.5, med, mu - b_half], [0.99, q1, s1 * mu], [0.999, q01, s01 * mu]]:
		var p: float = float(row[0])
		var i: float = float(row[2])
		out.append([-DM.log(1.0 - p), -DM.log(i), (1.0 - p) * float(row[1]) / i])
	return out


## The interpolation solved (§12.8 10.2, the PM's option A): mu by bisection so Q(0.9) is the 10% line, the knots and segments at it
static func _gpi_fit(med: float, b_half: float, tl: Dictionary) -> Dictionary:
	var lines: Array = tl["lines_yen_year"]
	var sh: Dictionary = tl["cash_income_shares_pct"]
	var q10: float = float(lines[0]) / 12.0 / 1e4
	var q1: float = float(lines[1]) / 12.0 / 1e4
	var q01: float = float(lines[2]) / 12.0 / 1e4
	var s1: float = float(sh["top1"]) / 100.0
	var s01: float = float(sh["top0_1"]) / 100.0
	# mu inside the window where the top 1% less 0.1%'s mean (s1 - s01) mu ÷ 0.009 lies between its two lines
	var lo: float = 0.009 * q1 / (s1 - s01)
	var hi: float = 0.009 * q01 / (s1 - s01)
	var g: Dictionary = {}
	for it: int in 100:
		var mid: float = 0.5 * (lo + hi)
		var kn: Array = _gpi_knots(med, b_half, mid, q1, s1, q01, s01)
		g = {"knots": kn, "segments": _gpi_spline(kn), "mu": mid}
		if _gpi_q(g, 0.9) < q10:
			lo = mid
		else:
			hi = mid
	return g


## The tail applied (§12.8 item 9): each adult point's and individual's income above the median mapped by its rank, the person's own
## level carrying the ratio (§12.8 10.1), the expected income reset to the income; an individual's assets ten years of its income (T). The
## would-be class factors (published ÷ the mapped class mean) are computed and reported, not applied
## Why not applying them (item 3 did): a constant per class opens an empty gap at every class line, and at the median line it made the
## share below half the median read 0.187 or 0.285 by seed (runs/t1s_g_b2f71cb5)
static func _class_factors(p: RefCounted, tm: Dictionary) -> void:
	var pub: Array = (_v(p, "classes") as Dictionary)["mean_income_yen_year"]
	var inc: PackedFloat64Array = p.tr_points["income"]
	var phi: PackedFloat64Array = p.tr_points["phi"]
	var pen: PackedFloat64Array = p.tr_points["pension_own"]
	var qi: PackedFloat64Array = p.tr_points["q_income"]
	var emp: PackedInt32Array = p.tr_points["employment"]
	var ages: PackedInt32Array = p.tr_points["age"]
	var s := PackedFloat64Array()
	s.resize(CLASS_NONE)
	var m := PackedFloat64Array()
	m.resize(CLASS_NONE)
	for g: int in p.tr_pt_code.size():
		var k: int = p.tr_pt_code[g] / (NTYPE * NEMP)
		if k < CLASS_NONE:
			var y: float = _tail_of(tm, inc[g])
			var pg: float = pen[g] * p.pension_index_at(ages[g]) if ages[g] >= p.PENSION_AGE else 0.0
			if (emp[g] == p.EMP_REGULAR or emp[g] == p.EMP_NONREGULAR or emp[g] == p.EMP_UNEMPLOYED) and inc[g] > pg:
				phi[g] *= (y - pg) / (inc[g] - pg)
			elif (emp[g] == p.EMP_RETIRED or (emp[g] == p.EMP_NONE and ages[g] >= p.PENSION_AGE)) and inc[g] > 0.0:
				pen[g] *= y / inc[g]
			inc[g] = y
			s[k] += inc[g] * float(p.tr_pt_mass[g])
			m[k] += float(p.tr_pt_mass[g])
		qi[g] = inc[g]
	for i: int in p.n:
		var k2: int = p.tr_indiv_code[i] / (NTYPE * NEMP)
		var x: float = _tail_of(tm, p.income[i])
		p.tier_income(i, x, x * 120.0)
		s[k2] += x
		m[k2] += 1.0
	var c := PackedFloat64Array()
	c.resize(CLASS_NONE)
	for k3: int in CLASS_NONE:
		c[k3] = float(pub[k3]) / 12.0 / 1e4 / (s[k3] / m[k3]) if s[k3] > 0.0 else 1.0
	p.tr_margins["class_factor"] = c
	p.tr_margins["tail_lines"] = tm["ty"]
	p.tr_margins["gpi"] = tm["gpi"]


## The survivors' pensions and 生活保護 at the start (§12.9 M1b, M1c), on the points after the tail map (the individuals are the top
## 0.01%, none of them eligible):
## - survivors: the women of 65+ outside the couple types in the bottom class with a basic-only or short-record kind, each point drawn
##   keyed at its band's share of the eligible mass that meets R72's recipients less those already in R70's 厚生-only kind; a point whose
##   income would cross the median line is skipped and counted; the paid mean joins its own pension (so it persists, 10.1)
## - 生活保護: the 65+ one-person households lowest income first by mass up to R72's elderly protected count, brought to the minimum
static func _transfers(p: RefCounted) -> void:
	var inc: PackedFloat64Array = p.tr_points["income"]
	var qi: PackedFloat64Array = p.tr_points["q_income"]
	var ages: PackedInt32Array = p.tr_points["age"]
	var sexes: PackedInt32Array = p.tr_points["sex"]
	var pen: PackedFloat64Array = p.tr_points["pension_own"]
	var kind: PackedInt32Array = p.tr_points["pension_kind"]
	var n_pts: int = p.tr_pt_code.size()
	var med: float = DM.exp(float(p.tr_margins["tail_lines"][0]))
	var sv: Dictionary = _v(p, "survivors")
	var surv := PackedFloat64Array()
	surv.resize(n_pts)
	var elig := PackedFloat64Array([0, 0, 0, 0])
	var recip := PackedFloat64Array([0, 0, 0, 0])
	var ok := PackedByteArray()
	ok.resize(n_pts)
	for g: int in n_pts:
		if sexes[g] == p.MALE or ages[g] < p.PENSION_AGE:
			continue
		var bi: int = clampi((ages[g] - p.PENSION_AGE) / 5, 0, 3)
		if kind[g] != PEN_NONE:
			recip[bi] += float(p.tr_pt_mass[g])
		var t: int = (p.tr_pt_code[g] / NEMP) % NTYPE
		var k: int = p.tr_pt_code[g] / (NTYPE * NEMP)
		if t != 1 and t != 2 and k == CLASS_NONE - 1 and (kind[g] == PEN_BASIC or kind[g] == PEN_BASIC_SHORT or kind[g] == PEN_EMPLOYEE_SHORT):
			ok[g] = 1
			elig[bi] += float(p.tr_pt_mass[g])
	var q := PackedFloat64Array([0, 0, 0, 0])
	var want := PackedFloat64Array([0, 0, 0, 0])
	for bi2: int in 4:
		want[bi2] = maxf(0.0, float(sv["right_holders"][bi2]) * float(sv["recipient_ratio"]) - recip[bi2] * float(sv["women_kosei_only_share"][bi2]))
		q[bi2] = clampf(want[bi2] / elig[bi2], 0.0, 1.0) if elig[bi2] > 0.0 else 0.0
	var drawn := PackedFloat64Array([0, 0, 0, 0])
	var skipped: float = 0.0
	for g2: int in n_pts:
		if ok[g2] == 0:
			continue
		var bi3: int = clampi((ages[g2] - p.PENSION_AGE) / 5, 0, 3)
		if p.KEYED.u(p.seed_v, "tier_surv", g2, 0, 0) >= q[bi3]:
			continue
		var idx: float = p.pension_index_at(ages[g2])
		var amt: float = float(sv["mean_yen"]) / 1e4 * idx
		if inc[g2] + amt >= med:
			skipped += float(p.tr_pt_mass[g2])
			continue
		surv[g2] = amt / idx
		pen[g2] += amt / idx
		inc[g2] += amt
		qi[g2] = inc[g2]
		drawn[bi3] += float(p.tr_pt_mass[g2])
	p.tr_points["survivor"] = surv
	var pr: Dictionary = _v(p, "protection")
	var floor_m: float = float(pr["minimum_yen"]) / 1e4
	var cand: Array = []
	for g3: int in n_pts:
		if ages[g3] >= p.PENSION_AGE and (p.tr_pt_code[g3] / NEMP) % NTYPE == 0 and inc[g3] < floor_m:
			cand.append([inc[g3], g3])
	cand.sort_custom(func(x: Array, y: Array) -> bool: return float(x[0]) < float(y[0]) if float(x[0]) != float(y[0]) else int(x[1]) < int(y[1]))
	var prot := PackedFloat64Array()
	prot.resize(n_pts)
	var taken: float = 0.0
	for c: Array in cand:
		if taken >= float(pr["elderly_households"]):
			break
		var g4: int = int(c[1])
		prot[g4] = floor_m - inc[g4]
		inc[g4] = floor_m
		qi[g4] = inc[g4]
		taken += float(p.tr_pt_mass[g4])
	p.tr_points["protection"] = prot
	p.tr_margins["survivors"] = {"want": want, "drawn": drawn, "skipped": skipped}
	p.tr_margins["protection"] = {"want": float(pr["elderly_households"]), "taken": taken, "below": cand.size()}


## The registry rows a point carries: every per-person array of people.fields() but the links and the groups (T4)
static func point_rows(p: RefCounted) -> Array:
	var out: Array = []
	for f: Array in p.fields():
		if int(f[2]) > 0 and not POINT_SKIP.has(String(f[0])) and String(f[1]) != "i64":
			out.append([String(f[0]), String(f[1]), int(f[2])])
	return out


## The household-bundles (§4.1, §11.3 b, §12.8 item 4): keyed prefecture x type x householder band x size class x class, an integer
## count of households and an integer composition by person-bundle and role. Per prefecture x type: each mix entry's persons split
## over the roles (head, partner, child, parent, other) by keyed systematic rounding of the D role shares; in the couple types the
## partners set equal to the heads; every head one household at its own band and class; the partners placed at a householder band by
## the age-gap kernel, the children at b + 6, the parents at b - 6, the others at b (T), each member's class in proportion to the heads'
## there; then per household-bundle the size classes from the D shares, kept to the type's allowed sizes and adjusted so Σ size x
## households = the persons, and the members split over the sizes by controlled rounding. The households the persons cannot fill to
## the type's minimum size go to tr_margins["hh_unfilled"]
## Why not round(persons / size) per household-bundle (T1): heads were not households, a role with share 0 could get a person, and a
## couple-only household could hold one person (M003 T3)
static func _households(p: RefCounted) -> void:
	var role_tbs: Dictionary = _v(p, "role_by_type_band_sex")
	var size_th: Dictionary = _v(p, "size_by_type_hband")
	p.tr_hh = {}
	p.tr_nh_hh = {}
	p.tr_margins["hh_unfilled"] = 0
	p.tr_margins["hh_unfilled_t"] = {}
	p.tr_margins["hh_childless"] = 0
	p.tr_margins["hh_partner_short"] = 0
	p.tr_margins["head_gap"] = {}
	var targets: Dictionary = _head_targets(p)
	var lt: Dictionary = _l_other(p)
	p.tr_margins["lc_clip"] = {}
	var groups: Dictionary = {}   # "c|t" -> [[u, band, sex, class, n], ...] in unit and mix order
	for u: int in p.tr_units:
		var c: int = p.tr_key[u * KEY_STRIDE]
		for mi: int in range(p.tr_mix_off[u], p.tr_mix_off[u + 1]):
			var n: int = p.tr_mix_n[mi]
			if n <= 0:
				continue
			var t: int = (p.tr_mix_code[mi] / NEMP) % NTYPE
			var gk: String = "%02d|%d" % [c, t]
			if not groups.has(gk):
				groups[gk] = []
			groups[gk].append([u, p.tr_key[u * KEY_STRIDE + 1], p.tr_key[u * KEY_STRIDE + 2], p.tr_mix_code[mi] / (NTYPE * NEMP), n, mi])
	var gkeys: Array = groups.keys()
	gkeys.sort()
	for gk2: String in gkeys:
		var parts: PackedStringArray = gk2.split("|")
		_household_group(p, int(parts[0]), int(parts[1]), groups[gk2], role_tbs, size_th, int(targets.get(gk2, -1)), lt)


## One prefecture x type (see _households)
static func _household_group(p: RefCounted, c: int, t: int, ents: Array, role_tbs: Dictionary, size_th: Dictionary, want_h: int, lt: Dictionary) -> void:
	var ne: int = ents.size()
	var roles: Array = []   # per entry: PackedInt64Array of 5 role counts
	var nhr: Array = []     # per entry: the non-head couples' persons [child, parent] (§12.12 (9), type 4)
	for j0: int in ne:
		nhr.append([0, 0])
	var heads: int = 0
	var partners: int = 0
	for j: int in ne:
		var e: Array = ents[j]
		var sh: Array = role_tbs.get("%d,%d,%d" % [t, int(e[1]), int(e[2])], [1.0, 0.0, 0.0, 0.0, 0.0])
		var v := PackedFloat64Array()
		for r: int in 5:
			v.append(float(e[4]) * maxf(0.0, float(sh[r])))
		var tot: float = 0.0
		for r2: int in 5:
			tot += v[r2]
		if tot <= 0.0:
			v[0] = float(e[4])
		var rc: PackedInt64Array = _systematic(v, int(e[4]), p.seed_v, "tier_role", int(e[5]))
		roles.append(rc)
		heads += rc[0]
		partners += rc[1]
	var gap: Dictionary = p.tr_margins["head_gap"]
	if t == 1 or t == 2 or t == 4:
		roles = _r77_roles(p, c, t, ents, role_tbs, want_h, nhr, lt)
		heads = 0
		partners = 0
		for j7: int in ne:
			heads += roles[j7][0]
			partners += roles[j7][1]
		if want_h >= 0:
			gap[t] = int(gap.get(t, 0)) + heads - want_h
	elif want_h >= 0 and t == 3:
		gap[t] = int(gap.get(t, 0)) + _set_heads(p, ents, roles, heads, want_h, role_tbs, t, c * NTYPE + t)
		heads = 0
		partners = 0
		for j9: int in ne:
			heads += roles[j9][0]
			partners += roles[j9][1]
	elif want_h >= 0 and t == 0:
		gap[t] = int(gap.get(t, 0)) + heads - want_h
	# the heads: households at their own band and class
	var hh_heads: Dictionary = {}   # hb * NCLASS + class -> heads
	var hh_men: Dictionary = {}     # the same, male heads only (V114 (2))
	var by_hb := PackedInt64Array()
	by_hb.resize(BANDS)
	for j2: int in ne:
		var h: int = roles[j2][0]
		if h > 0:
			var kh: int = int(ents[j2][1]) * NCLASS + int(ents[j2][3])
			hh_heads[kh] = int(hh_heads.get(kh, 0)) + h
			if int(ents[j2][2]) == 0:
				hh_men[kh] = int(hh_men.get(kh, 0)) + h
			by_hb[int(ents[j2][1])] += h
	if hh_heads.is_empty():
		hh_heads[mini(BANDS - 1, ADULT_FROM / 5) * NCLASS + CLASS_REST] = 0
	# members[hb * NCLASS + class] -> {u: {role: n}}
	var members: Dictionary = {}
	for kh2: int in hh_heads:
		members[kh2] = {}
	for j3: int in ne:
		if roles[j3][0] > 0:
			_member_add(members, int(ents[j3][1]) * NCLASS + int(ents[j3][3]), int(ents[j3][0]), 0, roles[j3][0])
	# the partners at their husbands' bands by R77's couples (§12.12 (5))
	if t == 1 or t == 2 or t == 4:
		_place_partners(p, ents, roles, by_hb, hh_men, members, c * NTYPE + t, _r77_z(p, c, t, ents, roles))
	if t == 4:
		var filled: Dictionary = _place_nonhead(p, c, ents, nhr, hh_heads, members)
		for j6: int in ne:
			roles[j6][2] += int(nhr[j6][0])
			roles[j6][3] += int(nhr[j6][1])
		_one_member_each(p, c, ents, roles, hh_heads, members, filled)
	# one child per couple + children and single-parent household first (§12.12 (5), V111 (1)); then children b + 6, parents b - 6,
	# others b: the nearest householder band holding heads, the class in proportion to its heads
	var kids: PackedInt64Array = PackedInt64Array()
	kids.resize(ne)
	for j5: int in ne:
		kids[j5] = roles[j5][2]
	if t == 2 or t == 3:
		_one_child_each(p, t, ents, kids, hh_heads, members)
	var dens: PackedFloat64Array = _child_dens(p) if t == 4 else PackedFloat64Array()
	for j4: int in ne:
		for r3: int in [1, 2, 3, 4]:
			var m: int = kids[j4] if r3 == 2 else roles[j4][r3]
			if m <= 0 or ((t == 1 or t == 2 or t == 4) and r3 == 1):
				continue
			if t == 4 and r3 == 3:
				_parent_window(p, by_hb, members, hh_heads, ents[j4], m, dens)
				continue
			var want: int = clampi(int(ents[j4][1]) + (6 if r3 == 2 else (-6 if r3 == 3 else 0)), 0, BANDS - 1)
			var hb: int = _nearest_hb(by_hb, want)
			_member_by_class(p, members, hh_heads, hb, int(ents[j4][0]), r3, m, "tier_mem", (int(ents[j4][5]) * 8 + r3))
	# size classes per household-bundle
	var mk: Array = members.keys()
	mk.sort()
	for kh3: int in mk:
		var absent: int = 0
		if t == 1 or t == 2 or t == 4:
			var pt3: int = 0
			for u3 in members[kh3]:
				pt3 += int((members[kh3][u3] as Dictionary).get(1, 0))
			absent = maxi(0, pt3 - int(hh_heads.get(kh3, 0)))
		_household_sizes(p, c, t, kh3 / NCLASS, kh3 % NCLASS, int(hh_heads.get(kh3, 0)), members[kh3], size_th, absent)


## The minimum pass (§12.12 (5), V111 (1); R83's window; the joint table TO_E 10:50): every household of the group gets one child-role
## person. A table of parents (band x mother / father, their households; the mother is the wife in type 2, the head in type 3; a male
## head with no wife or a cross-tier household under the father's window) against the child bands (their children), with a slack row
## of children not used, seeded by R83's density inside the window and a decaying epsilon outside (_decay_eps), raked (ipf2) and made
## integer by keyed dependent rounding (dep_round);
## the households and entries then in key order. kids[j] is left with the children not placed; the households without a child (more
## households than children) go to tr_margins["hh_childless"], the children outside the window to ["hh_outside_by"]
## Why not a pass in ascending band, nearest or density-drawn: the nearest took each window's low end, and the draw used up the children
## only later parents could take (838,990 outside)
static func _one_child_each(p: RefCounted, t: int, ents: Array, kids: PackedInt64Array, hh_heads: Dictionary, members: Dictionary) -> void:
	var gap: PackedInt64Array = _child_gaps(p)
	var dens: PackedFloat64Array = _child_dens(p)
	var by_band: Array = []   # per child band: the entries holding children, in order
	var sup := PackedInt64Array()
	sup.resize(BANDS)
	for b2: int in BANDS:
		by_band.append([])
	for j: int in ents.size():
		if kids[j] > 0:
			(by_band[int(ents[j][1])] as Array).append(j)
			sup[int(ents[j][1])] += kids[j]
	var rows: Dictionary = {}   # parent band * 2 + father -> [[kh, n], ...] in key order
	var keys: Array = hh_heads.keys()
	keys.sort()
	for kh: int in keys:
		var need: int = int(hh_heads[kh])
		if need <= 0:
			continue
		var mem: Dictionary = members.get(kh, {})
		var us: Array = mem.keys()
		us.sort()
		var held: int = 0
		for u in us:
			var r: int = 1 if t == 2 else 0
			var n: int = int((mem[u] as Dictionary).get(r, 0))
			if n <= 0:
				continue
			var fem: bool = p.tr_key[int(u) * KEY_STRIDE + 2] == 1
			var rk: int = p.tr_key[int(u) * KEY_STRIDE + 1] * 2 + (0 if fem else 1)
			if not rows.has(rk):
				rows[rk] = []
			(rows[rk] as Array).append([kh, n])
			held += n
		if need > held:
			var rk2: int = (kh / NCLASS) * 2 + 1
			if not rows.has(rk2):
				rows[rk2] = []
			(rows[rk2] as Array).append([kh, need - held])
	var rks: Array = rows.keys()
	rks.sort()
	var cols: Array = []
	for b3: int in BANDS:
		if sup[b3] > 0:
			cols.append(b3)
	if rks.is_empty() or cols.is_empty():
		return
	var rr: Array = []
	var tot_need: int = 0
	for rk3: int in rks:
		var sn: int = 0
		for e: Array in rows[rk3]:
			sn += int(e[1])
		rr.append(sn)
		tot_need += sn
	var cc: Array = []
	var tot_sup: int = 0
	for b4: int in cols:
		cc.append(sup[b4])
		tot_sup += sup[b4]
	rr.append(maxi(0, tot_sup - tot_need))   # the slack row: children not used
	var short: int = maxi(0, tot_need - tot_sup)
	if short > 0:
		cc.append(short)   # the slack column: households without a child
	var nr: int = rr.size()
	var ncol: int = cc.size()
	var seed := PackedFloat64Array()
	seed.resize(nr * ncol)
	for ri: int in rks.size():
		var m: int = int(rks[ri]) / 2
		var fa: int = int(rks[ri]) % 2
		for ci: int in cols.size():
			var b5: int = int(cols[ci])
			var g: int = m - b5
			if g <= 0 or g >= 13:
				continue
			var lo5: int = gap[b5 * 4 + fa * 2]
			var hi5: int = gap[b5 * 4 + fa * 2 + 1]
			var d5: int = lo5 - g if g < lo5 else (g - hi5 if g > hi5 else 0)
			seed[ri * ncol + ci] = dens[(b5 * 2 + fa) * 13 + g] if d5 == 0 else -float(d5)
		if short > 0:
			seed[ri * ncol + ncol - 1] = 1.0
	for ci2: int in cols.size():
		seed[(nr - 1) * ncol + ci2] = 1.0
	_decay_eps(seed)
	var x: PackedFloat64Array = ipf2(seed, rr, cc)
	var it: PackedInt64Array = dep_round(x, nr, ncol, p.seed_v, "tier_child_round", c_key(ents) * NTYPE + t)
	for ri2: int in rks.size():
		var m2: int = int(rks[ri2]) / 2
		var fa2: int = int(rks[ri2]) % 2
		var hh: Array = rows[rks[ri2]]
		var hi_at: int = 0
		for ci3: int in cols.size():
			var n2: int = it[ri2 * ncol + ci3]
			var b6: int = int(cols[ci3])
			var g2: int = m2 - b6
			var inside: bool = g2 >= gap[b6 * 4 + fa2 * 2] and g2 <= gap[b6 * 4 + fa2 * 2 + 1]
			while n2 > 0 and hi_at < hh.size():
				var e2: Array = hh[hi_at]
				var take: int = mini(n2, int(e2[1]))
				var left: int = take
				for j2 in by_band[b6]:
					if left <= 0:
						break
					var tk: int = mini(left, kids[int(j2)])
					if tk <= 0:
						continue
					_member_add(members, int(e2[0]), int(ents[int(j2)][0]), 2, tk)
					kids[int(j2)] -= tk
					left -= tk
				e2[1] = int(e2[1]) - take
				n2 -= take
				if int(e2[1]) <= 0:
					hi_at += 1
				# T1s-gap2 (M018): every pair, inside the window or not, mothers apart from fathers
				var g2k: String = "gap2_father" if fa2 == 1 else "gap2"
				p.tr_margins[g2k] = _gap_add(p.tr_margins.get(g2k, {}), b6, g2, take)
				if fa2 == 0:
					var mc: Dictionary = p.tr_margins.get("gap2_mc", {})
					mc["%d|%d" % [m2, b6]] = int(mc.get("%d|%d" % [m2, b6], 0)) + take
					p.tr_margins["gap2_mc"] = mc
				if inside:
					p.tr_margins["gap_child"] = _gap_add(p.tr_margins.get("gap_child", {}), b6, g2, take)
				else:
					var sk: String = "t%d %s %d-%d" % [t, "father" if fa2 == 1 else "mother", 5 * m2, 5 * m2 + 4]
					var ob: Dictionary = p.tr_margins.get("hh_outside_by", {})
					ob[sk] = int(ob.get(sk, 0)) + take
					p.tr_margins["hh_outside_by"] = ob
	p.tr_margins["hh_childless"] = int(p.tr_margins.get("hh_childless", 0)) + short


## R83's density of the parent's age at birth by band gap, per child band x (mother, father) x gap 0..12 (TO_E 10:28): each age group's
## share split between the two band gaps around its midpoint by the distance (D), the child's birth year's row (as _child_gaps)
static func _child_dens(p: RefCounted) -> PackedFloat64Array:
	var win: Dictionary = _v(p, "child_window")
	var out := PackedFloat64Array()
	out.resize(BANDS * 2 * 13)
	for b: int in BANDS:
		var y: int = 2024 - (5 * b + 2)
		var best: int = 0
		var bd: int = 1 << 30
		for i: int in (win["mother"] as Array).size():
			var d: int = absi(int(win["mother"][i][0]) - maxi(y, 1950))
			if d < bd:
				bd = d
				best = i
		for fa: int in 2:
			var rows: Array = win["mother_shares"][best] if fa == 0 else win["father_shares"]
			for r: Array in rows:
				var mid: float = (float(r[0]) + float(r[1])) * 0.5 / 5.0
				var g0: int = int(floor(mid))
				var fr: float = mid - float(g0)
				if g0 >= 0 and g0 < 13:
					out[(b * 2 + fa) * 13 + g0] += float(r[2]) * (1.0 - fr)
				if g0 + 1 >= 0 and g0 + 1 < 13:
					out[(b * 2 + fa) * 13 + g0 + 1] += float(r[2]) * fr
	return out


## Keyed dependent rounding of an nr x nc table whose row and column sums are integers (Gandhi, Khuller, Parthasarathy, Srinivasan
## 2006; TO_E 10:55, M015): the floors kept; while fractional cells remain, a cycle of them, alternately + and -, is shifted by +alpha
## with probability beta / (alpha + beta) (a keyed draw) or by -beta. Every row and column sum stays exact and each cell keeps its value
## in expectation. A node left with one fractional cell (round-off) rounds that cell to the nearer integer, counted in rounded[0]
## Why not the ordered max-flow: it filled the cells in descending fraction, which put ceilings into the window's epsilon cells
## (the integer fallback 2.7 times the real one, M015 E4)
static func dep_round(x: PackedFloat64Array, nr: int, nc: int, seed_v: int, tag: String, key: int, rounded: PackedInt64Array = PackedInt64Array([0])) -> PackedInt64Array:
	var out := PackedInt64Array()
	out.resize(nr * nc)
	var f := PackedFloat64Array()
	f.resize(nr * nc)
	for i: int in nr * nc:
		var fl: float = floor(x[i] + 1e-9)
		out[i] = int(fl)
		var r: float = x[i] - fl
		if r >= 1.0 - 1e-9:
			out[i] += 1
		elif r > 1e-9:
			f[i] = r
	var step: int = 0
	var scan: int = 0
	while true:
		var start: int = -1
		while scan < nr * nc:
			if f[scan] > 0.0:
				start = scan
				break
			scan += 1
		if start < 0:
			break
		var nodes: Array = [start / nc]
		var cells: Array = []
		var pos: Dictionary = {start / nc: 0}
		var cur: int = start / nc
		var prev: int = -1
		var from: int = -1
		while true:
			var nxt: int = -1
			if cur < nr:
				for j: int in nc:
					if f[cur * nc + j] > 0.0 and cur * nc + j != prev:
						nxt = cur * nc + j
						break
			else:
				for i2: int in nr:
					if f[i2 * nc + cur - nr] > 0.0 and i2 * nc + cur - nr != prev:
						nxt = i2 * nc + cur - nr
						break
			if nxt < 0:
				break
			var other: int = (nr + nxt % nc) if cur < nr else (nxt / nc)
			cells.append(nxt)
			if pos.has(other):
				from = int(pos[other])
				break
			pos[other] = nodes.size()
			nodes.append(other)
			prev = nxt
			cur = other
		if from < 0:
			var c0: int = int(cells.back()) if not cells.is_empty() else start
			out[c0] += 1 if f[c0] >= 0.5 else 0
			f[c0] = 0.0
			rounded[0] += 1
			continue
		var cyc: Array = cells.slice(from)
		var alpha: float = 1e300
		var beta: float = 1e300
		for k: int in cyc.size():
			var c: int = int(cyc[k])
			if k % 2 == 0:
				alpha = minf(alpha, 1.0 - f[c])
				beta = minf(beta, f[c])
			else:
				alpha = minf(alpha, f[c])
				beta = minf(beta, 1.0 - f[c])
		var d: float = alpha if KEYED.u(seed_v, tag, key, step, 0) < beta / (alpha + beta) else -beta
		step += 1
		for k2: int in cyc.size():
			var c2: int = int(cyc[k2])
			f[c2] += d if k2 % 2 == 0 else -d
			if f[c2] <= 1e-9:
				f[c2] = 0.0
			elif f[c2] >= 1.0 - 1e-9:
				f[c2] = 0.0
				out[c2] += 1
	return out


## The joint tables' outside seed (TO_E 10:55, M015): a cell marked -d (d bands from the window) becomes eps0 x 0.01^(d - 1), eps0 =
## 1e-6 x the table's smallest in-window seed
## Why not a flat epsilon: it spread the fallback over every band outside, 85% of it two or more bands away (M015 E3)
static func _decay_eps(seed: PackedFloat64Array) -> void:
	var lo: float = 1e300
	for v: float in seed:
		if v > 0.0 and v < lo:
			lo = v
	var e0: float = 1e-6 * (lo if lo < 1e300 else 1.0)
	for i: int in seed.size():
		if seed[i] < 0.0:
			seed[i] = e0 * DM.pow(0.01, -seed[i] - 1.0)


## M019 (2): a structural zero, the child as old as the parent or older (gap <= 0 in bands), except gap 0 with both in the open 85+
## band, whose ages can differ by up to 15 years
static func _no_pair(g: int, b1: int, b2: int) -> bool:
	return g < 0 or (g == 0 and not (b1 == BANDS - 1 and b2 == BANDS - 1))


## A group's key for the keyed rounding: its first entry's unit
static func c_key(ents: Array) -> int:
	return int(ents[0][0]) if not ents.is_empty() else 0


## A gap tally: "child band year group|gap" -> persons (T1s-gap)
static func _gap_add(d: Dictionary, b: int, g: int, n: int) -> Dictionary:
	var y: int = 2024 - (5 * b + 2)
	var grp: int = 0 if y < 1970 else (1 if y < 1990 else (2 if y < 2010 else 3))
	d["%d|%d" % [grp, g]] = int(d.get("%d|%d" % [grp, g], 0)) + n
	return d


## R83's window per child band (§12.12 (5)): [mother lo, hi, father lo, hi] as parent band - child band, from the child's birth year's
## 1st-99th percentile (the nearer data year, before 1950 1950's)
static func _child_gaps(p: RefCounted) -> PackedInt64Array:
	var win: Dictionary = _v(p, "child_window")
	var gap := PackedInt64Array()
	gap.resize(BANDS * 4)
	for b: int in BANDS:
		var y: int = 2024 - (5 * b + 2)
		var best: Array = []
		var bd: int = 1 << 30
		for row: Array in win["mother"]:
			var d: int = absi(int(row[0]) - maxi(y, 1950))
			if d < bd:
				bd = d
				best = row
		# M019 (3): a band gap is inside when any part of it lies within the 1st-99th percentile
		# Why not round(p / 5) (before 15:51): it cut gap 9 and piled its mass on gap 8
		gap[b * 4] = floori(float(best[2]) / 5.0)
		gap[b * 4 + 1] = ceili(float(best[3]) / 5.0)
		gap[b * 4 + 2] = floori(float(win["father"][0]) / 5.0)
		gap[b * 4 + 3] = ceili(float(win["father"][1]) / 5.0)
	return gap


## §12.12 (9) as ruled TO_E 10:00: one prefecture's non-head couples placed as pairs into "other" households by R83's window. A
## household's reference is its wife (its female head, or with neither its male head under the father's window). A child couple's wife
## is within her birth year's window below the reference; a parent couple's wife is the reference's mother by the reference's year. In two
## rounds, the child couples to the single-headed households, then every couple to the couple-headed ones, the households in ascending
## reference band, each taking the eligible demand whose last eligible reference band comes first (the
## youngest on a tie); a demand left over takes the nearest household outside its window (tr_margins["nh_outside"]). One household holds
## at most one non-head couple. Members join with the child or parent role, the pairs to tr_nh_hh["code|band|class"] as [husband unit,
## wife unit, kind, n] and the gaps in bands to tr_margins["nh_gaps"]
static func _place_nonhead(p: RefCounted, c: int, ents: Array, nhr: Array, hh_heads: Dictionary, members: Dictionary) -> Dictionary:
	var gap: PackedInt64Array = _child_gaps(p)
	var dens: PackedFloat64Array = _child_dens(p)
	var slots: Array = []   # [reference band, father 0/1, kh, n, single-headed 0/1]
	var keys: Array = hh_heads.keys()
	keys.sort()
	for kh: int in keys:
		var heads: int = int(hh_heads[kh])
		if heads <= 0:
			continue
		var mem: Dictionary = members.get(kh, {})
		var us: Array = mem.keys()
		us.sort()
		var wives: int = 0
		var fheads: int = 0
		for u in us:
			var fem: bool = p.tr_key[int(u) * KEY_STRIDE + 2] == 1
			var b: int = p.tr_key[int(u) * KEY_STRIDE + 1]
			var nw: int = int((mem[u] as Dictionary).get(1, 0)) if fem else 0
			var nf: int = int((mem[u] as Dictionary).get(0, 0)) if fem else 0
			if nw > 0:
				slots.append([b, 0, kh, nw, 0])
				wives += nw
			if nf > 0:
				slots.append([b, 0, kh, nf, 1])
				fheads += nf
		var rest: int = heads - fheads - wives
		if rest > 0:
			slots.append([kh / NCLASS, 1, kh, rest, 1])
	slots.sort()
	var dem: Array = []   # [kind, wife band, husband band, n]
	for key: String in p.tr_nh_couples:
		var k: PackedStringArray = key.split("|")
		if int(k[0]) == c:
			dem.append([int(k[3]), int(k[2]) + 3, int(k[1]) + 3, int(p.tr_nh_couples[key])])
	# Why not leave them to the slack (before TO_E 17:54): a parent couple whose wife has no couple-headed reference below her band in the
	# prefecture (M019 (2)'s structural zeros) can never be placed (Kochi's one at wife 20-24); it is the child couple of an older head
	# instead, its reservations and its record moved with it, counted
	for d5: Array in dem:
		if int(d5[0]) != 1:
			continue
		var ok: bool = false
		for sl5: Array in slots:
			if int(sl5[4]) == 0 and int(sl5[3]) > 0 and not _no_pair(int(d5[1]) - int(sl5[0]), int(d5[1]), int(sl5[0])):
				ok = true
				break
		if ok:
			continue
		var nm: int = int(d5[3])
		for side: Array in [[int(d5[1]), 1], [int(d5[2]), 0]]:
			var left: int = nm
			for j5: int in ents.size():
				if left <= 0:
					break
				if int(ents[j5][1]) == int(side[0]) and int(ents[j5][2]) == int(side[1]) and int(nhr[j5][1]) > 0:
					var mv: int = mini(left, int(nhr[j5][1]))
					nhr[j5][1] = int(nhr[j5][1]) - mv
					nhr[j5][0] = int(nhr[j5][0]) + mv
					left -= mv
		var k1: String = "%d|%d|%d|1" % [c, int(d5[2]) - 3, int(d5[1]) - 3]
		var k0: String = "%d|%d|%d|0" % [c, int(d5[2]) - 3, int(d5[1]) - 3]
		p.tr_nh_couples[k1] = int(p.tr_nh_couples[k1]) - nm
		if int(p.tr_nh_couples[k1]) == 0:
			p.tr_nh_couples.erase(k1)
		p.tr_nh_couples[k0] = int(p.tr_nh_couples.get(k0, 0)) + nm
		d5[0] = 0
		p.tr_margins["nh_kind_moved"] = int(p.tr_margins.get("nh_kind_moved", 0)) + nm
	dem.sort()
	var pick := func(d: Array, sl: Array) -> int:
		var w: int = int(d[1])
		var r: int = int(sl[0])
		var fa: int = int(sl[1])
		var g: int = r - w if int(d[0]) == 0 else w - r
		var cb: int = w if int(d[0]) == 0 else r
		var lo: int = gap[cb * 4 + fa * 2]
		var hi: int = gap[cb * 4 + fa * 2 + 1]
		return lo - g if g < lo else (g - hi if g > hi else 0)
	var placed: Array = []   # [demand index, slot index, n, outside]
	# the first round's cap (§12.12 (9) AMENDED after the third run): the child couples beyond R84's two-couple households (a share of
	# the 'other' households since M019) less the parent couples
	var nhp: Dictionary = (_v(p, "nonhead_couples") as Dictionary)["by_pref"][str(c)]
	var ccn: int = 0
	var pcn: int = 0
	for d0: Array in dem:
		ccn += int(d0[3]) if int(d0[0]) == 0 else 0
		pcn += int(d0[3]) if int(d0[0]) == 1 else 0
	# M019 (1): the floor a share of the 'other' households, census 2020's base x the target
	# Why not x the start's couples / 2020's (before 15:51): the type-4 target falls 7.1% and the couples did not (M019 §2)
	var ht: Dictionary = _v(p, "household_target")
	var o20: float = float(ht["census_2020"][str(c)][4])
	var low_s: int = int(round(float(nhp["two_couple_low"]) * float(_head_targets(p)["%02d|4" % c]) / o20)) if o20 > 0.0 else 0
	var cap0: int = maxi(0, ccn - maxi(0, low_s - pcn))
	# two joint tables (§12.12 (9) AMENDED after the second run; TO_E 10:50): the child couples to the single-headed households first,
	# at most cap0, then every couple left to the couple-headed ones; a parent couple never to a single-headed household
	for rnd: int in 2:
		var groups: Dictionary = {}   # reference band * 2 + father -> slot indices
		for si: int in slots.size():
			if int(slots[si][4]) == 1 - rnd and int(slots[si][3]) > 0:
				var gk2: int = int(slots[si][0]) * 2 + int(slots[si][1])
				if not groups.has(gk2):
					groups[gk2] = []
				(groups[gk2] as Array).append(si)
		var cgr: Dictionary = {}   # kind * BANDS + wife band -> demand indices (the seed depends on these two only)
		for di: int in dem.size():
			if int(dem[di][3]) > 0 and (rnd == 1 or int(dem[di][0]) == 0):
				var ck2: int = int(dem[di][0]) * BANDS + int(dem[di][1])
				if not cgr.has(ck2):
					cgr[ck2] = []
				(cgr[ck2] as Array).append(di)
		var cdx: Array = cgr.keys()
		cdx.sort()
		var gks: Array = groups.keys()
		gks.sort()
		if gks.is_empty() or cdx.is_empty():
			continue
		var rr: Array = []
		var ss: int = 0
		for gk3: int in gks:
			var sn: int = 0
			for si2: int in groups[gk3]:
				sn += int(slots[si2][3])
			rr.append(sn)
			ss += sn
		var cc: Array = []
		var sd: int = 0
		for ck3: int in cdx:
			var cn: int = 0
			for di2: int in cgr[ck3]:
				cn += int(dem[di2][3])
			cc.append(cn)
			sd += cn
		var k: int = mini(ss, sd) if rnd == 1 else mini(cap0, mini(ss, sd))
		rr.append(sd - k)
		cc.append(ss - k)
		var nr: int = rr.size()
		var ncol: int = cc.size()
		var seed := PackedFloat64Array()
		seed.resize(nr * ncol)
		for ri: int in gks.size():
			var r2: int = int(gks[ri]) / 2
			var fa2: int = int(gks[ri]) % 2
			var probe: Array = [r2, fa2, 0, 0, 0]
			for ci: int in cdx.size():
				var d4: Array = dem[int(cgr[cdx[ci]][0])]
				var w2: int = int(d4[1])
				var g4: int = r2 - w2 if int(d4[0]) == 0 else w2 - r2
				var dist: int = pick.call(d4, probe)
				# Why not 0 outside gaps 1-12 (before TO_E 15:17): the 85+ band is top-coded, so a couple whose only room was at gap 0 went to
				# the slack with a household to spare (T1s-nh's 46); those cells take the decaying epsilon like any outside cell
				if _no_pair(g4, r2, w2):
					continue
				if g4 <= 0 or g4 >= 13:
					seed[ri * ncol + ci] = -float(maxi(1, dist))
					continue
				seed[ri * ncol + ci] = (dens[(w2 * 2 + fa2) * 13 + g4] if int(d4[0]) == 0 else dens[(r2 * 2) * 13 + g4]) if dist == 0 else -float(dist)
			seed[ri * ncol + ncol - 1] = 1.0
		for ci2: int in cdx.size():
			seed[(nr - 1) * ncol + ci2] = 1.0
		_decay_eps(seed)
		var xt: PackedFloat64Array = ipf2(seed, rr, cc)
		var it: PackedInt64Array = dep_round(xt, nr, ncol, p.seed_v, "tier_nh_round", c * 2 + rnd)
		for ri2: int in gks.size():
			var sl_list: Array = groups[gks[ri2]]
			var at2: int = 0
			for ci3: int in cdx.size():
				var n4: int = it[ri2 * ncol + ci3]
				for di3: int in cgr[cdx[ci3]]:
					while n4 > 0 and at2 < sl_list.size() and int(dem[di3][3]) > 0:
						var si3: int = int(sl_list[at2])
						var take: int = mini(n4, mini(int(slots[si3][3]), int(dem[di3][3])))
						if take > 0:
							placed.append([di3, si3, take, 0 if pick.call(dem[di3], slots[si3]) == 0 else 1])
							slots[si3][3] = int(slots[si3][3]) - take
							dem[di3][3] = int(dem[di3][3]) - take
							n4 -= take
						if int(slots[si3][3]) <= 0:
							at2 += 1
	for di4: int in dem.size():
		if int(dem[di4][3]) > 0:
			p.tr_margins["nh_unplaced"] = int(p.tr_margins.get("nh_unplaced", 0)) + int(dem[di4][3])
			var uk: Dictionary = p.tr_margins.get("nh_unplaced_kind", {})
			uk["%d|%d" % [int(dem[di4][0]), int(dem[di4][1])]] = int(uk.get("%d|%d" % [int(dem[di4][0]), int(dem[di4][1])], 0)) + int(dem[di4][3])
			p.tr_margins["nh_unplaced_kind"] = uk
			var ub: Dictionary = p.tr_margins.get("nh_unplaced_by", {})
			ub[c] = int(ub.get(c, 0)) + int(dem[di4][3])
			p.tr_margins["nh_unplaced_by"] = ub
	var gaps: Dictionary = p.tr_margins.get("nh_gaps", {})
	var filled: Dictionary = {}   # kh -> its single heads reached by a couple
	for pl: Array in placed:
		var d3: Array = dem[int(pl[0])]
		var sl3: Array = slots[int(pl[1])]
		var n3: int = int(pl[2])
		var kind: int = int(d3[0])
		var g3: int = int(sl3[0]) - int(d3[1]) if kind == 0 else int(d3[1]) - int(sl3[0])
		var gk: String = "%s %s%d" % ["child" if kind == 0 else "parent", "out " if int(pl[3]) == 1 else "", g3]
		gaps[gk] = int(gaps.get(gk, 0)) + n3
		if int(pl[3]) == 0:
			p.tr_margins["gap_nh"] = _gap_add(p.tr_margins.get("gap_nh", {}), int(d3[1]) if kind == 0 else int(sl3[0]), g3, n3)
		if int(pl[3]) == 1:
			p.tr_margins["nh_outside"] = int(p.tr_margins.get("nh_outside", 0)) + n3
		if int(sl3[4]) == 1:
			filled[int(sl3[2])] = int(filled.get(int(sl3[2]), 0)) + n3
		if int(sl3[4]) == 0:
			p.tr_margins["nh_two_couple"] = int(p.tr_margins.get("nh_two_couple", 0)) + n3
			var tc: Dictionary = p.tr_margins.get("nh_two_couple_by", {})
			tc[c] = int(tc.get(c, 0)) + n3
			p.tr_margins["nh_two_couple_by"] = tc
		var left: int = n3
		while left > 0:
			var jh: int = _nh_entry(ents, nhr, int(d3[2]), 0, kind)
			var jw: int = _nh_entry(ents, nhr, int(d3[1]), 1, kind)
			if jh < 0 or jw < 0:
				p.tr_margins["nh_unplaced"] = int(p.tr_margins.get("nh_unplaced", 0)) + left
				var ub2: Dictionary = p.tr_margins.get("nh_unplaced_by", {})
				ub2[c] = int(ub2.get(c, 0)) + left
				p.tr_margins["nh_unplaced_by"] = ub2
				if int(sl3[4]) == 0:
					p.tr_margins["nh_two_couple"] = int(p.tr_margins.get("nh_two_couple", 0)) - left
					var tc2: Dictionary = p.tr_margins.get("nh_two_couple_by", {})
					tc2[c] = int(tc2.get(c, 0)) - left
					p.tr_margins["nh_two_couple_by"] = tc2
				break
			var m: int = mini(left, mini(int(nhr[jh][kind]), int(nhr[jw][kind])))
			var kh3: int = int(sl3[2])
			_member_add(members, kh3, int(ents[jh][0]), 2 if kind == 0 else 3, m)
			_member_add(members, kh3, int(ents[jw][0]), 2 if kind == 0 else 3, m)
			nhr[jh][kind] = int(nhr[jh][kind]) - m
			nhr[jw][kind] = int(nhr[jw][kind]) - m
			var rk: String = "%02d|%02d|%d" % [c, kh3 / NCLASS, kh3 % NCLASS]
			if not p.tr_nh_hh.has(rk):
				p.tr_nh_hh[rk] = []
			(p.tr_nh_hh[rk] as Array).append([int(ents[jh][0]), int(ents[jw][0]), kind, m])
			left -= m
	p.tr_margins["nh_gaps"] = gaps
	return filled


## Type 4's one member first (§12.12 (9) AMENDED, TO_E 11:10): the "other" households with a head and no other member after the
## non-head couples, by the head's band, against the type's persons still in the child, parent or other role by role x band, with a
## slack row for the persons not used; seeded by R83's density (a child: its birth year at head - child; a parent: the head's birth year
## at parent - head), 1 for an "other" within two bands of the head (T), and the decaying epsilon outside; raked (ipf2) and rounded
## (dep_round). The members join with their role and leave roles[j]; the households left without one go to tr_margins["t4_unfilled"]
static func _one_member_each(p: RefCounted, c: int, ents: Array, roles: Array, hh_heads: Dictionary, members: Dictionary, filled: Dictionary) -> void:
	var gap: PackedInt64Array = _child_gaps(p)
	var dens: PackedFloat64Array = _child_dens(p)
	var rows: Dictionary = {}   # head band -> [[kh, n]]
	var keys: Array = hh_heads.keys()
	keys.sort()
	for kh: int in keys:
		var mem: Dictionary = members.get(kh, {})
		var wives: int = 0
		for u in mem:
			if p.tr_key[int(u) * KEY_STRIDE + 2] == 1:
				wives += int((mem[u] as Dictionary).get(1, 0))
		var need: int = int(hh_heads[kh]) - wives - int(filled.get(kh, 0))
		if need <= 0:
			continue
		var hb: int = kh / NCLASS
		if not rows.has(hb):
			rows[hb] = []
		(rows[hb] as Array).append([kh, need])
	if rows.is_empty():
		return
	var cols: Array = []   # [role, band]
	var csup: Array = []
	for r: int in [2, 3, 4]:
		for b: int in BANDS:
			var sn: int = 0
			for j: int in ents.size():
				if int(ents[j][1]) == b:
					sn += roles[j][r]
			if sn > 0:
				cols.append([r, b])
				csup.append(sn)
	if cols.is_empty():
		p.tr_margins["t4_unfilled"] = int(p.tr_margins.get("t4_unfilled", 0)) + 1
		return
	var hbs: Array = rows.keys()
	hbs.sort()
	var rr: Array = []
	var need_t: int = 0
	for hb2: int in hbs:
		var sn2: int = 0
		for e: Array in rows[hb2]:
			sn2 += int(e[1])
		rr.append(sn2)
		need_t += sn2
	var cc: Array = csup.duplicate()
	var sup_t: int = 0
	for x0: int in csup:
		sup_t += x0
	rr.append(maxi(0, sup_t - need_t))
	var short: int = maxi(0, need_t - sup_t)
	if short > 0:
		cc.append(short)
	var nr: int = rr.size()
	var ncol: int = cc.size()
	var seed := PackedFloat64Array()
	seed.resize(nr * ncol)
	for ri: int in hbs.size():
		var hb3: int = int(hbs[ri])
		for ci: int in cols.size():
			var r3: int = int(cols[ci][0])
			var b3: int = int(cols[ci][1])
			var v: float = 0.0
			if r3 == 2 or r3 == 3:
				var cb: int = b3 if r3 == 2 else hb3
				var g: int = hb3 - b3 if r3 == 2 else b3 - hb3
				var lo: int = gap[cb * 4]
				var hi: int = gap[cb * 4 + 1]
				var d: int = lo - g if g < lo else (g - hi if g > hi else 0)
				if _no_pair(g, hb3, b3):
					v = 0.0
				else:
					v = dens[(cb * 2) * 13 + g] if d == 0 and g < 13 else -float(maxi(1, d))
			else:
				var d4: int = absi(b3 - hb3)
				v = 1.0 if d4 <= 2 else -float(d4 - 2)
			seed[ri * ncol + ci] = v
		if short > 0:
			seed[ri * ncol + ncol - 1] = 1.0
	for ci2: int in cols.size():
		seed[(nr - 1) * ncol + ci2] = 1.0
	_decay_eps(seed)
	var x: PackedFloat64Array = ipf2(seed, rr, cc)
	var it: PackedInt64Array = dep_round(x, nr, ncol, p.seed_v, "tier_t4_round", c)
	for ri2: int in hbs.size():
		var hh: Array = rows[hbs[ri2]]
		var at: int = 0
		for ci3: int in cols.size():
			var n: int = it[ri2 * ncol + ci3]
			var r4: int = int(cols[ci3][0])
			var b4: int = int(cols[ci3][1])
			while n > 0 and at < hh.size():
				var take: int = mini(n, int(hh[at][1]))
				var left: int = take
				for j2: int in ents.size():
					if left <= 0:
						break
					if int(ents[j2][1]) != b4 or roles[j2][r4] <= 0:
						continue
					var tk: int = mini(left, roles[j2][r4])
					_member_add(members, int(hh[at][0]), int(ents[j2][0]), r4, tk)
					roles[j2][r4] -= tk
					left -= tk
				hh[at][1] = int(hh[at][1]) - take
				n -= take
				if int(hh[at][1]) <= 0:
					at += 1
	p.tr_margins["t4_unfilled"] = int(p.tr_margins.get("t4_unfilled", 0)) + short


## The first entry of the band and sex (0 husband, 1 wife) still holding non-head persons of the kind, in entry order; -1 if none
static func _nh_entry(ents: Array, nhr: Array, b: int, s: int, kind: int) -> int:
	for j: int in ents.size():
		if int(ents[j][1]) == b and int(ents[j][2]) == s and int(nhr[j][kind]) > 0:
			return j
	return -1


static func _member_add(members: Dictionary, kh: int, u: int, r: int, n: int) -> void:
	if n <= 0:
		return
	if not members.has(kh):
		members[kh] = {}
	var m: Dictionary = members[kh]
	if not m.has(u):
		m[u] = {}
	m[u][r] = int(m[u].get(r, 0)) + n


static func _nearest_hb(by_hb: PackedInt64Array, want: int) -> int:
	for d: int in BANDS:
		if want - d >= 0 and by_hb[want - d] > 0:
			return want - d
		if want + d < BANDS and by_hb[want + d] > 0:
			return want + d
	return want


## m members of unit u in role r placed at householder band hb, split over the heads' classes there in proportion (keyed systematic)
static func _member_by_class(p: RefCounted, members: Dictionary, hh_heads: Dictionary, hb: int, u: int, r: int, m: int, tag: String, key: int) -> void:
	var v := PackedFloat64Array()
	var tot: float = 0.0
	for k: int in NCLASS:
		v.append(float(hh_heads.get(hb * NCLASS + k, 0)))
		tot += v[k]
	if tot <= 0.0:
		_member_add(members, hb * NCLASS + CLASS_REST, u, r, m)
		return
	for k2: int in NCLASS:
		v[k2] *= float(m) / tot
	var ints: PackedInt64Array = _systematic(v, m, p.seed_v, tag, key)
	for k3: int in NCLASS:
		_member_add(members, hb * NCLASS + k3, u, r, ints[k3])


## The heads per prefecture x type from the household-type target (§12.14 (1), (2): census 2020 x IPSS's ratio, PROJECTION), the
## integer nearest; types 1 and 2 the head couples placed there, type 4 its head couples + the single-headed 'other' households (§12.16
## (3), M022). Keys "pref|type" for the five private types
## Why not R64's share x private persons ÷ mean size (§12.8 item 4): it holds 2020's composition with the age-unknown inside (M017)
static func _head_targets(p: RefCounted) -> Dictionary:
	var tgt: Dictionary = (_v(p, "household_target") as Dictionary)["by_pref"]
	var out: Dictionary = {}
	for c: String in tgt:
		if c == "0":
			continue
		for t2: int in 5:
			out["%02d|%d" % [int(c), t2]] = int(round(float(tgt[c][t2])))
		for t3: int in [1, 2, 4]:
			out["%02d|%d" % [int(c), t3]] = 0
	var h4s: Dictionary = p.tr_margins["h4s"]
	for c2: Variant in h4s:
		out["%02d|4" % int(c2)] = int(round(float(h4s[c2])))
	for key: String in p.tr_couples:
		var k: PackedStringArray = key.split("|")
		if int(k[3]) == 1 or int(k[3]) == 2 or int(k[3]) == 4:
			out["%02d|%s" % [int(k[0]), k[3]]] = int(out["%02d|%s" % [int(k[0]), k[3]]]) + int(p.tr_couples[key])
	return out


## The entries' heads moved to the target by keyed systematic rounding in proportion to their D head shares, each within its
## persons of 15 and over; a lost head takes the entry's other D roles in proportion, a gained one comes out of them. Returns the
## heads left off the target (persons too few)
static func _set_heads(p: RefCounted, ents: Array, roles: Array, heads: int, want: int, role_tbs: Dictionary, t: int, key: int) -> int:
	var ne: int = ents.size()
	var up: bool = want > heads
	var cap := PackedInt64Array()
	cap.resize(ne)
	var v := PackedFloat64Array()
	v.resize(ne)
	var tot: float = 0.0
	var cap_tot: int = 0
	for j: int in ne:
		var rc: PackedInt64Array = roles[j]
		var sh: Array = role_tbs.get("%d,%d,%d" % [t, int(ents[j][1]), int(ents[j][2])], [1.0, 0.0, 0.0, 0.0, 0.0])
		if up:
			cap[j] = (rc[1] + rc[2] + rc[3] + rc[4]) if int(ents[j][1]) * 5 >= 15 else 0
			v[j] = float(cap[j]) * maxf(0.0, float(sh[0]))
		else:
			cap[j] = rc[0]
			v[j] = float(cap[j])
		tot += v[j]
		cap_tot += cap[j]
	var move: int = mini(absi(want - heads), cap_tot)
	if move <= 0:
		return heads - want
	for j2: int in ne:
		v[j2] = (v[j2] / tot if tot > 0.0 else float(cap[j2]) / float(maxi(1, cap_tot))) * float(move)
	var q: PackedInt64Array = _capped(v, cap, move, p.seed_v, "tier_heads", key)
	for j3: int in ne:
		if q[j3] <= 0:
			continue
		var rc2: PackedInt64Array = roles[j3]
		var sh2: Array = role_tbs.get("%d,%d,%d" % [t, int(ents[j3][1]), int(ents[j3][2])], [1.0, 0.0, 0.0, 0.0, 0.0])
		if up:
			var o := PackedFloat64Array([0.0, float(rc2[1]), float(rc2[2]), float(rc2[3]), float(rc2[4])])
			var take: PackedInt64Array = _systematic(o, q[j3], p.seed_v, "tier_heads_take", key * 4096 + j3)
			for r: int in [1, 2, 3, 4]:
				rc2[r] -= take[r]
			rc2[0] += q[j3]
		else:
			var o2 := PackedFloat64Array([0.0, maxf(0.0, float(sh2[1])), maxf(0.0, float(sh2[2])), maxf(0.0, float(sh2[3])), maxf(0.0, float(sh2[4]))])
			var ot: float = o2[1] + o2[2] + o2[3] + o2[4]
			if ot <= 0.0:
				o2[4] = 1.0
				ot = 1.0
			for r2: int in 5:
				o2[r2] *= float(q[j3]) / ot
			var give: PackedInt64Array = _systematic(o2, q[j3], p.seed_v, "tier_heads_give", key * 4096 + j3)
			for r3: int in [1, 2, 3, 4]:
				rc2[r3] += give[r3]
			rc2[0] -= q[j3]
		roles[j3] = rc2
	return (heads + (move if up else -move)) - want


## v to integers summing to total, each at most cap (keyed systematic, then the excess moved to entries with room in index order)
static func _capped(v: PackedFloat64Array, cap: PackedInt64Array, total: int, seed_v: int, tag: String, key: int) -> PackedInt64Array:
	var out: PackedInt64Array = _systematic(v, total, seed_v, tag, key)
	var over: int = 0
	for i: int in out.size():
		if out[i] > cap[i]:
			over += out[i] - cap[i]
			out[i] = cap[i]
	for i2: int in out.size():
		while over > 0 and out[i2] < cap[i2]:
			out[i2] += 1
			over -= 1
	return out


## The partners at a householder band by z, the (partner band x sex, householder band) table of R77's couples (_r77_z); each cell's
## partners then over the male heads' classes there (V114 (2); a band with no male head, a cross-tier husband, at the rest class)
## Why not all heads' classes (before V114): type 4's female heads drew wives into bundles with no husband (10,985 at 8a1f362f)
## Why not the age-gap kernel (before §12.12): R77 gives the husband's x the wife's age, and the kernel's N(2.2, 3.5) was T
static func _place_partners(p: RefCounted, ents: Array, roles: Array, by_hb: PackedInt64Array, hh_men: Dictionary, members: Dictionary, key: int, zfix: PackedInt64Array) -> void:
	var rows_n := PackedInt64Array()
	rows_n.resize(BANDS * 2)
	var row_ents: Dictionary = {}
	for j: int in ents.size():
		var q: int = roles[j][1]
		if q <= 0:
			continue
		var rb: int = int(ents[j][1]) * 2 + int(ents[j][2])
		rows_n[rb] += q
		if not row_ents.has(rb):
			row_ents[rb] = []
		row_ents[rb].append([int(ents[j][0]), q])
	var z: PackedInt64Array = zfix
	# per householder band: the partners dealt from each row's entries in entry order, then (entry x class) rounded jointly so the
	# partners by class are the heads by class there (scaled down by the largest remainder where partners are short)
	var at_hb: Dictionary = {}   # hb -> [[u, n], ...]
	for rb3: int in BANDS * 2:
		if not row_ents.has(rb3):
			continue
		var ent: Array = row_ents[rb3]
		var ei: int = 0
		var left: int = int(ent[0][1])
		for hb3: int in BANDS:
			var cnt: int = z[rb3 * BANDS + hb3]
			while cnt > 0:
				var take: int = mini(cnt, left)
				if not at_hb.has(hb3):
					at_hb[hb3] = []
				at_hb[hb3].append([int(ent[ei][0]), take])
				cnt -= take
				left -= take
				if left == 0 and ei + 1 < ent.size():
					ei += 1
					left = int(ent[ei][1])
	var hbs: Array = at_hb.keys()
	hbs.sort()
	for hb4: int in hbs:
		var es: Array = at_hb[hb4]
		var rws := PackedInt64Array()
		var tot: int = 0
		for e: Array in es:
			rws.append(int(e[1]))
			tot += int(e[1])
		var hk := PackedFloat64Array()
		var htot: int = 0
		for k: int in NCLASS:
			hk.append(float(hh_men.get(hb4 * NCLASS + k, 0)))
			htot += int(hh_men.get(hb4 * NCLASS + k, 0))
		for k2: int in NCLASS:
			hk[k2] *= float(tot) / float(maxi(1, htot))
		if htot == 0:
			hk[CLASS_REST] = float(tot)
		var kcols: PackedInt64Array = _largest(hk, tot)
		# V114 (2): a class's wives at most its male heads, the excess pooled into the classes with male heads to spare (in class order);
		# what no class can take stays where it fell (the cross-tier wives, counted)
		var spill: int = 0
		for k5: int in NCLASS:
			var cap: int = int(hh_men.get(hb4 * NCLASS + k5, 0))
			if htot > 0 and kcols[k5] > cap:
				spill += kcols[k5] - cap
				kcols[k5] = cap
		for k6: int in NCLASS:
			var room: int = int(hh_men.get(hb4 * NCLASS + k6, 0)) - kcols[k6]
			if spill > 0 and room > 0:
				var mv: int = mini(spill, room)
				kcols[k6] += mv
				spill -= mv
		if spill > 0:
			kcols[CLASS_REST if htot == 0 else _largest_key(hh_men, hb4)] += spill
		var x2 := PackedFloat64Array()
		x2.resize(es.size() * NCLASS)
		for q: int in es.size():
			for k3: int in NCLASS:
				x2[q * NCLASS + k3] = float(rws[q]) * float(kcols[k3]) / float(maxi(1, tot))
		var z2: PackedInt64Array = _table_round(p, x2, rws, kcols, es.size(), NCLASS, "tier_pcls", key * BANDS + hb4)
		for q2: int in es.size():
			for k4: int in NCLASS:
				_member_add(members, hb4 * NCLASS + k4, int(es[q2][0]), 1, z2[q2 * NCLASS + k4])


## The class with the most male heads at householder band hb (ties to the lower class)
static func _largest_key(hh_men: Dictionary, hb: int) -> int:
	var best: int = CLASS_REST
	var most: int = -1
	for k: int in NCLASS:
		var n: int = int(hh_men.get(hb * NCLASS + k, 0))
		if n > most:
			most = n
			best = k
	return best


## A real nr x nk table x (rows and columns raked to the integer totals) to integers: each row by keyed systematic rounding, then the
## columns repaired along alternating paths with every cell kept at its floor or ceiling where a path exists
static func _table_round(p: RefCounted, x: PackedFloat64Array, rows: PackedInt64Array, cols: PackedInt64Array, nr: int, nk: int, tag: String, key: int) -> PackedInt64Array:
	var z := PackedInt64Array()
	z.resize(nr * nk)
	for r: int in nr:
		var rv := PackedFloat64Array()
		rv.resize(nk)
		for k: int in nk:
			rv[k] = x[r * nk + k]
		var ri: PackedInt64Array = _systematic(rv, rows[r], p.seed_v, tag, key * 64 + r)
		for k2: int in nk:
			z[r * nk + k2] = ri[k2]
	_repair(z, x, cols, nr, nk)
	return z


## The size classes of one household-bundle (prefecture, type, householder band, class): its H households from the D size shares on
## the type's allowed sizes (keyed systematic), then one size class up or down at a time (the 5+ class absorbing any remainder above
## five a household) until Σ size x households = its persons; the heads, the partners (one per household in the couple types) and
## the other members then split over the sizes with the rows exact and the sizes' persons as the columns
static func _household_sizes(p: RefCounted, c: int, t: int, hb: int, k: int, H0: int, mem: Dictionary, size_th: Dictionary, absent: int = 0) -> void:
	var H: int = H0 + absent
	var persons: int = absent
	for u in mem:
		for r in mem[u]:
			persons += int(mem[u][r])
	var lo: int = SIZE_MIN[t]
	var hi: int = SIZE_MAX[t]
	var sh: Array = size_th.get("%d,%d" % [t, hb], [1.0, 0.0, 0.0, 0.0, 0.0])
	var v := PackedFloat64Array()
	v.resize(5)
	var tot: float = 0.0
	for z: int in range(lo, hi + 1):
		v[z] = maxf(0.0, float(sh[z]))
		tot += v[z]
	for z2: int in range(lo, hi + 1):
		v[z2] = float(H) * (v[z2] / tot if tot > 0.0 else (1.0 if z2 == lo else 0.0))
	var hz: PackedInt64Array = _systematic(v, H, p.seed_v, "tier_size", ((c * NTYPE + t) * BANDS + hb) * NCLASS + k)
	var cap := PackedInt64Array()
	cap.resize(5)
	var used: int = 0
	for z3: int in 5:
		cap[z3] = hz[z3] * (z3 + 1)
		used += cap[z3]
	# up while persons remain (smallest first), down while persons are short (largest first)
	var guard: int = 0
	while used < persons and guard < 10000000:
		guard += 1
		var moved: bool = false
		for z4: int in range(lo, hi):
			if hz[z4] > 0:
				hz[z4] -= 1
				hz[z4 + 1] += 1
				used += 1
				moved = true
				break
		if not moved:
			break
	while used > persons:
		var moved2: bool = false
		for z5: int in range(hi, lo, -1):
			if hz[z5] > 0:
				hz[z5] -= 1
				hz[z5 - 1] += 1
				used -= 1
				moved2 = true
				break
		if not moved2:
			break
	if used > persons:
		p.tr_margins["hh_unfilled"] = int(p.tr_margins["hh_unfilled"]) + (used - persons)
		p.tr_margins["hh_unfilled_t"][t] = int(p.tr_margins["hh_unfilled_t"].get(t, 0)) + (used - persons)
	for z6: int in 5:
		cap[z6] = hz[z6] * (z6 + 1)
	cap[4] += maxi(0, persons - used)
	# the persons over the sizes: heads one per household, partners with their husbands in the couple types, the rest by capacity
	var us: Array = mem.keys()
	us.sort()
	var head_cols := PackedInt64Array()
	head_cols.resize(5)
	var part_cols := PackedInt64Array()
	part_cols.resize(5)
	var rest_cols := PackedInt64Array()
	rest_cols.resize(5)
	var couple_t: bool = t == 1 or t == 2 or t == 4
	var n_part: int = 0
	for u2 in us:
		n_part += int(mem[u2].get(1, 0)) if couple_t else 0
	for z7: int in 5:
		head_cols[z7] = mini(hz[z7], cap[z7])
	var out: Dictionary = {}   # size -> {u: {r: n}}
	_fill_sizes(p, mem, us, [0], head_cols, out, c, t, hb, k, 0)
	# TO_E 15:17 (1): a size's partners at most its male heads, in size order; the cross-tier rest by the room left, largest first
	# Why not one partner per household of each size (_cols_split, before): it ignored whose heads were men, and in type 4 the partners
	# went with the other members, 171,054 wives above their size-bundle's husbands
	var left: int = n_part
	for z8: int in 5:
		var mh: int = 0
		for u4 in (out.get(z8, {}) as Dictionary):
			if p.tr_key[int(u4) * KEY_STRIDE + 2] == 0:
				mh += int((out[z8][u4] as Dictionary).get(0, 0))
		part_cols[z8] = mini(left, mini(mh, maxi(0, cap[z8] - head_cols[z8])))
		left -= part_cols[z8]
	for z9: int in range(4, -1, -1):
		var room: int = maxi(0, cap[z9] - head_cols[z9] - part_cols[z9])
		var add: int = mini(left, room)
		part_cols[z9] += add
		left -= add
	for z10: int in 5:
		rest_cols[z10] = maxi(0, cap[z10] - head_cols[z10] - part_cols[z10])
	_fill_sizes(p, mem, us, [1] if couple_t else [], part_cols, out, c, t, hb, k, 1)
	_fill_sizes(p, mem, us, [1, 2, 3, 4] if not couple_t else [2, 3, 4], rest_cols, out, c, t, hb, k, 2)
	for z9: int in 5:
		if hz[z9] <= 0 and not out.has(z9):
			continue
		var hk: String = "%02d|%d|%02d|%d|%d" % [c, t, hb, z9, k]
		p.tr_hh[hk] = {"count": hz[z9], "members": out.get(z9, {})}
		if absent > 0:
			var hd9: int = 0
			for u9 in (out.get(z9, {}) as Dictionary):
				hd9 += int((out[z9][u9] as Dictionary).get(0, 0))
			p.tr_hh[hk]["cross"] = maxi(0, hz[z9] - hd9)


## The members of the given roles split over the sizes: rows (unit, role) exact, columns the sizes' room, by the table rounding
static func _fill_sizes(p: RefCounted, mem: Dictionary, us: Array, rset: Array, cols: PackedInt64Array, out: Dictionary, c: int, t: int, hb: int, k: int, pass_i: int) -> void:
	var rk: Array = []
	var rows := PackedInt64Array()
	for u in us:
		for r: int in rset:
			var n: int = int(mem[u].get(r, 0))
			if n > 0:
				rk.append([u, r])
				rows.append(n)
	if rk.is_empty():
		return
	var nr: int = rk.size()
	var tot_r: int = 0
	for q: int in nr:
		tot_r += rows[q]
	var tot_c: int = 0
	for z: int in 5:
		tot_c += cols[z]
	var cf := cols.duplicate()
	if tot_c != tot_r:
		# the room differs from the persons (an unfilled size class): the 5+ class takes the difference, never below 0
		cf[4] = maxi(0, cf[4] + tot_r - tot_c)
		tot_c = 0
		for z2: int in 5:
			tot_c += cf[z2]
		var zi: int = 0
		while tot_c > tot_r and zi < 5:
			var cut: int = mini(cf[zi], tot_c - tot_r)
			cf[zi] -= cut
			tot_c -= cut
			zi += 1
	var x := PackedFloat64Array()
	x.resize(nr * 5)
	var rf := PackedFloat64Array()
	rf.resize(nr)
	var cff := PackedFloat64Array()
	cff.resize(5)
	for q2: int in nr:
		rf[q2] = float(rows[q2])
		for z3: int in 5:
			x[q2 * 5 + z3] = float(rows[q2]) * float(cf[z3]) / float(maxi(1, tot_r))
	var z4: PackedInt64Array = _table_round(p, x, rows, cf, nr, 5, "tier_fill%d" % pass_i, ((c * NTYPE + t) * BANDS + hb) * NCLASS + k)
	for q3: int in nr:
		for z5: int in 5:
			var n2: int = z4[q3 * 5 + z5]
			if n2 <= 0:
				continue
			if not out.has(z5):
				out[z5] = {}
			var m: Dictionary = out[z5]
			var u2 = rk[q3][0]
			if not m.has(u2):
				m[u2] = {}
			m[u2][int(rk[q3][1])] = int(m[u2].get(int(rk[q3][1]), 0)) + n2


## The household sector's instruments (§9.2 F, §12.8 item 6): each instrument's end-2022 total in integer yen placed over the adult
## points (by mass) and the individuals by the keyed largest remainder over their weights, so Σ = R67c's total exactly. The weight
## of a holder: its instrument group's age profile (financial assets by householder age S, the non-financial by net wealth less
## financial assets D, the liabilities by the debt profile T, all from the spec) x its income over its age group's mean (T). Held
## per point, then per individual, as int64 yen
## Why not one closing factor on the drawn assets (T1): floats summed to 4 decimals of 兆円, and the drawn assets carried no age profile
static func _instruments(p: RefCounted) -> void:
	var ins: Dictionary = _v(p, "instruments_hh_trillion_yen")
	var prof: Dictionary = _v(p, "instrument_age_profiles")
	var n_pts: int = p.tr_pt_off[p.tr_units]
	var n_all: int = n_pts + p.n
	var inc: PackedFloat64Array = p.tr_points["income"]
	var ages: PackedInt32Array = p.tr_points["age"]
	var mass := PackedFloat64Array()
	mass.resize(n_all)
	var income := PackedFloat64Array()
	income.resize(n_all)
	var grp := PackedInt32Array()
	grp.resize(n_all)
	var g_inc := PackedFloat64Array()
	g_inc.resize(7)
	var g_n := PackedFloat64Array()
	g_n.resize(7)
	# Why not the householder's age, as the profiles are published: the holdings are per person, so it would give an adult child at
	# home its parents' profile on its own income, and at T1 a point has no one householder age (§12.10 V4)
	for g: int in n_all:
		var a: int = ages[g] if g < n_pts else p.age[g - n_pts]
		grp[g] = clampi(a / 10 - 2, 0, 6) if a >= ADULT_FROM else -1
		if grp[g] < 0:
			continue
		mass[g] = float(p.tr_pt_mass[g]) if g < n_pts else 1.0
		income[g] = inc[g] if g < n_pts else p.income[g - n_pts]
		g_inc[grp[g]] += income[g] * mass[g]
		g_n[grp[g]] += mass[g]
	p.tr_instruments = {}
	p.tr_instrument_factor = {}
	var names: Array = ins.keys()
	names.sort()
	for name: String in names:
		if name == "net_worth":
			continue
		var curve: Array = prof[String(prof["by_instrument"][name])]
		var w := PackedFloat64Array()
		w.resize(n_all)
		var tot: float = 0.0
		for g2: int in n_all:
			if grp[g2] < 0 or g_inc[grp[g2]] <= 0.0:
				continue
			w[g2] = mass[g2] * float(curve[grp[g2]]) * income[g2] / (g_inc[grp[g2]] / g_n[grp[g2]])
			tot += w[g2]
		var total_yen: int = int(round(float(ins[name]) * 10.0)) * 100000000000
		p.tr_instruments[name] = _keyed_largest(w, tot, total_yen, p.seed_v, "tier_ins_" + name)
		p.tr_instrument_factor[name] = tot
	_wealth_from_instruments(p, prof, n_pts)


## The one wealth record (§12.8 10.5): a point's and an individual's assets are its financial instruments' sum and its debt its
## borrowing, each ÷ its mass in 万円 a person, written once from the instruments
## Why not keeping the generator's own draw beside them: two records of wealth disagreed, and T2's decisions read one while the
## balance sheet read the other (M004 W6)
static func _wealth_from_instruments(p: RefCounted, prof: Dictionary, n_pts: int) -> void:
	var by: Dictionary = prof["by_instrument"]
	var fin: Array = []
	for name: String in p.tr_instruments:
		if String(by.get(name, "")) == "financial":
			fin.append(name)
	fin.sort()
	var assets: PackedFloat64Array = p.tr_points["assets"]
	var debt: PackedFloat64Array = p.tr_points["debt"]
	var bor: PackedInt64Array = p.tr_instruments["borrowing"]
	for g: int in n_pts:
		var a: int = 0
		for name2: String in fin:
			a += (p.tr_instruments[name2] as PackedInt64Array)[g]
		var m: float = float(p.tr_pt_mass[g])
		assets[g] = float(a) / m / 1e4 if m > 0.0 else 0.0
		debt[g] = float(bor[g]) / m / 1e4 if m > 0.0 else 0.0
	for i: int in p.n:
		var a2: int = 0
		for name3: String in fin:
			a2 += (p.tr_instruments[name3] as PackedInt64Array)[n_pts + i]
		p.tier_wealth(i, float(a2) / 1e4, float(bor[n_pts + i]) / 1e4)


## total (int64) over the weights w by the largest remainder, ties in a keyed order: the floors of total x w / tot, then one each to
## the largest fractional parts
static func _keyed_largest(w: PackedFloat64Array, tot: float, total: int, seed_v: int, tag: String) -> PackedInt64Array:
	var out := PackedInt64Array()
	out.resize(w.size())
	var fr: Array = []
	var used: int = 0
	for i: int in w.size():
		if w[i] <= 0.0:
			continue
		var x: float = float(total) * (w[i] / tot)
		out[i] = int(floor(x))
		used += out[i]
		fr.append([x - floor(x), preload("res://sim/earth_core/keyed.gd").raw(seed_v, tag, i, 0, 0), i])
	fr.sort_custom(func(a: Array, b: Array) -> bool: return float(a[0]) > float(b[0]) if a[0] != b[0] else int(a[1]) < int(b[1]))
	var left: int = total - used
	var q: int = 0
	while left > 0 and not fr.is_empty():
		out[int(fr[q % fr.size()][2])] += 1
		left -= 1
		q += 1
	while left < 0 and not fr.is_empty():
		var i2: int = int(fr[fr.size() - 1 - (q % fr.size())][2])
		if out[i2] > 0:
			out[i2] -= 1
			left += 1
		q += 1
	return out


## The report for T1s-k: units by tier size and class, persons covered, individuals
static func report(p: RefCounted) -> Dictionary:
	var by_size: Dictionary = {}
	var by_class: Dictionary = {}
	var persons: int = 0
	for u: int in p.tr_units:
		var us: int = p.tr_tier_size[u]
		by_size[us] = int(by_size.get(us, 0)) + 1
		for m: int in range(p.tr_mix_off[u], p.tr_mix_off[u + 1]):
			var k: int = p.tr_mix_code[m] / (NTYPE * NEMP)
			by_class[k] = int(by_class.get(k, 0)) + p.tr_mix_n[m]
		persons += p.tr_count[u]
	return {"units": p.tr_units, "individuals": p.n, "persons_in_bundles": persons, "by_unit_size": by_size, "persons_by_class": by_class, "households": p.tr_hh.size(), "k": p.tr_k, "points": p.tr_pt_off[p.tr_units], "points_target": p.tr_k * p.tr_units}


## §12.13 L_p in reals: per prefecture x band x sex [子 in a nuclear household, 子 in another] = 第13-2表's 2020 count over the cell's 2020
## imputed persons (R87, M017b: the age-unknown join the denominator, none of them 子) x the start's persons (base). Index
## (ci * BANDS * 2 + bs) * 2
## Why not the age-known persons (R76, before 14:24): the start's ages are complete, so they would overstate living at home by up
## to 4 points
static func _child_targets(p: RefCounted, codes: Array, base: PackedFloat64Array) -> PackedFloat64Array:
	var cr: Dictionary = (_v(p, "child_role") as Dictionary)["by_pref"]
	var au: Dictionary = (_v(p, "age_unknown") as Dictionary)["by_pref"]
	var nbs: int = BANDS * 2
	var out := PackedFloat64Array()
	out.resize(codes.size() * nbs * 2)
	for ci: int in codes.size():
		var key: String = str(codes[ci])
		for bs: int in nbs:
			var b: int = bs / 2
			var e: Array = cr[key]["m" if bs % 2 == 0 else "f"][b]
			var den: float = float(au[key]["m" if bs % 2 == 0 else "f"]["imputed"][b])
			if den <= 0.0:
				continue
			out[(ci * nbs + bs) * 2] = float(e[1]) / den * base[ci * nbs + bs]
			out[(ci * nbs + bs) * 2 + 1] = float(int(e[0]) - int(e[1])) / den * base[ci * nbs + bs]
	return out




## (1)-(3) of §12.12: the couples by prefecture, the husband's and the wife's R77 band (0 = 15-19 .. 14 = 85+) and type (1 couple-only,
## 2 couple + children, 4 other) in integers, keyed systematic per prefecture; their persons as fixed (prefecture, band x sex, type)
## cells. The couples are R77c's, 2020's aged to the start (§12.15), each cell clipped at its husband band's men and its wife band's
## women and the clip counted; the couple-only share is 第32表's over its coarse cell; the rest split into types 2 and 4 by (N), per
## husband 5-year band (§12.13)
## Why not the 2024 men x the 2020 share of men in couples (before): it puts 2020's P(wife | husband) on 2024's husbands, the period
## error behind T1s-alt (§12.15)
static func _r77_couples(p: RefCounted, codes: Array, base: PackedFloat64Array) -> Dictionary:
	var cba: Dictionary = _v(p, "couples_by_age")
	var cob: Dictionary = _v(p, "couple_only_by_age")
	var c24: Dictionary = (_v(p, "couples_2024") as Dictionary)["by_pref"]
	var nc: int = codes.size()
	var nbs: int = BANDS * 2
	var fixed := PackedInt64Array()
	fixed.resize(nc * nbs * NTYPE)
	var out: Dictionary = {}
	var nh: Dictionary = {}
	var total: int = 0
	var cpl := PackedFloat64Array()
	cpl.resize(nc * 225)
	var co_x := PackedFloat64Array()
	co_x.resize(nc * 225)
	var nhf := PackedFloat64Array()   # §12.12 (9): per cell the 2020 share of child couples, then of parent couples
	nhf.resize(nc * 450)
	var call_c := PackedFloat64Array()   # every couple of the cell, head and non-head
	call_c.resize(nc * 225)
	var nh_clip: float = 0.0
	var c24_clip: float = 0.0
	for ci: int in nc:
		var key: String = str(codes[ci])
		var tab: Array = cba["by_pref"][key]
		var cot: Array = cob["by_pref"][key]
		var t24: Array = c24[key]
		nh_clip += _r77_nonhead(p, key, tab, nhf, ci)
		var coarse_n := PackedFloat64Array()
		coarse_n.resize(49)
		for h0: int in 15:
			for w0: int in 15:
				coarse_n[_coarse(h0) * 7 + _coarse(w0)] += float(tab[h0][w0]) * (1.0 - nhf[ci * 450 + h0 * 15 + w0] - nhf[ci * 450 + 225 + h0 * 15 + w0])
		var rw := PackedFloat64Array()
		rw.resize(15)
		var cw := PackedFloat64Array()
		cw.resize(15)
		for h1: int in 15:
			for w1: int in 15:
				rw[h1] += float(t24[h1][w1])
				cw[w1] += float(t24[h1][w1])
		for hb: int in 15:
			if rw[hb] <= 0.0:
				continue
			var fm: float = minf(1.0, base[ci * nbs + (hb + 3) * 2] / rw[hb])
			for wb2: int in 15:
				var cv: float = float(t24[hb][wb2])
				if cv <= 0.0:
					continue
				var fc: float = minf(fm, base[ci * nbs + (wb2 + 3) * 2 + 1] / cw[wb2])
				c24_clip += cv * (1.0 - fc)
				var cc: int = _coarse(hb) * 7 + _coarse(wb2)
				call_c[ci * 225 + hb * 15 + wb2] = cv * fc
				cpl[ci * 225 + hb * 15 + wb2] = call_c[ci * 225 + hb * 15 + wb2] * (1.0 - nhf[ci * 450 + hb * 15 + wb2] - nhf[ci * 450 + 225 + hb * 15 + wb2])
				co_x[ci * 225 + hb * 15 + wb2] = cpl[ci * 225 + hb * 15 + wb2] * (minf(1.0, float(cot[_coarse(hb)][_coarse(wb2)]) / coarse_n[cc]) if coarse_n[cc] > 0.0 else 0.0)
	co_x = _r77_rake(p, codes, base, cpl, co_x)
	# §12.13 (N), at the husband's 5-year band (TO_E 15:55): the couples in type 4, nationally, as R77's couples less the husbands in
	# nuclear households (第13-2表's 5-year persons in nuclear households over the imputed persons x the start's men, per prefecture, less
	# L's nuclear 子 men less the single-parent heads), floored at R84's non-head couples and capped at the couples not couple-only; the
	# head couples' share in type 4 then the same in every prefecture and cell of the band (T)
	# Why not R64's type 2 : 4 ratio of households (1ab2caab): one ratio for every band put twice the census's type-4 couples under 55
	# and too few at 55-74 (TO_PM 47)
	# Why not the husband's 10-year band (858548f8): its step filled the first 5-year half of each band's type 2 with wives, leaving the
	# daughters no room (TO_PM 50's alternation)
	var five0: Array = _five_shares(p)
	var ct: PackedFloat64Array = _child_targets(p, codes, base)
	var role_tbs: Dictionary = _v(p, "role_by_type_band_sex")
	var crp: Dictionary = (_v(p, "child_role") as Dictionary)["by_pref"]
	var aup: Dictionary = (_v(p, "age_unknown") as Dictionary)["by_pref"]
	var n4 := PackedFloat64Array()   # per 5-year band: all couples, non-head, couple-only, head not couple-only, nuclear men, L nuclear men, single-parent heads
	n4.resize(BANDS * 7)
	for ci: int in nc:
		var key0: String = str(codes[ci])
		for q0: int in 225:
			var g0: int = q0 / 15 + 3
			n4[g0 * 7] += call_c[ci * 225 + q0]
			n4[g0 * 7 + 1] += call_c[ci * 225 + q0] * (nhf[ci * 450 + q0] + nhf[ci * 450 + 225 + q0])
			n4[g0 * 7 + 2] += co_x[ci * 225 + q0]
			n4[g0 * 7 + 3] += cpl[ci * 225 + q0] - co_x[ci * 225 + q0]
		for b0: int in range(3, BANDS):
			var nm: float = base[ci * nbs + b0 * 2]
			var imp: float = float(aup[key0]["m"]["imputed"][b0])
			n4[b0 * 7 + 4] += float(crp[key0]["m"][b0][3]) / imp * nm if imp > 0.0 else 0.0
			n4[b0 * 7 + 5] += ct[(ci * nbs + b0 * 2) * 2]
			var sh: Array = role_tbs.get("3,%d,0" % b0, [0.0, 0.0, 0.0, 0.0, 0.0])
			var st: float = 0.0
			for r0: int in 5:
				st += maxf(0.0, float(sh[r0]))
			n4[b0 * 7 + 6] += float(five0[0][b0][3]) * nm * (maxf(0.0, float(sh[0])) / st if st > 0.0 else 0.0)
	var s4 := PackedFloat64Array()
	s4.resize(BANDS)
	var n4_rep: Dictionary = {}
	for g2: int in range(3, BANDS):
		var e: int = g2 * 7
		var raw: float = n4[e] - (n4[e + 4] - n4[e + 5] - n4[e + 6])
		var t4: float = clampf(raw, n4[e + 1], n4[e + 1] + n4[e + 3])
		s4[g2] = (t4 - n4[e + 1]) / n4[e + 3] if n4[e + 3] > 0.0 else 0.0
		n4_rep[g2] = [n4[e], n4[e + 1], raw, t4, n4[e + 4], n4[e + 5], n4[e + 6]]
	# §12.16 (3), M022: the couples spent once; type 4's couples at 2020's within-couple share of the husband band, raked to the
	# prefecture's census 2020 couple-only and couple + children counts, couple + children the rest (a shortfall taken from type 4,
	# counted in t2_clip); the single-headed 'other' households per prefecture, 2020's x IPSS's 'other' ratio (h4s)
	# Why not (N)'s share with type 2 scaled to IPSS (§12.13-12.14, before): IPSS's couple types use IPSS's couples, 1.5 M above R77c's,
	# and each one-type fix moved the shortfall to the next type (M022 §1)
	var m22: Dictionary = _v(p, "m022_within_couple")
	var cen: Dictionary = (_v(p, "household_target") as Dictionary)["census_2020"]
	var t2_clip: float = 0.0
	var h4s: Dictionary = {}
	for ci: int in nc:
		var key2: String = str(codes[ci])
		var tab2: Array = cba["by_pref"][key2]
		var d1: float = 0.0
		var d2: float = 0.0
		var c20t: float = 0.0
		var nh20: float = 0.0
		for h3: int in 15:
			for w3: int in 15:
				var x3: float = float(tab2[h3][w3])
				d1 += float(m22["s1"][h3]) * x3
				d2 += float(m22["s2"][h3]) * x3
				c20t += x3
				nh20 += x3 * (nhf[ci * 450 + h3 * 15 + w3] + nhf[ci * 450 + 225 + h3 * 15 + w3])
		var f1: float = float(cen[key2][1]) / d1 if d1 > 0.0 else 0.0
		var f2: float = float(cen[key2][2]) / d2 if d2 > 0.0 else 0.0
		var s4p := PackedFloat64Array()
		s4p.resize(15)
		for h4: int in 15:
			s4p[h4] = maxf(0.0, 1.0 - f1 * float(m22["s1"][h4]) - f2 * float(m22["s2"][h4]))
		h4s[codes[ci]] = maxf(0.0, (float(cen[key2][4]) - (c20t - float(cen[key2][1]) - float(cen[key2][2]) - nh20)) * float(m22["other_ratio"]))
		var v := PackedFloat64Array()
		var keys: Array = []
		for hb: int in 15:
			for wb2: int in 15:
				var c: float = cpl[ci * 225 + hb * 15 + wb2]
				var call: float = call_c[ci * 225 + hb * 15 + wb2]
				if call <= 0.0:
					continue
				# Why not the values as they come: co_x can sit a rounding error above c, and a negative weight rounds to a negative count that
				# the loop below skips, so the prefecture placed one couple more than its total (T1s-cpb, Gifu)
				var co: float = minf(co_x[ci * 225 + hb * 15 + wb2], c)
				var r2: float = call - co - maxf(s4p[hb] * call, call - c)
				var c2: float = maxf(0.0, r2)
				t2_clip += c2 - r2
				for tt: Array in [[1, co], [2, c2], [4, maxf(0.0, c - co - c2)], [NH_CHILD, call * nhf[ci * 450 + hb * 15 + wb2]], [NH_PARENT, call * nhf[ci * 450 + 225 + hb * 15 + wb2]]]:
					v.append(float(tt[1]))
					keys.append([hb, wb2, int(tt[0])])
		var tot: float = 0.0
		for x: float in v:
			tot += x
		var ints: PackedInt64Array = _systematic(v, int(floor(tot + 0.5)), p.seed_v, "tier_r77", ci)
		for q: int in ints.size():
			if ints[q] <= 0:
				continue
			var k: Array = keys[q]
			var t5: int = int(k[2])
			if t5 >= NH_CHILD:
				nh["%d|%d|%d|%d" % [codes[ci], int(k[0]), int(k[1]), t5 - NH_CHILD]] = ints[q]
				t5 = 4
			else:
				out["%d|%d|%d|%d" % [codes[ci], int(k[0]), int(k[1]), t5]] = ints[q]
			fixed[(ci * nbs + (int(k[0]) + 3) * 2) * NTYPE + t5] += ints[q]
			fixed[(ci * nbs + (int(k[1]) + 3) * 2 + 1) * NTYPE + t5] += ints[q]
			total += ints[q]
	return {"fixed": fixed, "couples": out, "nonhead": nh, "nh_clip": nh_clip, "total": total, "rake": p.tr_margins.get("r77_rake", {}), "n4": n4_rep, "t2_clip": t2_clip, "c24_clip": c24_clip, "h4s": h4s}


## §12.12 (9) the non-head couples of one prefecture in 2020 (R84, D): child couples from the children's spouses (a woman: the wife's band,
## the husband's by R77's P(husband | wife); a man: the reverse), parent couples R77 - the head's spouses - the child couples, their
## husbands by the head's parents' men, the wives by R77's P(wife | husband); written into nhf as shares of each R77 cell (child at
## ci * 450, parent at + 225), each cell's two at most 1. Returns the couples clipped (parent couples below 0, cells over 1)
static func _r77_nonhead(p: RefCounted, key: String, tab: Array, nhf: PackedFloat64Array, ci: int) -> float:
	var nh: Dictionary = (_v(p, "nonhead_couples") as Dictionary)["by_pref"][key]
	var cc := PackedFloat64Array()
	cc.resize(225)
	var pc := PackedFloat64Array()
	pc.resize(225)
	var rowt := PackedFloat64Array()
	rowt.resize(15)
	var colt := PackedFloat64Array()
	colt.resize(15)
	var all: float = 0.0
	for h: int in 15:
		for w: int in 15:
			rowt[h] += float(tab[h][w])
			colt[w] += float(tab[h][w])
			all += float(tab[h][w])
	var nch: float = 0.0
	for b: int in 15:
		var fw: float = float(nh["child_spouse_f"][b])
		var mh: float = float(nh["child_spouse_m"][b])
		nch += fw + mh
		for o: int in 15:
			if colt[b] > 0.0:
				cc[o * 15 + b] += fw * float(tab[o][b]) / colt[b]
			if rowt[b] > 0.0:
				cc[b * 15 + o] += mh * float(tab[b][o]) / rowt[b]
	var npc: float = all - float(nh["head_spouses"]) - nch
	var clip: float = maxf(0.0, -npc)
	npc = maxf(0.0, npc)
	var pt: float = 0.0
	for b2: int in 15:
		pt += float(nh["parents_m"][b2])
	for h2: int in 15:
		var nhh: float = npc * float(nh["parents_m"][h2]) / pt if pt > 0.0 else 0.0
		for w2: int in 15:
			if rowt[h2] > 0.0:
				pc[h2 * 15 + w2] = nhh * float(tab[h2][w2]) / rowt[h2]
	for q: int in 225:
		var n: float = float(tab[q / 15][q % 15])
		if n <= 0.0:
			clip += cc[q] + pc[q]
			continue
		var s: float = (cc[q] + pc[q]) / n
		var f: float = 1.0 / s if s > 1.0 else 1.0
		clip += (cc[q] + pc[q]) * (1.0 - f)
		nhf[ci * 450 + q] = cc[q] * f / n
		nhf[ci * 450 + 225 + q] = pc[q] * f / n
	return clip


## §12.12 (3) AMENDED (V111 (2)): the couple-only cells x(p, hb, wb) raked by IPF to (A) 第32表's coarse cells per prefecture (their
## start values, the 2024 couples x the 2020 coarse share), (B) 表V-1-3's couple-only men by husband band and (C) its women by wife
## band, nationally, (B) and (C) inside the under-60 coarse group only and scaled to (A)'s national total there; each cell at most its
## couples cpl (the capped cells held, the rest scaled); 20-59 only, since R77's couples cap 15-19 below 表V-1-3's couple-only share. The worst relative errors of (A), (B), (C) and the couple-only persons by band x
## sex before and after against 表V-1-3 x the start go to tr_margins["r77_rake"]
## Why not (B) and (C) at their own level: (A) fixes the national under-60 total, and two levels of one total cannot both hold
static func _r77_rake(p: RefCounted, codes: Array, base: PackedFloat64Array, cpl: PackedFloat64Array, x0: PackedFloat64Array) -> PackedFloat64Array:
	var nc: int = codes.size()
	var nbs: int = BANDS * 2
	var tbs: Array = _v(p, "type_by_band_sex")
	var x: PackedFloat64Array = x0.duplicate()
	var a := PackedFloat64Array()
	a.resize(nc * 49)
	for ci: int in nc:
		for q: int in 225:
			a[ci * 49 + _coarse(q / 15) * 7 + _coarse(q % 15)] += x0[ci * 225 + q]
	var tab := PackedFloat64Array()   # 表V-1-3 x the start: couple-only men by band (0-14), then women
	tab.resize(30)
	for b: int in 15:
		for s: int in 2:
			var n: float = 0.0
			for ci2: int in nc:
				n += base[ci2 * nbs + (b + 3) * 2 + s]
			tab[s * 15 + b] = float(tbs[s][b + 3][1]) * n
	var tgt := PackedFloat64Array()
	tgt.resize(30)
	for s2: int in 2:
		var g: float = 0.0
		var tb: float = 0.0
		for b2: int in range(1, 9):
			tb += tab[s2 * 15 + b2]
			for ci3: int in nc:
				for o: int in 15:
					g += x0[ci3 * 225 + (b2 * 15 + o if s2 == 0 else o * 15 + b2)]
		for b3: int in range(1, 9):
			tgt[s2 * 15 + b3] = g * tab[s2 * 15 + b3] / tb if tb > 0.0 else 0.0
	var err := PackedFloat64Array([0.0, 0.0, 0.0])
	var worst_a: Array = []
	for it: int in 200:
		for ci4: int in nc:
			var cells: Array = []
			for k: int in 49:
				cells.append(PackedInt64Array())
			for q2: int in 225:
				var k2: int = _coarse(q2 / 15) * 7 + _coarse(q2 % 15)
				cells[k2].append(ci4 * 225 + q2)
			for k3: int in 49:
				_rake_group(x, cpl, cells[k3], a[ci4 * 49 + k3])
		for s3: int in 2:
			for b4: int in range(1, 9):
				var idx := PackedInt64Array()
				for ci5: int in nc:
					for o2: int in 15:
						idx.append(ci5 * 225 + (b4 * 15 + o2 if s3 == 0 else o2 * 15 + b4))
				_rake_group(x, cpl, idx, tgt[s3 * 15 + b4])
	for ci6: int in nc:
		var sa := PackedFloat64Array()
		sa.resize(49)
		for q3: int in 225:
			sa[_coarse(q3 / 15) * 7 + _coarse(q3 % 15)] += x[ci6 * 225 + q3]
		for k4: int in 49:
			if a[ci6 * 49 + k4] > 0.0 and absf(sa[k4] / a[ci6 * 49 + k4] - 1.0) > err[0]:
				err[0] = absf(sa[k4] / a[ci6 * 49 + k4] - 1.0)
				worst_a = [codes[ci6], k4 / 7, k4 % 7, a[ci6 * 49 + k4], sa[k4]]
	var before := PackedFloat64Array()
	before.resize(30)
	var after := PackedFloat64Array()
	after.resize(30)
	for ci7: int in nc:
		for q4: int in 225:
			before[q4 / 15] += x0[ci7 * 225 + q4]
			before[15 + q4 % 15] += x0[ci7 * 225 + q4]
			after[q4 / 15] += x[ci7 * 225 + q4]
			after[15 + q4 % 15] += x[ci7 * 225 + q4]
	var worst_b: Array = [[], []]
	for s4: int in 2:
		for b5: int in 9:
			if tgt[s4 * 15 + b5] > 0.0 and absf(after[s4 * 15 + b5] / tgt[s4 * 15 + b5] - 1.0) > err[1 + s4]:
				err[1 + s4] = absf(after[s4 * 15 + b5] / tgt[s4 * 15 + b5] - 1.0)
				worst_b[s4] = [b5, tgt[s4 * 15 + b5], after[s4 * 15 + b5]]
	p.tr_margins["r77_rake"] = {"err": err, "before": before, "after": after, "table": tab, "worst": [worst_a, worst_b]}
	return x


## One margin of the rake: the cells idx of x scaled to sum to t, each at most cap; the capped cells are held and the rest rescaled
static func _rake_group(x: PackedFloat64Array, cap: PackedFloat64Array, idx: PackedInt64Array, t: float) -> void:
	for rep_i: int in 8:
		var held: float = 0.0
		var free: float = 0.0
		for i: int in idx:
			if x[i] >= cap[i]:
				held += x[i]
			else:
				free += x[i]
		if free <= 0.0:
			return
		var f: float = (t - held) / free
		if absf(f - 1.0) < 1e-12:
			return
		var hit: bool = false
		for i2: int in idx:
			if x[i2] < cap[i2]:
				x[i2] = x[i2] * maxf(0.0, f)
				if x[i2] > cap[i2]:
					x[i2] = cap[i2]
					hit = true
		if not hit:
			return


## R77's 5-year band index (0 = 15-19 .. 14 = 85+) to 第32表's coarse band (0 = under 60, 1 = 60-64 .. 6 = 85+)
static func _coarse(b: int) -> int:
	return 0 if b < 9 else b - 8



## The couple types' roles from R77 (§12.12 (5)): each band's husbands (the couples at that husband band) are heads and its wives
## partners, dealt over the band x sex's entries in proportion to their persons (keyed, within each entry's count). A spouse the bundles
## lack (a top-0.01% individual) is a cross-tier couple (§12.12 (7)), counted. The rest: couple-only none (reported), couple +
## children children, "other" by the role shares without the partner (its heads first held to R64's households less the couples)
static func _r77_roles(p: RefCounted, c: int, t: int, ents: Array, role_tbs: Dictionary, want_h: int, nhr: Array, lt: Dictionary) -> Array:
	var ne: int = ents.size()
	var hw := PackedInt64Array()
	hw.resize(BANDS)
	var ww := PackedInt64Array()
	ww.resize(BANDS)
	for key: String in p.tr_couples:
		var k: PackedStringArray = key.split("|")
		if int(k[0]) != c or int(k[3]) != t:
			continue
		hw[int(k[1]) + 3] += int(p.tr_couples[key])
		ww[int(k[2]) + 3] += int(p.tr_couples[key])
	var roles: Array = []
	for j: int in ne:
		roles.append(PackedInt64Array([0, 0, 0, 0, 0]))
	var cross := PackedInt64Array([0, 0])
	for b: int in BANDS:
		for s: int in 2:
			var want: int = hw[b] if s == 0 else ww[b]
			var idx: Array = []
			var avail: int = 0
			for j2: int in ne:
				if int(ents[j2][1]) == b and int(ents[j2][2]) == s:
					idx.append(j2)
					avail += int(ents[j2][4])
			var take: int = mini(want, avail)
			cross[s] += want - take
			if want > take:
				var cc: Dictionary = p.tr_margins.get("r77_cross_cells", {})
				cc["%d|%d|%d" % [c, b, s]] = int(cc.get("%d|%d|%d" % [c, b, s], 0)) + want - take
				p.tr_margins["r77_cross_cells"] = cc
			if take <= 0:
				continue
			var cap := PackedInt64Array()
			var v := PackedFloat64Array()
			for j3: int in idx:
				cap.append(int(ents[j3][4]))
				v.append(float(ents[j3][4]) * float(take) / float(avail))
			var q: PackedInt64Array = _capped(v, cap, take, p.seed_v, "tier_r77_role", (c * NTYPE + t) * BANDS * 2 + b * 2 + s)
			for i: int in idx.size():
				roles[int(idx[i])][s] = q[i]
	var rest1: int = 0
	if t == 4:
		_r77_nh_roles(p, c, ents, roles, nhr)
		_r77_other_heads(p, c, ents, roles, role_tbs, want_h, nhr)
		_l_children(p, c, ents, roles, nhr, lt)
	for j4: int in ne:
		var rc: PackedInt64Array = roles[j4]
		var rest: int = int(ents[j4][4]) - rc[0] - rc[1] - rc[2] - rc[3] - rc[4] - (int(nhr[j4][0]) + int(nhr[j4][1]) if t == 4 else 0)
		if rest <= 0:
			continue
		if t == 1:
			rc[4] += rest
			rest1 += rest
		elif t == 2:
			rc[2] += rest
		else:
			var sh: Array = role_tbs.get("%d,%d,%d" % [t, int(ents[j4][1]), int(ents[j4][2])], [1.0, 0.0, 0.0, 0.0, 0.0])
			# §12.13 L: type 4's children were set by _l_children, so the rest goes to the parent and other roles
			var v2 := PackedFloat64Array([0.0, 0.0, 0.0 if t == 4 else maxf(0.0, float(sh[2])), maxf(0.0, float(sh[3])), maxf(0.0, float(sh[4]))])
			if v2[2] + v2[3] + v2[4] <= 0.0:
				v2[4] = 1.0
			var vt: float = v2[2] + v2[3] + v2[4]
			for r: int in 5:
				v2[r] *= float(rest) / vt
			var add: PackedInt64Array = _systematic(v2, rest, p.seed_v, "tier_r77_rest", int(ents[j4][5]))
			for r2: int in 5:
				rc[r2] += add[r2]
		roles[j4] = rc
	p.tr_margins["r77_cross_husband"] = int(p.tr_margins.get("r77_cross_husband", 0)) + cross[0]
	p.tr_margins["r77_cross_wife"] = int(p.tr_margins.get("r77_cross_wife", 0)) + cross[1]
	p.tr_margins["r77_type1_rest"] = int(p.tr_margins.get("r77_type1_rest", 0)) + rest1
	return roles


## §12.13 step 7, the parent window (amended 5762e310): one entry's m parent-role persons over the head bands holding heads, in
## proportion to the heads x R83's density for the head's birth year at the gap (parent band - head band, the mother's table, T), the
## decaying epsilon by distance outside the window (M015); keyed systematic, each band's share over its classes (_member_by_class)
## Why not "b - 6, the nearest head band" (before): the open 85+ band mapped to one head band, 89.5% of the 85+ with heads 50-59 and the
## 60-69 heads with almost none (TO_PM 47)
static func _parent_window(p: RefCounted, by_hb: PackedInt64Array, members: Dictionary, hh_heads: Dictionary, ent: Array, m: int, dens: PackedFloat64Array) -> void:
	var pb: int = int(ent[1])
	var w := PackedFloat64Array()
	w.resize(BANDS)
	var lo: float = 1e300
	for hb: int in BANDS:
		var g: int = pb - hb
		if by_hb[hb] > 0 and g >= 1 and g <= 12 and dens[(hb * 2) * 13 + g] > 0.0:
			w[hb] = float(by_hb[hb]) * dens[(hb * 2) * 13 + g]
			lo = minf(lo, dens[(hb * 2) * 13 + g])
	var e0: float = 1e-6 * (lo if lo < 1e300 else 1.0)
	for hb2: int in BANDS:
		if by_hb[hb2] <= 0 or w[hb2] > 0.0 or _no_pair(pb - hb2, pb, hb2):
			continue
		var d: int = 13
		for hb3: int in BANDS:
			var g3: int = pb - hb3
			if g3 >= 1 and g3 <= 12 and dens[(hb3 * 2) * 13 + g3] > 0.0:
				d = mini(d, absi(hb3 - hb2))
		w[hb2] = float(by_hb[hb2]) * e0 * DM.pow(0.01, float(maxi(1, d)) - 1.0)
	var tot: float = 0.0
	for x: float in w:
		tot += x
	# Why not leave them out (before): with M019 (2)'s structural zeros a parent of 20-24 with no head under 20 had no band, and the
	# persons fell out of every household (T1s-b's 3 bundles at R77c's first T1 run); they are no one's parent, so they take the 'other'
	# role at the nearest head band, counted
	if tot <= 0.0:
		var hb0: int = _nearest_hb(by_hb, pb)
		_member_by_class(p, members, hh_heads, hb0, int(ent[0]), 4, m, "tier_mem", int(ent[5]) * 8 + 3)
		p.tr_margins["parent_none"] = int(p.tr_margins.get("parent_none", 0)) + m
		return
	for hb4: int in BANDS:
		w[hb4] *= float(m) / tot
	var ints: PackedInt64Array = _systematic(w, m, p.seed_v, "tier_parent", int(ent[5]))
	for hb5: int in BANDS:
		if ints[hb5] > 0:
			_member_by_class(p, members, hh_heads, hb5, int(ent[0]), 3, ints[hb5], "tier_mem", int(ent[5]) * 8 + 3)
			var gk: String = "%d|%d" % [pb, hb5]
			var pw: Dictionary = p.tr_margins.get("parent_window", {})
			pw[gk] = int(pw.get(gk, 0)) + ints[hb5]
			p.tr_margins["parent_window"] = pw


## §12.13 L as a share within its type (M019 (1), TO_E 15:51): per "code|band|sex" 第13-2表's 2020 子 over its persons in the same family
## type, the non-nuclear (kind 1, for type 4) or the nuclear (kind 0, for types 2-3)
## Why not 子 over all persons x the start's persons (319ddfb7): the type-4 target falls 7.1% and a share of all persons did not, so
## 1.14 M of L's children had no room (M019 §1)
static func _l_other(p: RefCounted, kind: int = 1) -> Dictionary:
	var cr: Dictionary = (_v(p, "child_role") as Dictionary)["by_pref"]
	var out: Dictionary = {}
	for key: String in cr:
		if key == "0":
			continue
		for s: int in 2:
			for b: int in BANDS:
				var e: Array = cr[key]["m" if s == 0 else "f"][b]
				var den: float = float(e[4]) if kind == 1 else float(e[3])
				var num: float = float(int(e[0]) - int(e[1])) if kind == 1 else float(e[1])
				out["%d|%d|%d" % [int(key), b, s]] = num / den if den > 0.0 else 0.0
	return out


## §12.13 L at the role step (type 4): per band x sex the entries' persons left after the couples and the heads give the child role up
## to L's non-nuclear share x the type-4 persons there (integer nearest), in proportion to what each entry has left (keyed); the rest of L is clipped into
## tr_margins["lc_clip"]. The parent and other roles then share what remains (_r77_roles' rest)
static func _l_children(p: RefCounted, c: int, ents: Array, roles: Array, nhr: Array, lt: Dictionary) -> void:
	var clip: Dictionary = p.tr_margins["lc_clip"]
	for b: int in BANDS:
		for s: int in 2:
			var persons: int = 0
			for j0: int in ents.size():
				if int(ents[j0][1]) == b and int(ents[j0][2]) == s:
					persons += int(ents[j0][4])
			var want: int = int(round(float(lt.get("%d|%d|%d" % [c, b, s], 0.0)) * float(persons)))
			if want <= 0:
				continue
			var idx: Array = []
			var cap := PackedInt64Array()
			var v := PackedFloat64Array()
			var room: int = 0
			for j: int in ents.size():
				if int(ents[j][1]) == b and int(ents[j][2]) == s:
					var rc: PackedInt64Array = roles[j]
					var r: int = maxi(0, int(ents[j][4]) - rc[0] - rc[1] - rc[2] - rc[3] - rc[4] - int(nhr[j][0]) - int(nhr[j][1]))
					idx.append(j)
					cap.append(r)
					room += r
			var take: int = mini(want, room)
			if take < want:
				clip["%d|%d" % [b, s]] = int(clip.get("%d|%d" % [b, s], 0)) + want - take
			if take <= 0:
				continue
			for q: int in idx.size():
				v.append(float(cap[q]) * float(take) / float(room))
			var ints: PackedInt64Array = _capped(v, cap, take, p.seed_v, "tier_lchild", (c * BANDS + b) * 2 + s)
			for q2: int in idx.size():
				var rc2: PackedInt64Array = roles[int(idx[q2])]
				rc2[2] += ints[q2]
				roles[int(idx[q2])] = rc2


## The partners' (wife band x sex, husband band) table of one prefecture x type from R77's couples, each wife band's row cut to its
## partners in the bundles (largest remainder) where a wife is a top-0.01% individual
static func _r77_z(p: RefCounted, c: int, t: int, ents: Array, roles: Array) -> PackedInt64Array:
	var z := PackedInt64Array()
	z.resize(BANDS * 2 * BANDS)
	for key: String in p.tr_couples:
		var k: PackedStringArray = key.split("|")
		if int(k[0]) != c or int(k[3]) != t:
			continue
		z[((int(k[2]) + 3) * 2 + 1) * BANDS + int(k[1]) + 3] += int(p.tr_couples[key])
	var have := PackedInt64Array()
	have.resize(BANDS * 2)
	for j: int in ents.size():
		have[int(ents[j][1]) * 2 + int(ents[j][2])] += roles[j][1]
	for rb: int in BANDS * 2:
		var row := PackedFloat64Array()
		var rt: int = 0
		for hb: int in BANDS:
			row.append(float(z[rb * BANDS + hb]))
			rt += z[rb * BANDS + hb]
		if rt == have[rb]:
			continue
		var cut: PackedInt64Array = _largest(row, have[rb]) if rt > 0 else PackedInt64Array()
		for hb2: int in BANDS:
			z[rb * BANDS + hb2] = cut[hb2] if rt > 0 else 0
	return z



## §12.12 (9) the non-head couples' persons of one prefecture in "other": each (band, sex)'s child-couple and parent-couple persons dealt
## over the band x sex's entries in proportion to their persons after the heads and partners (keyed, capped), into nhr[j] = [child,
## parent]; persons the entries lack go to tr_margins["nh_short"]
static func _r77_nh_roles(p: RefCounted, c: int, ents: Array, roles: Array, nhr: Array) -> void:
	var want := PackedInt64Array()
	want.resize(BANDS * 2 * 2)
	for key: String in p.tr_nh_couples:
		var k: PackedStringArray = key.split("|")
		if int(k[0]) != c:
			continue
		var n: int = int(p.tr_nh_couples[key])
		var kind: int = int(k[3])
		want[((int(k[1]) + 3) * 2) * 2 + kind] += n
		want[((int(k[2]) + 3) * 2 + 1) * 2 + kind] += n
	for bs: int in BANDS * 2:
		for kind2: int in 2:
			var w: int = want[bs * 2 + kind2]
			if w <= 0:
				continue
			var idx: Array = []
			var cap := PackedInt64Array()
			var v := PackedFloat64Array()
			var avail: int = 0
			for j: int in ents.size():
				if int(ents[j][1]) * 2 + int(ents[j][2]) == bs:
					var room: int = maxi(0, int(ents[j][4]) - roles[j][0] - roles[j][1] - int(nhr[j][0]) - int(nhr[j][1]))
					idx.append(j)
					cap.append(room)
					avail += room
			var take: int = mini(w, avail)
			if take < w:
				p.tr_margins["nh_short"] = int(p.tr_margins.get("nh_short", 0)) + w - take
			if take <= 0:
				continue
			for q: int in idx.size():
				v.append(float(cap[q]) * float(take) / float(avail))
			var ints: PackedInt64Array = _capped(v, cap, take, p.seed_v, "tier_nh_role", (c * BANDS * 2 + bs) * 2 + kind2)
			for q2: int in idx.size():
				nhr[int(idx[q2])][kind2] = int(nhr[int(idx[q2])][kind2]) + ints[q2]


## "Other" households' heads in no couple: R64's households less the couples' heads, dealt over the entries' persons in no couple in
## proportion to the role shares' head share (keyed, within each entry); written into roles[j][0] beside the couple heads
## Why not the role shares' head share alone: it is the share among all the type's persons, couples' heads included (2.2 M too many)
static func _r77_other_heads(p: RefCounted, c: int, ents: Array, roles: Array, role_tbs: Dictionary, want_h: int, nhr: Array) -> void:
	var ch: int = 0
	var cap := PackedInt64Array()
	var v := PackedFloat64Array()
	var avail: int = 0
	for j: int in ents.size():
		ch += roles[j][0]
		var rest: int = maxi(0, int(ents[j][4]) - roles[j][0] - roles[j][1] - int(nhr[j][0]) - int(nhr[j][1]))
		var sh: Array = role_tbs.get("4,%d,%d" % [int(ents[j][1]), int(ents[j][2])], [1.0, 0.0, 0.0, 0.0, 0.0])
		cap.append(rest if int(ents[j][1]) * 5 >= ADULT_FROM else 0)
		v.append(float(cap[j]) * maxf(0.0, float(sh[0])))
		avail += cap[j]
	var want: int = mini(avail, maxi(0, want_h - ch)) if want_h >= 0 else 0
	var vt: float = 0.0
	for x: float in v:
		vt += x
	if want <= 0:
		return
	for j2: int in v.size():
		v[j2] = v[j2] * float(want) / vt if vt > 0.0 else float(cap[j2]) * float(want) / float(maxi(1, avail))
	var q: PackedInt64Array = _capped(v, cap, want, p.seed_v, "tier_r77_heads", c)
	for j3: int in ents.size():
		roles[j3][0] += q[j3]


## T2.1 at month 0 (§14.2c; declared f7762c98, 57c1d540; amended for §12.12 f8834ff5, 145c7549, a1173165): the points' masses by
## single age (1), by household-bundle and role (3), the start's couple points (4, 5) and the marital states (6); (2) is birth_months()
static func build_t21(p: RefCounted) -> void:
	p.tr_hh_keys = PackedStringArray(p.tr_hh.keys())
	p.tr_hh_keys.sort()
	_age_layout(p)
	_role_layout(p)
	_couples(p)
	_nh_couple_points(p)
	_marital(p)
	_t22_start(p)


## A unit's points in a keyed permutation (the tag's order), as indices into the point arrays
static func _point_order(p: RefCounted, u: int, tag: String) -> Array:
	var rows: Array = []
	for j: int in range(p.tr_pt_off[u], p.tr_pt_off[u + 1]):
		rows.append([KEYED.u(p.seed_v, tag, u, j - p.tr_pt_off[u], 0), j])
	rows.sort()
	var out: Array = []
	for r: Array in rows:
		out.append(int(r[1]))
	return out


## Two partitions of one total laid end to end over [0, total), each in its given order: the integer overlaps [i, j, n] of segment i of
## a and segment j of b, n > 0, in order. Σ_j n = a[i] and Σ_i n = b[j] when Σ a = Σ b
static func _overlap(a: Array, b: Array) -> Array:
	var out: Array = []
	var i: int = 0
	var j: int = 0
	var ra: int = int(a[0]) if a.size() > 0 else 0
	var rb: int = int(b[0]) if b.size() > 0 else 0
	while i < a.size() and j < b.size():
		if ra == 0:
			i += 1
			ra = int(a[i]) if i < a.size() else 0
			continue
		if rb == 0:
			j += 1
			rb = int(b[j]) if j < b.size() else 0
			continue
		var n: int = mini(ra, rb)
		out.append([i, j, n])
		ra -= n
		rb -= n
	return out


## (1) each point's mass over its unit's single ages: the points in a keyed order against the ages in order
## Why not an IPF of the independence seed and a rounding: the layout is that table's exact integer form, with no rounding to verify
## Why the keyed order: in index order the first points would take the youngest ages
static func _age_layout(p: RefCounted) -> void:
	p.tr_pt_age = PackedInt64Array()
	p.tr_pt_age.resize(p.tr_pt_off[p.tr_units] * AGE_SLOTS)
	var mismatch: int = 0
	for u: int in p.tr_units:
		var order: Array = _point_order(p, u, "t21_age_order")
		var a: Array = []
		for j: int in order:
			a.append(p.tr_pt_mass[j])
		var b: Array = []
		var sb: int = 0
		for s: int in AGE_SLOTS:
			b.append(p.tr_age_counts[u * AGE_SLOTS + s])
			sb += p.tr_age_counts[u * AGE_SLOTS + s]
		if sb != p.tr_count[u]:
			mismatch += 1
		for r: Array in _overlap(a, b):
			p.tr_pt_age[int(order[int(r[0])]) * AGE_SLOTS + int(r[1])] += int(r[2])
	p.tr_margins["t21_age_mismatch"] = mismatch


## (3) each point's mass over the household-bundles and roles its unit's persons hold, in key order, the points in a second keyed order;
## a unit's persons in no household-bundle are the last segment and go to tr_margins["t21_role_rest"]
static func _role_layout(p: RefCounted) -> void:
	var ents: Array = []
	ents.resize(p.tr_units)
	for u0: int in p.tr_units:
		ents[u0] = []
	for h: int in p.tr_hh_keys.size():
		var mem: Dictionary = p.tr_hh[p.tr_hh_keys[h]]["members"]
		var uk: Array = mem.keys()
		uk.sort()
		for u1 in uk:
			for r: int in 5:
				var n: int = int((mem[u1] as Dictionary).get(r, 0))
				if n > 0:
					(ents[int(u1)] as Array).append([h, r, n])
	var rows: Array = []
	rows.resize(p.tr_hh_keys.size())
	for h1: int in p.tr_hh_keys.size():
		rows[h1] = []
	var rest: int = 0
	for u: int in p.tr_units:
		var order: Array = _point_order(p, u, "t21_role_order")
		var a: Array = []
		for j: int in order:
			a.append(p.tr_pt_mass[j])
		var b: Array = []
		var held: int = 0
		for e: Array in ents[u]:
			b.append(int(e[2]))
			held += int(e[2])
		rest += maxi(0, p.tr_count[u] - held)
		b.append(maxi(0, p.tr_count[u] - held))
		for o: Array in _overlap(a, b):
			if int(o[1]) < (ents[u] as Array).size():
				var e2: Array = ents[u][int(o[1])]
				(rows[int(e2[0])] as Array).append([int(order[int(o[0])]), int(e2[1]), int(o[2])])
	p.tr_hm_off = PackedInt64Array()
	p.tr_hm_pt = PackedInt32Array()
	p.tr_hm_role = PackedInt32Array()
	p.tr_hm_n = PackedInt64Array()
	for h2: int in p.tr_hh_keys.size():
		p.tr_hm_off.append(p.tr_hm_pt.size())
		for r2: Array in rows[h2]:
			p.tr_hm_pt.append(int(r2[0]))
			p.tr_hm_role.append(int(r2[1]))
			p.tr_hm_n.append(int(r2[2]))
	p.tr_hm_off.append(p.tr_hm_pt.size())
	p.tr_margins["t21_role_rest"] = rest


static func _r70_band(a: int) -> int:
	return 0 if a < 30 else mini(5, (a - 20) / 10)


static func _at_work(p: RefCounted, j: int) -> bool:
	var e: int = p.tr_points["employment"][j]
	return e == p.EMP_REGULAR or e == p.EMP_NONREGULAR


## R70's class of a husband point: its pay x 12 against the classes' lower edges (万円 a year); with no work income the first class
## (TO_E 03:24 (b), T until R76)
static func _r70_class(p: RefCounted, j: int, edges: Array) -> int:
	if not _at_work(p, j):
		return 0
	var y: float = float(p.tr_points["income"][j]) * 12.0
	var c: int = 0
	for k: int in edges.size():
		if y >= float(edges[k]):
			c = k
	return c


## The couple-role points' mid-ranks of pay among the at-work masses of their own sex and R70 band, nationally: point -> u in (0, 1)
static func _couple_ranks(p: RefCounted, pairs: Array) -> Dictionary:
	var by: Dictionary = {}
	for pr: Array in pairs:
		var j: int = int(pr[0])
		if not _at_work(p, j):
			continue
		var g: int = int(p.tr_points["sex"][j]) * 6 + _r70_band(int(p.tr_points["age"][j]))
		if not by.has(g):
			by[g] = {}
		by[g][j] = int(by[g].get(j, 0)) + int(pr[1])
	var out: Dictionary = {}
	for g2 in by:
		var rows: Array = []
		var tot: float = 0.0
		for j2 in by[g2]:
			rows.append([float(p.tr_points["income"][j2]), int(j2), float(by[g2][j2])])
			tot += float(by[g2][j2])
		rows.sort()
		var k: int = 0
		var acc: float = 0.0
		while k < rows.size():
			var k2: int = k
			var tie: float = 0.0
			while k2 < rows.size() and float(rows[k2][0]) == float(rows[k][0]):
				tie += float(rows[k2][2])
				k2 += 1
			for k3: int in range(k, k2):
				out[int(rows[k3][1])] = (acc + 0.5 * tie) / tot
			acc += tie
			k = k2
	return out


## (4) the seed of a wife point w and a husband point h (§14.2c): R70's odds ratio of an employed wife at the husband's class and her band
## over the band's all-classes odds (a husband with no work income: 労働力調査's odds by the wife's band, ruled (b)), and when both are at work the Gaussian copula density at their mid-ranks (T), ρ = 2 sin(π ρ_S ÷ 6)
static func couple_seed(p: RefCounted, w: int, h: int, ranks: Dictionary) -> float:
	var ce: Dictionary = _v(p, "couple_wife_employment")
	var wb: int = _r70_band(int(p.tr_points["age"][w]))
	if not _at_work(p, w):
		return 1.0
	var cs: Array = ce["couples"][wb]
	var es: Array = ce["wife_employed"][wb]
	var tc: float = 0.0
	var te: float = 0.0
	for k: int in cs.size():
		tc += float(cs[k])
		te += float(es[k])
	var s: float = 1.0
	if _at_work(p, h):
		var c: int = _r70_class(p, h, ce["class_from_man_yen_year"])
		var rate: float = float(es[c]) / float(cs[c])
		var all: float = te / tc
		s = (rate / (1.0 - rate)) / (all / (1.0 - all))
	else:
		var lf: Dictionary = _v(p, "couple_wife_work_husband_not_at_work")
		var k: int = 0
		for i: int in (lf["wife_band_from"] as Array).size():
			if int(p.tr_points["age"][w]) >= int(lf["wife_band_from"][i]):
				k = i
		s = float(lf["odds_ratio"][k])
	if _at_work(p, h) and ranks.has(w) and ranks.has(h):
		var rho_s: float = float((_v(p, "couple_spearman_both_earn") as Dictionary)["rho_s"][wb])
		var r: float = 2.0 * DM.sin(PI * rho_s / 6.0)
		var z1: float = DM.inv_normal(float(ranks[w]))
		var z2: float = DM.inv_normal(float(ranks[h]))
		s *= DM.exp(-(r * r * (z1 * z1 + z2 * z2) - 2.0 * r * z1 * z2) / (2.0 * (1.0 - r * r))) / sqrt(1.0 - r * r)
	return s


## An IPF of a rows x cols seed to integer margins R, C (Σ R = Σ C) until the worst relative margin error is below 1e-12 or 2,000 rounds
static func ipf2(seed: PackedFloat64Array, rr: Array, cc: Array) -> PackedFloat64Array:
	var nr: int = rr.size()
	var nc: int = cc.size()
	var x: PackedFloat64Array = seed.duplicate()
	for it: int in 2000:
		for i: int in nr:
			var s: float = 0.0
			for j: int in nc:
				s += x[i * nc + j]
			if s > 0.0:
				for j2: int in nc:
					x[i * nc + j2] *= float(rr[i]) / s
		var worst: float = 0.0
		for j3: int in nc:
			var s2: float = 0.0
			for i2: int in nr:
				s2 += x[i2 * nc + j3]
			if s2 > 0.0:
				for i3: int in nr:
					x[i3 * nc + j3] *= float(cc[j3]) / s2
		for i4: int in nr:
			var s3: float = 0.0
			for j4: int in nc:
				s3 += x[i4 * nc + j4]
			worst = maxf(worst, absf(s3 - float(rr[i4])) / maxf(1.0, float(rr[i4])))
		if worst < 1e-12:
			break
	return x


## (4), (5) the start's couple points (§14.2c, AMENDED for §12.12): per prefecture x type x householder band x class of the couple types
## and "other" (its household-bundles of every size together), its female partner points x its male head points (the couple point
## recorded in the wife's bundle), each margin its role masses. More wives than heads: the excess are cross-tier wives
## (tr_margins["cp_cross"]); more heads: in "other" the heads in no couple, in the couple types the partnerless heads
## (tr_margins["cp_nopartner"]); the larger side is cut to the smaller by keyed systematic rounding. The wives' and heads' masses
## outside the table but in a couple (cross-tier, partnerless) go to tr_margins["cp_extra"] by point
static func _couples(p: RefCounted) -> void:
	var pairs: Array = []
	for h0: int in p.tr_hh_keys.size():
		var t0: int = int(p.tr_hh_keys[h0].split("|")[1])
		if t0 != 1 and t0 != 2 and t0 != 4:
			continue
		for k0: int in range(p.tr_hm_off[h0], p.tr_hm_off[h0 + 1]):
			if p.tr_hm_role[k0] <= 1:
				pairs.append([p.tr_hm_pt[k0], p.tr_hm_n[k0]])
	var ranks: Dictionary = _couple_ranks(p, pairs)
	p.tr_cp_hh = PackedInt32Array()
	p.tr_cp_w = PackedInt32Array()
	p.tr_cp_h = PackedInt32Array()
	p.tr_cp_n = PackedInt64Array()
	var cross: int = 0
	var nopart: int = 0
	var extra: Dictionary = {}
	# the couples paired per (prefecture, type, householder band, class) across the size classes
	# Why not per household-bundle: _fill_sizes splits the wives and the heads over the sizes apart, so one size's bundle held wives
	# whose husbands were in another (109,407 counted as cross-tier against 590 real ones)
	var grp: Dictionary = {}
	for h0: int in p.tr_hh_keys.size():
		var f0: PackedStringArray = p.tr_hh_keys[h0].split("|")
		var t0: int = int(f0[1])
		if t0 != 1 and t0 != 2 and t0 != 4:
			continue
		var gk: String = "%s|%s|%s|%s" % [f0[0], f0[1], f0[2], f0[4]]
		if not grp.has(gk):
			grp[gk] = []
		(grp[gk] as Array).append(h0)
	var gkeys: Array = grp.keys()
	gkeys.sort()
	for gi: int in gkeys.size():
		var hs: Array = grp[gkeys[gi]]
		var h: int = int(hs[0])
		var t: int = int(p.tr_hh_keys[h].split("|")[1])
		var wd: Dictionary = {}
		var hd: Dictionary = {}
		var wb: Dictionary = {}   # wife point -> the bundle holding most of her mass
		for hh: int in hs:
			for k: int in range(p.tr_hm_off[hh], p.tr_hm_off[hh + 1]):
				var j: int = p.tr_hm_pt[k]
				var fem: bool = int(p.tr_points["sex"][j]) == p.FEMALE
				if fem and p.tr_hm_role[k] == 1:
					if p.tr_hm_n[k] > int(wd.get(j, 0)):
						wb[j] = hh
					wd[j] = int(wd.get(j, 0)) + p.tr_hm_n[k]
				elif not fem and p.tr_hm_role[k] == 0:
					hd[j] = int(hd.get(j, 0)) + p.tr_hm_n[k]
		var w: Array = wd.keys()
		w.sort()
		var hu: Array = hd.keys()
		hu.sort()
		var wn: Array = []
		for j1 in w:
			wn.append(int(wd[j1]))
		var hn: Array = []
		for j2 in hu:
			hn.append(int(hd[j2]))
		var sw: int = 0
		var sh: int = 0
		for x: int in wn:
			sw += x
		for y: int in hn:
			sh += y
		var wn0: Array = wn.duplicate()
		var hn0: Array = hn.duplicate()
		if sw > sh:
			cross += sw - sh
			var cx: Dictionary = p.tr_margins.get("cp_cross_by", {})
			var ckx: String = "type %d, householder %s" % [t, p.tr_hh_keys[h].get_slice("|", 2)]
			cx[ckx] = int(cx.get(ckx, 0)) + sw - sh
			p.tr_margins["cp_cross_by"] = cx
			wn = Array(_systematic(_scaled(wn, sh, sw), sh, p.seed_v, "t21_cp_cut", gi * 2)) if sh > 0 else _zeros(wn.size())
		elif sh > sw:
			nopart += (sh - sw) if t != 4 else 0
			hn = Array(_systematic(_scaled(hn, sw, sh), sw, p.seed_v, "t21_cp_cut", gi * 2 + 1)) if sw > 0 else _zeros(hn.size())
		for a0: int in w.size():
			if int(wn0[a0]) > int(wn[a0]):
				extra[int(w[a0])] = int(extra.get(int(w[a0]), 0)) + int(wn0[a0]) - int(wn[a0])
		if t != 4:
			for b0: int in hu.size():
				if int(hn0[b0]) > int(hn[b0]):
					extra[int(hu[b0])] = int(extra.get(int(hu[b0]), 0)) + int(hn0[b0]) - int(hn[b0])
		if mini(sw, sh) <= 0:
			continue
		var seed := PackedFloat64Array()
		seed.resize(w.size() * hu.size())
		for a: int in w.size():
			for b: int in hu.size():
				seed[a * hu.size() + b] = couple_seed(p, int(w[a]), int(hu[b]), ranks) if int(wn[a]) > 0 and int(hn[b]) > 0 else 0.0
		var xt: PackedFloat64Array = ipf2(seed, wn, hn)
		var it: PackedInt64Array = dep_round(xt, w.size(), hu.size(), p.seed_v, "t21_cp_round", gi)
		for a2: int in w.size():
			for b2: int in hu.size():
				var m: int = it[a2 * hu.size() + b2]
				if m > 0:
					p.tr_cp_hh.append(int(wb[int(w[a2])]))
					p.tr_cp_w.append(int(w[a2]))
					p.tr_cp_h.append(int(hu[b2]))
					p.tr_cp_n.append(m)
	p.tr_margins["cp_cross"] = cross
	p.tr_margins["cp_nopartner"] = nopart
	p.tr_margins["cp_extra"] = extra
	p.tr_margins["cp_ranks"] = ranks


## (c) restored as a subset (TO_E 09:56; §12.12 (9)): each recorded non-head couple [husband unit, wife unit, kind, n] of an "other"
## group pairs its units' points of the child (kind 0) or parent (kind 1) role in that group: n split over each side's points by their
## mass left (keyed systematic), the two sides then raked on the couple seed (ipf2) and rounded (dep_round), the couple points recorded
## in the wife's bundle. The masses a record could not find go to tr_margins["cp_nh_short"]
static func _nh_couple_points(p: RefCounted) -> void:
	var unit_of := PackedInt32Array()
	unit_of.resize(p.tr_pt_off[p.tr_units])
	for u: int in p.tr_units:
		for j: int in range(p.tr_pt_off[u], p.tr_pt_off[u + 1]):
			unit_of[j] = u
	var grp: Dictionary = {}   # "code|band|class" of type 4 -> its bundle indices
	for h: int in p.tr_hh_keys.size():
		var f0: PackedStringArray = p.tr_hh_keys[h].split("|")
		if int(f0[1]) != 4:
			continue
		var gk: String = "%s|%s|%s" % [f0[0], f0[2], f0[4]]
		if not grp.has(gk):
			grp[gk] = []
		(grp[gk] as Array).append(h)
	p.tr_margins["cp_nh_from"] = p.tr_cp_n.size()
	var ranks: Dictionary = p.tr_margins.get("cp_ranks", {})
	var short: int = 0
	var made: int = 0
	var rks: Array = p.tr_nh_hh.keys()
	rks.sort()
	for gi: int in rks.size():
		var rk: String = rks[gi]
		if not grp.has(rk):
			short += 1
			continue
		var left: Dictionary = {}   # "point|role" -> mass not yet paired, and the point's bundle
		var bun: Dictionary = {}
		for h2: int in grp[rk]:
			for k: int in range(p.tr_hm_off[h2], p.tr_hm_off[h2 + 1]):
				if p.tr_hm_role[k] == 2 or p.tr_hm_role[k] == 3:
					var key: String = "%d|%d" % [p.tr_hm_pt[k], p.tr_hm_role[k]]
					left[key] = int(left.get(key, 0)) + p.tr_hm_n[k]
					bun[p.tr_hm_pt[k]] = h2
		var recs: Array = p.tr_nh_hh[rk]
		for ri: int in recs.size():
			var rec: Array = recs[ri]
			var role: int = 2 if int(rec[2]) == 0 else 3
			var n: int = int(rec[3])
			var sides: Array = []
			for side: int in 2:
				var uu: int = int(rec[side])
				var pts: Array = []
				var ms: Array = []
				var tot: int = 0
				for j3: int in range(p.tr_pt_off[uu], p.tr_pt_off[uu + 1]):
					var m: int = int(left.get("%d|%d" % [j3, role], 0))
					if m > 0:
						pts.append(j3)
						ms.append(m)
						tot += m
				var take: int = mini(n, tot)
				var cut: Array = Array(_systematic(_scaled(ms, take, maxi(1, tot)), take, p.seed_v, "t21_nh_cut", (gi * 64 + ri) * 2 + side)) if take > 0 else []
				sides.append([pts, cut, take])
			var nn: int = mini(int(sides[0][2]), int(sides[1][2]))
			short += n - nn
			if nn <= 0:
				continue
			for side2: int in 2:
				if int(sides[side2][2]) > nn:
					sides[side2][1] = Array(_systematic(_scaled(sides[side2][1], nn, int(sides[side2][2])), nn, p.seed_v, "t21_nh_cut2", (gi * 64 + ri) * 2 + side2))
			var hp: Array = sides[0][0]
			var hn: Array = sides[0][1]
			var wp: Array = sides[1][0]
			var wn: Array = sides[1][1]
			var seed := PackedFloat64Array()
			seed.resize(wp.size() * hp.size())
			for a: int in wp.size():
				for b: int in hp.size():
					seed[a * hp.size() + b] = couple_seed(p, int(wp[a]), int(hp[b]), ranks) if int(wn[a]) > 0 and int(hn[b]) > 0 else 0.0
			var it: PackedInt64Array = dep_round(ipf2(seed, wn, hn), wp.size(), hp.size(), p.seed_v, "t21_nh_round", gi * 64 + ri)
			for a2: int in wp.size():
				for b2: int in hp.size():
					var m2: int = it[a2 * hp.size() + b2]
					if m2 <= 0:
						continue
					p.tr_cp_hh.append(int(bun[int(wp[a2])]))
					p.tr_cp_w.append(int(wp[a2]))
					p.tr_cp_h.append(int(hp[b2]))
					p.tr_cp_n.append(m2)
					made += m2
					var kw: String = "%d|%d" % [int(wp[a2]), role]
					var kh2: String = "%d|%d" % [int(hp[b2]), role]
					left[kw] = int(left[kw]) - m2
					left[kh2] = int(left[kh2]) - m2
	p.tr_margins["cp_nh"] = made
	p.tr_margins["cp_nh_short"] = short


static func _zeros(n: int) -> Array:
	var out: Array = []
	out.resize(n)
	out.fill(0)
	return out


static func _scaled(v: Array, num: int, den: int) -> PackedFloat64Array:
	var out := PackedFloat64Array()
	for x in v:
		out.append(float(x) * float(num) / float(den))
	return out


## (6) the marital states (§14.2c, made exact a1173165; §12.16): per prefecture x band x sex (15+), the persons in no couple NC take the
## married-apart MA (T1's), never married T1's (tr_never_married, at most NC - MA) and the rest as widowed and divorced in M021's ratio
## (tr_margins["m21"]); each point's mass in no couple takes the cell's shares by the largest remainder (ties in state order). Reports to
## tr_margins["ms"]
## Why not R76's shares on the single ages (before §12.16): T1's never married and married-apart follow R77c's cohort, and R76's
## 2020 shares beside them would not sum (M021)
static func _marital(p: RefCounted) -> void:
	var m21: Dictionary = p.tr_margins["m21"]
	var cpm: Dictionary = (p.tr_margins["cp_extra"] as Dictionary).duplicate()
	for c: int in p.tr_cp_n.size():
		cpm[p.tr_cp_w[c]] = int(cpm.get(p.tr_cp_w[c], 0)) + p.tr_cp_n[c]
		cpm[p.tr_cp_h[c]] = int(cpm.get(p.tr_cp_h[c], 0)) + p.tr_cp_n[c]
	var cells: Dictionary = {}   # "code|band|sex" -> [NC, MA, NM, W, D] (reals; NM T1's, W and D M021's)
	for u: int in p.tr_units:
		var b: int = p.tr_key[u * KEY_STRIDE + 1]
		if b * 5 < 15:
			continue
		var c2: int = p.tr_key[u * KEY_STRIDE]
		var sx: int = p.tr_key[u * KEY_STRIDE + 2]
		var ck: String = "%d|%d|%d" % [c2, b, sx]
		if not cells.has(ck):
			cells[ck] = [0.0, 0.0, 0.0, 0.0, 0.0]
		var e: Array = cells[ck]
		var cm: int = 0
		for j: int in range(p.tr_pt_off[u], p.tr_pt_off[u + 1]):
			cm += int(cpm.get(j, 0))
		e[0] = float(e[0]) + float(p.tr_count[u] - cm)
		e[1] = float(e[1]) + p.tr_married_apart[u] * float(p.tr_count[u])
		e[2] = float(e[2]) + p.tr_never_married[u] * float(p.tr_count[u])
		if m21.has(ck):
			e[3] = float(m21[ck][4])
			e[4] = float(m21[ck][5])
	var capped: int = 0
	var ma_over: int = 0
	for ck2: String in cells:
		var e2: Array = cells[ck2]
		var nc: float = float(e2[0])
		var ma: float = minf(float(e2[1]), nc)
		ma_over += 1 if float(e2[1]) > nc + 1e-6 else 0
		var nm: float = minf(float(e2[2]), nc - ma)
		capped += 1 if float(e2[2]) > nc - ma + 1e-6 else 0
		var rest: float = maxf(0.0, nc - ma - nm)
		var wd: float = float(e2[3]) + float(e2[4])
		var wi: float = rest * float(e2[3]) / wd if wd > 0.0 else rest * 0.5
		cells[ck2] = [nc, ma, nm, wi, rest - wi]
	p.tr_pt_ms = PackedInt64Array()
	p.tr_pt_ms.resize(p.tr_pt_off[p.tr_units] * 4)
	for u2: int in p.tr_units:
		var b2: int = p.tr_key[u2 * KEY_STRIDE + 1]
		var ck3: String = "%d|%d|%d" % [p.tr_key[u2 * KEY_STRIDE], b2, p.tr_key[u2 * KEY_STRIDE + 2]]
		for j2: int in range(p.tr_pt_off[u2], p.tr_pt_off[u2 + 1]):
			var cmj: int = int(cpm.get(j2, 0))
			var free: int = p.tr_pt_mass[j2] - cmj
			if b2 * 5 < 15 or not cells.has(ck3):
				p.tr_pt_ms[j2 * 4] = free
				p.tr_pt_ms[j2 * 4 + 1] = cmj
				continue
			var e3: Array = cells[ck3]
			var v := PackedFloat64Array()
			for k: int in [2, 1, 3, 4]:
				v.append(float(free) * float(e3[k]) / float(e3[0]) if float(e3[0]) > 0.0 else (float(free) if k == 2 else 0.0))
			var q: PackedInt64Array = _largest(v, free)
			p.tr_pt_ms[j2 * 4] = q[0]
			p.tr_pt_ms[j2 * 4 + 1] = cmj + q[1]
			p.tr_pt_ms[j2 * 4 + 2] = q[2]
			p.tr_pt_ms[j2 * 4 + 3] = q[3]
	p.tr_margins["ms"] = {"capped": capped, "ma_over": ma_over, "cells": cells.size()}


## (2) a (point, age) mass m's split over the 12 birth months (§14.2c ruled (a)): the birth year's shares (2023 - age; the nearer listed
## year, the earlier on a tie, before 1947 1947's), ⌊m s⌋ by month, the remainder by the largest remainder, ties from a keyed offset
## Why a function: the table is 26 M cells, all recomputable from the point, the age and the mass (a1173165)
static func birth_months(p: RefCounted, j: int, age: int, m: int) -> PackedInt64Array:
	var bm: Dictionary = _v(p, "birth_month_shares")
	var y: int = maxi(1947, 2023 - age)
	var best: int = 0
	var bd: int = 1 << 30
	for i: int in (bm["years"] as Array).size():
		var d: int = absi(int(bm["years"][i]) - y)
		if d < bd:
			bd = d
			best = i
	var sh: Array = bm["shares"][best]
	var out := PackedInt64Array()
	out.resize(12)
	var left: int = m
	var rows: Array = []
	var o: int = KEYED.below(12, p.seed_v, "t21_birth_month", j, age, 0)
	for k: int in 12:
		var x: float = float(m) * float(sh[k])
		out[k] = int(floor(x))
		left -= out[k]
		rows.append([-(x - float(out[k])), (k - o + 12) % 12, k])
	rows.sort()
	for r: int in left:
		out[int(rows[r % 12][2])] += 1
	return out


## §14.6 (1): the month-0 state of the T2.2 month, every cell's January mass and its mass not yet aged both its mass (month 0 a January)
static func _t22_start(p: RefCounted) -> void:
	var n_pts: int = p.tr_pt_off[p.tr_units]
	p.tr_pt_id = PackedInt64Array()
	p.tr_pt_id.resize(n_pts)
	for g: int in n_pts:
		p.tr_pt_id[g] = g
	p.tr_pt_next = n_pts
	p.tr_pt_jan = p.tr_pt_age.duplicate()
	p.tr_pt_old = p.tr_pt_age.duplicate()
	p.tr_class_lines = p.tr_margins["class_lines"]
	p.tr_pt_rem = {}
	p.tr_pt_muq = PackedFloat64Array()
	p.tr_pt_muq.resize(n_pts)
	p.tr_pt_mug = PackedFloat64Array()
	p.tr_pt_mug.resize(n_pts)
	p.tr_cp_cap = {}
	for c: int in p.tr_cp_n.size():
		p.tr_cp_cap[p.tr_cp_hh[c]] = int(p.tr_cp_cap.get(p.tr_cp_hh[c], 0)) + 1
	p.tr_pt_ag = _zeros_i(n_pts * AGE_SLOTS * NS)
	p.tr_pt_jg = _zeros_i(n_pts * AGE_SLOTS * NS)
	p.tr_pt_og = _zeros_i(n_pts * AGE_SLOTS * NS)
	p.tr_pt_T = _zeros_i(n_pts * 4 * NG)
	var pst: Dictionary = (LC._lc(p, "grade_kernel") as Dictionary)["p_stable_given_side"]
	# Why not each point's one start grade over its band's slots (M030 to T2.2c): its band's mean mix sat in every slot, c was solved
	# on that, and M035's birthday re-grade then pinned the arrivals to the steeper pi(a) (M036, the year-1 deaths +2-8%)
	for u: int in p.tr_units:
		var b: int = p.tr_key[u * KEY_STRIDE + 1]
		var s: int = p.tr_key[u * KEY_STRIDE + 2]
		for g2: int in range(p.tr_pt_off[u], p.tr_pt_off[u + 1]):
			var colm := PackedInt64Array()
			colm.resize(NG)
			for sl: int in _slots_in(b):
				var m0: int = p.tr_pt_age[g2 * AGE_SLOTS + sl]
				if m0 <= 0:
					continue
				var z: PackedInt64Array = _start_split(p, m0, LC.shares(p, b * 5 + sl, s), p.tr_pt_id[g2] * AGE_SLOTS + sl)
				for gr: int in NG:
					if z[gr] <= 0:
						continue
					colm[gr] += z[gr]
					var ps: float = float(pst["good" if gr < 2 else "bad"])
					var xs: int = binomial(z[gr], ps, KEYED.u(p.seed_v, "t22b_class0", p.tr_pt_id[g2] * NG + gr, sl, 0))
					var cx: int = (g2 * AGE_SLOTS + sl) * NS + gr * NK
					p.tr_pt_ag[cx] = xs
					p.tr_pt_ag[cx + 1] = z[gr] - xs
					p.tr_pt_jg[cx] = xs
					p.tr_pt_jg[cx + 1] = z[gr] - xs
					p.tr_pt_og[cx] = xs
					p.tr_pt_og[cx + 1] = z[gr] - xs
			var rows := PackedInt64Array()
			rows.resize(4)
			var mt: int = 0
			for k: int in 4:
				rows[k] = p.tr_pt_ms[g2 * 4 + k]
				mt += rows[k]
			if mt <= 0:
				continue
			var x := PackedFloat64Array()
			x.resize(4 * NG)
			for k2: int in 4:
				for gr2: int in NG:
					x[k2 * NG + gr2] = float(rows[k2]) * float(colm[gr2]) / float(mt)
			var tz: PackedInt64Array = _table_round(p, x, rows, colm, 4, NG, "m036_T", p.tr_pt_id[g2])
			for k3: int in 4:
				for gr3: int in NG:
					p.tr_pt_T[g2 * 4 * NG + k3 * NG + gr3] = tz[k3 * NG + gr3]
	_t22_quartiles(p)
	_t22_solve_c(p, true)


## M036 (§14.6 (16)): a slot's mass m over the states by the shares sh, by the largest remainder, ties in the keyed order (m036_start,
## key, state)
static func _start_split(p: RefCounted, m: int, sh: PackedFloat64Array, key: int) -> PackedInt64Array:
	var out := PackedInt64Array()
	out.resize(NG)
	var tot: float = 0.0
	for g: int in NG:
		tot += sh[g]
	var fr: Array = []
	var used: int = 0
	for g2: int in NG:
		var x: float = float(m) * sh[g2] / tot
		out[g2] = int(floor(x))
		used += out[g2]
		fr.append([x - floor(x), KEYED.raw(p.seed_v, "m036_start", key, g2, 0), g2])
	fr.sort_custom(func(a: Array, c: Array) -> bool: return float(a[0]) > float(c[0]) if a[0] != c[0] else int(a[1]) < int(c[1]))
	for q: int in m - used:
		out[int(fr[q % NG][2])] += 1
	return out


## T2.2 (§14.6): the tiers' month after the persons layer's: (1) ageing by birth month; (2)-(3) deaths and widowing; at January's end
## the K_b re-target; the quartiles re-read once (§14.6 (6)); (4) the compression; one rebuild of the point arrays; C5. T2s-gx's grade
## tables at each stage boundary against the stage's ledger. The month's tallies go to tr_margins["t22"]
static func step(p: RefCounted, _env: Dictionary) -> void:
	var t0: int = Time.get_ticks_usec()
	var w: Dictionary = _t22_work(p)
	var tl: Dictionary = w["tally"]
	if p.month % 12 == 0:
		p.tr_pt_jan = p.tr_pt_age.duplicate()
		p.tr_pt_old = p.tr_pt_age.duplicate()
		p.tr_pt_jg = p.tr_pt_ag.duplicate()
		p.tr_pt_og = p.tr_pt_ag.duplicate()
		p.tr_pt_rem = {}
	var t0b: int = Time.get_ticks_usec()
	var g0: PackedInt64Array = grade_table(p, [])
	var t1: int = Time.get_ticks_usec()
	_t22_age(p, w)
	var t2: int = Time.get_ticks_usec()
	var g1: PackedInt64Array = grade_table(p, w["lists"])
	var t2b: int = Time.get_ticks_usec()
	_t22_deaths(p, w)
	var t3: int = Time.get_ticks_usec()
	var g2: PackedInt64Array = grade_table(p, w["lists"])
	var t3a: int = Time.get_ticks_usec()
	if p.month % 12 == 0:
		p.tr_kb = _targets(p)
	var t3b: int = Time.get_ticks_usec()
	_t22_quartiles(p, w)
	var t4: int = Time.get_ticks_usec()
	_t22_compress(p, w)
	var t5: int = Time.get_ticks_usec()
	_t22_rebuild(p, w)
	var t6: int = Time.get_ticks_usec()
	var g3: PackedInt64Array = grade_table(p, [])
	var t6b: int = Time.get_ticks_usec()
	_t22_c5(p, w)
	var t7: int = Time.get_ticks_usec()
	var g4: PackedInt64Array = grade_table(p, [])
	var led_none: PackedInt64Array = _zeros_i(g0.size())
	var gxs: Dictionary = {"ageing and the re-grade": _gx_off(g0, g1, w["led_age"]), "deaths and widowing": _gx_off(g1, g2, w["led_death"]), "C1, C2 and the rebuild": _gx_off(g2, g3, led_none), "C5": _gx_off(g3, g4, led_none)}
	tl["gx_by_stage"] = gxs
	tl["gx"] = int(gxs["ageing and the re-grade"]) + int(gxs["deaths and widowing"]) + int(gxs["C1, C2 and the rebuild"]) + int(gxs["C5"])
	var t8: int = Time.get_ticks_usec()
	tl["usec_by_step"] = {"work": t0b - t0, "ageing": t2 - t1, "deaths and widowing": t3 - t2b, "quartiles": t4 - t3b, "C1 and C2": t5 - t4, "rebuild": t6 - t5, "C5": t7 - t6b, "K_b re-target": t3b - t3a, "T2s-gx tables": (t1 - t0b) + (t2b - t2) + (t3a - t3) + (t6b - t6) + (t8 - t7)}
	tl["usec"] = Time.get_ticks_usec() - t0
	p.tr_margins["t22"] = tl


## T2s-gx (EXTENDED, §14.6 (6)): the cells of after − before that differ from the stage's ledger
static func _gx_off(before: PackedInt64Array, after: PackedInt64Array, led: PackedInt64Array) -> int:
	var off: int = 0
	for x: int in before.size():
		off += 0 if after[x] - before[x] == led[x] else 1
	return off


## The month's working index: each unit's points, each point's couple and household entries, each entry's household-bundle, the
## points' instruments apart from the individuals', each point field's stride, the units by key
static func _t22_work(p: RefCounted) -> Dictionary:
	var n_pts: int = p.tr_pt_off[p.tr_units]
	var lists: Array = []
	for u: int in p.tr_units:
		var l: Array = []
		for g: int in range(p.tr_pt_off[u], p.tr_pt_off[u + 1]):
			l.append(g)
		lists.append(l)
	var cp_of: Array = []
	cp_of.resize(n_pts)
	var hm_of: Array = []
	hm_of.resize(n_pts)
	for g2: int in n_pts:
		cp_of[g2] = []
		hm_of[g2] = []
	for c: int in p.tr_cp_n.size():
		(cp_of[p.tr_cp_w[c]] as Array).append(c)
		(cp_of[p.tr_cp_h[c]] as Array).append(c)
	var hm_h := PackedInt32Array()
	hm_h.resize(p.tr_hm_pt.size())
	for h: int in p.tr_hh_keys.size():
		for k: int in range(p.tr_hm_off[h], p.tr_hm_off[h + 1]):
			hm_h[k] = h
			(hm_of[p.tr_hm_pt[k]] as Array).append(k)
	var ins_pt: Dictionary = {}
	var ins_ind: Dictionary = {}
	for name: String in p.tr_instruments:
		var arr: PackedInt64Array = p.tr_instruments[name]
		ins_pt[name] = arr.slice(0, n_pts)
		ins_ind[name] = arr.slice(n_pts)
	var stride: Dictionary = {}
	for name2: String in p.tr_points:
		stride[name2] = (p.tr_points[name2].size() / n_pts) if n_pts > 0 else 1
	var by_key: Dictionary = {}
	for u2: int in p.tr_units:
		var ks: String = _key_str(p.tr_key, u2)
		if not by_key.has(ks):
			by_key[ks] = []
		(by_key[ks] as Array).append(u2)
	var htype := PackedInt32Array()
	for hk: String in p.tr_hh_keys:
		htype.append(int(hk.get_slice("|", 1)))
	var unit_of := PackedInt32Array()
	unit_of.resize(n_pts)
	for u3: int in p.tr_units:
		for g3: int in range(p.tr_pt_off[u3], p.tr_pt_off[u3 + 1]):
			unit_of[g3] = u3
	var led_n: int = 2 * 9 * 4 * NG + p.AGES * 2 * NG
	return {"htype": htype, "lists": lists, "unit_of": unit_of, "led_age": _zeros_i(led_n), "led_death": _zeros_i(led_n), "cp_of": cp_of, "hm_of": hm_of, "hm_h": hm_h, "ins": ins_pt, "ins_ind": ins_ind, "stride": stride, "by_key": by_key,
		"tally": {"moved": 0, "due": 0, "splits": 0, "new_units": 0, "clamped": 0, "merges": 0, "dropped": 0, "class_entered": 0, "split_src": [], "c1": 0, "c2": 0, "cx_bad": 0, "cb_mr": _zeros_f(36), "cb_mv": _zeros_f(36), "cb_cr": _zeros_f(36), "cb_cv": _zeros_f(36), "c1_q_moved": 0,
			"cb_mm": _zeros_f(36), "cb_cm": _zeros_f(36), "cbg_m": _zeros_f(36), "cbq": 0, "cbq_mass": 0, "c5_moves": 0, "c5_x": 0,
			"c5_over": 0, "c5_r": _zeros_f(153), "c5_v": _zeros_f(153), "cp_blocks_capped": 0,
			"deaths": 0, "widowed": 0, "couples_lost": 0, "d_as": _zeros_i(p.AGES * 2), "d_old": _zeros_i(p.AGES * 2), "x_as": _zeros_f(p.AGES * 2),
			"e_as": _zeros_f(p.AGES * 2), "v_as": _zeros_f(p.AGES * 2), "d_g": _zeros_i(p.AGES * 2 * NG), "x_g": _zeros_f(p.AGES * 2 * NG), "d_k": _zeros_i(p.AGES * 8), "x_k": _zeros_f(p.AGES * 8),
			"wg_n": _zeros_f(2 * 9 * NG * NG), "wg_x": _zeros_f(2 * 9 * NG), "wg_e": _zeros_f(2 * 9 * NG), "wg_v": _zeros_f(2 * 9 * NG), "gx": 0}}


## T2s-gx's national tables: the four marital masses by grade x sex x 10-year band, then the mass by grade x sex x single age; the
## units' points from lists (before the rebuild) or, lists empty, from tr_pt_off
static func grade_table(p: RefCounted, lists: Array) -> PackedInt64Array:
	var base: int = 2 * 9 * 4 * NG
	var out: PackedInt64Array = _zeros_i(base + p.AGES * 2 * NG)
	for u: int in p.tr_units:
		var b: int = p.tr_key[u * KEY_STRIDE + 1]
		var s: int = p.tr_key[u * KEY_STRIDE + 2]
		var row: int = (s * 9 + LC._b10(b * 5)) * 4 * NG
		var pts: Array = lists[u] if lists.size() > 0 else range(p.tr_pt_off[u], p.tr_pt_off[u + 1])
		for g: int in pts:
			for x: int in 4 * NG:
				out[row + x] += p.tr_pt_T[g * 4 * NG + x]
			for sl: int in _slots_in(b):
				for sb: int in NS:
					out[base + ((b * 5 + sl) * 2 + s) * NG + sb / NK] += p.tr_pt_ag[(g * AGE_SLOTS + sl) * NS + sb]
	return out


## T2s-gm's identities of every point (M030 §6): its grade cells sum to its age, January and unaged masses, T's rows to its marital
## masses and its columns to its grade masses, every cell and entry at least 0; the violations counted
static func grade_identity(p: RefCounted) -> int:
	var bad: int = 0
	for g: int in p.tr_pt_off[p.tr_units]:
		var gm: PackedInt64Array = _zeros_i(NG)
		for sl: int in AGE_SLOTS:
			var sa: int = 0
			var sj: int = 0
			var so: int = 0
			for sb: int in NS:
				var cx: int = (g * AGE_SLOTS + sl) * NS + sb
				sa += p.tr_pt_ag[cx]
				sj += p.tr_pt_jg[cx]
				so += p.tr_pt_og[cx]
				gm[sb / NK] += p.tr_pt_ag[cx]
				bad += 1 if p.tr_pt_ag[cx] < 0 or p.tr_pt_jg[cx] < 0 or p.tr_pt_og[cx] < 0 else 0
			bad += 0 if sa == p.tr_pt_age[g * AGE_SLOTS + sl] else 1
			bad += 0 if sj == p.tr_pt_jan[g * AGE_SLOTS + sl] else 1
			bad += 0 if so == p.tr_pt_old[g * AGE_SLOTS + sl] else 1
		for k: int in 4:
			var r: int = 0
			for gr2: int in NG:
				r += p.tr_pt_T[g * 4 * NG + k * NG + gr2]
				bad += 1 if p.tr_pt_T[g * 4 * NG + k * NG + gr2] < 0 else 0
			bad += 0 if r == p.tr_pt_ms[g * 4 + k] else 1
		for gr3: int in NG:
			var c: int = 0
			for k2: int in 4:
				c += p.tr_pt_T[g * 4 * NG + k2 * NG + gr3]
			bad += 0 if c == gm[gr3] else 1
	return bad


static func _key_str(key: PackedInt32Array, u: int) -> String:
	return "%d|%d|%d|%d|%d|%d" % [key[u * KEY_STRIDE], key[u * KEY_STRIDE + 1], key[u * KEY_STRIDE + 2], key[u * KEY_STRIDE + 3], key[u * KEY_STRIDE + 4], key[u * KEY_STRIDE + 5]]


## The key of a person of code (class, type, employment) at prefecture c, band b, sex s, by §12.7's rule (as build_start's units)
static func key_of(c: int, b: int, s: int, code: int) -> PackedInt32Array:
	var k: int = code / (NTYPE * NEMP)
	var gk: int = k
	var gt: int = (code / NEMP) % NTYPE
	var ge: int = code % NEMP
	if k < CLASS_REST:
		gt = -1
		ge = -1
	elif k < CLASS_NONE:
		gk = CLASS_REST
		if b >= EMP_KEY_UNTIL_BAND:
			ge = -1
	else:
		ge = -1
	return PackedInt32Array([c, b, s, gk, gt, ge])


## The adult class of an income against the class lines (class 0 the top, above the first line)
static func class_of_income(lines: PackedFloat64Array, y: float) -> int:
	var k: int = 0
	while k < lines.size() and y < lines[k]:
		k += 1
	return k


static func _top_slot(b: int) -> int:
	return AGE_SLOTS - 1 if b == BANDS - 1 else 4


## (1) Each (point, age, state, class) cell's not-yet-aged mass O born in this calendar month moves up one age (§14.6 (1) as built,
## M030, T2.2b): X = HG(N, S_m, O) with S = birth_months(id x 10 + state x 2 + class, a, J) and N = Σ_{k >= m} S_k raised to O, all of
## O in December. M035 (§14.6 (14)): the month's arrivals, pooled by their new age × sex × quartile, are moved within their class to
## π(a) by LC.grade_flows, each cell's X by sequential keyed binomials and its marital states from the state's column, before they join
## age a: inside the band slot to slot, from the band's top in one split per point into the unit one band up; 100 re-graded at each
## anniversary, staying at 100
static func _t22_age(p: RefCounted, w: Dictionary) -> void:
	var mc: int = p.month % 12
	var lists: Array = w["lists"]
	var tl: Dictionary = w["tally"]
	var U0: int = p.tr_units
	var nc: int = p.AGES * 2 * 4
	var nn: PackedFloat64Array = _zeros_f(nc * NK * NG)
	var mv: Array = []
	for u: int in U0:
		var b: int = p.tr_key[u * KEY_STRIDE + 1]
		var s: int = p.tr_key[u * KEY_STRIDE + 2]
		for g: int in (lists[u] as Array):
			var id: int = p.tr_pt_id[g]
			var k: int = p.tr_pt_q[g]
			for sl: int in _slots_in(b):
				var a: int = b * 5 + sl
				var a2: int = mini(a + 1, p.AGES - 1)
				for sb: int in NS:
					var cx: int = (g * AGE_SLOTS + sl) * NS + sb
					var o: int = p.tr_pt_og[cx]
					if o <= 0:
						continue
					var gk: int = id * NS + sb
					var rk: int = (id * AGE_SLOTS + sl) * NS + sb
					var has_r: bool = p.tr_pt_rem.has(rk)
					var S: PackedInt64Array = p.tr_pt_rem[rk] if has_r else birth_months(p, gk, a, p.tr_pt_jg[cx])
					var nr: int = 0
					for k2: int in range(mc, 12):
						nr += S[k2]
					tl["due"] = int(tl["due"]) + S[mc]
					var x: int = o
					if mc < 11:
						if nr < o:
							nr = o
							tl["clamped"] = int(tl["clamped"]) + 1
						x = hypergeometric(nr, mini(S[mc], nr), o, KEYED.u(p.seed_v, "t22_age", gk, a, p.month))
					if has_r:
						p.tr_pt_rem[rk][mc] = 0
					if x <= 0:
						continue
					mv.append([u, g, sl, sb, x])
					nn[((a2 * 2 + s) * 4 + k) * (NK * NG) + (sb % NK) * NG + sb / NK] += float(x)
	var pm: PackedFloat64Array = _zeros_f(nc * NK * NG * NG)
	var gp: Dictionary = {"res": 0.0}
	for k0: String in ["before", "target", "after", "var", "stay", "stay_seed"]:
		gp[k0] = _zeros_f(2 * 9 * NG)
	gp["stay_c"] = _zeros_f(2 * 2 * 9 * NG)
	gp["n_c"] = _zeros_f(2 * 2 * 9 * NG)
	for k6: String in ["b4_target", "b4_after", "b4_var", "b4_n", "b4_exit"]:
		gp[k6] = _zeros_f(14)
	for cell: int in nc:
		var n8: PackedFloat64Array = nn.slice(cell * NK * NG, cell * NK * NG + NK * NG)
		var nt: float = 0.0
		for x0: int in NK * NG:
			nt += n8[x0]
		if nt <= 0.0:
			continue
		var a3: int = cell / 8
		var s2: int = (cell / 4) % 2
		var pi0: PackedFloat64Array = LC.shares(p, a3, s2)
		var pt: float = 0.0
		for g8: int in NG:
			pt += pi0[g8]
		var out: Array = LC.grade_flows(p, n8, pi0)
		var pr: PackedFloat64Array = out[0]
		for x1: int in NK * NG * NG:
			pm[cell * NK * NG * NG + x1] = pr[x1]
		gp["res"] = maxf(float(gp["res"]), float(out[1]))
		var row: int = (s2 * 9 + LC._b10(a3)) * NG
		for g1: int in NG:
			gp["target"][row + g1] += pi0[g1] / pt * nt
		if a3 >= 65:
			gp["b4_target"][s2 * 7 + mini((a3 - 65) / 5, 6)] += pi0[4] / pt * nt
		for c: int in NK:
			var kc: PackedFloat64Array = LC.grade_kernel(p, c, pi0)
			for g5: int in NG:
				gp["before"][row + g5] += n8[c * NG + g5]
				gp["stay_seed"][row + g5] += n8[c * NG + g5] * kc[g5 * NG + g5]
	var lb: int = 2 * 9 * 4 * NG
	var ups: Dictionary = {}
	var moved: int = 0
	for e: Array in mv:
		var u2: int = e[0]
		var g2: int = e[1]
		var sl2: int = e[2]
		var sb2: int = e[3]
		var m: int = e[4]
		var b2: int = p.tr_key[u2 * KEY_STRIDE + 1]
		var s3: int = p.tr_key[u2 * KEY_STRIDE + 2]
		var top: int = _top_slot(b2)
		var a4: int = b2 * 5 + sl2
		var a5: int = mini(a4 + 1, p.AGES - 1)
		var id2: int = p.tr_pt_id[g2]
		var gr2: int = sb2 / NK
		var cl: int = sb2 % NK
		var cell2: int = (a5 * 2 + s3) * 4 + p.tr_pt_q[g2]
		var rw: int = cl * NG + gr2
		var cx2: int = (g2 * AGE_SLOTS + sl2) * NS + sb2
		var b10s: int = LC._b10(b2 * 5)
		var row2: int = (s3 * 9 + LC._b10(a5)) * NG
		var xs: PackedInt64Array = _zeros_i(NG)
		var rem: int = m
		var rp: float = 1.0
		for g3: int in NG:
			var pg: float = pm[cell2 * NK * NG * NG + rw * NG + g3]
			gp["var"][row2 + g3] += float(m) * pg * (1.0 - pg)
			var x2: int = rem
			if g3 < NG - 1:
				x2 = binomial(rem, clampf(pg / rp, 0.0, 1.0), KEYED.u(p.seed_v, "t22b_grade", id2 * NS + sb2, a5, p.month * NG + g3)) if rp > 0.0 and rem > 0 else 0
			rp -= pg
			rem -= x2
			xs[g3] = x2
			gp["after"][row2 + g3] += float(x2)
		gp["stay"][row2 + gr2] += float(xs[gr2])
		gp["stay_c"][cl * 18 * NG + row2 + gr2] += float(xs[gr2])
		gp["n_c"][cl * 18 * NG + row2 + gr2] += float(m)
		if a5 >= 65:
			var r5: int = s3 * 7 + mini((a5 - 65) / 5, 6)
			gp["b4_var"][r5] += float(m) * pm[cell2 * NK * NG * NG + rw * NG + 4] * (1.0 - pm[cell2 * NK * NG * NG + rw * NG + 4])
			gp["b4_after"][r5] += float(xs[4])
			if gr2 == 4:
				gp["b4_n"][r5] += float(m)
				gp["b4_exit"][r5] += float(xs[3])
		tl["moved"] = int(tl["moved"]) + m
		p.tr_pt_og[cx2] -= m
		p.tr_pt_ag[cx2] -= m
		p.tr_pt_old[g2 * AGE_SLOTS + sl2] -= m
		p.tr_pt_age[g2 * AGE_SLOTS + sl2] -= m
		p.tr_age_counts[u2 * AGE_SLOTS + sl2] -= m
		for g4: int in NG:
			var x3: int = xs[g4]
			if x3 <= 0:
				continue
			w["led_age"][lb + (a4 * 2 + s3) * NG + gr2] -= x3
			w["led_age"][lb + (a5 * 2 + s3) * NG + g4] += x3
			if g4 != gr2:
				moved += x3
				var col := PackedInt64Array()
				for k3: int in 4:
					col.append(p.tr_pt_T[g2 * 4 * NG + k3 * NG + gr2])
				var md: PackedInt64Array = hypergeometric_split(col, x3, p.seed_v, "t22b_ms", (((id2 * NS + sb2) * NG + g4) * 128 + a5) * 256 + p.month % 256)
				for k4: int in 4:
					p.tr_pt_T[g2 * 4 * NG + k4 * NG + gr2] -= md[k4]
					p.tr_pt_T[g2 * 4 * NG + k4 * NG + g4] += md[k4]
					w["led_age"][(s3 * 9 + b10s) * 4 * NG + k4 * NG + gr2] -= md[k4]
					w["led_age"][(s3 * 9 + b10s) * 4 * NG + k4 * NG + g4] += md[k4]
			var dsb: int = g4 * NK + cl
			if a4 >= p.AGES - 1:
				p.tr_pt_ag[(g2 * AGE_SLOTS + sl2) * NS + dsb] += x3
				p.tr_pt_age[g2 * AGE_SLOTS + sl2] += x3
				p.tr_age_counts[u2 * AGE_SLOTS + sl2] += x3
			elif sl2 < top:
				p.tr_pt_ag[(g2 * AGE_SLOTS + sl2 + 1) * NS + dsb] += x3
				p.tr_pt_age[g2 * AGE_SLOTS + sl2 + 1] += x3
				p.tr_age_counts[u2 * AGE_SLOTS + sl2 + 1] += x3
			else:
				if not ups.has(g2):
					ups[g2] = [u2, _zeros_i(NS), a5]
				ups[g2][1][dsb] += x3
	for g6 in ups:
		var up: Array = ups[g6]
		_t22_split(p, w, int(up[0]), int(g6), up[1], int(up[2]))
	gp["moved"] = moved
	gp["nn"] = nn
	gp["pm"] = pm
	tl["t22b"] = gp


## A split of xc persons by (grade, class) cell of point g (unit u) at age a into the unit one band up (§14.6 (1) as built, M030): a new point with
## g's state, its code's class set from its income when it enters the adult bands; each grade's marital column by the keyed largest
## remainder, the married summed over grades over g's couple points and its other married mass and its household entries by keyed
## systematic rounding, the instruments pro rata
static func _t22_split(p: RefCounted, w: Dictionary, u: int, g: int, xc: PackedInt64Array, a: int) -> void:
	var tl: Dictionary = w["tally"]
	var xs: PackedInt64Array = _zeros_i(NG)
	var x: int = 0
	for sb: int in NS:
		xs[sb / NK] += xc[sb]
		x += xc[sb]
	var b: int = a / 5
	var code: int = p.tr_pt_code[g]
	if code / (NTYPE * NEMP) == CLASS_NONE and a >= ADULT_FROM:
		var k: int = class_of_income(p.tr_class_lines, float(p.tr_points["income"][g]))
		code = (k * NTYPE + (code / NEMP) % NTYPE) * NEMP + code % NEMP
		tl["class_entered"] = int(tl["class_entered"]) + x
	var key: PackedInt32Array = key_of(p.tr_key[u * KEY_STRIDE], b, p.tr_key[u * KEY_STRIDE + 2], code)
	var ks: String = "%d|%d|%d|%d|%d|%d" % [key[0], key[1], key[2], key[3], key[4], key[5]]
	var id: int = p.tr_pt_id[g]
	var v: int = -1
	if (w["by_key"] as Dictionary).has(ks):
		var us: Array = w["by_key"][ks]
		v = int(us[0]) if us.size() == 1 else int(us[KEYED.below(us.size(), p.seed_v, "t22_part", id, p.month, 0)])
	else:
		v = _t22_new_unit(p, w, u, key, ks)
	var m: int = p.tr_pt_mass[g]
	var h := _t22_new_point(p, w, g, v, code)
	p.tr_points["age"][h] = a
	p.tr_pt_age[h * AGE_SLOTS] = x
	for sb3: int in NS:
		p.tr_pt_ag[h * AGE_SLOTS * NS + sb3] = xc[sb3]
	p.tr_pt_mass[h] = x
	p.tr_pt_mass[g] = m - x
	var fr: float = float(x) / float(m)
	p.tr_pt_muq[h] = p.tr_pt_muq[g] * fr
	p.tr_pt_muq[g] -= p.tr_pt_muq[h]
	p.tr_pt_mug[h] = p.tr_pt_mug[g] * fr
	p.tr_pt_mug[g] -= p.tr_pt_mug[h]
	p.tr_count[u] -= x
	p.tr_count[v] += x
	p.tr_age_counts[v * AGE_SLOTS] += x
	tl["splits"] = int(tl["splits"]) + 1
	(tl["split_src"] as Array).append([p.tr_pt_id[h], id])
	var q := PackedInt64Array([0, 0, 0, 0])
	for gr2: int in NG:
		if xs[gr2] <= 0:
			continue
		var held_ms := PackedInt64Array()
		var col: int = 0
		for k4: int in 4:
			held_ms.append(p.tr_pt_T[g * 4 * NG + k4 * NG + gr2])
			col += held_ms[k4]
		var ms := PackedFloat64Array()
		for k2: int in 4:
			ms.append(float(xs[gr2]) * float(held_ms[k2]) / float(col) if col > 0 else 0.0)
		var qg: PackedInt64Array = cap_to(largest_keyed(ms, xs[gr2], p.seed_v, "t22_split_ms", id * NG + gr2, p.month), held_ms)
		var sx: int = p.tr_key[u * KEY_STRIDE + 2]
		for k5: int in 4:
			w["led_age"][(sx * 9 + LC._b10(p.tr_key[u * KEY_STRIDE + 1] * 5)) * 4 * NG + k5 * NG + gr2] -= qg[k5]
			w["led_age"][(sx * 9 + LC._b10(b * 5)) * 4 * NG + k5 * NG + gr2] += qg[k5]
		for k3: int in 4:
			p.tr_pt_T[g * 4 * NG + k3 * NG + gr2] -= qg[k3]
			p.tr_pt_T[h * 4 * NG + k3 * NG + gr2] = qg[k3]
			p.tr_pt_ms[g * 4 + k3] -= qg[k3]
			p.tr_pt_ms[h * 4 + k3] += qg[k3]
			q[k3] += qg[k3]
	var cps: Array = w["cp_of"][g]
	var holds := PackedInt64Array()
	var cm: int = 0
	for c: int in cps:
		holds.append(p.tr_cp_n[c])
		cm += p.tr_cp_n[c]
	holds.append(maxi(0, p.tr_pt_ms[g * 4 + 1] + q[1] - cm))
	var y: PackedInt64Array = split_holds(holds, q[1], p.seed_v, "t22_split_cp", id, p.month)
	for i: int in cps.size():
		if y[i] <= 0:
			continue
		var c2: int = cps[i]
		p.tr_cp_n[c2] -= y[i]
		var fem: bool = p.tr_cp_w[c2] == g
		p.tr_cp_hh.append(p.tr_cp_hh[c2])
		p.tr_cp_w.append(h if fem else p.tr_cp_w[c2])
		p.tr_cp_h.append(p.tr_cp_h[c2] if fem else h)
		p.tr_cp_n.append(y[i])
		var nc: int = p.tr_cp_n.size() - 1
		(w["cp_of"][h] as Array).append(nc)
		(w["cp_of"][p.tr_cp_h[c2] if fem else p.tr_cp_w[c2]] as Array).append(nc)
	var hms: Array = w["hm_of"][g]
	var hh := PackedInt64Array()
	var held: int = 0
	for e: int in hms:
		hh.append(p.tr_hm_n[e])
		held += p.tr_hm_n[e]
	hh.append(maxi(0, m - held))
	var z: PackedInt64Array = split_holds(hh, x, p.seed_v, "t22_split_hm", id, p.month)
	for i2: int in hms.size():
		if z[i2] <= 0:
			continue
		var e2: int = hms[i2]
		p.tr_hm_n[e2] -= z[i2]
		p.tr_hm_pt.append(h)
		p.tr_hm_role.append(p.tr_hm_role[e2])
		p.tr_hm_n.append(z[i2])
		w["hm_h"].append(w["hm_h"][e2])
		(w["hm_of"][h] as Array).append(p.tr_hm_n.size() - 1)
	for name: String in w["ins"]:
		var amt: int = w["ins"][name][g]
		var mv: int = amt * x / m
		w["ins"][name][g] = amt - mv
		w["ins"][name][h] = mv


## A new point in unit v with point g's state and code code, all its masses 0, appended to every point array
static func _t22_new_point(p: RefCounted, w: Dictionary, g: int, v: int, code: int) -> int:
	var h: int = p.tr_pt_mass.size()
	p.tr_pt_mass.append(0)
	p.tr_pt_code.append(code)
	p.tr_pt_q.append(p.tr_pt_q[g])
	p.tr_pt_muq.append(0.0)
	p.tr_pt_mug.append(0.0)
	p.tr_pt_id.append(p.tr_pt_next)
	p.tr_pt_next += 1
	p.tr_pt_age.resize((h + 1) * AGE_SLOTS)
	p.tr_pt_jan.resize((h + 1) * AGE_SLOTS)
	p.tr_pt_old.resize((h + 1) * AGE_SLOTS)
	p.tr_pt_ms.resize((h + 1) * 4)
	p.tr_pt_ag.resize((h + 1) * AGE_SLOTS * NS)
	p.tr_pt_jg.resize((h + 1) * AGE_SLOTS * NS)
	p.tr_pt_og.resize((h + 1) * AGE_SLOTS * NS)
	p.tr_pt_T.resize((h + 1) * 4 * NG)
	w["unit_of"].append(v)
	for name: String in p.tr_points:
		var st: int = w["stride"][name]
		for k: int in st:
			p.tr_points[name].append(p.tr_points[name][g * st + k])
	for name2: String in w["ins"]:
		w["ins"][name2].append(0)
	(w["cp_of"] as Array).append([])
	(w["hm_of"] as Array).append([])
	(w["lists"][v] as Array).append(h)
	return h


## A unit of key key for the splits of unit u that found none: u's K_b, tier size and shares until the yearly re-target, an empty mix
static func _t22_new_unit(p: RefCounted, w: Dictionary, u: int, key: PackedInt32Array, ks: String) -> int:
	var v: int = p.tr_units
	p.tr_key.append_array(key)
	p.tr_count.append(0)
	var z := PackedInt64Array()
	z.resize(AGE_SLOTS)
	p.tr_age_counts.append_array(z)
	p.tr_never_married.append(p.tr_never_married[u])
	p.tr_married_apart.append(p.tr_married_apart[u])
	p.tr_tier_size.append(p.tr_tier_size[u])
	p.tr_mix_off.append(p.tr_mix_code.size())
	p.tr_kb.append(p.tr_kb[u])
	p.tr_units += 1
	(w["lists"] as Array).append([])
	w["by_key"][ks] = [v]
	w["tally"]["new_units"] = int(w["tally"]["new_units"]) + 1
	return v


## v to integers summing to total: the floors, then the remainder to the largest fractional parts, ties from a keyed offset
static func largest_keyed(v: PackedFloat64Array, total: int, seed_v: int, tag: String, a: int, b: int) -> PackedInt64Array:
	var out := PackedInt64Array()
	out.resize(v.size())
	var used: int = 0
	var rows: Array = []
	var o: int = KEYED.below(maxi(1, v.size()), seed_v, tag, a, b, 0)
	for i: int in v.size():
		out[i] = int(floor(v[i]))
		used += out[i]
		rows.append([-(v[i] - floor(v[i])), (i - o + v.size()) % v.size(), i])
	rows.sort()
	var r: int = 0
	while used < total:
		out[int(rows[r % v.size()][2])] += 1
		used += 1
		r += 1
	return out


## x persons drawn from holders holds (x <= Σ holds) by keyed systematic rounding of x × hold ÷ Σ holds, each at most its hold
static func split_holds(holds: PackedInt64Array, x: int, seed_v: int, tag: String, a: int, b: int) -> PackedInt64Array:
	var tot: int = 0
	for hd: int in holds:
		tot += hd
	var v := PackedFloat64Array()
	v.resize(holds.size())
	if tot <= 0 or x <= 0:
		var zero := PackedInt64Array()
		zero.resize(holds.size())
		return zero
	var xx: int = mini(x, tot)
	for i: int in holds.size():
		v[i] = float(xx) * float(holds[i]) / float(tot)
	return cap_to(_systematic(v, xx, seed_v, tag, a * 12 + b), holds)


## out with every entry at most its hold, the excess moved to the entries with room in index order (the total kept while Σ holds allows)
static func cap_to(out: PackedInt64Array, holds: PackedInt64Array) -> PackedInt64Array:
	var over: int = 0
	for i2: int in holds.size():
		if out[i2] > holds[i2]:
			over += out[i2] - holds[i2]
			out[i2] = holds[i2]
	for i3: int in holds.size():
		if over <= 0:
			break
		var room: int = mini(over, holds[i3] - out[i3])
		out[i3] += room
		over -= room
	return out


## (4) The compression (§14.6 (4) under M025): (C1) the unit's points of bit-equal intensive state merged into the lower id; (C2) a unit
## above ⌈1.5 K_b⌉ points (K_b at least 1) back to K_b by merges of the pair of least w_i w_k (‖Δz‖² + ‖Δc‖²), the state kept i's with
## probability w_i ÷ (w_i + w_k); every extensive mass summed (C3's couple sums at the rebuild). Points of mass 0 leave first
static func _t22_compress(p: RefCounted, w: Dictionary) -> void:
	var lists: Array = w["lists"]
	var tl: Dictionary = w["tally"]
	for u: int in p.tr_units:
		var l: Array = []
		for g: int in lists[u]:
			if p.tr_pt_mass[g] > 0:
				l.append(g)
			else:
				tl["dropped"] = int(tl["dropped"]) + 1
		if l.size() <= 1:
			lists[u] = l
			continue
		var before: PackedFloat64Array = _t22_totals(p, w, l)
		l = _t22_coalesce(p, w, u, l)
		var kb: int = cap_target(p, u, l)
		if l.size() > int(ceil(1.5 * float(kb))):
			l = _t22_cap(p, w, u, l, kb)
		var after: PackedFloat64Array = _t22_totals(p, w, l)
		for x: int in before.size():
			if before[x] != after[x]:
				tl["cx_bad"] = int(tl["cx_bad"]) + 1
				break
		lists[u] = l


## A unit's compression target (T2s-drift's fix, TO_E 11:33): max(K_b, the quartiles its points hold), at least 1
## Why not K_b alone: a unit holding more quartiles than K_b had to merge across a quartile line, and that drift accumulated
static func cap_target(p: RefCounted, u: int, l: Array) -> int:
	var seen: Dictionary = {}
	for g: int in l:
		seen[p.tr_pt_q[g]] = true
	return maxi(maxi(1, p.tr_kb[u]), seen.size())


## T2s-cx's extensive totals of a unit's points: by age, J, O, marital state, couple marginal, household entries, instruments, then
## (T2s-gx, M030) the grade cells' mass, J and O by age and T
static func _t22_totals(p: RefCounted, w: Dictionary, l: Array) -> PackedFloat64Array:
	var out := PackedFloat64Array()
	var gb: int = AGE_SLOTS * 3 + 6 + (w["ins"] as Dictionary).size()
	out.resize(gb + AGE_SLOTS * NS * 3 + 4 * NG)
	for g: int in l:
		for x2: int in AGE_SLOTS * NS:
			out[gb + x2] += float(p.tr_pt_ag[g * AGE_SLOTS * NS + x2])
			out[gb + AGE_SLOTS * NS + x2] += float(p.tr_pt_jg[g * AGE_SLOTS * NS + x2])
			out[gb + 2 * AGE_SLOTS * NS + x2] += float(p.tr_pt_og[g * AGE_SLOTS * NS + x2])
		for x3: int in 4 * NG:
			out[gb + 3 * AGE_SLOTS * NS + x3] += float(p.tr_pt_T[g * 4 * NG + x3])
		for s: int in AGE_SLOTS:
			out[s] += float(p.tr_pt_age[g * AGE_SLOTS + s])
			out[AGE_SLOTS + s] += float(p.tr_pt_jan[g * AGE_SLOTS + s])
			out[2 * AGE_SLOTS + s] += float(p.tr_pt_old[g * AGE_SLOTS + s])
		for k: int in 4:
			out[3 * AGE_SLOTS + k] += float(p.tr_pt_ms[g * 4 + k])
		for c: int in w["cp_of"][g]:
			out[3 * AGE_SLOTS + 4] += float(p.tr_cp_n[c])
		for e: int in w["hm_of"][g]:
			out[3 * AGE_SLOTS + 5] += float(p.tr_hm_n[e])
		var x: int = 3 * AGE_SLOTS + 6
		for name: String in w["ins"]:
			out[x] += float(w["ins"][name][g])
			x += 1
	return out


## (C1) bit-equal intensive states: the code and every tr_points field but the start's grade (M030: the grade is the cells), not the
## quartile, the id or the masses
static func _t22_same(p: RefCounted, w: Dictionary, a: int, b: int) -> bool:
	if p.tr_pt_code[a] != p.tr_pt_code[b]:
		return false
	for name: String in p.tr_points:
		if name == "health":
			continue
		var st: int = w["stride"][name]
		for k: int in st:
			if p.tr_points[name][a * st + k] != p.tr_points[name][b * st + k]:
				return false
	return true


static func _t22_coalesce(p: RefCounted, w: Dictionary, u: int, l: Array) -> Array:
	var tl: Dictionary = w["tally"]
	var grp: Dictionary = {}
	for g: int in l:
		var key: String = "%d|%s|%s" % [p.tr_pt_code[g], String.num(float(p.tr_points["income"][g]), 14), String.num(float(p.tr_points["phi"][g]), 14)]
		if not grp.has(key):
			grp[key] = []
		(grp[key] as Array).append(g)
	var gone: Dictionary = {}
	for key2: String in grp:
		var gs: Array = grp[key2]
		if gs.size() < 2:
			continue
		var reps: Array = []
		for g2: int in gs:
			var hit: int = -1
			for r: int in reps.size():
				if _t22_same(p, w, int(reps[r]), g2):
					hit = r
					break
			if hit < 0:
				reps.append(g2)
				continue
			var a: int = int(reps[hit])
			var kept: int = a if p.tr_pt_id[a] < p.tr_pt_id[g2] else g2
			var drop: int = g2 if kept == a else a
			if p.tr_pt_q[kept] != p.tr_pt_q[drop]:
				tl["c1_q_moved"] = int(tl["c1_q_moved"]) + p.tr_pt_mass[drop]
			_t22_merge(p, w, kept, drop, u)
			gone[drop] = true
			reps[hit] = kept
			tl["c1"] = int(tl["c1"]) + 1
	var out: Array = []
	for g3: int in l:
		if not gone.has(g3):
			out.append(g3)
	return out


## (C2) the cap: z (ranks of income and assets, each over its variance in the unit; employment, education and dream kind as 0/1
## mismatches x 2 ÷ their Gini impurity) fixed for the compression, c (marital shares, couple share, household-type shares, the share
## in none and, M030, the four grade shares) recomputed for the merged point; the pair of least w_i w_k (‖Δz‖² + ‖Δc‖²), ties to the
## lower pair
static func _t22_cap(p: RefCounted, w: Dictionary, u: int, l: Array, kb: int) -> Array:
	var tl: Dictionary = w["tally"]
	var n: int = l.size()
	var num: Array = []
	for name: String in ["income", "assets"]:
		var idx: Array = range(n)
		idx.sort_custom(func(i: int, j: int) -> bool: return float(p.tr_points[name][l[i]]) < float(p.tr_points[name][l[j]]) if float(p.tr_points[name][l[i]]) != float(p.tr_points[name][l[j]]) else i < j)
		var r := PackedFloat64Array()
		r.resize(n)
		for k: int in n:
			r[idx[k]] = float(k) / float(maxi(1, n - 1))
		num.append(r)
	var nsc := PackedFloat64Array()
	for v: PackedFloat64Array in num:
		var mean: float = 0.0
		for x: float in v:
			mean += x
		mean /= float(n)
		var var_v: float = 0.0
		for x2: float in v:
			var_v += (x2 - mean) * (x2 - mean)
		var_v /= float(n)
		nsc.append(1.0 / var_v if var_v > 0.0 else 0.0)
	var cat: Array = []
	var csc := PackedFloat64Array()
	for name2: String in ["employment", "education", "dream_kind"]:
		var v2 := PackedInt32Array()
		var cnt: Dictionary = {}
		for g2: int in l:
			v2.append(int(p.tr_points[name2][g2]))
			cnt[v2[v2.size() - 1]] = int(cnt.get(v2[v2.size() - 1], 0)) + 1
		var gini: float = 1.0
		for c in cnt:
			gini -= DM.pow(float(cnt[c]) / float(n), 2.0)
		cat.append(v2)
		csc.append(2.0 / gini if gini > 1e-12 else 0.0)
	var zrow := PackedInt32Array()
	var comp: Array = []
	var alive: Array = []
	for i2: int in n:
		zrow.append(i2)
		comp.append(_t22_comp(p, w, int(l[i2])))
		alive.append(int(l[i2]))
	var left: int = n
	var b10: int = LC._b10(p.tr_key[u * KEY_STRIDE + 1] * 5)
	while left > kb:
		var bi: int = -1
		var bj: int = -1
		var best: float = INF
		var per_q := PackedInt32Array([0, 0, 0, 0])
		for g5 in alive:
			if int(g5) >= 0:
				per_q[p.tr_pt_q[int(g5)]] += 1
		var cross_ok: bool = per_q[0] <= 1 and per_q[1] <= 1 and per_q[2] <= 1 and per_q[3] <= 1
		for i3: int in n:
			if int(alive[i3]) < 0:
				continue
			for j3: int in range(i3 + 1, n):
				if int(alive[j3]) < 0:
					continue
				if not cross_ok and p.tr_pt_q[int(alive[i3])] != p.tr_pt_q[int(alive[j3])]:
					continue
				var d: float = 0.0
				var a: int = zrow[i3]
				var b: int = zrow[j3]
				for q: int in num.size():
					var dz: float = float(num[q][a]) - float(num[q][b])
					d += dz * dz * nsc[q]
				for q2: int in cat.size():
					if cat[q2][a] != cat[q2][b]:
						d += csc[q2]
				var ca: PackedFloat64Array = comp[i3]
				var cb: PackedFloat64Array = comp[j3]
				for q3: int in ca.size():
					d += (ca[q3] - cb[q3]) * (ca[q3] - cb[q3])
				var cost: float = float(p.tr_pt_mass[int(alive[i3])]) * float(p.tr_pt_mass[int(alive[j3])]) * d
				if cost < best:
					best = cost
					bi = i3
					bj = j3
		var gi: int = alive[bi]
		var gj: int = alive[bj]
		var lo: int = bi if p.tr_pt_id[gi] < p.tr_pt_id[gj] else bj
		var hi: int = bj if lo == bi else bi
		var glo: int = alive[lo]
		var ghi: int = alive[hi]
		var wl: float = float(p.tr_pt_mass[glo])
		var wh: float = float(p.tr_pt_mass[ghi])
		var ku: float = KEYED.u(p.seed_v, "t22_merge", u, p.month, p.tr_pt_id[glo] * 100000000 + p.tr_pt_id[ghi])
		var keep: int = lo if ku * (wl + wh) < wl else hi
		var drop: int = hi if keep == lo else lo
		if p.tr_pt_q[int(alive[keep])] != p.tr_pt_q[int(alive[drop])]:
			tl["cbq"] = int(tl["cbq"]) + 1
			tl["cbq_mass"] = int(tl["cbq_mass"]) + p.tr_pt_mass[int(alive[keep])] + p.tr_pt_mass[int(alive[drop])]
		_t22_cb(p, w, alive[keep], alive[drop], b10, wl, wh)
		_t22_book_mu(p, alive[keep], alive[drop], wl, wh, keep == lo)
		_t22_merge(p, w, alive[keep], alive[drop], u)
		comp[keep] = _t22_comp(p, w, int(alive[keep]))
		alive[drop] = -1
		left -= 1
		tl["c2"] = int(tl["c2"]) + 1
	var out: Array = []
	for g4 in alive:
		if int(g4) >= 0:
			out.append(int(g4))
	return out


## (C2)'s c of a point: its marital shares (four), its couple-married share, its household entries' shares by type (six) and in none,
## its grade shares (four, M030)
static func _t22_comp(p: RefCounted, w: Dictionary, g: int) -> PackedFloat64Array:
	var out := PackedFloat64Array()
	out.resize(12 + NG)
	var m: float = float(p.tr_pt_mass[g])
	if m <= 0.0:
		return out
	for k: int in 4:
		out[k] = float(p.tr_pt_ms[g * 4 + k]) / m
	var cm: float = 0.0
	for c: int in w["cp_of"][g]:
		cm += float(p.tr_cp_n[c])
	out[4] = cm / m
	var held: float = 0.0
	for e: int in w["hm_of"][g]:
		out[5 + int(w["htype"][w["hm_h"][e]])] += float(p.tr_hm_n[e]) / m
		held += float(p.tr_hm_n[e])
	out[11] = maxf(0.0, m - held) / m
	for gr: int in NG:
		var gm: int = 0
		for k2: int in 4:
			gm += p.tr_pt_T[g * 4 * NG + k2 * NG + gr]
		out[12 + gr] = float(gm) / m
	return out


## T2s-cb's tallies of one cap merge: the married and couple masses by quartile x 10-year band, after against before, and the merge's
## variance p_i p_k (M_i + M_k)² on the two cells when the quartiles differ
static func _t22_cb(p: RefCounted, w: Dictionary, keep: int, drop: int, b10: int, wl: float, wh: float) -> void:
	var qk: int = p.tr_pt_q[keep]
	var qd: int = p.tr_pt_q[drop]
	var tl: Dictionary = w["tally"]
	var pp: float = wl * wh / ((wl + wh) * (wl + wh))
	var mk: float = float(p.tr_pt_ms[keep * 4 + 1])
	var md: float = float(p.tr_pt_ms[drop * 4 + 1])
	var wk: float = float(p.tr_pt_mass[keep])
	var wd: float = float(p.tr_pt_mass[drop])
	var pk: float = wk / (wk + wd)
	if qk == qd:
		return
	var ck: float = 0.0
	var cd: float = 0.0
	for c: int in w["cp_of"][keep]:
		ck += float(p.tr_cp_n[c])
	for c2: int in w["cp_of"][drop]:
		cd += float(p.tr_cp_n[c2])
	var xk: int = qk * 9 + b10
	var xd: int = qd * 9 + b10
	tl["cb_mr"][xk] += md
	tl["cb_mr"][xd] -= md
	tl["cb_cr"][xk] += cd
	tl["cb_cr"][xd] -= cd
	for x: int in [xk, xd]:
		tl["cb_mv"][x] += pp * (mk + md) * (mk + md)
		tl["cb_cv"][x] += pp * (ck + cd) * (ck + cd)
	var mu_m: float = pk * md - (1.0 - pk) * mk
	var mu_c: float = pk * cd - (1.0 - pk) * ck
	tl["cb_mm"][xk] += mu_m
	tl["cb_mm"][xd] -= mu_m
	tl["cb_cm"][xk] += mu_c
	tl["cb_cm"][xd] -= mu_c


## M025 C4: a (point, age, grade, class) cell's remaining births by month after month mc, its own vector if merged before, else its birth
## months (0 at months <= mc)
static func _t22_rem(p: RefCounted, g: int, sl: int, sb: int, a: int, mc: int) -> PackedInt64Array:
	var rk: int = (p.tr_pt_id[g] * AGE_SLOTS + sl) * NS + sb
	if p.tr_pt_rem.has(rk):
		return (p.tr_pt_rem[rk] as PackedInt64Array).duplicate()
	var j: int = p.tr_pt_jg[(g * AGE_SLOTS + sl) * NS + sb]
	var out := PackedInt64Array()
	out.resize(12)
	if j > 0:
		out = birth_months(p, p.tr_pt_id[g] * NS + sb, a, j)
		for k: int in mini(12, mc + 1):
			out[k] = 0
	return out


## T2s-drift's stock form (TO_E 11:37): a cap merge's expected married mass moved into the kept point's cell, p_i m_k − p_k m_i,
## booked to the kept point when it crosses a quartile line (M030: merges sum the grade cells, so none crosses a grade line)
static func _t22_book_mu(p: RefCounted, keep: int, drop: int, wl: float, wh: float, keep_is_lo: bool) -> void:
	var wk: float = wl if keep_is_lo else wh
	var wd: float = wh if keep_is_lo else wl
	var pk: float = wk / (wk + wd)
	var mu: float = pk * float(p.tr_pt_ms[drop * 4 + 1]) - (1.0 - pk) * float(p.tr_pt_ms[keep * 4 + 1])
	if p.tr_pt_q[keep] != p.tr_pt_q[drop]:
		p.tr_pt_muq[keep] += mu


static func _t22_merge(p: RefCounted, w: Dictionary, i: int, k: int, u: int) -> void:
	var mc: int = p.month % 12
	var b: int = p.tr_key[u * KEY_STRIDE + 1]
	for s0: int in AGE_SLOTS:
		for sb: int in NS:
			var cx: int = s0 * NS + sb
			var rd: int = (p.tr_pt_id[k] * AGE_SLOTS + s0) * NS + sb
			if mc < 11 and p.tr_pt_og[i * AGE_SLOTS * NS + cx] + p.tr_pt_og[k * AGE_SLOTS * NS + cx] > 0:
				var ri: PackedInt64Array = _t22_rem(p, i, s0, sb, b * 5 + s0, mc)
				var rk2: PackedInt64Array = _t22_rem(p, k, s0, sb, b * 5 + s0, mc)
				for m2: int in 12:
					ri[m2] += rk2[m2]
				p.tr_pt_rem[(p.tr_pt_id[i] * AGE_SLOTS + s0) * NS + sb] = ri
			p.tr_pt_rem.erase(rd)
	p.tr_pt_muq[i] += p.tr_pt_muq[k]
	p.tr_pt_muq[k] = 0.0
	p.tr_pt_mug[i] += p.tr_pt_mug[k]
	p.tr_pt_mug[k] = 0.0
	p.tr_pt_mass[i] += p.tr_pt_mass[k]
	p.tr_pt_mass[k] = 0
	for s: int in AGE_SLOTS:
		p.tr_pt_age[i * AGE_SLOTS + s] += p.tr_pt_age[k * AGE_SLOTS + s]
		p.tr_pt_jan[i * AGE_SLOTS + s] += p.tr_pt_jan[k * AGE_SLOTS + s]
		p.tr_pt_old[i * AGE_SLOTS + s] += p.tr_pt_old[k * AGE_SLOTS + s]
	for s2: int in 4:
		p.tr_pt_ms[i * 4 + s2] += p.tr_pt_ms[k * 4 + s2]
	for x: int in AGE_SLOTS * NS:
		p.tr_pt_ag[i * AGE_SLOTS * NS + x] += p.tr_pt_ag[k * AGE_SLOTS * NS + x]
		p.tr_pt_jg[i * AGE_SLOTS * NS + x] += p.tr_pt_jg[k * AGE_SLOTS * NS + x]
		p.tr_pt_og[i * AGE_SLOTS * NS + x] += p.tr_pt_og[k * AGE_SLOTS * NS + x]
		p.tr_pt_ag[k * AGE_SLOTS * NS + x] = 0
		p.tr_pt_jg[k * AGE_SLOTS * NS + x] = 0
		p.tr_pt_og[k * AGE_SLOTS * NS + x] = 0
	for x2: int in 4 * NG:
		p.tr_pt_T[i * 4 * NG + x2] += p.tr_pt_T[k * 4 * NG + x2]
		p.tr_pt_T[k * 4 * NG + x2] = 0
	for name: String in w["ins"]:
		w["ins"][name][i] += w["ins"][name][k]
		w["ins"][name][k] = 0
	for c: int in w["cp_of"][k]:
		if p.tr_cp_w[c] == k:
			p.tr_cp_w[c] = i
		if p.tr_cp_h[c] == k:
			p.tr_cp_h[c] = i
		(w["cp_of"][i] as Array).append(c)
	for e: int in w["hm_of"][k]:
		p.tr_hm_pt[e] = i
		(w["hm_of"][i] as Array).append(e)
	w["cp_of"][k] = []
	w["hm_of"][k] = []


## The point arrays rebuilt once in unit order (each unit's points as its list holds them), the entries re-pointed, the empty ones
## dropped and the duplicates summed, the household entries in household-bundle order; the points' assets and debt re-read from their
## instruments (§12.8 10.5's one record)
static func _t22_rebuild(p: RefCounted, w: Dictionary) -> void:
	var lists: Array = w["lists"]
	var order := PackedInt64Array()
	var off := PackedInt64Array()
	for u: int in p.tr_units:
		off.append(order.size())
		for g: int in lists[u]:
			if p.tr_pt_mass[g] > 0:
				order.append(g)
	off.append(order.size())
	var n_old: int = p.tr_pt_mass.size()
	var nid := PackedInt64Array()
	nid.resize(n_old)
	nid.fill(-1)
	for i: int in order.size():
		nid[order[i]] = i
	p.tr_pt_off = off
	p.tr_pt_mass = _perm_i64(p.tr_pt_mass, order, 1)
	p.tr_pt_id = _perm_i64(p.tr_pt_id, order, 1)
	p.tr_pt_age = _perm_i64(p.tr_pt_age, order, AGE_SLOTS)
	p.tr_pt_jan = _perm_i64(p.tr_pt_jan, order, AGE_SLOTS)
	p.tr_pt_old = _perm_i64(p.tr_pt_old, order, AGE_SLOTS)
	p.tr_pt_ms = _perm_i64(p.tr_pt_ms, order, 4)
	p.tr_pt_ag = _perm_i64(p.tr_pt_ag, order, AGE_SLOTS * NS)
	p.tr_pt_jg = _perm_i64(p.tr_pt_jg, order, AGE_SLOTS * NS)
	p.tr_pt_og = _perm_i64(p.tr_pt_og, order, AGE_SLOTS * NS)
	p.tr_pt_T = _perm_i64(p.tr_pt_T, order, 4 * NG)
	var code := PackedInt32Array()
	code.resize(order.size())
	for i2: int in order.size():
		code[i2] = p.tr_pt_code[order[i2]]
	p.tr_pt_code = code
	var pq := PackedInt32Array()
	pq.resize(order.size())
	for i4: int in order.size():
		pq[i4] = p.tr_pt_q[order[i4]]
	p.tr_pt_q = pq
	var muq := PackedFloat64Array()
	muq.resize(order.size())
	var mug := PackedFloat64Array()
	mug.resize(order.size())
	for i5: int in order.size():
		muq[i5] = p.tr_pt_muq[order[i5]]
		mug[i5] = p.tr_pt_mug[order[i5]]
	p.tr_pt_muq = muq
	p.tr_pt_mug = mug
	for name: String in p.tr_points:
		var st: int = w["stride"][name]
		var src = p.tr_points[name]
		var dst = src.duplicate()
		dst.resize(order.size() * st)
		for i3: int in order.size():
			for k: int in st:
				dst[i3 * st + k] = src[order[i3] * st + k]
		p.tr_points[name] = dst
	for name2: String in w["ins"]:
		var pts: PackedInt64Array = _perm_i64(w["ins"][name2], order, 1)
		pts.append_array(w["ins_ind"][name2])
		p.tr_instruments[name2] = pts
	var seen: Dictionary = {}
	var cw := PackedInt32Array()
	var chh := PackedInt32Array()
	var chu := PackedInt32Array()
	var cn := PackedInt64Array()
	var lost: int = 0
	var lost_hm: int = 0
	for c: int in p.tr_cp_n.size():
		if p.tr_cp_n[c] <= 0:
			continue
		var a: int = nid[p.tr_cp_w[c]]
		var b: int = nid[p.tr_cp_h[c]]
		if a < 0 or b < 0:
			lost += p.tr_cp_n[c]
			continue
		var ck: int = (a * order.size() + b) * (p.tr_hh_keys.size() + 1) + p.tr_cp_hh[c]
		if seen.has(ck):
			cn[int(seen[ck])] += p.tr_cp_n[c]
			continue
		seen[ck] = cn.size()
		chh.append(p.tr_cp_hh[c])
		cw.append(a)
		chu.append(b)
		cn.append(p.tr_cp_n[c])
	p.tr_cp_hh = chh
	p.tr_cp_w = cw
	p.tr_cp_h = chu
	p.tr_cp_n = cn
	var hm_h: PackedInt32Array = w["hm_h"]
	var rows: Array = []
	for e: int in p.tr_hm_n.size():
		if p.tr_hm_n[e] <= 0:
			continue
		if nid[p.tr_hm_pt[e]] < 0:
			lost_hm += p.tr_hm_n[e]
			continue
		rows.append([hm_h[e], e])
	rows.sort()
	var seen2: Dictionary = {}
	var hpt := PackedInt32Array()
	var hro := PackedInt32Array()
	var hn := PackedInt64Array()
	var hoff := PackedInt64Array()
	hoff.resize(p.tr_hh_keys.size() + 1)
	var at: int = 0
	for r: Array in rows:
		var e2: int = int(r[1])
		var hk: int = (int(r[0]) * order.size() + nid[p.tr_hm_pt[e2]]) * 8 + p.tr_hm_role[e2]
		if seen2.has(hk):
			hn[int(seen2[hk])] += p.tr_hm_n[e2]
			continue
		while at <= int(r[0]):
			hoff[at] = hpt.size()
			at += 1
		seen2[hk] = hn.size()
		hpt.append(nid[p.tr_hm_pt[e2]])
		hro.append(p.tr_hm_role[e2])
		hn.append(p.tr_hm_n[e2])
	while at <= p.tr_hh_keys.size():
		hoff[at] = hpt.size()
		at += 1
	p.tr_hm_off = hoff
	p.tr_hm_pt = hpt
	p.tr_hm_role = hro
	p.tr_hm_n = hn
	w["tally"]["lost"] = lost
	var ids: Dictionary = {}
	for g5: int in p.tr_pt_id:
		ids[g5] = true
	for rk3 in p.tr_pt_rem.keys():
		if not ids.has(int(rk3) / (AGE_SLOTS * NS)):
			p.tr_pt_rem.erase(rk3)
	w["tally"]["lost_hm"] = lost_hm
	_point_wealth(p)


static func _perm_i64(src: PackedInt64Array, order: PackedInt64Array, st: int) -> PackedInt64Array:
	var out := PackedInt64Array()
	out.resize(order.size() * st)
	for i: int in order.size():
		for k: int in st:
			out[i * st + k] = src[order[i] * st + k]
	return out


## The points' assets and debt from their instruments ÷ their mass (as _wealth_from_instruments, the points only)
## Why not _wealth_from_instruments: it also re-writes the individuals, whose wealth the persons layer has moved since the start
static func _point_wealth(p: RefCounted) -> void:
	var by: Dictionary = (_v(p, "instrument_age_profiles") as Dictionary)["by_instrument"]
	var fin: Array = []
	for name: String in p.tr_instruments:
		if String(by.get(name, "")) == "financial":
			fin.append(name)
	fin.sort()
	var n_pts: int = p.tr_pt_off[p.tr_units]
	for g: int in n_pts:
		var a: int = 0
		for name2: String in fin:
			a += p.tr_instruments[name2][g]
		var m: float = float(p.tr_pt_mass[g])
		p.tr_points["assets"][g] = float(a) / m / 1e4 if m > 0.0 else 0.0
		p.tr_points["debt"][g] = float(p.tr_instruments["borrowing"][g]) / m / 1e4 if m > 0.0 else 0.0


static func _zeros_i(n: int) -> PackedInt64Array:
	var a := PackedInt64Array()
	a.resize(n)
	return a


static func _zeros_f(n: int) -> PackedFloat64Array:
	var a := PackedFloat64Array()
	a.resize(n)
	return a


## μ_a(t) = −ln(1 − q_x(a, s, t)) by single age x sex for the month's year: the 2022 table x the ratio (§14.6 (2), M009 (3), R75 medium)
static func mu_path(p: RefCounted, variant: String = "medium") -> PackedFloat64Array:
	var lt: Dictionary = LC._lc(p, "qx_2022")
	var r: Dictionary = _v(p, "mortality_ratio_ipss_2023")
	var years: Array = r["years"]
	var yi: int = clampi(p.base_year + p.month / 12 - int(years[0]), -1, years.size() - 1)
	var out := PackedFloat64Array()
	out.resize(p.AGES * 2)
	for s: int in 2:
		var tab: Array = lt["men" if s == p.MALE else "women"]
		for a: int in p.AGES:
			var q: float = float(tab[mini(a, tab.size() - 1)])
			if yi >= 0:
				q = minf(1.0, q * float(r["by_variant"][variant]["M" if s == p.MALE else "F"][yi][mini(a, int(r["ages"]) - 1)]))
			out[a * 2 + s] = INF if q >= 1.0 else -DM.log(1.0 - q)
	return out


## (2) and (3) (§14.6 as built, M030 §3): each (point, age, grade, class) cell after the ageing dies at Bin(m, q_m), q_m = death_q(c_{a,s},
## g, k, μ_a(t), 12); the not-yet-aged among the dead by HG(m, O_g, d); each grade's dead over its marital column, the married dead
## summed over grades over the couple points by sequential hypergeometric draws, each partner's point moving that mass from married
## to widowed in grades drawn by hypergeometric over its married row T[1][·]
static func _t22_deaths(p: RefCounted, w: Dictionary) -> void:
	var tl: Dictionary = w["tally"]
	var mu: PackedFloat64Array = mu_path(p)
	var lists: Array = w["lists"]
	var unit_of: PackedInt32Array = w["unit_of"]
	for u: int in p.tr_units:
		var b: int = p.tr_key[u * KEY_STRIDE + 1]
		var s: int = p.tr_key[u * KEY_STRIDE + 2]
		for g: int in lists[u]:
			if p.tr_pt_mass[g] <= 0:
				continue
			var id: int = p.tr_pt_id[g]
			var k: int = p.tr_pt_q[g]
			var dead: int = 0
			var dead_g: PackedInt64Array = _zeros_i(NG)
			for sl: int in _slots_in(b):
				var a: int = b * 5 + sl
				var ix: int = a * 2 + s
				for sb: int in NS:
					var gr: int = sb / NK
					var cx: int = (g * AGE_SLOTS + sl) * NS + sb
					var m: int = p.tr_pt_ag[cx]
					if m <= 0:
						continue
					var gk: int = id * NS + sb
					var qm: float = 1.0 if mu[ix] == INF else LC.death_q(p, p.tr_c[ix], a, gr, k, mu[ix], 12.0)
					tl["x_as"][ix] += float(m) / 12.0
					tl["e_as"][ix] += float(m) * qm
					tl["v_as"][ix] += float(m) * qm * (1.0 - qm)
					tl["x_g"][ix * NG + gr] += float(m) / 12.0
					tl["x_k"][ix * 4 + k] += float(m) / 12.0
					var d: int = binomial(m, qm, KEYED.u(p.seed_v, "t22_death", gk, a, p.month))
					if d <= 0:
						continue
					var o: int = p.tr_pt_og[cx]
					var od: int = hypergeometric(m, o, d, KEYED.u(p.seed_v, "t22_death_old", gk, a, p.month))
					w["led_death"][2 * 9 * 4 * NG + ix * NG + gr] -= d
					p.tr_pt_og[cx] -= od
					p.tr_pt_ag[cx] -= d
					p.tr_pt_old[g * AGE_SLOTS + sl] -= od
					p.tr_pt_age[g * AGE_SLOTS + sl] -= d
					p.tr_age_counts[u * AGE_SLOTS + sl] -= d
					tl["d_as"][ix] += d
					tl["d_old"][ix] += od
					tl["d_g"][ix * NG + gr] += d
					tl["d_k"][ix * 4 + k] += d
					dead_g[gr] += d
					dead += d
			if dead <= 0:
				continue
			tl["deaths"] = int(tl["deaths"]) + dead
			var keep_fr: float = float(p.tr_pt_mass[g] - dead) / float(p.tr_pt_mass[g])
			p.tr_pt_muq[g] *= keep_fr
			p.tr_pt_mug[g] *= keep_fr
			p.tr_pt_mass[g] -= dead
			p.tr_count[u] -= dead
			var married0: int = p.tr_pt_ms[g * 4 + 1]
			var md1: PackedInt64Array = _zeros_i(NG)
			for gr2: int in NG:
				if dead_g[gr2] <= 0:
					continue
				var col := PackedInt64Array()
				for k2: int in 4:
					col.append(p.tr_pt_T[g * 4 * NG + k2 * NG + gr2])
				var md: PackedInt64Array = hypergeometric_split(col, dead_g[gr2], p.seed_v, "t22_death_ms", (id * NG + gr2) * 1200 + p.month)
				for k3: int in 4:
					w["led_death"][(s * 9 + LC._b10(b * 5)) * 4 * NG + k3 * NG + gr2] -= md[k3]
					p.tr_pt_T[g * 4 * NG + k3 * NG + gr2] -= md[k3]
					p.tr_pt_ms[g * 4 + k3] -= md[k3]
				md1[gr2] = md[1]
			var mdt: int = 0
			for g6: int in NG:
				mdt += md1[g6]
			if mdt <= 0:
				continue
			var cps: Array = w["cp_of"][g]
			var holds := PackedInt64Array()
			var cm: int = 0
			for c: int in cps:
				holds.append(p.tr_cp_n[c])
				cm += p.tr_cp_n[c]
			holds.append(maxi(0, married0 - cm))
			var y: PackedInt64Array = hypergeometric_split(holds, mdt, p.seed_v, "t22_death_cp", id * 1200 + p.month)
			for i: int in cps.size():
				if y[i] <= 0:
					continue
				var c2: int = cps[i]
				p.tr_cp_n[c2] -= y[i]
				var other: int = p.tr_cp_h[c2] if p.tr_cp_w[c2] == g else p.tr_cp_w[c2]
				var wv: int = mini(y[i], p.tr_pt_ms[other * 4 + 1])
				tl["couples_lost"] = int(tl["couples_lost"]) + y[i]
				if wv <= 0:
					continue
				var row1 := PackedInt64Array()
				var n1: int = 0
				for g3: int in NG:
					row1.append(p.tr_pt_T[other * 4 * NG + NG + g3])
					n1 += row1[g3]
				var wg: PackedInt64Array = hypergeometric_split(row1, wv, p.seed_v, "t22_widow", (p.tr_pt_id[other] * 1200 + p.month) * 64 + c2 % 64)
				var uo: int = unit_of[other]
				var wx: int = (p.tr_key[uo * KEY_STRIDE + 2] * 9 + LC._b10(p.tr_key[uo * KEY_STRIDE + 1] * 5)) * NG
				var lw: int = (p.tr_key[uo * KEY_STRIDE + 2] * 9 + LC._b10(p.tr_key[uo * KEY_STRIDE + 1] * 5)) * 4 * NG
				for g4: int in NG:
					w["led_death"][lw + NG + g4] -= wg[g4]
					w["led_death"][lw + 2 * NG + g4] += wg[g4]
					p.tr_pt_T[other * 4 * NG + NG + g4] -= wg[g4]
					p.tr_pt_T[other * 4 * NG + 2 * NG + g4] += wg[g4]
					var pr: float = float(row1[g4]) / float(n1)
					tl["wg_x"][wx + g4] += float(wg[g4])
					tl["wg_e"][wx + g4] += float(wv) * pr
					tl["wg_v"][wx + g4] += float(wv) * pr * (1.0 - pr) * float(n1 - wv) / float(maxi(1, n1 - 1))
					for dg: int in NG:
						tl["wg_n"][(wx + dg) * NG + g4] += float(wg[g4]) * float(md1[dg]) / float(mdt)
				p.tr_pt_ms[other * 4 + 1] -= wv
				p.tr_pt_ms[other * 4 + 2] += wv
				tl["widowed"] = int(tl["widowed"]) + wv


static func _slots_in(b: int) -> int:
	return AGE_SLOTS if b == BANDS - 1 else 5


## Each point's quartile (§14.6 (2) as built, T until T2.3): its household entries' bundle equivalized incomes (Σ n x income ÷
## households ÷ √(persons ÷ households)) and its mass in no bundle at its own income, mass-weighted; the cuts by mass in the 10-year
## band, both sexes, the point at its mass's midpoint
static func _t22_quartiles(p: RefCounted, w: Dictionary = {}) -> void:
	if not w.is_empty():
		_t22_quartiles_w(p, w)
		return
	var n_pts: int = p.tr_pt_off[p.tr_units]
	var inc: PackedFloat64Array = p.tr_points["income"]
	var eq := PackedFloat64Array()
	eq.resize(p.tr_hh_keys.size())
	var held := PackedInt64Array()
	held.resize(n_pts)
	var sum_e := PackedFloat64Array()
	sum_e.resize(n_pts)
	for h: int in p.tr_hh_keys.size():
		var hc: float = float(int(p.tr_hh[p.tr_hh_keys[h]]["count"]))
		var tot: float = 0.0
		var pers: float = 0.0
		for e: int in range(p.tr_hm_off[h], p.tr_hm_off[h + 1]):
			tot += float(p.tr_hm_n[e]) * inc[p.tr_hm_pt[e]]
			pers += float(p.tr_hm_n[e])
		eq[h] = (tot / hc) / sqrt(pers / hc) if hc > 0.0 and pers > 0.0 else 0.0
		for e2: int in range(p.tr_hm_off[h], p.tr_hm_off[h + 1]):
			held[p.tr_hm_pt[e2]] += p.tr_hm_n[e2]
			sum_e[p.tr_hm_pt[e2]] += float(p.tr_hm_n[e2]) * eq[h]
	var by: Array = []
	for b10: int in 9:
		by.append([])
	for u: int in p.tr_units:
		var b10b: int = LC._b10(p.tr_key[u * KEY_STRIDE + 1] * 5)
		for g: int in range(p.tr_pt_off[u], p.tr_pt_off[u + 1]):
			var m: int = p.tr_pt_mass[g]
			var rest: int = maxi(0, m - held[g])
			var den: float = float(held[g] + rest)
			var e3: float = (sum_e[g] + float(rest) * inc[g]) / den if den > 0.0 else inc[g]
			(by[b10b] as Array).append([e3, g, m])
	p.tr_pt_q = PackedInt32Array()
	p.tr_pt_q.resize(n_pts)
	var qm := PackedFloat64Array([0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0])
	for b2: int in 9:
		var rows: Array = by[b2]
		rows.sort()
		var tot2: float = 0.0
		for r: Array in rows:
			tot2 += float(r[2])
		var acc: float = 0.0
		for r2: Array in rows:
			var pos: float = (acc + 0.5 * float(r2[2])) / tot2 if tot2 > 0.0 else 0.0
			var kq: int = 3 if pos < 0.25 else (2 if pos < 0.5 else (1 if pos < 0.75 else 0))
			p.tr_pt_q[int(r2[1])] = kq
			qm[kq] += float(r2[0]) * float(r2[2])
			qm[4 + kq] += float(r2[2])
			acc += float(r2[2])
	p.tr_margins["t22_q_means"] = qm


## §14.6 (6): the month's one quartile re-read, after the deaths and before the compression, on the working lists (the units'
## points with the splits' new ones; every household entry with its bundle from hm_h), the read and the cuts as _t22_quartiles
## Why not after the compression: the cap's target max(K_b, quartiles present) would then be judged on quartiles it never saw (T2s-np)
static func _t22_quartiles_w(p: RefCounted, w: Dictionary) -> void:
	var n_pts: int = p.tr_pt_mass.size()
	var inc: PackedFloat64Array = p.tr_points["income"]
	var hm_h: PackedInt32Array = w["hm_h"]
	var nh: int = p.tr_hh_keys.size()
	var tot := PackedFloat64Array()
	tot.resize(nh)
	var pers := PackedFloat64Array()
	pers.resize(nh)
	for e: int in p.tr_hm_n.size():
		if p.tr_hm_n[e] <= 0:
			continue
		tot[hm_h[e]] += float(p.tr_hm_n[e]) * inc[p.tr_hm_pt[e]]
		pers[hm_h[e]] += float(p.tr_hm_n[e])
	var eq := PackedFloat64Array()
	eq.resize(nh)
	for h: int in nh:
		var hc: float = float(int(p.tr_hh[p.tr_hh_keys[h]]["count"]))
		eq[h] = (tot[h] / hc) / sqrt(pers[h] / hc) if hc > 0.0 and pers[h] > 0.0 else 0.0
	var held := PackedInt64Array()
	held.resize(n_pts)
	var sum_e := PackedFloat64Array()
	sum_e.resize(n_pts)
	for e2: int in p.tr_hm_n.size():
		if p.tr_hm_n[e2] <= 0:
			continue
		held[p.tr_hm_pt[e2]] += p.tr_hm_n[e2]
		sum_e[p.tr_hm_pt[e2]] += float(p.tr_hm_n[e2]) * eq[hm_h[e2]]
	var by: Array = []
	for b10: int in 9:
		by.append([])
	var lists: Array = w["lists"]
	for u: int in p.tr_units:
		var b10b: int = LC._b10(p.tr_key[u * KEY_STRIDE + 1] * 5)
		for g: int in lists[u]:
			var m: int = p.tr_pt_mass[g]
			if m <= 0:
				continue
			var rest: int = maxi(0, m - held[g])
			var den: float = float(held[g] + rest)
			var e3: float = (sum_e[g] + float(rest) * inc[g]) / den if den > 0.0 else inc[g]
			(by[b10b] as Array).append([e3, g, m])
	var qm := PackedFloat64Array([0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0])
	for b2: int in 9:
		var rows: Array = by[b2]
		rows.sort()
		var tot2: float = 0.0
		for r: Array in rows:
			tot2 += float(r[2])
		var acc: float = 0.0
		for r2: Array in rows:
			var pos: float = (acc + 0.5 * float(r2[2])) / tot2 if tot2 > 0.0 else 0.0
			var kq: int = 3 if pos < 0.25 else (2 if pos < 0.5 else (1 if pos < 0.75 else 0))
			p.tr_pt_q[int(r2[1])] = kq
			qm[kq] += float(r2[0]) * float(r2[2])
			qm[4 + kq] += float(r2[2])
			acc += float(r2[2])
	p.tr_margins["t22_q_means"] = qm


## c_{a,s} (§14.4a, §14.6 (2), CALIBRATED): once, at the start, per single age and sex by LC.solve_c's bisection (on [0, 16], 60 halvings)
## of Σ s_{g,k} exp(−c m_g I_k μ_a) = 1 − q_x on the observed 2022 table, s the points' masses by grade x quartile at the age (from the
## grade cells, or with from_cells false each point's whole mass at its start grade, retired as T2s-c0's comparison by M036); an age with no mass takes
## its 10-year band's, counted in tr_margins["t22_c_band"]
static func _t22_solve_c(p: RefCounted, from_cells: bool) -> void:
	var m: Array = LC._lc(p, "death_multiplier")
	var lt: Dictionary = LC._lc(p, "qx_2022")
	var ws := PackedFloat64Array()
	ws.resize(p.AGES * 2 * NG * 4)
	var wb := PackedFloat64Array()
	wb.resize(9 * 2 * NG * 4)
	for u: int in p.tr_units:
		var b: int = p.tr_key[u * KEY_STRIDE + 1]
		var s: int = p.tr_key[u * KEY_STRIDE + 2]
		for g: int in range(p.tr_pt_off[u], p.tr_pt_off[u + 1]):
			for sl: int in _slots_in(b):
				for sb: int in NS:
					var gr: int = sb / NK
					if not from_cells and sb != int(p.tr_points["health"][g]) * NK:
						continue
					var x: float = float(p.tr_pt_ag[(g * AGE_SLOTS + sl) * NS + sb] if from_cells else p.tr_pt_age[g * AGE_SLOTS + sl])
					if x <= 0.0:
						continue
					var a: int = b * 5 + sl
					var gk: int = gr * 4 + p.tr_pt_q[g]
					ws[(a * 2 + s) * NG * 4 + gk] += x
					wb[(LC._b10(a) * 2 + s) * NG * 4 + gk] += x
	p.tr_c = PackedFloat64Array()
	p.tr_c.resize(p.AGES * 2)
	var band: int = 0
	for a2: int in p.AGES:
		for s2: int in 2:
			var src: PackedFloat64Array = ws
			var cell: int = (a2 * 2 + s2) * NG * 4
			var tot: float = 0.0
			for x0: int in NG * 4:
				tot += ws[cell + x0]
			if tot <= 0.0:
				src = wb
				cell = (LC._b10(a2) * 2 + s2) * NG * 4
				band += 1
				for x1: int in NG * 4:
					tot += wb[cell + x1]
			var tab: Array = lt["men" if s2 == p.MALE else "women"]
			var q: float = float(tab[mini(a2, tab.size() - 1)])
			if tot <= 0.0 or q >= 1.0:
				p.tr_c[a2 * 2 + s2] = 1.0
				continue
			var mu: float = -DM.log(1.0 - q)
			var target: float = DM.exp(-mu)
			var lo: float = 0.0
			var hi: float = 16.0
			for it: int in 60:
				var c: float = 0.5 * (lo + hi)
				var surv: float = 0.0
				for gg: int in NG:
					for k: int in 4:
						surv += src[cell + gg * 4 + k] / tot * DM.exp(-c * float(m[gg]) * LC.income_factor(p, a2, k) * mu)
				if surv > target:
					lo = c
				else:
					hi = c
			p.tr_c[a2 * 2 + s2] = 0.5 * (lo + hi)
	p.tr_margins["t22_c_band"] = band


## (C5, M025b) per household-bundle block, after the rebuild's sums (C3): while its couple entries exceed its cap (its start count, at
## least ⌈1.5 (P_w + P_h − 1)⌉), the lightest cell off a heaviest-first spanning forest and the forest's path close a cycle, moved by
## +d_1 / −d_1 with probability d_2 ÷ (d_1 + d_2), else −d_2 / +d_2; the empty cells dropped. T2s-c5x's marginals and T2s-c5b's cells
## (wife quartile x husband quartile x the husband's 10-year band, and the both-earning couples by band) tallied
static func _t22_c5(p: RefCounted, w: Dictionary) -> void:
	var tl: Dictionary = w["tally"]
	var unit_of := PackedInt32Array()
	unit_of.resize(p.tr_pt_off[p.tr_units])
	for u: int in p.tr_units:
		for g: int in range(p.tr_pt_off[u], p.tr_pt_off[u + 1]):
			unit_of[g] = u
	var blocks: Dictionary = {}
	for c: int in p.tr_cp_n.size():
		if not blocks.has(p.tr_cp_hh[c]):
			blocks[p.tr_cp_hh[c]] = []
		(blocks[p.tr_cp_hh[c]] as Array).append(c)
	var bk: Array = blocks.keys()
	bk.sort()
	for hb in bk:
		var cells: Array = blocks[hb]
		var pw: Dictionary = {}
		var ph: Dictionary = {}
		for c2: int in cells:
			pw[p.tr_cp_w[c2]] = true
			ph[p.tr_cp_h[c2]] = true
		var cap: int = maxi(int(p.tr_cp_cap.get(int(hb), 0)), int(ceil(1.5 * float(pw.size() + ph.size() - 1))))
		if cells.size() <= cap:
			continue
		tl["cp_blocks_capped"] = int(tl["cp_blocks_capped"]) + 1
		var before: Dictionary = _t22_c5_marg(p, cells)
		_t22_c5_block(p, tl, cells, cap, int(hb), unit_of)
		var kept: Array = []
		for c3: int in cells:
			if p.tr_cp_n[c3] > 0:
				kept.append(c3)
		if kept.size() > cap:
			tl["c5_over"] = int(tl["c5_over"]) + 1
		var after: Dictionary = _t22_c5_marg(p, kept)
		if before.hash() != after.hash() or before.size() != after.size():
			tl["c5_x"] = int(tl["c5_x"]) + 1
	var hh := PackedInt32Array()
	var cw := PackedInt32Array()
	var ch := PackedInt32Array()
	var cn := PackedInt64Array()
	for c4: int in p.tr_cp_n.size():
		if p.tr_cp_n[c4] > 0:
			hh.append(p.tr_cp_hh[c4])
			cw.append(p.tr_cp_w[c4])
			ch.append(p.tr_cp_h[c4])
			cn.append(p.tr_cp_n[c4])
	p.tr_cp_hh = hh
	p.tr_cp_w = cw
	p.tr_cp_h = ch
	p.tr_cp_n = cn


## A block's couples by wife point and by husband point, and its total, in key order (T2s-c5x)
static func _t22_c5_marg(p: RefCounted, cells: Array) -> Dictionary:
	var m: Dictionary = {}
	var tot: int = 0
	for c: int in cells:
		var kw: int = p.tr_cp_w[c] * 2
		var kh: int = p.tr_cp_h[c] * 2 + 1
		m[kw] = int(m.get(kw, 0)) + p.tr_cp_n[c]
		m[kh] = int(m.get(kh, 0)) + p.tr_cp_n[c]
		tot += p.tr_cp_n[c]
	var ks: Array = m.keys()
	ks.sort()
	var out: Dictionary = {"total": tot}
	for k in ks:
		if int(m[k]) > 0:
			out[k] = m[k]
	return out


## (C5 as AMENDED) one heaviest-first forest for the block (cells by descending mass, ties by the wife's then the husband's id); the
## off-forest cells taken lightest first (the same ties) while the block's live cells exceed its cap; each one's cycle with the forest's
## path moved as declared; a forest cell the move empties gives its place to the moved cell (the basis exchange), and an off-forest cell
## whose ends the forest no longer joins becomes a forest cell
static func _t22_c5_block(p: RefCounted, tl: Dictionary, cells: Array, cap: int, hb: int, unit_of: PackedInt32Array) -> void:
	var rows: Array = []
	for c: int in cells:
		rows.append([-p.tr_cp_n[c], p.tr_pt_id[p.tr_cp_w[c]], p.tr_pt_id[p.tr_cp_h[c]], c])
	rows.sort()
	var parent: Dictionary = {}
	var adj: Dictionary = {}
	var off: Array = []
	for r: Array in rows:
		var c2: int = int(r[3])
		var a: int = p.tr_cp_w[c2] * 2
		var b: int = p.tr_cp_h[c2] * 2 + 1
		var ra: int = _uf_find(parent, a)
		var rb: int = _uf_find(parent, b)
		if ra != rb:
			parent[ra] = rb
			_c5_link(adj, a, b, c2)
		else:
			off.append([p.tr_cp_n[c2], int(r[1]), int(r[2]), c2])
	off.sort()
	var live: int = cells.size()
	for o: Array in off:
		if live <= cap:
			break
		var c3: int = int(o[3])
		if p.tr_cp_n[c3] <= 0:
			continue
		var start: int = p.tr_cp_h[c3] * 2 + 1
		var goal: int = p.tr_cp_w[c3] * 2
		var path: Array = _c5_path(adj, start, goal)
		if path.is_empty():
			_c5_link(adj, goal, start, c3)
			continue
		var cyc: Array = [c3]
		cyc.append_array(path)
		var d1: int = 1 << 60
		var d2: int = 1 << 60
		for i: int in cyc.size():
			if i % 2 == 1:
				d1 = mini(d1, p.tr_cp_n[cyc[i]])
			else:
				d2 = mini(d2, p.tr_cp_n[cyc[i]])
		var u: float = KEYED.u(p.seed_v, "t22_c5", p.month, hb, p.tr_pt_id[p.tr_cp_w[c3]] * 100000000 + p.tr_pt_id[p.tr_cp_h[c3]])
		var dv: int = d1 if u * float(d1 + d2) < float(d2) else -d2
		var fsum: Dictionary = {}
		for i2: int in cyc.size():
			var sg: int = 1 if i2 % 2 == 0 else -1
			var c5: int = cyc[i2]
			p.tr_cp_n[c5] += sg * dv
			for f: int in _t22_c5_keys(p, c5, unit_of):
				fsum[f] = int(fsum.get(f, 0)) + sg
		for f2 in fsum:
			tl["c5_r"][int(f2)] += float(int(fsum[f2]) * dv)
			tl["c5_v"][int(f2)] += float(d1) * float(d2) * float(int(fsum[f2]) * int(fsum[f2]))
		tl["c5_moves"] = int(tl["c5_moves"]) + 1
		var lost_edge: bool = false
		for i3: int in range(1, cyc.size()):
			var e: int = cyc[i3]
			if p.tr_cp_n[e] <= 0:
				_c5_unlink(adj, p.tr_cp_w[e] * 2, p.tr_cp_h[e] * 2 + 1, e)
				lost_edge = true
				live -= 1
		if p.tr_cp_n[c3] <= 0:
			live -= 1
		elif lost_edge:
			_c5_link(adj, goal, start, c3)


static func _c5_link(adj: Dictionary, a: int, b: int, c: int) -> void:
	if not adj.has(a):
		adj[a] = {}
	if not adj.has(b):
		adj[b] = {}
	adj[a][c] = b
	adj[b][c] = a


static func _c5_unlink(adj: Dictionary, a: int, b: int, c: int) -> void:
	if adj.has(a):
		(adj[a] as Dictionary).erase(c)
	if adj.has(b):
		(adj[b] as Dictionary).erase(c)


## The forest's path of cells from node start to node goal (breadth first), empty when they are not joined
static func _c5_path(adj: Dictionary, start: int, goal: int) -> Array:
	var prev: Dictionary = {start: [-1, -1]}
	var queue: Array = [start]
	var qi: int = 0
	while qi < queue.size() and not prev.has(goal):
		var x: int = queue[qi]
		qi += 1
		var nb: Dictionary = adj.get(x, {})
		for c: int in nb:
			var y: int = int(nb[c])
			if not prev.has(y):
				prev[y] = [x, c]
				queue.append(y)
	if not prev.has(goal):
		return []
	var path: Array = []
	var at: int = goal
	while at != start:
		path.append(int(prev[at][1]))
		at = int(prev[at][0])
	path.reverse()
	return path


static func _uf_find(parent: Dictionary, x: int) -> int:
	var r: int = x
	while parent.has(r) and int(parent[r]) != r:
		r = int(parent[r])
	var y: int = x
	while parent.has(y) and int(parent[y]) != r:
		var nx: int = int(parent[y])
		parent[y] = r
		y = nx
	if not parent.has(r):
		parent[r] = r
	return r


## T2s-c5b's cells of a couple entry: (wife quartile x husband quartile) x the husband's 10-year band, and 144 + the band when both earn
static func _t22_c5_keys(p: RefCounted, c: int, unit_of: PackedInt32Array) -> Array:
	var wq: int = p.tr_pt_q[p.tr_cp_w[c]]
	var hq: int = p.tr_pt_q[p.tr_cp_h[c]]
	var b10: int = LC._b10(p.tr_key[unit_of[p.tr_cp_h[c]] * KEY_STRIDE + 1] * 5)
	var out: Array = [(wq * 4 + hq) * 9 + b10]
	if _at_work(p, p.tr_cp_w[c]) and _at_work(p, p.tr_cp_h[c]):
		out.append(144 + b10)
	return out

