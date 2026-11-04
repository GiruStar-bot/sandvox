extends RefCounted
## The households (ISS_HOUSEHOLD_REDESIGN.md, H1 §10.1): the start's households by prefecture, drawn whole (a type, then members of
## consistent ages), one weight per household raked at the household level, and the members as each other's family contacts. Behind
## people.households (default off: nothing is allocated, nothing enters to_dict or the digest). The household's kind indexes
## people.HOUSEHOLD: 0 single (one-person), 1 couple (couple only), 2 couple_children, 3 single_parent, 4 other (built as three-generation).
const SPEC := "res://data/modern/people/%s_households_2024.json"
const TYPES := ["one_person", "couple_only", "couple_children", "single_parent", "other"]
const MALE_AT_BIRTH := 0.512   # T: the sex ratio at birth 105 : 100
const INSTITUTION := 5          # life_course.INSTITUTION
const SIZE_ATTEMPTS := 16       # T: rebuilds of a household for the size draw
const PILOT := 400              # T: keyed pilot households per type for the size draw's lambda


static func load_spec(p: RefCounted) -> String:
	var d: Variant = p.CANON.load_json(SPEC % p.state.to_lower())
	if not (d is Dictionary):
		return "households: no spec for " + p.state
	p.hh_spec = d
	return ""


static func _v(p: RefCounted, k: String) -> Variant:
	return (p.hh_spec[k] as Dictionary)["value"]


static func _band_index(a: int, bands: Array) -> int:
	for b: int in bands.size():
		var s: String = String(bands[b])
		if s.ends_with("+"):
			if a >= int(s.trim_suffix("+")):
				return b
			continue
		var lo_hi: PackedStringArray = s.split("-")
		if a >= int(lo_hi[0]) and a <= int(lo_hi[1]):
			return b
	return -1


## One keyed draw of an age (and sex when both are open) over the cohort's counts times a shape: shape(a, s) >= 0
static func _draw_age(p: RefCounted, x: float, sexes: Array, lo: int, hi: int, shape: Callable) -> Vector2i:
	var tot: float = 0.0
	for s: int in sexes:
		for a: int in range(lo, hi + 1):
			tot += p.cohort[a * p.SEXES + s] * float(shape.call(a, s))
	var target: float = x * tot
	var acc: float = 0.0
	var last := Vector2i(lo, int(sexes[0]))
	for s2: int in sexes:
		for a2: int in range(lo, hi + 1):
			var wgt: float = p.cohort[a2 * p.SEXES + s2] * float(shape.call(a2, s2))
			if wgt <= 0.0:
				continue
			acc += wgt
			last = Vector2i(a2, s2)
			if target < acc:
				return last
	return last


static func _pick(shares: Dictionary, keys: Array, x: float) -> String:
	var acc: float = 0.0
	for k: String in keys:
		acc += float(shares[k])
		if x < acc:
			return k
	return String(keys[keys.size() - 1])


## The children of a mother aged ma, the r-th draw: their number given any, each one's age from the births by mother's age; a child not
## yet born is not counted, a child 18+ stays with the chance of not having left home at its age and sex (R62 表8; 35+ at 35-39's)
static func _children(p: RefCounted, code: int, k: int, ma: int, r: int = 0) -> Array:
	var u := func(tag: String, j: int) -> float: return p.KEYED.u(p.seed_v, tag, code, k, r * 8 + j)
	var nk: int = int(_pick(_v(p, "children_given_any"), ["1", "2", "3", "4"], u.call("hhkids", 0)))
	var bb: Dictionary = _v(p, "births_by_mother_age")
	var left: Dictionary = _v(p, "left_home_by_age")
	var out: Array = []
	for c: int in nk:
		var band: String = _pick(bb, ["15-19", "20-24", "25-29", "30-34", "35-39", "40-44", "45-49"], u.call("hhbirthage", c))
		var lo: int = int(band.split("-")[0])
		var b: int = lo + int(5.0 * u.call("hhbirthyear", c))
		var ca: int = ma - b
		if ca < 0:
			continue
		var cs: int = p.MALE if u.call("hhkidsex", c) < MALE_AT_BIRTH else p.FEMALE
		if ca >= 18:
			var lb: String = "18-19" if ca < 20 else ("20-24" if ca < 25 else ("25-29" if ca < 30 else ("30-34" if ca < 35 else "35+")))
			if u.call("hhkidhome", c) < float(left[lb][cs]):
				continue
		out.append(Vector2i(ca, cs))
	return out


