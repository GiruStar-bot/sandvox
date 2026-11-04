extends "res://tools/test/test_kit.gd"
## The modern mode's data (MODERN_PLAN 1.3; sim/modern/modern_data.gd).
##   godot --headless --path . --script res://sim/modern/test_modern_data.gd
## D1 every data file matches its manifest sha256 and loads, for the base year 2024 and the hindcast year 2022
## D2 the entity table (R54): 215 field entities (R54's 220 less the 5 de-facto ones that start inside their host), 193 UN members, 13
##    dependent territories, sorted keys, every one with a macro region
## D3 the regions: every region's shares sum to 1 (within 1e-6) over entities that exist; every entity sits in some region
## D4 the compute chain: each good's shares sum to 1 over the entities (within 1e-9); Taiwan holds the <10 nm logic share with South Korea
##    (69 / 31); ROW's neon sits in Ukraine alone; SIA/BCG's ATP row (3/3/6/9/28/30/20, 99%) is scaled to 1, so Taiwan's ATP is 28/99
## D5 the start's state is the year before the base year (R56 section 0): a figure missing in that year is held from its latest earlier year and
##    recorded (Syria's GDP for a 2024 start, from 2022); a figure missing in every year is 0 and listed (Vatican's GDP); electricity in
##    average MW is TWh x 1e6 / 8760, carried half a year to the start by the demand's growth (Japan's 2023 demand for a 2024 start at its
##    2018 -> 2023 compound rate, and its generation by the same factor)
## D6 a 2022 start reads the July 2022 Ember vintage (Japan's 2021 demand 958.53 TWh there, 1,034.67 TWh in the latest release)
## D7 demand growth for a 2022 start, mainland China: rule v2 (default) the compound rate 2016 -> 2021, rule v1 ("last") 2020 -> 2021
## D8 the canonical snap is stable: every float written with 15 or more significant digits in a data/modern JSON file (those a parser can
##    read one ulp off, V084) keeps its canonical value at its two neighbouring doubles, under the loader that reads the file (canon_m for
##    the M-stage files at the top and in views/, canon otherwise)
const MD = preload("res://sim/modern/modern_data.gd")
const CANON = preload("res://sim/modern/canon.gd")


