extends RefCounted
## The public's evaluation (BLUEPRINT_v2 4, P8 first cut): citizen groups by prefecture (population weights, S) whose approval of the
## cabinet answers what they feel: the food price's yearly change, the unemployment rate's change, and policy events (a tax rise, a
## benefit). The form is declared (T) with the signs from the literature (retrospective evaluation: Lewis-Beck & Stegmaier 2000); the
## coefficients are to be replaced by a published Japanese estimate. Prefectures share one national approval until prefecture-level
## exposures are loaded (T); the election reads the approval change through election.gd's swing.
## approval_t = approval_{t-1} + a x (-food_price_yoy) + b x (-d_unemployment_pt) + policy effects; clamped to [0.05, 0.9]
const A_FOOD := 0.15     # T: a 10% rise of food prices over a year costs 1.5 points of approval
const B_UNEMP := 0.02    # T: one point of unemployment costs 2 points
const EFFECT := {"consumption_tax_rate": -0.05, "child_allowance": 0.01, "fuel_subsidy": 0.01, "rice_stock_release": 0.005, "defence_budget_share": -0.005}   # T, per application
const CARRY := 0.9       # T: the month's shock fades by a tenth a month

var prefectures: Dictionary = {}
var approval: float = 0.4
var shock: float = 0.0        # the accumulated evaluation shock, fading
var history: Array = []       # [month, approval, food_yoy, d_unemp, effects]


func load_state(key: String, start_approval: float) -> String:
	var p: String = "res://data/modern/polity/%s_prefectures.json" % key.to_lower()
	var d: Variant = JSON.parse_string(FileAccess.get_file_as_string(p))
	if d is Dictionary:
		prefectures = (d as Dictionary)["prefectures"]
	approval = start_approval
	return ""


## One month: the shock from what people feel, applied to the approval; levers applied this month add their effects
func step(month: int, food_price_yoy: float, d_unemployment_pt: float, levers_applied: Array) -> float:
	var eff: float = 0.0
	for lid: String in levers_applied:
		eff += float(EFFECT.get(lid, 0.0))
	var s: float = A_FOOD * (-food_price_yoy) + B_UNEMP * (-d_unemployment_pt) + eff
	shock = CARRY * shock + s
	approval = clampf(approval + s, 0.05, 0.9)
	history.append([month, approval, food_price_yoy, d_unemployment_pt, eff])
	return approval


## The approval change since a given month (for the election's retrospective swing)
func change_since(month: int) -> float:
	for row: Array in history:
		if int(row[0]) == month:
			return approval - float(row[1])
	return 0.0


func to_dict() -> Dictionary:
	return {"approval": approval, "shock": shock, "history": history.duplicate(true)}


func from_dict(d: Dictionary) -> void:
	approval = float(d.get("approval", approval))
	shock = float(d.get("shock", 0.0))
	history = (d.get("history", []) as Array).duplicate(true)
