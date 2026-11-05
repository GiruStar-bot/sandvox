extends SceneTree
## The oracle's side of the Python trial (docs/team/modern/py/PY_TRIAL_PLAN.md §3): builds the national tiers start, writes its
## whole state S0, then steps the tiers month by month and writes each month's per-field SHA-256s (the tiers digest's terms).
##   ORACLE_OUT=outputs/py_oracle/<tag> ORACLE_MONTHS=13 [ORACLE_MODE=people] [ORACLE_FULL=1,12] [ORACLE_K=8] \
##     godot --headless --path . --script res://tools/py/oracle_dump.gd
## ORACLE_PREFS=13,47 builds the start on those prefectures only (T23_PLAN §6, the two-prefecture start of T2s-fr AMENDED).
## ORACLE_MODE=people steps people.step instead of TR.step alone (P2a), and writes the persons' rows each month (PERSONS_PORT_PLAN
## §2-§4): mNN.persons.sha.txt, mNN.persons.nonfinite.txt (Q-nan) and, at the ORACLE_FULL months, mNN_persons/state.json. ORACLE_FULL lists the months whose whole state is written too.
## ORACLE_CKPT=n writes people.to_dict() every n months (ckpt_mNN.bin, zstd); ORACLE_RESUME=<that file> continues from it, its month next
## Why the save and not the dump's own tree: from_dict is the restore T2s-f shows continues at the uninterrupted run's digest
## The state: every tr_* variable of people.gd, hh_spec, and the scalars month, seed_v, base_year, written as state.json (a typed tree)
## and one raw little-endian file per packed array. The digest's canonical bytes are tiers_digest.py's (the same definition).
const PEOPLE = preload("res://sim/modern/people/people.gd")
const MS = preload("res://sim/modern/modern_status.gd")
const CANON = preload("res://sim/modern/canon.gd")
const TR = preload("res://sim/modern/people/tiers.gd")
const ENV := {"inflation_month": 0.02 / 12.0, "food_price_yoy": 0.0, "unemployment_rate": 0.025, "levers": []}
const SKIP := ["tr_margins"]

var _files: int = 0


func _init() -> void:
	var out: String = OS.get_environment("ORACLE_OUT")
	var months: int = int(OS.get_environment("ORACLE_MONTHS")) if OS.get_environment("ORACLE_MONTHS") != "" else 13
	var people_mode: bool = OS.get_environment("ORACLE_MODE") == "people"
	var full: Array = []
	for s: String in OS.get_environment("ORACLE_FULL").split(",", false):
		full.append(int(s))
	DirAccess.make_dir_recursive_absolute(out)
	var st = MS.new()
	st.load(2024, ["JPN"])
	var prefs: Dictionary = CANON.load_json("res://data/modern/polity/jpn_prefectures.json")["prefectures"]
	if OS.get_environment("ORACLE_PREFS") != "":
		var only: Dictionary = {}
		for c: String in OS.get_environment("ORACLE_PREFS").split(",", false):
			only[c] = prefs[c]
		prefs = only
	var p = PEOPLE.new()
	p.tiers = true
	if OS.get_environment("ORACLE_K") != "":
		p.tier_k = int(OS.get_environment("ORACLE_K"))
	var t0: int = Time.get_ticks_usec()
	var ckpt: int = int(OS.get_environment("ORACLE_CKPT")) if OS.get_environment("ORACLE_CKPT") != "" else 0
	var first: int = 1
	if OS.get_environment("ORACLE_RESUME") != "":
		var fr := FileAccess.open_compressed(OS.get_environment("ORACLE_RESUME"), FileAccess.READ, FileAccess.COMPRESSION_ZSTD)
		var saved: Dictionary = fr.get_var(false)
		fr.close()
		p = PEOPLE.new()
		p.from_dict(saved)
		saved = {}
		first = p.month + 1
		print("ORACLE resumed at month %d from %s" % [p.month, OS.get_environment("ORACLE_RESUME")])
	else:
		p.create("JPN", 1, st.cohort["JPN"], st.qx["JPN"], prefs, 0, 2024)
		print("ORACLE start usec %d units %d points %d k %d" % [Time.get_ticks_usec() - t0, p.tr_units, p.tr_pt_off[p.tr_units], p.tr_k])
		_write_state(p, out + "/m00")
		_write_hashes(p, out + "/m00.sha.txt")
		if people_mode:
			_write_persons(p, out, "m00", 0 in full)
	for m: int in range(first, months + 1):
		var t1: int = Time.get_ticks_usec()
		if people_mode:
			p.step(ENV)
		else:
			TR.step(p, ENV)
			p.month += 1
		var us: int = Time.get_ticks_usec() - t1
		var tag: String = "m%02d" % m
		var dg: String = _write_hashes(p, "%s/%s.sha.txt" % [out, tag])
		var tl: Dictionary = p.tr_margins.get("t22", {})
		var tally := {}
		for k: String in tl:
			if not k.begins_with("usec"):
				tally[k] = tl[k]
		var f := FileAccess.open("%s/%s.tally.json" % [out, tag], FileAccess.WRITE)
		f.store_string(JSON.stringify(_enc(tally, "", ""), "", false))
		f.close()
		if m in full:
			_write_state(p, "%s/%s" % [out, tag])
		if people_mode:
			_write_persons(p, out, tag, m in full)
		print("ORACLE month %d usec %d digest %s by_step %s" % [m, us, dg, JSON.stringify(tl.get("usec_by_step", {}))])
		if ckpt > 0 and m % ckpt == 0:
			var fw := FileAccess.open_compressed("%s/ckpt_m%03d.bin" % [out, m], FileAccess.WRITE, FileAccess.COMPRESSION_ZSTD)
			fw.store_var(p.to_dict(), false)
			fw.close()
			print("ORACLE checkpoint month %d" % m)
	quit(0)


