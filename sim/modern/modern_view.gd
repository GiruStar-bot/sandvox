extends RefCounted
## One state's view (MODERN_PLAN 4, scope b): the observation a seat gets, built from its own entity's truth and the publication register,
## then mapped into the view: every entity is named by the view's opaque token ("T" + 10 hex of HMAC-SHA256 under the run's secret salt
## of the view key and the entity key; never the field's index or a code) and the view's name; kinds are the view's; an entity the view
## does not hold at all ("unknown")
## has no token, no name and no row, and links, licences and claims that touch it are left out.
## Own block: the truth, exact, today. Others: only what the register has published by today, with year and basis.
const MD = preload("res://sim/modern/modern_data.gd")
const MP = preload("res://sim/modern/modern_publish.gd")
const MONTH_DAYS: Array[int] = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]

var key: String = ""
var spec: Dictionary = {}
var error: String = ""
var _token := {}    # entity key -> token
var _entity := {}   # token -> entity index


func load_view(view_key: String, data: RefCounted, salt: PackedByteArray) -> String:
	key = view_key
	# Why not a plain hash of the view and the key (V076): anyone who knows the formula can hash every key and invert the tokens, learning
	# internal keys and entities the view does not hold; under a secret salt a token says nothing without the salt
	if salt.size() < 16:
		error = "modern view: a view needs the run's secret salt (16 bytes or more)"
		return error
	var crypto := Crypto.new()
	var v: Variant = MD.CANON.load_json_m("res://data/modern/views/%s.json" % view_key)
	if not (v is Dictionary):
		error = "modern view: no view " + view_key
		return error
	spec = v
	for e: int in data.entity_count():
		var k: String = data.keys[e]
		if kind_of(k) == "unknown":
			continue
		var tok: String = "T" + crypto.hmac_digest(HashingContext.HASH_SHA256, salt, ("modern-view|%s|%s" % [key, k]).to_utf8_buffer()).hex_encode().left(10)
		_token[k] = tok
		_entity[tok] = e
	return ""


func kind_of(entity_key: String) -> String:
	return String(spec["entities"].get(entity_key, {}).get("kind", "unknown"))


func token_of(entity_key: String) -> String:
	return String(_token.get(entity_key, ""))


## The entity a token names in this view, or -1
func entity_of(tok: String) -> int:
	return int(_entity.get(tok, -1))


static func date_of(base_year: int, day: int) -> String:
	var y: int = base_year + day / 365
	var d: int = day % 365
	var m: int = 0
	while d >= MONTH_DAYS[m]:
		d -= MONTH_DAYS[m]
		m += 1
	return "%04d-%02d-%02d" % [y, m + 1, d + 1]


func _row(w: RefCounted, e: int) -> Dictionary:
	var k: String = w.data.keys[e]
	var r: Dictionary = spec["entities"][k]
	var out := {"token": _token[k], "name": String(r["name"]), "kind": String(r["kind"])}
	if r.has("of") and r["of"] != null and _token.has(String(r["of"])):
		out["of"] = _token[String(r["of"])]
	return out


