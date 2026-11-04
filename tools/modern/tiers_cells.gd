## Dumps T1's occupied cells (key -> persons) for the sizing count of ISS_TIERED_POPULATION.md §11.1a:
##   OUT=<json> godot --headless --path . --script res://tools/modern/tiers_cells.gd
extends SceneTree
const PEOPLE = preload("res://sim/modern/people/people.gd")
const TR = preload("res://sim/modern/people/tiers.gd")
const MS = preload("res://sim/modern/modern_status.gd")
const CANON = preload("res://sim/modern/canon.gd")
func _init() -> void:
	var st = MS.new()
	st.load(2024, ["JPN"])
	var prefs: Dictionary = CANON.load_json("res://data/modern/polity/jpn_prefectures.json")["prefectures"]
	var t0: int = Time.get_ticks_msec()
	var p = PEOPLE.new()
	p.tiers = true
	p.create("JPN", 1, st.cohort["JPN"], st.qx["JPN"], prefs, 0, 2024)
	var cells := {}
	for u: int in p.tr_units:
		var parts: Array = []
		for j: int in TR.KEY_STRIDE:
			parts.append(str(p.tr_key[u * TR.KEY_STRIDE + j]))
		var k: String = "|".join(parts)
		cells[k] = int(cells.get(k, 0)) + p.tr_count[u]
	var f := FileAccess.open(OS.get_environment("OUT"), FileAccess.WRITE)
	f.store_string(JSON.stringify({"cells": cells, "build_ms": Time.get_ticks_msec() - t0, "units": p.tr_units}))
	f.close()
	quit()
