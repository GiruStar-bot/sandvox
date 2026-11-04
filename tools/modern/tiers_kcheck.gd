## T1s-g (ISS_TIERED_POPULATION.md §12.5 F8): the start at P / U = 4, 8 and 16 points per bundle, R seeds each; per K the mean of each
## reading and its SE over the seeds, the 1/K regime and T(inf) = 2 T(16) - T(8); written as JSON for the run note.
##   OUT=<json> SEEDS=10 [KS=4,8,16] godot --headless --path . --script res://tools/modern/tiers_kcheck.gd
## Readings, nationally and for Tottori (31), weighted by the points' masses, adults (20+) only:
##   assets  the mean of the points' assets (万円)
##   poor    the share of persons whose point's monthly income is below half the national median
##   bundles the persons' share in bundles whose share of persons with a point income under 15 万円 exceeds 50% (a bundle at
##           exactly 50% counted half; M003 T8: a count of bundles jumps by whole bundles as K changes a tie)
extends SceneTree
const PEOPLE = preload("res://sim/modern/people/people.gd")
const TR = preload("res://sim/modern/people/tiers.gd")
const MS = preload("res://sim/modern/modern_status.gd")
const CANON = preload("res://sim/modern/canon.gd")
const SMALL := 31


func _readings(p) -> Dictionary:
	var inc: PackedFloat64Array = p.tr_points["income"]
	var ass: PackedFloat64Array = p.tr_points["assets"]
	var pairs: Array = []
	for u: int in p.tr_units:
		if p.tr_key[u * TR.KEY_STRIDE + 1] * 5 < TR.ADULT_FROM:
			continue
		for g: int in range(p.tr_pt_off[u], p.tr_pt_off[u + 1]):
			pairs.append([inc[g], p.tr_pt_mass[g]])
	pairs.sort_custom(func(a: Array, b: Array) -> bool: return float(a[0]) < float(b[0]))
	var tot: int = 0
	for q: Array in pairs:
		tot += int(q[1])
	var acc: int = 0
	var median: float = 0.0
	for q2: Array in pairs:
		acc += int(q2[1])
		if acc * 2 >= tot:
			median = float(q2[0])
			break
	var out := {}
	for scope: String in ["national", "small"]:
		var m: float = 0.0
		var a: float = 0.0
		var poor: float = 0.0
		var nb: float = 0.0
		var nb_hit: float = 0.0
		for u2: int in p.tr_units:
			if p.tr_key[u2 * TR.KEY_STRIDE + 1] * 5 < TR.ADULT_FROM:
				continue
			if scope == "small" and p.tr_key[u2 * TR.KEY_STRIDE] != SMALL:
				continue
			var bm: float = 0.0
			var low: float = 0.0
			for g2: int in range(p.tr_pt_off[u2], p.tr_pt_off[u2 + 1]):
				var w: float = float(p.tr_pt_mass[g2])
				m += w
				a += w * ass[g2]
				if inc[g2] < 0.5 * median:
					poor += w
				bm += w
				if inc[g2] < 15.0:
					low += w
			if bm > 0.0:
				nb += bm
				nb_hit += bm * (1.0 if low > 0.5 * bm else (0.5 if low == 0.5 * bm else 0.0))
		out[scope] = {"assets": a / maxf(1.0, m), "poor": poor / maxf(1.0, m), "bundles": nb_hit / maxf(1.0, nb)}
	return out


func _init() -> void:
	var st = MS.new()
	st.load(2024, ["JPN"])
	var prefs: Dictionary = CANON.load_json("res://data/modern/polity/jpn_prefectures.json")["prefectures"]
	var seeds: int = int(OS.get_environment("SEEDS")) if OS.get_environment("SEEDS") != "" else 10
	var res := {}
	var ks: Array = [4, 8, 16]
	if OS.get_environment("KS") != "":
		ks = []
		for t: String in OS.get_environment("KS").split(","):
			ks.append(int(t))
	for k: int in ks:
		var rows: Array = []
		for sd: int in range(1, seeds + 1):
			var t0: int = Time.get_ticks_msec()
			var p = PEOPLE.new()
			p.tiers = true
			p.tier_k = k
			p.create("JPN", sd, st.cohort["JPN"], st.qx["JPN"], prefs, 0, 2024)
			var r: Dictionary = _readings(p)
			r["ms"] = Time.get_ticks_msec() - t0
			r["points"] = p.tr_pt_off[p.tr_units]
			rows.append(r)
			print("K %d seed %d %s" % [k, sd, JSON.stringify(r)])
		res[str(k)] = rows
	var f := FileAccess.open(OS.get_environment("OUT"), FileAccess.WRITE)
	f.store_string(JSON.stringify(res))
	f.close()
	quit()
