extends SceneTree
## The faithfulness report (BLUEPRINT 0): F-A, the cross-section coverage of the status catalogue per status for every entity with a
## status file (sourced / catalogued, with the labels' split), and the list of catalogued indicators still missing; F-B is the hindcast
## (tools/modern/hindcast.gd) and the chronicle reading, not repeated here.
##   godot --headless --path . --script res://tools/modern/faithfulness.gd -- [--year 2024] [--out <file.md>]
const MS = preload("res://sim/modern/modern_status.gd")
const MD = preload("res://sim/modern/modern_data.gd")


func _init() -> void:
	var a := {"year": "2024", "out": ""}
	var args: PackedStringArray = OS.get_cmdline_user_args()
	for i: int in range(0, args.size() - 1, 2):
		a[args[i].trim_prefix("--")] = args[i + 1]
	var d = MD.new()
	var err: String = d.load_year(int(a["year"]))
	if err != "":
		print("ERROR ", err)
		quit(1)
		return
	var st = MS.new()
	err = st.load(int(a["year"]), d.keys)
	if err != "":
		print("ERROR ", err)
		quit(1)
		return
	var lines: PackedStringArray = PackedStringArray()
	lines.append("# Faithfulness report F-A (cross-section coverage), base %s" % a["year"])
	lines.append("")
	lines.append("Coverage = catalogued indicators with a sourced value / catalogued indicators. Labels: S sourced, D derived, T declared. Missing rows are the owner's and the researcher's list.")
	for k: String in st.entities:
		lines.append("")
		lines.append("## %s" % k)
		lines.append("| status | catalogued | with value | S | D | T | coverage | missing |")
		lines.append("|---|---|---|---|---|---|---|---|")
		var tot_c: int = 0
		var tot_h: int = 0
		for s: String in st.catalog["statuses"]:
			var cat: Dictionary = st.catalog["statuses"][s]["indicators"]
			var have: int = 0
			var ns: int = 0
			var nd: int = 0
			var nt: int = 0
			var missing: PackedStringArray = PackedStringArray()
			for id: String in cat:
				var row: Dictionary = (st.data[k] as Dictionary)["indicators"].get(id, {})
				if row.has("value"):
					have += 1
					var lab: String = String(row.get("label", "S"))
					if lab.begins_with("S"):
						ns += 1
					elif lab.begins_with("D"):
						nd += 1
					else:
						nt += 1
				else:
					missing.append(id)
			tot_c += cat.size()
			tot_h += have
			lines.append("| %s | %d | %d | %d | %d | %d | %.0f%% | %s |" % [st.catalog["statuses"][s]["title"], cat.size(), have, ns, nd, nt, 100.0 * float(have) / float(cat.size()), ", ".join(missing)])
		lines.append("| **all** | %d | %d | | | | **%.0f%%** | |" % [tot_c, tot_h, 100.0 * float(tot_h) / float(tot_c)])
		lines.append("")
		lines.append("Levers in the action space: %d (%s)" % [(st.levers[k] as Dictionary)["levers"].size(), ", ".join(PackedStringArray((st.levers[k] as Dictionary)["levers"].keys()))])
		var lk: Dictionary = st.links[k]
		var nlinks: int = 0
		for key: String in lk:
			if lk[key] is Dictionary:
				nlinks += 1
		lines.append("Foreign links recorded (placeholders with counterpart, BLUEPRINT 4b): %d blocks" % nlinks)
	var text: String = "\n".join(lines) + "\n"
	print(text)
	if String(a["out"]) != "":
		var f := FileAccess.open(String(a["out"]), FileAccess.WRITE)
		f.store_string(text)
		f.close()
	quit(0)
