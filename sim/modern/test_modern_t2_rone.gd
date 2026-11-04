extends "res://tools/test/test_kit.gd"
## ISS tiered population T2.R, R-one (ISS_TIERED_POPULATION.md §14.1; ISS_CHECKS.md R-one, AMENDED V109 TO_E 04:25, 9bcf370e, and V110
## TO_E 06:32, 7fd0e864): one rate
## function per rule, read from the call sites and from a run. The list below is the code-level list V reads.
##   godot --headless --path . --script res://sim/modern/test_modern_t2_rone.gd
## R-one (a)  every rule draw of the month's rules goes through people.below(tag, i, b, c, operand), the tag listed, its operand (the last
##        argument) exactly the listed rate function's call or a local assigned exactly from it and not reassigned before the draw; the
##        law rows draw through their law function; no listed tag is drawn by a bare u()
## R-one (a′) a households-on society of 2 x 400 run month by month with the record on until every listed tag has drawn, at most 60
##        months: no listed tag without a draw, and every draw's operand equals in bits the latest output of its listed rate function
## R-one (a″) each of V109's inline finding rate and V110's M1 (h_retire(p) * 0.9) and M2 (h_regrade(p) + 0.002), applied to the text,
##        fails (a) on its own tag (rows that must fail)
## R-one (b)  each listed rate function exists and writes nothing: no assignment to p.<field>, no mutating call on anything but a local
## R-one (d)  (V112) below() itself: on a grid of h around each keyed u (0, 1, u, the floats next to u, quarters) it returns exactly u < h;
##        (d′) V112's M4, its comparison changed to x < h * 0.999 and compiled at run time, fails (d). R-one's blind spot (a rate called on
##        the wrong state, V112's M5) is T2s-dgq's must-fail row at T2.2
## R-one (c)  a person and a point with the same state give equal bits: PENDING until the points (T2.4), a report line
const PEOPLE = preload("res://sim/modern/people/people.gd")
const MS = preload("res://sim/modern/modern_status.gd")
const FILES := ["res://sim/modern/econ/labour.gd", "res://sim/modern/people/life_course.gd", "res://sim/modern/people/actions.gd",
	"res://sim/modern/people/people.gd"]
## [the draw's tag, the file, the rate function the draw compares against]
const RULES := [
	["sep", "labour.gd", "rates"], ["find", "labour.gd", "rates"], ["change", "labour.gd", "rates"],
	["toregular", "labour.gd", "h_to_regular"], ["nonreg2", "people.gd", "h_nonregular"],
	["death", "life_course.gd", "h_death"], ["death", "people.gd", "h_death_off"], ["retire", "life_course.gd", "h_retire"],
	["lc_intend", "life_course.gd", "h_intend"], ["lc_reintend", "life_course.gd", "h_intend"],
	["lc_inst", "life_course.gd", "h_institution"], ["lc_movein", "life_course.gd", "h_move_in"],
	["lc_divorce", "life_course.gd", "h_divorce"], ["lc_custody", "life_course.gd", "h_custody"], ["lc_birth", "life_course.gd", "h_birth"],
	["lc_leave", "life_course.gd", "h_leave"], ["lc_partner", "life_course.gd", "h_look"], ["lc_accept", "life_course.gd", "h_accept"],
	["lc_agree", "life_course.gd", "h_accept"], ["lc_econ", "life_course.gd", "h_carry"]]
## The categorical laws, drawn by inversion against the law function's output: [tag, file, law function]
const LAWS := [["lc_kids", "life_course.gd", "law_kids"], ["choose", "actions.gd", "action_law"], ["t22b_grade", "life_course.gd", "grade_flows"]]
## The construction's draws (the start, T1's), outside the month's rules (§14.1 names the month's)
const START := ["evermar0", "parity0", "grade0", "grade_class0"]
## people.gd's functions that hold month rules; the rest draw the persons' attributes at creation and rebirth
const PEOPLE_SCOPE := ["_year", "labour_from_rates"]
const MUTATORS := ["append", "append_array", "push_back", "push_front", "erase", "remove_at", "clear", "resize", "fill", "sort",
	"sort_custom", "insert", "merge"]
