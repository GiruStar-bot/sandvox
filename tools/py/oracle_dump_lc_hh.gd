extends SceneTree
## The oracle's side of the life course and households port (docs/team/modern/py/LC_HH_PORT_PLAN.md §2, §5). It reads the persons'
## state and writes files only. Two people objects run side by side: one by people.create / people.step, one by this file's copies of
## _create_households, step and _year with the cuts of §2. Each cut writes its whole state, or its per-field SHA-256 lines.
##   LCHH_OUT=outputs/lchh/<tag> LCHH_SEED=1 LCHH_N=60 LCHH_MONTHS=36 [LCHH_FULL=1,6,12,13,36] \
##     godot --headless --path . --script res://tools/py/oracle_dump_lc_hh.gd
## Writes:
## - registry.json, spec.json, grid.json (L0-k, L0-sort);
## - start/<cut>_{pre,post}/ and .sha.txt;
## - mNN_pre/ (whole) with mNN_pre.sha.txt; mNN_post.sha.txt, with the whole mNN_post/ at the LCHH_FULL months;
## - mNN_newborn.json (the births' replayed fields), mNN_y.json (the Y calls), mNN_sort.json (the quartile cuts' permutations);
## - hook.json (L-h: the hooked object's digests against the real one's).
## Why copies of people.gd's functions and not hooks in it: the GDScript is frozen (D475), and L-h shows the copies equal the originals.
const PEOPLE = preload("res://sim/modern/people/people.gd")
const MS = preload("res://sim/modern/modern_status.gd")
const CANON = preload("res://sim/modern/canon.gd")
const KEYED = preload("res://sim/earth_core/keyed.gd")
const LC = preload("res://sim/modern/people/life_course.gd")
const HH = preload("res://sim/modern/people/households.gd")
const ENV := {"inflation_month": 0.02 / 12.0, "food_price_yoy": 0.0, "unemployment_rate": 0.025, "levers": []}
const EXTRAS := ["n", "month", "seed_v", "base_year", "hh_n", "hh_members", "next_k", "life_log", "lc_births", "lc_dying", "lc_t22b",
	"lc_c_band", "groups", "pref_pop", "pref_codes"]
## The newborn's fields the life course writes, or that are written after its birth (LC_HH_PORT_PLAN §2): not replayed
const LC_WRITES := ["pid", "pref", "k_in_pref", "age", "sex", "hh_kind", "hh_size", "health", "weight", "contact_idx", "contact_kind",
	"contact_last", "contact_trust", "member_of"]

var _files: int = 0
var out: String = ""
var ylog: Array = []


func _init() -> void:
	out = OS.get_environment("LCHH_OUT")
	var seed: int = int(OS.get_environment("LCHH_SEED")) if OS.get_environment("LCHH_SEED") != "" else 1
	var n_per: int = int(OS.get_environment("LCHH_N")) if OS.get_environment("LCHH_N") != "" else 60
	var months: int = int(OS.get_environment("LCHH_MONTHS")) if OS.get_environment("LCHH_MONTHS") != "" else 36
	var full: Array = [1, 6, 12, 13, 36]
	if OS.get_environment("LCHH_FULL") != "":
		full = []
		for s: String in OS.get_environment("LCHH_FULL").split(",", false):
			full.append(int(s))
	DirAccess.make_dir_recursive_absolute(out + "/start")
	var st = MS.new()
	st.load(2024, ["JPN"])
	var prefs: Dictionary = CANON.load_json("res://data/modern/polity/jpn_prefectures.json")["prefectures"]
	var pr = PEOPLE.new()
	pr.households = true
	pr.create("JPN", seed, st.cohort["JPN"], st.qx["JPN"], prefs, n_per, 2024)
	var p = PEOPLE.new()
	p.households = true
	_create_hooked(p, "JPN", seed, st.cohort["JPN"], st.qx["JPN"], prefs, n_per, 2024)
	_write_registry(p)
	_write_grid(seed)
	var hook: Array = [[0, pr.digest(), p.digest(), _lines_digest(pr), _lines_digest(p)]]
	for m: int in range(1, months + 1):
		pr.step(ENV)
		ylog = []
		_step_hooked(p, ENV, m, m in full)
		hook.append([m, pr.digest(), p.digest(), _lines_digest(pr), _lines_digest(p)])
		print("LCHH month %d n %d hh %d equal %s" % [m, p.n, p.hh_n, str(hook[m][1] == hook[m][2] and hook[m][3] == hook[m][4])])
	_store(out + "/hook.json", JSON.stringify(hook))
	_cases(p)
	quit(0)