## The households by householder age band (D, §10.1 amendment 5): the persons living alone in the band over R64's one-person share
## there; then per type P(band | type) as cumulative weights over the bands
static func _householder_ages(p: RefCounted, alone_shape: Callable) -> Array:
	var ta: Dictionary = _v(p, "type_by_householder_age")
	var bands: Array = ta["bands"]
	var hh := PackedFloat64Array()
	hh.resize(bands.size())
	for b: int in bands.size():
		var lohi: Vector2i = _band_range(p, String(bands[b]))
		var al: float = 0.0
		for a: int in range(lohi.x, lohi.y + 1):
			for s: int in 2:
				al += p.cohort[a * p.SEXES + s] * float(alone_shape.call(a, s))
		hh[b] = al / maxf(1e-9, float(ta["shares"][b][0]))
	var out: Array = []
	for t: int in TYPES.size():
		var w := PackedFloat64Array()
		w.resize(bands.size())
		for b2: int in bands.size():
			w[b2] = float(ta["shares"][b2][t]) * hh[b2]
		out.append([bands, w])
	return out


static func _band_range(p: RefCounted, band: String) -> Vector2i:
	if band.ends_with("+"):
		return Vector2i(int(band.trim_suffix("+")), p.AGES - 1)
	var lh: PackedStringArray = band.split("-")
	return Vector2i(int(lh[0]), int(lh[1]))


## A householder's age: its band by the type's weights, then the age within the band by the cohort of its sex
static func _householder_age(p: RefCounted, bw: Array, x_band: float, x_age: float, sex: int) -> int:
	var w: PackedFloat64Array = bw[1]
	var tot: float = 0.0
	for v: float in w:
		tot += v
	var acc: float = 0.0
	var b: int = w.size() - 1
	for i: int in w.size():
		acc += w[i]
		if x_band * tot < acc:
			b = i
			break
	var lohi: Vector2i = _band_range(p, String(bw[0][b]))
	return _draw_age(p, x_age, [sex], lohi.x, lohi.y, func(_a: int, _s: int) -> float: return 1.0).x


