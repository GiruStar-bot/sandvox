extends "res://tools/test/test_kit.gd"
## ISS tiered population T2.2, T2s-f (ISS_CHECKS.md; §14.6): the national tiers, seed 1.
##   godot --headless --path . --script res://sim/modern/test_modern_t2_restore.gd
## T2s-f  the same seed twice gives the same digest at month 12; a state saved at month 12 and restored continues to month 14 at the
##        uninterrupted run's digest; tiers off leaves every digest unchanged (test_modern_tiers' T1s-f, the month's call behind the flag)
const PEOPLE = preload("res://sim/modern/people/people.gd")
const MS = preload("res://sim/modern/modern_status.gd")
const CANON = preload("res://sim/modern/canon.gd")
const ENV := {"inflation_month": 0.02 / 12.0, "food_price_yoy": 0.0, "unemployment_rate": 0.025, "levers": []}


func _run(st: RefCounted, prefs: Dictionary, months: int) -> RefCounted:
	var p = PEOPLE.new()
	p.tiers = true
	p.create("JPN", 1, st.cohort["JPN"], st.qx["JPN"], prefs, 0, 2024)
	for m: int in months:
		p.step(ENV)
	return p


func _init() -> void:
	var st = MS.new()
	st.load(2024, ["JPN"])
	var prefs: Dictionary = CANON.load_json("res://data/modern/polity/jpn_prefectures.json")["prefectures"]
	var a = _run(st, prefs, 12)
	var d12: String = a.digest()
	var saved: Dictionary = a.to_dict()
	a.step(ENV)
	a.step(ENV)
	var d14: String = a.digest()
	a = null
	var b = PEOPLE.new()
	b.from_dict(saved)
	saved = {}
	var r12: String = b.digest()
	b.step(ENV)
	b.step(ENV)
	var r14: String = b.digest()
	b = null
	var c = _run(st, prefs, 12)
	var c12: String = c.digest()
	check(c12 == d12, "T2s-f the same seed twice at month 12: %s and %s" % [d12.left(8), c12.left(8)])
	check(r12 == d12 and r14 == d14, "T2s-f restored at month 12 (%s, uninterrupted %s) continues to month 14 at %s (uninterrupted %s)" % [r12.left(8), d12.left(8), r14.left(8), d14.left(8)])
	finish()
