extends SceneTree
## Run the monthly economy for N months, with an optional declared drought, and write the chronicle rows (JSONL) and a monthly table of
## the goods ledger for the owner's reading (BLUEPRINT_v2 7, S1').
##   godot --headless --path . --script res://tools/modern/econ_run.gd -- [--months 36] [--drought 12:23:0.6] [--out <dir>] [--base 2025] [--seed N]
const EM = preload("res://sim/modern/econ/econ_month.gd")


func _init() -> void:
	var a := {"months": "36", "drought": "", "out": "", "base": "2025", "seed": ""}
	var args: PackedStringArray = OS.get_cmdline_user_args()
	for i: int in range(0, args.size() - 1, 2):
		a[args[i].trim_prefix("--")] = args[i + 1]
	var e = EM.new()
	if e.create("JPN") != "":
		print("ERROR ", e.error)
		quit(1)
		return
	if String(a["drought"]) != "":
		var p: PackedStringArray = String(a["drought"]).split(":")
		e.declare_shock(int(p[0]), int(p[1]), {"rice": float(p[2]), "vegetables": float(p[2])}, "declared drought")
	if String(a["seed"]) != "":
		e.seed_shocks(int(a["seed"]), int(a["months"]) / 12 + 1)
	var base: int = int(a["base"])
	var rows: Array = []
	var table: PackedStringArray = PackedStringArray()
	table.append("| month | rice produced | rice inventory | rice traded | rice unmet | rice price (JPY/t) | veg inventory | veg price | wheat imported | wheat price | food planned | food output | food unmet | food price | scarcest input (fill) | farming cash | food cash | traders cash |")
	table.append("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
	for i: int in int(a["months"]):
		var m: int = e.world.month
		e.step()
		rows.append_array(e.chronicle_rows(base, m))
		var r: Dictionary = e.world.good("rice", "JPN")
		var v: Dictionary = e.world.good("vegetables", "JPN")
		var f: Dictionary = e.world.good("food_products", "JPN")
		var fm = e.actors[1]
		var w: Dictionary = e.world.good("wheat", "JPN")
		var scarcest: String = ""
		var fmin: float = 1.0
		for c: String in fm.input_fill:
			if float(fm.input_fill[c]) < fmin:
				fmin = float(fm.input_fill[c])
				scarcest = c
		table.append("| %04d-%02d | %.0f | %.0f | %.0f | %.0f | %.0f | %.0f | %.0f | %.0f | %.0f | %.1f | %.1f | %.1f | %.3f | %s (%.3f) | %.1f | %.1f | %.1f |" % [base + m / 12, m % 12 + 1, r["produced_last"], r["inventory"], r["traded_last"], r["unmet_last"], float(r["price"]) * 1e9, v["inventory"], float(v["price"]) * 1e9, w.get("imported_last", w["imported"]), float(w["price"]) * 1e9, fm.planned, fm.output, f["unmet_last"], float(f["price"]), scarcest, fmin, e.world.cash.get("crop_farming_JPN", 0.0), e.world.cash.get("food_manufacturing_JPN", 0.0), e.world.cash.get("trading_houses_JPN", 0.0)])
	print("DIGEST %d %s" % [e.world.month, e.digest()])
	print("ROWS %d" % rows.size())
	if String(a["out"]) != "":
		DirAccess.make_dir_recursive_absolute(String(a["out"]))
		var fh := FileAccess.open(String(a["out"]).path_join("econ_chronicle.jsonl"), FileAccess.WRITE)
		for r: Dictionary in rows:
			fh.store_line(JSON.stringify(r))
		fh.close()
		var g := FileAccess.open(String(a["out"]).path_join("econ_table.md"), FileAccess.WRITE)
		g.store_string("\n".join(table) + "\n")
		g.close()
		print("WROTE ", a["out"])
	quit(0)
