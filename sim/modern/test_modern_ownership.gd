extends "res://tools/test/test_kit.gd"
## One writer per datum (ISS_HOUSEHOLD_REDESIGN.md §10.3 C; the owner's tidy-up of 2026-10-29): no file of sim/modern writes a person's
## or a household's array unless it owns it. people.gd owns every field not listed below and writes them by name; the other files write
## p.<field> only for the fields they own, and ask people.gd's functions for the rest.
##   godot --headless --path . --script res://sim/modern/test_modern_ownership.gd
## W1 every write to p.<field> outside people.gd (assignment, compound assignment, resize, fill, append, remove) is in an owner's file
## W2 the guard sees writes: the owners' files hold writes it recognises (a guard that matches nothing would pass every file)
## W3 the check-period values stay out of the simulation: no file under res://sim names data/modern/checks/ (R65: CHECK ONLY, never
##    an input)
## W4 people.gd itself writes another module's field only while constructing a person (the start, a newborn, a reborn slot), in its
##    storage (sizing, growth, compaction) and its restore; the start's weight and its person-level rake (households off) for weight
## W5 the spec's checks block stays out of the simulation: no non-test file under res://sim/modern names "checks" (the targets the
##    report and the tests read, V099 item 4; as W3 for R65)
## W6 the registry is complete: every packed array of people.gd (by reflection) is in fields(), household_fields() or TRANSIENT
## The guard's limits: W1 and W4 are text scans of `p.<field>` (W1) and a field's bare name at a line's start (W4). They do not see a
## write through an alias (`var a = p.contact_idx; a[0] = 1`), through set()/get() by name, through a variable not called `p`, or a write
## inside a lambda's body on the same line as another match. The mutating calls they see: assignment, compound assignment, resize, fill,
## append, append_array, remove_at, erase, clear, push_back, insert, sort, reverse, set. Why not a runtime guard: the packed arrays have
## no write hook, and wrapping them would change every digest path
const TIERS := "res://sim/modern/people/tiers.gd"
const HOUSEHOLD := ["res://sim/modern/people/households.gd", "res://sim/modern/people/life_course.gd"]
const OWNERS := {
	"contact_idx": ["res://sim/modern/people/relations.gd"], "contact_kind": ["res://sim/modern/people/relations.gd"],
	"contact_trust": ["res://sim/modern/people/relations.gd"], "contact_last": ["res://sim/modern/people/relations.gd"],
	"met": ["res://sim/modern/people/relations.gd"], "belief": ["res://sim/modern/people/relations.gd"],
	"belief_known": ["res://sim/modern/people/relations.gd"], "belief_source": ["res://sim/modern/people/relations.gd"],
	"belief_month": ["res://sim/modern/people/relations.gd"],
	"member_of": ["res://sim/modern/people/groups.gd"], "union_cover": ["res://sim/modern/people/groups.gd"],
	"groups": ["res://sim/modern/people/groups.gd"], "group_log": ["res://sim/modern/people/groups.gd"],
	"employment": ["res://sim/modern/econ/labour.gd", "res://sim/modern/people/life_course.gd"], "pay_factor": ["res://sim/modern/econ/labour.gd"],
	"weight": ["res://sim/modern/people/households.gd"], "hh_weight": ["res://sim/modern/people/households.gd"],
	"health": ["res://sim/modern/people/life_course.gd"],
	"tr_spec": [TIERS], "tr_k": [TIERS], "tr_units": [TIERS], "tr_key": [TIERS], "tr_count": [TIERS], "tr_age_counts": [TIERS], "tr_never_married": [TIERS], "tr_married_apart": [TIERS], "tr_pt_age": [TIERS], "tr_hh_keys": [TIERS], "tr_hm_off": [TIERS], "tr_hm_pt": [TIERS], "tr_hm_role": [TIERS], "tr_hm_n": [TIERS], "tr_cp_hh": [TIERS], "tr_cp_w": [TIERS], "tr_cp_h": [TIERS], "tr_cp_n": [TIERS], "tr_pt_ms": [TIERS],
	"tr_tier_size": [TIERS], "tr_residual": [TIERS], "tr_points": [TIERS], "tr_hh": [TIERS], "tr_instruments": [TIERS], "tr_instrument_factor": [TIERS],
	"tr_indiv_unit": [TIERS], "tr_pt_off": [TIERS], "tr_pt_mass": [TIERS], "tr_couples": [TIERS], "tr_nh_couples": [TIERS], "tr_nh_hh": [TIERS], "tr_margins": [TIERS],
	"tr_mix_off": [TIERS], "tr_mix_code": [TIERS], "tr_mix_n": [TIERS], "tr_pt_code": [TIERS], "tr_indiv_code": [TIERS],
	"tr_phi": [TIERS], "tr_pension": [TIERS], "tr_pension_kind": [TIERS],
	"tr_pt_id": [TIERS], "tr_pt_jan": [TIERS], "tr_pt_old": [TIERS], "tr_pt_next": [TIERS], "tr_kb": [TIERS], "tr_class_lines": [TIERS], "tr_c": [TIERS], "tr_pt_q": [TIERS], "tr_pt_rem": [TIERS], "tr_cp_cap": [TIERS], "tr_pt_muq": [TIERS], "tr_pt_mug": [TIERS],
	"tr_pt_ag": [TIERS], "tr_pt_jg": [TIERS], "tr_pt_og": [TIERS], "tr_pt_T": [TIERS],
}
const PEOPLE = preload("res://sim/modern/people/people.gd")
## Why not saved: lc_dying holds the month's deaths only between the yearly turns and the month's end, and is empty at every save
const TRANSIENT := ["lc_dying", "tr_key", "tr_count", "tr_age_counts", "tr_never_married", "tr_married_apart", "tr_pt_age", "tr_hh_keys", "tr_hm_off", "tr_hm_pt", "tr_hm_role", "tr_hm_n", "tr_cp_hh", "tr_cp_w", "tr_cp_h", "tr_cp_n", "tr_pt_ms", "tr_tier_size", "tr_residual", "tr_indiv_unit", "tr_pt_off", "tr_pt_mass", "tr_couples", "tr_nh_couples", "tr_nh_hh", "tr_mix_off", "tr_mix_code", "tr_mix_n", "tr_pt_code", "tr_indiv_code", "tr_pt_id", "tr_pt_jan", "tr_pt_old", "tr_kb", "tr_class_lines", "tr_c", "tr_pt_q", "tr_pt_muq", "tr_pt_mug", "tr_pt_ag", "tr_pt_jg", "tr_pt_og", "tr_pt_T"]
const CONSTRUCT := ["_draw_attributes", "_resize", "grow_persons", "remove_persons", "from_dict", "tier_person", "tier_income", "tier_wealth", "tier_education", "tier_pension"]
const RAKE := ["create", "reweight", "_create_tiers"]
const HOUSEHOLD_FIELDS := ["hh_id", "hh_type", "hh_pref", "hh_members", "hh_n", "hh_role", "partner", "ever_married", "ever_left",
	"union_month", "last_birth", "births_n", "next_k", "life_log", "lc_dying", "lc_c", "lc_qcut", "lc_c_band", "lc_expected", "lc_deaths", "lc_births", "hh_spec",
	"hh_kind", "hh_size", "intends_marry", "intended_kids", "lc_nm_short", "health_class", "lc_t22b"]


