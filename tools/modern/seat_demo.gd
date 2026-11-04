extends SceneTree
## A demonstration for M5 (scripted seats only, no model call): the same 2022 world run twice to the end of 2025, once with every entity on
## the rule actors, once with Japan's seat scripted to close photoresist to mainland China in its first month (in Japan's view: 中国 by
## token). Prints what differs, and an excerpt of Japan's last observation (its own block and two other rows) as the seat sees it.
##   godot --headless --path . --script res://tools/modern/seat_demo.gd -- [--days 1460] [--dump <file.json>] [--salt <hex>]
## The views' salt is --salt or 16 random bytes, so the tokens differ from run to run; the world digests do not.
## --dump writes Japan's first observation and its answer exactly as the seat saw and gave them.
const MW = preload("res://sim/modern/modern_world.gd")
const MV = preload("res://sim/modern/modern_view.gd")
const SEATS = preload("res://sim/modern/modern_seats.gd")


func _sum(w: RefCounted, arr: String, keys: Array) -> float:
	var t: float = 0.0
	for k: String in keys:
		t += float(w.field.get(arr)[w.data.index_of(k)])
	return t


func _init() -> void:
	var a := {"days": "1460", "dump": "", "salt": ""}
	var args: PackedStringArray = OS.get_cmdline_user_args()
	for i: int in range(0, args.size() - 1, 2):
		a[args[i].trim_prefix("--")] = args[i + 1]
	var days: int = int(a["days"])
	var salt: String = a["salt"] if a["salt"] != "" else Crypto.new().generate_random_bytes(16).hex_encode()
	var base = MW.new()
	base.create(2022, {"view_salt": salt})
	base.advance_to(days)
	var w = MW.new()
	w.create(2022, {"view_salt": salt})
	var v = w.make_view("jpn")
	var jpn: int = w.data.index_of("JPN")
	var once := {"done": false, "obs": {}, "answer": []}
	var seat = SEATS.scripted(v, func(o: Dictionary) -> Array:
		if once["done"]:
			return []
		once["done"] = true
		once["obs"] = o
		for r: Dictionary in o["others"]:
			if String(r["name"]) == "中国":
				once["answer"] = [{"act": "licence", "good": "photoresist", "to": String(r["token"]), "open": false}]
		return once["answer"])
	w.seats[jpn] = seat
	w.advance_to(days)
	if a["dump"] != "":
		var fo := FileAccess.open(a["dump"], FileAccess.WRITE)
		fo.store_string(JSON.stringify({"observation": once["obs"], "answer": once["answer"]}, " ", true))
		fo.close()
	print("SEAT_DEMO %d days from 2022; rules only %s; Japan seated %s" % [days, base.digest().left(16), w.digest().left(16)])
	for k: String in ["CHN", "TWN", "KOR", "JPN", "USA"]:
		var e: int = w.data.index_of(k)
		print("ROW %s fab_output_day %.6f -> %.6f | servers_it_mw %.0f -> %.0f | chips_held %.4f -> %.4f" % [k, base.field.fab_out[e], w.field.fab_out[e],
			base.field.servers[e], w.field.servers[e], base.field.chips[e], w.field.chips[e]])
	var ws0: float = 0.0
	var ws1: float = 0.0
	for e2: int in w.field.E:
		ws0 += base.field.servers[e2]
		ws1 += w.field.servers[e2]
	print("WORLD servers_it_mw %.0f -> %.0f (%+.2f%%)" % [ws0, ws1, (ws1 / ws0 - 1.0) * 100.0])
	print("CLOSED %s" % str(w.field.chain.closed_rows().map(func(r: Array) -> String: return "%s %s -> %s" % [w.data.keys[r[0]], r[1], w.data.keys[r[2]]])))
	var obs: Dictionary = v.observe(w, jpn)
	var ex := {"view": obs["view"], "date": obs["date"], "self_name": obs["self"]["name"], "self_fab_served": obs["self"]["figures"]["fab_served"],
		"licences_closed": obs["licences_closed"], "others_sample": []}
	for r2: Dictionary in obs["others"]:
		if ["中国", "台湾"].has(String(r2["name"])):
			ex["others_sample"].append(r2)
	print("JAPAN_SEES ", JSON.stringify(ex, " ", true))
	quit(0)
