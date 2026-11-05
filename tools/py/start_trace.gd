extends SceneTree
## The start's trace (START_PORT_PLAN §2): people.create's tiers start at the frozen oracle, with TR.build_start's body copied here
## so its stages can be checked one by one. At each stage it writes every tr_* field's SHA-256 (tr_margins without its "usec" keys),
## each person array's, and the stage's locals', in oracle_dump.gd's canonical bytes; TRACE_FULL lists the stages whose whole state is
## also written as a typed tree, so a Python stage can start from the oracle's inputs.
##   TRACE_OUT=outputs/py_oracle/<tag> [TRACE_FULL=08_units,12_points] godot --headless --path . --script res://tools/py/start_trace.gd
## Why a copy of build_start and not a hook in tiers.gd: tiers.gd is frozen at cd165891 (D475); the final stage's tr_* hashes must
## equal oracle_dump.gd's m00, which shows the copy is the start (row S0-t)
const PEOPLE = preload("res://sim/modern/people/people.gd")
const MS = preload("res://sim/modern/modern_status.gd")
const CANON = preload("res://sim/modern/canon.gd")
const TR = preload("res://sim/modern/people/tiers.gd")
const HH = preload("res://sim/modern/people/households.gd")

var _out: String = ""
var _full: Array = []
var _files: int = 0


func _init() -> void:
	_out = OS.get_environment("TRACE_OUT")
	for s: String in OS.get_environment("TRACE_FULL").split(",", false):
		_full.append(s)
	DirAccess.make_dir_recursive_absolute(_out)
	var st = MS.new()
	st.load(2024, ["JPN"])
	var prefectures: Dictionary = CANON.load_json("res://data/modern/polity/jpn_prefectures.json")["prefectures"]
	var p = PEOPLE.new()
	p.tiers = true
	var t0: int = Time.get_ticks_usec()
	# people.create up to _create_tiers, as at cd165891 (people.gd 447-460, 506-519)
	if p.load_spec("JPN") != "":
		push_error("start_trace: " + p.error)
		quit(1)
		return
	p.seed_v = 1
	p.base_year = 2024
	p.cohort = (st.cohort["JPN"] as PackedFloat64Array).duplicate()
	p.qx = (st.qx["JPN"] as PackedFloat64Array).duplicate()
	p.pref_codes = prefectures.keys()
	p.pref_codes.sort()
	if TR.load_spec(p) != "" or HH.load_spec(p) != "":
		push_error("start_trace: no spec")
		quit(1)
		return
	for code: String in p.pref_codes:
		p.pref_pop[int(code)] = float(prefectures[code]["pop_thousand"]) * 1000.0
	_ck(p, "00_inputs", {"prefectures": prefectures})
	_build_start(p, prefectures)
	for i: int in p.n:
		p.weight[i] = 1.0
	_ck(p, "19_weights", {})
	print("TRACE done usec %d units %d" % [Time.get_ticks_usec() - t0, p.tr_units])
	quit(0)