## The must-fail mutations, on the text as it stands now: [name, file, from, to, the tag (a) must flag]. V109's (verify-reports
## b7c7644a §7) and V110's M1, M2 (04761d21 §3)
const MUTS := [
	["V109 inline finding rate", "labour.gd", 'elif h[1] > 0.0 and p.below("find", i, m, 0, h[1]):',
		'elif p.employment[i] == p.EMP_UNEMPLOYED and p.below("find", i, m, 0, f * (p.ACT.SEARCH_BOOST if p.search[i] == 1 else p.ACT.NO_SEARCH)):', "find"],
	["V110 M1", "life_course.gd", 'p.below("retire", i, p.month, 0, h_retire(p))', 'p.below("retire", i, p.month, 0, h_retire(p) * 0.9)', "retire"],
	["T2.2b's law link (§14.6 (8); V110 M2 retired with the redraw)", "life_course.gd", "		var out: Array = grade_flows(p, n8, pi0)", "		var out: Array = [PackedFloat64Array(), 0.0]", "t22b_grade"]]
const RUN_MONTHS := 60
const UNIT_TAGS := ["sep", "death", "lc_divorce", "retire"]


func _init() -> void:
	var texts: Dictionary = {}
	for path: String in FILES:
		texts[path.get_file()] = FileAccess.get_file_as_string(path)
	var bad: Array = _static(texts)
	check(bad.is_empty(), "R-one (a) every rule draw goes through below() against its listed rate function (%d rules, %d laws): %s" % [RULES.size(), LAWS.size(), str(bad)])
	for mu: Array in MUTS:
		var mut: Dictionary = texts.duplicate()
		var applied: bool = String(mut[mu[1]]).count(String(mu[2])) == 1
		mut[mu[1]] = String(mut[mu[1]]).replace(String(mu[2]), String(mu[3]))
		var bad_m: Array = _static(mut)
		var hit: bool = false
		for b2: String in bad_m:
			hit = hit or (b2.begins_with("%s:%s " % [mu[1], mu[4]]) and not bad.has(b2))
		check(applied and hit, "R-one (a″) %s fails (a) on the %s draw (applied once %s): %s" % [mu[0], mu[4], str(applied), str(bad_m)])
	var soc = _runtime()
	_pure(texts)
	_below_unit(soc, String(texts["people.gd"]))
	print("REPORT R-one (c) a person and a point with the same state give equal bits: PENDING until the points (T2.4)")
	finish()


## The functions of a source text: name -> [lines]
func _functions(text: String) -> Dictionary:
	var out: Dictionary = {}
	var fn: String = ""
	for ln: String in text.split("\n"):
		if ln.begins_with("func ") or ln.begins_with("static func "):
			fn = ln.split("func ")[1].split("(")[0]
			out[fn] = []
			continue
		if fn != "" and ln != "" and not ln.begins_with("\t") and not ln.begins_with(" "):
			fn = ""
			continue
		if fn != "":
			(out[fn] as Array).append(ln)
	return out


## The argument list of the call that opens at text[at] ('('): the top-level arguments as strings
func _args(text: String, at: int) -> Array:
	var depth: int = 0
	var cur: String = ""
	var out: Array = []
	var q: bool = false
	for k: int in range(at, text.length()):
		var ch: String = text[k]
		if ch == "\"":
			q = not q
		if not q and (ch == "(" or ch == "["):
			depth += 1
			if depth == 1:
				continue
		elif not q and (ch == ")" or ch == "]"):
			depth -= 1
			if depth == 0:
				out.append(cur.strip_edges())
				return out
		elif not q and ch == "," and depth == 1:
			out.append(cur.strip_edges())
			cur = ""
			continue
		cur += ch
	return out


func _static(texts: Dictionary) -> Array:
	var listed: Dictionary = {}
	for r: Array in RULES:
		listed["%s|%s" % [r[0], r[1]]] = String(r[2])
	var laws: Dictionary = {}
	for l: Array in LAWS:
		laws["%s|%s" % [l[0], l[1]]] = String(l[2])
	var bad: Array = []
	var seen: Dictionary = {}
	var re_below := RegEx.create_from_string("\\bbelow\\(\"([a-z0-9_]+)\"")
	var re_u := RegEx.create_from_string("\\bu\\(\"([a-z0-9_]+)\"")
	for name: String in texts:
		var fns: Dictionary = _functions(String(texts[name]))
		for fn: String in fns:
			if name == "people.gd" and not PEOPLE_SCOPE.has(fn):
				continue
			var body: Array = fns[fn]
			for li: int in body.size():
				var ln: String = body[li]
				for m: RegExMatch in re_below.search_all(ln):
					var key: String = "%s|%s" % [m.get_string(1), name]
					if not listed.has(key):
						bad.append("%s:%s unlisted (in %s)" % [name, m.get_string(1), fn])
						continue
					seen[key] = true
					var args: Array = _args(ln, m.get_start() + "below".length())
					var operand: String = String(args[args.size() - 1]) if args.size() == 5 else ""
					if not _from_rate(operand, String(listed[key]), body, li):
						bad.append("%s:%s in %s operand '%s' is not %s's output" % [name, m.get_string(1), fn, operand, listed[key]])
				for m2: RegExMatch in re_u.search_all(ln):
					var tag: String = m2.get_string(1)
					var key2: String = "%s|%s" % [tag, name]
					if START.has(tag):
						continue
					if laws.has(key2):
						seen[key2] = true
						var so_far: String = "\n".join(body.slice(0, li + 1))
						if not so_far.contains(String(laws[key2]) + "("):
							bad.append("%s:%s in %s not drawn through %s" % [name, tag, fn, laws[key2]])
						continue
					bad.append("%s:%s in %s drawn by a bare u()" % [name, tag, fn])
	for key3: String in listed:
		if not seen.has(key3):
			bad.append("%s listed, no draw" % key3)
	for key4: String in laws:
		if not seen.has(key4):
			bad.append("%s law listed, no draw" % key4)
	return bad