## The K cases of LC_HH_PORT_PLAN §7, after month 36 on the hooked object: the read-only ones first (K7, K5, K4), then those that
## change the state (K1, K2, K3, K6), each with its whole pre and post state. Why after month 36: months 0-36 and L-h stay the dump's
func _cases(p: RefCounted) -> void:
	var K: String = out + "/k"
	DirAccess.make_dir_recursive_absolute(K)
	var ks: Dictionary = HH.kish(p)
	var ts: Dictionary = HH.type_shares(p)
	_store(K + "/k7.json", JSON.stringify({"kish": _bits_tree(ks), "type_shares": _bits_tree(ts)}))
	var al: Array = (p.hh_spec["alone_share_by_band"] as Dictionary)["value"]["bands"]
	var zero_even := func(a: int, _s: int) -> float: return 0.0 if a % 2 == 0 else 1.0
	var da: Array = []
	for x: float in [0.5, 1.0]:
		var v: Vector2i = HH._draw_age(p, x, [0, 1], 15, p.AGES - 1, zero_even)
		da.append([v.x, v.y])
	var hd: Array = []
	for a: int in 111:
		for s: int in 2:
			hd.append(_bits(LC.h_death(p, a, s, 4, 0)))
	_store(K + "/k5.json", JSON.stringify({"band_index": [HH._band_index(10, al), HH._band_index(90, al)], "draw_age": da,
		"pick": HH._pick(HH._v(p, "type_shares"), HH.TYPES, 1.0), "h_death": hd}))
	var fr := FileAccess.open("res://tools/py/lchh_k4_sort.json", FileAccess.READ)
	var arrs: Array = (JSON.parse_string(fr.get_as_text()) as Dictionary)["arrays"]
	fr.close()
	var perms: Array = []
	for e: Dictionary in arrs:
		var rows: Array = []
		var kk: Array = e["keys"]
		for i: int in kk.size():
			rows.append([float(kk[i]), 0.0, i])
		rows.sort_custom(func(x: Array, y: Array) -> bool: return float(x[0]) < float(y[0]))
		var perm: Array = []
		for r: Array in rows:
			perm.append(int(r[2]))
		perms.append(perm)
	_store(K + "/k4.json", JSON.stringify(perms))
	# K1: move_household as people.move_to calls it (people.gd:364), one person of each kind, in distinct households
	var found := {"a": -1, "b": -1, "c": -1, "d": -1}
	var used := {}
	for i: int in p.n:
		var h: int = p.hh_id[i]
		if used.has(h):
			continue
		var kind: String = ""
		if p.hh_type[h] == LC.INSTITUTION:
			kind = "d"
		elif p.hh_role[i] <= p.R_PARTNER:
			kind = "a" if (p.hh_members[h] as PackedInt32Array).size() >= 2 and _in_group(p, h) else ""
		elif p.partner[i] >= 0 and p.hh_id[p.partner[i]] == h:
			kind = "b"
		else:
			kind = "c"
		if kind != "" and int(found[kind]) < 0:
			found[kind] = i
			used[h] = true
	_snap(p, K + "/k1_pre", true)
	var mv: Array = []
	for kind2: String in ["a", "b", "c", "d"]:
		var i2: int = int(found[kind2])
		if i2 < 0:
			mv.append([kind2, "-1", -1, []])
			continue
		var dest: int = -1
		for code: String in p.pref_codes:
			if int(code) != p.pref[i2]:
				dest = int(code)
				break
		var moved: Array = LC.move_household(p, i2, dest, "job")
		var mp: Array = []
		for j: int in moved:
			mp.append(str(p.pid[j]))
		mv.append([kind2, str(p.pid[i2]), dest, mp])
	_snap(p, K + "/k1_post", true)
	_store(K + "/k1.json", JSON.stringify(mv))
	# K2: dies as people._year calls it (people.gd:1443), on every person, then again on those who died, then the whole cut L
	_snap(p, K + "/k2_pre", true)
	var dc: Array = []
	var died: Array = []
	for i3: int in p.n:
		var d3: bool = LC.dies(p, i3)
		dc.append([str(p.pid[i3]), d3])
		if d3:
			died.append(i3)
	for i4: int in died:
		dc.append([str(p.pid[i4]), LC.dies(p, i4)])
	_store(K + "/k2.json", JSON.stringify(dc))
	var n_pre: int = p.n
	var pre_pids := {}
	for i5: int in p.n:
		pre_pids[p.pid[i5]] = true
	LC.grade_birthday(p)
	LC.month(p, {})
	p.reweight(PackedFloat64Array())
	_write_sort(p, K + "/k2_sort.json")
	LC.quartile_cuts(p)
	_snap(p, K + "/k2_post", true)
	_write_newborns(p, n_pre, pre_pids, K + "/k2_newborn.json")
	# K3: band 0 emptied, then the cuts
	_snap(p, K + "/k3_pre", true)
	for i6: int in p.n:
		if p.age[i6] < 10:
			p.age[i6] = 10
	LC.quartile_cuts(p)
	_snap(p, K + "/k3_post", true)
	# K6: _scale_cell with no record, link_family on a full state, _tilt_sizes with prefecture 13's target 0
	_snap(p, K + "/k6_pre", true)
	_k6_prepare(p)
	HH._scale_cell(p, [0, 0, 0, 1.0], func(h: int) -> bool: return HH._private(p, h) and p.hh_type[h] == p.HK_SINGLE)
	HH.link_family(p)
	var ms: Dictionary = (p.hh_spec["mean_size_by_prefecture"] as Dictionary)["value"]
	var old: Variant = ms["13"]
	ms["13"] = 0.0
	HH._tilt_sizes(p)
	ms["13"] = old
	_snap(p, K + "/k6_post", true)
	print("LCHH cases written")


