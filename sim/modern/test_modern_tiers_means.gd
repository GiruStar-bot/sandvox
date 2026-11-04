extends "res://tools/test/test_kit.gd"
## ISS tiered population T1b item 9 on the cash concept (ISS_TIERED_POPULATION.md §12.8 10.2; ISS_CHECKS T1s-cm, T1s-hi): the checks the
## tail fit does not use. The fit's inputs are the MOF lines at 10 / 1 / 0.1 % and the shares at 1 / 0.1 % (before matching). Built by the `tiers` flag at K = 4, seed 1, all 47 prefectures, month 0.
##   godot --headless --path . --script res://sim/modern/test_modern_tiers_means.gd
## T1s-cm the fitted tail's top 0.01 % line and mean against the tax table's (168.8 M, 508.8 M; a check, not an input: §12.8 10.2,
##        option A), within 5 % (T); DINA's nested class means and lines printed as not comparable (national income, not cash)
## T1s-hi the households' cash income (12 x Σ members' monthly incomes; eight keyed sample households per household-bundle, members
##        independent, T) against 国民生活基礎調査 2022's 2021 incomes brought to 2022 (§12.9): the median and the mean (S) and the nine
##        decile points from the 21 classes (D), each within 10 % (T); the shares at 1,000 万円 and 2,000 万円 and over reported
## T1s-pe the 65+'s pensions by entitlement (§12.9 M1; with the start's other outcome checks, not among the identities): kinds and
##        amounts agree, the none and basic-only shares by sex x band within 2 SE, the kind means within 2%
const PEOPLE = preload("res://sim/modern/people/people.gd")
const TR = preload("res://sim/modern/people/tiers.gd")
const MS = preload("res://sim/modern/modern_status.gd")
const CANON = preload("res://sim/modern/canon.gd")
const TOL_SHARE := 0.05
const TOL_HH := 0.10
const SAMPLES := 8
const NAMES := ["top 0.01%", "top 0.1% less 0.01%", "top 1% less 0.1%", "top 10% less 1%", "middle 40%", "bottom 50%"]
## 国民生活基礎調査 2022 (2021 incomes), R67a: % of households by class of 100 万円 (the last open at 2,000+), the median and mean (万円)
const HH_CLASSES := [6.7, 13.0, 14.6, 12.7, 10.3, 8.4, 7.3, 6.2, 4.9, 3.6, 3.1, 2.1, 1.7, 1.1, 1.0, 0.7, 0.5, 0.4, 0.3, 0.3, 1.4]
const HH_MEDIAN := 423.0
const HH_MEAN := 545.7


func _init() -> void:
	var st = MS.new()
	st.load(2024, ["JPN"])
	var prefs: Dictionary = CANON.load_json("res://data/modern/polity/jpn_prefectures.json")["prefectures"]
	var p = PEOPLE.new()
	p.tiers = true
	p.create("JPN", 1, st.cohort["JPN"], st.qx["JPN"], prefs, 0, 2024)
	check(p.error == "", "tiers built: '%s'" % p.error)
	_top_shares(p)
	_households(p)
	_pensions(p)
	finish()