## One household of type t built around its householder (§10.1 amendment 5), every draw keyed by the prefecture c and k; returns [the
## type after the conversions (no child left: couple only or one-person), the members [age, sex, role, partner offset]]
static func _construct(p: RefCounted, c: int, k: int, t: int, cx: Dictionary) -> Array:
	var age_of: Array = cx["age_of"]
	var alone_shape: Callable = cx["alone_shape"]
	var gap: Dictionary = cx["gap"]
	var gp: Dictionary = cx["gp"]
	var hb: Dictionary = cx["hb"]
	var u := func(tag: String, j: int = 0) -> float: return p.KEYED.u(p.seed_v, tag, c, k, j)
	var gap_n := func(tag: String, j: int = 0) -> int: return int(round(float(gap["mean"]) + float(gap["sd"]) * p.KEYED.normal(p.seed_v, tag, c, k, j)))
	var ms: Array = []           # [age, sex, role, partner offset]
	if t == p.HK_SINGLE:
		var as0: Vector2i = _draw_age(p, u.call("hhalone"), [p.MALE, p.FEMALE], 15, p.AGES - 1, alone_shape)
		ms.append([as0.x, as0.y, p.R_HEAD, -1])
	elif t == p.HK_COUPLE:
		var man: int = _householder_age(p, age_of[p.HK_COUPLE], u.call("hhband"), u.call("hhage"), p.MALE)
		ms.append([man, p.MALE, p.R_HEAD, 1])
		ms.append([clampi(man - gap_n.call("hhgap"), 18, p.AGES - 1), p.FEMALE, p.R_PARTNER, 0])
	elif t == p.HK_COUPLE_CHILDREN or t == p.HK_SINGLE_PARENT:
		var ps: int = p.MALE if t == p.HK_COUPLE_CHILDREN else (p.FEMALE if u.call("hhspsex") < float(_v(p, "single_parent_mother")) else p.MALE)
		var ha: int = _householder_age(p, age_of[t], u.call("hhband"), u.call("hhage"), ps)
		var mother_age: int = clampi(ha - gap_n.call("hhgap"), 18, p.AGES - 1) if t == p.HK_COUPLE_CHILDREN else ha
		var kids: Array = []
		for r: int in int(hb["redraws"]):
			kids = _children(p, c, k, mother_age, r)
			if not kids.is_empty():
				break
		ms.append([ha, ps, p.R_HEAD, 1 if t == p.HK_COUPLE_CHILDREN else -1])
		if t == p.HK_COUPLE_CHILDREN:
			ms.append([mother_age, p.FEMALE, p.R_PARTNER, 0])
		for kd: Vector2i in kids:
			ms.append([kd.x, kd.y, p.R_CHILD, -1])
		if kids.is_empty():
			t = p.HK_COUPLE if t == p.HK_COUPLE_CHILDREN else p.HK_SINGLE
	else:
		var ha4: int = _householder_age(p, age_of[p.HK_OTHER], u.call("hhband"), u.call("hhage"), p.MALE)
		if ha4 < int(hb["old_from"]):
			var mother4: int = clampi(ha4 - gap_n.call("hhgap"), 18, p.AGES - 1)
			ms.append([ha4, p.MALE, p.R_HEAD, 1])
			ms.append([mother4, p.FEMALE, p.R_PARTNER, 0])
			for kd4: Vector2i in _children(p, c, k, mother4):
				ms.append([kd4.x, kd4.y, p.R_CHILD, -1])
			ms.append([clampi(mother4 + int(round(float(gp["offset_mean"]) + float(gp["offset_sd"]) * p.KEYED.normal(p.seed_v, "hhgrand", c, k, 0))), 50, p.AGES - 1), p.FEMALE if u.call("hhgrandsex") < float(gp["female"]) else p.MALE, p.R_PARENT, -1])
		else:
			var spouse: bool = u.call("hholdspouse") < float(hb["old_spouse"])
			var hs: int = p.MALE if spouse else (p.FEMALE if u.call("hhgrandsex") < float(gp["female"]) else p.MALE)
			ms.append([ha4, hs, p.R_HEAD, 1 if spouse else -1])
			if spouse:
				ms.append([clampi(ha4 - gap_n.call("hhgap"), 18, p.AGES - 1), p.FEMALE, p.R_PARTNER, 0])
			var cw: int = clampi(ha4 - int(round(float(hb["child_gap_mean"]) + float(hb["child_gap_sd"]) * p.KEYED.normal(p.seed_v, "hhchildgap", c, k, 0))), 18, p.AGES - 1)
			var ch: int = clampi(cw + gap_n.call("hhgap", 1), 18, p.AGES - 1)
			var son: bool = u.call("hhson") < float(hb["son"])
			var o: int = ms.size()
			ms.append([ch, p.MALE, p.R_CHILD if son else p.R_OTHER, o + 1])
			ms.append([cw, p.FEMALE, p.R_OTHER if son else p.R_CHILD, o])
			for kd5: Vector2i in _children(p, c, k, cw):
				ms.append([kd5.x, kd5.y, p.R_OTHER, -1])
	return [t, ms]