func _in_group(p: RefCounted, h: int) -> bool:
	for j: int in (p.hh_members[h] as PackedInt32Array):
		for m: int in p.GRP.M:
			if p.member_of[j * p.GRP.M + m] >= 0:
				return true
	return false


## K6's preparation (LC_HH_PORT_PLAN §7, AMENDED): in the first private household of 2+, its first member's links dropped and its second
## member's contacts filled with friends, so link_family's reverse add fails
func _k6_prepare(p: RefCounted) -> void:
	for h: int in p.hh_n:
		var ms: PackedInt32Array = p.hh_members[h]
		if ms.size() < 2 or not HH._private(p, h):
			continue
		var i: int = ms[0]
		var j: int = ms[1]
		p.REL.drop_all(p, i)
		var x: int = 0
		while p.contact_count(j) < p.REL.C and x < p.n:
			if x != j and not p.REL.has_contact(p, j, x):
				p.REL.add(p, j, x, p.REL.K_FRIEND)
			x += 1
		return


func _bits_tree(d: Dictionary) -> Dictionary:
	var o := {}
	for k in d:
		o[k] = _bits(d[k]) if typeof(d[k]) == TYPE_FLOAT else str(d[k])
	return o


## people.create's head and _create_households (people.gd:447-461, 580-600) with the four start cuts of LC_HH_PORT_PLAN §2
func _create_hooked(p: RefCounted, key: String, seed: int, cohort_: PackedFloat64Array, qx_: PackedFloat64Array, prefectures: Dictionary, n_per: int, year: int) -> void:
	p.load_spec(key)
	p.seed_v = seed
	p.base_year = year
	p.cohort = cohort_.duplicate()
	p.qx = qx_.duplicate()
	if n_per <= 0:
		n_per = int(p.spec["n_per_prefecture"]["value"])
	p.pref_codes = prefectures.keys()
	p.pref_codes.sort()
	HH.load_spec(p)
	for code: String in p.pref_codes:
		p.pref_pop[int(code)] = float(prefectures[code]["pop_thousand"]) * 1000.0
	_store(out + "/start/n_per.json", JSON.stringify({"n_per": n_per}))
	_snap(p, out + "/start/hh_pre", true)
	HH.build_start(p, prefectures, n_per)
	_snap(p, out + "/start/hh_post", true)
	for i: int in p.n:
		p._draw_attributes(i)
		p._draw_traits(i)
		p._draw_dream(i)
	_snap(p, out + "/start/lc_pre", true)
	LC.start(p)
	_snap(p, out + "/start/lc_post", true)
	p._ranks()
	for j: int in p.n:
		p._compose_drives(j)
		p._init_states(j)
	_snap(p, out + "/start/link_pre", true)
	HH.link_family(p)
	_snap(p, out + "/start/link_post", true)
	p.REL.build(p)
	p.GRP.seed_groups(p)
	_snap(p, out + "/start/rake_pre", true)
	p.reweight(PackedFloat64Array(), true)
	LC.solve_c(p)
	_snap(p, out + "/start/rake_post", true)


