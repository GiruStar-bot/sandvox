extends SceneTree
## A run with the status layer (S1): the world from a base year, every entity with a status file run by its rule brain, for N days; writes
## the chronicle as JSONL and a yearly table of each status indicator for the owner's reading (BLUEPRINT L4). No LLM, no seat unless a
## replay transcript is given later.
##   godot --headless --path . --script res://tools/modern/status_run.gd -- [--year 2024] [--days 365] [--out <dir>]
const MW = preload("res://sim/modern/modern_world.gd")


func _init() -> void:
	var a := {"year": "2024", "days": "365", "out": "", "salt": "0123456789abcdef0123456789abcdef"}
	var args: PackedStringArray = OS.get_cmdline_user_args()
	for i: int in range(0, args.size() - 1, 2):
		a[args[i].trim_prefix("--")] = args[i + 1]
	var w = MW.new()
	if w.create(int(a["year"]), {"view_salt": a["salt"]}) != "":
		print("ERROR ", w.error)
		quit(1)
		return
	var days: int = int(a["days"])
	var table: Dictionary = {}   # entity -> indicator -> [values per 365 days]
	var d: int = 0
	while d < days:
		d = mini(days, d + 365)
		w.advance_to(d)
		for k: String in w.status.entities:
			var row: Dictionary = table.get(k, {})
			var iv: Dictionary = w.status.ind[k]
			for id: String in iv:
				var arr: Array = row.get(id, [])
				arr.append(iv[id])
				row[id] = arr
			table[k] = row
	print("DIGEST %d %s" % [w.field.day, w.digest()])
	print("CHRONICLE rows %d" % w.chronicle.rows.size())
	var out: String = String(a["out"])
	if out != "":
		DirAccess.make_dir_recursive_absolute(out)
		var f := FileAccess.open(out.path_join("chronicle.jsonl"), FileAccess.WRITE)
		f.store_string(w.chronicle.to_jsonl())
		f.close()
		var lines: PackedStringArray = PackedStringArray()
		for k: String in table:
			lines.append("# %s: statuses by year end (base %s)" % [k, a["year"]])
			lines.append("| indicator | start | " + " | ".join(range(1, (table[k] as Dictionary).values()[0].size() + 1).map(func(i: int) -> String: return "year %d" % i)) + " |")
			lines.append("|---|---|" + "---|".repeat((table[k] as Dictionary).values()[0].size()))
			var ids: Array = (table[k] as Dictionary).keys()
			ids.sort()
			for id: String in ids:
				var start: float = float(w.status.ind0[k].get(id, NAN))
				var cells: PackedStringArray = PackedStringArray()
				for v: float in table[k][id]:
					cells.append(String.num(v, 6))
				lines.append("| %s | %s | %s |" % [id, String.num(start, 6), " | ".join(cells)])
		var g := FileAccess.open(out.path_join("statuses.md"), FileAccess.WRITE)
		g.store_string("\n".join(lines) + "\n")
		g.close()
		print("WROTE ", out)
	quit(0)
