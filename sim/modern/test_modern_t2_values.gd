extends "res://tools/test/test_kit.gd"
## ISS tiered population T2.R 4′ and 4″ (ISS_TIERED_POPULATION.md §14.1, declared 3d7a743b and 6b270046; V109, V110 (2)): the month's
## effects as values, on a state view.
##   godot --headless --path . --script res://sim/modern/test_modern_t2_values.gd
## T2.R 4′ month_values over every person of a households-on society run 6 months leaves the state unchanged in bits (the digest, and
##        a household-bundle-free society's too); apply_month_values of those values is the month's own path (R-pure, run apart)
## T2s-sv1 month_values on a point view holding a person's state equals month_values on the person's view, in bits, for every person
## T2s-sv2 month_values, deficit_values, _dream_values and the view's helpers read no persons-layer array by index and call no index
##        helper; a mutation reading one directly must fail
const PEOPLE = preload("res://sim/modern/people/people.gd")
const SV = preload("res://sim/modern/people/state_view.gd")
const GRP = preload("res://sim/modern/people/groups.gd")
const REL = preload("res://sim/modern/people/relations.gd")
const TR = preload("res://sim/modern/people/tiers.gd")
const MS = preload("res://sim/modern/modern_status.gd")
const ENV := {"inflation_month": 0.02 / 12.0, "food_price_yoy": 0.03, "unemployment_rate": 0.025, "levers": ["consumption_tax_rate", "child_allowance"]}
const ARRAYS := ["age", "assets", "basket", "belief", "belief_known", "debt", "dw", "emo", "emo_base", "employment", "hh_kind", "hh_size",
	"income", "lam", "last_action", "met", "plan", "pref_social", "pressure_prev", "q_act", "q_income", "q_job", "q_price", "skill",
	"health", "rank", "flags", "traits", "dream_progress", "dream_blocked", "dream_importance", "dream_status", "dream_kind",
	"contact_idx", "member_of"]
const FUNCS := ["func month_values(", "func deficit_values(", "func _dream_values(", "func _cost_v(", "func _trait_v(", "func _food_rise_v("]


func _init() -> void:
	var st = MS.new()
	st.load(2024, ["JPN"])
	for hh: bool in [true, false]:
		var p = PEOPLE.new()
		p.households = hh
		p.create("JPN", 7, st.cohort["JPN"], st.qx["JPN"], {"13": {"pop_thousand": 14178}, "47": {"pop_thousand": 1467}}, 200 if hh else 30)
		for m: int in 6:
			p.step(ENV)
		var d0: String = p.digest()
		var moves: int = 0
		for i: int in p.n:
			var v: Dictionary = p.month_values(SV.new().of_person(p, i), float(ENV["inflation_month"]), ENV["levers"])
			moves += (v["rec"] as Array).size()
		check(p.digest() == d0 and moves > 0, "T2.R 4′ month_values over %d persons (households %s) leaves the digest %s unchanged (%s); %d move records" % [p.n, str(hh), d0.left(8), p.digest().left(8), moves])
		_sv1(p, hh)
	_sv2()
	finish()


## T2s-sv1: each person's state copied into a scratch point store (point 0), the fields a point does not carry given as the person's
func _sv1(p, hh: bool) -> void:
	var keep: Dictionary = p.tr_points
	var rows: Array = TR.point_rows(p)
	var bad: int = 0
	for i: int in p.n:
		var tp: Dictionary = {}
		for r: Array in rows:
			var nm: String = String(r[0])
			var k: int = int(r[2])
			tp[nm] = (p.get(nm) as Variant).slice(i * k, (i + 1) * k)
		p.tr_points = tp
		var given: Dictionary = {"belief": p.belief.slice(i * REL.NF, (i + 1) * REL.NF), "belief_known": p.belief_known.slice(i * REL.NF, (i + 1) * REL.NF),
			"met": [p.met[i]], "contacts": p.contact_count(i), "memberships": GRP.memberships(p, i), "in_movement": p.in_movement(i)}
		var a: Dictionary = p.month_values(SV.new().of_point(p, 0, given), float(ENV["inflation_month"]), ENV["levers"])
		p.tr_points = keep
		var b: Dictionary = p.month_values(SV.new().of_person(p, i), float(ENV["inflation_month"]), ENV["levers"])
		if var_to_bytes(a) != var_to_bytes(b):
			bad += 1
	p.tr_points = keep
	check(bad == 0 and p.n > 0, "T2s-sv1 (§14.1 T2.R 4″, bit-exact) month_values on a point view holding the person's state against the person's view, households %s: %d of %d persons differ in bits" % [str(hh), bad, p.n])


## T2s-sv2: the direct reads and index-helper calls in the call tree's source (0), and in a mutated copy (must be > 0)
func _sv2() -> void:
	var src: String = FileAccess.get_file_as_string("res://sim/modern/people/people.gd")
	var found: Array = _direct_reads(src)
	var mut: String = src.replace("func month_values(v: RefCounted, infl: float, levers: Array) -> Dictionary:\n", "func month_values(v: RefCounted, infl: float, levers: Array) -> Dictionary:\n\tvar _m: int = age[0]\n")
	var found_m: Array = _direct_reads(mut)
	check(found.is_empty() and found_m.size() > 0 and mut != src, "T2s-sv2 (§14.1 T2.R 4″, a static row) direct persons-layer reads or index-helper calls in month_values, deficit_values, _dream_values and the view's helpers: %d %s; the must-fail mutation (age[0] in month_values) found %d" % [found.size(), str(found), found_m.size()])


func _direct_reads(src: String) -> Array:
	var lines: PackedStringArray = src.split("\n")
	var out: Array = []
	var arr := RegEx.new()
	arr.compile("(?<![\\w.\"])(" + "|".join(ARRAYS) + ")\\[")
	var helper := RegEx.new()
	helper.compile("(?<![\\w.])(cost_of_living|trait_of|believed_cost_rise|believed_food_rise|contact_count|in_movement)\\(|GRP\\.memberships\\(")
	for f: String in FUNCS:
		var at: int = -1
		for k: int in lines.size():
			if lines[k].begins_with(f):
				at = k
				break
		if at < 0:
			out.append("missing " + f)
			continue
		var j: int = at + 1
		while j < lines.size() and not lines[j].begins_with("func ") and not lines[j].begins_with("## "):
			var code: String = lines[j].split("#")[0] if not lines[j].strip_edges().begins_with("#") else ""
			if arr.search(code) != null or helper.search(code) != null:
				out.append("%s line %d" % [f.trim_prefix("func ").trim_suffix("("), j + 1])
			j += 1
	return out