## people.step (people.gd:1240-1307) with the cut before LC.grade_birthday and after LC.quartile_cuts, and _year's LC calls logged
func _step_hooked(p: RefCounted, env: Dictionary, m: int, full_post: bool) -> void:
	var infl: float = float(env.get("inflation_month", 0.02 / 12.0))
	p.price_index *= 1.0 + infl
	p.wage_index = float(env.get("wage_index", p.wage_index))
	p._pension_month()
	var ur: float = float(env.get("unemployment_rate", float(p.spec["unemployment_rate_start"]["value"])))
	var f: float = float(p.spec["job_finding_rate_month"]["value"])
	var yoy_true: float = float(env.get("food_price_yoy", 0.0))
	var levers: Array = env.get("levers", [])
	var counts: Dictionary = {}
	var dec_counts: Dictionary = {}
	var ref_counts: Dictionary = {}
	for i: int in p.n:
		var ch: Dictionary = p.ACT.choose(p, i, p.month)
		var act: int = int(ch["action"])
		p.ACT.apply(p, i, act, p.month)
		if act == p.ACT.A_FOUND:
			p.GRP.found_movement(p, i, counts)
		p.last_action[i] = act
		p._count_decision(dec_counts, act, int(ch["top_drive"]), String(ch["modulated_by"]), i)
		for r: Array in ch["refused"]:
			var rk: String = "%d|%s" % [int(r[0]), String(r[1])]
			ref_counts[rk] = int(ref_counts.get(rk, 0)) + 1
		if p.trace_pids.has(p.pid[i]):
			p.trace.append([p.month, p.pid[i], "decision", p.ACT.ACTIONS[act], float(ch["u"]), "top drive %s%s, %d options" % [p.DRIVES[int(ch["top_drive"])] if int(ch["top_drive"]) >= 0 else "none", (" (" + String(ch["modulated_by"]) + ")") if String(ch["modulated_by"]) != "" else "", int(ch["options"])]])
	p.REL.interact(p, counts)
	p.REL.learn(p, {"food_price_yoy": yoy_true, "unemployment_rate": ur}, counts)
	p.GRP.step(p, counts)
	var s: float = p._mean_finding(f) * ur / maxf(1e-6, 1.0 - ur)
	var pools: Dictionary = {}
	for i0: int in p.n:
		if not pools.has(p.pref[i0]):
			pools[p.pref[i0]] = []
		pools[p.pref[i0]].append(i0)
	for i: int in p.n:
		if p.month % 12 == int(p.pid[i] % 12):
			_year_hooked(p, i, counts)
			if p.contact_renewal:
				p.REL.replenish(p, i, pools[p.pref[i]])
		p.LAB.person_month(p, i, s, f, counts)
		p.apply_month_values(i, p.month_values(p.SV.new().of_person(p, i), infl, levers), counts)
	var tag: String = "%s/m%02d" % [out, m]
	_snap(p, tag + "_pre", true)
	_store(tag + "_y.json", JSON.stringify(ylog))
	var n_pre: int = p.n
	var pre_pids := {}
	for i1: int in p.n:
		pre_pids[p.pid[i1]] = true
	LC.grade_birthday(p)
	LC.month(p, counts)
	p.reweight(env.get("cohort", PackedFloat64Array()))
	_write_sort(p, tag + "_sort.json")
	LC.quartile_cuts(p)
	_snap(p, tag + "_post", full_post)
	_write_newborns(p, n_pre, pre_pids, tag + "_newborn.json")
	p.GRP.refresh_weights(p)
	p._ranks()
	for key: String in dec_counts:
		p.decisions.append(dec_counts[key])
	for rk: String in ref_counts:
		var parts: PackedStringArray = rk.split("|")
		p.refusals.append({"month": p.month, "action": p.ACT.ACTIONS[int(parts[0])], "why": parts[1], "count": int(ref_counts[rk])})
	for kind: String in counts:
		var c: Dictionary = counts[kind]
		p.events.append({"month": p.month, "kind": kind, "count": int(c["n"]), "weight": float(c["w"]), "mean_move": float(c["move"]) / maxf(1.0, float(c["n"])), "why": String(c["why"])})
	p.month += 1