## Each prefecture's lambda for the size draw: keyed pilot households of each type (prefecture code -1) give each type's sizes; lambda
## by bisection so the prefecture's types' tilted mean sizes average to its 表I-5-1 mean. Why a pilot and not a size table: the sizes
## within each type by prefecture are NF (R64 gives the two margins only)
static func _size_lambdas(p: RefCounted, cx: Dictionary, by_pref: Dictionary, ts: Dictionary) -> Dictionary:
	var sizes: Array = []
	var smax: int = 1
	for t: int in TYPES.size():
		var sz := PackedInt32Array()
		for q: int in PILOT:
			var b: Array = _construct(p, -1, q * SIZE_ATTEMPTS, t, cx)
			sz.append((b[1] as Array).size())
			smax = maxi(smax, (b[1] as Array).size())
		sizes.append(sz)
	cx["size_max"] = smax
	var target: Dictionary = _v(p, "mean_size_by_prefecture")
	var out := {}
	for code: String in p.pref_codes:
		var sh: Array = by_pref[code] if by_pref.has(code) else TYPES.map(func(tn: String) -> float: return float(ts[tn]))
		var lo: float = -3.0
		var hi: float = 3.0
		for it: int in 40:
			var mid: float = 0.5 * (lo + hi)
			var m: float = 0.0
			for t2: int in TYPES.size():
				var w: float = 0.0
				var ws: float = 0.0
				for s2: int in (sizes[t2] as PackedInt32Array):
					var x: float = p.DM.exp(mid * float(s2 - smax))
					w += x
					ws += x * float(s2)
				m += float(sh[t2]) * ws / maxf(1e-12, w)
			if m < float(target.get(code, 2.21)):
				lo = mid
			else:
				hi = mid
		out[int(code)] = 0.5 * (lo + hi)
	return out