## expr is exactly one call of rate (or p.rate): its opening parenthesis's match is the last character. Why not a prefix test: it
## passed `h_retire(p) * 0.9` (V110 M1)
func _is_call(expr: String, rate: String) -> bool:
	var e: String = expr.strip_edges()
	if e.begins_with("p."):
		e = e.substr(2)
	if not e.begins_with(rate + "("):
		return false
	var depth: int = 0
	var q: bool = false
	for k: int in range(rate.length(), e.length()):
		var ch: String = e[k]
		if ch == "\"":
			q = not q
		elif not q and ch == "(":
			depth += 1
		elif not q and ch == ")":
			depth -= 1
			if depth == 0:
				return k == e.length() - 1
	return false


## The operand is exactly the rate function's call, or a local (optionally indexed) assigned exactly from it earlier in the function and
## not reassigned between
func _from_rate(operand: String, rate: String, body: Array, li: int) -> bool:
	if _is_call(operand, rate):
		return true
	var m: RegExMatch = RegEx.create_from_string("^([a-z_][a-z0-9_]*)(\\[[0-9]+\\])?$").search(operand)
	if m == null:
		return false
	var v: String = m.get_string(1)
	var found: int = -1
	var re_set := RegEx.create_from_string("^\\s*var " + v + "(: [A-Za-z0-9]+)? :?= (.*)$")
	var re_re := RegEx.create_from_string("^\\s*" + v + "(\\[[^\\]]*\\])? [+\\-*/]?= ")
	for k: int in range(li - 1, -1, -1):
		var ms: RegExMatch = re_set.search(String(body[k]))
		if ms != null:
			found = k if _is_call(ms.get_string(2), rate) else -1
			break
	if found < 0:
		return false
	for k2: int in range(found + 1, li):
		if re_re.search(String(body[k2])) != null:
			return false
	return true


func _runtime() -> Object:
	var st = MS.new()
	st.load(2024, ["JPN"])
	var p = PEOPLE.new()
	p.households = true
	p.create("JPN", 7, st.cohort["JPN"], st.qx["JPN"], {"13": {"pop_thousand": 14178}, "47": {"pop_thousand": 1467}}, 400)
	p.rone_on = true
	var by_tag: Dictionary = {}
	for r: Array in RULES:
		by_tag[String(r[0])] = (by_tag.get(String(r[0]), []) as Array) + [String(r[2])]
	var last: Dictionary = {}
	var draws: int = 0
	var bad: int = 0
	var txt: String = ""
	var tags: Dictionary = {}
	var months: int = 0
	while months < RUN_MONTHS and tags.size() < by_tag.size():
		p.step({"inflation_month": 0.02 / 12.0, "food_price_yoy": 0.0, "unemployment_rate": 0.025, "levers": []})
		months += 1
		for e: Array in p.rone_log:
			if String(e[0]) == "out":
				last[String(e[1])] = e[2]
				continue
			draws += 1
			var tag: String = e[1]
			tags[tag] = int(tags.get(tag, 0)) + 1
			var h: float = float(e[3])
			var ok: bool = false
			for fn: String in by_tag.get(tag, []):
				var v: Variant = last.get(fn)
				if v is PackedFloat64Array:
					ok = ok or (v as PackedFloat64Array).has(h)
				elif v != null:
					ok = ok or float(v) == h
			if not ok:
				bad += 1
				if bad <= 5:
					txt += " %s person %d operand %s;" % [tag, int(e[2]), str(h)]
		p.rone_log.clear()
	var none: Array = []
	for t: String in by_tag:
		if not tags.has(t):
			none.append(t)
	check(draws > 0 and bad == 0 and none.is_empty(), "R-one (a′) a households-on run of 2 x 400 to month %d (stops when every listed tag has drawn, at most %d): listed tags with no draw %s; %d draws, each operand equal in bits to its rate function's latest output: %d not;%s draws by tag %s" % [months, RUN_MONTHS, str(none), draws, bad, txt, str(tags)])
	return p


