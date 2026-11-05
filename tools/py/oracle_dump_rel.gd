extends SceneTree
## The oracle's side of REL_PORT_PLAN (§2-4): the households-off persons stepped by rel_hooked_people.gd, whose cuts write the state at
## each module call boundary; the frozen people.gd is stepped beside it for D-hook.
##   ORACLE_OUT=outputs/py_oracle/rel [ORACLE_SEEDS=1,7,42] [ORACLE_MONTHS=36] [ORACLE_NPER=20] [ORACLE_U_SEED=7] \
##     godot --headless --path . --script res://tools/py/oracle_dump_rel.gd
## Per seed, under <out>/s<seed>/: m00 (the created state), s0g.txt, and for each month m: mMM_pre, mMM_a, mMM_b, mMM_wpre (whole states,
## each with its .sha.txt), mMM_w.sha.txt, mMM_r.json (the replenish records), mMM_truth.json; and, for ORACLE_U_SEED, u_in, u_out.json,
## u_out.sha.txt and u_post.sha.txt, then k_in, k_out.json, k_out.sha.txt and k_post.sha.txt (row K). dhook.txt holds D-hook's line per month.
## Each month also writes mMM_kpre (the state _ranks reads), mMM_rank.sha.txt, mMM_recpre and mMM_rec.sha.txt (rows T-rank, T-rec).
## ORACLE_TIERS=1 (§6, P-a's mode; one national run, alone): under <out>/t<seed>/ the same month files and dhook_t.txt; with
## ORACLE_FROZEN=1 the frozen people only, writing dhook_ref_fromNN.txt. ORACLE_CKPT=k saves to.dict() every k months (ckpt_mNNN.bin,
## zstd); ORACLE_RESUME=<that file> continues from it to ORACLE_MONTHS. The plan's runs (AMENDED T2): hooked seed 1 to month 24 in
## chunks of 7 (ORACLE_CKPT=7), hooked seeds 7 and 42 to month 7
const PEOPLE = preload("res://sim/modern/people/people.gd")
const HOOKED = preload("res://tools/py/rel_hooked_people.gd")
const REL = preload("res://sim/modern/people/relations.gd")
const GRP = preload("res://sim/modern/people/groups.gd")
const ACT = preload("res://sim/modern/people/actions.gd")
const KEYED = preload("res://sim/earth_core/keyed.gd")
const MS = preload("res://sim/modern/modern_status.gd")
const CANON = preload("res://sim/modern/canon.gd")
const TIERS_ENV := {"inflation_month": 0.02 / 12.0, "food_price_yoy": 0.0, "unemployment_rate": 0.025, "levers": []}   # oracle_dump.gd's ENV
const LINKS := ["contact_idx", "contact_kind", "contact_trust", "contact_last", "member_of", "union_cover", "groups"]

var _files: int = 0
var _dir: String = ""
var _r: Array = []
var _fails: int = 0


