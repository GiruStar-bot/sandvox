extends "res://tools/test/test_kit.gd"
## ISS tiered population T2.2, T2s-f (ISS_CHECKS.md; §14.6): the national tiers, seed 1.
##   godot --headless --path . --script res://sim/modern/test_modern_t2_restore.gd
## T2s-f  the same seed twice gives the same digest at month 12; a state saved at month 12 and restored continues to month 14 at the
##        uninterrupted run's digest; tiers off leaves every digest unchanged (test_modern_tiers' T1s-f, the month's call behind the flag)
## T2s-f AMENDED (2026-11-05, the 15 GB box; not after a fail of the row, which was never read: the run was killed at 13.5 GB): one
##        national state at a time, and every digest by parts (tools/test/stream_digest.gd). The uninterrupted run to month 14 is the
##        second run of the same seed, so the save, the restore and the two runs never live together
## T2s-fs the digest by parts equals people.gd's digest() on runs small enough to hold both: a persons run with tiers off (n 20 per
##        prefecture) at months 0 and 2, and a value with every type numeric_only keeps or drops, nested; must-fail: the parts with the
##        keys reversed differ
const PEOPLE = preload("res://sim/modern/people/people.gd")
const MS = preload("res://sim/modern/modern_status.gd")
const CANON = preload("res://sim/modern/canon.gd")
const SD = preload("res://tools/test/stream_digest.gd")
const ENV := {"inflation_month": 0.02 / 12.0, "food_price_yoy": 0.0, "unemployment_rate": 0.025, "levers": []}


func _run(st: RefCounted, prefs: Dictionary, months: int) -> RefCounted:
	var p = PEOPLE.new()
	p.tiers = true
	p.create("JPN", 1, st.cohort["JPN"], st.qx["JPN"], prefs, 0, 2024)
	for m: int in months:
		p.step(ENV)
	return p


func _whole(v: Variant) -> String:
	var ctx := HashingContext.new()
	ctx.start(HashingContext.HASH_SHA256)
	ctx.update(var_to_bytes(CANON.numeric_only(v)))
	return ctx.finish().hex_encode()


func _init() -> void:
	var st = MS.new()
	st.load(2024, ["JPN"])
	var prefs: Dictionary = CANON.load_json("res://data/modern/polity/jpn_prefectures.json")["prefectures"]
	var s = PEOPLE.new()
	s.create("JPN", 1, st.cohort["JPN"], st.qx["JPN"], prefs, 20, 2024)
	var small_ok: bool = SD.digest(s) == s.digest()
	s.step(ENV)
	s.step(ENV)
	small_ok = small_ok and SD.digest(s) == s.digest()
	s = null
	var mixed := {"b": [1, 2.5, "drop", true, {"z": PackedInt64Array([1 << 40]), "y": PackedInt32Array([7]), 3: "x", "w": [PackedFloat64Array([0.1])]}],
		"a": 1 << 40, "c": "dropped", "d": {}, "e": PackedByteArray([1, 2]), "f": PackedStringArray(["s"]), "g": {"n": {"m": [[], {}]}}}
	var mixed_ok: bool = SD.of_value(mixed.duplicate(true)) == _whole(mixed)
	var mf_differs: bool = SD.of_value(mixed.duplicate(true), true) != _whole(mixed)
	check(small_ok and mixed_ok and mf_differs, "T2s-fs the digest by parts equals digest(): tiers-off persons run at months 0 and 2 %s; every numeric_only type, nested %s; must-fail (keys reversed) differs %s" % [small_ok, mixed_ok, mf_differs])
	var a = _run(st, prefs, 12)
	var d12: String = SD.digest(a)
	var saved: Dictionary = a.to_dict()
	a = null
	var b = PEOPLE.new()
	b.from_dict(saved)
	saved = {}
	var r12: String = SD.digest(b)
	b.step(ENV)
	b.step(ENV)
	var r14: String = SD.digest(b)
	b = null
	var c = _run(st, prefs, 12)
	var c12: String = SD.digest(c)
	c.step(ENV)
	c.step(ENV)
	var d14: String = SD.digest(c)
	c = null
	check(c12 == d12, "T2s-f the same seed twice at month 12: %s and %s" % [d12.left(8), c12.left(8)])
	check(r12 == d12 and r14 == d14, "T2s-f restored at month 12 (%s, uninterrupted %s) continues to month 14 at %s (uninterrupted %s)" % [r12.left(8), d12.left(8), r14.left(8), d14.left(8)])
	finish()
