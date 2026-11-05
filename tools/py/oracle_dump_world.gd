extends SceneTree
## The oracle's side of the world and polity port (docs/team/modern/py/WORLD_PORT_PLAN.md §2-§5).
##   WORLD_MODE=tables WORLD_OUT=outputs/py_oracle/world_tables godot --headless --path . --script res://tools/py/oracle_dump_world.gd
##     W0-h's hash and HMAC table, W0-j's per-file canonical hashes, W-el's election grid (tables.json)
##   WORLD_MODE=run WORLD_OUT=<dir> WORLD_YEAR=2024 WORLD_DAYS=1095 [WORLD_PARAMS='{"compute_growth": 0.15}'] [WORLD_EXTRA=40,365]
##     [WORLD_FULL=31,365] [WORLD_VIEWS=31,365] godot --headless --path . --script res://tools/py/oracle_dump_world.gd
##     the per-field hashes at day 0, every month end and the WORLD_EXTRA days (dNNNN.sha.txt), the whole tree at WORLD_FULL days
##     (dNNNN/state.json), the views' observations of JPN at WORLD_VIEWS days, and the interface values (iface.json, floats as bits)
##   WORLD_CASE (AMENDED B1, WORLD_PORT_PLAN §5): a comma list of declared cases, written into iface.json for the Python to read:
##     drought  the econ's declared shock of test_modern_econ (months 12-23, rice and vegetables x 0.6)
##     cost     crop_farming_JPN's fixed costs x 100 from the start, so the bank refuses its loans and its arrears open a procedure
##     release  the rice_stock_release lever set to 100 kt at the end of day 40 (the world applies it after its 30-day lead)
## The digest's canonical bytes are oracle_dump.gd's _canon (py/core/digest.py's definition); the tree is the world's to_dict() less
## run, econ and people, with field, actors, register and status split one level and every "why" and "line" entry left out (§2)
const MW = preload("res://sim/modern/modern_world.gd")
const MA = preload("res://sim/modern/modern_actors.gd")
const MD = preload("res://sim/modern/modern_data.gd")
const MP = preload("res://sim/modern/modern_publish.gd")
const MV = preload("res://sim/modern/modern_view.gd")
const MEL = preload("res://sim/modern/polity/election.gd")
const MORG = preload("res://sim/modern/polity/organs.gd")
const CANON = preload("res://sim/modern/canon.gd")
const SPLIT := ["field", "actors", "register", "status"]
const DROP := ["run", "econ", "people"]
const FREE_TEXT := ["why", "line"]
const SALT := "0123456789abcdef0123456789abcdef"


## Why a subclass and not a hook in the world: the GDScript is frozen (D475); the world calls enforcement.step(m, econ) by name, so the
## dump swaps in this twin, which records every econ actor's arrears and procedure_until around the frozen rule
class EnfTap extends "res://sim/modern/polity/enforcement.gd":
	var taps: Array = []

	func _snap(econ: RefCounted) -> Array:
		var rows: Array = []
		for a in econ.actors:
			rows.append([a.id, a.stocks.has("arrears"), float(a.stocks.get("arrears", 0.0)), a.stocks.has("procedure_until"),
				a.stocks.get("procedure_until", -1)])
		return rows

	func step(month: int, econ: RefCounted) -> void:
		var before: Array = _snap(econ) if econ != null else []
		super.step(month, econ)
		taps.append({"month": month, "before": before, "after": _snap(econ) if econ != null else []})


var _files: int = 0


func _init() -> void:
	var out: String = OS.get_environment("WORLD_OUT")
	DirAccess.make_dir_recursive_absolute(out)
	if OS.get_environment("WORLD_MODE") == "tables":
		_tables(out)
	else:
		_run(out)
	quit(0)


func _ints(env: String) -> Array:
	var a: Array = []
	for s: String in OS.get_environment(env).split(",", false):
		a.append(int(s))
	return a


