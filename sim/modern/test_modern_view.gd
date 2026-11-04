extends "res://tools/test/test_kit.gd"
## The leak test (MODERN_PLAN 4, owner's scope b; sim/modern/modern_view.gd, modern_publish.gd), on a 2022 world.
##   godot --headless --path . --script res://sim/modern/test_modern_view.gd
## V1 two views of one entity on one world give different observations (Japan's view and the test fixture, seat Japan)
## V2 one view twice gives byte-equal observations (md5), also from a second load of the view
## V3 nothing internal leaks: every entity reference is a token of that view, no key names an index or a code, no entity key or ISO code
##    appears as a word, and an entity the view does not hold (Kosovo in the fixture) has no name, alias or token anywhere, even in its
##    neighbour Serbia's observation
## V4 another entity's figures are only what is published: no key beyond token, name, kind, of and published; only figures R54's
##    visibility table lists; each appears only after its lag (the USA's population of 2020 on 1 February 2022, of 2021 by 5 February 2023;
##    its 2022 fab capacity not before 1 January 2024, then an estimate within ±15%)
## V5 the own block is the truth, exact, today
## V6 the same entity has different tokens in different views
## V7 the tokens are salted per run (V076): two runs with different salts give every entity different tokens, the same salt gives the same
##    tokens (a world restored from its keyframe makes them again, so replay stays exact), no token is the unsalted hash of its view and
##    key, a world without a salt makes no view, a rules-only world's digest is the same under either salt, and neither the salt nor its
##    bytes appear in any observation or in a seat's transcript
const MW = preload("res://sim/modern/modern_world.gd")
const SEATS = preload("res://sim/modern/modern_seats.gd")
const SALT_A := "6d6f6465726e2d746573742d73616c742d41"
const SALT_B := "6d6f6465726e2d746573742d73616c742d42"
const MV = preload("res://sim/modern/modern_view.gd")
const REF_KEYS: Array[String] = ["token", "to", "from", "of", "administered_by", "link_to"]
const BAD_KEYS: Array[String] = ["index", "entity", "key", "iso", "iso_a3", "ne_a3", "id"]


func _view(k: String, w: RefCounted) -> RefCounted:
	return w.make_view(k)


## Every entity reference in obs is a token of v; no key is an index or a code
func _refs_ok(obs: Variant, v: RefCounted) -> bool:
	if obs is Dictionary:
		for k: Variant in obs:
			if BAD_KEYS.has(String(k)):
				return false
			if REF_KEYS.has(String(k)) and (not (obs[k] is String) or v.entity_of(String(obs[k])) < 0):
				return false
			if not _refs_ok(obs[k], v):
				return false
	elif obs is Array:
		for x: Variant in obs:
			if not _refs_ok(x, v):
				return false
	return true


func _codes_in(text: String, w: RefCounted) -> Array:
	var codes := {}
	for e: int in w.data.entity_count():
		codes[w.data.keys[e]] = true
	var ent: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://data/modern/entities.json"))
	for r: Dictionary in ent["entities"]:
		codes[String(r["iso_a3"])] = true
		codes[String(r["ne_a3"])] = true
	var rx := RegEx.create_from_string("\\b[A-Z]{3}\\b")
	var hits: Array = []
	for m: RegExMatch in rx.search_all(text):
		if codes.has(m.get_string()):
			hits.append(m.get_string())
	return hits


func _salted(salt: String) -> RefCounted:
	var w = MW.new()
	w.create(2022, {"view_salt": salt})
	return w