## The start: households per prefecture until each prefecture's person count is met (the last household may pass it by its members).
## The type from the prefecture's shares, the householder's age from P(type | householder age) x the households by householder age
## (§10.1 amendment 5), the members around the householder
static func build_start(p: RefCounted, prefectures: Dictionary, n_per: int) -> void:
	var ts: Dictionary = _v(p, "type_shares")
	var by_pref: Dictionary = _v(p, "type_by_prefecture")
	var alone: Dictionary = _v(p, "alone_share_by_band")
	var gap: Dictionary = _v(p, "partner_age_gap")
	var gp: Dictionary = _v(p, "grandparent")
	var hb: Dictionary = _v(p, "householder_build")
	var alone_shape := func(a: int, s: int) -> float:
		var b: int = _band_index(a, alone["bands"])
		return 0.0 if b < 0 else float(alone["men" if s == 0 else "women"][b])
	var flat := func(_a: int, _s: int) -> float: return 1.0
	var age_of: Array = _householder_ages(p, alone_shape)
	var inst: Dictionary = _v(p, "institution_start")
	var inst_shape := func(a: int, s: int) -> float: return _inst_share(inst, a, s)
	var inst_frac: float = 0.0
	var ctot: float = 0.0
	for a0: int in p.AGES:
		for s0: int in 2:
			inst_frac += p.cohort[a0 * p.SEXES + s0] * _inst_share(inst, a0, s0)
			ctot += p.cohort[a0 * p.SEXES + s0]
	inst_frac /= maxf(1e-9, ctot)
	var cx := {"age_of": age_of, "alone_shape": alone_shape, "gap": gap, "gp": gp, "hb": hb}
	var lambdas: Dictionary = _size_lambdas(p, cx, by_pref, ts)
	var members: Array = []      # per person: [code, household, age, sex, role (life_course.ROLES), its partner's offset in the household or -1]
	var types: Array = []        # per household: [code, type]
	for code: String in p.pref_codes:
		var c: int = int(code)
		var shares: Dictionary = ts
		if by_pref.has(code):
			shares = {}
			for t0: int in TYPES.size():
				shares[TYPES[t0]] = float(by_pref[code][t0])
		var count: int = 0
		var k: int = 0
		# the institution residents first (§10.3 A): one-person type-5 records, their number the prefecture's share of the cohort in one
		var n_inst: int = int(round(float(n_per) * inst_frac))
		for q: int in n_inst:
			var ai: Vector2i = _draw_age(p, p.KEYED.u(p.seed_v, "hhinst", c, q, 0), [0, 1], 75, p.AGES - 1, inst_shape)
			types.append([c, INSTITUTION])
			members.append([c, types.size() - 1, ai.x, ai.y, p.R_HEAD, -1])
		count = n_inst
		var lam: float = float(lambdas[c])
		var sref: float = float(cx["size_max"]) if lam >= 0.0 else 1.0
		while count < n_per:
			var t: int = TYPES.find(_pick(shares, TYPES, p.KEYED.u(p.seed_v, "hhtype", c, k, 0)))
			var built: Array = []
			# the size draw (§10.4 ruling 4): a household is kept with probability exp(lambda x (size - sref)), else rebuilt, so the
			# drawn sizes meet the prefecture's mean before any weight; the last attempt is kept
			for att: int in SIZE_ATTEMPTS:
				built = _construct(p, c, k * SIZE_ATTEMPTS + att, t, cx)
				var sz: float = float((built[1] as Array).size())
				if att == SIZE_ATTEMPTS - 1 or p.KEYED.u(p.seed_v, "hhsize", c, k * SIZE_ATTEMPTS + att, 0) < p.DM.exp(lam * (sz - sref)):
					break
			t = int(built[0])
			var ms: Array = built[1]
			types.append([c, t])
			for m: Array in ms:
				members.append([c, types.size() - 1, int(m[0]), int(m[1]), int(m[2]), int(m[3])])
			count += ms.size()
			k += 1
	p.place_persons(members.size())
	p.hh_n = types.size()
	p.hh_type.resize(p.hh_n)
	p.hh_pref.resize(p.hh_n)
	p.hh_weight.resize(p.hh_n)
	p.hh_id.resize(p.n)
	for arr in [p.hh_role, p.partner, p.ever_married, p.ever_left, p.union_month, p.last_birth, p.births_n]:
		arr.resize(p.n)
		arr.fill(0)
	p.partner.fill(-1)
	var per_pref: Dictionary = {}
	for h: int in p.hh_n:
		p.hh_type[h] = int(types[h][1])
		p.hh_pref[h] = int(types[h][0])
	for m2: Array in members:
		per_pref[int(m2[0])] = int(per_pref.get(int(m2[0]), 0)) + 1
	var k_in := {}
	for i: int in p.n:
		var code2: int = int(members[i][0])
		var kk: int = int(k_in.get(code2, 0))
		k_in[code2] = kk + 1
		p.place_person(i, code2, kk, int(members[i][2]), int(members[i][3]))
		p.hh_id[i] = int(members[i][1])
		p.hh_role[i] = int(members[i][4])
	for h2: int in p.hh_n:
		p.hh_weight[h2] = float(p.pref_pop[p.hh_pref[h2]]) / float(per_pref[p.hh_pref[h2]])
	refresh_members(p)
	for h4: int in p.hh_n:
		var ms4: PackedInt32Array = p.hh_members[h4]
		for x: int in ms4.size():
			var off: int = int(members[ms4[x]][5])
			if off >= 0:
				p.partner[ms4[x]] = ms4[off]
	for i2: int in p.n:
		p.weight[i2] = p.hh_weight[p.hh_id[i2]]
		p.hh_kind[i2] = p.HK_SINGLE if p.hh_type[p.hh_id[i2]] == INSTITUTION else p.hh_type[p.hh_id[i2]]
		p.hh_size[i2] = float((p.hh_members[p.hh_id[i2]] as PackedInt32Array).size())


## The members of each household, rebuilt from the persons' household ids
static func refresh_members(p: RefCounted) -> void:
	p.hh_members = []
	p.hh_members.resize(p.hh_n)
	for h: int in p.hh_n:
		p.hh_members[h] = PackedInt32Array()
	for i: int in p.n:
		var arr: PackedInt32Array = p.hh_members[p.hh_id[i]]
		arr.append(i)
		p.hh_members[p.hh_id[i]] = arr


static func _inst_share(inst: Dictionary, a: int, s: int) -> float:
	for b: int in (inst["bands"] as Array).size():
		if a >= int(inst["bands"][b][0]) and a <= int(inst["bands"][b][1]):
			return float(inst["men" if s == 0 else "women"][b])
	return 0.0