func _run(out: String) -> void:
	var year: int = int(OS.get_environment("WORLD_YEAR")) if OS.get_environment("WORLD_YEAR") != "" else 2024
	var days: int = int(OS.get_environment("WORLD_DAYS")) if OS.get_environment("WORLD_DAYS") != "" else 1095
	var p: Dictionary = {}
	if OS.get_environment("WORLD_PARAMS") != "":
		p = JSON.parse_string(OS.get_environment("WORLD_PARAMS"))
	if not p.has("view_salt"):
		p["view_salt"] = SALT
	var extra: Array = _ints("WORLD_EXTRA")
	var full: Array = _ints("WORLD_FULL")
	var views: Array = _ints("WORLD_VIEWS")
	var w = MW.new()
	var t0: int = Time.get_ticks_usec()
	var err: String = w.create(year, p)
	if err != "":
		print("ORACLE_WORLD error ", err)
		quit(1)
		return
	var cases: Array = []
	for c: String in OS.get_environment("WORLD_CASE").split(",", false):
		cases.append(c)
	if w.econ != null and "drought" in cases:
		w.econ.declare_shock(12, 23, {"rice": 0.6, "vegetables": 0.6}, "declared drought in the second year")
	if w.econ != null and "cost" in cases:
		for a in w.econ.actors:
			if a.id == "crop_farming_JPN":
				a.stocks["fixed_costs_bn_month"] = float(a.stocks["fixed_costs_bn_month"]) * 100.0
	var tap: RefCounted = null
	if w.enforcement != null:
		tap = EnfTap.new()
		w.enforcement = tap
	print("ORACLE_WORLD start usec %d entities %d status %s econ %s" % [Time.get_ticks_usec() - t0, w.field.E, str(w.status.entities), str(w.econ != null)])
	var iface := {"year": year, "params": _enc(p, "", ""), "days": days, "cases": cases, "release": [], "month": [], "enforcement": []}
	_check_day(w, out, 0, 0 in full)
	var seen: int = w.chronicle.rows.size()
	for d: int in range(1, days + 1):
		w.advance_to(d)
		if d == 40 and "release" in cases:
			w.status.set_lever("JPN", "rice_stock_release", 100.0)
		var price_rows: Array = []
		for i: int in range(seen, w.chronicle.rows.size()):
			var r: Dictionary = w.chronicle.rows[i]
			if String(r["kind"]) == "release":
				iface["release"].append({"day": d, "rice_t": _enc(r["facts"]["rice_t"], "", ""), "asked_kt": _enc(r["facts"]["asked_kt"], "", "")})
			elif String(r["kind"]) == "price":
				price_rows.append([String(r["facts"]["commodity"]), _enc(r["facts"]["before"], "", ""), _enc(r["facts"]["after"], "", "")])
		seen = w.chronicle.rows.size()
		var month_end: bool = MA.is_month_end(d)
		if month_end and w.econ != null:
			var env: Dictionary = w.econ.world.env
			var row := {"day": d, "world_month": _enc(w.econ.world.month, "", ""), "has_inflation": env.has("inflation"),
				"inflation": _enc(float(env.get("inflation", 0.0)), "", ""), "has_food_price_yoy": env.has("food_price_yoy"),
				"food_price_yoy": _enc(float(env.get("food_price_yoy", 0.0)), "", ""), "prices": price_rows}
			if w.econ.labour != null:
				row["labour"] = _enc([w.econ.labour.u, w.econ.labour.wage_index, float(w.econ.labour.demand_scale.get("food_products", 1.0)),
					w.econ.labour.search_share], "", "")
			iface["month"].append(row)
		if month_end or d in extra or d == days:
			var dg: String = _check_day(w, out, d, d in full)
			print("ORACLE_WORLD day %d digest %s" % [d, dg])
		if d in views:
			_views(w, out, d)
	if tap != null:
		iface["enforcement"] = _enc(tap.taps, "", "")
	var f := FileAccess.open(out + "/iface.json", FileAccess.WRITE)
	f.store_string(JSON.stringify(iface, "", false))
	f.close()
	print("ORACLE_WORLD done usec %d" % (Time.get_ticks_usec() - t0))


## The world's tree of §2
func tree_of(w: RefCounted) -> Dictionary:
	var st: Dictionary = w.to_dict()
	for k: String in DROP:
		st.erase(k)
	var sd: Dictionary = st["status"]
	var indn: Dictionary = {}
	var coh: Dictionary = {}
	for k: String in w.status.entities:
		indn[k] = (w.status.ind[k] as Dictionary).duplicate()
		coh[k] = (w.status.cohort[k] as PackedFloat64Array).duplicate()
	sd["ind"] = indn
	sd["cohort"] = coh
	var out: Dictionary = {}
	for k: String in st:
		if k in SPLIT:
			for k2: String in st[k]:
				out[k + "." + k2] = _strip(st[k][k2])
		else:
			out[k] = _strip(st[k])
	return out


func _strip(v: Variant) -> Variant:
	if v is Dictionary:
		var o: Dictionary = {}
		for k: Variant in v:
			if (k is String or k is StringName) and String(k) in FREE_TEXT:
				continue
			o[k] = _strip(v[k])
		return o
	if v is Array:
		var a: Array = []
		for x: Variant in v:
			a.append(_strip(x))
		return a
	return v


func _check_day(w: RefCounted, out: String, d: int, write_full: bool) -> String:
	var t: Dictionary = tree_of(w)
	var names: Array = t.keys()
	names.sort()
	var lines := ""
	for n: String in names:
		lines += "%s %s\n" % [n, _hash(t[n])]
	var f := FileAccess.open("%s/d%04d.sha.txt" % [out, d], FileAccess.WRITE)
	f.store_string(lines)
	f.close()
	if write_full:
		var dir: String = "%s/d%04d" % [out, d]
		DirAccess.make_dir_recursive_absolute(dir)
		_files = 0
		var enc := {}
		for n2: String in names:
			enc[n2] = _enc(t[n2], dir, n2)
		var f2 := FileAccess.open(dir + "/state.json", FileAccess.WRITE)
		f2.store_string(JSON.stringify(enc, "", false))
		f2.close()
	return lines.sha256_text()


