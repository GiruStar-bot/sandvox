extends SceneTree
## The oracle of the integrated month I-1 (docs/team/modern/py/INTEGRATED_MONTH_PLAN.md §2): the modern world with the representative
## persons, as people_run.gd builds it, advanced by a copy of modern_world.gd advance_to's body with a hook after each of the month's
## steps, and a plain world beside it advanced by advance_to itself (row I-0: their month-end hashes must be equal).
##   MONTH_OUT=<dir> [MONTH_MONTHS=24] [MONTH_FULL=0,1,11,12,17,18,23] [MONTH_SEED=1] [MONTH_N=200] [MONTH_FORCE=day:k:lever:v;...] \
##     godot --headless --path . --script res://tools/py/oracle_dump_month.gd
## At each boundary (B1 after M2 on the month's last day; B2 after M6; B3 after M8; B4 after M9; B5 after M10) it writes
## mMM.bNN.world.sha.txt, .econ.sha.txt and .persons.sha.txt: one "name hex" line per field, each module hashed by the definition its
## own port is checked with (oracle_dump_world.gd's tree_of, oracle_dump_econ.gd's _fields, oracle_dump.gd's persons names), over
## oracle_dump.gd's _canon bytes. mMM.iface.json holds the supply at M4, the env at M8, the summary, the releases and the applied
## levers, every float as its bits; the whole states at the ends of the MONTH_FULL months, each a state.json typed tree: mMM_world
## (the world's to_dict less econ and people, which py/world's from_dict reads), mMM_econ (econ's fields), mMM_persons.
## mMM.plain.sha.txt is the plain world's B5 lines, for I-0. MONTH_FORCE (§7, the release case): at the end of each named day, status.set_lever
## on both worlds; force.json lists them for the Python rows.
const MW = preload("res://sim/modern/modern_world.gd")
const MA = preload("res://sim/modern/modern_actors.gd")
const MD = preload("res://sim/modern/modern_data.gd")
const SALT := "0123456789abcdef0123456789abcdef"
const SPLIT := ["field", "actors", "register", "status"]
const DROP := ["run", "econ", "people"]
const FREE_TEXT := ["why", "line"]
const ECON_SKIP := ["error"]

var _files: int = 0
var _iface: Dictionary = {}


func _init() -> void:
	var out: String = OS.get_environment("MONTH_OUT")
	DirAccess.make_dir_recursive_absolute(out)
	var months: int = int(OS.get_environment("MONTH_MONTHS")) if OS.get_environment("MONTH_MONTHS") != "" else 24
	var full: Array = []
	for s: String in (OS.get_environment("MONTH_FULL") if OS.get_environment("MONTH_FULL") != "" else "0,1,11,12,17,18,23").split(",", false):
		full.append(int(s))
	var seed_p: int = int(OS.get_environment("MONTH_SEED")) if OS.get_environment("MONTH_SEED") != "" else 1
	var n_p: int = int(OS.get_environment("MONTH_N")) if OS.get_environment("MONTH_N") != "" else 200
	var force: Array = []
	for f5: String in OS.get_environment("MONTH_FORCE").split(";", false):
		var p5: PackedStringArray = f5.split(":")
		force.append([int(p5[0]), p5[1], p5[2], float(p5[3])])
	var ff := FileAccess.open("%s/force.json" % out, FileAccess.WRITE)
	ff.store_string(JSON.stringify(force))
	ff.close()
	var params := {"view_salt": SALT, "people": true, "people_seed": seed_p, "people_per_prefecture": n_p}
	var w = MW.new()
	var plain = MW.new()
	var err: String = w.create(2024, params.duplicate(true))
	var err2: String = plain.create(2024, params.duplicate(true))
	if err != "" or err2 != "":
		print("ERROR ", err, err2)
		quit(1)
		return
	_boundary(w, out, "m00.b05")
	if 0 in full:
		_whole(w, out, "m00")
	var i0_bad: int = 0
	for m: int in range(1, months + 1):
		var day: int = w.field.day + 1
		while not MA.is_month_end(day):
			day += 1
		_iface = {"supply": null, "env": null, "summary": null, "releases": [], "levers": []}
		var d0: int = w.field.day
		for fc: Array in force:
			if int(fc[0]) > d0 and int(fc[0]) <= day:
				_hooked_to(w, int(fc[0]), out, m)
				plain.advance_to(int(fc[0]))
				w.status.set_lever(String(fc[1]), String(fc[2]), float(fc[3]))
				plain.status.set_lever(String(fc[1]), String(fc[2]), float(fc[3]))
		_hooked_to(w, day, out, m)
		plain.advance_to(day)
		var lines: String = _module_lines(plain)
		var fp := FileAccess.open("%s/m%02d.plain.sha.txt" % [out, m], FileAccess.WRITE)
		fp.store_string(lines)
		fp.close()
		var same: bool = lines == _module_lines(w)
		i0_bad += 0 if same else 1
		var fi := FileAccess.open("%s/m%02d.iface.json" % [out, m], FileAccess.WRITE)
		fi.store_string(JSON.stringify(_iface, "", false))
		fi.close()
		if m in full:
			_whole(w, out, "m%02d" % m)
		print("ORACLE_MONTH month %d day %d I-0 %s" % [m, day, "same" if same else "DIFFERS"])
	print("ORACLE_MONTH I-0 months differing %d of %d" % [i0_bad, months])
	quit(0)