## T1s-pe (§12.9 M1): the 65+'s pensions by entitlement, points by mass and individuals: the kind and the amount agree (an amount > 0
## exactly where the kind is not none), every 65+ has a kind; the none and basic-only shares by sex x band against R70's within 2 SE
## (n_eff of the masses); each kind's mean by sex against its tables' (25-year+ and short-record mixed by the short-record share)
## within 2%
func _pensions(p) -> void:
	var pe: Dictionary = p.tr_spec["pension_entitlement"]["value"]
	var ages: PackedInt32Array = p.tr_points["age"]
	var sexes: PackedInt32Array = p.tr_points["sex"]
	var pen: PackedFloat64Array = p.tr_points["pension_own"]
	var kind: PackedInt32Array = p.tr_points["pension_kind"]
	var surv: PackedFloat64Array = p.tr_points["survivor"]
	var m := {}
	var bad_k: int = 0
	var n65: int = 0
	var rows: Array = []
	for g: int in ages.size():
		if ages[g] >= p.PENSION_AGE:
			rows.append([sexes[g], ages[g], kind[g], (pen[g] - surv[g]) * p.pension_index_at(ages[g]), float(p.tr_pt_mass[g])])
	for i: int in p.n:
		if p.age[i] >= p.PENSION_AGE:
			rows.append([p.sex[i], p.age[i], int(p.tr_pension_kind.get(p.pid[i], -1)), p.entitled(i) if p.employment[i] != p.EMP_RETIRED else p.income[i], 1.0])
	for r: Array in rows:
		n65 += 1
		var kd: int = int(r[2])
		if kd < 0 or (kd == TR.PEN_NONE) != (float(r[3]) <= 0.0):
			bad_k += 1
		var key: String = "%d|%d" % [int(r[0]), clampi((int(r[1]) - p.PENSION_AGE) / 5, 0, 3)]
		if not m.has(key):
			m[key] = PackedFloat64Array([0, 0, 0, 0])
		var w: float = float(r[4])
		m[key][0] += w
		m[key][1] += w * w
		m[key][2] += w if kd == TR.PEN_NONE else 0.0
		m[key][3] += w if kd == TR.PEN_BASIC or kd == TR.PEN_BASIC_SHORT else 0.0
	var bad_s: int = 0
	var txt: String = ""
	var keys: Array = m.keys()
	keys.sort()
	for key2: String in keys:
		var sx: int = int(key2.split("|")[0])
		var bi: int = int(key2.split("|")[1])
		var sn: String = "male" if sx == p.MALE else "female"
		var v: PackedFloat64Array = m[key2]
		var n_eff: float = v[0] * v[0] / maxf(1.0, v[1])
		var want_n: float = float(pe["none_share"][sn][bi])
		var want_b: float = (1.0 - want_n) * float(pe["basic_only_share"][sn][bi])
		var got_n: float = v[2] / v[0]
		var got_b: float = v[3] / v[0]
		var se_n: float = sqrt(want_n * (1.0 - want_n) / n_eff)
		var se_b: float = sqrt(want_b * (1.0 - want_b) / n_eff)
		if absf(got_n - want_n) > 2.0 * se_n or absf(got_b - want_b) > 2.0 * se_b:
			bad_s += 1
		var band: String = "%d-%d" % [p.PENSION_AGE + 5 * bi, p.PENSION_AGE + 5 * bi + 4] if bi < 3 else "%d+" % (p.PENSION_AGE + 5 * bi)
		txt += " %s %s: none %.4f (%.4f), basic %.4f (%.4f), n_eff %.0f;" % [sn, band, got_n, want_n, got_b, want_b, n_eff]
	var bad_m: int = 0
	var txt_m: String = ""
	for sx2: int in [p.MALE, 1 - p.MALE]:
		var sn2: String = "male" if sx2 == p.MALE else "female"
		for grp: Array in [["basic", [TR.PEN_BASIC, TR.PEN_BASIC_SHORT], "basic_only"], ["employee", [TR.PEN_EMPLOYEE, TR.PEN_EMPLOYEE_SHORT], "employee"]]:
			var sh: float = float(pe["short_record_share"][sn2][String(grp[2])])
			var t25: String = "basic_only_classes" if String(grp[2]) == "basic_only" else "employee_classes"
			var tsh: String = "basic_only_short_classes" if String(grp[2]) == "basic_only" else "employee_short_classes"
			var want: float = ((1.0 - sh) * float(pe[t25][sn2]["mean_yen"]) + sh * float(pe[tsh][sn2]["mean_yen"])) / 1e4
			var sw: float = 0.0
			var sy: float = 0.0
			for r2: Array in rows:
				if int(r2[0]) == sx2 and (grp[1] as Array).has(int(r2[2])):
					sw += float(r2[4])
					sy += float(r2[4]) * float(r2[3])
			var got: float = sy / maxf(1.0, sw)
			if absf(got / want - 1.0) > 0.02:
				bad_m += 1
			txt_m += " %s %s %.3f (%.3f, %+.1f%%);" % [sn2, String(grp[0]), got, want, 100.0 * (got / want - 1.0)]
	var sv: Dictionary = p.tr_margins["survivors"]
	var pr: Dictionary = p.tr_margins["protection"]
	check(bad_k == 0 and bad_s == 0 and bad_m == 0 and n65 > 0, "T1s-pe (§12.9 M1) the 65+'s pensions by entitlement over %d points and individuals: kind and amount at odds %d; sex x band shares beyond 2 SE %d:%s kind means (万円 a month, own amounts before a survivor's, against the tables') beyond 2%% %d:%s; survivors (M1b) drawn %s against %s by band, %.0f skipped at the median line; 生活保護 (M1c) %.0f one-person 65+ taken against %.0f (%d points below the minimum)" % [n65, bad_k, bad_s, txt, bad_m, txt_m, str(sv["drawn"]), str(sv["want"]), float(sv["skipped"]), float(pr["taken"]), float(pr["want"]), int(pr["below"])])


