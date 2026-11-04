extends "res://tools/test/test_kit.gd"
## ISS tiered population, T2s-fr AMENDED (2) (ISS_CHECKS.md, declared at b5319afc, amended at 60434c3b and b40a3ff1; TO_E 07:17, 08:20): the tiers on
## Tokyo (13) and Okinawa (47), seed 1.
##   godot --headless --path . --script res://sim/modern/test_modern_t2_resume.gd
## T2s-fr  saved at month 6 and restored into a new body, months 7-13 equal the straight run's in the digest and in the full tiers
##         state (every tr_* field but tr_spec, each value canonicalised with its type tag, dictionaries in sorted key order); must-fail:
##         the save without its "exact" block (the save before the fix) differs at month 7
## (2): the state hash leaves out tr_margins["t22"]["usec"] and ["usec_by_step"] (wall-clock time); the control: two straight runs hash
##         equal at month 7 with that exclusion and unequal without it
const PEOPLE = preload("res://sim/modern/people/people.gd")
const MS = preload("res://sim/modern/modern_status.gd")
const CANON = preload("res://sim/modern/canon.gd")
const ENV := {"inflation_month": 0.02 / 12.0, "food_price_yoy": 0.0, "unemployment_rate": 0.025, "levers": []}
const SAVE_AT := 6
const LAST := 13


func _init() -> void:
	var st = MS.new()
	st.load(2024, ["JPN"])
	var all: Dictionary = CANON.load_json("res://data/modern/polity/jpn_prefectures.json")["prefectures"]
	# Why not every prefecture (the first form): the national body and its month-6 save reached 13.8-13.9 GB and were killed twice;
	# the national resume is Cpくん's oracle check at b316b6e8 (TO_PM_PY 995bf630)
	var prefs: Dictionary = {"13": all["13"], "47": all["47"]}
	var a = PEOPLE.new()
	a.tiers = true
	a.create("JPN", 1, st.cohort["JPN"], st.qx["JPN"], prefs, 0, 2024)
	var names: Array = _tier_fields(a)
	var straight: Dictionary = {}
	var saved: Dictionary = {}
	for m: int in LAST:
		a.step(ENV)
		if m + 1 == SAVE_AT:
			saved = a.to_dict()
		if m + 1 > SAVE_AT:
			straight[m + 1] = [a.digest(), _state_hash(a, names)]
	a = null
	var b = PEOPLE.new()
	b.from_dict(saved)
	var off: Array = []
	for m2: int in range(SAVE_AT + 1, LAST + 1):
		b.step(ENV)
		var got: Array = [b.digest(), _state_hash(b, names)]
		if got[0] != straight[m2][0] or got[1] != straight[m2][1]:
			off.append("month %d: digest %s / %s, state %s / %s" % [m2, String(got[0]).left(8), String(straight[m2][0]).left(8), String(got[1]).left(8), String(straight[m2][1]).left(8)])
	b = null
	check(off.is_empty(), "T2s-fr AMENDED (2) (Tokyo + Okinawa; the wall-clock tallies left out) saved at month %d, restored, months %d-%d equal the straight run's digest and full tiers state (%d fields): %s" % [SAVE_AT, SAVE_AT + 1, LAST, names.size(), "all equal" if off.is_empty() else "; ".join(off)])
	var old: Dictionary = saved.duplicate()
	var td: Dictionary = (saved["tiers"] as Dictionary).duplicate()
	td.erase("exact")
	old["tiers"] = td
	saved = {}
	var c = PEOPLE.new()
	c.from_dict(old)
	c.step(ENV)
	var c7: String = _state_hash(c, names)
	check(c7 != straight[SAVE_AT + 1][1], "T2s-fr AMENDED must-fail: the save without its exact block (before the fix) differs in the full tiers state at month %d: %s against %s" % [SAVE_AT + 1, c7.left(8), String(straight[SAVE_AT + 1][1]).left(8)])
	c = null
	var h: Array = []
	for r: int in 2:
		var x = PEOPLE.new()
		x.tiers = true
		x.create("JPN", 1, st.cohort["JPN"], st.qx["JPN"], prefs, 0, 2024)
		for m3: int in SAVE_AT + 1:
			x.step(ENV)
		h.append([_state_hash(x, names), _state_hash(x, names, true)])
		x = null
	check(h[0][0] == h[1][0] and h[0][1] != h[1][1], "T2s-fr AMENDED (2) control: two straight runs at month %d hash %s / %s with the wall-clock tallies left out (equal) and %s / %s with them (unequal)" % [SAVE_AT + 1, String(h[0][0]).left(8), String(h[1][0]).left(8), String(h[0][1]).left(8), String(h[1][1]).left(8)])
	finish()


## Every tr_* property but tr_spec (reloaded from its file), in name order
static func _tier_fields(p: Object) -> Array:
	var out: Array = []
	for pr: Dictionary in p.get_property_list():
		var nm: String = String(pr["name"])
		if nm.begins_with("tr_") and nm != "tr_spec":
			out.append(nm)
	out.sort()
	return out


## Why not one buffer of every field (the first run): with the straight body and its month-6 save held, the whole state's bytes at once
## took the process to 13.9 GB and it was killed; field by field, only one field's bytes are held at a time
func _state_hash(p: Object, names: Array, timed: bool = false) -> String:
	var ctx := HashingContext.new()
	ctx.start(HashingContext.HASH_SHA256)
	for nm: String in names:
		var v: Variant = p.get(nm)
		if nm == "tr_margins" and not timed and (v as Dictionary).has("t22"):
			v = (v as Dictionary).duplicate()
			var t22: Dictionary = (v["t22"] as Dictionary).duplicate()
			t22.erase("usec")
			t22.erase("usec_by_step")
			v["t22"] = t22
		ctx.update(var_to_bytes([nm, _canon(v)]))
	return ctx.finish().hex_encode()


## A value with its type tag at every level, dictionaries as [key, value] pairs in sorted key order
## Why not var_to_bytes of the value alone: a dictionary's bytes follow its insertion order, which a restore may rebuild differently
## without any field changing
func _canon(v: Variant) -> Variant:
	if typeof(v) == TYPE_DICTIONARY:
		var pairs: Array = []
		for k in (v as Dictionary):
			pairs.append([var_to_str(k), k])
		pairs.sort_custom(func(x: Array, y: Array) -> bool: return String(x[0]) < String(y[0]))
		var out: Array = []
		for pr: Array in pairs:
			out.append([_canon(pr[1]), _canon(v[pr[1]])])
		return [TYPE_DICTIONARY, out]
	if typeof(v) == TYPE_ARRAY:
		var out2: Array = []
		for e in (v as Array):
			out2.append(_canon(e))
		return [TYPE_ARRAY, out2]
	return [typeof(v), v]
