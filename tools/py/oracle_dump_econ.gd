extends SceneTree
## The oracle's side of the economy's port (docs/team/modern/py/ECON_PORT_PLAN.md §2, A1, A2, A4): builds the economy's start, writes
## its state m00, then steps the economy month by month and writes each month's per-field SHA-256s and its interface values.
##   ORACLE_OUT=outputs/py_oracle/econ_<tag> ORACLE_MONTHS=36 [ORACLE_SEED=7] [ORACLE_DROUGHT=12:23:0.6] [ORACLE_FULL=12,24] \
##     godot --headless --path . --script res://tools/py/oracle_dump_econ.gd
##   ORACLE_OUT=<dir> ORACLE_MODE=json godot ... (E0-j: the canonical bytes of every econ data file after canon, one line each)
##   ORACLE_OUT=<dir> ORACLE_MODE=people [ORACLE_PEOPLE_SEED=1] [ORACLE_PEOPLE_N=200] ORACLE_MONTHS=36 godot ... (E2: the modern world
##     with the persons, as people_run.gd builds it; the economy's state after each month end, its interface, and the state's rice releases)
## ORACLE_SEED and ORACLE_DROUGHT are econ_run.gd's --seed and --drought (the seeded shocks over months / 12 + 1 years; the drought on
## rice and vegetables), so the last month's legacy digest printed here is econ_run_36's recorded value for the same run.
## The fields: every script variable of the econ month, the world state, each actor (named by its id), the bank and labour, as
## "<owner>.<variable>". Left out as free text (A1): world.records' why (index 7), world.transfers' why (index 4), each actor's log
## (its rule and reason texts), each shock's "why", and the error strings. The control strings (ids, kinds, statuses, the record keys,
## the transfer tags) stay. labour.log is kept: its rows are numbers.
const EM = preload("res://sim/modern/econ/econ_month.gd")
const MW = preload("res://sim/modern/modern_world.gd")
const MA = preload("res://sim/modern/modern_actors.gd")
const CANON = preload("res://sim/modern/canon.gd")
const ECON_DIR := "res://data/modern/econ/"
const SKIP := ["error"]

var _files: int = 0


func _init() -> void:
	var out: String = OS.get_environment("ORACLE_OUT")
	DirAccess.make_dir_recursive_absolute(out)
	if OS.get_environment("ORACLE_MODE") == "json":
		print("ORACLE json %s" % _write_json_hashes(out + "/econ_json.sha.txt"))
		quit(0)
		return
	var months: int = int(OS.get_environment("ORACLE_MONTHS")) if OS.get_environment("ORACLE_MONTHS") != "" else 36
	if OS.get_environment("ORACLE_MODE") == "people":
		_people(out, months)
		quit(0)
		return
	var full: Array = []
	for s: String in OS.get_environment("ORACLE_FULL").split(",", false):
		full.append(int(s))
	var e = EM.new()
	if e.create("JPN") != "":
		print("ERROR ", e.error)
		quit(1)
		return
	var drought: String = OS.get_environment("ORACLE_DROUGHT")
	if drought != "":
		var dp: PackedStringArray = drought.split(":")
		e.declare_shock(int(dp[0]), int(dp[1]), {"rice": float(dp[2]), "vegetables": float(dp[2])}, "declared drought")
	if OS.get_environment("ORACLE_SEED") != "":
		e.seed_shocks(int(OS.get_environment("ORACLE_SEED")), months / 12 + 1)
		if e.error != "":
			print("ERROR ", e.error)
			quit(1)
			return
	_write_state(e, out + "/m00")
	print("ORACLE month 0 digest %s" % _write_hashes(e, out + "/m00.sha.txt"))
	_write_iface(e, out + "/m00.iface.json")
	for m: int in range(1, months + 1):
		e.step()
		var tag: String = "m%02d" % m
		var dg: String = _write_hashes(e, "%s/%s.sha.txt" % [out, tag])
		_write_iface(e, "%s/%s.iface.json" % [out, tag])
		if m in full:
			_write_state(e, "%s/%s" % [out, tag])
		print("ORACLE month %d digest %s" % [m, dg])
	print("ORACLE legacy digest %d %s" % [e.world.month, e.digest()])
	quit(0)