func _top_shares(p) -> void:
	var tl: Dictionary = p.tr_spec["income_tail"]["value"]
	var pub: Array = p.tr_spec["classes"]["value"]["mean_income_yen_year"]
	var inc: PackedFloat64Array = p.tr_points["income"]
	var s := PackedFloat64Array([0, 0, 0, 0, 0, 0])
	var m := PackedFloat64Array([0, 0, 0, 0, 0, 0])
	for g: int in p.tr_pt_code.size():
		var k: int = p.tr_pt_code[g] / (TR.NTYPE * TR.NEMP)
		if k < TR.CLASS_NONE:
			s[k] += inc[g] * float(p.tr_pt_mass[g])
			m[k] += float(p.tr_pt_mass[g])
	for i: int in p.n:
		var k2: int = p.tr_indiv_code[i] / (TR.NTYPE * TR.NEMP)
		s[k2] += p.income[i]
		m[k2] += 1.0
	# the tax table's top 0.01% is a check of the fitted tail, not an input (§12.8 10.2, option A)
	var tax: Dictionary = tl["tax_top_0_01"]
	var line_m: float = exp(p.tr_margins["tail_lines"][4]) * 12.0 * 1e4
	var mean_m: float = s[0] / m[0] * 12.0 * 1e4
	var rl: float = line_m / float(tax["line_yen_year"]) - 1.0
	var rm: float = mean_m / float(tax["mean_yen_year"]) - 1.0
	check(absf(rl) <= TOL_SHARE and absf(rm) <= TOL_SHARE, "T1s-cm the fitted top 0.01%%: line %.1f M against the tax table's %.1f M (%+.1f%%), mean %.1f M against %.1f M (%+.1f%%) (tolerance %.0f%%; suspected cause of a gap: 合計所得 includes separately taxed capital gains, R67a)" % [line_m / 1e6, float(tax["line_yen_year"]) / 1e6, 100.0 * rl, mean_m / 1e6, float(tax["mean_yen_year"]) / 1e6, 100.0 * rm, 100.0 * TOL_SHARE])
	var txt: String = ""
	for k3: int in 6:
		txt += " %s %.2f M (DINA %.2f M);" % [NAMES[k3], s[k3] / m[k3] * 12.0 / 100.0, float(pub[k3]) / 1e6]
	print("T1s-cm (not comparable, national income against cash) the class means:%s DINA's lines %s yen a year against the cash lines %s" % [txt, str(tl["dina_lines_yen_year"]), str(tl["lines_yen_year"])])