func _init() -> void:
	var out: String = OS.get_environment("ORACLE_OUT")
	var months: int = _env_int("ORACLE_MONTHS", 36)
	var n_per: int = _env_int("ORACLE_NPER", 20)
	var u_seed: int = _env_int("ORACLE_U_SEED", 7)
	var seeds: Array = []
	for s: String in (OS.get_environment("ORACLE_SEEDS") if OS.get_environment("ORACLE_SEEDS") != "" else "1,7,42").split(",", false):
		seeds.append(int(s))
	var st = MS.new()
	st.load(2024, ["JPN"])
	var prefs: Dictionary = CANON.load_json("res://data/modern/polity/jpn_prefectures.json")["prefectures"]
	if OS.get_environment("ORACLE_TIERS") == "1":
		for sv: int in seeds:
			_tiers_run(st, out, sv, months, OS.get_environment("ORACLE_FROZEN") == "1")
		print("ORACLE_REL done, %d failures" % _fails)
		quit(1 if _fails > 0 else 0)
		return
	for sv: int in seeds:
		var sd: String = "%s/s%d" % [out, sv]
		DirAccess.make_dir_recursive_absolute(sd)
		var pf = PEOPLE.new()
		var ph = HOOKED.new()
		var pg = PEOPLE.new()
		for q in [pf, ph, pg]:
			var err: String = q.create("JPN", sv, st.cohort["JPN"], st.qx["JPN"], prefs, n_per, 2024)
			if err != "":
				push_error("oracle_dump_rel: create " + err)
				quit(2)
				return
		_write_state(_snap(ph, {}), sd + "/m00")
		# S0-g: the clearing of REL_PORT_PLAN §2 (S0) and a rebuild reproduce the created links, so the cleared state is the true pre-build state
		_clear_links(pg)
		REL.build(pg)
		GRP.seed_groups(pg)
		var bad: Array = []
		for k: String in LINKS:
			if _hash(_field(pg, k)) != _hash(_field(ph, k)):
				bad.append(k)
		_line(sd + "/s0g.txt", "%s S0-g seed %d: the cleared state rebuilt equals the created links, differing %s" % ["ok  " if bad.is_empty() else "FAIL", sv, bad])
		var dh := ""
		for m: int in range(1, months + 1):
			_dir = "%s/m%02d" % [sd, m]
			_r = []
			ph.hook = self
			var env: Dictionary = env_of(ph.month)
			ph.step(env)
			pf.step(env_of(pf.month))
			var f := FileAccess.open(_dir + "_r.json", FileAccess.WRITE)
			f.store_string(JSON.stringify(_enc(_r, "", ""), "", false))
			f.close()
			var same: bool = pf.digest() == ph.digest()
			if not same:
				_fails += 1
			dh += "%s D-hook seed %d month %d: hooked digest %s, frozen %s\n" % ["ok  " if same else "FAIL", sv, m, ph.digest().left(16), pf.digest().left(16)]
			print("ORACLE_REL seed %d month %d d-hook %s" % [sv, m, same])
		var fd := FileAccess.open(sd + "/dhook.txt", FileAccess.WRITE)
		fd.store_string(dh)
		fd.close()
		if sv == u_seed:
			ph.hook = null
			_call_table(ph, sd)
			_cases(ph, sd)
	print("ORACLE_REL done, %d failures" % _fails)
	quit(1 if _fails > 0 else 0)


## REL_PORT_PLAN §6 (AMENDED T1): P-a's mode, the national tiers start as oracle_dump.gd makes it, stepped with its fixed ENV. frozen: the
## frozen people alone, its digest per month (D-hook-t's reference); else the hooked people with the cuts
func _tiers_run(st: RefCounted, out: String, sv: int, months: int, frozen: bool) -> void:
	var sd: String = "%s/t%d" % [out, sv]
	DirAccess.make_dir_recursive_absolute(sd)
	var prefs: Dictionary = CANON.load_json("res://data/modern/polity/jpn_prefectures.json")["prefectures"]
	var p = PEOPLE.new() if frozen else HOOKED.new()
	# Why a checkpoint: a national month takes about 8.4 min in Godot, and the verify box stops a command at 2 h (V-rel tiers README)
	if OS.get_environment("ORACLE_RESUME") != "":
		var fr := FileAccess.open_compressed(OS.get_environment("ORACLE_RESUME"), FileAccess.READ, FileAccess.COMPRESSION_ZSTD)
		var saved: Dictionary = fr.get_var(false)
		fr.close()
		p.from_dict(saved)
		saved = {}
		print("ORACLE_REL tiers resumed at month %d from %s" % [p.month, OS.get_environment("ORACLE_RESUME")])
	else:
		p.tiers = true
		if OS.get_environment("ORACLE_K") != "":
			p.tier_k = int(OS.get_environment("ORACLE_K"))
		var err: String = p.create("JPN", sv, st.cohort["JPN"], st.qx["JPN"], prefs, 0, 2024)
		if err != "":
			push_error("oracle_dump_rel: tiers create " + err)
			_fails += 1
			return
	var ckpt: int = _env_int("ORACLE_CKPT", 0)
	var first: int = p.month + 1
	var lines := ""
	for m: int in range(first, months + 1):
		_dir = "%s/m%02d" % [sd, m]
		_r = []
		if not frozen:
			p.hook = self
		p.step(TIERS_ENV)
		if not frozen:
			var f := FileAccess.open(_dir + "_r.json", FileAccess.WRITE)
			f.store_string(JSON.stringify(_enc(_r, "", ""), "", false))
			f.close()
		var dg: String = p.digest()
		lines += "%d %s\n" % [m, dg]
		var fd := FileAccess.open(sd + ("/dhook_ref_from%02d.txt" if frozen else "/dhook_t_from%02d.txt") % first, FileAccess.WRITE)
		fd.store_string(lines)
		fd.close()
		if ckpt > 0 and m % ckpt == 0:
			var fw := FileAccess.open_compressed("%s/ckpt_m%03d.bin" % [sd, m], FileAccess.WRITE, FileAccess.COMPRESSION_ZSTD)
			fw.store_var(p.to_dict(), false)
			fw.close()
			print("ORACLE_REL tiers checkpoint month %d" % m)
		print("ORACLE_REL tiers seed %d month %d %s %s" % [sv, m, "frozen" if frozen else "hooked", dg.left(16)])


