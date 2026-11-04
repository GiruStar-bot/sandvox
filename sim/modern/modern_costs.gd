extends RefCounted
## New-build costs for R55's cost logit (R56 Part 1, data/modern/r56.json), per entity:
##   LCOE (USD/MWh) = WEO's LCOE + capex x (learning x CRF(the entity's WACC, life) - CRF(WEO's WACC, life)) / (8.76 x capacity factor)
##   costs by region from WEO 2022 (US, EU, China, India); any other entity takes them by income group (T): high income the mean of the US
##     and EU rows, upper-middle China's, lower-middle and low India's. Income group by GDP per capita of the year before the base year
##     against the World Bank's FY2023 GNI thresholds (T: GDP per capita stands in for GNI per capita, which the data lacks)
##   WACC: WEO 2022 Table 4.2 for the states it names (EU members take Europe's), else R56's income-group mapping (T)
##   learning (Wright, S): capex x (X / X0)^-b, b = -log2(1 - learning rate), X / X0 = the world's fleet of that source now over the start's
const DM = preload("res://sim/api/det_math.gd")
const CANON = preload("res://sim/modern/canon.gd")
const R56_PATH := "res://data/modern/r56.json"

var r56: Dictionary = {}
var region: PackedStringArray = PackedStringArray()   # entity -> a WEO region, or "HIGH" (US/EU mean)
var wacc := PackedFloat64Array()
var income: PackedStringArray = PackedStringArray()


func create(data: RefCounted) -> void:
	r56 = CANON.load_json_m(R56_PATH)
	var E: int = data.entity_count()
	var th: Dictionary = r56["income_thresholds_gni_pc"]
	var named := {}
	for k: String in r56["wacc"]:
		var row: Dictionary = r56["wacc"][k]
		if row["iso3"] != null:
			named[String(row["iso3"])] = float(row["value"])
	var europe: float = float(r56["wacc"]["Europe"]["value"])
	var prev: Dictionary = data.history.get(data.base_year - 1, {})
	region.resize(E)
	wacc.resize(E)
	income.resize(E)
	for e: int in E:
		var k2: String = data.keys[e]
		var h: Dictionary = prev.get(k2, {})
		var gdp: float = float(h["gdp"]) if h.get("gdp") != null else data.gdp[e]
		var pop: float = float(h["population"]) if h.get("population") != null else data.population[e]
		var pc: float = gdp / pop if pop > 0.0 and gdp > 0.0 else 0.0
		var g: String = "low" if pc <= float(th["low_max"]) else ("lower_middle" if pc <= float(th["lower_middle_max"]) else ("upper_middle"
			if pc <= float(th["upper_middle_max"]) else "high"))
		# Why not "low" for an entity with no GDP figure (Taiwan, DPRK, ...): no figure is not a low income; such entities take the upper-middle
		# row (T), the middle of the four
		if pc == 0.0:
			g = "upper_middle"
		income[e] = g
		var macro: String = String(data.MACROS[data.macro[e]])
		if k2 == "USA":
			region[e] = "US"
		elif macro == "EU":
			region[e] = "EU"
		elif k2 == "CHN":
			region[e] = "China"
		elif k2 == "IND":
			region[e] = "India"
		else:
			region[e] = {"high": "HIGH", "upper_middle": "China", "lower_middle": "India", "low": "India"}[g]
		if named.has(k2):
			wacc[e] = named[k2]
		elif macro == "EU":
			wacc[e] = europe
		else:
			wacc[e] = float(r56["wacc_by_income"][g])


func _cost(reg: String, src: String, field: String) -> float:
	if reg == "HIGH":
		return 0.5 * (float(r56["costs"]["US"][src][field]) + float(r56["costs"]["EU"][src][field]))
	return float(r56["costs"][reg][src][field])


static func crf(w: float, years: float) -> float:
	return w / (1.0 - DM.pow(1.0 + w, -years))


## The learning multiplier on capex for a source whose world fleet is ratio x the start's
func learning(src: String, ratio: float) -> float:
	if not (r56["learning"] as Dictionary).has(src) or ratio <= 0.0:
		return 1.0
	var b: float = -DM.log(1.0 - float(r56["learning"][src]["rate"])) / DM.log(2.0)
	return DM.pow(ratio, -b)


# Why not rebuild the LCOE from WEO's parts: for PV and wind the parts give back WEO's figure, for thermal they do not (US CCGT 53 against
# 60, coal 79 against 95: WEO's thermal LCOE holds costs its parts do not show); so WEO's LCOE is kept and only the capital part moves
func lcoe(e: int, src: String, learn: float = 1.0) -> float:
	var reg: String = region[e]
	var capex: float = _cost(reg, src, "capex_usd_kw")
	var life: float = float(r56["life_yr"][src][0])
	var cap_now: float = capex * learn * crf(wacc[e], life)
	var cap_weo: float = capex * crf(float(r56["weo_wacc"][src]), life)
	return _cost(reg, src, "lcoe_pub") + (cap_now - cap_weo) / (8.76 * _cost(reg, src, "cf"))