## The rake at the household level (§10.1, §10.3 A/D): every member keeps its household's weight. Why not person weights: members of
## one household with different weights would make its budget and its votes inconsistent (§3). Per round, in order (amendment 6): at
## the start each prefecture's types and the twelve alone cells of 表V-1-3, always the age-sex cells (the geometric mean of the members'
## factors; at the start in nine bands, amendment 7), at the start the institution cells, always each prefecture's mean size (a tilt by
## size, amendment 7), then the prefecture totals. 30 rounds
## at the start, 8 a month. Why not the types, alone and institution cells every month: the life course moves them, and they are its
## checks at year 10 (HB1, HB1b, HB10); the mean size is held so the rake cannot move it (ruling D)
static func rake(p: RefCounted, cell_target: PackedFloat64Array, scale: float, start: bool = false) -> void:
	var by_pref: Dictionary = _v(p, "type_by_prefecture")
	var pop_total: float = 0.0
	for code0: int in p.pref_pop:
		pop_total += float(p.pref_pop[code0]) * scale
	var cells: PackedFloat64Array = cell_target
	var alone_t: Array = []      # [band lo, hi, sex, target weight]
	var inst_t: Array = []
	if start:
		var ctot: float = 0.0
		for k: int in p.cohort.size():
			ctot += p.cohort[k]
		var al: Dictionary = _v(p, "alone_share_by_band")
		for b: int in (al["bands"] as Array).size():
			var band: String = String(al["bands"][b])
			if band == "45-54" or band == "55-64":
				continue
			var lh: Vector2i = _band_range(p, band)
			for s: int in 2:
				var cc: float = 0.0
				for a: int in range(lh.x, lh.y + 1):
					cc += p.cohort[a * p.SEXES + s]
				alone_t.append([lh.x, lh.y, s, float(al["men" if s == 0 else "women"][b]) * cc / ctot * pop_total])
		var inst: Dictionary = _v(p, "institution_start")
		for b2: int in (inst["bands"] as Array).size():
			for s2: int in 2:
				var cc2: float = 0.0
				for a2: int in range(int(inst["bands"][b2][0]), mini(int(inst["bands"][b2][1]), p.AGES - 1) + 1):
					cc2 += p.cohort[a2 * p.SEXES + s2]
				var sh: float = float(inst["men" if s2 == 0 else "women"][b2])
				inst_t.append([int(inst["bands"][b2][0]), int(inst["bands"][b2][1]), s2, sh * cc2 / ctot * pop_total])
		cells = PackedFloat64Array()
		cells.resize(FINE.size() * p.SEXES)
		for a3: int in p.AGES:
			for s3: int in 2:
				cells[_fine(a3) * p.SEXES + s3] += p.cohort[a3 * p.SEXES + s3] / ctot
	for r: int in (30 if start else 8):
		if start:
			var tw: Dictionary = {}
			for h0: int in p.hh_n:
				if _private(p, h0):
					var key: int = p.hh_pref[h0]
					if not tw.has(key):
						tw[key] = PackedFloat64Array([0, 0, 0, 0, 0, 0])
					var arr: PackedFloat64Array = tw[key]
					arr[p.hh_type[h0]] += p.hh_weight[h0]
					arr[5] += p.hh_weight[h0]
					tw[key] = arr
			for h1: int in p.hh_n:
				if not _private(p, h1):
					continue
				var a1: PackedFloat64Array = tw.get(p.hh_pref[h1], PackedFloat64Array())
				var code: String = "%02d" % p.hh_pref[h1]
				if a1.size() > 0 and a1[p.hh_type[h1]] > 0.0 and by_pref.has(code):
					p.hh_weight[h1] *= float(by_pref[code][p.hh_type[h1]]) * a1[5] / a1[p.hh_type[h1]]
		for t: Array in alone_t:
			_scale_cell(p, t, func(h: int) -> bool: return _private(p, h) and p.hh_type[h] == p.HK_SINGLE)
		var csum := PackedFloat64Array()
		csum.resize(cells.size())
		var all: float = 0.0
		for h4: int in p.hh_n:
			for i: int in (p.hh_members[h4] as PackedInt32Array):
				csum[_cell(p, i, start)] += p.hh_weight[h4]
				all += p.hh_weight[h4]
		var logf := PackedFloat64Array()
		logf.resize(cells.size())
		for c: int in cells.size():
			logf[c] = p.DM.log(cells[c] * all / csum[c]) if csum[c] > 0.0 and cells[c] > 0.0 else 0.0
		for h: int in p.hh_n:
			var ms: PackedInt32Array = p.hh_members[h]
			if ms.is_empty():
				continue
			var acc: float = 0.0
			for i2: int in ms:
				acc += logf[_cell(p, i2, start)]
			p.hh_weight[h] *= p.DM.exp(acc / float(ms.size()))
		for t2: Array in inst_t:
			_scale_cell(p, t2, func(h: int) -> bool: return p.hh_type[h] == INSTITUTION)
		_tilt_sizes(p)
		var now: Dictionary = {}
		for h5: int in p.hh_n:
			now[p.hh_pref[h5]] = float(now.get(p.hh_pref[h5], 0.0)) + p.hh_weight[h5] * float((p.hh_members[h5] as PackedInt32Array).size())
		for h6: int in p.hh_n:
			var w0: float = float(now.get(p.hh_pref[h6], 0.0))
			if w0 > 0.0 and p.pref_pop.has(p.hh_pref[h6]):
				p.hh_weight[h6] *= float(p.pref_pop[p.hh_pref[h6]]) * scale / w0
	for i3: int in p.n:
		p.weight[i3] = p.hh_weight[p.hh_id[i3]]