func observe(w: RefCounted, me: int) -> Dictionary:
	var f = w.field
	var d = w.data
	var S: int = MD.SOURCES.size()
	var day: int = f.day
	var own: Dictionary = _row(w, me)
	var sup := {}
	for s: int in S:
		sup[MD.SOURCES[s]] = f.supply_of(me, s)
	own["figures"] = {"population": w.population(me), "gdp": d.gdp[me] * MD.DM.pow(1.0 + d.gdp_growth[me], float(day - 182) / 365.0),
		"demand_mw": f.demand[me], "supply_mw": sup, "contracted_imports_mw": f.imports_of(me), "storage_mwh": f.storage[me],
		"storage_capacity_mwh": f.storage_cap[me], "dc_capacity_it_mw": f.dc_it[me], "servers_it_mw": f.servers[me], "chips_held": f.chips[me],
		"fab_capacity": f.fab_cap[me], "fab_output_day": f.fab_out[me], "dc_served": f.dc_served[me], "fab_served": f.fab_served[me],
		"unserved_mw": f.unserved[me], "dc_water_l": f.water_l[me], "cut_first": "fab" if f.fab_first[me] == 1 else "dc"}
	var projects: Array = []
	for p: Array in f.projects:
		if int(p[0]) != me:
			continue
		var pr := {"kind": String(p[1]), "size": float(p[2]), "started": date_of(d.base_year, int(p[3])), "finishes": date_of(d.base_year, int(p[4]))}
		if int(p[5]) >= 0:
			var other: int = f.link_b[int(p[5])] if f.link_a[int(p[5])] == me else f.link_a[int(p[5])]
			if not _token.has(d.keys[other]):
				continue
			pr["link_to"] = _token[d.keys[other]]
		projects.append(pr)
	own["projects"] = projects
	# The status layer (BLUEPRINT L1, scope b): the own state in full, with the menu of levers; another state's statuses only as published
	# (no status is published in S1, so others carry none)
	if w.status != null and w.status.has(d.keys[me]):
		var st: Dictionary = (w.status.ind[d.keys[me]] as Dictionary).duplicate()
		var ks: Array = st.keys()
		ks.sort()
		var ordered: Dictionary = {}
		for id: String in ks:
			ordered[id] = st[id]
		own["statuses"] = ordered
		own["menu"] = w.status.menu(d.keys[me])
	var links: Array = []
	for l: int in f.links_of[me]:
		var o: int = f.link_b[l] if f.link_a[l] == me else f.link_a[l]
		if not _token.has(d.keys[o]):
			continue
		links.append({"to": _token[d.keys[o]], "capacity_mw": f.link_cap[l], "flow_out_mw": f.link_flow[l] if f.link_a[l] == me else -f.link_flow[l]})
	links.sort_custom(func(x: Dictionary, y: Dictionary) -> bool: return String(x["to"]) < String(y["to"]))
	own["links"] = links
	var others: Array = []
	for e: int in f.E:
		if e == me or not _token.has(d.keys[e]):
			continue
		var r: Dictionary = _row(w, e)
		var pub := {}
		for fig: String in w.register.FIGURES:
			var v: Dictionary = w.register.published(fig, e, day)
			if not v.is_empty():
				pub[fig] = v
		r["published"] = pub
		others.append(r)
	others.sort_custom(func(x: Dictionary, y: Dictionary) -> bool: return String(x["token"]) < String(y["token"]))
	var lic: Array = []
	for row: Array in f.chain.closed_rows():
		var ki: String = d.keys[int(row[0])]
		var kd: String = d.keys[int(row[2])]
		if _token.has(ki) and _token.has(kd):
			lic.append({"from": _token[ki], "good": String(row[1]), "to": _token[kd]})
	lic.sort_custom(func(x: Dictionary, y: Dictionary) -> bool: return "%s|%s|%s" % [x["from"], x["good"], x["to"]] < "%s|%s|%s" % [y["from"], y["good"], y["to"]])
	var claims: Array = []
	for c: Dictionary in spec["claims"]:
		if _token.has(String(c["administered_by"])):
			claims.append({"label": String(c["label"]), "administered_by": _token[String(c["administered_by"])]})
	return {"view": key, "date": date_of(d.base_year, day), "self": own, "others": others, "licences_closed": lic, "claims": claims,
		"sources": Array(MD.SOURCES), "goods_licensed": Array(w.field.chain.GOODS_LICENSED), "project_kinds": Array(w.field.PROJECT_KINDS)}


static func text_of(obs: Dictionary) -> String:
	return JSON.stringify(obs, "", true, true)


## A seat's action in the view's terms -> the world's action, or {"error": why}
func to_world(a: Variant) -> Dictionary:
	if not (a is Dictionary):
		return {"error": "not an action"}
	var act: Dictionary = (a as Dictionary).duplicate()
	for field_name: String in ["to", "link_to"]:
		if act.has(field_name):
			var e: int = entity_of(String(act[field_name]))
			if e < 0:
				return {"error": "unknown token " + String(act[field_name])}
			act[field_name] = e
	return act