## TR.build_start's body at cd165891 (tiers.gd 60-299), each call qualified with TR., and the stage checks added
func _build_start(p: RefCounted, prefectures: Dictionary) -> void:
	var K: int = p.tier_k if p.tier_k > 0 else int(TR._v(p, "k_points"))
	p.tr_k = K
	var cls: Dictionary = TR._v(p, "classes")
	var emp_bs: Array = TR._v(p, "employment_by_band_sex")
	var adult_shares: Array = cls["adult_shares"]
	var ctot: float = 0.0
	for a0: int in p.cohort.size():
		ctot += p.cohort[a0]
	# the band x sex shape of the cohort (S), applied to every prefecture (T: by prefecture NF)
	var band_share := PackedFloat64Array()
	band_share.resize(TR.BANDS * 2)
	for a: int in p.AGES:
		for s: int in 2:
			band_share[TR.band_of(a) * 2 + s] += p.cohort[a * p.SEXES + s] / ctot
	var age_in_band := PackedFloat64Array()   # the share of each single age within its band, for the single-year counts
	age_in_band.resize(p.AGES * 2)
	for a2: int in p.AGES:
		for s2: int in 2:
			var bs: float = band_share[TR.band_of(a2) * 2 + s2]
			age_in_band[a2 * 2 + s2] = (p.cohort[a2 * p.SEXES + s2] / ctot) / bs if bs > 0.0 else 0.0
	# the seed on (prefecture, band x sex, type): pop x shape x P(type | band, sex) (T, stated); employment and class are factors
	# inside each cell
	var codes: Array = []
	for code: String in prefectures:
		codes.append(int(code))
	codes.sort()
	var nc: int = codes.size()
	var nbs: int = TR.BANDS * 2
	var base: PackedFloat64Array = TR._base(p, codes, prefectures, band_share)
	var emp_c: Array = TR._employment(p, base, codes, emp_bs)
	_ck(p, "01_base", {"K": K, "cls": cls, "emp_bs": emp_bs, "adult_shares": adult_shares, "ctot": ctot, "band_share": band_share, "age_in_band": age_in_band, "codes": codes, "nc": nc, "nbs": nbs, "base": base, "emp_c": emp_c})
	# the couples first (§12.12): integer couples by (prefecture, husband band, wife band, type), their persons fixed cells; the seed
	# is the persons in no couple, P(type | band, sex) less the couples' share of the cell, floored at 0 and renormalised; the
	# couple-only type holds couples only, so its seed is 0
	var cp: Dictionary = TR._r77_couples(p, codes, base)
	var fixed: PackedInt64Array = cp["fixed"]
	p.tr_couples = cp["couples"]
	p.tr_nh_couples = cp["nonhead"]
	p.tr_margins["h4s"] = cp["h4s"]
	_ck(p, "02_couples", {"K": K, "cls": cls, "emp_bs": emp_bs, "adult_shares": adult_shares, "ctot": ctot, "band_share": band_share, "age_in_band": age_in_band, "codes": codes, "nc": nc, "nbs": nbs, "base": base, "emp_c": emp_c, "cp": cp, "fixed": fixed})
	var five: Array = TR._completed_shares(p, TR._five_shares(p), base, nc)
	var sd: Array = TR._seed(nc, base, fixed, five)
	var y: PackedFloat64Array = sd[0]
	p.tr_residual = TR._fit(p, y, codes, prefectures, fixed, base, five)
	_ck(p, "03_fit", {"K": K, "cls": cls, "emp_bs": emp_bs, "adult_shares": adult_shares, "ctot": ctot, "band_share": band_share, "age_in_band": age_in_band, "codes": codes, "nc": nc, "nbs": nbs, "base": base, "emp_c": emp_c, "cp": cp, "fixed": fixed, "five": five, "sd": sd, "y": y})
	# §12.13 (c), TO_E 14:10: type 2's head couples at most the prefecture's type-2 persons in no couple (its children), the excess to
	# type 4 and the fit once more
	var moved: Dictionary = TR._type2_cap(p, codes, y, fixed)
	if not moved.is_empty():
		sd = TR._seed(nc, base, fixed, five)
		y = sd[0]
		p.tr_residual = TR._fit(p, y, codes, prefectures, fixed, base, five)
	var floor_moved: Dictionary = TR._size_floor(p, codes, y, fixed)
	var floor_excess: float = sd[1]
	_ck(p, "04_cap_floor", {"K": K, "cls": cls, "emp_bs": emp_bs, "adult_shares": adult_shares, "ctot": ctot, "band_share": band_share, "age_in_band": age_in_band, "codes": codes, "nc": nc, "nbs": nbs, "base": base, "emp_c": emp_c, "cp": cp, "fixed": fixed, "five": five, "sd": sd, "y": y, "moved": moved, "floor_moved": floor_moved, "floor_excess": floor_excess})
	var ten_shift: float = float(p.tr_margins.get("ten_shift", 0.0))
	var one_rake: Array = p.tr_margins.get("one_rake", [])
	var yi: PackedInt64Array = TR._round(p, y, codes, prefectures, base, fixed)
	_ck(p, "05_round", {"K": K, "cls": cls, "emp_bs": emp_bs, "adult_shares": adult_shares, "ctot": ctot, "band_share": band_share, "age_in_band": age_in_band, "codes": codes, "nc": nc, "nbs": nbs, "base": base, "emp_c": emp_c, "cp": cp, "fixed": fixed, "five": five, "sd": sd, "y": y, "moved": moved, "floor_moved": floor_moved, "floor_excess": floor_excess, "ten_shift": ten_shift, "one_rake": one_rake, "yi": yi})
	p.tr_margins["ten_shift"] = ten_shift
	p.tr_margins["one_rake"] = one_rake
	p.tr_margins["t2_clip"] = cp["t2_clip"]
	p.tr_margins["c24_clip"] = cp["c24_clip"]
	p.tr_margins["h4s"] = cp["h4s"]
	p.tr_margins["floor_moved"] = floor_moved
	p.tr_margins["r77_floor_excess"] = floor_excess
	p.tr_margins["r77_couples"] = cp["total"]
	p.tr_margins["r77_rake"] = cp["rake"]
	p.tr_margins["n4"] = cp["n4"]
	p.tr_margins["n4_cap"] = moved
	p.tr_margins["nh_clip"] = cp["nh_clip"]
	# the class of an adult from the generator's own income law (§12.8 item 3): the national class lines solved over the adults'
	# laws weighted by their counts, then P(class | band, sex, employment) for the cell split
	var tab: PackedFloat64Array = TR._phi_table()
	var mass: Dictionary = {}
	for ci7: int in nc:
		for bs7: int in nbs:
			if bs7 / 2 * 5 < TR.ADULT_FROM:
				continue
			var n7: float = 0.0
			for t7: int in TR.NTYPE:
				n7 += float(yi[(ci7 * nbs + bs7) * TR.NTYPE + t7])
			var er7: PackedFloat64Array = emp_c[ci7][bs7 % 2][bs7 / 2]
			var et7: float = 0.0
			for e7: int in TR.NEMP:
				et7 += maxf(0.0, er7[e7])
			for e8: int in TR.NEMP:
				if et7 > 0.0 and er7[e8] > 0.0:
					mass[bs7 * TR.NEMP + e8] = float(mass.get(bs7 * TR.NEMP + e8, 0.0)) + n7 * er7[e8] / et7
	var laws: Dictionary = {}
	for kl: int in mass:
		laws[kl] = TR._income_law(p, kl / TR.NEMP / 2, (kl / TR.NEMP) % 2, kl % TR.NEMP, age_in_band)
	var lines: PackedFloat64Array = TR._class_lines(tab, laws, mass, adult_shares)
	var pk: Dictionary = {}
	for kl2: int in laws:
		pk[kl2] = TR._class_probs(tab, laws[kl2], lines)
	p.tr_margins["class_lines"] = lines
	var tm: Dictionary = TR._tail_map(p, tab, laws, mass, lines, adult_shares)
	_ck(p, "06_class", {"K": K, "cls": cls, "emp_bs": emp_bs, "adult_shares": adult_shares, "ctot": ctot, "band_share": band_share, "age_in_band": age_in_band, "codes": codes, "nc": nc, "nbs": nbs, "base": base, "emp_c": emp_c, "cp": cp, "fixed": fixed, "five": five, "sd": sd, "y": y, "moved": moved, "floor_moved": floor_moved, "floor_excess": floor_excess, "ten_shift": ten_shift, "one_rake": one_rake, "yi": yi, "tab": tab, "mass": mass, "laws": laws, "lines": lines, "pk": pk, "tm": tm})
	# each integer (prefecture, band, sex, type) cell split over employment x class by keyed systematic rounding
	var cells: Dictionary = {}   # key string -> [pref, band, sex, class, type, emp, count]
	var top_real: float = 0.0
	var top_cand: Array = []
	for ci2: int in nc:
		for bs2: int in nbs:
			var b: int = bs2 / 2
			var s3: int = bs2 % 2
			var adult: bool = b * 5 + 4 >= TR.ADULT_FROM
			for t3: int in TR.NTYPE:
				var n0: int = yi[(ci2 * nbs + bs2) * TR.NTYPE + t3]
				if n0 <= 0:
					continue
				var sub := PackedFloat64Array()
				var tags: Array = []
				var erow: PackedFloat64Array = emp_c[ci2][s3][b]
				var etot: float = 0.0
				for e: int in TR.NEMP:
					etot += maxf(0.0, erow[e])
				for e2: int in TR.NEMP:
					var pe: float = maxf(0.0, erow[e2]) / etot if etot > 0.0 else (1.0 if e2 == 0 else 0.0)
					if pe <= 0.0:
						continue
					if not adult:
						sub.append(float(n0) * pe)
						tags.append([TR.CLASS_NONE, e2])
					else:
						for k: int in TR.NCLASS - 1:
							sub.append(float(n0) * pe * float(pk.get(bs2 * TR.NEMP + e2, PackedFloat64Array([0.0, 0.0, 0.0, 0.0, 0.0, 1.0]))[k]))
							tags.append([k, e2])
				var ints: PackedInt64Array = TR._systematic(sub, n0, p.seed_v, "tier_cell", (ci2 * nbs + bs2) * TR.NTYPE + t3)
				for q: int in ints.size():
					if ints[q] > 0:
						TR._cell_add(cells, codes[ci2], b, s3, int(tags[q][0]), t3, int(tags[q][1]), float(ints[q]))
					if adult and int(tags[q][0]) == 0:
						top_real += sub[q]
						top_cand.append([sub[q], codes[ci2], b, s3, t3, int(tags[q][1])])
	TR._hold_top(p, cells, top_real, top_cand)
	_ck(p, "07_cells", {"K": K, "cls": cls, "emp_bs": emp_bs, "adult_shares": adult_shares, "ctot": ctot, "band_share": band_share, "age_in_band": age_in_band, "codes": codes, "nc": nc, "nbs": nbs, "base": base, "emp_c": emp_c, "cp": cp, "fixed": fixed, "five": five, "sd": sd, "y": y, "moved": moved, "floor_moved": floor_moved, "floor_excess": floor_excess, "ten_shift": ten_shift, "one_rake": one_rake, "yi": yi, "tab": tab, "mass": mass, "laws": laws, "lines": lines, "pk": pk, "tm": tm, "cells": cells, "top_real": top_real, "top_cand": top_cand})
	# the units at E (§12.7): the top tiers keyed (pref, band, sex, class), the rest 90% one class, persons under 20 without employment;
	# each unit's mix holds the integer counts of the (class, type, employment) combinations its key merges
	var groups: Dictionary = {}
	for ks: String in cells:
		var cell: Array = cells[ks]
		var n: int = int(cell[6])
		if n <= 0:
			continue
		var k: int = int(cell[3])
		var t: int = int(cell[4])
		var e: int = int(cell[5])
		var gk: int = k
		var gt: int = t
		var ge: int = e
		if k < TR.CLASS_REST:
			gt = -1
			ge = -1
		elif k < TR.CLASS_NONE:
			gk = TR.CLASS_REST
			if int(cell[1]) >= TR.EMP_KEY_UNTIL_BAND:
				ge = -1
		else:
			ge = -1
		var gs: String = "%02d|%02d|%d|%d|%d|%d" % [int(cell[0]), int(cell[1]), int(cell[2]), gk, gt + 1, ge + 1]
		if not groups.has(gs):
			groups[gs] = [int(cell[0]), int(cell[1]), int(cell[2]), gk, gt, ge, {}]
		var mix: Dictionary = groups[gs][6]
		var code: int = (k * TR.NTYPE + t) * TR.NEMP + e
		mix[code] = int(mix.get(code, 0)) + n
	var keys: Array = groups.keys()
	keys.sort()
	p.tr_units = 0
	p.tr_key = PackedInt32Array()
	p.tr_count = PackedInt64Array()
	p.tr_age_counts = PackedInt64Array()
	p.tr_never_married = PackedFloat64Array()
	p.tr_married_apart = PackedFloat64Array()
	p.tr_tier_size = PackedInt32Array()
	p.tr_mix_off = PackedInt64Array()
	p.tr_mix_code = PackedInt32Array()
	p.tr_mix_n = PackedInt64Array()
	var unit_size: Array = cls["unit_size"]
	for gi: int in keys.size():
		var g: Array = groups[keys[gi]]
		var mixg: Dictionary = g[6]
		var mcodes: Array = mixg.keys()
		mcodes.sort()
		var n2: int = 0
		for mc: int in mcodes:
			n2 += int(mixg[mc])
		var us: int = int(unit_size[int(g[3])])
		var parts: int = 1 if us <= 0 else maxi(1, int(round(float(n2) / float(us))))
		# a top tier's merged cell splits into sub-bundles of the ladder's size: each combination dealt evenly over the parts, the
		# remainders laid round the parts from a keyed start, so the parts' totals differ by one at most
		var split: Array = []
		for q: int in parts:
			split.append({})
		var off: int = p.KEYED.below(parts, p.seed_v, "tier_part", gi, 0, 0)
		for mc2: int in mcodes:
			var nc2: int = int(mixg[mc2])
			var r: int = nc2 % parts
			for q2: int in parts:
				var add: int = nc2 / parts + (1 if (q2 - off + parts) % parts < r else 0)
				if add > 0:
					split[q2][mc2] = add
			off = (off + r) % parts
		for q3: int in parts:
			var sm: Dictionary = split[q3]
			var share: int = 0
			for mc3 in sm:
				share += int(sm[mc3])
			if share <= 0:
				continue
			for f: int in TR.KEY_STRIDE:
				p.tr_key.append(int(g[f]))
			p.tr_count.append(share)
			p.tr_tier_size.append(us)
			p.tr_mix_off.append(p.tr_mix_code.size())
			var sk: Array = sm.keys()
			sk.sort()
			for mc4: int in sk:
				p.tr_mix_code.append(mc4)
				p.tr_mix_n.append(int(sm[mc4]))
			var b2: int = int(g[1])
			var s4: int = int(g[2])
			var av := PackedFloat64Array()
			av.resize(TR.AGE_SLOTS)
			for a3: int in range(b2 * 5, p.AGES if b2 == TR.BANDS - 1 else b2 * 5 + 5):
				av[a3 - b2 * 5] += float(share) * age_in_band[a3 * 2 + s4]
			# Why not the last age taking the rounding: it went to -1 in 390 of 239,480 slots (V104)
			# Why not the largest remainder: like units (same count, same shares) gave the +1 to the same ages, 1,148 persons at age 52
			# nationally and 47 of 101 ages beyond an unbiased rounding's bound (§12.10 V3)
			p.tr_age_counts.append_array(TR._systematic(av, share, p.seed_v, "tier_age_split", p.tr_units))
			p.tr_units += 1
	p.tr_mix_off.append(p.tr_mix_code.size())
	_ck(p, "08_units", {"K": K, "cls": cls, "emp_bs": emp_bs, "adult_shares": adult_shares, "ctot": ctot, "band_share": band_share, "age_in_band": age_in_band, "codes": codes, "nc": nc, "nbs": nbs, "base": base, "emp_c": emp_c, "cp": cp, "fixed": fixed, "five": five, "sd": sd, "y": y, "moved": moved, "floor_moved": floor_moved, "floor_excess": floor_excess, "ten_shift": ten_shift, "one_rake": one_rake, "yi": yi, "tab": tab, "mass": mass, "laws": laws, "lines": lines, "pk": pk, "tm": tm, "cells": cells, "top_real": top_real, "top_cand": top_cand, "groups": groups, "keys": keys, "unit_size": unit_size})
	TR._individuals(p, lines, tab)
	_ck(p, "09_individuals", {"K": K, "cls": cls, "emp_bs": emp_bs, "adult_shares": adult_shares, "ctot": ctot, "band_share": band_share, "age_in_band": age_in_band, "codes": codes, "nc": nc, "nbs": nbs, "base": base, "emp_c": emp_c, "cp": cp, "fixed": fixed, "five": five, "sd": sd, "y": y, "moved": moved, "floor_moved": floor_moved, "floor_excess": floor_excess, "ten_shift": ten_shift, "one_rake": one_rake, "yi": yi, "tab": tab, "mass": mass, "laws": laws, "lines": lines, "pk": pk, "tm": tm, "cells": cells, "top_real": top_real, "top_cand": top_cand, "groups": groups, "keys": keys, "unit_size": unit_size})
	TR._drop_empty(p)
	_ck(p, "10_drop_empty", {"K": K, "cls": cls, "emp_bs": emp_bs, "adult_shares": adult_shares, "ctot": ctot, "band_share": band_share, "age_in_band": age_in_band, "codes": codes, "nc": nc, "nbs": nbs, "base": base, "emp_c": emp_c, "cp": cp, "fixed": fixed, "five": five, "sd": sd, "y": y, "moved": moved, "floor_moved": floor_moved, "floor_excess": floor_excess, "ten_shift": ten_shift, "one_rake": one_rake, "yi": yi, "tab": tab, "mass": mass, "laws": laws, "lines": lines, "pk": pk, "tm": tm, "cells": cells, "top_real": top_real, "top_cand": top_cand, "groups": groups, "keys": keys, "unit_size": unit_size})
	p.tr_residual.append(TR._class_residual(p, adult_shares))
	_ck(p, "11_class_residual", {"K": K, "cls": cls, "emp_bs": emp_bs, "adult_shares": adult_shares, "ctot": ctot, "band_share": band_share, "age_in_band": age_in_band, "codes": codes, "nc": nc, "nbs": nbs, "base": base, "emp_c": emp_c, "cp": cp, "fixed": fixed, "five": five, "sd": sd, "y": y, "moved": moved, "floor_moved": floor_moved, "floor_excess": floor_excess, "ten_shift": ten_shift, "one_rake": one_rake, "yi": yi, "tab": tab, "mass": mass, "laws": laws, "lines": lines, "pk": pk, "tm": tm, "cells": cells, "top_real": top_real, "top_cand": top_cand, "groups": groups, "keys": keys, "unit_size": unit_size})
	TR._points(p, lines, tab, tm)
	_ck(p, "12_points", {"K": K, "cls": cls, "emp_bs": emp_bs, "adult_shares": adult_shares, "ctot": ctot, "band_share": band_share, "age_in_band": age_in_band, "codes": codes, "nc": nc, "nbs": nbs, "base": base, "emp_c": emp_c, "cp": cp, "fixed": fixed, "five": five, "sd": sd, "y": y, "moved": moved, "floor_moved": floor_moved, "floor_excess": floor_excess, "ten_shift": ten_shift, "one_rake": one_rake, "yi": yi, "tab": tab, "mass": mass, "laws": laws, "lines": lines, "pk": pk, "tm": tm, "cells": cells, "top_real": top_real, "top_cand": top_cand, "groups": groups, "keys": keys, "unit_size": unit_size})
	TR._transfers(p)
	_ck(p, "13_transfers", {"K": K, "cls": cls, "emp_bs": emp_bs, "adult_shares": adult_shares, "ctot": ctot, "band_share": band_share, "age_in_band": age_in_band, "codes": codes, "nc": nc, "nbs": nbs, "base": base, "emp_c": emp_c, "cp": cp, "fixed": fixed, "five": five, "sd": sd, "y": y, "moved": moved, "floor_moved": floor_moved, "floor_excess": floor_excess, "ten_shift": ten_shift, "one_rake": one_rake, "yi": yi, "tab": tab, "mass": mass, "laws": laws, "lines": lines, "pk": pk, "tm": tm, "cells": cells, "top_real": top_real, "top_cand": top_cand, "groups": groups, "keys": keys, "unit_size": unit_size})
	TR._households(p)
	_ck(p, "14_households", {"K": K, "cls": cls, "emp_bs": emp_bs, "adult_shares": adult_shares, "ctot": ctot, "band_share": band_share, "age_in_band": age_in_band, "codes": codes, "nc": nc, "nbs": nbs, "base": base, "emp_c": emp_c, "cp": cp, "fixed": fixed, "five": five, "sd": sd, "y": y, "moved": moved, "floor_moved": floor_moved, "floor_excess": floor_excess, "ten_shift": ten_shift, "one_rake": one_rake, "yi": yi, "tab": tab, "mass": mass, "laws": laws, "lines": lines, "pk": pk, "tm": tm, "cells": cells, "top_real": top_real, "top_cand": top_cand, "groups": groups, "keys": keys, "unit_size": unit_size})
	TR._never_married(p)
	_ck(p, "15_never_married", {"K": K, "cls": cls, "emp_bs": emp_bs, "adult_shares": adult_shares, "ctot": ctot, "band_share": band_share, "age_in_band": age_in_band, "codes": codes, "nc": nc, "nbs": nbs, "base": base, "emp_c": emp_c, "cp": cp, "fixed": fixed, "five": five, "sd": sd, "y": y, "moved": moved, "floor_moved": floor_moved, "floor_excess": floor_excess, "ten_shift": ten_shift, "one_rake": one_rake, "yi": yi, "tab": tab, "mass": mass, "laws": laws, "lines": lines, "pk": pk, "tm": tm, "cells": cells, "top_real": top_real, "top_cand": top_cand, "groups": groups, "keys": keys, "unit_size": unit_size})
	TR._married_apart(p)
	_ck(p, "16_married_apart", {"K": K, "cls": cls, "emp_bs": emp_bs, "adult_shares": adult_shares, "ctot": ctot, "band_share": band_share, "age_in_band": age_in_band, "codes": codes, "nc": nc, "nbs": nbs, "base": base, "emp_c": emp_c, "cp": cp, "fixed": fixed, "five": five, "sd": sd, "y": y, "moved": moved, "floor_moved": floor_moved, "floor_excess": floor_excess, "ten_shift": ten_shift, "one_rake": one_rake, "yi": yi, "tab": tab, "mass": mass, "laws": laws, "lines": lines, "pk": pk, "tm": tm, "cells": cells, "top_real": top_real, "top_cand": top_cand, "groups": groups, "keys": keys, "unit_size": unit_size})
	TR._instruments(p)
	_ck(p, "17_instruments", {"K": K, "cls": cls, "emp_bs": emp_bs, "adult_shares": adult_shares, "ctot": ctot, "band_share": band_share, "age_in_band": age_in_band, "codes": codes, "nc": nc, "nbs": nbs, "base": base, "emp_c": emp_c, "cp": cp, "fixed": fixed, "five": five, "sd": sd, "y": y, "moved": moved, "floor_moved": floor_moved, "floor_excess": floor_excess, "ten_shift": ten_shift, "one_rake": one_rake, "yi": yi, "tab": tab, "mass": mass, "laws": laws, "lines": lines, "pk": pk, "tm": tm, "cells": cells, "top_real": top_real, "top_cand": top_cand, "groups": groups, "keys": keys, "unit_size": unit_size})
	TR.build_t21(p)
	_ck(p, "18_t21", {"K": K, "cls": cls, "emp_bs": emp_bs, "adult_shares": adult_shares, "ctot": ctot, "band_share": band_share, "age_in_band": age_in_band, "codes": codes, "nc": nc, "nbs": nbs, "base": base, "emp_c": emp_c, "cp": cp, "fixed": fixed, "five": five, "sd": sd, "y": y, "moved": moved, "floor_moved": floor_moved, "floor_excess": floor_excess, "ten_shift": ten_shift, "one_rake": one_rake, "yi": yi, "tab": tab, "mass": mass, "laws": laws, "lines": lines, "pk": pk, "tm": tm, "cells": cells, "top_real": top_real, "top_cand": top_cand, "groups": groups, "keys": keys, "unit_size": unit_size})