func _env_int(k: String, d: int) -> int:
	return int(OS.get_environment(k)) if OS.get_environment(k) != "" else d


## test_modern_relations' declared env (REL_PORT_PLAN §4)
static func env_of(m: int) -> Dictionary:
	return {"inflation_month": 0.027 / 12.0, "food_price_yoy": 0.15 if m >= 12 else 0.0, "unemployment_rate": 0.12 if (m >= 6 and m < 9) else 0.025, "levers": []}


func _line(path: String, s: String) -> void:
	print(s)
	if s.begins_with("FAIL"):
		_fails += 1
	var f := FileAccess.open(path, FileAccess.WRITE)
	f.store_string(s + "\n")
	f.close()


func _clear_links(p: RefCounted) -> void:
	p.contact_idx.fill(-1)
	p.contact_kind.fill(0)
	p.contact_trust.fill(0.0)
	p.contact_last.fill(0)
	p.member_of.fill(-1)
	p.union_cover.fill(0)
	p.groups = []


func _field(p: RefCounted, k: String) -> Variant:
	return p.get(k)


## The group log without its free text (REL_PORT_PLAN §3, ECON A1)
static func _log(p: RefCounted) -> Array:
	var out: Array = []
	for e: Dictionary in p.group_log:
		var d: Dictionary = e.duplicate()
		d.erase("why")
		out.append(d)
	return out


## The cut's state: every row of people.fields(), the groups, the scalars and flags the modules read, and the cut's extra values
func _snap(p: RefCounted, extra: Dictionary) -> Dictionary:
	var t := {}
	for f: Array in p.fields():
		t[String(f[0])] = p.get(String(f[0]))
	t["groups"] = p.groups
	t["group_log"] = _log(p)
	t["pref_pop"] = p.pref_pop
	t["pref_codes"] = p.pref_codes
	t["month"] = p.month
	t["seed_v"] = p.seed_v
	t["n"] = p.n
	t["households"] = p.households
	t["group_influence"] = p.group_influence
	t["contact_news"] = p.contact_news
	t["contact_renewal"] = p.contact_renewal
	t["trace_pids"] = p.trace_pids
	for k: String in extra:
		t[k] = extra[k]
	return t


func cut_pre(p: RefCounted) -> void:
	_write_state(_snap(p, {}), _dir + "_pre")


func cut_a(p: RefCounted, counts: Dictionary, dec_counts: Dictionary, ref_counts: Dictionary) -> void:
	_write_state(_snap(p, {"counts": counts, "dec_counts": dec_counts, "ref_counts": ref_counts}), _dir + "_a")


func cut_b(p: RefCounted, counts: Dictionary, truth: Dictionary) -> void:
	_write_state(_snap(p, {"counts": counts}), _dir + "_b")
	var f := FileAccess.open(_dir + "_truth.json", FileAccess.WRITE)
	f.store_string(JSON.stringify(_enc(truth, "", ""), "", false))
	f.close()


