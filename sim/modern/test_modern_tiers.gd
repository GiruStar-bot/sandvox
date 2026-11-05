extends "res://tools/test/test_kit.gd"
## ISS tiered population T1 (sim/modern/people/tiers.gd; ISS_TIERED_POPULATION.md §12): the identities of the start, declared in
## ISS_CHECKS.md "Tiered population T1" before this code. Built by the `tiers` flag at K = 4, seed 1, all 47 prefectures, month 0.
##   godot --headless --path . --script res://sim/modern/test_modern_tiers.gd
## T1s-a Σ unit counts (bundles + individuals) by prefecture = the prefectures' populations; by band x sex = the cohort's split; the
##       persons by household type reported against the fit's targets
## T1s-b every household-bundle's composition sums, per person-bundle, to that bundle's count (integer)
## T1s-b2 heads = households in every household-bundle; partners = heads in the couple types; persons = Σ size x households; no
##        person in a size its type forbids; the persons short of the minimum sizes reported
## T1s-hh0 (V111 (1)) no person below its type's minimum size in types 0, 2 and 3 (types 1 and 4 declared cases, counted); every couple +
##        children and single-parent household holds a child (the minimum pass, R83's window by the child's birth year)
## T1s-cp0 (§12.12) the couples from R77: in the couple types no female head and no male partner, heads and partners equal per
##        household-bundle but for the cross-tier couples, couple-only persons all in couples
## T1s-w  (§12.12, TO_E 05:28; V111 (3)) WITHDRAWN as superseded by R77c's rows: (i) TO_E 17:02, (ii) 17:54; both printed as REPORTs
## T1s-bnw, T1s-bnh, T1s-bpw, T1s-bph, T1s-bpr, T1s-bj35, T1s-bja (§12.15, TO_E 16:12, 16:58) R77c's 2015 -> 2020 backtest on the tool's
##        own code, read from the spec: each P95 the declared one (M014 R3's; the prefecture rows M020's with R88's split), cells beyond
##        it at most 5% + 2 SE, none beyond twice it
## T1s-c1 (§12.12; V110 (4)) the couple-only share against R77's 第32表, reported in integers: a read-back of the input, not evidence
## T1s-ma (§12.12 (6); V110 (4); RE-DECLARED §12.16) married-living-apart per prefecture x band x sex = the couple persons x 2020's
##        married-apart ratio (marital_2024): a read-back, its number D; the 2020 CHECK reported
## T1s-c9 the income tail (§12.8 item 9): R67a's lines, classes on their sides, the shares above each line, no empty gap at a line;
##        the top 0.01%'s individuals and bundled points one law by the fitted tail's quartile bins, chi2(3) < 11.34 each (the class
##        means are T1s-cm's, test_modern_tiers_means.gd)
## T1s-d the same seed twice gives the same digest; to_dict, from_dict gives the same digest
## T1s-e Σ counts = the population (the sum rule), every unit's single-age counts sum to its count
## T1s-f the flag: tiers off leaves the test society's digest (households off, 9ae891d6 since S-year) and the households-on 12-month digest unchanged
## T1s-h the IPF's worst relative margin error <= 1e-8 (the fit's feasibility read), the later marginals' residuals reported
## T1s-n never-married per prefecture x band x sex against marital_2024 (§12.16: the cohort identity and its residual share, recomputed)
##       where the free share lies in [0, 1]; the forced rows and R62 reported
## T1s-cpb (§12.16 (3), an identity) the couples placed in types 1, 2 and 4 = R77c's per prefecture (and per husband band within rounding)
## T1s-co, T1s-cc, T1s-o4, T1s-lp1 (§12.16 (3), M022 §4) the couple-only, couple + children, other and lone-parent households against
##        M022's predictions; T1s-ip (REPORT) every type against IPSS's ratio
## T1s-1pi (§12.16, M023, M024) one-person households by householder sex x 10-year band against census 2020 (the age-unknown by
##        M017b's IPF) x IPSS 2018's ratio, levelled to T1's total: at most one cell beyond 7.6%, none beyond 15.2%
## T1s-ms2 (§12.16) married = couple persons + married-apart per prefecture x band x sex (an identity)
## T1s-nmt (§12.16) the national never-married share's 2020-24 change per year against 2015-20's, bands 45-69 the same sign (a tripwire)
## T1s-res (§12.16) the residual by band x sex, a REPORT, a tripwire at 12%; R81's 2022 foreign stock beside it
## T1s-o every single age 0-100 against the cohort within an unbiased rounding's bound, 3 sqrt(H/4) + 1 (H the units holding it)
## T1s-p the individuals' own levels persist (§12.8 10.1): income unchanged by repay() and by a job pay factor reset, x1.1 at a
##       factor of 1.1, a pension x1.02 with R68's indices x1.02, the counts above the cash lines unchanged
## SB3   Σ over the points and individuals of each instrument = the household sector's total (R67c) in integer yen
## T1s-k units <= 50,000, Σ K_b within 2% of P, no unit at count 0
const PEOPLE = preload("res://sim/modern/people/people.gd")
const TR = preload("res://sim/modern/people/tiers.gd")
const MS = preload("res://sim/modern/modern_status.gd")
const CANON = preload("res://sim/modern/canon.gd")
const P5_DIGEST := "4250a82647dd26afa5631f1ea0d2e382cc14e224b2399f46cd70ce41a14efb5f"
const HH_12 := "30fc0e0c33ecc59fcc8369776bab6cd78bf9be23978f0c97d1b4999d8fab1e38"
const CHI2_3_99 := 11.345
const ENV := {"inflation_month": 0.02 / 12.0, "food_price_yoy": 0.0, "unemployment_rate": 0.025, "levers": []}


func _build(st, prefs: Dictionary, seed: int) -> Object:
	var p = PEOPLE.new()
	p.tiers = true
	p.create("JPN", seed, st.cohort["JPN"], st.qx["JPN"], prefs, 0, 2024)
	return p


## T1s-nh (§12.12 (9)): the households holding a non-head couple beside a head couple, per prefecture, against R84's two-couple households
## (a lower bound, CHECK); the counts, the clips, the window's gaps reported
func _t1s_nh(p, prefs: Dictionary, n_head: int, n_nh: PackedInt64Array) -> void:
	var nh: Dictionary = TR._v(p, "nonhead_couples")["by_pref"]
	var ht0: Dictionary = TR._v(p, "household_target")
	var by: Dictionary = p.tr_margins.get("nh_two_couple_by", {})
	var bad: int = 0
	var txt: String = ""
	var tot: int = 0
	var raw_short: int = 0
	for code: String in prefs:
		var c: int = int(code)
		var low_raw: int = int(nh[str(c)]["two_couple_low"])
		var o20: float = float(ht0["census_2020"][str(c)][4])
		var low: int = int(round(float(low_raw) * float(ht0["by_pref"][str(c)][4]) / o20)) if o20 > 0.0 else low_raw
		var got: int = int(by.get(c, 0))
		tot += got
		raw_short += 1 if got < low_raw else 0
		if got < low:
			bad += 1
			txt += " %d: %d < %d;" % [c, got, low]
	check(bad == 0, "T1s-nh (§12.12 (9), CHECK, a NEAR READ-BACK: the bound is the cap's own input; TO_E 11:10; amendment 4 REVERTED, V114 (4): the placed households alone) households with a non-head couple beside a head couple, per prefecture, at least R84's two-couple households as a share of census 2020's 'other' households x the target's (M019 (1)): %d of %d below;%s total %d (R84 raw low %d, high %d; below the raw count %d prefectures; unplaced %d by kind|wife band %s; individuals redrawn off type-4 couple persons %d; parent couples with no couple-headed reference below them, moved to the child kind %d)" % [bad, prefs.size(), txt, tot, int(nh["0"]["two_couple_low"]), int(nh["0"]["two_couple_high"]), raw_short, int(p.tr_margins.get("nh_unplaced", 0)), str(p.tr_margins.get("nh_unplaced_kind", {})), int(p.tr_margins.get("indiv_redrawn", 0)), int(p.tr_margins.get("nh_kind_moved", 0))])
	var ub: Dictionary = p.tr_margins.get("nh_unplaced_by", {})
	var ut: int = 0
	var utxt: String = ""
	var uks: Array = ub.keys()
	uks.sort()
	for uk in uks:
		ut += int(ub[uk])
		utxt += " %d: %d;" % [int(uk), int(ub[uk])]
	var lim: int = int(floor(0.0005 * float(n_nh[0] + n_nh[1])))
	check(ut <= lim, "T1s-nhu (TO_E 11:27, a tripwire, T; the 0.05%% SET AFTER SEEING the 222, V114 (4)) non-head couples left unplaced %d, at most 0.05%% of %d (%d); by prefecture:%s" % [ut, n_nh[0] + n_nh[1], lim, utxt])
	print("REPORT T1s-nh head couples %d, child couples %d, parent couples %d (R84 2020: head %d, child spouses %d); clipped %.0f; persons the entries lacked %d; placed outside R83's window %d, unplaced %d; gaps in bands (reference - child wife, parent wife - reference) %s" % [n_head, n_nh[0], n_nh[1], int(nh["0"]["head_spouses"]), int(nh["0"]["child_spouse_m"].reduce(func(a, b): return a + b, 0)) + int(nh["0"]["child_spouse_f"].reduce(func(a, b): return a + b, 0)), float(p.tr_margins.get("nh_clip", 0.0)), int(p.tr_margins.get("nh_short", 0)), int(p.tr_margins.get("nh_outside", 0)), int(p.tr_margins.get("nh_unplaced", 0)), str(p.tr_margins.get("nh_gaps", {}))])


## T1s-gap (§12.12 (5), (9), TO_E 10:28; CHECK): the parent-child gaps in bands of the minimum pass and the non-head couples, by the
## child's birth-year group, against R83's group mean (first births from 1970), each share within R83's own year-to-year spread
func _t1s_gap(p) -> void:
	const TOL := [0.043, 0.039, 0.072, 0.017]
	var win: Dictionary = TR._v(p, "child_window")
	var ref := PackedFloat64Array()
	ref.resize(4 * 13)
	var ny := PackedInt64Array([0, 0, 0, 0])
	for i: int in (win["mother"] as Array).size():
		var y: int = int(win["mother"][i][0])
		var grp: int = 0 if y < 1970 else (1 if y < 1990 else (2 if y < 2010 else 3))
		ny[grp] += 1
		for r: Array in win["mother_shares"][i]:
			var mid: float = (float(r[0]) + float(r[1])) * 0.5 / 5.0
			var g0: int = int(floor(mid))
			if g0 >= 0 and g0 < 13:
				ref[grp * 13 + g0] += float(r[2]) * (1.0 - (mid - float(g0)))
			if g0 + 1 < 13:
				ref[grp * 13 + g0 + 1] += float(r[2]) * (mid - float(g0))
	var got := PackedFloat64Array()
	got.resize(4 * 13)
	var tot := PackedFloat64Array([0.0, 0.0, 0.0, 0.0])
	for src: Dictionary in [p.tr_margins.get("gap_child", {}), p.tr_margins.get("gap_nh", {})]:
		for k: String in src:
			var kk: PackedStringArray = k.split("|")
			var g: int = int(kk[1])
			if g < 0 or g >= 13:
				continue
			got[int(kk[0]) * 13 + g] += float(src[k])
			tot[int(kk[0])] += float(src[k])
	var bad: int = 0
	var txt: String = ""
	for grp2: int in 4:
		if tot[grp2] <= 0.0 or ny[grp2] == 0:
			continue
		var worst: float = 0.0
		var row: String = ""
		for g2: int in 13:
			var a: float = got[grp2 * 13 + g2] / tot[grp2]
			var b: float = ref[grp2 * 13 + g2] / float(ny[grp2])
			if a < 0.005 and b < 0.005:
				continue
			worst = maxf(worst, absf(a - b))
			row += " %d: %.3f/%.3f" % [g2, a, b]
		bad += 1 if worst > float(TOL[grp2]) else 0
		txt += " [%s, %.0f persons, worst %.3f, tol %.3f:%s]" % [["1950-69", "1970-89", "1990-2009", "2010-22"][grp2], tot[grp2], worst, float(TOL[grp2]), row]
	print("REPORT T1s-gap (§12.12 (5), (9); a REPORT since TO_E 11:10: R83 counts births to all mothers, these are co-resident pairs) parent-child gaps in bands by the child's birth-year group, the start/R83: groups beyond R83's own spread %d;%s" % [bad, txt])


## T1s-lc (§12.13, M016 §4; a tripwire, T): L's type-4 child persons (a share within type 4, M019) clipped for want of room, by sex x
## band, each at most 0.5% of the band's persons; L's nuclear 子 (its share x the start's type 2-3 persons) against their children reported
func _t1s_lc(p) -> void:
	var clip: Dictionary = p.tr_margins.get("lc_clip", {})
	var per := {}
	var kid := {}
	for u: int in p.tr_units:
		var k: String = "%d|%d" % [p.tr_key[u * TR.KEY_STRIDE + 1], p.tr_key[u * TR.KEY_STRIDE + 2]]
		per[k] = int(per.get(k, 0)) + p.tr_count[u]
	for hk: String in p.tr_hh:
		var tt: int = int(hk.get_slice("|", 1))
		if tt != 2 and tt != 3:
			continue
		var mem: Dictionary = p.tr_hh[hk]["members"]
		for u2 in mem:
			var k2: String = "%d|%d" % [p.tr_key[int(u2) * TR.KEY_STRIDE + 1], p.tr_key[int(u2) * TR.KEY_STRIDE + 2]]
			kid[k2] = int(kid.get(k2, 0)) + int((mem[u2] as Dictionary).get(2, 0))
	var bad: int = 0
	var txt: String = ""
	var tot: int = 0
	for k3: String in clip:
		tot += int(clip[k3])
		if float(clip[k3]) > 0.005 * float(per.get(k3, 0)):
			bad += 1
			txt += " %s %d of %d;" % [k3, int(clip[k3]), int(per.get(k3, 0))]
	check(bad == 0, "T1s-lc (§12.13, M016 §4; a tripwire, T; L at the role step) L's type-4 child persons clipped %d in all, cells beyond 0.5%% of the band's persons %d;%s" % [tot, bad, txt])
	# L as a share within types 2-3 (M019 (1)): the share x the start's type 2-3 persons of the cell
	var ln: Dictionary = TR._l_other(p, 0)
	var p23 := {}
	for hk3: String in p.tr_hh:
		var t3: int = int(hk3.get_slice("|", 1))
		if t3 != 2 and t3 != 3:
			continue
		var mem3: Dictionary = p.tr_hh[hk3]["members"]
		for u3 in mem3:
			var kc: String = "%d|%d|%d" % [p.tr_key[int(u3) * TR.KEY_STRIDE], p.tr_key[int(u3) * TR.KEY_STRIDE + 1], p.tr_key[int(u3) * TR.KEY_STRIDE + 2]]
			for r3 in mem3[u3]:
				p23[kc] = int(p23.get(kc, 0)) + int(mem3[u3][r3])
	var lnb := {}
	for k4: String in p23:
		var kb: String = "%s|%s" % [k4.get_slice("|", 1), k4.get_slice("|", 2)]
		lnb[kb] = int(lnb.get(kb, 0)) + int(round(float(ln.get(k4, 0.0)) * float(p23[k4])))
	var rows: String = ""
	for b5: int in TR.BANDS:
		for s5: int in 2:
			var k5: String = "%d|%d" % [b5, s5]
			if int(lnb.get(k5, 0)) > 0:
				rows += " %d%s %d/%d;" % [b5 * 5, "m" if s5 == 0 else "f", int(kid.get(k5, 0)), int(lnb.get(k5, 0))]
	print("REPORT T1s-lc L's nuclear 子 against the start's type 2-3 child persons, the start/L by band x sex:%s" % rows)