## people._year (people.gd:1440-1463), households on, with each LC call's inputs and outputs appended to the Y log
func _year_hooked(p: RefCounted, i: int, counts: Dictionary) -> void:
	var a: int = p.age[i]
	var e: float = LC.equivalized(p, i)
	var qk: int = LC.quartile(p, i)
	var q: float = LC.h_death(p, a, p.sex[i], p.health[i], qk)
	var died: bool = LC.dies(p, i)
	ylog.append({"call": "dies", "pid": str(p.pid[i]), "age": a, "sex": p.sex[i], "health": p.health[i], "e": _bits(e), "quartile": qk, "q": _bits(q), "died": died})
	if died:
		return
	p.age[i] = a + 1
	var im0: int = p.intends_marry[i]
	var ik0: int = p.intended_kids[i]
	LC.year_turn(p, i)
	ylog.append({"call": "year_turn", "pid": str(p.pid[i]), "age": p.age[i], "sex": p.sex[i], "births_n": p.births_n[i], "intends_marry0": im0,
		"intended_kids0": ik0, "intends_marry": p.intends_marry[i], "intended_kids": p.intended_kids[i]})
	if p.age[i] == 22 and p.employment[i] == p.EMP_STUDENT:
		p._draw_attributes_education(i)
		p.LAB.enter_work(p, i, counts)
	elif p.age[i] == 15 and p.employment[i] == p.EMP_NONE:
		LC.enter_school(p, i)
		ylog.append({"call": "enter_school", "pid": str(p.pid[i])})
	elif p.age[i] == 65 and (p.employment[i] == p.EMP_REGULAR or p.employment[i] == p.EMP_NONREGULAR or p.employment[i] == p.EMP_UNEMPLOYED):
		LC.retire(p, i, counts)
		ylog.append({"call": "retire", "pid": str(p.pid[i]), "retired": p.employment[i] == p.EMP_RETIRED})
	elif p.employment[i] == p.EMP_REGULAR or p.employment[i] == p.EMP_NONREGULAR:
		p.income[i] = p.wage(i)
	p.skill[i] = minf(100.0, p.skill[i] + (0.8 if p.employment[i] <= p.EMP_NONREGULAR and p.employment[i] >= p.EMP_REGULAR else 0.2))
	p._compose_drives(i)


func _bits(x: float) -> String:
	return str(PackedFloat64Array([x]).to_byte_array().decode_s64(0))


func _store(path: String, s: String) -> void:
	var f := FileAccess.open(path, FileAccess.WRITE)
	f.store_string(s)
	f.close()