const FINE := [0, 15, 25, 35, 45, 55, 65, 75, 85]


static func _fine(a: int) -> int:
	var b: int = 0
	for k: int in FINE.size():
		if a >= FINE[k]:
			b = k
	return b


static func _cell(p: RefCounted, i: int, fine: bool) -> int:
	return (_fine(p.age[i]) if fine else p.band_of(p.age[i])) * p.SEXES + p.sex[i]


## Each prefecture's private households tilted by size, weight x exp(lambda x size), lambda by bisection so the weighted mean size is
## 表I-5-1's (amendment 7). Why not a scaling of the count: a uniform scaling leaves the mean size where it was
static func _tilt_sizes(p: RefCounted) -> void:
	var sizes: Dictionary = _v(p, "mean_size_by_prefecture")
	var by: Dictionary = {}
	for h: int in p.hh_n:
		if _private(p, h):
			if not by.has(p.hh_pref[h]):
				by[p.hh_pref[h]] = []
			by[p.hh_pref[h]].append(h)
	for code: int in by:
		var target: float = float(sizes.get("%02d" % code, 0.0))
		if target <= 0.0:
			continue
		var hs: Array = by[code]
		var lo: float = -3.0
		var hi: float = 3.0
		for it: int in 40:
			var mid: float = 0.5 * (lo + hi)
			var w: float = 0.0
			var ws: float = 0.0
			for h2: int in hs:
				var sz: float = float((p.hh_members[h2] as PackedInt32Array).size())
				var x: float = p.hh_weight[h2] * p.DM.exp(mid * (sz - target))
				w += x
				ws += x * sz
			if ws / maxf(1e-12, w) < target:
				lo = mid
			else:
				hi = mid
		var lam: float = 0.5 * (lo + hi)
		for h3: int in hs:
			p.hh_weight[h3] *= p.DM.exp(lam * (float((p.hh_members[h3] as PackedInt32Array).size()) - target))


## A member's weight set to its household's (a newborn; one weight per household)
static func set_member_weight(p: RefCounted, i: int) -> void:
	p.weight[i] = p.hh_weight[p.hh_id[i]]


## A household the life course opens (a new couple, a leaver, a divorce, a mover, an institution) takes the weight w it is given: the
## rake module writes every household weight (the one-writer rule, V099 item 6)
static func add_household_weight(p: RefCounted, w: float) -> void:
	p.hh_weight.append(w)


static func _private(p: RefCounted, h: int) -> bool:
	return p.hh_type[h] < TYPES.size() and not (p.hh_members[h] as PackedInt32Array).is_empty()