func _households(p) -> void:
	var inc: PackedFloat64Array = p.tr_points["income"]
	var hk: Array = p.tr_hh.keys()
	hk.sort()
	var pairs: Array = []
	var q: int = 0
	for key: String in hk:
		var hh: Dictionary = p.tr_hh[key]
		var cnt: int = int(hh["count"])
		if cnt <= 0:
			continue
		var heads: Array = []
		var others: Array = []
		var persons: int = 0
		var mem: Dictionary = hh["members"]
		var us: Array = mem.keys()
		us.sort()
		for u in us:
			for r in [0, 1, 2, 3, 4]:
				var n: int = int(mem[u].get(r, 0))
				if n <= 0:
					continue
				persons += n
				if r == 0:
					heads.append([int(u), n])
				else:
					others.append([int(u), n])
		if heads.is_empty():
			continue
		var size: int = maxi(1, int(round(float(persons) / float(cnt))))
		for smp: int in SAMPLES:
			var y: float = _draw(p, heads, inc, q, 0)
			for slot: int in range(1, size):
				if not others.is_empty():
					y += _draw(p, others, inc, q, slot)
			pairs.append([y * 12.0, float(cnt) / float(SAMPLES)])
			q += 1
	pairs.sort_custom(func(a: Array, b: Array) -> bool: return float(a[0]) < float(b[0]))
	var tot: float = 0.0
	var sum: float = 0.0
	var at1000: float = 0.0
	var at2000: float = 0.0
	for e: Array in pairs:
		tot += float(e[1])
		sum += float(e[0]) * float(e[1])
		if float(e[0]) >= 1000.0:
			at1000 += float(e[1])
		if float(e[0]) >= 2000.0:
			at2000 += float(e[1])
	# the survey's 2021 incomes brought to the inputs' 2022 (§12.9, the PM's ruling; 毎月勤労統計 100.3 -> 102.3)
	var ix: float = float(p.tr_spec["hh_income_index_2021_2022"]["value"])
	var want_q: Array = _class_deciles(ix)
	var got_q: Array = []
	var acc: float = 0.0
	var next: int = 1
	for e2: Array in pairs:
		acc += float(e2[1])
		while next <= 9 and acc >= tot * float(next) / 10.0:
			got_q.append(float(e2[0]))
			next += 1
	var median: float = got_q[4]
	var mean: float = sum / tot
	var bad: int = 0
	var txt: String = ""
	for d: int in 9:
		var rel: float = float(got_q[d]) / float(want_q[d]) - 1.0
		if absf(rel) > TOL_HH:
			bad += 1
		txt += " D%d %.0f (%.0f, %+.0f%%)" % [d + 1, got_q[d], want_q[d], 100.0 * rel]
	var rel_m: float = median / (HH_MEDIAN * ix) - 1.0
	var rel_a: float = mean / (HH_MEAN * ix) - 1.0
	check(bad == 0 and absf(rel_m) <= TOL_HH and absf(rel_a) <= TOL_HH, "T1s-hi the households' cash income (万円 a year, %d sample households for %.0f households) against 国民生活基礎調査 2022's 2021 incomes x%.4f (2022): median %.0f against %.0f (%+.1f%%), mean %.1f against %.1f (%+.1f%%), deciles%s; %d of 9 deciles beyond %.0f%%; shares at 1,000 万円+ %.3f (12.6%% in 2021), 2,000 万円+ %.3f (1.4%%); the couples' incomes independent at T1 (M005 (b); their link is T2's, F12), a known cause at D9" % [pairs.size(), tot, ix, median, HH_MEDIAN * ix, 100.0 * rel_m, mean, HH_MEAN * ix, 100.0 * rel_a, txt, bad, 100.0 * TOL_HH, at1000 / tot, at2000 / tot])


## One member's monthly income: a person-bundle of the list in proportion to its count, then one of its points by mass (keyed)
func _draw(p, lst: Array, inc: PackedFloat64Array, q: int, slot: int) -> float:
	var tot: int = 0
	for e: Array in lst:
		tot += int(e[1])
	var x: int = p.KEYED.below(tot, p.seed_v, "t1s_hi_unit", q, slot, 0)
	var u: int = int(lst[lst.size() - 1][0])
	var acc: int = 0
	for e2: Array in lst:
		acc += int(e2[1])
		if x < acc:
			u = int(e2[0])
			break
	var c: int = p.tr_count[u]
	var y: int = p.KEYED.below(maxi(1, c), p.seed_v, "t1s_hi_point", q, slot, 0)
	var acc2: int = 0
	for g: int in range(p.tr_pt_off[u], p.tr_pt_off[u + 1]):
		acc2 += p.tr_pt_mass[g]
		if y < acc2:
			return inc[g]
	return inc[p.tr_pt_off[u + 1] - 1]


## The nine decile points of the published class distribution, linear within each class of 100 万円 (the shares renormalised), x ix
func _class_deciles(ix: float) -> Array:
	var tot: float = 0.0
	for c: float in HH_CLASSES:
		tot += c
	var out: Array = []
	var acc: float = 0.0
	var next: int = 1
	for k: int in HH_CLASSES.size():
		var lo: float = 100.0 * k
		var share: float = float(HH_CLASSES[k]) / tot
		while next <= 9 and acc + share >= float(next) / 10.0:
			out.append(ix * (lo + 100.0 * (float(next) / 10.0 - acc) / share))
			next += 1
		acc += share
	return out