func _names(p: RefCounted) -> Array:
	var names: Array = []
	for f: Array in p.fields():
		names.append(String(f[0]))
	for h: Array in p.household_fields():
		names.append(String(h[0]))
	for x: String in EXTRAS:
		names.append(x)
	names.sort()
	return names


## A cut: its per-field SHA-256 lines, and with whole its typed tree (oracle_dump.gd's _enc)
func _snap(p: RefCounted, dir: String, whole: bool) -> void:
	var lines := ""
	for nm: String in _names(p):
		var h := HashingContext.new()
		h.start(HashingContext.HASH_SHA256)
		_canon(h, p.get(nm))
		lines += "%s %s\n" % [nm, h.finish().hex_encode()]
	_store(dir + ".sha.txt", lines)
	if not whole:
		return
	DirAccess.make_dir_recursive_absolute(dir)
	_files = 0
	var tree := {}
	for nm2: String in _names(p):
		tree[nm2] = _enc(p.get(nm2), dir, nm2)
	_store(dir + "/state.json", JSON.stringify(tree, "", false))


func _lines_digest(p: RefCounted) -> String:
	var lines := ""
	for nm: String in _names(p):
		var h := HashingContext.new()
		h.start(HashingContext.HASH_SHA256)
		_canon(h, p.get(nm))
		lines += "%s %s\n" % [nm, h.finish().hex_encode()]
	return lines.sha256_text()


func _write_registry(p: RefCounted) -> void:
	var consts := {"C": p.REL.C, "M": p.GRP.M, "NT": p.NT, "NE": p.NE, "ND": p.ND, "K_MEM": p.K_MEM, "AGES": p.AGES, "SEXES": p.SEXES,
		"K_FAMILY": p.REL.K_FAMILY, "TRUST0": p.REL.TRUST0, "MOVE_KEEP": p.MOVE_KEEP, "AGE_BANDS": p.AGE_BANDS,
		"EMOTIONS": p.EMOTIONS, "DRIVES": p.DRIVES, "D_FAMILY": p.D_FAMILY, "D_AUTONOMY": p.D_AUTONOMY, "D_SECURITY": p.D_SECURITY,
		"GRADE_POOR": p.GRADE_POOR, "GRADE_LIMITED": p.GRADE_LIMITED, "EMP_STUDENT": p.EMP_STUDENT, "EMP_RETIRED": p.EMP_RETIRED}
	_store(out + "/registry.json", JSON.stringify({"fields": p.fields(), "household_fields": p.household_fields(), "extras": EXTRAS,
		"lc_writes": LC_WRITES, "consts": consts}))
	DirAccess.make_dir_recursive_absolute(out + "/spec")
	_files = 0
	_store(out + "/spec/state.json", JSON.stringify({"spec": _enc(p.spec, out + "/spec", "spec"), "hh_spec": _enc(p.hh_spec, out + "/spec", "hh_spec")}, "", false))