## E2's oracle: the economy inside the modern world with the persons. Each month end it writes the economy's fields after the day (the
## persons' supply already received, as labour's search_share, wage_demand_share and demand_scale), the interface values, and the
## state's rice releases that reached the economy before its step (the trading houses' release_rice notes, in order).
## Why after the day and not between econ.step and enforcement: the polity's enforcement writes into the actors only on arrears, and a
## replay that misses such a write shows it as a differing field, not as a pass
func _people(out: String, months: int) -> void:
	var w = MW.new()
	var seed_p: int = int(OS.get_environment("ORACLE_PEOPLE_SEED")) if OS.get_environment("ORACLE_PEOPLE_SEED") != "" else 1
	var n_p: int = int(OS.get_environment("ORACLE_PEOPLE_N")) if OS.get_environment("ORACLE_PEOPLE_N") != "" else 200
	var err: String = w.create(2024, {"view_salt": "0123456789abcdef0123456789abcdef", "people": true, "people_seed": seed_p, "people_per_prefecture": n_p})
	if err != "":
		print("ERROR ", err)
		return
	var e = w.econ
	_write_state(e, out + "/m00")
	print("ORACLE month 0 digest %s" % _write_hashes(e, out + "/m00.sha.txt"))
	_write_iface(e, out + "/m00.iface.json")
	var th = e.trading_house()
	var day: int = w.field.day
	for m: int in range(1, months + 1):
		var logged: int = th.log.size()
		day += 1
		while not MA.is_month_end(day):
			day += 1
		w.advance_to(day)
		var rel: Array = []
		for i: int in range(logged, th.log.size()):
			if String(th.log[i][2]) == "release_rice":
				rel.append({"f": str(PackedFloat64Array([float(th.log[i][3])]).to_byte_array().decode_s64(0))})
		var tag: String = "m%02d" % m
		var dg: String = _write_hashes(e, "%s/%s.sha.txt" % [out, tag])
		_write_iface(e, "%s/%s.iface.json" % [out, tag], rel)
		print("ORACLE month %d day %d digest %s releases %d" % [m, day, dg, rel.size()])


func _vars(o: Object) -> Array:
	var names: Array = []
	for prop: Dictionary in o.get_property_list():
		if int(prop["usage"]) & PROPERTY_USAGE_SCRIPT_VARIABLE and not String(prop["name"]) in SKIP:
			names.append(String(prop["name"]))
	return names


## The econ state as {"<owner>.<variable>": value}, the free text left out (the header)
func _fields(e: RefCounted) -> Dictionary:
	var f := {}
	for n: String in _vars(e):
		var v: Variant = e.get(n)
		if n in ["world", "actors", "bank", "labour"]:
			continue
		if n == "shocks":
			var sh: Array = []
			for s: Dictionary in v:
				var c: Dictionary = s.duplicate(true)
				c.erase("why")
				sh.append(c)
			v = sh
		f["econ." + n] = v
	for n: String in _vars(e.world):
		var w: Variant = e.world.get(n)
		if n == "records":
			var rs: Array = []
			for r: Array in w:
				rs.append(r.slice(0, 7))
			w = rs
		elif n == "transfers":
			var ts: Array = []
			for t: Array in w:
				ts.append(t.slice(0, 4))
			w = ts
		f["world." + n] = w
	var owners: Array = []
	for a in e.actors:
		owners.append(["actor." + String(a.id), a])
	if e.bank != null:
		owners.append(["bank", e.bank])
	if e.labour != null:
		owners.append(["labour", e.labour])
	for ow: Array in owners:
		for n: String in _vars(ow[1]):
			if n == "log" and String(ow[0]) != "labour":
				continue
			f[String(ow[0]) + "." + n] = ow[1].get(n)
	return f


func _write_state(e: RefCounted, dir: String) -> void:
	DirAccess.make_dir_recursive_absolute(dir)
	_files = 0
	var f: Dictionary = _fields(e)
	var names: Array = f.keys()
	names.sort()
	var tree := {}
	for n: String in names:
		tree[n] = _enc(f[n], dir, n)
	var fh := FileAccess.open(dir + "/state.json", FileAccess.WRITE)
	fh.store_string(JSON.stringify(tree, "", false))
	fh.close()