## advance_to's body (modern_world.gd), with the hooks; every line not marked a hook is the oracle's, in its order
func _hooked_to(w: RefCounted, day: int, out: String, m: int) -> void:
	var S: int = MD.SOURCES.size()
	var sup := PackedFloat64Array()
	sup.resize(w.field.E * S)
	while w.field.day < day:
		for e: int in w.field.E:
			for s: int in S:
				sup[e * S + s] = w.field.supply_of(e, s)
		w.field.step()
		w.register.observe_day(w.field, sup)
		var logged: int = w.status.lever_log.size()
		w.status.step()
		for i: int in range(logged, w.status.lever_log.size()):
			var row: Array = w.status.lever_log[i]
			if String(row[4]) == "applied":
				w.chronicle.add(w.field.day, "lever_applied", String(row[1]), "field", {"lever": String(row[2]), "value": float(row[3])}, "lead time over; the response function ran")
				(_iface["levers"] as Array).append([w.field.day, String(row[1]), String(row[2]), _bits(float(row[3]))])
				if String(row[2]) == "rice_stock_release" and w.econ != null and float(row[3]) > 0.0:
					var got: float = w.econ.release_state_rice(w.field.day / 30, float(row[3]) * 1000.0)
					(_iface["releases"] as Array).append([w.field.day, w.field.day / 30, _bits(float(row[3]) * 1000.0), _bits(got)])
					w.chronicle.add(w.field.day, "release", "JPN", "state", {"rice_t": got, "asked_kt": float(row[3])}, "食糧法: the MA stock to the market")
		if w.econ != null and MA.is_month_end(w.field.day):
			_boundary(w, out, "m%02d.b01" % m)
			if w.people != null:
				var psup: Dictionary = w.people.supply()
				var sc := {}
				for c: String in psup["scales"]:
					sc[c] = _bits(float(psup["scales"][c]))
				_iface["supply"] = {"search_share": _bits(float(psup["search_share"])), "wage_demand_share": _bits(float(psup["wage_demand_share"])), "scales": sc}
				w.econ.labour.receive(float(psup["search_share"]), float(psup["wage_demand_share"]), psup["scales"])
			w.econ.step()
			if w.people != null:
				w.status.ind["JPN"]["unemployment_rate"] = w.econ.labour.u
				var lf: float = w.status.value("JPN", "employed") + w.status.value("JPN", "unemployed")
				w.status.ind["JPN"]["unemployed"] = lf * w.econ.labour.u
				w.status.ind["JPN"]["employed"] = lf * (1.0 - w.econ.labour.u)
			_boundary(w, out, "m%02d.b02" % m)
			for r: Dictionary in w.econ.chronicle_rows(w.data.base_year, w.econ.world.month - 1):
				if String(r["ledger"]) == "goods" and String(r["field"]) == "price":
					w.chronicle.add(w.field.day, "price", "JPN", "market", {"commodity": String(r["key"]).split("|")[0], "before": r["before"], "after": r["after"]}, String(r["why"]))
			if w.people != null:
				var applied_ids: Array = []
				for i: int in range(logged, w.status.lever_log.size()):
					if String(w.status.lever_log[i][4]) == "applied":
						applied_ids.append(String(w.status.lever_log[i][2]))
				var env := {"inflation_month": float(w.econ.world.env.get("inflation", 0.02)) / 12.0, "food_price_yoy": float(w.econ.world.env.get("food_price_yoy", 0.0)), "unemployment_rate": w.econ.labour.u, "wage_index": w.econ.labour.wage_index, "levers": applied_ids, "cohort": w.status.cohort["JPN"]}
				_iface["env"] = {"inflation_month": _bits(env["inflation_month"]), "food_price_yoy": _bits(env["food_price_yoy"]), "unemployment_rate": _bits(env["unemployment_rate"]),
					"wage_index": _bits(env["wage_index"]), "levers": applied_ids.duplicate(), "cohort": _hash(env["cohort"])}
				w.people.step(env)
				var sm: Dictionary = w.people.summary()
				_iface["summary"] = _enc(sm, "", "")
				w.chronicle.add(w.field.day, "people", "JPN", "persons", {"anxiety_p50": float(sm["anxiety_p10_p50_p90"][1]), "discontent_p50": float(sm["discontent_p10_p50_p90"][1]), "real_income_p50": float(sm["real_income_p10_p50_p90"][1]), "pressure_mean": float(sm["pressure_mean"]), "unemployment_rate": float(sm["unemployment_rate"])}, "weighted quantiles over the representative persons")
				w.chronicle.add(w.field.day, "labour", "JPN", "economy", {"unemployment_rate": w.econ.labour.u, "wage_index": w.econ.labour.wage_index, "food_demand_scale": float(w.econ.labour.demand_scale.get("food_products", 1.0)), "search_share": w.econ.labour.search_share}, "the labour market's month (T rules): the persons' supply in, unemployment and the wage index out")
			_boundary(w, out, "m%02d.b03" % m)
			w._s4_month(logged)
			_boundary(w, out, "m%02d.b04" % m)
		w.chronicle.observe_field(w.field, w.data.keys)
		if w.field.day % 365 == 0:
			w.register.close_year(w, w.data.base_year + w.field.day / 365 - 1)
			for k: String in w.status.entities:
				w.chronicle.add(w.field.day, "year_close", k, "field", {"pop_total": w.status.value(k, "pop_total"), "gov_debt_total": w.status.value(k, "gov_debt_total"),
					"niip": w.status.value(k, "niip"), "debt_to_gdp": w.status.value(k, "debt_to_gdp")}, "the year's statuses")
		if MA.is_month_end(w.field.day):
			w._month()
			_boundary(w, out, "m%02d.b05" % m)