func _strip_usec(v: Variant) -> Variant:
	if v is Dictionary:
		var d := {}
		for k in v:
			if k is String and (k as String).begins_with("usec"):
				continue
			d[k] = _strip_usec(v[k])
		return d
	return v


func _ck(p: RefCounted, stage: String, locals: Dictionary) -> void:
	var lines := ""
	var names: Array = []
	for prop: Dictionary in p.get_property_list():
		var n: String = prop["name"]
		if n.begins_with("tr_"):
			names.append(n)
	names.sort()
	for n: String in names:
		lines += "%s %s\n" % [n, _sha(_strip_usec(p.get(n)) if n == "tr_margins" else p.get(n))]
	var pf: Array = []
	for row: Array in p.fields():
		pf.append(String(row[0]))
	pf.sort()
	for n2: String in pf:
		lines += "persons.%s %s\n" % [n2, _sha(p.get(n2))]
	for n3: String in ["n", "pref_pop", "pension", "wage_index", "price_index", "spec", "hh_spec", "seed_v", "base_year", "month"]:
		lines += "persons.%s %s\n" % [n3, _sha(p.get(n3))]
	var lk: Array = locals.keys()
	lk.sort()
	for n4: String in lk:
		lines += "local.%s %s\n" % [n4, _sha(locals[n4])]
	var f := FileAccess.open("%s/%s.sha.txt" % [_out, stage], FileAccess.WRITE)
	f.store_string(lines)
	f.close()
	if stage in _full:
		var dir: String = "%s/%s" % [_out, stage]
		DirAccess.make_dir_recursive_absolute(dir)
		_files = 0
		var tree := {}
		for n5: String in names:
			tree[n5] = _enc(p.get(n5), dir, n5)
		for n6: String in pf:
			tree["persons." + n6] = _enc(p.get(n6), dir, n6)
		for n7: String in ["n", "pref_pop", "pension", "wage_index", "price_index", "hh_spec", "spec", "month", "seed_v", "base_year"]:
			tree["persons." + n7] = _enc(p.get(n7), dir, n7)
		for n8: String in lk:
			tree["local." + n8] = _enc(locals[n8], dir, n8)
		var fs := FileAccess.open(dir + "/state.json", FileAccess.WRITE)
		fs.store_string(JSON.stringify(tree, "", false))
		fs.close()
	print("TRACE stage %s" % stage)


