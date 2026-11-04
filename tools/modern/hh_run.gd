extends SceneTree
## The households' behaviour run (ISS_CHECKS.md HB1..HB11, ISS_HH_BEHAVIOUR.md): Japan's persons built by households inside the modern
## world for Y years, one table row per year (stocks at the year's end, flows over the year) and life stories from the life log.
##   godot --headless --path . --script res://tools/modern/hh_run.gd -- [--years 10] [--seed 1] [--n 2128] [--stories 5] [--out <dir>]
##     [--run <id>]   (the run id written on every row and line: the commit and the run's name, ruling H of 2026-10-29 23:45)
const MW = preload("res://sim/modern/modern_world.gd")
const HH = preload("res://sim/modern/people/households.gd")
const ALONE := [["M", 15, 24], ["M", 25, 34], ["M", 35, 44], ["M", 65, 74], ["M", 75, 84], ["M", 85, 200], ["F", 15, 24], ["F", 25, 34], ["F", 35, 44], ["F", 65, 74], ["F", 75, 84], ["F", 85, 200]]
const BIRTH_BANDS := [15, 20, 25, 30, 35, 40, 45, 50]


func _init() -> void:
	var a := {"years": "10", "seed": "1", "n": "2128", "stories": "5", "out": "", "run": ""}
	var args: PackedStringArray = OS.get_cmdline_user_args()
	for i: int in range(0, args.size() - 1, 2):
		a[args[i].trim_prefix("--")] = args[i + 1]
	var t0: int = Time.get_ticks_msec()
	var w = MW.new()
	var err: String = w.create(2024, {"view_salt": "0123456789abcdef0123456789abcdef", "people": true, "people_households": true, "people_seed": int(a["seed"]), "people_per_prefecture": int(a["n"])})
	if err != "":
		print("ERROR ", err)
		quit(1)
		return
	var p = w.people
	var out: PackedStringArray = PackedStringArray()
	out.append("RUN %s seed %s n %s years %s" % [a["run"], a["seed"], a["n"], a["years"]])
	out.append("CREATE %d persons, %d households, %d ms, memory %.0f MB" % [p.n, p.hh_n, Time.get_ticks_msec() - t0, OS.get_static_memory_usage() / 1048576.0])
	print(out[0])
	out.append(_stock_row(p, 0))
	print(out[out.size() - 1])
	var jl: PackedStringArray = PackedStringArray()
	var d0: Dictionary = _detail(p, 0, 0, 0, {}, {})
	d0["run"] = a["run"]
	jl.append(JSON.stringify(d0))
	var log_from: int = 0
	var birth_from: int = 0
	var deaths_by := {}
	var expo_by := {}
	for y: int in range(1, int(a["years"]) + 1):
		var t1: int = Time.get_ticks_msec()
		var expo0: Dictionary = _exposure(p)
		var pref0 := {}
		for i0: int in p.n:
			pref0[p.pid[i0]] = p.pref[i0]
		w.advance_to(365 * y)
		var expo1: Dictionary = _exposure(p)
		for k: String in expo0:
			expo_by[k] = float(expo_by.get(k, 0.0)) + 0.5 * (float(expo0[k]) + float(expo1.get(k, 0.0)))
		var flows: Dictionary = _flows(p, log_from, birth_from, expo0, expo1, deaths_by)
		var det: Dictionary = _detail(p, y, log_from, birth_from, expo0, expo1)
		det["run"] = a["run"]
		var mv := {}
		for i1: int in p.n:
			if pref0.has(p.pid[i1]):
				var b1: String = str(mini(p.age[i1] / 5, 20))
				var cell: Array = mv.get(b1, [0.0, 0.0, 0, 0])
				cell[1] += p.weight[i1]
				cell[3] += 1
				if int(pref0[p.pid[i1]]) != p.pref[i1]:
					cell[0] += p.weight[i1]
					cell[2] += 1
				mv[b1] = cell
		det["movers_by_band"] = mv
		jl.append(JSON.stringify(det))
		log_from = p.life_log.size()
		birth_from = p.lc_births.size()
		var ms: float = float(Time.get_ticks_msec() - t1) / 12.0
		out.append(_stock_row(p, y) + " | " + flows["text"] + " | %.1f s/month, %d persons, %.0f MB" % [ms / 1000.0, p.n, OS.get_static_memory_usage() / 1048576.0])
		print(out[out.size() - 1])
	out.append("E0 (years 1-%s pooled, unweighted rates by 5-year band): %s" % [a["years"], _e0(deaths_by, expo_by)])
	out.append_array(_stories(p, int(a["stories"])))
	print("\n".join(out.slice(out.size() - int(a["stories"]) - 1)))
	print("DIGEST %s" % p.digest())
	if String(a["out"]) != "":
		DirAccess.make_dir_recursive_absolute(String(a["out"]))
		var fh := FileAccess.open(String(a["out"]).path_join("hh_run.txt"), FileAccess.WRITE)
		fh.store_string("\n".join(out) + "\n")
		fh.close()
		var fj := FileAccess.open(String(a["out"]).path_join("hh_run.jsonl"), FileAccess.WRITE)
		fj.store_string("\n".join(jl) + "\n")
		fj.close()
	quit(0)