## T1s-nho (V114 (3a), TO_E 14:11; CHECK): the non-head couples placed outside R83's window at most 2% of the non-head couples
func _t1s_nho(p, n_nh: int) -> void:
	var out: int = int(p.tr_margins.get("nh_outside", 0))
	check(float(out) <= 0.02 * float(n_nh), "T1s-nho (V114 (3a); CHECK) non-head couples outside R83's window %d of %d (%.2f%%), at most 2%%" % [out, n_nh, 100.0 * float(out) / float(maxi(1, n_nh))])


## T1s-gap2 (M018, TO_E 14:22; CHECK; 1950-69 a CHECK again, TO_E 17:55): the minimum pass's mother-child gaps in 5-year bands (the mother's band, 85+ top-coded, less the
## child's) by the child's birth-year group, against M018's comparator (R83 at single ages x survival), the largest |start - comparator|
## share per group within 3.6 / 4.1 / 3.3 / 2.6 points; fathers and the non-head couples reported apart
func _t1s_gap2(p) -> void:
	# M018 (math-reports dc6d9039), its script's main shares on R83 and R80, by group then gap
	const REF := [{3: 0.060797, 4: 0.294574, 5: 0.428829, 6: 0.200869, 7: 0.014927}, {3: 0.005737, 4: 0.115567, 5: 0.363678, 6: 0.361498, 7: 0.131115, 8: 0.020829, 9: 0.001551}, {3: 0.007554, 4: 0.077636, 5: 0.260292, 6: 0.357775, 7: 0.224632, 8: 0.064372, 9: 0.00753, 10: 0.000194}, {3: 0.005209, 4: 0.048004, 5: 0.176562, 6: 0.313425, 7: 0.293021, 8: 0.137439, 9: 0.025583, 10: 0.000723}]
	const TOL := [0.036, 0.041, 0.033, 0.026]
	var src: Dictionary = p.tr_margins.get("gap2", {})
	var got := PackedFloat64Array()
	got.resize(4 * 20)
	var tot := PackedFloat64Array([0.0, 0.0, 0.0, 0.0])
	for k: String in src:
		var gr: int = int(k.get_slice("|", 0))
		var g: int = clampi(int(k.get_slice("|", 1)), 0, 19)
		got[gr * 20 + g] += float(src[k])
		tot[gr] += float(src[k])
	var bad: int = 0
	var txt: String = ""
	for gr2: int in 4:
		var worst: float = 0.0
		var row: String = ""
		for g2: int in 20:
			var a: float = got[gr2 * 20 + g2] / tot[gr2] if tot[gr2] > 0.0 else 0.0
			var b: float = float((REF[gr2] as Dictionary).get(g2, 0.0))
			if a < 0.0005 and b < 0.0005:
				continue
			worst = maxf(worst, absf(a - b))
			row += " %d: %.3f/%.3f" % [g2, a, b]
		bad += 1 if worst > float(TOL[gr2]) else 0
		txt += " [%s, %.0f pairs, worst %.3f, tol %.3f:%s]" % [["1950-69", "1970-89", "1990-2009", "2010-22"][gr2], tot[gr2], worst, float(TOL[gr2]), row]
	check(bad == 0, "T1s-gap2 (M018, TO_E 14:22; CHECK; 1950-69 a CHECK again, TO_E 17:55) mother-child gaps of the minimum pass by the child's birth-year group, the start/M018, worst share gap within the group's tolerance: %d of 4 beyond;%s" % [bad, txt])
	var mc: Dictionary = p.tr_margins.get("gap2_mc", {})
	var mk: Array = mc.keys()
	mk.sort_custom(func(a, b): return int(a.get_slice("|", 0)) * 100 + int(a.get_slice("|", 1)) < int(b.get_slice("|", 0)) * 100 + int(b.get_slice("|", 1)))
	var mtxt: String = ""
	for k2 in mk:
		mtxt += " %s:%d;" % [k2, int(mc[k2])]
	print("REPORT T1s-gap2 the minimum pass's mother-child pairs by mother band|child band (M019 (4)):%s" % mtxt)
	print("REPORT T1s-gap2 excluded: the father-child pairs %s; the non-head couples' gaps (T1s-nh's report); type 4's child members are not in this row yet (their placement does not record the head's sex)" % str(p.tr_margins.get("gap2_father", {})))


## T1s-wm (V114 (2), TO_E 14:11): in the couple types, the wives (partners) above each household-bundle's male heads, summed, at most the
## cross-tier husbands (§12.12 (7)); the excess by type reported
func _t1s_wm(p) -> void:
	var over := {}
	var tot: int = 0
	for hk: String in p.tr_hh:
		var tt: int = int(hk.get_slice("|", 1))
		if tt != 1 and tt != 2 and tt != 4:
			continue
		var mem: Dictionary = p.tr_hh[hk]["members"]
		var men: int = 0
		var wives: int = 0
		for u in mem:
			var m: Dictionary = mem[u]
			if p.tr_key[int(u) * TR.KEY_STRIDE + 2] == 0:
				men += int(m.get(0, 0))
			wives += int(m.get(1, 0))
		if wives > men:
			over[tt] = int(over.get(tt, 0)) + wives - men
			tot += wives - men
	var cross: int = int(p.tr_margins.get("r77_cross_husband", 0))
	var grp := {}
	for hk2: String in p.tr_hh:
		var f: PackedStringArray = hk2.split("|")
		if int(f[1]) != 1 and int(f[1]) != 2 and int(f[1]) != 4:
			continue
		var gk: String = "%s|%s|%s|%s" % [f[0], f[1], f[2], f[4]]
		if not grp.has(gk):
			grp[gk] = [0, 0]
		var mem2: Dictionary = p.tr_hh[hk2]["members"]
		for u2 in mem2:
			if p.tr_key[int(u2) * TR.KEY_STRIDE + 2] == 0:
				grp[gk][0] = int(grp[gk][0]) + int((mem2[u2] as Dictionary).get(0, 0))
			grp[gk][1] = int(grp[gk][1]) + int((mem2[u2] as Dictionary).get(1, 0))
	var gtot: int = 0
	for gk2: String in grp:
		gtot += maxi(0, int(grp[gk2][1]) - int(grp[gk2][0]))
	check(tot <= cross, "T1s-wm (V114 (2); CHECK) wives in the couple types above their household-bundle's male heads %d, at most the cross-tier husbands %d; by type %s; across the sizes of a (prefecture, type, householder band, class) group, as T2.1 pairs them, %d" % [tot, cross, str(over), gtot])


## T1s-1p (§12.14 (4), M017 §3; a transcription): national one-person heads = the household-type target (21.731 M), |Δ| < 1,000;
## the gap to IPSS 2024's CHECK reported. T1s-1pa (M017b §3, M017c; a READ-BACK, TO_E 17:55): one-person persons by 10-year band x sex
## against M017c's table (computed on T1's start persons), each within max(2%, 20,000)
func _t1s_1p(p) -> void:
	# M017c (math-reports 81aebaf9, TO_E 14:45 (2)): M017b's completed shares x T1's start persons, raked x1.0330 to the target
	const PRED := [[1332000, 2173000, 1437000, 1910000, 1678000, 1390000, 877000, 355000], [1064000, 1430000, 796000, 1090000, 1179000, 1538000, 2220000, 1262000]]
	var ht: Dictionary = TR._v(p, "household_target")
	var want: float = float(ht["by_pref"]["0"][0])
	var heads: int = 0
	var by := PackedFloat64Array()
	by.resize(18)
	for hk: String in p.tr_hh:
		if int(hk.get_slice("|", 1)) != 0:
			continue
		var mem: Dictionary = p.tr_hh[hk]["members"]
		for u in mem:
			var h: int = int((mem[u] as Dictionary).get(0, 0))
			heads += h
			var b: int = p.tr_key[int(u) * TR.KEY_STRIDE + 1]
			by[TR._ten_band(b) * 2 + p.tr_key[int(u) * TR.KEY_STRIDE + 2]] += float(h)
	var chk: float = float(ht["check_2024_ipss2024"]["one_person"])
	check(absf(float(heads) - want) < 1000.0, "T1s-1p (§12.14 (4), M017 §3; a TRANSCRIPTION of the target) national one-person heads %d against the target %.0f (Δ %+.0f, at most 1,000); IPSS 2024's CHECK %.0f (gap %+.0f, reported); the rake factor on the completed shares %s" % [heads, want, float(heads) - want, chk, want - chk, str(p.tr_margins.get("one_rake", []))])
	var bad: int = 0
	var txt: String = ""
	var gl: Array = ["15-24", "25-34", "35-44", "45-54", "55-64", "65-74", "75-84", "85+"]
	for s: int in 2:
		for g: int in 8:
			var got: float = by[(g + 1) * 2 + s]
			var pr: float = float(PRED[s][g])
			var tol: float = maxf(0.02 * pr, 20000.0)
			bad += 1 if absf(got - pr) > tol else 0
			txt += " %s %s %.0f/%.0f;" % ["m" if s == 0 else "f", gl[g], got, pr]
	var fm: Dictionary = p.tr_margins.get("floor_moved", {})
	var fmt := {}
	for k: String in fm:
		fmt[k.get_slice("|", 0)] = float(fmt.get(k.get_slice("|", 0), 0.0)) + float(fm[k])
	print("REPORT T1s-1p the size floor (§12.14, TO_E 14:45) persons moved into a type, by type %s; by type|band %s" % [str(fmt), str(fm)])
	check(bad == 0, "T1s-1pa (M017b §3; a READ-BACK, TO_E 17:55: M017c's table is computed on T1's start persons; table RE-COMPUTED, M017c) one-person persons by 10-year band x sex, the start/M017c, each within max(2%%, 20,000): %d of 16 beyond;%s (under 15: %.0f)" % [bad, txt, by[0] + by[1]])


## T1s-n4 (§12.13, M016 §4; CHECK, a near read-back; bound AMENDED 14:10): the type-4 couples (head + child + parent) by husband
## 10-year band, each at least R77's 2020 husbands less (第13-2表's men in nuclear households less its nuclear 子 men), x the band's
## start ÷ 2020 couples; M016 §1's form from 第49-2表 and the gap between the tables reported; under 65 第49-2表's married men living
## with a parent reported
func _t1s_n4(p) -> void:
	var ten: Array = TR._ten_shares(p)
	var pop: Array = TR._v(p, "population_2020_by_pref_sex_band")["by_pref"]["0"]
	var cba: Array = TR._v(p, "couples_by_age")["by_pref"]["0"]
	var lm: Array = TR._v(p, "coresident_marital")["men"]
	var cr: Array = TR._v(p, "child_role")["by_pref"]["0"]["m"]
	var n13 := PackedFloat64Array()
	n13.resize(9)
	var c20 := PackedFloat64Array()
	c20.resize(9)
	var nuc := PackedFloat64Array()
	nuc.resize(9)
	var cn := PackedFloat64Array()
	cn.resize(9)
	var mar := PackedFloat64Array()
	mar.resize(9)
	for hb: int in 15:
		var g: int = TR._ten_band(hb + 3)
		for wb: int in 15:
			c20[g] += float(cba[hb][wb])
		nuc[g] += (float(ten[0][g][1]) + float(ten[0][g][2]) + float(ten[0][g][3])) * float(pop[0][hb])
		for m: int in 4:
			cn[g] += float(lm[hb][m][0])
		mar[g] += float(lm[hb][1][0]) + float(lm[hb][1][1])
		n13[g] += float(cr[hb + 3][3]) - float(cr[hb + 3][1])
	var cs := PackedFloat64Array()
	cs.resize(9)
	var c4 := PackedFloat64Array()
	c4.resize(9)
	for src: Dictionary in [p.tr_couples, p.tr_nh_couples]:
		for k: String in src:
			var f: PackedStringArray = k.split("|")
			var g2: int = TR._ten_band(int(f[1]) + 3)
			cs[g2] += float(src[k])
			if src == p.tr_nh_couples or int(f[3]) == 4:
				c4[g2] += float(src[k])
	var bad: int = 0
	var txt: String = ""
	var gl: Array = ["<15", "15-24", "25-34", "35-44", "45-54", "55-64", "65-74", "75-84", "85+"]
	for g3: int in range(1, 9):
		var sc: float = cs[g3] / c20[g3] if c20[g3] > 0.0 else 0.0
		var bound: float = maxf(0.0, c20[g3] - n13[g3]) * sc
		var b49: float = maxf(0.0, c20[g3] - (nuc[g3] - cn[g3])) * sc
		bad += 1 if c4[g3] < bound else 0
		txt += " %s %.0f (bound %.0f; 第49-2表's form %.0f, the tables' gap %+.0f%s)" % [gl[g3], c4[g3], bound, b49, b49 - bound, (", married men with a parent %.0f" % (mar[g3] * sc)) if g3 <= 5 else ""] + ";"
	check(bad == 0, "T1s-n4 (§12.13, M016 §4; CHECK, a NEAR READ-BACK: (N) is the same identity; bound AMENDED 14:10 to 第13-2表's definition) type-4 couples by husband 10-year band at least R77's husbands − (第13-2表's nuclear men − nuclear 子 men), x start ÷ 2020 couples: %d of 8 below;%s" % [bad, txt])
	print("REPORT T1s-n4 the type-2 cap (§12.13 (c)) moved couples to type 4 by prefecture: %s" % str(p.tr_margins.get("n4_cap", {})))
	print("REPORT T1s-n4 (N) by husband 10-year band [all couples, non-head, raw, type 4, nuclear men, L nuclear men, single-parent heads]: %s" % str(p.tr_margins.get("n4", {})))


