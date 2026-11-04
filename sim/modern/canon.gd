extends RefCounted
## Canonical floats for cross-machine runs (V082): Godot's JSON parser can differ by one ulp between builds, and "%.0f" rounds ties
## differently, so (1) every float read from a data file is snapped to nine decimals through integer arithmetic, and (2) digests are taken
## over numeric state only, never over formatted strings. The snap is stable only if no number sits on the nine-decimal tie (ten decimals
## ending in 5): regions.json had 276 (V089) and is written at its canonical values (tools/modern/canon_json_file.py); test_modern_data D8
## checks every float of data/modern against its two neighbouring doubles.
## canon(v) walks a parsed JSON value and snaps every float; canon_f snaps one.
static func canon_f(x: float) -> float:
	if not is_finite(x):
		return x
	if absf(x) >= 1e7:
		return floor(x + 0.5) if absf(x - floor(x + 0.5)) < 1e-3 else x
	return floor(x * 1e9 + 0.5) / 1e9


static func canon(v: Variant) -> Variant:
	if v is float:
		return canon_f(v)
	if v is Dictionary:
		var d: Dictionary = v
		for k: Variant in d.keys():
			d[k] = canon(d[k])
		return d
	if v is Array:
		var a: Array = v
		for i: int in a.size():
			a[i] = canon(a[i])
		return a
	return v


## Parse a JSON file and snap its floats
static func load_json(path: String) -> Variant:
	var v: Variant = JSON.parse_string(FileAccess.get_file_as_string(path))
	return canon(v)


## The M-stage data (stats, entities, compute chain, R56-R58, views, visibility): as canon(), and a float of 1e7 or more is rounded to
## the nearest whole unit. Why not canon_f alone: it leaves a large non-integer as parsed (GDP in US$ such as 4384854269961.9277), and
## Godot's parse differs by one ulp between builds there (V084: 540 of 27,026 numbers in stats.json), which reached the field's link_cap
static func canon_m(v: Variant) -> Variant:
	if v is float:
		var x: float = v
		return floor(x + 0.5) if is_finite(x) and absf(x) >= 1e7 else canon_f(x)
	if v is Dictionary:
		var d: Dictionary = v
		for k: Variant in d.keys():
			d[k] = canon_m(d[k])
		return d
	if v is Array:
		var a: Array = v
		for i: int in a.size():
			a[i] = canon_m(a[i])
		return a
	return v


static func load_json_m(path: String) -> Variant:
	return canon_m(JSON.parse_string(FileAccess.get_file_as_string(path)))


## A digest over numeric state only: strings are dropped, so a formatted number in a reason text cannot move it
static func numeric_only(v: Variant) -> Variant:
	if v is Dictionary:
		var out: Dictionary = {}
		var d: Dictionary = v
		var ks: Array = d.keys()
		ks.sort_custom(func(a: Variant, b: Variant) -> bool: return str(a) < str(b))
		for k: Variant in ks:
			var c: Variant = numeric_only(d[k])
			if c != null:
				out[str(k)] = c
		return out
	if v is Array:
		var oa: Array = []
		for e: Variant in v:
			var c: Variant = numeric_only(e)
			if c != null:
				oa.append(c)
		return oa
	if v is float or v is int or v is bool or v is PackedFloat64Array or v is PackedInt32Array or v is PackedByteArray:
		return v
	return null