func _priv(p, i: int) -> bool:
	return p.hh_type[p.hh_id[i]] < HH.TYPES.size()


## The stocks at a year's end: HB1 types, HB2 size, HB1b alone cells, HB1c the 65+, HB5 never married, HB6 leaving home, HB8 symptoms, HB10
func _stock_row(p, y: int) -> String:
	var ts: Dictionary = HH.type_shares(p)
	var parts: PackedStringArray = PackedStringArray()
	parts.append("Y%d types %.3f/%.3f/%.3f/%.3f/%.3f size %.2f" % [y, ts["one_person"], ts["couple_only"], ts["couple_children"], ts["single_parent"], ts["other"], ts["mean_size"]])
	var al: PackedStringArray = PackedStringArray()
	for c: Array in ALONE:
		al.append("%.3f" % _share(p, func(i: int) -> bool: return p.sex[i] == (0 if c[0] == "M" else 1) and p.age[i] >= c[1] and p.age[i] <= c[2], func(i: int) -> bool: return p.hh_type[p.hh_id[i]] == 0))
	parts.append("alone " + "/".join(al))
	var o65 := func(i: int) -> bool: return p.age[i] >= 65 and _priv(p, i)
	var married_child := func(i: int) -> bool:
		var h: int = p.hh_id[i]
		if p.hh_role[i] != 3:
			return false
		for j: int in (p.hh_members[h] as PackedInt32Array):
			if p.hh_role[j] == 0 and p.partner[j] >= 0:
				return true
		return false
	var with_child := func(i: int) -> bool: return p.hh_type[p.hh_id[i]] >= 2 and p.hh_role[i] != 2
	parts.append("65+ alone %.3f couple %.3f child %.3f (married %.3f)" % [_share(p, o65, func(i: int) -> bool: return p.hh_type[p.hh_id[i]] == 0), _share(p, o65, func(i: int) -> bool: return p.hh_type[p.hh_id[i]] == 1), _share(p, o65, with_child), _share(p, o65, married_child)])
	var nm := PackedStringArray()
	for s: int in 2:
		nm.append("%.3f/%.3f" % [_share(p, func(i: int) -> bool: return p.sex[i] == s and p.age[i] >= 30 and p.age[i] <= 34, func(i: int) -> bool: return p.ever_married[i] == 0), _share(p, func(i: int) -> bool: return p.sex[i] == s and p.age[i] >= 45 and p.age[i] <= 54, func(i: int) -> bool: return p.ever_married[i] == 0)])
	parts.append("never married 30-34/45-54 M %s F %s" % [nm[0], nm[1]])
	var lh := PackedStringArray()
	for s2: int in 2:
		var cells := PackedStringArray()
		for b: Array in [[18, 19], [20, 24], [25, 29], [30, 34]]:
			cells.append("%.2f" % _share(p, func(i: int) -> bool: return p.sex[i] == s2 and p.age[i] >= b[0] and p.age[i] <= b[1], func(i: int) -> bool: return p.ever_left[i] == 1))
		lh.append("/".join(cells))
	var um := PackedStringArray()
	for s3: int in 2:
		um.append("%.3f" % _share(p, func(i: int) -> bool: return p.sex[i] == s3 and p.age[i] >= 18 and p.age[i] <= 34 and p.ever_married[i] == 0, func(i: int) -> bool: return p.hh_role[i] == 2))
	parts.append("ever left M %s F %s; unmarried 18-34 with a parent %s/%s" % [lh[0], lh[1], um[0], um[1]])
	var sy := PackedStringArray()
	for b2: int in 9:
		sy.append("%.2f" % _share(p, func(i: int) -> bool: return mini(p.age[i] / 10, 8) == b2, func(i: int) -> bool: return p.health[i] >= 1))
	parts.append("grade2+ by decade " + "/".join(sy))
	parts.append("women 85+ in an institution %.3f" % _share(p, func(i: int) -> bool: return p.sex[i] == 1 and p.age[i] >= 85, func(i: int) -> bool: return not _priv(p, i)))
	return " | ".join(parts)