## T1s-lp (R85, CHECK): the share living with a parent by sex x band (15-69) x marital, against 第49-2表, ±5 points on cells of at least
## 100k persons: the child role (married within a recorded child couple, else never married) and the heads and partners of "other"
## groups holding a parent (the recorded parent couples + the parent-role persons in no couple, at most the households)
func _t1s_lp(p) -> void:
	var cr: Dictionary = TR._v(p, "coresident")["living_with_parent"]
	var live := PackedFloat64Array()   # (sex * 2 + married) * BANDS + band
	live.resize(4 * TR.BANDS)
	var den := PackedFloat64Array()
	den.resize(4 * TR.BANDS)
	var r2u: Dictionary = {}
	var mcu: Dictionary = {}
	for hk: String in p.tr_hh:
		var mem: Dictionary = p.tr_hh[hk]["members"]
		for u in mem:
			r2u[int(u)] = int(r2u.get(int(u), 0)) + int((mem[u] as Dictionary).get(2, 0))
	var pcg: Dictionary = {}
	for rk: String in p.tr_nh_hh:
		for rec: Array in p.tr_nh_hh[rk]:
			if int(rec[2]) == 0:
				mcu[int(rec[0])] = int(mcu.get(int(rec[0]), 0)) + int(rec[3])
				mcu[int(rec[1])] = int(mcu.get(int(rec[1]), 0)) + int(rec[3])
			else:
				pcg[rk] = int(pcg.get(rk, 0)) + int(rec[3])
	var g4: Dictionary = {}   # "code|band|class" -> [households, parent persons, heads by unit {u: n}, partners by unit, wives]
	for hk2: String in p.tr_hh:
		var f: PackedStringArray = hk2.split("|")
		var mem2: Dictionary = p.tr_hh[hk2]["members"]
		for u2 in mem2:
			var n2: int = int((mem2[u2] as Dictionary).get(2, 0))
			if n2 > 0:
				var b2: int = p.tr_key[int(u2) * TR.KEY_STRIDE + 1]
				var s2: int = p.tr_key[int(u2) * TR.KEY_STRIDE + 2]
				var fr: float = minf(1.0, float(mcu.get(int(u2), 0)) / float(maxi(1, int(r2u[int(u2)]))))
				live[(s2 * 2 + 1) * TR.BANDS + b2] += float(n2) * fr
				live[(s2 * 2) * TR.BANDS + b2] += float(n2) * (1.0 - fr)
		if int(f[1]) != 4:
			continue
		var gk: String = "%s|%s|%s" % [f[0], f[2], f[4]]
		if not g4.has(gk):
			g4[gk] = [0, 0, {}, {}, 0]
		var e: Array = g4[gk]
		e[0] = int(e[0]) + int(p.tr_hh[hk2]["count"])
		for u3 in mem2:
			var m3: Dictionary = mem2[u3]
			e[1] = int(e[1]) + int(m3.get(3, 0))
			if int(m3.get(0, 0)) > 0:
				e[2][int(u3)] = int(e[2].get(int(u3), 0)) + int(m3.get(0, 0))
			if int(m3.get(1, 0)) > 0:
				e[3][int(u3)] = int(e[3].get(int(u3), 0)) + int(m3.get(1, 0))
				e[4] = int(e[4]) + int(m3.get(1, 0))
	for gk2: String in g4:
		var e2: Array = g4[gk2]
		var pc: int = int(pcg.get("%02d|%s|%s" % [int(gk2.get_slice("|", 0)), gk2.get_slice("|", 1), gk2.get_slice("|", 2)], 0))
		var hwp: int = mini(int(e2[0]), pc + maxi(0, int(e2[1]) - 2 * pc))
		var rho: float = float(hwp) / float(maxi(1, int(e2[0])))
		var heads: int = 0
		for u4 in e2[2]:
			heads += int(e2[2][u4])
		var mf: float = minf(1.0, float(e2[4]) / float(maxi(1, heads)))
		for u5 in e2[2]:
			var b5: int = p.tr_key[int(u5) * TR.KEY_STRIDE + 1]
			var s5: int = p.tr_key[int(u5) * TR.KEY_STRIDE + 2]
			live[(s5 * 2 + 1) * TR.BANDS + b5] += float(e2[2][u5]) * rho * mf
			live[(s5 * 2) * TR.BANDS + b5] += float(e2[2][u5]) * rho * (1.0 - mf)
		for u6 in e2[3]:
			var b6: int = p.tr_key[int(u6) * TR.KEY_STRIDE + 1]
			var s6: int = p.tr_key[int(u6) * TR.KEY_STRIDE + 2]
			live[(s6 * 2 + 1) * TR.BANDS + b6] += float(e2[3][u6]) * rho
	for u7: int in p.tr_units:
		var b7: int = p.tr_key[u7 * TR.KEY_STRIDE + 1]
		var s7: int = p.tr_key[u7 * TR.KEY_STRIDE + 2]
		den[(s7 * 2) * TR.BANDS + b7] += p.tr_never_married[u7] * float(p.tr_count[u7])
		den[(s7 * 2 + 1) * TR.BANDS + b7] += p.tr_married_apart[u7] * float(p.tr_count[u7])
	for src: Dictionary in [p.tr_couples, p.tr_nh_couples]:
		for kq: String in src:
			var kp: PackedStringArray = kq.split("|")
			den[1 * TR.BANDS + int(kp[1]) + 3] += float(src[kq])
			den[3 * TR.BANDS + int(kp[2]) + 3] += float(src[kq])
	# Why not each marital column's own age-unknown: R87 has none by marital state, so they join each column in proportion (T, M017b §4)
	var au0: Dictionary = TR._v(p, "age_unknown")["by_pref"]["0"]
	var alt_s := PackedFloat64Array()
	alt_s.resize(2 * TR.BANDS)
	var alt_c := PackedFloat64Array()
	alt_c.resize(2 * TR.BANDS)
	var bad: int = 0
	var n: int = 0
	var txt: String = ""
	for sx: int in 2:
		for mr: int in 2:
			var row: Array = cr["men" if sx == 0 else "women"]["married" if mr == 1 else "never"]
			for b8: int in range(3, 14):
				var d8: float = den[(sx * 2 + mr) * TR.BANDS + b8]
				if d8 < 100000.0:
					continue
				var a8: float = live[(sx * 2 + mr) * TR.BANDS + b8] / d8
				var r8: float = float(row[b8 - 3]) * float(au0["m" if sx == 0 else "f"]["raw"][b8]) / float(au0["m" if sx == 0 else "f"]["imputed"][b8])
				if mr == 0:
					alt_s[sx * TR.BANDS + b8] = a8
					alt_c[sx * TR.BANDS + b8] = r8
				n += 1
				if absf(a8 - r8) > 0.05:
					bad += 1
				txt += " %s%s%d %.3f/%.3f;" % ["m" if sx == 0 else "f", "M" if mr == 1 else "N", b8 * 5, a8, r8]
	# T1s-alt (TO_E 15:55; REPORT): the roughness of the never-married at-home shares by 5-year band, the start against 第49-2表
	var atxt: String = ""
	for sa: int in 2:
		var rs: float = 0.0
		var rc: float = 0.0
		for ba: int in range(4, 13):
			var l0: int = sa * TR.BANDS + ba
			if alt_s[l0 - 1] > 0.0 and alt_s[l0] > 0.0 and alt_s[l0 + 1] > 0.0:
				rs += absf(alt_s[l0] - (alt_s[l0 - 1] + alt_s[l0 + 1]) * 0.5)
				rc += absf(alt_c[l0] - (alt_c[l0 - 1] + alt_c[l0 + 1]) * 0.5)
		atxt += " %s %.3f (第49-2表 %.3f);" % ["men" if sa == 0 else "women", rs, rc]
	print("REPORT T1s-alt (TO_E 15:55; a CHECK once its threshold is declared) the never-married at-home share's roughness over 20-64, Σ |a(b) - (a(b-1) + a(b+1)) / 2|:%s" % atxt)
	var pw: Dictionary = p.tr_margins.get("parent_window", {})
	var p85 := PackedFloat64Array()
	p85.resize(TR.BANDS)
	var t85: float = 0.0
	for kp: String in pw:
		if int(kp.get_slice("|", 0)) == TR.BANDS - 1:
			p85[int(kp.get_slice("|", 1))] += float(pw[kp])
			t85 += float(pw[kp])
	var row85: String = ""
	for hb9: int in TR.BANDS:
		if p85[hb9] > 0.0:
			row85 += " %d-%d %.1f%%;" % [hb9 * 5, hb9 * 5 + 4, 100.0 * p85[hb9] / t85]
	print("REPORT T1s-lp the parent window (§12.13 step 7): type 4's 85+ parents in no couple (%.0f) by their head's band:%s; parent-role persons with no head band in the window, placed as 'other' %d" % [t85, row85, int(p.tr_margins.get("parent_none", 0))])
	check(bad == 0, "T1s-lp (R85 第49-2表, CHECK, ±5pt T; comparator RE-BASED on the imputed persons, TO_E 14:24) the share living with a parent by sex x band x marital (N never, M married), the start/census: %d of %d cells beyond 5 points;%s" % [bad, n, txt])


## T1s-gapm (R85, CHECK): couple households with a child under 18 by the wife's band, as shares, against 第15-5表, ±5 points on cells of
## at least 50k households: per bundle of types 2 and 4, its wives' households, at most its child-role persons under 18 (15-19 at 3/5,
## D), over the wives' bands in proportion
func _t1s_gapm(p) -> void:
	var ref: Array = TR._v(p, "coresident")["young_child_households"]
	var got := PackedFloat64Array()
	got.resize(11)
	for hk: String in p.tr_hh:
		var t: int = int(hk.get_slice("|", 1))
		if t != 2 and t != 4:
			continue
		var mem: Dictionary = p.tr_hh[hk]["members"]
		var kids: float = 0.0
		var wives := PackedFloat64Array()
		wives.resize(11)
		var wt: float = 0.0
		for u in mem:
			var b: int = p.tr_key[int(u) * TR.KEY_STRIDE + 1]
			var m: Dictionary = mem[u]
			if int(m.get(2, 0)) > 0 and b <= 3:
				kids += float(int(m[2])) * (0.6 if b == 3 else 1.0)
			if p.tr_key[int(u) * TR.KEY_STRIDE + 2] == 1 and int(m.get(1, 0)) > 0 and b >= 3:
				wives[mini(10, b - 3)] += float(int(m[1]))
				wt += float(int(m[1]))
		if wt <= 0.0:
			continue
		var hhk: float = minf(wt, kids)
		for i: int in 11:
			got[i] += hhk * wives[i] / wt
	var tg: float = 0.0
	var tr: float = 0.0
	for i2: int in 11:
		tg += got[i2]
		tr += float(ref[i2])
	var bad: int = 0
	var txt: String = ""
	for i3: int in 11:
		if float(ref[i3]) < 50000.0:
			continue
		var a: float = got[i3] / tg
		var r: float = float(ref[i3]) / tr
		bad += 1 if absf(a - r) > 0.05 else 0
		txt += " %d: %.3f/%.3f;" % [15 + 5 * i3, a, r]
	check(bad == 0, "T1s-gapm (R85 第15-5表, CHECK, ±5pt T) couple households with a child under 18 by the wife's band, the start/census shares (%.0f / %.0f households): cells beyond 5 points %d;%s" % [tg, tr, bad, txt])
	print("REPORT T1s-gapm the youngest and oldest child classes are not held by T1 (each household's children), revisited when T2's points carry them")


## A P95 row's allowed exceedances (V111 (3)): 5% of n cells plus 2 binomial SE, floored
## T1s-b*: R77c's backtest rows as the tool wrote them into the spec, and the start's couples against the block
func _t1s_b(p) -> void:
	var c24: Dictionary = TR._v(p, "couples_2024")
	var bt: Dictionary = c24["backtest"]
	for row: Array in [["T1s-bnw", "nat_wife", 0.0420], ["T1s-bnh", "nat_husband", 0.0440], ["T1s-bpw", "pref_wife", 0.0471], ["T1s-bph", "pref_husband", 0.0437], ["T1s-bpr", "pref_rel", 0.0316], ["T1s-bj35", "joint_35", 0.0682], ["T1s-bja", "joint_all", 0.0688]]:
		var r: Dictionary = bt[row[1]]
		var same: bool = absf(float(r["p95"]) - float(row[2])) < 0.0001
		# Why not the reproduction for the prefecture rows under 'pref' rates (amended after its first run, §R rule 4): their tolerances
		# are M020's on the national rates, and the prefectures' own survival and leaving (17:10) changed the method they were read on
		var own: bool = str(c24.get("rates", "nat")) == "pref" and str(row[1]).begins_with("pref")
		var p_ok: bool = float(r["p95"]) <= float(row[2]) + 0.0001 if own else same
		check(p_ok and int(r["beyond"]) <= int(floor(float(r["allowed"]))) and int(r["beyond_twice"]) == 0, "%s (§12.15, M014 R3, the prefecture rows M020's; the tool's 2015 -> 2020 backtest read from the spec, marriage_share '%s', rates '%s') %s, %d cells: P95 %.4f against the declared %.4f (%s); beyond it %d (at most %d, 5%% + 2 SE); beyond twice it %d (must be 0); max %.4f" % [row[0], str(c24["marriage_share"]), str(c24.get("rates", "nat")), row[1], int(r["n"]), float(r["p95"]), float(row[2]), ("at most it" if p_ok else "ABOVE it") if own else ("reproduced" if same else "NOT reproduced"), int(r["beyond"]), int(floor(float(r["allowed"]))), int(r["beyond_twice"]), float(r["max"])])
	var want: float = 0.0
	for code: Variant in c24["by_pref"]:
		if str(code) != "0":
			for hr: Array in c24["by_pref"][code]:
				for x: Variant in hr:
					want += float(x)
	print("REPORT T1s-b the start's couples %d (head and non-head) against R77c's prefectures %.0f (national %.0f): clipped at the cells' persons %.0f" % [int(p.tr_margins["r77_couples"]), want, float(c24["totals"]["start_national"]), float(p.tr_margins.get("c24_clip", 0.0))])


func _p95_allow(n: int) -> int:
	return int(floor(0.05 * float(n) + 2.0 * sqrt(float(n) * 0.05 * 0.95)))