## The persons replenish(i) can read or write: i and its ten keyed candidates (relations.gd:100 draws pool[below(…, month * 16 + t)])
func _touched(p: RefCounted, i: int, pool: Array) -> Array:
	var js: Array = [i]
	if pool.size() > 0:
		for t: int in 10:
			var j: int = pool[KEYED.below(pool.size(), p.seed_v, "replenish", int(p.pid[i] & 0x7FFFFFFFFFFF), p.month * 16 + t, 0)]
			if not js.has(j):
				js.append(j)
	return js


func _rows(p: RefCounted, js: Array) -> Array:
	var out: Array = []
	for j: int in js:
		out.append([j, p.contact_idx.slice(j * REL.C, (j + 1) * REL.C), p.contact_kind.slice(j * REL.C, (j + 1) * REL.C),
			p.contact_trust.slice(j * REL.C, (j + 1) * REL.C), p.contact_last.slice(j * REL.C, (j + 1) * REL.C), p.age[j], p.employment[j],
			p.hh_kind[j], p.pref_social[j], p.pid[j]])
	return out


func cut_r_pre(p: RefCounted, i: int, pool: Array) -> void:
	var js: Array = _touched(p, i, pool)
	_r.append({"i": i, "pool_n": pool.size(), "pref": p.pref[i], "pre": _rows(p, js), "js": js})


func cut_r_post(p: RefCounted, i: int) -> void:
	var rec: Dictionary = _r[_r.size() - 1]
	rec["post"] = _rows(p, rec["js"])


func cut_w_pre(p: RefCounted) -> void:
	_write_state({"weight": p.weight, "member_of": p.member_of, "groups": p.groups}, _dir + "_wpre")


func cut_w_post(p: RefCounted) -> void:
	_write_hashes({"groups": p.groups}, _dir + "_w.sha.txt")
	_write_state({"n": p.n, "income": p.income, "weight": p.weight, "pid": p.pid, "pref": p.pref, "rank": p.rank}, _dir + "_kpre")


func cut_rank_post(p: RefCounted) -> void:
	_write_hashes({"rank": p.rank}, _dir + "_rank.sha.txt")


func cut_rec_pre(p: RefCounted, counts: Dictionary, dec_counts: Dictionary, ref_counts: Dictionary) -> void:
	_write_state({"month": p.month, "decisions": p.decisions, "refusals": p.refusals, "events": p.events, "counts": counts,
		"dec_counts": dec_counts, "ref_counts": ref_counts}, _dir + "_recpre")


func cut_rec_post(p: RefCounted) -> void:
	_write_hashes({"decisions": p.decisions, "refusals": p.refusals, "events": p.events}, _dir + "_rec.sha.txt")


