extends SceneTree
## The oracle's side of the persons layer's sample start (py/people/layer.py, row L): people.create's sample path (tiers off,
## households off) at a test size, then people.step with the env the integrated month passes, writing at month 0 and after each month
## the persons' per-field hashes (oracle_dump.gd's _write_persons rows and its "rec." records), supply() and summary() as typed trees
## and their hashes, and at the end to_dict()'s hash, per key and whole.
##   SAMPLE_OUT=outputs/py_oracle/ps/s1_n20 SAMPLE_SEED=1 SAMPLE_NPER=20 SAMPLE_MONTHS=13 \
##     godot --headless --path . --script res://tools/py/persons_sample_dump.gd
## Why supply() after the month's hashes and before the next step: the integrated month calls it before people.step, and its first
## call sets food_plan_start, so mNN's hashes read the state the next month's supply sees
## SAMPLE_HOUSEHOLDS=1 (P-b, PERSONS_PORT_PLAN §9) sets people.households before create, and each month also writes every
## household_fields() row as "hh.<variable>", the registry itself (its keys, kinds, strides and digest flags) as "hh_fields", and the
## households' state outside the registry that the next month reads or the save holds as "hhx.<variable>"; at the end each key of
## to_dict()'s "households" as "to_dict.households.<key>"
const PEOPLE = preload("res://sim/modern/people/people.gd")
const MS = preload("res://sim/modern/modern_status.gd")
const CANON = preload("res://sim/modern/canon.gd")
const SUMMARY_CODE := 13


func _init() -> void:
	var out: String = OS.get_environment("SAMPLE_OUT")
	var seed: int = int(OS.get_environment("SAMPLE_SEED")) if OS.get_environment("SAMPLE_SEED") != "" else 1
	var n_per: int = int(OS.get_environment("SAMPLE_NPER")) if OS.get_environment("SAMPLE_NPER") != "" else 20
	var months: int = int(OS.get_environment("SAMPLE_MONTHS")) if OS.get_environment("SAMPLE_MONTHS") != "" else 13
	var hh_on: bool = OS.get_environment("SAMPLE_HOUSEHOLDS") == "1"
	DirAccess.make_dir_recursive_absolute(out)
	var st = MS.new()
	st.load(2024, ["JPN"])
	var prefs: Dictionary = CANON.load_json("res://data/modern/polity/jpn_prefectures.json")["prefectures"]
	var p = PEOPLE.new()
	p.tiers = false
	p.households = hh_on
	var err: String = p.create("JPN", seed, st.cohort["JPN"], st.qx["JPN"], prefs, n_per, 2024)
	if err != "":
		push_error("persons_sample_dump: create: " + err)
		quit(1)
		return
	print("SAMPLE start n %d seed %d n_per %d households %s" % [p.n, seed, n_per, str(hh_on)])
	_write_month(p, out, "m00")
	var env := {"inflation_month": 0.02 / 12.0, "food_price_yoy": 0.0, "unemployment_rate": 0.025, "wage_index": 1.0, "levers": [], "cohort": st.cohort["JPN"]}
	for m: int in range(1, months + 1):
		p.step(env)
		_write_month(p, out, "m%02d" % m)
		print("SAMPLE month %d" % m)
	var d: Dictionary = p.to_dict()
	var lines := ""
	var ks: Array = d.keys()
	ks.sort()
	for k: String in ks:
		lines += "to_dict.%s %s\n" % [k, _sha(d[k])]
	lines += "to_dict %s\n" % _sha(d)
	if d.has("households"):
		var hd: Dictionary = d["households"]
		var hk: Array = hd.keys()
		hk.sort()
		for k2: String in hk:
			lines += "to_dict.households.%s %s\n" % [k2, _sha(hd[k2])]
	var f := FileAccess.open("%s/m%02d.to_dict.sha.txt" % [out, months], FileAccess.WRITE)
	f.store_string(lines)
	f.close()
	var fj := FileAccess.open("%s/m%02d.to_dict.json" % [out, months], FileAccess.WRITE)
	fj.store_string(JSON.stringify(_enc(d), "", false))
	fj.close()
	var fr := FileAccess.open(out + "/READY", FileAccess.WRITE)
	fr.store_string("%d %d %d\n" % [seed, n_per, months])
	fr.close()
	quit(0)