## T1s-ma: the units' married-apart against M − C recomputed from the spec, tr_couples and the cross-tier cells
func _t1s_ma(p) -> void:
	var ex21: Dictionary = _m21_expected(p)
	var have := {}
	var neg: int = 0
	var over: int = 0
	for u: int in p.tr_units:
		var b: int = p.tr_key[u * TR.KEY_STRIDE + 1]
		var x: float = p.tr_married_apart[u]
		neg += 1 if x < 0.0 else 0
		over += 1 if x > 1.0 else 0
		if b * 5 < 15:
			neg += 1 if x != 0.0 else 0
			continue
		var ck: String = "%d|%d|%d" % [p.tr_key[u * TR.KEY_STRIDE], b, p.tr_key[u * TR.KEY_STRIDE + 2]]
		have[ck] = float(have.get(ck, 0.0)) + x * float(p.tr_count[u])
	var bad: int = 0
	var worst: float = 0.0
	for ck4: String in ex21:
		var g: float = absf(float(have.get(ck4, 0.0)) - (float(ex21[ck4][1]) - float(ex21[ck4][2])))
		worst = maxf(worst, g)
		bad += 1 if g > 1e-6 else 0
	var rep: Dictionary = p.tr_margins["ma"]
	check(bad == 0 and neg == 0 and over == 0, "T1s-ma (§12.12 (6), RE-DECLARED §12.16; a READ-BACK, its number D) the units' married-apart against the couple persons x 2020's married-apart ratio (marital_2024) per prefecture x band x sex: %d of %d cells off beyond 1e-6 (worst %s); shares negative or under 15 and not 0 %d, above 1 %d" % [bad, ex21.size(), str(worst), neg, over])
	var nat: PackedFloat64Array = rep["national"]
	var txt: String = ""
	for b2: int in range(3, TR.BANDS):
		for s2: int in 2:
			var at: int = (b2 * 2 + s2) * 4
			if nat[at + 1] > 0.0 and nat[at + 3] > 0.0:
				txt += " %d%s %.3f (2020 %.3f);" % [b2 * 5, "m" if s2 == 0 else "f", nat[at] / nat[at + 1], nat[at + 2] / nat[at + 3]]
	print("REPORT T1s-ma the married-apart share of the married by band x sex, 2024 start (2020 CHECK):%s" % txt)
	print("REPORT T1s-ma cells 20+ where the married plus the start's never-married exceed the persons %d" % int(rep["over1"]))


## §12.16: per "code|band|sex" (15+) [persons, married, couple persons, never married, widowed, divorced, residual] recomputed from
## marital_2024, the units' counts and tr_couples / tr_nh_couples less the cross-tier cells
func _m21_expected(p) -> Dictionary:
	var m24: Dictionary = TR._v(p, "marital_2024")["by_pref"]
	var imm: Dictionary = TR._v(p, "immigration_2020_2023")
	var n := {}
	for u: int in p.tr_units:
		var b: int = p.tr_key[u * TR.KEY_STRIDE + 1]
		if b * 5 >= 15:
			var ck: String = "%d|%d|%d" % [p.tr_key[u * TR.KEY_STRIDE], b, p.tr_key[u * TR.KEY_STRIDE + 2]]
			n[ck] = float(n.get(ck, 0.0)) + float(p.tr_count[u])
	var c := {}
	for src: Dictionary in [p.tr_couples, p.tr_nh_couples]:
		for key: String in src:
			var k: PackedStringArray = key.split("|")
			for sx: int in 2:
				var ck2: String = "%s|%d|%d" % [k[0], int(k[1 + sx]) + 3, sx]
				c[ck2] = float(c.get(ck2, 0.0)) + float(src[key])
	var cross: Dictionary = p.tr_margins.get("r77_cross_cells", {})
	for ck3: String in cross:
		c[ck3] = float(c.get(ck3, 0.0)) - float(cross[ck3])
	var out := {}
	for ck4: String in n:
		var kk: PackedStringArray = ck4.split("|")
		var row: Array = m24[kk[0]][int(kk[2])][mini(int(kk[1]) - 3, 14)]
		var cp: float = maxf(0.0, float(c.get(ck4, 0.0)))
		var mar: float = minf(float(n[ck4]), cp * (1.0 + float(row[1])))
		var nv: float = maxf(0.0, float(n[ck4]) - mar - float(row[3]) - float(row[4])) if float(row[2]) < 0.0 else float(row[2])
		var res: float = float(n[ck4]) - mar - nv - float(row[3]) - float(row[4])
		var bi: int = mini(int(kk[1]) - 3, 14)
		var iv: float = minf(maxf(0.0, float(imm["by_pref"][kk[0]][int(kk[2])][bi])), maxf(0.0, res))
		var ish: Array = imm["marital_shares"][int(kk[2])][bi]
		var res2: float = res - iv
		var nonm: float = nv + float(row[3]) + float(row[4])
		var f: float = maxf(0.0, 1.0 + res2 / nonm) if nonm > 0.0 else 0.0
		out[ck4] = [float(n[ck4]), mar + iv * float(ish[1]), cp, (nv * f if nonm > 0.0 else maxf(0.0, res2)) + iv * float(ish[0]), float(row[3]) * f + iv * float(ish[2]), float(row[4]) * f + iv * float(ish[3]), res, iv]
	return out


## T1s-cpb, T1s-co, T1s-cc, T1s-o4, T1s-lp1, T1s-ip (§12.16 (3), M022 §4; each against its prediction)
func _t1s_m22(p) -> void:
	var c24: Dictionary = TR._v(p, "couples_2024")["by_pref"]
	var by_p := {}
	var by_pb := {}
	for src: Dictionary in [p.tr_couples, p.tr_nh_couples]:
		for key: String in src:
			var k: PackedStringArray = key.split("|")
			by_p[k[0]] = int(by_p.get(k[0], 0)) + int(src[key])
			by_pb[k[0] + "|" + k[1]] = int(by_pb.get(k[0] + "|" + k[1], 0)) + int(src[key])
	var bad_p: int = 0
	var bad_b: int = 0
	var worst_b: float = 0.0
	var off_p: Array = []
	for code: Variant in c24:
		if str(code) == "0":
			continue
		var tot: float = 0.0
		for hb: int in 15:
			var row: float = 0.0
			for wb: int in 15:
				row += float(c24[code][hb][wb])
			tot += row
			var g: float = absf(float(by_pb.get(str(code) + "|" + str(hb), 0)) - row)
			worst_b = maxf(worst_b, g)
			bad_b += 1 if g > 15.0 else 0
		if absf(float(by_p.get(str(code), 0)) - tot) > 1.0:
			bad_p += 1
			off_p.append([str(code), int(by_p.get(str(code), 0)), tot])
	check(bad_p == 0 and bad_b == 0, "T1s-cpb (§12.16 (3), an IDENTITY) the couples placed in types 1, 2 and 4 (head and non-head) against R77c's: prefectures off by more than the total's rounding (1) %d of 47 %s; prefecture x husband band beyond the cells' rounding (15) %d, worst %.1f" % [bad_p, str(off_p), bad_b, worst_b])
	var heads := PackedInt64Array([0, 0, 0, 0, 0])
	var h4c: int = 0
	for hk: String in p.tr_hh:
		var t: int = int(hk.get_slice("|", 1))
		if t > 4:
			continue
		heads[t] += int(p.tr_hh[hk]["count"])
	for key2: String in p.tr_couples:
		if int(key2.get_slice("|", 3)) == 4:
			h4c += int(p.tr_couples[key2])
	var h4s: float = 0.0
	for c5: Variant in p.tr_margins["h4s"]:
		h4s += float(p.tr_margins["h4s"][c5])
	check(absf(float(heads[1]) - 10.92e6) <= 0.02e6, "T1s-co (§12.16 (3), a READ-BACK; M022 predicts 10.92 M +- 0.02 M) couple-only households %d" % heads[1])
	check(absf(float(heads[2]) - 13.24e6) <= 0.15e6, "T1s-cc (§12.16 (3), a TRANSCRIPTION; M022 predicts 13.24 M +- 0.15 M) couple + children households %d" % heads[2])
	check(absf(float(heads[4]) - 4.11e6) <= 0.1e6, "T1s-o4 (§12.16 (3), a TRANSCRIPTION; M022 predicts 4.11 M +- 0.1 M = 2.50 couple-headed + 1.61 single-headed) 'other' households %d (head couples placed %d, single-headed target %.0f)" % [heads[4], h4c, h4s])
	var ht: Dictionary = TR._v(p, "household_target")
	check(absi(heads[3] - int(round(float(ht["by_pref"]["0"][3])))) <= 1000, "T1s-lp1 (§12.16 (3), a TRANSCRIPTION of M017's target) lone-parent households %d against %.0f" % [heads[3], float(ht["by_pref"]["0"][3])])
	var txt: String = ""
	var tot_h: int = 0
	var tot_i: float = 0.0
	for t2: int in 5:
		tot_h += heads[t2]
		tot_i += float(ht["by_pref"]["0"][t2])
		txt += " %s %d / %.0f (%+.0f);" % [["one-person", "couple only", "couple + children", "lone parent", "other"][t2], heads[t2], float(ht["by_pref"]["0"][t2]), float(heads[t2]) - float(ht["by_pref"]["0"][t2])]
	print("REPORT T1s-ip (§12.16 (3), M022; M022 predicts the gaps -0.33 / -0.37 / +0.13 M and -0.66 M in all) the households by type against IPSS's ratio (M017's targets, CHECK):%s total %d / %.0f (%+.0f); the couple + children shortfall taken from type 4 %.0f" % [txt, tot_h, tot_i, float(tot_h) - tot_i, float(p.tr_margins.get("t2_clip", 0.0))])


## T1s-1pi (§12.16, TO_E 17:55, M023): one-person households by householder sex x 10-year band against census 2020 x IPSS's ratio
func _t1s_1pi(p) -> void:
	var ck: Dictionary = TR._v(p, "one_person_check_2024")
	var tol: Dictionary = ck["tolerance"]
	var got := PackedFloat64Array()
	got.resize(16)
	for hk: String in p.tr_hh:
		if int(hk.get_slice("|", 1)) != 0:
			continue
		var mem: Dictionary = p.tr_hh[hk]["members"]
		for u in mem:
			var b: int = p.tr_key[int(u) * TR.KEY_STRIDE + 1]
			if b < 3:
				continue
			got[p.tr_key[int(u) * TR.KEY_STRIDE + 2] * 8 + mini((b - 3) / 2, 7)] += float((mem[u] as Dictionary).get(0, 0))
	var want := PackedFloat64Array()
	var tg: float = 0.0
	var tw: float = 0.0
	for s: int in 2:
		for b2: int in 8:
			want.append(float(ck["by_sex"][s][b2]))
			tw += float(ck["by_sex"][s][b2])
			tg += got[s * 8 + b2]
	var lev: float = tg / tw
	var beyond: int = 0
	var worst: float = 0.0
	var txt: String = ""
	for c: int in 16:
		var e: float = got[c] / (want[c] * lev) - 1.0
		worst = maxf(worst, absf(e))
		beyond += 1 if absf(e) > float(tol["cell"]) else 0
		txt += " %s %s %.0f/%.0f (%+.3f);" % ["m" if c < 8 else "f", ck["bands"][c % 8], got[c], want[c] * lev, e]
	check(beyond <= int(tol["cells_beyond_at_most"]) and worst <= float(tol["max"]), "T1s-1pi (§12.16, M023, M024; CHECK, INDEPENDENT of T1 in the age drift and SHARED in the age-unknown's allocation, M017b's IPF; the comparator census 2020 x IPSS 2018's ratio levelled x%.4f to T1's total) one-person households by householder sex x 10-year band: cells beyond %.1f%% %d (at most %d), worst %.3f (at most %.3f);%s" % [lev, 100.0 * float(tol["cell"]), beyond, int(tol["cells_beyond_at_most"]), worst, float(tol["max"]), txt])


## T1s-ms2, T1s-nmt, T1s-res (§12.16)
func _t1s_m21(p) -> void:
	var ex21: Dictionary = _m21_expected(p)
	var ma := {}
	for u: int in p.tr_units:
		var ck: String = "%d|%d|%d" % [p.tr_key[u * TR.KEY_STRIDE], p.tr_key[u * TR.KEY_STRIDE + 1], p.tr_key[u * TR.KEY_STRIDE + 2]]
		ma[ck] = float(ma.get(ck, 0.0)) + p.tr_married_apart[u] * float(p.tr_count[u])
	var bad: int = 0
	var nat := PackedFloat64Array()   # band x sex: persons, married, never, widowed, divorced, residual, immigrants
	nat.resize(15 * 2 * 7)
	for ck2: String in ex21:
		var e: Array = ex21[ck2]
		if absf(float(e[2]) + float(ma.get(ck2, 0.0)) - float(e[1])) > 1e-6 * maxf(1.0, float(e[0])):
			bad += 1
		var kk: PackedStringArray = ck2.split("|")
		var at: int = (mini(int(kk[1]) - 3, 14) * 2 + int(kk[2])) * 7
		for j: int in 7:
			nat[at + j] += float(e[[0, 1, 3, 4, 5, 6, 7][j]])
	check(bad == 0, "T1s-ms2 (§12.16, an IDENTITY) married = couple persons + married-apart per prefecture x band x sex: %d of %d cells off beyond 1e-6 of the cell" % [bad, ex21.size()])
	var m24: Dictionary = TR._v(p, "marital_2024")
	var nat24: Array = m24["by_pref"]["0"]
	var flip: int = 0
	var txt: String = ""
	for s: int in 2:
		for b: int in range(1, 15):
			var r: Array = nat24[s][b]
			var traced: float = float(r[0]) * (1.0 + float(r[1])) + float(r[2]) + float(r[3]) + float(r[4])
			var sh24: float = float(r[2]) / traced if traced > 0.0 else 0.0
			var sh20: float = float(m24["never_share_2020"][s][b])
			var sh15: float = float(m24["never_share_2015"][s][b])
			var d1: float = (sh24 - sh20) / 4.0
			var d0: float = (sh20 - sh15) / 5.0
			if b >= 6 and b <= 10 and d1 * d0 < 0.0:
				flip += 1
			txt += " %d%s %.3f/%.3f/%.3f;" % [15 + 5 * b, "m" if s == 0 else "f", sh15, sh20, sh24]
	check(flip == 0, "T1s-nmt (§12.16, CHECK, a tripwire T) the national never-married share 2015 / 2020 (R82) / 2024 traced (marital_2024 nationally): bands 45-69 whose 2020-24 change per year has the opposite sign to 2015-20's %d (must be 0);%s" % [flip, txt])
	var fx: Array = TR._v(p, "foreign_2022_by_sex_band")["national"]
	var worst: float = 0.0
	var txt2: String = ""
	var res_t: float = 0.0
	var imm_t: float = 0.0
	for s2: int in 2:
		for b2: int in 15:
			var at2: int = (b2 * 2 + s2) * 7
			var sh: float = nat[at2 + 5] / nat[at2] if nat[at2] > 0.0 else 0.0
			worst = maxf(worst, absf(sh))
			res_t += nat[at2 + 5]
			imm_t += nat[at2 + 6]
			txt2 += " %d%s %+.0f (%+.1f%%; immigrants %.0f; foreign 2022 %d);" % [15 + 5 * b2, "m" if s2 == 0 else "f", nat[at2 + 5], 100.0 * sh, nat[at2 + 6], int(fx[s2][b2])]
	var tot := PackedFloat64Array([0, 0, 0, 0, 0])
	for k: int in 15 * 2:
		for j2: int in 5:
			tot[j2] += nat[k * 7 + j2]
	print("REPORT T1s-res (§12.16, a tripwire at 12%% of a band, T) the residual (persons less married, never married, widowed and divorced), %+.0f in all, of it immigration (R90, §12.16 (4)) %.0f (%.1f%%), by band x sex, with R81's 2022 foreign stock beside it:%s" % [res_t, imm_t, 100.0 * imm_t / maxf(1.0, res_t), txt2])
	print("REPORT T1s-res the start 15+ by state after the residual: persons %.0f, married %.0f, never married %.0f, widowed %.0f, divorced %.0f; the most beyond 12%%: %s" % [tot[0], tot[1], tot[2], tot[3], tot[4], "none" if worst <= 0.12 else "%.3f" % worst])


