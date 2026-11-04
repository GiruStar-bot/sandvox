extends SceneTree
## Run Japan's representative persons for N months through the economy's own environment inside the modern world (people on), and print
## the national and the prefecture aggregates (weighted quantiles) for the owner's reading (ISS Phase 1).
##   godot --headless --path . --script res://tools/modern/people_run.gd -- [--days 730] [--seed 1] [--n 200] [--out <dir>]
const MW = preload("res://sim/modern/modern_world.gd")


func _init() -> void:
	var a := {"days": "730", "seed": "1", "n": "200", "out": ""}
	var args: PackedStringArray = OS.get_cmdline_user_args()
	for i: int in range(0, args.size() - 1, 2):
		a[args[i].trim_prefix("--")] = args[i + 1]
	var w = MW.new()
	var err: String = w.create(2024, {"view_salt": "0123456789abcdef0123456789abcdef", "people": true, "people_seed": int(a["seed"]), "people_per_prefecture": int(a["n"])})
	if err != "":
		print("ERROR ", err)
		quit(1)
		return
	var t0: int = Time.get_ticks_msec()
	w.advance_to(int(a["days"]))
	var ms: int = Time.get_ticks_msec() - t0
	var p = w.people
	var lines: PackedStringArray = PackedStringArray()
	lines.append("| prefecture | persons | population | unemployment | real income p10/p50/p90 (万円) | anxiety p10/p50/p90 | discontent p50 | hope p50 | pressure |")
	lines.append("|---|---|---|---|---|---|---|---|---|")
	var nat: Dictionary = p.summary()
	lines.append(_row("JPN", nat))
	for code: String in p.pref_codes:
		lines.append(_row(code, p.summary(int(code))))
	print("\n".join(lines))
	var shares: Dictionary = nat["last_action_shares"]
	var ks: Array = shares.keys()
	ks.sort_custom(func(x: String, y: String) -> bool: return float(shares[x]) > float(shares[y]))
	var parts: PackedStringArray = PackedStringArray()
	for k: String in ks:
		parts.append("%s %.3f" % [k, float(shares[k])])
	print("ACTIONS last month (weighted shares): ", ", ".join(parts))
	print("DECISIONS %d rows, REFUSALS %d rows; last month's refusals: " % [p.decisions.size(), p.refusals.size()])
	for r: Dictionary in p.refusals:
		if int(r["month"]) == p.month - 1:
			print("  %s refused %d: %s" % [r["action"], r["count"], r["why"]])
	print("EVENTS %d rows; last month's: " % p.events.size())
	for ev: Dictionary in p.events:
		if int(ev["month"]) == p.month - 1:
			print("  %s n=%d w=%.0f mean_move=%.3f (%s)" % [ev["kind"], ev["count"], ev["weight"], ev["mean_move"], ev["why"]])
	print("PEOPLE %d persons, %d months, %d ms; DIGEST %s" % [p.n, p.month, ms, p.digest()])
	print("WORLD DIGEST %d %s" % [w.field.day, w.digest()])
	if String(a["out"]) != "":
		DirAccess.make_dir_recursive_absolute(String(a["out"]))
		var fh := FileAccess.open(String(a["out"]).path_join("people_table.md"), FileAccess.WRITE)
		fh.store_string("\n".join(lines) + "\n")
		fh.close()
		print("WROTE ", a["out"])
	quit(0)


func _row(label: String, s: Dictionary) -> String:
	var ri: Array = s["real_income_p10_p50_p90"]
	var ax: Array = s["anxiety_p10_p50_p90"]
	return "| %s | %d | %.0f | %.3f | %.1f/%.1f/%.1f | %.2f/%.2f/%.2f | %.2f | %.2f | %.3f |" % [label, s["persons"], s["population"], s["unemployment_rate"], ri[0], ri[1], ri[2], ax[0], ax[1], ax[2], s["discontent_p10_p50_p90"][1], s["hope_p10_p50_p90"][1], s["pressure_mean"]]