func _sha(v: Variant) -> String:
	var h := HashingContext.new()
	h.start(HashingContext.HASH_SHA256)
	_canon(h, v)
	return h.finish().hex_encode()


## A typed tree: ints as {"i": "decimal"}, floats as {"f": "their 64 bits in decimal"}, bools, strings as {"s": …}, arrays as {"a": […]},
## dictionaries as {"d": [[key, value], …]} in insertion order, packed arrays as {"p": kind, "file": …} (a raw file, or inline when small)
## Why not JSON numbers: Godot's JSON writes floats at 17 digits and reads every number back as a float, so int64 and the last bits are lost
func _enc(v: Variant, dir: String, path: String) -> Variant:
	match typeof(v):
		TYPE_NIL:
			return null
		TYPE_BOOL:
			return v
		TYPE_INT:
			return {"i": str(v)}
		TYPE_FLOAT:
			return {"f": str(PackedFloat64Array([v]).to_byte_array().decode_s64(0))}
		TYPE_STRING, TYPE_STRING_NAME:
			return {"s": String(v)}
		TYPE_ARRAY:
			var a: Array = []
			for i: int in (v as Array).size():
				a.append(_enc(v[i], dir, "%s.%d" % [path, i]))
			return {"a": a}
		TYPE_DICTIONARY:
			var d: Array = []
			var j: int = 0
			for k in v:
				d.append([_enc(k, dir, ""), _enc(v[k], dir, "%s.%d" % [path, j])])
				j += 1
			return {"d": d}
		TYPE_PACKED_STRING_ARRAY:
			return {"p": "str", "v": Array(v)}
		TYPE_PACKED_INT64_ARRAY, TYPE_PACKED_INT32_ARRAY, TYPE_PACKED_FLOAT64_ARRAY, TYPE_PACKED_FLOAT32_ARRAY, TYPE_PACKED_BYTE_ARRAY:
			var kind: String = {TYPE_PACKED_INT64_ARRAY: "i64", TYPE_PACKED_INT32_ARRAY: "i32", TYPE_PACKED_FLOAT64_ARRAY: "f64",
				TYPE_PACKED_FLOAT32_ARRAY: "f32", TYPE_PACKED_BYTE_ARRAY: "u8"}[typeof(v)]
			var b: PackedByteArray = v.to_byte_array() if kind != "u8" else v
			if dir == "":
				return {"p": kind, "hex": b.hex_encode()}
			_files += 1
			var name: String = "%05d.bin" % _files
			var f := FileAccess.open(dir + "/" + name, FileAccess.WRITE)
			f.store_buffer(b)
			f.close()
			return {"p": kind, "file": name, "n": (v as Variant).size()}
	push_error("oracle_dump: an unencoded type %d at %s" % [typeof(v), path])
	return {"x": typeof(v)}