func _quartile(qb: Array, y: float) -> int:
	return 0 if y < float(qb[0]) else (1 if y < float(qb[1]) else (2 if y < float(qb[2]) else 3))


## Pearson's statistic of four bins against a quarter each, at n_eff observations
func _chi2(bins: PackedFloat64Array, tot: float, n_eff: float) -> float:
	var x: float = 0.0
	for k: int in 4:
		var d: float = bins[k] / maxf(1.0, tot) - 0.25
		x += d * d / 0.25
	return x * n_eff


func _shares(bins: PackedFloat64Array) -> String:
	var t: float = bins[0] + bins[1] + bins[2] + bins[3]
	return "[%.3f, %.3f, %.3f, %.3f]" % [bins[0] / t, bins[1] / t, bins[2] / t, bins[3] / t]


func _same(a: float, b: float) -> bool:
	return absf(a - b) <= 1e-12 * absf(b)


func _init() -> void:
	var st = MS.new()
	st.load(2024, ["JPN"])
	var prefs: Dictionary = CANON.load_json("res://data/modern/polity/jpn_prefectures.json")["prefectures"]
	var t0: int = Time.get_ticks_msec()
	var p = _build(st, prefs, 1)
	var ms: int = Time.get_ticks_msec() - t0
	check(p.error == "", "tiers built: '%s' (%d units, %d individuals, %d ms)" % [p.error, p.tr_units, p.n, ms])
	# T1s-a and T1s-e
	var by_pref := {}
	var by_bs := {}
	var total: int = 0
	var age_ok: bool = true
	var neg: int = 0
	var old_age := {}
	var holders := {}
	for u: int in p.tr_units:
		var c: int = p.tr_key[u * TR.KEY_STRIDE]
		var bs: int = p.tr_key[u * TR.KEY_STRIDE + 1] * 2 + p.tr_key[u * TR.KEY_STRIDE + 2]
		by_pref[c] = int(by_pref.get(c, 0)) + p.tr_count[u]
		by_bs[bs] = int(by_bs.get(bs, 0)) + p.tr_count[u]
		total += p.tr_count[u]
		var s5: int = 0
		var b17: bool = p.tr_key[u * TR.KEY_STRIDE + 1] == TR.BANDS - 1
		for y: int in TR.AGE_SLOTS:
			s5 += p.tr_age_counts[u * TR.AGE_SLOTS + y]
			var a0: int = p.tr_key[u * TR.KEY_STRIDE + 1] * 5 + y
			old_age[a0] = int(old_age.get(a0, 0)) + p.tr_age_counts[u * TR.AGE_SLOTS + y]
			if p.tr_age_counts[u * TR.AGE_SLOTS + y] > 0:
				holders[a0] = int(holders.get(a0, 0)) + 1
			if p.tr_age_counts[u * TR.AGE_SLOTS + y] < 0 or (not b17 and y >= 5 and p.tr_age_counts[u * TR.AGE_SLOTS + y] != 0):
				neg += 1
		age_ok = age_ok and s5 == p.tr_count[u]
	for i: int in p.n:
		by_pref[p.pref[i]] = int(by_pref.get(p.pref[i], 0)) + 1
		by_bs[TR.band_of(p.age[i]) * 2 + p.sex[i]] = int(by_bs.get(TR.band_of(p.age[i]) * 2 + p.sex[i], 0)) + 1
		total += 1
	var pop: int = 0
	var worst_pref: int = 0
	for code: String in prefs:
		var want: int = int(prefs[code]["pop_thousand"]) * 1000
		pop += want
		worst_pref = maxi(worst_pref, absi(int(by_pref.get(int(code), 0)) - want))
	var ctot: float = 0.0
	for a: int in p.cohort.size():
		ctot += p.cohort[a]
	var worst_bs: float = 0.0
	for bs2: int in by_bs:
		var share: float = 0.0
		for a2: int in p.AGES:
			if TR.band_of(a2) * 2 + (a2 * 0) == bs2 - bs2 % 2 + 0 and false:
				pass
		# the cohort's share of this band x sex
		var cs: float = 0.0
		for a3: int in p.AGES:
			if TR.band_of(a3) * 2 + 0 == bs2 - bs2 % 2:
				cs += p.cohort[a3 * p.SEXES + bs2 % 2]
		share = cs / ctot
		worst_bs = maxf(worst_bs, absf(float(by_bs[bs2]) / float(pop) - share))
	check(worst_pref == 0 and total == pop, "T1s-a / T1s-e the sum rule: Σ counts %d = population %d; worst prefecture gap %d persons; band x sex shares within %.6f of the cohort's (rounding only)" % [total, pop, worst_pref, worst_bs])
	check(age_ok and neg == 0 and worst_bs < 1e-4, "T1s-e single-age counts sum to each unit's count %s, %d slots below 0 or outside the band; the band x sex shape held to %.6f" % [str(age_ok), neg, worst_bs])
	for i8: int in p.n:
		old_age[p.age[i8]] = int(old_age.get(p.age[i8], 0)) + 1
	var bad_o: int = 0
	var bad_oh: int = 0
	var worst_o: float = 0.0
	var worst_a: int = 0
	var worst_r: float = 0.0
	for a8: int in p.AGES:
		var want8: float = (p.cohort[a8 * p.SEXES] + p.cohort[a8 * p.SEXES + 1]) / ctot * float(pop)
		var gap8: float = absf(float(old_age.get(a8, 0)) - want8)
		var h8: float = float(holders.get(a8, 0))
		if gap8 > worst_o:
			worst_o = gap8
			worst_a = a8
		worst_r = maxf(worst_r, gap8 / (3.0 * sqrt(h8 / 4.0) + 1.0))
		if gap8 > 3.0 * sqrt(h8 / 4.0) + 1.0:
			bad_o += 1
		if gap8 > h8 + 1.0:
			bad_oh += 1
	check(bad_o == 0 and bad_oh == 0 and int(old_age.get(100, 0)) > 0, "T1s-o (§12.10 V3) every single age 0-100 against the cohort: %d of %d ages beyond 3 sqrt(H/4) + 1 (an unbiased rounding's bound; the worst at %.2f of it), %d beyond H + 1; worst gap %.1f persons at age %d; age 100+ holds %d" % [bad_o, p.AGES, worst_r, bad_oh, worst_o, worst_a, int(old_age.get(100, 0))])
	# T1s-b
	var comp := {}
	for hk: String in p.tr_hh:
		var mem: Dictionary = p.tr_hh[hk]["members"]
		for u2 in mem:
			for r in mem[u2]:
				comp[u2] = int(comp.get(u2, 0)) + int(mem[u2][r])
	var bad_b: int = 0
	for u3: int in p.tr_units:
		if int(comp.get(u3, 0)) != p.tr_count[u3]:
			bad_b += 1
	check(bad_b == 0, "T1s-b compositions sum to the person-bundles' counts: %d of %d bundles off (%d household-bundles)" % [bad_b, p.tr_units, p.tr_hh.size()])
	# T1s-b2: the household-bundles as households
	var bad_h: int = 0
	var bad_pz: int = 0
	var bad_f: int = 0
	var short_p: int = 0
	var part_def: int = 0
	var short_t := {}
	var part_over: int = 0
	var nopart_t := {}
	var t4_cases := {}
	var n_hh: int = 0
	for hk2: String in p.tr_hh:
		var f2: PackedStringArray = hk2.split("|")
		var t2: int = int(f2[1])
		var z2: int = int(f2[3])
		var cnt2: int = int(p.tr_hh[hk2]["count"])
		n_hh += cnt2
		var hd: int = 0
		var pt: int = 0
		var ps: int = 0
		var mem2: Dictionary = p.tr_hh[hk2]["members"]
		for u5 in mem2:
			hd += int(mem2[u5].get(0, 0))
			pt += int(mem2[u5].get(1, 0))
			for r5 in mem2[u5]:
				ps += int(mem2[u5][r5])
		var cross2: int = int(p.tr_hh[hk2].get("cross", 0))
		ps += cross2
		if hd + cross2 != cnt2:
			bad_h += 1
		if (z2 < TR.SIZE_MIN[t2] or z2 > TR.SIZE_MAX[t2]) and (ps > 0 or cnt2 > 0):
			bad_f += 1
			print("REPORT T1s-b2 forbidden size: %s households %d persons %d heads %d partners %d" % [hk2, cnt2, ps, hd, pt])
		var size2: int = z2 + 1
		if z2 < 4 and ps > size2 * cnt2:
			bad_pz += 1
		short_p += maxi(0, size2 * cnt2 - ps)
		short_t[t2] = int(short_t.get(t2, 0)) + maxi(0, size2 * cnt2 - ps)
		if t2 == 4 and size2 * cnt2 > ps:
			t4_cases["%s|%s" % [f2[0], f2[2]]] = int(t4_cases.get("%s|%s" % [f2[0], f2[2]], 0)) + size2 * cnt2 - ps
		if t2 == 1 or t2 == 2:
			nopart_t[t2] = int(nopart_t.get(t2, 0)) + maxi(0, hd - pt)
			part_def += maxi(0, cnt2 - pt)
			part_over += maxi(0, pt - cnt2)
	check(bad_h == 0 and bad_f == 0 and bad_pz == 0 and part_over <= int(p.tr_margins.get("r77_cross_husband", 0)) and short_p == int(p.tr_margins["hh_unfilled"]), "T1s-b2 households: %d households in %d household-bundles; heads off the count in %d, persons in a forbidden size in %d, persons above size x households in %d, partners above heads in the couple types %d (at most the cross-tier husbands %d, §12.12 (7)); persons short of size x households %d (reported %d), couples without a partner %d (partner supply short %d); the shortfall by type %s; the heads against the household-type target by type (§12.14; type 1 R77's couple-only) %s" % [n_hh, p.tr_hh.size(), bad_h, bad_f, bad_pz, part_over, int(p.tr_margins.get("r77_cross_husband", 0)), short_p, int(p.tr_margins["hh_unfilled"]), part_def, int(p.tr_margins["hh_partner_short"]), str(short_t), str(p.tr_margins["head_gap"])])
	var un_t: Dictionary = p.tr_margins.get("hh_unfilled_t", {})
	var un_03: int = int(un_t.get(0, 0)) + int(un_t.get(3, 0))
	var un_2: int = int(un_t.get(2, 0))
	check(un_03 == 0 and un_2 <= int(nopart_t.get(2, 0)) and int(p.tr_margins.get("hh_childless", 0)) == 0, "T1s-hh0 (§12.12 (5), V111 (1), AMENDED after its first run) persons below their type's minimum size: types 0 and 3 %d; type 2 %d (at most its couple heads without a placed partner %d); the counted cases, type 1 %d (partnerless heads %d), type 4 %d ('other' heads with no non-head member); by type %s; couple + children and single-parent households the minimum pass left without a child %d" % [un_03, un_2, int(nopart_t.get(2, 0)), int(un_t.get(1, 0)), int(nopart_t.get(1, 0)), int(un_t.get(4, 0)), str(un_t), int(p.tr_margins.get("hh_childless", 0))])
	print("REPORT T1s-hh0 the minimum pass's children from outside R83's 1st-99th window, by parent %s; households left without a child by parent %s" % [str(p.tr_margins.get("hh_outside_by", {})), str(p.tr_margins.get("hh_childless_by", {}))])
	var out_by: Dictionary = p.tr_margins.get("hh_outside_by", {})
	var out_n: int = 0
	var out_else: int = 0
	for ko: String in out_by:
		out_n += int(out_by[ko])
		out_else += 0 if ko == "t2 mother 15-19" else int(out_by[ko])
	check(out_else == 0, "T1s-hh0 (a) (V113) the minimum pass's children outside R83's 1st-99th window: %d, all to wives 15-19 (elsewhere %d, must be 0)" % [out_n, out_else])
	var t4_n: int = int(p.tr_margins.get("hh_unfilled_t", {}).get(4, 0))
	var t4_keys: Array = t4_cases.keys()
	t4_keys.sort()
	var t4_txt: String = ""
	for kc: String in t4_keys:
		t4_txt += " %s (prefecture|householder band): %d;" % [kc, int(t4_cases[kc])]
	check(t4_n <= 1000, "T1s-hh0 (b) (V113) type 4 ('other') persons below the minimum size %d, at most 1,000 (T, a tripwire); the cases:%s" % [t4_n, t4_txt])
	# T1s-c9: the income tail (§12.8 item 9): the target lines are R67a's, every class on its side of each line after the mapping, the
	# persons' share above each line against its published share within 2 SE, no empty gap at a line; and the top 0.01% as one law:
	# the individuals' and the bundled points' shares in the fitted tail's quartile bins (§12.10 V1). The class means are T1s-cm's
	# (test_modern_tiers_means.gd)
	var inc: PackedFloat64Array = p.tr_points["income"]
	var tl: Dictionary = p.tr_spec["income_tail"]["value"]
	var t_log: PackedFloat64Array = p.tr_margins["tail_lines"]
	var t_m := PackedFloat64Array()
	for j0: int in t_log.size():
		t_m.append(exp(t_log[j0]))
	var bad_l: int = 0
	for j1: int in tl["lines_yen_year"].size():
		var want_l: float = float(tl["lines_yen_year"][j1]) / 12.0 / 1e4
		if absf(t_m[j1 + 1] - want_l) / want_l > 1e-9:
			bad_l += 1
	var hold: Array = []
	for i0: int in p.n:
		hold.append([p.tr_indiv_code[i0] / (TR.NTYPE * TR.NEMP), p.income[i0], 1.0])
	for g: int in p.tr_pt_code.size():
		var k: int = p.tr_pt_code[g] / (TR.NTYPE * TR.NEMP)
		if k < TR.CLASS_NONE:
			hold.append([k, inc[g], float(p.tr_pt_mass[g])])
	var c_min := PackedFloat64Array([INF, INF, INF, INF, INF, INF])
	var c_max := PackedFloat64Array([0.0, 0.0, 0.0, 0.0, 0.0, 0.0])
	var above := PackedFloat64Array([0.0, 0.0, 0.0, 0.0, 0.0])
	var near := PackedFloat64Array([0.0, 0.0, 0.0, 0.0, 0.0])
	var w_tot: float = 0.0
	var w_sq: float = 0.0
	for h: Array in hold:
		var kh: int = int(h[0])
		var yh: float = float(h[1])
		var wh: float = float(h[2])
		c_min[kh] = minf(c_min[kh], yh)
		c_max[kh] = maxf(c_max[kh], yh)
		w_tot += wh
		w_sq += wh * wh
		for j2: int in t_m.size():
			if yh > t_m[j2]:
				above[j2] += wh
			if absf(yh - t_m[j2]) <= 0.02 * t_m[j2]:
				near[j2] += wh
	var pub_s := PackedFloat64Array([0.5, 0.1, 0.01, 0.001, 0.0001])
	var bad_side: int = 0
	var bad_share: int = 0
	var bad_gap: int = 0
	var txt_t: String = ""
	for j3: int in t_m.size():
		# line j3 runs between class 4 - j3 (above) and 5 - j3 (below)
		if c_min[4 - j3] < t_m[j3] * (1.0 - 1e-9) or c_max[5 - j3] > t_m[j3] * (1.0 + 1e-9):
			bad_side += 1
		var sh: float = above[j3] / w_tot
		var se_s: float = sqrt(pub_s[j3] * (1.0 - pub_s[j3]) * w_sq) / w_tot
		if absf(sh - pub_s[j3]) > 2.0 * se_s + 1e-4 * pub_s[j3]:
			bad_share += 1
		if near[j3] <= 0.0:
			bad_gap += 1
		txt_t += " %.2f (share above %.5f, mass within 2%% %.0f)" % [t_m[j3], sh, near[j3]]
	# T1s-c9 (§12.8 10.2): the interpolation's Q strictly increasing over the ranks it covers; Q's slope left and right of the 0.1%
	# knot, where the spline meets the Pareto above it, reported
	var gpi: Dictionary = p.tr_margins["gpi"]
	var bad_mono: int = 0
	var q_prev: float = 0.0
	for i9: int in 20001:
		var p9: float = 0.5 + 0.4999 * float(i9) / 20000.0
		var q9: float = TR._gpi_q(gpi, p9)
		if q9 <= q_prev:
			bad_mono += 1
		q_prev = q9
	var e9: float = 1e-7
	var sl_l: float = (TR._gpi_q(gpi, 0.999) - TR._gpi_q(gpi, 0.999 - e9)) / e9
	var sl_r: float = (TR._gpi_q(gpi, 0.999 + e9) - TR._gpi_q(gpi, 0.999)) / e9
	check(bad_mono == 0, "T1s-c9 (GPI) Q strictly increasing on [0.5, 0.9999]: %d of 20,001 ranks not; the cash mean per adult mu %.3f M yen a year; Q's slope right ÷ left of the 0.1%% knot %.3f" % [bad_mono, float(gpi["mu"]) * 12.0 / 100.0, sl_r / sl_l])
	var cf: PackedFloat64Array = p.tr_margins["class_factor"]
	var t_x: Array = []
	for g4: int in p.tr_pt_code.size():
		if p.tr_pt_code[g4] / (TR.NTYPE * TR.NEMP) == 0:
			t_x.append([inc[g4], float(p.tr_pt_mass[g4])])
	var i_sum: float = 0.0
	var i_sq: float = 0.0
	for i3: int in p.n:
		i_sum += p.income[i3]
		i_sq += p.income[i3] * p.income[i3]
	var b_w: float = 0.0
	var b_x: float = 0.0
	for q: Array in t_x:
		b_w += float(q[1])
		b_x += float(q[0]) * float(q[1])
	var b_m: float = b_x / maxf(1.0, b_w)
	var b_v: float = 0.0
	for q2: Array in t_x:
		b_v += float(q2[1]) * float(q2[1]) * (float(q2[0]) - b_m) * (float(q2[0]) - b_m)
	b_v /= maxf(1.0, b_w * b_w)
	var i_m: float = i_sum / maxf(1.0, float(p.n))
	var i_v: float = maxf(0.0, i_sq / maxf(1.0, float(p.n)) - i_m * i_m) / maxf(1.0, float(p.n))
	var se: float = sqrt(b_v + i_v)
	var qb: Array = [TR._gpi_q(gpi, 0.999925), TR._gpi_q(gpi, 0.99995), TR._gpi_q(gpi, 0.999975)]
	var bin_i := PackedFloat64Array([0, 0, 0, 0])
	var bin_b := PackedFloat64Array([0, 0, 0, 0])
	for i4: int in p.n:
		bin_i[_quartile(qb, p.income[i4])] += 1.0
	var b_sq: float = 0.0
	for q3: Array in t_x:
		bin_b[_quartile(qb, float(q3[0]))] += float(q3[1])
		b_sq += float(q3[1]) * float(q3[1])
	var chi_i: float = _chi2(bin_i, float(p.n), float(p.n))
	var chi_b: float = _chi2(bin_b, b_w, b_w * b_w / maxf(1.0, b_sq))
	check(bad_l == 0 and bad_side == 0 and bad_share == 0 and bad_gap == 0 and chi_i < CHI2_3_99 and chi_b < CHI2_3_99, "T1s-c9 the income tail: lines off R67a's %d; classes across a line %d; shares above a line beyond 2 SE %d; lines with an empty gap %d; the lines (monthly 万円, the median first):%s; the would-be class factors (not applied) %s; the top 0.01%% as one law (§12.10 V1): the shares in the fitted tail's quartile bins, individuals %s (chi2 %.2f), bundled points by mass %s (n_eff %.0f, chi2 %.2f), against %.2f; the means printed: bundled points %.1f (%d points), individuals %.1f, gap %.1f, 2 SE %.1f" % [bad_l, bad_side, bad_share, bad_gap, txt_t, str(cf), _shares(bin_i), chi_i, _shares(bin_b), b_w * b_w / maxf(1.0, b_sq), chi_b, CHI2_3_99, b_m, t_x.size(), i_m, absf(b_m - i_m), 2.0 * se])
	var rep: Dictionary = TR.report(p)
	# SB3: each instrument's Σ over the points and the individuals = R67c's total in integer yen
	var ins: Dictionary = p.tr_spec["instruments_hh_trillion_yen"]["value"]
	var bad_sb: int = 0
	var txt_sb: String = ""
	for name: String in p.tr_instruments:
		var arr: PackedInt64Array = p.tr_instruments[name]
		var s: int = 0
		var neg_sb: int = 0
		for v: int in arr:
			s += v
			if v < 0:
				neg_sb += 1
		var want_sb: int = int(round(float(ins[name]) * 10.0)) * 100000000000
		if s != want_sb or neg_sb > 0 or arr.size() != p.tr_pt_code.size() + p.n:
			bad_sb += 1
		txt_sb += " %s %d" % [name, s]
	# the age profile read back: borrowing per adult by householder age group, relative to its mean (the 40s peak declared)
	var age_pt: PackedInt32Array = p.tr_points["age"]
	var bw := PackedFloat64Array([0, 0, 0, 0, 0, 0, 0])
	var bn := PackedFloat64Array([0, 0, 0, 0, 0, 0, 0])
	var bor: PackedInt64Array = p.tr_instruments["borrowing"]
	for g5: int in p.tr_pt_code.size():
		if age_pt[g5] >= TR.ADULT_FROM:
			var gi5: int = clampi(age_pt[g5] / 10 - 2, 0, 6)
			bw[gi5] += float(bor[g5])
			bn[gi5] += float(p.tr_pt_mass[g5])
	var txt_b: String = ""
	for gi6: int in 7:
		txt_b += " %.0f" % (bw[gi6] / maxf(1.0, bn[gi6]))
	check(bad_sb == 0 and bw[2] / bn[2] > bw[0] / bn[0] and bw[2] / bn[2] > bw[5] / bn[5], "SB3 each instrument's Σ over the points and the individuals = R67c's total in integer yen: %d instruments off (yen:%s); borrowing per adult by age group <30 .. 80+ (yen):%s" % [bad_sb, txt_sb, txt_b])
	# §12.8 10.5: one wealth record: every point's and individual's assets and debt read back from its instruments (万円 a person)
	var prof10: Dictionary = p.tr_spec["instrument_age_profiles"]["value"]["by_instrument"]
	var n_pt10: int = p.tr_pt_code.size()
	var ass10: PackedFloat64Array = p.tr_points["assets"]
	var debt10: PackedFloat64Array = p.tr_points["debt"]
	var worst10: float = 0.0
	for h10: int in n_pt10 + p.n:
		var a10: int = 0
		for nm10: String in p.tr_instruments:
			if String(prof10.get(nm10, "")) == "financial":
				a10 += (p.tr_instruments[nm10] as PackedInt64Array)[h10]
		var b10: int = (p.tr_instruments["borrowing"] as PackedInt64Array)[h10]
		var m10: float = float(p.tr_pt_mass[h10]) if h10 < n_pt10 else 1.0
		var ga: float = ass10[h10] if h10 < n_pt10 else p.assets[h10 - n_pt10]
		var gd: float = debt10[h10] if h10 < n_pt10 else p.debt[h10 - n_pt10]
		worst10 = maxf(worst10, absf(ga * m10 * 1e4 - float(a10)) / maxf(1.0, float(a10)))
		worst10 = maxf(worst10, absf(gd * m10 * 1e4 - float(b10)) / maxf(1.0, float(b10)))
	check(worst10 <= 1e-9, "§12.8 10.5 one wealth record: assets and debt against the instruments (financial sum, borrowing), worst relative gap %s over %d holders" % [str(worst10), n_pt10 + p.n])
	# T1s-n (§12.13 step 6, RE-DECLARED §12.16): the never-married share per prefecture x band x sex read back from the bundles against
	# marital_2024's never married and its residual share, recomputed here; R62 reported
	var nm_exp: Dictionary = _m21_expected(p)
	var nm_n := {}
	var nm_x := {}
	var nb_n := {}
	var nb_x := {}
	for u10: int in p.tr_units:
		var ck10: String = "%d|%d|%d" % [p.tr_key[u10 * TR.KEY_STRIDE], p.tr_key[u10 * TR.KEY_STRIDE + 1], p.tr_key[u10 * TR.KEY_STRIDE + 2]]
		nm_n[ck10] = float(nm_n.get(ck10, 0.0)) + float(p.tr_count[u10])
		nm_x[ck10] = float(nm_x.get(ck10, 0.0)) + float(p.tr_count[u10]) * p.tr_never_married[u10]
		var bs10: int = p.tr_key[u10 * TR.KEY_STRIDE + 1] * 2 + p.tr_key[u10 * TR.KEY_STRIDE + 2]
		nb_n[bs10] = float(nb_n.get(bs10, 0.0)) + float(p.tr_count[u10])
		nb_x[bs10] = float(nb_x.get(bs10, 0.0)) + float(p.tr_count[u10]) * p.tr_never_married[u10]
	var bad_n: int = 0
	var forced: int = 0
	for row: Array in p.tr_margins["nm"]:
		var ck11: String = "%d|%d|%d" % [int(row[0]), int(row[1]), int(row[2])]
		var got11: float = float(nm_x[ck11]) / float(nm_n[ck11])
		var free_in: bool = float(row[4]) > 0.0 and float(row[4]) < 1.0
		if free_in and absf(got11 - float(nm_exp[ck11][3]) / float(nm_exp[ck11][0])) > 1e-6:
			bad_n += 1
		if not free_in:
			forced += 1
	var nm62: Dictionary = p.tr_spec["never_married"]["value"]
	var txt62: String = ""
	for i62: int in (nm62["ages"] as Array).size():
		var b62: int = int(nm62["ages"][i62]) / 5
		for s62: int in 2:
			txt62 += " %d%s %.3f/%.3f;" % [b62 * 5, "m" if s62 == 0 else "f", float(nb_x.get(b62 * 2 + s62, 0.0)) / maxf(1.0, float(nb_n.get(b62 * 2 + s62, 0.0))), float(nm62["men" if s62 == 0 else "women"][i62])]
	check(bad_n == 0 and p.tr_margins["nm"].size() > 0, "T1s-n (§12.13 step 6, RE-DECLARED §12.16) never-married against marital_2024 (the cohort identity and its residual share, recomputed) per prefecture x band x sex: %d of %d cells off where the free share is inside [0, 1] (%d cells forced to 0 or 1 by the roles); R62 national, the start/R62:%s" % [bad_n, p.tr_margins["nm"].size(), forced, txt62])
	# T1s-h (§12.6): each prefecture's age groups and labour rates read back from the units against R69's
	var groups: Dictionary = p.tr_spec["age_groups_by_prefecture"]["value"]
	var plab: Dictionary = p.tr_spec["labour_by_prefecture"]["value"]["prefectures"]
	var g_pc := {}
	var l_pc := {}
	for u9: int in p.tr_units:
		var cc: int = p.tr_key[u9 * TR.KEY_STRIDE]
		var bb: int = p.tr_key[u9 * TR.KEY_STRIDE + 1]
		if not g_pc.has(cc):
			g_pc[cc] = PackedFloat64Array([0.0, 0.0, 0.0, 0.0, 0.0])
			l_pc[cc] = PackedFloat64Array([0.0, 0.0, 0.0])
		for m9: int in range(p.tr_mix_off[u9], p.tr_mix_off[u9 + 1]):
			var ee: int = p.tr_mix_code[m9] % TR.NEMP
			var n9: int = p.tr_mix_n[m9]
			g_pc[cc][TR._age_group(bb)] += float(n9)
			g_pc[cc][4] += float(n9)
			if bb >= 3:
				l_pc[cc][0] += float(n9)
				if ee == 1 or ee == 2 or ee == 3:
					l_pc[cc][1] += float(n9)
				if ee == 3:
					l_pc[cc][2] += float(n9)
	var worst_g: float = 0.0
	var worst_lf: float = 0.0
	var worst_u: float = 0.0
	for cc2: int in g_pc:
		var code2: String = "%02d" % cc2
		if groups.has(code2):
			for gi: int in 4:
				worst_g = maxf(worst_g, absf(g_pc[cc2][gi] / g_pc[cc2][4] - float(groups[code2][gi])))
		if plab.has(code2):
			worst_lf = maxf(worst_lf, absf(l_pc[cc2][1] / l_pc[cc2][0] - float(plab[code2]["labour force rate"])))
			worst_u = maxf(worst_u, absf(l_pc[cc2][2] / l_pc[cc2][1] - float(plab[code2]["unemployment rate"])))
	# T1s-h: the IPF's error is the feasibility condition read (a non-negative table with the three margins exists only if the IPF
	# converges); the later marginals' residuals reported beside it
	check(p.tr_residual[1] <= 1e-8 and int(p.tr_residual[5]) == 0, "T1s-h the fit: the IPF's worst relative margin error %s after %d rounds (feasible at <= 1e-8); R64's person-type shares against the fit (a report since §12.14), worst gap %.4f; the class marginal after the rounding, worst relative gap %.4f; the top 0.01%% tier off its real total by %d persons; never-married forced rows in T1s-n; R69 (§12.6) against the census's prefecture figures: worst age-group share gap %.4f (the cohort held nationally), worst labour-force rate gap %.4f, worst unemployment-rate gap %.4f; the households (§12.8 item 4): persons short of the minimum sizes by type %s, heads against the household-type target by type %s (§12.14; R64 read as a report)" % [str(p.tr_residual[1]), int(p.tr_residual[2]), p.tr_residual[0], p.tr_residual[6], int(p.tr_residual[5]), worst_g, worst_lf, worst_u, str(short_t), str(p.tr_margins["head_gap"])])
	# T1s-l: (0) prefecture x band x sex and (1) band x sex x type exact in integers
	var pbs := {}
	var bst := {}
	for u6: int in p.tr_units:
		var kk: String = "%d|%d|%d" % [p.tr_key[u6 * TR.KEY_STRIDE], p.tr_key[u6 * TR.KEY_STRIDE + 1], p.tr_key[u6 * TR.KEY_STRIDE + 2]]
		pbs[kk] = int(pbs.get(kk, 0)) + p.tr_count[u6]
		for m6: int in range(p.tr_mix_off[u6], p.tr_mix_off[u6 + 1]):
			var kt: String = "%d|%d|%d" % [p.tr_key[u6 * TR.KEY_STRIDE + 1], p.tr_key[u6 * TR.KEY_STRIDE + 2], (p.tr_mix_code[m6] / TR.NEMP) % TR.NTYPE]
			bst[kt] = int(bst.get(kt, 0)) + p.tr_mix_n[m6]
	for i6: int in p.n:
		var kk2: String = "%d|%d|%d" % [p.pref[i6], TR.band_of(p.age[i6]), p.sex[i6]]
		pbs[kk2] = int(pbs.get(kk2, 0)) + 1
		var kt2: String = "%d|%d|%d" % [TR.band_of(p.age[i6]), p.sex[i6], (p.tr_indiv_code[i6] / TR.NEMP) % TR.NTYPE]
		bst[kt2] = int(bst.get(kt2, 0)) + 1
	var re: Dictionary = TR.rounded_margins(p, prefs)
	var bad0: int = 0
	for k0: String in re["pbs"]:
		if int(pbs.get(k0, 0)) != int(re["pbs"][k0]):
			bad0 += 1
	var bad1: int = 0
	for k1: String in re["bst"]:
		var want1: int = int(re["bst"][k1])
		if int(bst.get(k1, 0)) != want1:
			bad1 += 1
	var d_bs: float = 0.0
	var nat_bs := {}
	for k3: String in pbs:
		var pk: PackedStringArray = k3.split("|")
		var kb3: String = pk[1] + "|" + pk[2]
		nat_bs[kb3] = int(nat_bs.get(kb3, 0)) + int(pbs[k3])
	for kb4: String in re["bs_real"]:
		d_bs = maxf(d_bs, absf(float(nat_bs.get(kb4, 0)) - float(re["bs_real"][kb4])))
	var d_bst: float = 0.0
	for kt3: String in re["bst_real"]:
		d_bst = maxf(d_bst, absf(float(bst.get(kt3, 0)) - float(re["bst_real"][kt3])))
	check(neg == 0, "T1s-a (T1b; V111 (4)) exact against the code's integer targets; the national cells from the fit's real targets (not 表V-1-3 since §12.12): band x sex from the cohort worst %.2f persons, band x sex x type from the fit's real targets worst %.2f persons (rounding)" % [d_bs, d_bst])
	var ten: Array = TR._ten_shares(p)
	var l1: float = 0.0
	var tot_p: float = 0.0
	var net := PackedFloat64Array()
	net.resize(TR.NTYPE)
	var big: Array = []
	var n10 := PackedFloat64Array()
	n10.resize(18)
	var h10 := PackedFloat64Array()
	h10.resize(18 * TR.NTYPE)
	for ba: int in TR.BANDS:
		for sa: int in 2:
			var g: int = TR._ten_band(ba) * 2 + sa
			n10[g] += float(nat_bs.get("%d|%d" % [ba, sa], 0))
			for ta: int in TR.NTYPE:
				h10[g * TR.NTYPE + ta] += float(bst.get("%d|%d|%d" % [ba, sa, ta], 0))
	var gl: Array = ["<15", "15-24", "25-34", "35-44", "45-54", "55-64", "65-74", "75-84", "85+"]
	for g2: int in 18:
		tot_p += n10[g2]
		for tb: int in TR.NTYPE:
			var wa: float = float(ten[g2 % 2][g2 / 2][tb]) * n10[g2]
			var ha: float = h10[g2 * TR.NTYPE + tb]
			l1 += absf(ha - wa)
			net[tb] += ha - wa
			if wa >= 50000.0:
				big.append([absf(ha / wa - 1.0), "%s %s type %d: %.0f against %.0f" % [gl[g2 / 2], "m" if g2 % 2 == 0 else "f", tb, ha, wa]])
	big.sort()
	big.reverse()
	var big_txt: String = ""
	for ea: Array in big.slice(0, 6):
		big_txt += " %s (%+.1f%%);" % [String(ea[1]), 100.0 * float(ea[0])]
	print("REPORT T1s-a (V111 (4); §12.13 at 表V-1-3's 10-year cells) (1)'s shift against 表V-1-3 x the start's 10-year band x sex: half the L1 %.0f persons (%.2f%% of %.0f); net by type %s; the largest relative gaps among cells of at least 50,000:%s; the projection onto the couples' fixed cells moved %.0f persons" % [l1 / 2.0, 50.0 * l1 / tot_p, tot_p, str(net), big_txt, float(p.tr_margins.get("ten_shift", 0.0))])
	check(bad0 == 0 and bad1 == 0, "T1s-l the start fit: (0) prefecture x band x sex cells off %d of %d, (1) band x sex x type cells off the code's integer targets %d of %d (an outcome since §12.12, reported against 表V-1-3 in T1s-a); column repairs %d moves, %d out of bound; couple persons above their (0) cell %d" % [bad0, re["pbs"].size(), bad1, re["bst"].size(), int(p.tr_residual[3]), int(p.tr_residual[4]), int(p.tr_margins.get("r77_over", 0))])
	# T1s-m: the points (per prefecture: P_c = K x its units, K_b by its own worth), the codes' and ages' point masses
	var bad_m: int = 0
	var bad_k: int = 0
	var bad_cm: int = 0
	var pc_n := {}
	var pc_u := {}
	var pc_k := {}
	for u0: int in p.tr_units:
		var c0: int = p.tr_key[u0 * TR.KEY_STRIDE]
		pc_n[c0] = int(pc_n.get(c0, 0)) + p.tr_count[u0]
		pc_u[c0] = int(pc_u.get(c0, 0)) + 1
		pc_k[c0] = int(pc_k.get(c0, 0)) + p.tr_pt_off[u0 + 1] - p.tr_pt_off[u0]
	var worst_pc: float = 0.0
	for c1: int in pc_u:
		worst_pc = maxf(worst_pc, absf(float(pc_k[c1]) / float(p.tr_k * int(pc_u[c1])) - 1.0))
	for u8: int in p.tr_units:
		var sm: int = 0
		var mmax: int = 0
		var by_code := {}
		var by_age := {}
		for g2: int in range(p.tr_pt_off[u8], p.tr_pt_off[u8 + 1]):
			sm += p.tr_pt_mass[g2]
			mmax = maxi(mmax, p.tr_pt_mass[g2])
			by_code[p.tr_pt_code[g2]] = int(by_code.get(p.tr_pt_code[g2], 0)) + p.tr_pt_mass[g2]
			var ya: int = TR.a_slot(p, u8, p.tr_points["age"][g2])
			by_age[ya] = int(by_age.get(ya, 0)) + p.tr_pt_mass[g2]
		var smx: int = 0
		for m8: int in range(p.tr_mix_off[u8], p.tr_mix_off[u8 + 1]):
			smx += p.tr_mix_n[m8]
			if absi(int(by_code.get(p.tr_mix_code[m8], 0)) - p.tr_mix_n[m8]) > mmax:
				bad_cm += 1
		for y8: int in TR.AGE_SLOTS:
			if absi(int(by_age.get(y8, 0)) - p.tr_age_counts[u8 * TR.AGE_SLOTS + y8]) > mmax:
				bad_cm += 1
		if sm != p.tr_count[u8] or smx != p.tr_count[u8]:
			bad_m += 1
		var c8: int = p.tr_key[u8 * TR.KEY_STRIDE]
		var worth: float = float(pc_n[c8]) / float(p.tr_k * int(pc_u[c8]))
		var kb: int = p.tr_pt_off[u8 + 1] - p.tr_pt_off[u8]
		var want_one: bool = p.tr_count[u8] > 0 and float(p.tr_count[u8]) < worth
		if (want_one and kb != 1) or (not want_one and p.tr_count[u8] > 0 and kb < 2):
			bad_k += 1
	check(bad_m == 0 and bad_k == 0 and bad_cm == 0, "T1s-m the points and the mixes: masses or mixes off their counts %d, K_b off the prefecture's rule %d, codes' or ages' point masses beyond one point mass of their counts %d; Σ K_b %d against P = 4U %d, the worst prefecture %.4f off its P_c" % [bad_m, bad_k, bad_cm, int(rep["points"]), int(rep["points_target"]), worst_pc])
	# T1s-m (§12.8 10.4): inside each unit with more than one code, the points' code index and age slot centred on the unit's means;
	# the pooled correlation over those units against 0 within 2 SE (1 ÷ sqrt of the points pooled)
	var sxy: float = 0.0
	var sxx: float = 0.0
	var syy: float = 0.0
	var n_c: int = 0
	for u12: int in p.tr_units:
		var a12: int = p.tr_pt_off[u12]
		var b12: int = p.tr_pt_off[u12 + 1]
		if b12 - a12 < 2 or p.tr_mix_off[u12 + 1] - p.tr_mix_off[u12] < 2:
			continue
		var mx: float = 0.0
		var my: float = 0.0
		for g12: int in range(a12, b12):
			mx += float(p.tr_pt_code[g12])
			my += float(TR.a_slot(p, u12, p.tr_points["age"][g12]))
		mx /= float(b12 - a12)
		my /= float(b12 - a12)
		for g13: int in range(a12, b12):
			var dx: float = float(p.tr_pt_code[g13]) - mx
			var dy: float = float(TR.a_slot(p, u12, p.tr_points["age"][g13])) - my
			sxy += dx * dy
			sxx += dx * dx
			syy += dy * dy
			n_c += 1
	var r_ca: float = sxy / sqrt(maxf(1e-30, sxx * syy))
	var se_ca: float = 1.0 / sqrt(float(maxi(1, n_c)))
	check(absf(r_ca) <= 2.0 * se_ca, "T1s-m (§12.8 10.4) the points' code and age inside the units with more than one code: pooled within-unit correlation %.4f against 0, 2 SE %.4f (%d points)" % [r_ca, 2.0 * se_ca, n_c])
	var empty_u: int = 0
	for u11: int in p.tr_units:
		if p.tr_count[u11] <= 0:
			empty_u += 1
	var pts_gap: float = absf(float(rep["points"]) / float(rep["points_target"]) - 1.0)
	check(int(rep["units"]) <= 50000 and pts_gap <= 0.02 and empty_u == 0, "T1s-k units %d against the oracle budget 50,000 (by unit size %s; %d emptied by the individuals removed, %d left at count 0); Σ K_b %.4f off P; individuals %d, persons in bundles %d, by class %s, household-bundles %d, K %d, %d ms" % [rep["units"], str(rep["by_unit_size"]), int(p.tr_margins["dropped_units"]), empty_u, pts_gap, rep["individuals"], rep["persons_in_bundles"], str(rep["persons_by_class"]), rep["households"], rep["k"], ms])
	# T1s-d
	var d1: String = p.digest()
	var q = _build(st, prefs, 1)
	var r2 = PEOPLE.new()
	r2.from_dict(bytes_to_var(var_to_bytes(p.to_dict())))
	check(d1 == q.digest() and d1 == r2.digest() and r2.tr_units == p.tr_units, "T1s-d determinism %s, round trip %s (%s)" % [str(d1 == q.digest()), str(d1 == r2.digest()), d1.left(8)])
	# T1s-p on the restored state, so the save carries the own levels
	var lines_p: Array = []
	for l: Variant in (p.tr_spec["income_tail"]["value"]["lines_yen_year"] as Array):
		lines_p.append(float(l) / 12.0 / 1e4)
	var above0 := [0, 0, 0]
	var above1 := [0, 0, 0]
	var bad_p := [0, 0, 0, 0]
	var n_w: int = 0
	var n_r: int = 0
	for i12: int in r2.n:
		var y0: float = p.income[i12]
		r2.repay(i12)
		if not _same(r2.income[i12], y0):
			bad_p[0] += 1
		for c12: int in 3:
			above0[c12] += 1 if y0 >= lines_p[c12] else 0
			above1[c12] += 1 if r2.income[i12] >= lines_p[c12] else 0
		var e12: int = r2.employment[i12]
		if e12 == r2.EMP_REGULAR or e12 == r2.EMP_NONREGULAR:
			n_w += 1
			r2.pay_factor[i12] = 1.0
			r2.repay(i12)
			if not _same(r2.income[i12], y0):
				bad_p[1] += 1
			# a worker of 65+ holds its pension beside its pay (§12.9 M1): the job's factor moves the pay only
			var pen12: float = r2.entitled(i12)
			r2.pay_factor[i12] = 1.1
			r2.repay(i12)
			if not _same(r2.income[i12], 1.1 * (y0 - pen12) + pen12):
				bad_p[2] += 1
			r2.pay_factor[i12] = 1.0
			r2.repay(i12)
	# the pensioner arm on the points and one individual set to a pensioner: no individual is one (the top 0.01%, amended after the first run)
	var pr12: Dictionary = r2.spec["pension_rule"]["value"]
	var p_age: PackedInt32Array = r2.tr_points["age"]
	var p_emp: PackedInt32Array = r2.tr_points["employment"]
	var p_inc: PackedFloat64Array = r2.tr_points["income"]
	var p_pen: PackedFloat64Array = r2.tr_points["pension_own"]
	var p_prot: PackedFloat64Array = r2.tr_points["protection"]
	for g12: int in p_emp.size():
		if p_emp[g12] == r2.EMP_RETIRED:
			n_r += 1
			var idx12: float = float(r2.pension["new"]) if p_age[g12] <= int(pr12["new_until_age"]) else float(r2.pension["old"])
			# 生活保護 is the household's, re-read by H5's monthly means test, not the person's own level (§12.9 M1c)
			# Why not pension x index against income - protection (before TO_E 15:31): the difference cancels where 生活保護 is nearly all
			# the income, and one point at 5e-4 万円 read 4e-12 off for float rounding alone
			if not _same(p_pen[g12] * idx12 + p_prot[g12], p_inc[g12]):
				bad_p[3] += 1
				if bad_p[3] <= 5:
					print("REPORT T1s-p pensioner point %d off: age %d, own pension %s x index %s = %s against income %s - protection %s = %s" % [g12, p_age[g12], str(p_pen[g12]), str(idx12), str(p_pen[g12] * idx12), str(p_inc[g12]), str(p_prot[g12]), str(p_inc[g12] - p_prot[g12])])
	var i0: int = 0
	r2.employment[i0] = r2.EMP_RETIRED
	r2.tier_income(i0, 20.0, -1.0)
	r2.pension["new"] = float(r2.pension["new"]) * 1.02
	r2.pension["old"] = float(r2.pension["old"]) * 1.02
	r2.repay(i0)
	var y_own: float = r2.income[i0]
	r2.tr_pension.erase(r2.pid[i0])
	r2.repay(i0)
	var y_tab: float = float(r2.spec["pension_man_yen"]["value"]) * (0.7 + 0.6 * r2.u("pension", i0)) * r2.pension_index(i0)
	var ind_ok: bool = _same(y_own, 20.0 * 1.02) and _same(r2.income[i0], y_tab) and not _same(y_tab, y_own)
	check(bad_p == [0, 0, 0, 0] and above0 == above1 and n_w > 0 and n_r > 0 and ind_ok, "T1s-p (§12.8 10.1) the own level persists over %d individuals: changed by repay() %d; of %d workers changed by a job pay factor reset to 1 %d, not x1.1 at 1.1 %d; individuals above the 10 / 1 / 0.1%% lines %s before, %s after the repay; of %d pensioner points the own pension x the index off the income %d; one individual set to a pensioner at 20 万円 reads %.4f with both R68 indices x1.02 (20.4), %.4f from the table once its own is erased (%.4f) %s" % [r2.n, bad_p[0], n_w, bad_p[1], bad_p[2], str(above0), str(above1), n_r, bad_p[3], y_own, r2.income[i0], y_tab, str(ind_ok)])
	# §12.12: T1s-cp0, T1s-w, T1s-c1
	var cpl: Dictionary = p.tr_couples
	var n_cpl: int = 0
	var wives := {}
	var c_tot := {}
	var c_co := {}
	for kq: String in cpl:
		var kp: PackedStringArray = kq.split("|")
		var nq: int = int(cpl[kq])
		n_cpl += nq
		var wk: String = "%s|%s" % [kp[0], kp[2]]
		wives[wk] = int(wives.get(wk, 0)) + nq
		var ck: String = "%s|%d|%d" % [kp[0], TR._coarse(int(kp[1])), TR._coarse(int(kp[2]))]
		c_tot[ck] = int(c_tot.get(ck, 0)) + nq
		if int(kp[3]) == 1:
			c_co[ck] = int(c_co.get(ck, 0)) + nq
	var n_nh := PackedInt64Array([0, 0])
	for kn: String in p.tr_nh_couples:
		var kpn: PackedStringArray = kn.split("|")
		n_nh[int(kpn[3])] += int(p.tr_nh_couples[kn])
		var wkn: String = "%s|%s" % [kpn[0], kpn[2]]
		wives[wkn] = int(wives.get(wkn, 0)) + int(p.tr_nh_couples[kn])
	var fh_n: int = 0
	var mp_n: int = 0
	var hd_n: int = 0
	var pt_n: int = 0
	var hk_off: int = 0
	for hk6: String in p.tr_hh:
		var t6: int = int(hk6.split("|")[1])
		if t6 != 1 and t6 != 2:
			continue
		var m6: Dictionary = p.tr_hh[hk6]["members"]
		var hd6: int = 0
		var pt6: int = 0
		for u6 in m6:
			var fem6: bool = p.tr_key[int(u6) * TR.KEY_STRIDE + 2] == 1
			var h6: int = int((m6[u6] as Dictionary).get(0, 0))
			var q6: int = int((m6[u6] as Dictionary).get(1, 0))
			fh_n += h6 if fem6 else 0
			mp_n += 0 if fem6 else q6
			hd6 += h6
			pt6 += q6
		hd_n += hd6
		pt_n += pt6
		hk_off += absi(hd6 - pt6)
	var xh: int = int(p.tr_margins.get("r77_cross_husband", 0))
	var xw: int = int(p.tr_margins.get("r77_cross_wife", 0))
	_t1s_nh(p, prefs, n_cpl, n_nh)
	_t1s_nho(p, n_nh[0] + n_nh[1])
	_t1s_gap(p)
	_t1s_gap2(p)
	_t1s_lc(p)
	_t1s_wm(p)
	_t1s_1p(p)
	_t1s_n4(p)
	_t1s_lp(p)
	_t1s_gapm(p)
	_t1s_b(p)
	_t1s_m21(p)
	_t1s_m22(p)
	_t1s_1pi(p)
	check(fh_n == 0 and mp_n == 0 and hk_off <= xh + xw and n_cpl + n_nh[0] + n_nh[1] == int(p.tr_margins["r77_couples"]) and int(p.tr_margins.get("r77_type1_rest", 0)) == 0, "T1s-cp0 (§12.12) %d couples from R77 (recorded %d); in the couple types female heads %d, male partners %d, heads %d and partners %d, |heads − partners| summed over the household-bundles %d (at most the cross-tier couples %d + %d); couple-only persons in no couple %d; non-couple seed excess floored %.0f" % [n_cpl, int(p.tr_margins["r77_couples"]), fh_n, mp_n, hd_n, pt_n, hk_off, xh, xw, int(p.tr_margins.get("r77_type1_rest", 0)), float(p.tr_margins.get("r77_floor_excess", 0.0))])
	var pop20: Dictionary = TR._v(p, "population_2020_by_pref_sex_band")["by_pref"]
	var cba: Dictionary = TR._v(p, "couples_by_age")["by_pref"]
	var cells_g: Array = []   # [band, got, comparator] per prefecture x band with at least 10,000 women
	var nat_m := PackedFloat64Array()
	nat_m.resize(15)
	var nat_e := PackedFloat64Array()
	nat_e.resize(15)
	var nat_w := PackedFloat64Array()
	nat_w.resize(15)
	for code7: String in prefs:
		var ci7: int = int(code7)
		var tab7: Array = cba[str(ci7)]
		for wb7: int in 15:
			var col7: float = 0.0
			for hb7: int in 15:
				col7 += float(tab7[hb7][wb7])
			var w20: float = float(pop20[str(ci7)][1][wb7])
			var w24: float = float(re["pbs"].get("%d|%d|1" % [ci7, wb7 + 3], 0))
			var expect: float = w24 * col7 / w20 if w20 > 0.0 else 0.0
			var got: float = float(wives.get("%d|%d" % [ci7, wb7], 0))
			nat_m[wb7] += got
			nat_e[wb7] += expect
			nat_w[wb7] += w24
			if w24 >= 10000.0 and expect > 0.0:
				cells_g.append([wb7, got, expect, ci7])
	var nat_bad: int = 0
	var nat_worst: float = 0.0
	var nat_txt: String = ""
	for wb8: int in range(1, 15):
		if nat_w[wb8] < 10000.0 or nat_e[wb8] <= 0.0:
			continue
		var g2: float = absf(nat_m[wb8] / nat_e[wb8] - 1.0)
		nat_worst = maxf(nat_worst, g2)
		nat_bad += 1 if g2 > 0.156 else 0
		nat_txt += " %d: %+.4f;" % [15 + 5 * wb8, nat_m[wb8] / nat_e[wb8] - 1.0]
	var nat_n: int = nat_txt.count(";")
	var nat_allow: int = _p95_allow(nat_n)
	print("REPORT T1s-w (i) (WITHDRAWN as superseded by R77c's rows, TO_E 17:02: its comparator is the 2020 share R77c replaced) national women in couples over the comparator by band 20+: bands beyond the P95 15.6%% %d of %d (at most %d, 5%% + 2 SE); worst %.4f (the backtest's maximum 20.0%%);%s" % [nat_bad, nat_n, nat_allow, nat_worst, nat_txt])
	var rel_bad: int = 0
	var rel_worst: float = 0.0
	var by_band := {}
	var worst_cells: Array = []
	for cg: Array in cells_g:
		var gn: float = nat_m[int(cg[0])] / nat_e[int(cg[0])]
		var gr: float = absf((float(cg[1]) / float(cg[2])) / gn - 1.0)
		rel_worst = maxf(rel_worst, gr)
		if gr > 0.066:
			rel_bad += 1
			by_band[15 + 5 * int(cg[0])] = int(by_band.get(15 + 5 * int(cg[0]), 0)) + 1
			worst_cells.append([gr, int(cg[3]), 15 + 5 * int(cg[0]), (float(cg[1]) / float(cg[2])) / gn])
	worst_cells.sort()
	worst_cells.reverse()
	print("REPORT T1s-w (ii) the cells beyond 6.6%% by band %s; the worst %s" % [str(by_band), str(worst_cells.slice(0, 8))])
	var rel_allow: int = _p95_allow(cells_g.size())
	print("REPORT T1s-w (ii) (WITHDRAWN as superseded by R77c's prefecture rows, TO_E 17:54: its comparator is the 2020 share R77c replaced) prefecture relative to national in the same band, %d cells with at least 10,000 women: beyond the P95 6.6%% %d (at most %d, 5%% + 2 SE); worst %.4f (the backtest's maximum 16.9%%)" % [cells_g.size(), rel_bad, rel_allow, rel_worst])
	var cob: Dictionary = TR._v(p, "couple_only_by_age")["by_pref"]
	var co_txt: String = ""
	var co_worst: float = 0.0
	for ck2: String in c_tot:
		var kc: PackedStringArray = ck2.split("|")
		var r77_co: float = float(cob[kc[0]][int(kc[1])][int(kc[2])])
		var r77_all: float = 0.0
		var tab8: Array = cba[kc[0]]
		for h8: int in 15:
			for w8: int in 15:
				if TR._coarse(h8) == int(kc[1]) and TR._coarse(w8) == int(kc[2]):
					r77_all += float(tab8[h8][w8])
		if r77_all > 0.0 and int(c_tot[ck2]) >= 1000:
			co_worst = maxf(co_worst, absf(float(c_co.get(ck2, 0)) / float(c_tot[ck2]) - minf(1.0, r77_co / r77_all)))
	var rk: Dictionary = p.tr_margins.get("r77_rake", {})
	if not rk.is_empty():
		var bt: String = ""
		var pb: PackedFloat64Array = rk["before"]
		var pa: PackedFloat64Array = rk["after"]
		var ptab: PackedFloat64Array = rk["table"]
		for s7: int in 2:
			for b7: int in range(1, 15):
				if ptab[s7 * 15 + b7] > 0.0:
					bt += " %d%s %.0f→%.0f (表V-1-3 %.0f);" % [15 + 5 * b7, "m" if s7 == 0 else "f", pb[s7 * 15 + b7], pa[s7 * 15 + b7], ptab[s7 * 15 + b7]]
		print("REPORT T1s-c1 (§12.12 (3) AMENDED, V111 (2)) the couple-only rake: worst relative error 第32表's coarse cells %s, 表V-1-3's shape under 60 men %s, women %s; couple-only persons by band x sex before → after the rake (in reals):%s" % [str(rk["err"][0]), str(rk["err"][1]), str(rk["err"][2]), bt])
	print("REPORT T1s-c1 (§12.12; a READ-BACK of the input, not evidence, V110 (4)) the couple-only share of the start's couples (integers) against R77 第32表 by (prefecture, coarse husband, coarse wife), cells of at least 1,000 couples: worst gap %.4f (the reals equal it by construction, _r77_couples)" % co_worst)
	_t1s_ma(p)
	# T1s-f
	var two := {"13": {"pop_thousand": 14178}, "47": {"pop_thousand": 1467}}
	var f0 = PEOPLE.new()
	f0.create("JPN", 7, st.cohort["JPN"], st.qx["JPN"], two, 30)
	for m: int in 6:
		f0.step(ENV)
	var f1 = PEOPLE.new()
	f1.households = true
	f1.create("JPN", 7, st.cohort["JPN"], st.qx["JPN"], two, 200)
	for m2: int in 12:
		f1.step(ENV)
	check(f0.digest() == P5_DIGEST and f1.digest() == HH_12 and not f0.to_dict().has("tiers"), "T1s-f tiers off: the test society %s (recorded %s), households-on 12 months %s (recorded %s), no tiers key %s" % [f0.digest().left(8), P5_DIGEST.left(8), f1.digest().left(8), HH_12.left(8), str(not f0.to_dict().has("tiers"))])
	finish()