## A4: the persons' interface values and the inflation the bank reads, each float as its 64 bits (Godot's JSON does not round-trip
## every double); a value the run does not have (labour off) is null
func _write_iface(e: RefCounted, path: String, releases: Array = []) -> void:
	var bits := func(x: Variant) -> Variant: return null if x == null else {"f": str(PackedFloat64Array([float(x)]).to_byte_array().decode_s64(0))}
	var iv := {"inflation": bits.call(e.world.env.get("inflation")), "food_price_yoy": bits.call(e.world.env.get("food_price_yoy"))}
	for k: String in ["search_share", "wage_demand_share", "wage_index", "u"]:
		iv[k] = bits.call(e.labour.get(k)) if e.labour != null else null
	var sc := {}
	if e.labour != null:
		for c: String in e.labour.demand_scale:
			sc[c] = bits.call(e.labour.demand_scale[c])
	iv["scales"] = sc
	iv["rice_releases"] = releases
	var fh := FileAccess.open(path, FileAccess.WRITE)
	fh.store_string(JSON.stringify(iv, "", false))
	fh.close()


## A typed tree, as oracle_dump.gd's: ints as {"i": "decimal"}, floats as {"f": "their 64 bits in decimal"}, bools, strings as
## {"s": …}, arrays as {"a": […]}, dictionaries as {"d": [[key, value], …]} in insertion order, packed arrays as {"p": kind, …}
## Why insertion order in the tree though the digest sorts: the port iterates its dictionaries in the oracle's order (§4), so a Python
## start read from this tree must get that order
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
			for k in v:
				d.append([_enc(k, dir, ""), _enc(v[k], dir, "")])
			return {"d": d}
		TYPE_PACKED_STRING_ARRAY:
			return {"p": "str", "v": Array(v)}
		TYPE_PACKED_INT64_ARRAY, TYPE_PACKED_INT32_ARRAY, TYPE_PACKED_FLOAT64_ARRAY, TYPE_PACKED_FLOAT32_ARRAY, TYPE_PACKED_BYTE_ARRAY:
			var kind: String = {TYPE_PACKED_INT64_ARRAY: "i64", TYPE_PACKED_INT32_ARRAY: "i32", TYPE_PACKED_FLOAT64_ARRAY: "f64",
				TYPE_PACKED_FLOAT32_ARRAY: "f32", TYPE_PACKED_BYTE_ARRAY: "u8"}[typeof(v)]
			var b: PackedByteArray = v.to_byte_array() if kind != "u8" else v
			return {"p": kind, "hex": b.hex_encode()}
	push_error("oracle_dump_econ: an unencoded type %d at %s" % [typeof(v), path])
	return {"x": typeof(v)}


## Each field's SHA-256 over its canonical bytes, one "name hex" line each in name order; returns the SHA-256 of those lines (the
## tiers' definition, oracle_dump.gd)
func _write_hashes(e: RefCounted, path: String) -> String:
	var f: Dictionary = _fields(e)
	var names: Array = f.keys()
	names.sort()
	var lines := ""
	for n: String in names:
		var h := HashingContext.new()
		h.start(HashingContext.HASH_SHA256)
		_canon(h, f[n])
		lines += "%s %s\n" % [n, h.finish().hex_encode()]
	var fh := FileAccess.open(path, FileAccess.WRITE)
	fh.store_string(lines)
	fh.close()
	return lines.sha256_text()


## E0-j (A2): every econ data file as CANON.load_json reads it, its canonical bytes hashed, "file hex" in file-name order; returns the
## SHA-256 of those lines
func _write_json_hashes(path: String) -> String:
	var files: Array = []
	for fn: String in DirAccess.get_files_at(ECON_DIR):
		if fn.ends_with(".json"):
			files.append(fn)
	files.sort()
	var lines := ""
	for fn: String in files:
		var h := HashingContext.new()
		h.start(HashingContext.HASH_SHA256)
		_canon(h, CANON.load_json(ECON_DIR + fn))
		lines += "%s %s\n" % [fn, h.finish().hex_encode()]
	var fh := FileAccess.open(path, FileAccess.WRITE)
	fh.store_string(lines)
	fh.close()
	return lines.sha256_text()


## The canonical bytes, as oracle_dump.gd's _canon (a type byte, then int64 LE / float64 LE / UTF-8 with its length / an array's
## length and elements / a dictionary's length and its entries in sorted key order / a packed array's kind, length and LE bytes)
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
			push_error("oracle_dump_econ: no canonical form for type %d" % typeof(v))
