extends SceneTree
## Row G-sort's oracle side (START_PORT_PLAN §2): Array.sort() and sort_custom() on inputs with ties, written with each element's
## original index, so py/tests/test_gdsort.py can check that core/gdsort.py gives Godot's order, ties included.
##   GDSORT_OUT=outputs/py_oracle/gdsort.json godot --headless --path . --script res://tools/py/gdsort_dump.gd
## Why an LCG and not KEYED: the inputs only need to be the same on both sides, and an LCG is three lines in each language

var _s: int = 12345


func _r(n: int) -> int:
	_s = (_s * 6364136223846793005 + 1442695040888963407) & 0x7FFFFFFFFFFFFFFF
	return (_s >> 17) % n


func _init() -> void:
	var cases: Array = []
	var sizes: Array = [0, 1, 2, 3, 15, 16, 17, 31, 33, 64, 100, 257, 1000, 5000]
	for c: int in 40:
		var n: int = sizes[c % sizes.size()]
		var span: int = [2, 5, 50, 1000000][c % 4]
		var rows: Array = []
		for i: int in n:
			rows.append([_r(span), i])
		var a: Array = rows.duplicate(true)
		a.sort_custom(func(x: Array, y: Array) -> bool: return x[0] < y[0])
		var out: Array = []
		for x: Array in a:
			out.append(x[1])
		cases.append({"kind": "custom", "in": rows, "out": out})
	for c2: int in 30:
		var n2: int = sizes[c2 % sizes.size()]
		var vals: Array = []
		for i2: int in n2:
			var t: int = _r(6)
			if t == 0:
				vals.append(_r(20))
			elif t == 1:
				vals.append(float(_r(40)) / 2.0)
			elif t == 2:
				vals.append([_r(3), _r(3)])
			elif t == 3:
				vals.append([_r(3), float(_r(6)) / 2.0, _r(2)])
			elif t == 4:
				vals.append("k%d" % _r(30))
			else:
				vals.append([_r(2)])
		var b: Array = vals.duplicate(true)
		b.sort()
		cases.append({"kind": "default", "in": vals, "out": b})
	for c3: int in 10:
		var n3: int = sizes[(c3 * 3) % sizes.size()]
		var ss: Array = []
		for i3: int in n3:
			ss.append("%02d|%d|%s" % [_r(50), _r(3), ["a", "b", "é", "日"][_r(4)]])
		var d: Array = ss.duplicate()
		d.sort()
		cases.append({"kind": "default", "in": ss, "out": d})
	var f := FileAccess.open(OS.get_environment("GDSORT_OUT"), FileAccess.WRITE)
	f.store_string(JSON.stringify(_enc(cases), "", false))
	f.close()
	print("GDSORT cases %d" % cases.size())
	quit(0)


func _enc(v: Variant) -> Variant:
	match typeof(v):
		TYPE_INT:
			return {"i": str(v)}
		TYPE_FLOAT:
			return {"f": str(PackedFloat64Array([v]).to_byte_array().decode_s64(0))}
		TYPE_STRING:
			return {"s": v}
		TYPE_ARRAY:
			var a: Array = []
			for x in v:
				a.append(_enc(x))
			return {"a": a}
		TYPE_DICTIONARY:
			var d: Array = []
			for k in v:
				d.append([_enc(k), _enc(v[k])])
			return {"d": d}
	return null
