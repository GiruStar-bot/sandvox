extends "res://tools/test/test_kit.gd"
## The modern world's determinism (MODERN_PLAN 3; sim/modern/modern_world.gd).
##   godot --headless --path . --script res://sim/modern/test_modern_world.gd
## W1 two worlds made alike give the same digest after 400 days (with growth, so the rule actors build)
## W2 a world saved and restored at day 40, 365 or 400 (through bytes, as a keyframe file) reaches day 430 with the straight run's digest
## W3 the digest moves when the state does (a different compute growth, or one licence closed)
const MW = preload("res://sim/modern/modern_world.gd")
const P := {"compute_growth": 0.15}


func _world(p: Dictionary = P) -> RefCounted:
	var w = MW.new()
	w.create(2022, p)
	return w


func _init() -> void:
	var a = _world()
	var b = _world()
	a.advance_to(400)
	b.advance_to(400)
	check(a.digest() == b.digest() and a.field.projects.size() > 0, "W1 day 400: %s and %s; %d projects open" % [a.digest().left(16), b.digest().left(16),
		a.field.projects.size()])
	var straight = _world()
	straight.advance_to(430)
	var want: String = straight.digest()
	var same: Array = []
	for stop: int in [40, 365, 400]:
		var r = _world()
		r.advance_to(stop)
		var r2 = MW.from_dict(bytes_to_var(var_to_bytes(r.to_dict())))
		r2.advance_to(430)
		same.append(r2.digest() == want)
	check(same == [true, true, true], "W2 resumed at 40 / 365 / 400 equal the straight run at 430: %s (%s)" % [str(same), want.left(16)])
	var c = _world({"compute_growth": 0.14})
	c.advance_to(430)
	var d = _world()
	d.advance_to(40)
	d.field.chain.set_licence(d.data.index_of("USA"), "chips", d.data.index_of("CHN"), false)
	d.advance_to(430)
	check(c.digest() != want and d.digest() != want, "W3 growth 0.14 and one closed licence each move the digest")
	finish()
