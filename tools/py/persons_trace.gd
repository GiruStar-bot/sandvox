extends SceneTree
## The persons' month traced (PERSONS_PORT_PLAN §3, §6): the tiers start of oracle_dump.gd, then people.step's body at cd165891
## (people.gd 1240-1307) copied here, every member reached through p, with a check between its sections. Each check writes the
## persons' per-field SHA-256s (people.fields() and the saved scalars, as oracle_dump.gd's people mode), the records ("rec."),
## the month's locals ("local."), and every tr_* field's; PTRACE_FULL lists "month:stage" pairs whose whole state is written too,
## so a Python part can start from the oracle's state at its section.
##   PTRACE_OUT=outputs/py_oracle/<tag> PTRACE_MONTHS=24 [PTRACE_FULL=1:c0,1:c2,...] [PTRACE_CKPT=6] [PTRACE_RESUME=<ckpt>] [PTRACE_SEED=1] godot --headless --path . --script res://tools/py/persons_trace.gd
## Why a copy of step and not hooks in people.gd: people.gd is frozen at cd165891 (D475). Row Q-t: each month's tr_* hashes at c8
## equal oracle_dump.gd's tiers-only dump (TR.step reads no persons array), and month 1's persons hashes at c8 equal
## oracle_dump.gd's people mode
const PEOPLE = preload("res://sim/modern/people/people.gd")
const MS = preload("res://sim/modern/modern_status.gd")
const CANON = preload("res://sim/modern/canon.gd")
const TR = preload("res://sim/modern/people/tiers.gd")
const ACT = preload("res://sim/modern/people/actions.gd")
const REL = preload("res://sim/modern/people/relations.gd")
const GRP = preload("res://sim/modern/people/groups.gd")
const LAB = preload("res://sim/modern/econ/labour.gd")
const SV = preload("res://sim/modern/people/state_view.gd")
const LC = preload("res://sim/modern/people/life_course.gd")
const ENV := {"inflation_month": 0.02 / 12.0, "food_price_yoy": 0.0, "unemployment_rate": 0.025, "levers": []}
const STAGES := ["c0", "c1", "c2", "c3", "c4", "c5", "c6", "c7", "c8"]

var _out: String = ""
var _full: Array = []
var _files: int = 0
var _m: int = 0


func _init() -> void:
	_out = OS.get_environment("PTRACE_OUT")
	var months: int = int(OS.get_environment("PTRACE_MONTHS")) if OS.get_environment("PTRACE_MONTHS") != "" else 24
	for s: String in OS.get_environment("PTRACE_FULL").split(",", false):
		_full.append(s)
	DirAccess.make_dir_recursive_absolute(_out)
	var st = MS.new()
	st.load(2024, ["JPN"])
	var prefs: Dictionary = CANON.load_json("res://data/modern/polity/jpn_prefectures.json")["prefectures"]
	var p = PEOPLE.new()
	p.tiers = true
	var first: int = 1
	var ckpt: int = int(OS.get_environment("PTRACE_CKPT")) if OS.get_environment("PTRACE_CKPT") != "" else 0
	if OS.get_environment("PTRACE_RESUME") != "":
		var fr := FileAccess.open_compressed(OS.get_environment("PTRACE_RESUME"), FileAccess.READ, FileAccess.COMPRESSION_ZSTD)
		var saved: Dictionary = fr.get_var(false)
		fr.close()
		p.from_dict(saved)
		first = p.month + 1
		print("PTRACE resumed at month %d" % p.month)
	else:
		p.create("JPN", int(OS.get_environment("PTRACE_SEED")) if OS.get_environment("PTRACE_SEED") != "" else 1, st.cohort["JPN"], st.qx["JPN"], prefs, 0, 2024)
	print("PTRACE start units %d persons %d" % [p.tr_units, p.n])
	for m: int in range(first, months + 1):
		_m = m
		_step(p, ENV)
		print("PTRACE month %d" % m)
		if ckpt > 0 and m % ckpt == 0:
			var fw := FileAccess.open_compressed("%s/ckpt_m%03d.bin" % [_out, m], FileAccess.WRITE, FileAccess.COMPRESSION_ZSTD)
			fw.store_var(p.to_dict(), false)
			fw.close()
			print("PTRACE checkpoint month %d" % m)
	quit(0)