func _sha(v: Variant) -> String:
	var h := HashingContext.new()
	h.start(HashingContext.HASH_SHA256)
	_canon(h, v)
	return h.finish().hex_encode()


func _write_month(p: RefCounted, out: String, tag: String) -> void:
	var lines := ""
	var nonfinite := ""
	for n: String in _persons_names(p):
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
	if p.households:
		lines += "hh_fields %s\n" % _sha(p.household_fields())
		for row: Array in p.household_fields():
			var hn: String = String(row[0])
			var hv: Variant = p.get(hn)
			lines += "hh.%s %s\n" % [hn, _sha(hv)]
			if hv is PackedFloat64Array:
				var ha: PackedFloat64Array = hv
				for i2: int in ha.size():
					if not is_finite(ha[i2]):
						nonfinite += "hh.%s %d %x\n" % [hn, i2, PackedFloat64Array([ha[i2]]).to_byte_array().decode_u64(0)]
		for xn: String in ["hh_n", "hh_members", "next_k", "life_log", "lc_births", "lc_dying", "lc_t22b", "lc_c_band"]:
			lines += "hhx.%s %s\n" % [xn, _sha(p.get(xn))]
	var sup: Dictionary = p.supply()
	var sm: Dictionary = p.summary()
	var smc: Dictionary = p.summary(SUMMARY_CODE)
	lines += "iface.supply %s\n" % _sha(sup)
	lines += "iface.summary %s\n" % _sha(sm)
	lines += "iface.summary_%d %s\n" % [SUMMARY_CODE, _sha(smc)]
	var f := FileAccess.open("%s/%s.persons.sha.txt" % [out, tag], FileAccess.WRITE)
	f.store_string(lines)
	f.close()
	var f2 := FileAccess.open("%s/%s.persons.nonfinite.txt" % [out, tag], FileAccess.WRITE)
	f2.store_string(nonfinite)
	f2.close()
	var f3 := FileAccess.open("%s/%s.iface.json" % [out, tag], FileAccess.WRITE)
	f3.store_string(JSON.stringify(_enc({"supply": sup, "summary": sm, "summary_%d" % SUMMARY_CODE: smc}), "", false))
	f3.close()


## oracle_dump.gd's _persons_names
func _persons_names(p: RefCounted) -> Array:
	var names: Array = []
	for row: Array in p.fields():
		names.append(String(row[0]))
	for n: String in ["n", "month", "price_index", "wage_index", "food_plan_start", "pref_pop", "pension", "groups"]:
		names.append(n)
	names.sort()
	return names


## oracle_dump.gd's typed tree, with packed arrays always inline (hex): the sample's arrays are small
func _enc(v: Variant) -> Variant:
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
				a.append(_enc(v[i]))
			return {"a": a}
		TYPE_DICTIONARY:
			var d: Array = []
			for k in v:
				d.append([_enc(k), _enc(v[k])])
			return {"d": d}
		TYPE_PACKED_STRING_ARRAY:
			return {"p": "str", "v": Array(v)}
		TYPE_PACKED_INT64_ARRAY, TYPE_PACKED_INT32_ARRAY, TYPE_PACKED_FLOAT64_ARRAY, TYPE_PACKED_FLOAT32_ARRAY, TYPE_PACKED_BYTE_ARRAY:
			var kind: String = {TYPE_PACKED_INT64_ARRAY: "i64", TYPE_PACKED_INT32_ARRAY: "i32", TYPE_PACKED_FLOAT64_ARRAY: "f64",
				TYPE_PACKED_FLOAT32_ARRAY: "f32", TYPE_PACKED_BYTE_ARRAY: "u8"}[typeof(v)]
			var b: PackedByteArray = v.to_byte_array() if kind != "u8" else v
			return {"p": kind, "hex": b.hex_encode()}
	push_error("persons_sample_dump: an unencoded type %d" % typeof(v))
	return {"x": typeof(v)}


## oracle_dump.gd's _canon
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
			# Why the guard: HashingContext.update refuses an empty buffer (an empty household, no deaths this month); no bytes either way
			if (v as Variant).size() > 0:
				h.update(v.to_byte_array() if typeof(v) != TYPE_PACKED_BYTE_ARRAY else v)
		_:
			push_error("persons_sample_dump: no canonical form for type %d" % typeof(v))
