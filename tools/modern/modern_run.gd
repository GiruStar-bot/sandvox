extends SceneTree
## Runs the modern world with keyframes (MODERN_PLAN 3).
##   godot --headless --path . --script res://tools/modern/modern_run.gd -- --year 2022 --days 1460 --every 365 --out <dir> \
##       [--growth persistence | <a year>] [--rules r55 | placeholder | none] [--salt <hex>] [--resume <keyframe .bin>]
## The run manifest <out>/run_manifest.json holds the year, the params and the views' secret salt (--salt, or 16 random bytes): it is the
## one place the salt is written, so a replay can make the same tokens; no observation or transcript carries it.
## A keyframe is var_to_bytes(world.to_dict()) at a day, written as <out>/kf_<day>.bin, with a line "KEYFRAME day digest". On --resume the
## run starts from the file (saved and restored once at the start, as the deep-time driver does) and goes on to --days.
## The last line is "DIGEST day digest elapsed_s".
const MW = preload("res://sim/modern/modern_world.gd")


func _init() -> void:
	var a := {"year": "2022", "days": "1460", "every": "365", "out": "", "growth": "persistence", "rules": "r55", "resume": "", "salt": ""}
	var args: PackedStringArray = OS.get_cmdline_user_args()
	for i: int in range(0, args.size() - 1, 2):
		a[args[i].trim_prefix("--")] = args[i + 1]
	var t0: int = Time.get_ticks_msec()
	var w: RefCounted
	if a["resume"] != "":
		var f := FileAccess.open(a["resume"], FileAccess.READ)
		w = MW.from_dict(bytes_to_var(f.get_buffer(f.get_length())))
		f.close()
	else:
		w = MW.new()
		var salt: String = a["salt"] if a["salt"] != "" else Crypto.new().generate_random_bytes(16).hex_encode()
		if w.create(int(a["year"]), {"compute_growth": a["growth"] if a["growth"] == "persistence" else float(a["growth"]), "rules": a["rules"],
				"view_salt": salt}) != "":
			print("ERROR ", w.error)
			quit(1)
			return
	if a["out"] != "":
		DirAccess.make_dir_recursive_absolute(a["out"])
		var mf := FileAccess.open("%s/run_manifest.json" % a["out"], FileAccess.WRITE)
		mf.store_string(JSON.stringify({"year": w.data.base_year, "params": w.params, "view_salt": w.view_salt.hex_encode()}, " ", true))
		mf.close()
	var every: int = int(a["every"])
	var end: int = int(a["days"])
	while w.field.day < end:
		var next: int = mini(end, (w.field.day / every + 1) * every)
		w.advance_to(next)
		var dg: String = w.digest()
		if a["out"] != "":
			var o := FileAccess.open("%s/kf_%d.bin" % [a["out"], w.field.day], FileAccess.WRITE)
			o.store_buffer(var_to_bytes(w.to_dict()))
			o.close()
		print("KEYFRAME %d %s" % [w.field.day, dg])
	print("DIGEST %d %s %.1f" % [w.field.day, w.digest(), float(Time.get_ticks_msec() - t0) / 1000.0])
	quit(0)