func _init() -> void:
	var d = MD.new()
	check(d.load_year(2024) == "", "D1 the 2024 data loads (%s)" % d.error)
	var d22 = MD.new()
	check(d22.load_year(2022) == "", "D1 the 2022 data loads (%s)" % d22.error)
	var E: int = d.entity_count()
	var un: int = 0
	var dep: int = 0
	var sorted_ok: bool = true
	var macro_ok: bool = true
	for i: int in E:
		un += 1 if d.kind[i] == "un_member" else 0
		dep += 1 if d.kind[i] == "dependency" else 0
		sorted_ok = sorted_ok and (i == 0 or d.keys[i - 1] < d.keys[i])
		macro_ok = macro_ok and d.macro[i] >= 0
	check(E == 215 and un == 193 and dep == 13 and sorted_ok and macro_ok, "D2 %d entities, %d UN members, %d dependent territories, sorted, all with a macro region"
		% [E, un, dep])
	var sums_ok: bool = true
	var seen := {}
	for sh: Array in d.regions:
		var t: float = 0.0
		for pair: Array in sh:
			t += float(pair[1])
			seen[int(pair[0])] = true
		sums_ok = sums_ok and absf(t - 1.0) < 1e-6
	check(sums_ok and seen.size() == E, "D3 region shares sum to 1; %d of %d entities sit in a region" % [seen.size(), E])
	var goods_ok: bool = true
	for g: String in MD.GOODS:
		var tg: float = 0.0
		for i2: int in E:
			tg += d.share_of(i2, g)
		goods_ok = goods_ok and absf(tg - 1.0) < 1e-9
		if absf(tg - 1.0) >= 1e-9:
			print("good %s sums to %.12f" % [g, tg])
	check(goods_ok, "D4 every good's shares sum to 1 over the entities")
	var tw: int = d.index_of("TWN")
	var kr: int = d.index_of("KOR")
	var ua: int = d.index_of("UKR")
	var row_neon: float = 0.0
	for i3: int in E:
		if MD.MACROS[d.macro[i3]] == "ROW" and i3 != ua:
			row_neon += d.share_of(i3, "neon")
	check(absf(d.share_of(tw, "logic_lt10nm") - 0.69) < 1e-12 and absf(d.share_of(kr, "logic_lt10nm") - 0.31) < 1e-12 and absf(d.share_of(ua, "neon") - 0.495) < 1e-12
		and row_neon == 0.0 and absf(d.share_of(tw, "atp") - 0.28 / 0.99) < 1e-12, "D4 <10 nm logic Taiwan %.2f, South Korea %.2f; neon Ukraine %.3f, the rest of ROW %.3f; Taiwan ATP %.4f" % [d.share_of(tw, "logic_lt10nm"),
		d.share_of(kr, "logic_lt10nm"), d.share_of(ua, "neon"), row_neon, d.share_of(tw, "atp")])
	var jp: int = d.index_of("JPN")
	check(d.data_year == 2023 and int(d.held.get("SYR/gdp", 0)) == 2022 and not d.held.has("JPN/gdp")
		and (d.no_data.get("gdp", PackedStringArray()) as PackedStringArray).has("VAT"),
		"D5 a 2024 start from %d's figures: Syria's GDP held from %s; Vatican's GDP listed with no data" % [d.data_year, str(d.held.get("SYR/gdp"))])
	var g_jp: float = pow(1013.26 / float(d.history[2018]["JPN"]["demand"]), 1.0 / 5.0) - 1.0
	var c_jp: float = sqrt(1.0 + g_jp)
	var gen_jp: float = 0.0
	for s: int in MD.SOURCES.size():
		gen_jp += d.supply_mw[jp * MD.SOURCES.size() + s]
	check(absf(d.demand_mw[jp] - 1013.26 * 1e6 / 8760.0 * c_jp) < 1e-6 and absf(gen_jp / (float(d.history[2023]["JPN"]["generation"]) * 1e6 / 8760.0) - c_jp) < 1e-12,
		"D5 Japan's 2024 start demand %.1f MW = 1,013.26 TWh / 8,760 h x %.5f (half a year at %+.2f%%), generation by the same" % [d.demand_mw[jp], c_jp, g_jp * 100.0])
	var jp22: int = d22.index_of("JPN")
	var c22: float = pow(958.53 / float(d22.history[2016]["JPN"]["demand"]), 0.1)
	check(d22.stats_file.ends_with("stats_v2022.json") and absf(d22.demand_mw[jp22] - 958.53 * 1e6 / 8760.0 * c22) < 1e-6,
		"D6 the 2022 start reads %s: Japan's demand %.1f MW = 958.53 TWh / 8,760 h x %.5f" % [d22.stats_file.get_file(), d22.demand_mw[jp22], c22])
	var cn: int = d22.index_of("CHN")
	var v1 = MD.new()
	v1.load_year(2022, "last")
	var h21: float = float(d22.history[2021]["CHN"]["demand"])
	var want2: float = pow(h21 / float(d22.history[2016]["CHN"]["demand"]), 0.2) - 1.0
	var want1: float = h21 / float(d22.history[2020]["CHN"]["demand"]) - 1.0
	check(d22.demand_rule == "cagr5" and absf(d22.demand_growth[cn] - want2) < 1e-12 and absf(v1.demand_growth[cn] - want1) < 1e-12,
		"D7 China's demand growth for a 2022 start: v2 %+.2f%% a year (2016 -> 2021), v1 %+.2f%% (2020 -> 2021)" % [d22.demand_growth[cn] * 100.0,
		v1.demand_growth[cn] * 100.0])
	var long_n: int = 0
	var unstable: PackedStringArray = PackedStringArray()
	var files: int = _canon_stability("res://data/modern", "", unstable)
	long_n = int(unstable[0])
	unstable.remove_at(0)
	check(files > 20 and long_n > 1000 and unstable.is_empty(), "D8 %d files, %d floats with 15+ significant digits; unstable under one ulp: %d %s" % [files, long_n, unstable.size(), ", ".join(unstable.slice(0, 5))])
	metric("entities", E)
	print("no_data: ", d.no_data)
	finish()


static func _neighbour(x: float, step: int) -> float:
	var b: PackedByteArray = PackedFloat64Array([x]).to_byte_array()
	b.encode_s64(0, b.decode_s64(0) + step)
	return b.decode_double(0)


## Walks the folder; counts files; out[0] carries the number of long floats seen, the rest names the unstable ones
func _canon_stability(dir: String, rel: String, out: PackedStringArray) -> int:
	if out.is_empty():
		out.append("0")
	var files: int = 0
	var da := DirAccess.open(dir)
	for f: String in da.get_files():
		if not f.ends_with(".json"):
			continue
		files += 1
		var m_stage: bool = rel == "" or rel.begins_with("views")
		var text: String = FileAccess.get_file_as_string(dir.path_join(f))
		var re := RegEx.new()
		re.compile("-?[0-9]+\\.[0-9]+(?:[eE][-+]?[0-9]+)?")
		for hit: RegExMatch in re.search_all(text):
			var tok: String = hit.get_string()
			var digits: String = tok.split("e")[0].split("E")[0].replace("-", "").replace(".", "").lstrip("0")
			if digits.length() < 15:
				continue
			var x: float = tok.to_float()
			if x == floor(x):
				continue
			out[0] = str(int(out[0]) + 1)
			var c0: float = CANON.canon_m(x) if m_stage else CANON.canon_f(x)
			for step: int in [-1, 1]:
				var y: float = _neighbour(x, step)
				var c1: float = CANON.canon_m(y) if m_stage else CANON.canon_f(y)
				if c1 != c0:
					out.append("%s %s" % [rel.path_join(f), tok])
					break
	for sub: String in da.get_directories():
		files += _canon_stability(dir.path_join(sub), rel.path_join(sub) if rel != "" else sub, out)
	return files