## The Kish effective n of a domain, (sum w)^2 / sum w^2 over its persons: the n every share of it carries its SE on
func _neff(p, den: Callable) -> float:
	var sw: float = 0.0
	var sw2: float = 0.0
	for i: int in p.n:
		if den.call(i):
			sw += p.weight[i]
			sw2 += p.weight[i] * p.weight[i]
	return sw * sw / maxf(1e-9, sw2)


func _share(p, den: Callable, num: Callable) -> float:
	var d: float = 0.0
	var nn: float = 0.0
	for i: int in p.n:
		if den.call(i):
			d += p.weight[i]
			if num.call(i):
				nn += p.weight[i]
	return nn / maxf(1e-9, d)


## Unweighted persons by 5-year band x sex (the rates' denominators) and women by birth band
func _exposure(p) -> Dictionary:
	var e := {}
	for i: int in p.n:
		var k: String = "%d%s" % [mini(p.age[i] / 5, 20), "MF"[p.sex[i]]]
		e[k] = float(e.get(k, 0.0)) + 1.0
	return e


## The year's flows: HB3 births, HB4 deaths (pooled for e0), HB5 first partnerings, HB9 divorces
func _flows(p, log_from: int, birth_from: int, expo0: Dictionary, expo1: Dictionary, deaths_by: Dictionary) -> Dictionary:
	var births := PackedFloat64Array()
	births.resize(BIRTH_BANDS.size() - 1)
	var bw := PackedFloat64Array()
	bw.resize(BIRTH_BANDS.size() - 1)
	for e: Array in p.lc_births.slice(birth_from):
		for b: int in BIRTH_BANDS.size() - 1:
			if int(e[1]) >= BIRTH_BANDS[b] and int(e[1]) < BIRTH_BANDS[b + 1]:
				births[b] += 1.0
				bw[b] += float(e[2])
	var tfr: float = 0.0
	var btot: float = 0.0
	for b2: int in births.size():
		var k: String = "%dF" % (BIRTH_BANDS[b2] / 5)
		tfr += 5.0 * births[b2] / maxf(1.0, 0.5 * (float(expo0.get(k, 0.0)) + float(expo1.get(k, 0.0))))
		btot += bw[b2]
	var bsh := PackedStringArray()
	for b3: int in bw.size():
		bsh.append("%.3f" % (bw[b3] / maxf(1e-9, btot)))
	var fm := [[0.0, 0.0], [0.0, 0.0]]
	var div_w: float = 0.0
	var dur := [0.0, 0.0, 0.0]
	var counts := {}
	for e2: Array in p.life_log.slice(log_from):
		var kind: String = String(e2[2])
		counts[kind] = int(counts.get(kind, 0)) + 1
		var det: Variant = e2[4]
		if kind == "death":
			var k2: String = "%d%s" % [mini(int(det["age"]) / 5, 20), "MF"[_sex_of_log(p, e2)]]
			deaths_by[k2] = float(deaths_by.get(k2, 0.0)) + 1.0
		elif kind == "partnered" and bool(det["first"]):
			var sx: int = _sex_of_log(p, e2)
			if sx >= 0:
				fm[sx][0] += float(det["age"])
				fm[sx][1] += 1.0
		elif kind == "divorce":
			div_w += float(e2[5])
			var yrs: float = float(det["years"])
			dur[0] += float(e2[5]) if yrs < 5.0 else 0.0
			dur[1] += float(e2[5]) if yrs >= 20.0 else 0.0
			dur[2] += float(e2[5])
	var pop: float = 0.0
	for i: int in p.n:
		pop += p.weight[i]
	var txt: String = "TFR %.2f births %s | first partnering age M %.1f F %.1f (%d/%d) | divorces %.2f per 1,000, <5y %.2f, 20y+ %.2f | events %s" % [tfr, "/".join(bsh), fm[0][0] / maxf(1.0, fm[0][1]), fm[1][0] / maxf(1.0, fm[1][1]), int(fm[0][1]), int(fm[1][1]), 1000.0 * div_w / maxf(1.0, pop), dur[0] / maxf(1e-9, dur[2]), dur[1] / maxf(1e-9, dur[2]), str(counts)]
	return {"text": txt}