func _bits(x: float) -> Dictionary:
	return {"f": str(PackedFloat64Array([x]).to_byte_array().decode_s64(0))}


## The three modules' lines at one boundary, one file each
func _boundary(w: RefCounted, out: String, tag: String) -> void:
	for mod: Array in [["world", _world_tree(w)], ["econ", _econ_fields(w.econ)], ["persons", _persons_fields(w.people)]]:
		var f := FileAccess.open("%s/%s.%s.sha.txt" % [out, tag, mod[0]], FileAccess.WRITE)
		f.store_string(_lines(mod[1]))
		f.close()


func _module_lines(w: RefCounted) -> String:
	return "WORLD\n" + _lines(_world_tree(w)) + "ECON\n" + _lines(_econ_fields(w.econ)) + "PERSONS\n" + _lines(_persons_fields(w.people))


func _lines(t: Dictionary) -> String:
	var names: Array = t.keys()
	names.sort()
	var s := ""
	for n: String in names:
		s += "%s %s\n" % [n, _hash(t[n])]
	return s


func _whole(w: RefCounted, out: String, tag: String) -> void:
	var wd: Dictionary = w.to_dict()
	wd.erase("econ")
	wd.erase("people")
	for mod: Array in [["world", wd], ["econ", _econ_fields(w.econ)], ["persons", _persons_tree(w.people)]]:
		var dir: String = "%s/%s_%s" % [out, tag, mod[0]]
		DirAccess.make_dir_recursive_absolute(dir)
		_files = 0
		var t: Dictionary = mod[1]
		var names: Array = t.keys()
		names.sort()
		var enc := {}
		for n: String in names:
			enc[n] = _enc(t[n], dir, n)
		var f := FileAccess.open(dir + "/state.json", FileAccess.WRITE)
		f.store_string(JSON.stringify(enc, "", false))
		f.close()


## oracle_dump_world.gd's tree_of
func _world_tree(w: RefCounted) -> Dictionary:
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


func _vars(o: Object) -> Array:
	var names: Array = []
	for prop: Dictionary in o.get_property_list():
		if int(prop["usage"]) & PROPERTY_USAGE_SCRIPT_VARIABLE and not String(prop["name"]) in ECON_SKIP:
			names.append(String(prop["name"]))
	return names


## oracle_dump_econ.gd's _fields
func _econ_fields(e: RefCounted) -> Dictionary:
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
		var wv: Variant = e.world.get(n)
		if n == "records":
			var rs: Array = []
			for r: Array in wv:
				rs.append(r.slice(0, 7))
			wv = rs
		elif n == "transfers":
			var ts: Array = []
			for t: Array in wv:
				ts.append(t.slice(0, 4))
			wv = ts
		f["world." + n] = wv
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


## oracle_dump.gd's persons names (PERSONS_PORT_PLAN §2) and the month's records as "rec." fields
func _persons_names(p: RefCounted) -> Array:
	var names: Array = []
	for row: Array in p.fields():
		names.append(String(row[0]))
	for n: String in ["n", "month", "price_index", "wage_index", "food_plan_start", "pref_pop", "pension", "groups"]:
		names.append(n)
	names.sort()
	return names


func _persons_fields(p: RefCounted) -> Dictionary:
	var f := {}
	if p == null:
		return f
	for n: String in _persons_names(p):
		f[n] = p.get(n)
	for n2: String in ["decisions", "refusals", "events", "trace", "group_log"]:
		f["rec." + n2] = p.get(n2)
	return f


func _persons_tree(p: RefCounted) -> Dictionary:
	var f: Dictionary = _persons_fields(p)
	if p != null:
		for n: String in ["pref_codes", "base_year", "seed_v", "spec"]:
			f[n] = p.get(n)
	return f


func _hash(v: Variant) -> String:
	var h := HashingContext.new()
	h.start(HashingContext.HASH_SHA256)
	_canon(h, v)
	return h.finish().hex_encode()


## oracle_dump.gd's typed tree
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
	push_error("oracle_dump_month: an unencoded type %d at %s" % [typeof(v), path])
	return {"x": typeof(v)}


## oracle_dump.gd's _canon bytes
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
			push_error("oracle_dump_month: no canonical form for type %d" % typeof(v))