## people.gd step (1240-1307 at cd165891), members through p, checks c0 .. c8 between its sections
func _step(p: RefCounted, env: Dictionary) -> void:
	_ck(p, "c0", {})
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
	_ck(p, "c1", {"infl": infl, "ur": ur, "f": f, "yoy_true": yoy_true, "levers": levers})
	for i: int in p.n:
		var ch: Dictionary = ACT.choose(p, i, p.month)
		var act: int = int(ch["action"])
		ACT.apply(p, i, act, p.month)
		if act == ACT.A_FOUND:
			GRP.found_movement(p, i, counts)
		p.last_action[i] = act
		p._count_decision(dec_counts, act, int(ch["top_drive"]), String(ch["modulated_by"]), i)
		for r: Array in ch["refused"]:
			var rk: String = "%d|%s" % [int(r[0]), String(r[1])]
			ref_counts[rk] = int(ref_counts.get(rk, 0)) + 1
		if p.trace_pids.has(p.pid[i]):
			p.trace.append([p.month, p.pid[i], "decision", ACT.ACTIONS[act], float(ch["u"]), "top drive %s%s, %d options" % [p.DRIVES[int(ch["top_drive"])] if int(ch["top_drive"]) >= 0 else "none", (" (" + String(ch["modulated_by"]) + ")") if String(ch["modulated_by"]) != "" else "", int(ch["options"])]])
	_ck(p, "c2", {"counts": counts, "dec_counts": dec_counts, "ref_counts": ref_counts})
	REL.interact(p, counts)
	REL.learn(p, {"food_price_yoy": yoy_true, "unemployment_rate": ur}, counts)
	GRP.step(p, counts)
	var s: float = p._mean_finding(f) * ur / maxf(1e-6, 1.0 - ur)
	_ck(p, "c3", {"counts": counts, "s": s})
	var pools: Dictionary = {}
	for i0: int in p.n:
		if not pools.has(p.pref[i0]):
			pools[p.pref[i0]] = []
		pools[p.pref[i0]].append(i0)
	for i: int in p.n:
		if p.month % 12 == int(p.pid[i] % 12):
			p._year(i, counts)
			if p.contact_renewal:
				REL.replenish(p, i, pools[p.pref[i]])
		LAB.person_month(p, i, s, f, counts)
		p.apply_month_values(i, p.month_values(SV.new().of_person(p, i), infl, levers), counts)
	_ck(p, "c4", {"counts": counts})
	if p.households:
		LC.grade_birthday(p)
		LC.month(p, counts)
	p.reweight(env.get("cohort", PackedFloat64Array()))
	if p.households:
		LC.quartile_cuts(p)
	_ck(p, "c5", {})
	GRP.refresh_weights(p)
	p._ranks()
	_ck(p, "c6", {})
	for key: String in dec_counts:
		p.decisions.append(dec_counts[key])
	for rk: String in ref_counts:
		var parts: PackedStringArray = rk.split("|")
		p.refusals.append({"month": p.month, "action": ACT.ACTIONS[int(parts[0])], "why": parts[1], "count": int(ref_counts[rk])})
	for kind: String in counts:
		var c: Dictionary = counts[kind]
		p.events.append({"month": p.month, "kind": kind, "count": int(c["n"]), "weight": float(c["w"]), "mean_move": float(c["move"]) / maxf(1.0, float(c["n"])), "why": String(c["why"])})
	_ck(p, "c7", {})
	if p.tiers:
		TR.step(p, env)
	p.month += 1
	_ck(p, "c8", {})


func _persons_names(p: RefCounted) -> Array:
	var names: Array = []
	for row: Array in p.fields():
		names.append(String(row[0]))
	for n: String in ["n", "month", "price_index", "wage_index", "food_plan_start", "pref_pop", "pension", "groups"]:
		names.append(n)
	names.sort()
	return names


func _strip_usec(v: Variant) -> Variant:
	if v is Dictionary:
		var d := {}
		for k in v:
			if k is String and (k as String).begins_with("usec"):
				continue
			d[k] = _strip_usec(v[k])
		return d
	return v