func _sex_of_log(_p, e: Array) -> int:
	return int(e[6])


func _e0(deaths: Dictionary, expo: Dictionary) -> String:
	var out := PackedStringArray()
	for s: String in ["M", "F"]:
		var lx: float = 1.0
		var e0: float = 0.0
		for b: int in 21:
			var k: String = "%d%s" % [b, s]
			var mx: float = float(deaths.get(k, 0.0)) / maxf(1.0, float(expo.get(k, 0.0)))
			if b == 20:
				e0 += lx / maxf(1e-6, mx)
				break
			var qx: float = clampf(5.0 * mx / (1.0 + 2.5 * mx), 0.0, 1.0)
			var l2: float = lx * (1.0 - qx)
			e0 += 2.5 * (lx + l2)
			lx = l2
		out.append("%s %.2f" % [s, e0])
	return ", ".join(out)


## Life stories: the persons alive at the end with the most logged events, their events in order (model output)
func _stories(p, k: int) -> PackedStringArray:
	var by := {}
	for e: Array in p.life_log:
		if not by.has(e[1]):
			by[e[1]] = []
		by[e[1]].append(e)
		if int(e[3]) >= 0 and String(e[2]) != "partnered":
			if not by.has(e[3]):
				by[e[3]] = []
			by[e[3]].append(e)
	var alive := {}
	for i: int in p.n:
		alive[p.pid[i]] = i
	var keys: Array = by.keys()
	keys.sort_custom(func(x, y2) -> bool: return (by[x] as Array).size() > (by[y2] as Array).size() or ((by[x] as Array).size() == (by[y2] as Array).size() and int(x) < int(y2)))
	var out := PackedStringArray()
	out.append("LIFE STORIES (model output: the persons with the most logged events)")
	var shown: int = 0
	for key in keys:
		if shown >= k:
			break
		var lines := PackedStringArray()
		var who: String = "pid %d" % int(key)
		if alive.has(key):
			var i2: int = alive[key]
			who += " (%s, now %d, pref %d, household type %d, grade %d)" % ["MF"[p.sex[i2]], p.age[i2], p.pref[i2], p.hh_type[p.hh_id[i2]], p.health[i2] + 1]
		for e2: Array in by[key]:
			lines.append("  m%d %s%s %s" % [int(e2[0]), String(e2[2]), "" if int(e2[1]) == int(key) else " (of %d)" % int(e2[1]), str(e2[4])])
		out.append(who)
		out.append_array(lines)
		shown += 1
	return out