## L0-k and L0-sort's inputs and GDScript's answers
func _write_grid(seed: int) -> void:
	var tags := ["hhinst", "hhtype", "hhsize", "hhalone", "hhband", "hhage", "hhgap", "hhspsex", "hhkids", "hhbirthage", "hhbirthyear",
		"hhkidsex", "hhkidhome", "hhgrand", "hhgrandsex", "hholdspouse", "hhchildgap", "hhson", "grade0", "grade_class0", "evermar0", "parity0",
		"lc_intend", "lc_reintend", "lc_kids", "death", "retire", "t22b_grade", "lc_inst", "lc_movein", "lc_divorce", "lc_birth", "lc_leave",
		"lc_partner", "lc_partnerpick", "lc_accept", "lc_agree", "lc_econ", "lc_custody", "lc_sex", "movekeep"]
	var g: Array = []
	for t: String in tags:
		for a: int in [-1, 0, 1, 13, 47, 1000003, 140737488355327]:
			g.append([t, a, _bits(KEYED.u(seed, t, a, 7, 3)), KEYED.below(17, seed, t, a, 7, 3), _bits(KEYED.normal(seed, t, a, 7, 3))])
	var pids: Array = []
	for r: int in [1, 13, 47]:
		for y: int in [1924, 2024, 2026]:
			for s: int in 2:
				for k: int in [0, 5, 1000000, 1000123]:
					pids.append([r, y, s, k, str(KEYED.pid(seed, r, y, s, k))])
	var sorts: Array = []
	for sz: int in [0, 1, 2, 3, 15, 16, 17, 31, 33, 64, 100, 257, 300]:
		for ties: int in [3, 1000000]:
			var rows: Array = []
			var keys: Array = []
			for i: int in sz:
				var v: float = floor(KEYED.u(seed, "sortgrid", sz, ties, i) * float(ties))
				rows.append([v, 0.0, i])
				keys.append(_bits(v))
			rows.sort_custom(func(x: Array, y: Array) -> bool: return float(x[0]) < float(y[0]))
			var perm: Array = []
			for r2: Array in rows:
				perm.append(int(r2[2]))
			sorts.append({"keys": keys, "perm": perm})
	_store(out + "/grid.json", JSON.stringify({"seed": seed, "keyed": g, "pid": pids, "sort": sorts}))


## LC.quartile_cuts' rows (life_course.gd:349-353) with each row's index after them, sorted by its comparator: the permutation per band
func _write_sort(p: RefCounted, path: String) -> void:
	var by: Array = []
	for b: int in 9:
		by.append([])
	for i: int in p.n:
		(by[LC._b10(p.age[i])] as Array).append([LC.equivalized(p, i), p.weight[i], i])
	var perms: Array = []
	for b2: int in 9:
		var rows: Array = by[b2]
		rows.sort_custom(func(x: Array, y: Array) -> bool: return float(x[0]) < float(y[0]))
		var perm: Array = []
		for r: Array in rows:
			perm.append(int(r[2]))
		perms.append(perm)
	_store(path, JSON.stringify(perms))


## The month's newborns: the post state's persons whose pid the pre state did not hold, in index order
func _write_newborns(p: RefCounted, n_pre: int, pre_pids: Dictionary, path: String) -> void:
	var rows: Array = []
	var lcw := {}
	for x: String in LC_WRITES:
		lcw[x] = true
	for h: Array in p.household_fields():
		if int(h[3]) > 0:
			lcw[String(h[0])] = true
	for i: int in p.n:
		if pre_pids.has(p.pid[i]):
			continue
		var row := {"pid": str(p.pid[i])}
		for f: Array in p.fields():
			var nm: String = String(f[0])
			var st: int = int(f[2])
			if st <= 0 or lcw.has(nm):
				continue
			var arr = p.get(nm)
			var vals: Array = []
			for c: int in st:
				var v: Variant = arr[i * st + c]
				vals.append(_bits(v) if typeof(v) == TYPE_FLOAT else str(v))
			row[nm] = vals
		rows.append(row)
	_store(path, JSON.stringify({"n_pre": n_pre, "rows": rows}))