func _ck(p: RefCounted, stage: String, locals: Dictionary) -> void:
	var tag: String = "m%02d_%s" % [_m, stage]
	var lines := ""
	var nonfinite := ""
	var pn: Array = _persons_names(p)
	for n: String in pn:
		var v: Variant = p.get(n)
		lines += "%s %s\n" % [n, _sha(v)]
		if v is PackedFloat64Array:
			var a: PackedFloat64Array = v
			for i: int in a.size():
				if not is_finite(a[i]):
					nonfinite += "%s %d %x\n" % [n, i, PackedFloat64Array([a[i]]).to_byte_array().decode_u64(0)]
		elif v is float and not is_finite(v):
			nonfinite += "%s -1 %x\n" % [n, PackedFloat64Array([v]).to_byte_array().decode_u64(0)]
	for n2: String in ["decisions", "refusals", "events", "trace", "group_log"]:
		lines += "rec.%s %s\n" % [n2, _sha(p.get(n2))]
	var lk: Array = locals.keys()
	lk.sort()
	for n3: String in lk:
		lines += "local.%s %s\n" % [n3, _sha(locals[n3])]
	var tn: Array = []
	for prop: Dictionary in p.get_property_list():
		var nm: String = prop["name"]
		if nm.begins_with("tr_"):
			tn.append(nm)
	tn.sort()
	for n4: String in tn:
		lines += "%s %s\n" % [n4, _sha(_strip_usec(p.get(n4)) if n4 == "tr_margins" else p.get(n4))]
	var f := FileAccess.open("%s/%s.sha.txt" % [_out, tag], FileAccess.WRITE)
	f.store_string(lines)
	f.close()
	if nonfinite != "":
		var f2 := FileAccess.open("%s/%s.nonfinite.txt" % [_out, tag], FileAccess.WRITE)
		f2.store_string(nonfinite)
		f2.close()
	if ("%d:%s" % [_m, stage]) in _full:
		var dir: String = "%s/%s" % [_out, tag]
		DirAccess.make_dir_recursive_absolute(dir)
		_files = 0
		var tree := {}
		for n5: String in pn:
			tree["persons." + n5] = _enc(p.get(n5), dir, n5)
		for n6: String in ["decisions", "refusals", "events", "trace", "group_log", "pref_codes", "base_year", "seed_v", "spec",
				"hh_spec", "trace_pids", "households", "tiers", "group_influence", "contact_news", "contact_renewal", "food_elasticity",
				"state"]:
			tree["persons." + n6] = _enc(p.get(n6), dir, n6)
		# Why only the persons' tr_* reads before c7: the tiers' whole state is about 1 GB, and only TR.step (c7 -> c8) reads it
		for n7: String in tn:
			if stage == "c7" or n7 in ["tr_phi", "tr_pension", "tr_pension_kind", "tr_spec"]:
				tree[n7] = _enc(p.get(n7), dir, n7)
		for n8: String in lk:
			tree["local." + n8] = _enc(locals[n8], dir, n8)
		var fs := FileAccess.open(dir + "/state.json", FileAccess.WRITE)
		fs.store_string(JSON.stringify(tree, "", false))
		fs.close()


func _sha(v: Variant) -> String:
	var h := HashingContext.new()
	h.start(HashingContext.HASH_SHA256)
	_canon(h, v)
	return h.finish().hex_encode()


## A typed tree: ints as {"i": "decimal"}, floats as {"f": "their 64 bits in decimal"}, bools, strings as {"s": …}, arrays as {"a": […]},
## dictionaries as {"d": [[key, value], …]} in insertion order, packed arrays as {"p": kind, "file": …} (a raw file, or inline when small)
## Why not JSON numbers: Godot's JSON writes floats at 17 digits and reads every number back as a float, so int64 and the last bits are lost
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
	push_error("oracle_dump: an unencoded type %d at %s" % [typeof(v), path])
	return {"x": typeof(v)}


## The canonical bytes: a type byte, then int64 LE / float64 LE / UTF-8 with its length / an array's length and elements / a
## dictionary's length and its entries in sorted key order / a packed array's kind, length and LE bytes
## Why sorted keys: the save sorts the pid and remainder dictionaries (people._pid_rows, _rem_rows) and T2s-f shows the month does not
## depend on their order, so insertion order is not part of the state
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
			push_error("oracle_dump: no canonical form for type %d" % typeof(v))