## Row U's call table (REL_PORT_PLAN §4, AMENDED U1): readers first, then the mutating calls, in this order
func _call_table(p: RefCounted, sd: String) -> void:
	_write_state(_snap(p, {}), sd + "/u_in")
	var outs: Array = []
	var a37: Array = []
	var a41: Array = []
	for i: int in p.n:
		if i % 37 == 0:
			a37.append(i)
		if i % 41 == 5:
			a41.append(i)
	for i: int in a37:
		outs.append(["classes.%d" % i, GRP.classes(p, i)])
		outs.append(["targets.%d" % i, REL.targets(p, i)])
		outs.append(["union_rate.%d" % i, GRP.union_rate(p, i)])
		for a: int in [ACT.A_THRIFT, ACT.A_SPLURGE, ACT.A_SOCIALIZE]:
			outs.append(["contact_action_share.%d.%d" % [i, a], REL.contact_action_share(p, i, a)])
		outs.append(["action_law.%d" % i, ACT.action_law(p, i)])
		outs.append(["pick_group.%d" % i, GRP.pick_group(p, i)])
		outs.append(["discontented_contacts.%d" % i, GRP.discontented_contacts(p, i)])
		outs.append(["most_trusted.%d" % i, REL.most_trusted(p, i)])
		outs.append(["most_trusted_family.%d" % i, REL.most_trusted(p, i, REL.K_FAMILY)])
		outs.append(["pick_partner.%d" % i, REL.pick_partner(p, i, "partner")])
	for ka: int in 6:
		for kb: int in 6:
			outs.append(["relation.%d.%d" % [ka, kb], GRP.relation(ka, kb)])
	outs.append(["group_summary", GRP.group_summary(p)])
	for ck: String in ["age_band", "employment", "income_tercile", "education", "prefecture"]:
		outs.append(["summary_by_class.%s" % ck, GRP.summary_by_class(p, ck, p.emotion_column("anxiety"))])
	for i: int in a37:
		GRP.new_job(p, i)
	for i: int in a41:
		var c0: int = -1
		var c1: int = -1
		for c: int in REL.C:
			if p.contact_idx[i * REL.C + c] >= 0:
				if c0 < 0:
					c0 = c
				elif c1 < 0:
					c1 = c
		if c0 >= 0:
			var j: int = p.contact_idx[i * REL.C + c0]
			REL.unlink(p, j, i)
			outs.append(["has_contact_after_unlink.%d" % i, REL.has_contact(p, j, i)])
			outs.append(["add_back.%d" % i, REL.add(p, j, i, REL.K_FRIEND)])
		if c1 >= 0:
			REL.unlink_slot(p, i, c1)
		REL.drop_all(p, i)
		REL.forget(p, i)
		GRP.clear_cover(p, i)
	var f := FileAccess.open(sd + "/u_out.json", FileAccess.WRITE)
	f.store_string(JSON.stringify(_enc(outs, "", ""), "", false))
	f.close()
	var lines := ""
	for o: Array in outs:
		lines += "%s %s\n" % [o[0], _hash(o[1])]
	var fl := FileAccess.open(sd + "/u_out.sha.txt", FileAccess.WRITE)
	fl.store_string(lines)
	fl.close()
	_write_hashes(_snap(p, {}), sd + "/u_post.sha.txt")


## Row K's declared cases (REL_PORT_PLAN AMENDED K1), on the state the call table left, in this order
func _cases(p: RefCounted, sd: String) -> void:
	_write_state(_snap(p, {}), sd + "/k_in")
	var outs: Array = []
	var a0: int = _first_adult(p, -1, 0)
	outs.append(["kind_id.union", GRP.kind_id("union")])
	outs.append(["kind_id.none", GRP.kind_id("none")])
	outs.append(["slot_self", REL.slot(p, a0, a0)])
	REL.unlink(p, a0, a0)
	for i: int in p.n:
		if i % 29 == 3:
			REL.clear_met(p, i)
	for gid: int in p.groups.size():
		var ok: bool = GRP.join(p, a0, gid)
		outs.append(["join.%d" % gid, ok])
		if not ok and not GRP.is_member(p, a0, gid):
			break
	outs.append(["join.again", GRP.join(p, a0, p.member_of[a0 * GRP.M])])
	var f1: int = _first_adult(p, 13, 0)
	var f2: int = _first_adult(p, 13, 1)
	var c0: Dictionary = {}
	outs.append(["found.1", GRP.found_movement(p, f1, c0)])
	outs.append(["found.2", GRP.found_movement(p, f1, c0)])
	outs.append(["found.3", GRP.found_movement(p, f2, c0)])
	outs.append(["found.counts", c0])
	var gm: int = GRP.find_group(p, GRP.G_MOVEMENT, 13)
	if gm < 0:
		gm = GRP._new_group(p, GRP.G_MOVEMENT, 13, -1)
	var kept: int = 0
	for i: int in p.n:
		if GRP.is_member(p, i, gm):
			if kept < 2:
				kept += 1
			else:
				GRP.leave(p, i, gm)
	for i: int in p.n:
		if kept < 2 and p.pref[i] == 13 and p.age[i] >= 18 and GRP.memberships(p, i) < GRP.M and not GRP.is_member(p, i, gm):
			GRP.join(p, i, gm)
			kept += 1
	p.groups[gm]["small_months"] = GRP.DISSOLVE_MONTHS - 1
	var c1: Dictionary = {}
	GRP.step(p, c1)
	outs.append(["dissolve.status", int(p.groups[gm]["status"])])
	outs.append(["dissolve.counts", c1])
	var c2: Dictionary = {}
	GRP.step(p, c2)
	outs.append(["after.counts", c2])
	p.group_influence = false
	var c3: Dictionary = {}
	GRP.step(p, c3)
	p.group_influence = true
	outs.append(["no_influence.counts", c3])
	for i: int in p.n:
		if p.employment[i] == p.EMP_REGULAR or p.employment[i] == p.EMP_NONREGULAR:
			GRP.new_job(p, i)
	var b0: int = _first_adult(p, 47, 0)
	REL.drop_all(p, b0)
	for j: int in p.n:
		if REL.C <= p.contact_count(b0):
			break
		if j != b0 and p.pref[j] == 47 and not REL.has_contact(p, b0, j):
			REL.add(p, b0, j, REL.K_NEIGHBOUR)
	outs.append(["full_row", p.contact_count(b0)])
	REL.build(p)
	var f := FileAccess.open(sd + "/k_out.json", FileAccess.WRITE)
	f.store_string(JSON.stringify(_enc(outs, "", ""), "", false))
	f.close()
	var lines := ""
	for o: Array in outs:
		lines += "%s %s\n" % [o[0], _hash(o[1])]
	var fl := FileAccess.open(sd + "/k_out.sha.txt", FileAccess.WRITE)
	fl.store_string(lines)
	fl.close()
	_write_hashes(_snap(p, {}), sd + "/k_post.sha.txt")