func _views(w: RefCounted, out: String, d: int) -> void:
	for vk: String in ["jpn", "test_b"]:
		var v = w.make_view(vk)
		if v.error != "":
			print("ORACLE_WORLD view error ", v.error)
			continue
		var obs: Dictionary = v.observe(w, w.data.index_of("JPN"))
		var f := FileAccess.open("%s/view_%s_d%04d.json" % [out, vk, d], FileAccess.WRITE)
		f.store_string(JSON.stringify({"sha": _hash(obs), "obs": _enc(obs, "", "")}, "", false))
		f.close()


func _hash(v: Variant) -> String:
	var h := HashingContext.new()
	h.start(HashingContext.HASH_SHA256)
	_canon(h, v)
	return h.finish().hex_encode()


## W0-h, W0-j and W-el (§5)
func _tables(out: String) -> void:
	var data = MD.new()
	if data.load_year(2024) != "":
		print("ORACLE_WORLD error ", data.error)
		return
	var keys: PackedStringArray = data.keys
	var goods: Array = ["lithography", "photoresist", "silicon_wafers", "gallium", "neon", "chips"]
	var figs: Array = MP.FIGURES
	var restrict: Array = []
	for i: int in 1000:
		var s: String = "modern-restrict|%d|%s|%s|%d" % [2022 + i % 3, keys[(i * 7) % keys.size()], goods[i % goods.size()], 30 + i * 13]
		var hb: PackedByteArray = s.sha256_buffer()
		restrict.append([s, hb.decode_u32(0), _enc(float(hb.decode_u32(0)) / 4294967296.0, "", "")])
	var publish: Array = []
	for i2: int in 1000:
		var u: float = MP._unit(keys[(i2 * 11) % keys.size()], String(figs[i2 % figs.size()]), 2015 + i2 % 15)
		publish.append([keys[(i2 * 11) % keys.size()], String(figs[i2 % figs.size()]), 2015 + i2 % 15, _enc(u, "", "")])
	var crypto := Crypto.new()
	var hm: Array = []
	for salt_hex: String in [SALT, SALT + "ff", SALT + SALT]:
		var salt: PackedByteArray = salt_hex.hex_decode()
		for vk: String in ["jpn", "test_b"]:
			for k: String in keys:
				hm.append([salt_hex, vk, k, "T" + crypto.hmac_digest(HashingContext.HASH_SHA256, salt, ("modern-view|%s|%s" % [vk, k]).to_utf8_buffer()).hex_encode().left(10)])
	var files: Array = []
	var m_files: Array = ["MANIFEST.json", "entities.json", "stats.json", "stats_v2022.json", "entity_regions.json", "compute_chain.json", "r56.json",
		"r57.json", "r58.json", "dc_history.json", "visibility.json", "views/jpn.json", "views/test_b.json"]
	for n: String in m_files:
		files.append([n, "m", _hash(CANON.load_json_m("res://data/modern/" + n))])
	for n2: String in ["status/catalog.json", "jpn/status_2024.json", "jpn/levers.json", "jpn/links_2024.json", "polity/jpn_organs.json",
			"polity/jpn_election.json", "polity/jpn_prefectures.json"]:
		files.append([n2, "c", _hash(CANON.load_json("res://data/modern/" + n2))])
	for n3: String in ["polity/jpn_laws.json", "polity/jpn_prefectures.json"]:
		files.append([n3, "raw", _hash(JSON.parse_string(FileAccess.get_file_as_string("res://data/modern/" + n3)))])
	var el = MEL.new()
	el.load_state("JPN")
	var org = MORG.new()
	org.load_state("JPN")
	var grid: Array = []
	for ia: int in range(-4, 5):
		for iu: int in [-1, 0, 1]:
			var shares: Dictionary = el.vote_shares(org.governing, 0.05 * float(ia), float(iu), 0.0)
			var lo: Dictionary = el.run_lower_house(shares)
			var up: Dictionary = el.run_upper_house(shares)
			var des: Dictionary = MEL.designate(lo["seats"], org.governing, org.house_total("house_of_representatives"), org.spec.get("partners", {}))
			grid.append({"a": ia, "u": iu, "sha": _hash({"shares": shares, "lower": lo, "upper": up, "designate": _strip(des)}),
				"shares": _enc(shares, "", ""), "lower_seats": _enc(lo["seats"], "", ""), "upper": _enc(up["composition"], "", "")})
	var f := FileAccess.open(out + "/tables.json", FileAccess.WRITE)
	f.store_string(JSON.stringify({"restrict": restrict, "publish": publish, "hmac": hm, "files": files, "election": grid}, "", false))
	f.close()
	print("ORACLE_WORLD tables restrict %d publish %d hmac %d files %d election %d" % [restrict.size(), publish.size(), hm.size(), files.size(), grid.size()])


## oracle_dump.gd's typed tree (ints {"i"}, floats {"f": bits}, strings {"s"}, arrays {"a"}, dictionaries {"d"} in insertion order,
## packed arrays {"p"} as a raw file or inline hex)
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
	push_error("oracle_dump_world: an unencoded type %d at %s" % [typeof(v), path])
	return {"x": typeof(v)}


## oracle_dump.gd's _canon, unchanged
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
			push_error("oracle_dump_world: no canonical form for type %d" % typeof(v))