func _tr_names(p: RefCounted) -> Array:
	var names: Array = []
	for prop: Dictionary in p.get_property_list():
		var n: String = prop["name"]
		if n.begins_with("tr_") and not n in SKIP:
			names.append(n)
	names.sort()
	return names


func _write_state(p: RefCounted, dir: String) -> void:
	DirAccess.make_dir_recursive_absolute(dir)
	_files = 0
	var tree := {}
	for n: String in _tr_names(p):
		tree[n] = _enc(p.get(n), dir, n)
	tree["hh_spec"] = _enc(p.hh_spec, dir, "hh_spec")
	tree["month"] = _enc(p.month, dir, "")
	tree["seed_v"] = _enc(p.seed_v, dir, "")
	tree["base_year"] = _enc(p.base_year, dir, "")
	var f := FileAccess.open(dir + "/state.json", FileAccess.WRITE)
	f.store_string(JSON.stringify(tree, "", false))
	f.close()


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


## Each tr_* field's SHA-256 over its canonical bytes, one "name hex" line each in name order; returns the SHA-256 of those lines
func _write_hashes(p: RefCounted, path: String) -> String:
	var lines := ""
	for n: String in _tr_names(p):
		var h := HashingContext.new()
		h.start(HashingContext.HASH_SHA256)
		_canon(h, p.get(n))
		lines += "%s %s\n" % [n, h.finish().hex_encode()]
	var f := FileAccess.open(path, FileAccess.WRITE)
	f.store_string(lines)
	f.close()
	return lines.sha256_text()


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


## The persons' digest (PERSONS_PORT_PLAN §2): every registry row of people.fields(), the saved scalars and dictionaries, and the
## month's records ("rec." lines, Q-rec), each hashed per field in _canon's bytes; the non-finite values with their bits (Q-nan)
func _persons_names(p: RefCounted) -> Array:
	var names: Array = []
	for row: Array in p.fields():
		names.append(String(row[0]))
	for n: String in ["n", "month", "price_index", "wage_index", "food_plan_start", "pref_pop", "pension", "groups"]:
		names.append(n)
	names.sort()
	return names


func _write_persons(p: RefCounted, out: String, tag: String, whole: bool) -> void:
	var lines := ""
	var nonfinite := ""
	for n: String in _persons_names(p):
		var v: Variant = p.get(n)
		var h := HashingContext.new()
		h.start(HashingContext.HASH_SHA256)
		_canon(h, v)
		lines += "%s %s\n" % [n, h.finish().hex_encode()]
		if v is PackedFloat64Array:
			var a: PackedFloat64Array = v
			for i: int in a.size():
				if not is_finite(a[i]):
					nonfinite += "%s %d %x\n" % [n, i, PackedFloat64Array([a[i]]).to_byte_array().decode_u64(0)]
		elif v is float and not is_finite(v):
			nonfinite += "%s -1 %x\n" % [n, PackedFloat64Array([v]).to_byte_array().decode_u64(0)]
	for n2: String in ["decisions", "refusals", "events", "trace", "group_log"]:
		var h2 := HashingContext.new()
		h2.start(HashingContext.HASH_SHA256)
		_canon(h2, p.get(n2))
		lines += "rec.%s %s\n" % [n2, h2.finish().hex_encode()]
	var f := FileAccess.open("%s/%s.persons.sha.txt" % [out, tag], FileAccess.WRITE)
	f.store_string(lines)
	f.close()
	var f2 := FileAccess.open("%s/%s.persons.nonfinite.txt" % [out, tag], FileAccess.WRITE)
	f2.store_string(nonfinite)
	f2.close()
	if whole:
		var dir: String = "%s/%s_persons" % [out, tag]
		DirAccess.make_dir_recursive_absolute(dir)
		_files = 0
		var tree := {}
		for n3: String in _persons_names(p):
			tree[n3] = _enc(p.get(n3), dir, n3)
		for n4: String in ["decisions", "refusals", "events", "trace", "group_log", "pref_codes", "base_year", "seed_v", "spec"]:
			tree[n4] = _enc(p.get(n4), dir, n4)
		var fs := FileAccess.open(dir + "/state.json", FileAccess.WRITE)
		fs.store_string(JSON.stringify(tree, "", false))
		fs.close()