## The canonical bytes: a type byte, then int64 LE / float64 LE / UTF-8 with its length / an array's length and elements / a
## dictionary's length and its entries in sorted key order / a packed array's kind, length and LE bytes
## Why sorted keys: the save sorts the pid and remainder dictionaries (people._pid_rows, _rem_rows) and T2s-f shows the month does not
## depend on their order, so insertion order is not part of the state
func _canon(h: HashingContext, v: Variant) -> void:
	var b := PackedByteArray()
	match typeof(v):
		TYPE_NIL:
			h.update("n".to_utf8_buffer())
		TYPE_BOOL:
			h.update(("b1" if v else "b0").to_utf8_buffer())
		TYPE_INT:
			b.resize(9)
			b[0] = 0x69
			b.encode_s64(1, v)
			h.update(b)
		TYPE_FLOAT:
			b.resize(9)
			b[0] = 0x66
			b.encode_double(1, v)
			h.update(b)
		TYPE_STRING, TYPE_STRING_NAME:
			var s: PackedByteArray = String(v).to_utf8_buffer()
			b.resize(9)
			b[0] = 0x73
			b.encode_s64(1, s.size())
			h.update(b)
			h.update(s)
		TYPE_ARRAY:
			b.resize(9)
			b[0] = 0x61
			b.encode_s64(1, (v as Array).size())
			h.update(b)
			for x in v:
				_canon(h, x)
		TYPE_DICTIONARY:
			b.resize(9)
			b[0] = 0x64
			b.encode_s64(1, (v as Dictionary).size())
			h.update(b)
			var ks: Array = (v as Dictionary).keys()
			ks.sort()
			for k in ks:
				_canon(h, k)
				_canon(h, v[k])
		TYPE_PACKED_STRING_ARRAY:
			b.resize(9)
			b[0] = 0x53
			b.encode_s64(1, (v as PackedStringArray).size())
			h.update(b)
			for s2: String in v:
				_canon(h, s2)
		TYPE_PACKED_INT64_ARRAY, TYPE_PACKED_INT32_ARRAY, TYPE_PACKED_FLOAT64_ARRAY, TYPE_PACKED_FLOAT32_ARRAY, TYPE_PACKED_BYTE_ARRAY:
			var kind: int = {TYPE_PACKED_INT64_ARRAY: 0x71, TYPE_PACKED_INT32_ARRAY: 0x6c, TYPE_PACKED_FLOAT64_ARRAY: 0x44, TYPE_PACKED_FLOAT32_ARRAY: 0x46, TYPE_PACKED_BYTE_ARRAY: 0x42}[typeof(v)]
			b.resize(9)
			b[0] = kind
			b.encode_s64(1, (v as Variant).size())
			h.update(b)
			h.update(v.to_byte_array() if typeof(v) != TYPE_PACKED_BYTE_ARRAY else v)
		_:
			push_error("oracle_dump: no canonical form for type %d" % typeof(v))