## One-person records of one person cell (band lo..hi, sex) scaled to the cell's target weight
## The band of R62's never-married table an age falls in: from each listed age to the next one's, the last (the at-50 share) to 54
static func _nm_band(a: int, lo: Array) -> int:
	for b: int in range(lo.size() - 1, -1, -1):
		if a >= int(lo[b]):
			return b if (b < lo.size() - 1 or a <= int(lo[b]) + 9) else -1
	return -1


static func _scale_cell(p: RefCounted, t: Array, which: Callable) -> void:
	var w: float = 0.0
	var hs: Array = []
	for h: int in p.hh_n:
		var ms: PackedInt32Array = p.hh_members[h]
		if ms.size() == 1 and which.call(h):
			var i: int = ms[0]
			if p.sex[i] == int(t[2]) and p.age[i] >= int(t[0]) and p.age[i] <= int(t[1]):
				w += p.hh_weight[h]
				hs.append(h)
	if w <= 0.0:
		return
	for h2: int in hs:
		p.hh_weight[h2] *= float(t[3]) / w


## The members of a household as each other's family contacts, before the prefecture's pool fills the other kinds
static func link_family(p: RefCounted) -> void:
	for h: int in p.hh_n:
		var ms: PackedInt32Array = p.hh_members[h]
		for a: int in ms.size():
			for b: int in range(a + 1, ms.size()):
				var i: int = ms[a]
				var j: int = ms[b]
				if p.REL.has_contact(p, i, j):
					continue
				if p.REL.add(p, i, j, p.REL.K_FAMILY):
					if not p.REL.add(p, j, i, p.REL.K_FAMILY):
						p.REL.unlink(p, i, j)


## Kish's effective sample size of the private households and of the persons: (sum w)^2 / sum w^2 (§10.4 ruling 4: every SE uses it)
static func kish(p: RefCounted) -> Dictionary:
	var sw: float = 0.0
	var sw2: float = 0.0
	var nh: int = 0
	for h: int in p.hh_n:
		if _private(p, h):
			sw += p.hh_weight[h]
			sw2 += p.hh_weight[h] * p.hh_weight[h]
			nh += 1
	var pw: float = 0.0
	var pw2: float = 0.0
	for i: int in p.n:
		pw += p.weight[i]
		pw2 += p.weight[i] * p.weight[i]
	# within each prefecture: the national figure is dominated by the uniform sample per prefecture (until H6's proportional one)
	var by := {}
	for h2: int in p.hh_n:
		if _private(p, h2):
			var a: PackedFloat64Array = by.get(p.hh_pref[h2], PackedFloat64Array([0.0, 0.0, 0.0]))
			a[0] += p.hh_weight[h2]
			a[1] += p.hh_weight[h2] * p.hh_weight[h2]
			a[2] += 1.0
			by[p.hh_pref[h2]] = a
	var eff_in: float = 0.0
	for code: int in by:
		var b: PackedFloat64Array = by[code]
		eff_in += b[0] * b[0] / maxf(1e-12, b[1])
	return {"households": nh, "households_eff": sw * sw / maxf(1e-12, sw2), "households_eff_within": eff_in, "persons": p.n, "persons_eff": pw * pw / maxf(1e-12, pw2)}


## The weighted shares of the household types and the mean size (H1s-a, H1s-b)
static func type_shares(p: RefCounted) -> Dictionary:
	var w := PackedFloat64Array()
	w.resize(TYPES.size())
	var tot: float = 0.0
	var persons: float = 0.0
	for h: int in p.hh_n:
		var sz: int = (p.hh_members[h] as PackedInt32Array).size()
		if sz == 0 or p.hh_type[h] >= TYPES.size():
			continue
		w[p.hh_type[h]] += p.hh_weight[h]
		tot += p.hh_weight[h]
		persons += p.hh_weight[h] * float(sz)
	var out := {}
	for t: int in TYPES.size():
		out[TYPES[t]] = w[t] / maxf(1e-9, tot)
	out["mean_size"] = persons / maxf(1e-9, tot)
	return out