## The float next to x toward +inf (dir 1) or -inf (dir -1), x in (0, 1)
func _next(x: float, dir: int) -> float:
	var a := PackedFloat64Array([x])
	var bits: PackedByteArray = a.to_byte_array()
	bits.encode_s64(0, bits.decode_s64(0) + dir)
	return bits.decode_double(0)


## below()'s comparison line, compiled alone as cmp(x, h)
func _compiled(line: String) -> Object:
	var gs := GDScript.new()
	gs.source_code = "extends RefCounted\nfunc cmp(x: float, h: float) -> bool:\n" + line + "\n"
	if gs.reload() != OK:
		return null
	return gs.new()


func _grid_bad(p, f: Callable) -> int:
	var bad: int = 0
	for i: int in mini(50, p.n):
		for tag: String in UNIT_TAGS:
			var x: float = p.u(tag, i, p.month, 0)
			for h: float in [0.0, 1.0, x, _next(x, 1), _next(x, -1), 0.25, 0.5, 0.75]:
				if bool(f.call(tag, i, x, h)) != (x < h):
					bad += 1
	return bad


func _below_unit(p, text: String) -> void:
	var body: Array = _functions(text).get("below", [])
	var line: String = ""
	for ln: String in body:
		if ln.strip_edges().begins_with("return "):
			line = ln
	var bad_real: int = _grid_bad(p, func(tag: String, i: int, _x: float, h: float) -> bool: return p.below(tag, i, p.month, 0, h))
	var orig: Object = _compiled(line)
	var bad_orig: int = _grid_bad(p, func(_tag: String, _i: int, x: float, h: float) -> bool: return orig.cmp(x, h)) if orig != null else -1
	check(line != "" and bad_real == 0 and bad_orig == 0, "R-one (d) (V112) below() on a grid of %d persons x %d tags x 8 h (0, 1, u, the floats next to u, quarters): returns other than u < h %d times (the comparison '%s' compiled alone: %d)" % [mini(50, p.n), UNIT_TAGS.size(), bad_real, line.strip_edges(), bad_orig])
	var mut: Object = _compiled(line.replace("x < h", "x < h * 0.999"))
	var bad_mut: int = _grid_bad(p, func(_tag: String, _i: int, x: float, h: float) -> bool: return mut.cmp(x, h)) if mut != null else 0
	check(line.contains("x < h") and mut != null and bad_mut > 0, "R-one (d′) V112's M4 (below()'s comparison as x < h * 0.999, compiled at run time) fails (d): %d of the grid's cells differ" % bad_mut)


func _pure(texts: Dictionary) -> void:
	var bad: Array = []
	var assign := RegEx.create_from_string("\\bp\\.[a-z_]+(\\[[^\\]]*\\])?\\s*([+\\-*/]?=)[^=]")
	var call := RegEx.create_from_string("\\b([A-Za-z_][A-Za-z0-9_]*)((\\.[A-Za-z_][A-Za-z0-9_]*)|(\\[[^\\]]*\\]))*\\.(" + "|".join(MUTATORS) + ")\\(")
	for r: Array in RULES + LAWS:
		var fns: Dictionary = _functions(String(texts[String(r[1])]))
		if not fns.has(String(r[2])):
			bad.append("%s.%s missing" % [r[1], r[2]])
			continue
		var body: Array = fns[String(r[2])]
		var locals: Dictionary = {}
		for ln: String in body:
			var mv: RegExMatch = RegEx.create_from_string("^\\s*var ([a-z_][a-z0-9_]*)").search(ln)
			if mv != null:
				locals[mv.get_string(1)] = true
			var mf: RegExMatch = RegEx.create_from_string("^\\s*for ([a-z_][a-z0-9_]*)").search(ln)
			if mf != null:
				locals[mf.get_string(1)] = true
		for ln2: String in body:
			if assign.search(ln2) != null:
				bad.append("%s.%s assigns: %s" % [r[1], r[2], ln2.strip_edges()])
			for mc: RegExMatch in call.search_all(ln2):
				if not locals.has(mc.get_string(1)):
					bad.append("%s.%s calls a mutator on %s: %s" % [r[1], r[2], mc.get_string(1), ln2.strip_edges()])
	check(bad.is_empty(), "R-one (b) each listed rate and law function exists and writes nothing (no assignment to p.<field>, no mutating call on a non-local): %s" % str(bad))