## The k-th person aged 18 or more in index order, of prefecture code (any when code < 0); -1 when there is none
func _first_adult(p: RefCounted, code: int, k: int) -> int:
	var seen: int = 0
	for i: int in p.n:
		if p.age[i] >= 18 and (code < 0 or p.pref[i] == code):
			if seen == k:
				return i
			seen += 1
	return -1


func _write_state(tree: Dictionary, dir: String) -> void:
	DirAccess.make_dir_recursive_absolute(dir)
	_files = 0
	var enc := {}
	for k: String in tree:
		enc[k] = _enc(tree[k], dir, k)
	var f := FileAccess.open(dir + "/state.json", FileAccess.WRITE)
	f.store_string(JSON.stringify(enc, "", false))
	f.close()
	_write_hashes(tree, dir + ".sha.txt")


func _hash(v: Variant) -> String:
	var h := HashingContext.new()
	h.start(HashingContext.HASH_SHA256)
	_canon(h, v)
	return h.finish().hex_encode()


## One "name hex" line per field in name order; returns the SHA-256 of those lines
func _write_hashes(tree: Dictionary, path: String) -> String:
	var names: Array = tree.keys()
	names.sort()
	var lines := ""
	for k: String in names:
		lines += "%s %s\n" % [k, _hash(tree[k])]
	var f := FileAccess.open(path, FileAccess.WRITE)
	f.store_string(lines)
	f.close()
	return lines.sha256_text()


## oracle_dump.gd's typed tree. Why a copy and not a preload of oracle_dump.gd: it is a SceneTree whose _init runs the tiers dump
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
			if dir == "":
				return {"p": kind, "hex": b.hex_encode()}
			_files += 1
			var name: String = "%05d.bin" % _files
			var f := FileAccess.open(dir + "/" + name, FileAccess.WRITE)
			f.store_buffer(b)
			f.close()
			return {"p": kind, "file": name, "n": (v as Variant).size()}
	push_error("oracle_dump_rel: an unencoded type %d at %s" % [typeof(v), path])
	return {"x": typeof(v)}


## oracle_dump.gd's canonical bytes (core/digest.py), copied for the same reason as _enc
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
			push_error("oracle_dump_rel: no canonical form for type %d" % typeof(v))