## oracle_dump.gd's typed tree (_enc); packed arrays up to 256 bytes inline. Why inline: a cut has hundreds of small packed arrays (hh_members)
func _enc(v: Variant, dir: String, path: String) -> Variant:
	match typeof(v):
		TYPE_NIL:
			return null
		TYPE_BOOL:
			return v
		TYPE_INT:
			return {"i": str(v)}
		TYPE_FLOAT:
			return {"f": str(PackedFloat64Array([v]).to_byte_array().decode_s64(0))}
		TYPE_STRING, TYPE_STRING_NAME:
			return {"s": String(v)}
		TYPE_ARRAY:
			var a: Array = []
			for i: int in (v as Array).size():
				a.append(_enc(v[i], dir, "%s.%d" % [path, i]))
			return {"a": a}
		TYPE_DICTIONARY:
			var d: Array = []
			var j: int = 0
			for k in v:
				d.append([_enc(k, dir, ""), _enc(v[k], dir, "%s.%d" % [path, j])])
				j += 1
			return {"d": d}
		TYPE_PACKED_STRING_ARRAY:
			return {"p": "str", "v": Array(v)}
		TYPE_PACKED_INT64_ARRAY, TYPE_PACKED_INT32_ARRAY, TYPE_PACKED_FLOAT64_ARRAY, TYPE_PACKED_FLOAT32_ARRAY, TYPE_PACKED_BYTE_ARRAY:
			var kind: String = {TYPE_PACKED_INT64_ARRAY: "i64", TYPE_PACKED_INT32_ARRAY: "i32", TYPE_PACKED_FLOAT64_ARRAY: "f64",
				TYPE_PACKED_FLOAT32_ARRAY: "f32", TYPE_PACKED_BYTE_ARRAY: "u8"}[typeof(v)]
			var b: PackedByteArray = v.to_byte_array() if kind != "u8" else v
			if dir == "" or b.size() <= 256:
				return {"p": kind, "hex": b.hex_encode()}
			_files += 1
			var name: String = "%05d.bin" % _files
			var f := FileAccess.open(dir + "/" + name, FileAccess.WRITE)
			f.store_buffer(b)
			f.close()
			return {"p": kind, "file": name, "n": (v as Variant).size()}
	push_error("oracle_dump_lc_hh: an unencoded type %d at %s" % [typeof(v), path])
	return {"x": typeof(v)}


## oracle_dump.gd's canonical bytes (_canon), unchanged
func _canon(h: HashingContext, v: Variant) -> void:
	var b := PackedByteArray()
	match typeof(v):
		TYPE_NIL:
			h.update("n".to_utf8_buffer())
		TYPE_BOOL:
			h.update(("b1" if v else "b0").to_utf8_buffer())
		TYPE_INT:
			b.resize(9)
			b[0] = 0x69
			b.encode_s64(1, v)
			h.update(b)
		TYPE_FLOAT:
			b.resize(9)
			b[0] = 0x66
			b.encode_double(1, v)
			h.update(b)
		TYPE_STRING, TYPE_STRING_NAME:
			var s: PackedByteArray = String(v).to_utf8_buffer()
			b.resize(9)
			b[0] = 0x73
			b.encode_s64(1, s.size())
			h.update(b)
			h.update(s)
		TYPE_ARRAY:
			b.resize(9)
			b[0] = 0x61
			b.encode_s64(1, (v as Array).size())
			h.update(b)
			for x in v:
				_canon(h, x)
		TYPE_DICTIONARY:
			b.resize(9)
			b[0] = 0x64
			b.encode_s64(1, (v as Dictionary).size())
			h.update(b)
			var ks: Array = (v as Dictionary).keys()
			ks.sort()
			for k in ks:
				_canon(h, k)
				_canon(h, v[k])
		TYPE_PACKED_STRING_ARRAY:
			b.resize(9)
			b[0] = 0x53
			b.encode_s64(1, (v as PackedStringArray).size())
			h.update(b)
			for s2: String in v:
				_canon(h, s2)
		TYPE_PACKED_INT64_ARRAY, TYPE_PACKED_INT32_ARRAY, TYPE_PACKED_FLOAT64_ARRAY, TYPE_PACKED_FLOAT32_ARRAY, TYPE_PACKED_BYTE_ARRAY:
			var kind: int = {TYPE_PACKED_INT64_ARRAY: 0x71, TYPE_PACKED_INT32_ARRAY: 0x6c, TYPE_PACKED_FLOAT64_ARRAY: 0x44, TYPE_PACKED_FLOAT32_ARRAY: 0x46, TYPE_PACKED_BYTE_ARRAY: 0x42}[typeof(v)]
			b.resize(9)
			b[0] = kind
			b.encode_s64(1, (v as Variant).size())
			h.update(b)
			h.update(v.to_byte_array() if typeof(v) != TYPE_PACKED_BYTE_ARRAY else v)
		_:
			push_error("oracle_dump_lc_hh: no canonical form for type %d" % typeof(v))