## The year's numbers for the graphs (ISS roadmap 10.6): stocks by 5-year band at the year's end, the year's flows with their denominators
func _detail(p, y: int, log_from: int, birth_from: int, expo0: Dictionary, expo1: Dictionary) -> Dictionary:
	var d := {"year": 2024 + y, "run_year": y, "persons": p.n, "households": p.hh_n}
	var ts: Dictionary = HH.type_shares(p)
	d["types"] = [ts["one_person"], ts["couple_only"], ts["couple_children"], ts["single_parent"], ts["other"]]
	d["mean_size"] = ts["mean_size"]
	var bands5: Array = []
	for b: int in range(3, 13):
		bands5.append([5 * b, 5 * b + 4])
	var nm := [[], []]
	var left := [[], []]
	var alone := [[], []]
	var g4 := [[], []]
	for s: int in 2:
		for bb: Array in bands5:
			nm[s].append(_share(p, func(i: int) -> bool: return p.sex[i] == s and p.age[i] >= bb[0] and p.age[i] <= bb[1], func(i: int) -> bool: return p.ever_married[i] == 0))
		for bl: Array in [[18, 19], [20, 24], [25, 29], [30, 34], [35, 39]]:
			left[s].append(_share(p, func(i: int) -> bool: return p.sex[i] == s and p.age[i] >= bl[0] and p.age[i] <= bl[1], func(i: int) -> bool: return p.ever_left[i] == 1))
		for c: Array in ALONE:
			if (c[0] == "M") == (s == 0):
				alone[s].append(_share(p, func(i: int) -> bool: return p.sex[i] == s and p.age[i] >= c[1] and p.age[i] <= c[2], func(i: int) -> bool: return p.hh_type[p.hh_id[i]] == 0))
		for b4: int in range(0, 18):
			var lo: int = 5 * b4
			var hi: int = 200 if b4 == 17 else lo + 4
			g4[s].append(_share(p, func(i: int) -> bool: return p.sex[i] == s and p.age[i] >= lo and p.age[i] <= hi, func(i: int) -> bool: return p.health[i] == 3))
	d["never_married_bands"] = bands5
	d["never_married"] = nm
	d["ever_left"] = left
	d["alone"] = alone
	d["grade4_5y"] = g4
	var o65 := func(i: int) -> bool: return p.age[i] >= 65 and _priv(p, i)
	d["old_65"] = [_share(p, o65, func(i: int) -> bool: return p.hh_type[p.hh_id[i]] == 0), _share(p, o65, func(i: int) -> bool: return p.hh_type[p.hh_id[i]] == 1), _share(p, o65, func(i: int) -> bool: return p.hh_type[p.hh_id[i]] >= 2 and p.hh_role[i] != 2)]
	d["inst_women_85"] = _share(p, func(i: int) -> bool: return p.sex[i] == 1 and p.age[i] >= 85, func(i: int) -> bool: return not _priv(p, i))
	var pop: float = 0.0
	for i2: int in p.n:
		pop += p.weight[i2]
	d["population"] = pop
	d["kish"] = HH.kish(p)
	var wives := {}
	for i5: int in p.n:
		if p.sex[i5] == 1 and p.partner[i5] >= 0:
			var b5: String = str(mini(p.age[i5] / 5 * 5, 65))
			wives[b5] = float(wives.get(b5, 0.0)) + p.weight[i5]
	d["married_wives"] = wives
	var nmw := [{}, {}]
	for i8: int in p.n:
		if p.ever_married[i8] == 0 and p.age[i8] >= 15:
			var b8: String = str(mini(p.age[i8] / 5, 20))
			nmw[p.sex[i8]][b8] = float(nmw[p.sex[i8]].get(b8, 0.0)) + p.weight[i8]
	d["never_married_w"] = nmw
	var el := []
	var um := [[], []]
	for s7: int in 2:
		el.append(_share(p, func(i: int) -> bool: return p.sex[i] == s7 and p.age[i] >= 25 and p.age[i] <= 27, func(i: int) -> bool: return p.ever_left[i] == 1))
		for r7: Array in [[18, 27], [18, 34]]:
			um[s7].append(_share(p, func(i: int) -> bool: return p.sex[i] == s7 and p.age[i] >= r7[0] and p.age[i] <= r7[1] and p.ever_married[i] == 0, func(i: int) -> bool: return p.hh_role[i] == 2))
	d["ever_left_25_27"] = el
	d["unmarried_with_parent"] = {"bands": [[18, 27], [18, 34]], "men": um[0], "women": um[1]}
	var g2 := []
	for b8: int in 9:
		g2.append(_share(p, func(i: int) -> bool: return mini(p.age[i] / 10, 8) == b8, func(i: int) -> bool: return p.health[i] >= 1))
	d["grade2_by_decade"] = g2
	var ne := {"alone": [], "never_married_30_34": [], "ever_left": [[], []], "grade2": []}
	for c9: Array in ALONE:
		ne["alone"].append(_neff(p, func(i: int) -> bool: return p.sex[i] == (0 if c9[0] == "M" else 1) and p.age[i] >= c9[1] and p.age[i] <= c9[2]))
	ne["old_65"] = _neff(p, o65)
	for s9: int in 2:
		ne["never_married_30_34"].append(_neff(p, func(i: int) -> bool: return p.sex[i] == s9 and p.age[i] >= 30 and p.age[i] <= 34))
		for r9: Array in [[18, 19], [20, 24], [25, 27]]:
			ne["ever_left"][s9].append(_neff(p, func(i: int) -> bool: return p.sex[i] == s9 and p.age[i] >= r9[0] and p.age[i] <= r9[1]))
	for b9: int in [3, 4, 5]:
		ne["grade2"].append(_neff(p, func(i: int) -> bool: return mini(p.age[i] / 10, 8) == b9))
	d["neff"] = ne
	if y == 0:
		return d
	var births := PackedFloat64Array()
	births.resize(BIRTH_BANDS.size() - 1)
	var bw := PackedFloat64Array()
	bw.resize(BIRTH_BANDS.size() - 1)
	for e: Array in p.lc_births.slice(birth_from):
		for b2: int in BIRTH_BANDS.size() - 1:
			if int(e[1]) >= BIRTH_BANDS[b2] and int(e[1]) < BIRTH_BANDS[b2 + 1]:
				births[b2] += 1.0
				bw[b2] += float(e[2])
	var women := []
	for b3: int in births.size():
		var k: String = "%dF" % (BIRTH_BANDS[b3] / 5)
		women.append(0.5 * (float(expo0.get(k, 0.0)) + float(expo1.get(k, 0.0))))
	d["births_by_mother_age"] = Array(births)
	d["births_weighted"] = Array(bw)
	d["women_by_band"] = women
	var deaths := {}
	var first := [[], []]
	var first_w := [{}, {}]
	var first_re := [[0.0, 0.0], [0.0, 0.0]]
	var events := {}
	var div := []
	for e2: Array in p.life_log.slice(log_from):
		var kind: String = String(e2[2])
		events[kind] = float(events.get(kind, 0.0)) + float(e2[5])
		var det: Variant = e2[4]
		if kind == "death":
			var k2: String = "%d%s" % [mini(int(det["age"]) / 5, 20), "MF"[int(e2[6])]]
			deaths[k2] = float(deaths.get(k2, 0.0)) + 1.0
		elif kind == "partnered" and bool(det["first"]):
			first_re[int(e2[6])][0] += float(e2[5])
			first[int(e2[6])].append(int(det["age"]))
			var bf: String = str(mini(int(det["age"]) / 5, 20))
			first_w[int(e2[6])][bf] = float(first_w[int(e2[6])].get(bf, 0.0)) + float(e2[5])
		elif kind == "partnered":
			first_re[int(e2[6])][1] += float(e2[5])
		elif kind == "divorce":
			div.append([float(det["years"]), float(e2[5]), int(det.get("wife_age", -1))])
	d["deaths"] = deaths
	var ex := {}
	for k3: String in expo0:
		ex[k3] = 0.5 * (float(expo0[k3]) + float(expo1.get(k3, 0.0)))
	d["exposure"] = ex
	d["first_partnering_ages"] = first
	d["first_partnering_w"] = first_w
	d["partnered_first_re"] = first_re
	d["events_weighted"] = events
	d["divorces"] = div
	return d