func _files(dir: String, out: Array) -> void:
	var d := DirAccess.open(dir)
	if d == null:
		return
	for f: String in d.get_files():
		if f.ends_with(".gd") and not f.begins_with("test_"):
			out.append(dir.path_join(f))
	for sub: String in d.get_directories():
		_files(dir.path_join(sub), out)


func _init() -> void:
	var files: Array = []
	_files("res://sim/modern", files)
	var write := RegEx.new()
	write.compile("\\bp\\.([a-z_]+)(\\[[^\\]\\n]*\\])*\\s*([-+*/|&]?=)(?!=)|\\bp\\.([a-z_]+)\\.(resize|fill|append|append_array|remove_at|erase|clear|push_back|insert|sort|reverse|set)\\(")
	var bad: Array = []
	var seen: int = 0
	for f: String in files:
		if f.ends_with("/people/people.gd"):
			continue
		var lines: PackedStringArray = FileAccess.get_file_as_string(f).split("\n")
		for ln: int in lines.size():
			var line: String = lines[ln]
			if line.strip_edges().begins_with("#"):
				continue
			for m: RegExMatch in write.search_all(line):
				var field: String = m.get_string(1) if m.get_string(1) != "" else m.get_string(4)
				var owners: Array = HOUSEHOLD if HOUSEHOLD_FIELDS.has(field) else OWNERS.get(field, ["res://sim/modern/people/people.gd"])
				seen += 1
				if not owners.has(f):
					bad.append("%s:%d p.%s" % [f.get_file(), ln + 1, field])
	check(bad.is_empty(), "W1 writes outside their owner: %s" % (str(bad) if not bad.is_empty() else "none (%d files)" % files.size()))
	check(seen >= 50, "W2 the guard recognises the owners' writes: %d" % seen)
	var all_sim: Array = []
	_files("res://sim", all_sim)
	var readers: Array = []
	for f2: String in all_sim:
		if FileAccess.get_file_as_string(f2).contains("data/modern/checks"):
			readers.append(f2.get_file())
	check(readers.is_empty(), "W3 check-only values read by the simulation: %s (%d files scanned)" % [str(readers), all_sim.size()])
	var foreign: Array = OWNERS.keys() + HOUSEHOLD_FIELDS
	var own := RegEx.new()
	own.compile("^\\s*(%s)(\\[[^\\]\\n]*\\])?\\s*([-+*/|&]?=)(?!=)|^\\s*(%s)\\.(resize|fill|append|append_array|remove_at|erase|clear|push_back|insert|sort|reverse|set)\\(" % ["|".join(foreign), "|".join(foreign)])
	var func_re := RegEx.new()
	func_re.compile("^(static )?func (\\w+)")
	var bad4: Array = []
	var seen4: int = 0
	var fn: String = ""
	var plines: PackedStringArray = FileAccess.get_file_as_string("res://sim/modern/people/people.gd").split("\n")
	for ln4: int in plines.size():
		var fm: RegExMatch = func_re.search(plines[ln4])
		if fm != null:
			fn = fm.get_string(2)
		var wm: RegExMatch = own.search(plines[ln4])
		if wm == null:
			continue
		seen4 += 1
		var field4: String = wm.get_string(1) if wm.get_string(1) != "" else wm.get_string(4)
		if CONSTRUCT.has(fn) or (field4 == "weight" and RAKE.has(fn)):
			continue
		bad4.append("people.gd:%d %s in %s" % [ln4 + 1, field4, fn])
	check(bad4.is_empty() and seen4 > 0, "W4 people.gd writes another module's field outside construction: %s (%d construction writes seen)" % [str(bad4) if not bad4.is_empty() else "none", seen4])
	var spec_readers: Array = []
	for f5: String in files:
		if FileAccess.get_file_as_string(f5).contains("\"checks\""):
			spec_readers.append(f5.get_file())
	check(spec_readers.is_empty(), "W5 the spec's checks block named by the simulation: %s (%d files scanned)" % [str(spec_readers), files.size()])
	var p6 = PEOPLE.new()
	var reg := {}
	for r6: Array in p6.fields():
		reg[String(r6[0])] = true
	for h6: Array in p6.household_fields():
		reg[String(h6[0])] = true
	var packed := [TYPE_PACKED_BYTE_ARRAY, TYPE_PACKED_INT32_ARRAY, TYPE_PACKED_INT64_ARRAY, TYPE_PACKED_FLOAT32_ARRAY, TYPE_PACKED_FLOAT64_ARRAY, TYPE_PACKED_STRING_ARRAY]
	var missing: Array = []
	var n6: int = 0
	for prop: Dictionary in p6.get_property_list():
		if packed.has(int(prop["type"])) and int(prop["usage"]) & PROPERTY_USAGE_SCRIPT_VARIABLE:
			n6 += 1
			if not reg.has(String(prop["name"])) and not TRANSIENT.has(String(prop["name"])):
				missing.append(String(prop["name"]))
	check(missing.is_empty() and n6 > 0, "W6 packed arrays in no registry: %s (%d packed arrays reflected)" % [str(missing), n6])
	finish()
