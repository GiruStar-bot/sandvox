extends SceneTree
## Per-component hashes of the modern world's state for cross-machine diffing (V083): the world of 2024 with a fixed salt, advanced to
## days 0, 31 and 365; each top-level key of to_dict() and each part of the field, status, actors and register hashed on its own
## (12 hex of sha256(var_to_bytes(numeric_only(x)))). The first differing key between two machines localises the cause.
##   godot --headless --path . --script res://tools/modern/hash_parts.gd
const MW = preload("res://sim/modern/modern_world.gd")
const CANON = preload("res://sim/modern/canon.gd")


func h(x: Variant) -> String:
	var ctx := HashingContext.new()
	ctx.start(HashingContext.HASH_SHA256)
	ctx.update(var_to_bytes(CANON.numeric_only(x)))
	return ctx.finish().hex_encode().substr(0, 12)


func parts(label: String, d: Dictionary) -> void:
	var out: PackedStringArray = PackedStringArray([label + ":"])
	for k: String in d:
		out.append("%s %s" % [k, h(d[k])])
	print(" ".join(out))


func _init() -> void:
	var w = MW.new()
	w.create(2024, {"view_salt": "0123456789abcdef0123456789abcdef"})
	for day: int in [0, 31, 365]:
		w.advance_to(day)
		var st: Dictionary = w.to_dict()
		parts("day %d" % day, st)
		parts("  field parts", st["field"])
		parts("  status parts", st["status"])
		parts("  actors parts", st["actors"])
		parts("  register parts", st["register"])
	print("DIGEST 365 ", w.digest())
	quit(0)