func _init() -> void:
	var w = _salted(SALT_A)
	w.advance_to(31)
	var jpn: int = w.data.index_of("JPN")
	var vj = _view("jpn", w)
	var vb = _view("test_b", w)
	var tj: String = MV.text_of(vj.observe(w, jpn))
	var tb: String = MV.text_of(vb.observe(w, jpn))
	check(tj.md5_text() != tb.md5_text(), "V1 seat Japan, two views: %s / %s" % [tj.md5_text().left(12), tb.md5_text().left(12)])
	var tj2: String = MV.text_of(_view("jpn", w).observe(w, jpn))
	check(tj2.md5_text() == tj.md5_text() and MV.text_of(vj.observe(w, jpn)) == tj, "V2 Japan's view twice: %s" % tj.md5_text().left(12))

	var srb: int = w.data.index_of("SRB")
	var ob: Dictionary = vb.observe(w, srb)
	var tsrb: String = MV.text_of(ob)
	var kos_names: Array = [w.data.names_en[w.data.index_of("XKX")]]
	kos_names.append_array(vb.spec["entities"]["XKX"]["aliases"])
	var kos_hits: Array = []
	for n: String in kos_names:
		if tsrb.contains(n):
			kos_hits.append(n)
	var kos_tok: String = "T" + Crypto.new().hmac_digest(HashingContext.HASH_SHA256, SALT_A.hex_decode(), "modern-view|test_b|XKX".to_utf8_buffer()).hex_encode().left(10)
	var refs_ok: bool = _refs_ok(vj.observe(w, jpn), vj) and _refs_ok(ob, vb) and _refs_ok(vb.observe(w, jpn), vb)
	var codes: Array = _codes_in(tj, w) + _codes_in(tb, w) + _codes_in(tsrb, w)
	check(refs_ok and codes.is_empty() and kos_hits.is_empty() and not tsrb.contains(kos_tok) and vb.token_of("XKX") == "",
		"V3 references all tokens: %s; codes as words: %s; Kosovo in Serbia's fixture view: %s" % [str(refs_ok), str(codes), str(kos_hits)])

	var usa: int = w.data.index_of("USA")
	var vis: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://data/modern/visibility.json"))
	var shape_ok: bool = true
	for r: Dictionary in vj.observe(w, jpn)["others"]:
		for k: String in r:
			shape_ok = shape_ok and ["token", "name", "kind", "of", "published"].has(k)
		for fig: String in r["published"]:
			shape_ok = shape_ok and (vis["figures"] as Dictionary).has(fig)
	var p31: int = int(w.register.published("population", usa, w.field.day).get("year", -1))
	var f31: bool = w.register.published("fab_capacity", usa, w.field.day).is_empty()
	w.advance_to(400)
	var p400: int = int(w.register.published("population", usa, w.field.day).get("year", -1))
	var f729: bool = w.register.published("fab_capacity", usa, 729).is_empty()
	w.advance_to(730)
	var fab: Dictionary = w.register.published("fab_capacity", usa, w.field.day)
	var truth: float = w.register.history[2022]["fab_capacity"][usa]
	var fab_ok: bool = int(fab.get("year", -1)) == 2022 and String(fab.get("basis", "")) == "estimate" and absf(float(fab["value"]) / truth - 1.0) <= 0.15
	check(shape_ok and p31 == 2020 and f31 and p400 == 2021 and f729 and fab_ok,
		"V4 others: shape %s; USA population year %d on day 31, %d on day 400; fab capacity hidden to day 729, then %s (truth %.4f)" % [str(shape_ok),
		p31, p400, str(fab), truth])

	var own: Dictionary = vj.observe(w, jpn)["self"]
	var f = w.field
	var fi: Dictionary = own["figures"]
	var own_ok: bool = fi["fab_capacity"] == f.fab_cap[jpn] and fi["dc_capacity_it_mw"] == f.dc_it[jpn] and fi["servers_it_mw"] == f.servers[jpn] \
		and fi["demand_mw"] == f.demand[jpn] and fi["population"] == w.population(jpn) and fi["supply_mw"]["solar"] == f.supply_of(jpn, 6) \
		and String(own["name"]) == "日本" and String(own["kind"]) == "self"
	check(own_ok, "V5 Japan's own block is the truth today (%s, %s, fab %.4f)" % [own["name"], own["kind"], fi["fab_capacity"]])
	var differ: bool = true
	for k2: String in ["USA", "CHN", "TWN", "KOR"]:
		differ = differ and vj.token_of(k2) != vb.token_of(k2) and vj.token_of(k2) != ""
	check(differ, "V6 tokens differ between views (USA %s / %s)" % [vj.token_of("USA"), vb.token_of("USA")])

	var wa = _salted(SALT_A)
	var wb = _salted(SALT_B)
	var va = wa.make_view("jpn")
	var va2 = MW.from_dict(wa.to_dict()).make_view("jpn")
	var vbs = wb.make_view("jpn")
	var n_held: int = 0
	var all_differ: bool = true
	var same: bool = true
	var unsalted: int = 0
	for k3: String in wa.data.keys:
		if va.token_of(k3) == "":
			continue
		n_held += 1
		all_differ = all_differ and va.token_of(k3) != vbs.token_of(k3)
		same = same and va.token_of(k3) == va2.token_of(k3)
		for vk: String in ["jpn", "test_b"]:
			if va.token_of(k3) == "T" + ("modern-view|%s|%s" % [vk, k3]).sha256_text().left(10):
				unsalted += 1
	var bare = MW.new()
	bare.create(2022)
	var no_salt_err: String = bare.make_view("jpn").error
	wa.advance_to(31)
	wb.advance_to(31)
	var dga: String = wa.digest()
	var dgb: String = wb.digest()
	var seat = SEATS.scripted(va, func(o: Dictionary) -> Array: return [])
	wa.seats[jpn] = seat
	wa.advance_to(62)
	var texts: String = JSON.stringify(seat.transcript) + MV.text_of(va.observe(wa, jpn)) + MV.text_of(wa.make_view("test_b").observe(wa,
		wa.data.index_of("SRB")))
	var leaks: Array = []
	for needle: String in [SALT_A, SALT_A.to_upper(), SALT_A.hex_decode().get_string_from_ascii(), Marshalls.raw_to_base64(SALT_A.hex_decode())]:
		if texts.contains(needle):
			leaks.append(needle)
	check(n_held > 200 and all_differ and same and unsalted == 0 and no_salt_err != "" and dga == dgb and leaks.is_empty(),
		"V7 %d tokens: all differ between salts %s, same under one salt %s, unsalted matches %d; no salt: \"%s\"; digests %s / %s; salt in texts %s"
		% [n_held, str(all_differ), str(same), unsalted, no_salt_err, dga.left(12), dgb.left(12), str(leaks)])
	finish()
