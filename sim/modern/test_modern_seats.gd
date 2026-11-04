extends "res://tools/test/test_kit.gd"
## Seats (MODERN_PLAN 4; sim/modern/modern_seats.gd): scripted and replay occupants only; no network, no model call.
##   godot --headless --path . --script res://sim/modern/test_modern_seats.gd
## S1 a scripted seat acts in its view's terms: Japan's seat finds 北朝鮮 by name in its observation and closes chips to it by token, and
##    builds 500 MW of solar; the world applies both as the seat's
## S2 a replay of that seat's transcript gives the same world digest after four months, and every observation matches the one recorded
## S3 the validator refuses a whole answer: an unknown token, or one bad action next to a good one; the refusal is logged and the rules stand in
## S4 two seats at once, each in its own view: Japan's in Japanese, the USA's in the fixture's English; the USA closes chips to China by its
##    own token, and Japan's next observation shows that licence under Japan's tokens; each seat's transcript holds only its own months
## S5 the seat path has no network or process call (source check of the seat, view, world and register files)
const MW = preload("res://sim/modern/modern_world.gd")
const MV = preload("res://sim/modern/modern_view.gd")
const SEATS = preload("res://sim/modern/modern_seats.gd")


func _world() -> RefCounted:
	var w = MW.new()
	w.create(2022, {"view_salt": "6d6f6465726e2d736561742d73616c74"})
	return w


func _view(k: String, w: RefCounted) -> RefCounted:
	return w.make_view(k)


static func _token_named(obs: Dictionary, name: String) -> String:
	for r: Dictionary in obs["others"]:
		if String(r["name"]) == name:
			return String(r["token"])
	return ""


static func _japan(obs: Dictionary) -> Array:
	return [{"act": "licence", "good": "chips", "to": _token_named(obs, "北朝鮮"), "open": false}, {"act": "build", "kind": "solar", "size": 500.0}]


func _init() -> void:
	var w = _world()
	var jpn: int = w.data.index_of("JPN")
	var prk: int = w.data.index_of("PRK")
	var seat = SEATS.scripted(_view("jpn", w), _japan)
	w.seats[jpn] = seat
	w.advance_to(31)
	var solar: float = w.field.pending(jpn, "solar")
	var seat_rows: Array = w.log.filter(func(r: Array) -> bool: return String(r[1]) == "JPN" and String(r[2]) == "seat")
	check(not w.field.chain.is_open(jpn, "chips", prk) and solar == 500.0 and seat_rows.size() == 2,
		"S1 Japan's seat: chips to 北朝鮮 closed, %.0f MW solar started, %d actions logged as the seat's" % [solar, seat_rows.size()])
	w.advance_to(120)
	var r = _world()
	var rep = SEATS.replay(_view("jpn", r), seat.transcript)
	r.seats[jpn] = rep
	r.advance_to(120)
	check(r.digest() == w.digest() and rep.diverged == 0 and seat.transcript.size() == 4,
		"S2 replay of %d months: %s / %s, %d observations differ" % [seat.transcript.size(), r.digest().left(16), w.digest().left(16), rep.diverged])

	var b = _world()
	b.seats[jpn] = SEATS.scripted(_view("jpn", b), func(_o: Dictionary) -> Array: return [{"act": "licence", "good": "chips", "to": "T0000000000",
		"open": false}])
	b.advance_to(31)
	var c = _world()
	c.seats[jpn] = SEATS.scripted(_view("jpn", c), func(_o: Dictionary) -> Array: return [{"act": "build", "kind": "solar", "size": 500.0},
		{"act": "licence", "good": "uranium", "to": _token_named(_o, "中国"), "open": false}])
	c.advance_to(31)
	var refused: int = 0
	for row: Array in b.log + c.log:
		refused += 1 if String(row[1]) == "JPN" and String(row[2]) == "refused" else 0
	var fivehundred: int = c.field.projects.filter(func(p: Array) -> bool: return int(p[0]) == jpn and float(p[2]) == 500.0).size()
	check(refused == 2 and b.field.chain.closed_rows().is_empty() and fivehundred == 0,
		"S3 refused %d answers; nothing of them applied (closed %d, Japan's 500 MW solar projects %d)" % [refused, b.field.chain.closed_rows().size(), fivehundred])

	var t = _world()
	var usa: int = t.data.index_of("USA")
	var chn: int = t.data.index_of("CHN")
	var vb = _view("test_b", t)
	var names := {}
	var sj = SEATS.scripted(_view("jpn", t), func(o: Dictionary) -> Array:
		names["jpn"] = String(o["self"]["name"])
		names["jpn_lic"] = o["licences_closed"]
		return [])
	var su = SEATS.scripted(vb, func(o: Dictionary) -> Array:
		names["usa"] = String(o["self"]["name"])
		return [{"act": "licence", "good": "chips", "to": _token_named(o, "China"), "open": false}])
	t.seats[jpn] = sj
	t.seats[usa] = su
	t.advance_to(59)
	var vj = sj.view
	var lic: Array = names.get("jpn_lic", [])
	var lic_ok: bool = lic.size() >= 1 and String(lic[0]["from"]) == vj.token_of("USA") and String(lic[0]["to"]) == vj.token_of("CHN") \
		and vj.token_of("USA") != vb.token_of("USA")
	check(names.get("jpn") == "日本" and names.get("usa") == "United States of America" and lic_ok and sj.transcript.size() == 2
		and su.transcript.size() == 2 and sj.transcript[0]["obs_md5"] != su.transcript[0]["obs_md5"] and not t.field.chain.is_open(usa, "chips", chn),
		"S4 two seats: %s / %s; Japan sees %s" % [names.get("jpn"), names.get("usa"), str(lic)])

	var bad: Array = []
	for path: String in ["res://sim/modern/modern_seats.gd", "res://sim/modern/modern_view.gd", "res://sim/modern/modern_world.gd",
			"res://sim/modern/modern_publish.gd"]:
		var src: String = FileAccess.get_file_as_string(path)
		for word: String in ["HTTPRequest", "HTTPClient", "StreamPeerTCP", "WebSocket", "OS.execute", "OS.create_process", "api_key"]:
			if src.contains(word):
				bad.append("%s: %s" % [path.get_file(), word])
	check(bad.is_empty(), "S5 no network or process call on the seat path %s" % str(bad))
	finish()
