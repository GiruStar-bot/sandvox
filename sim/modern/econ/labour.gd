extends RefCounted
## The labour market of the economy (ISS Phase 5, survey 2: the economy OWNS employment and wages; the persons supply labour and receive
## jobs and pay). Attached to the monthly economy when the representative persons run. Each month it reads what the persons supply
## (their search share, their consumption plans, their unions' wage demands) and what the modelled sectors do (capacity use), and writes
## the unemployment rate, the wage index and the scale of final demand; the persons and the status layer then read them.
## Rules (parameters with their labels in data/modern/econ/labour_jpn.json):
##   u_t = rho u_{t-1} + (1 - rho) (u* - okun_k x sum over the modelled sectors of employment share x (capacity use - its start)), clamped;
##   the persons' search raises their OWN finding rate
##   w_t = w_{t-1} x (1 + (w_pi pi_e + w_u (u* - u_t) + w_demand x wage-demand share) / 12)   (a Phillips-type rule with expected prices)
##   final demand scale of a commodity = the persons' weighted consumption plan of it / the start's (the economy keeps the published
##   level, the persons move it); the S2' price elasticity of such a commodity is applied by each person to the price it believes, and
##   the economy drops its own for it (counted once)
const CANON = preload("res://sim/modern/canon.gd")

var spec: Dictionary = {}
var u: float = NAN
var wage_index: float = 1.0
var use_start: float = NAN
var search_share: float = 0.0
var wage_demand_share: float = 0.0
var demand_scale: Dictionary = {}   # commodity -> scale on the held final demand
var log: Array = []                 # [month, u, wage_index, gap, search_share, wage_demand_share, scale_food]


func load_state(key: String) -> String:
	var d: Variant = CANON.load_json("res://data/modern/econ/labour_%s.json" % key.to_lower())
	if not (d is Dictionary):
		return "labour: no spec for " + key
	spec = d
	u = _p("u_star")
	return ""


func _p(name: String) -> float:
	return float(spec[name]["value"])


## What the persons and their groups supply this month (called by the world before the economy steps)
func receive(search: float, wage_demands: float, scales: Dictionary) -> void:
	search_share = search
	wage_demand_share = wage_demands
	demand_scale = scales.duplicate()


## The month's labour market, after the sectors have planned (capacity use of food manufacturing as the gap's reading, T)
func step(month: int, capacity_use: float, expected_inflation: float) -> void:
	if is_nan(use_start):
		use_start = capacity_use
	# Why weighted by the sector's employment share: the economy models one manufacturing sector of about 2% of the employed; read alone,
	# its use gap moved the national rate as if it were the whole economy (its input collapse sent u to the 15% clamp, Phase 5 run)
	var gap: float = float(spec["sector_employment_share"]["food_manufacturing"]["value"]) * (capacity_use - use_start)
	var rho: float = _p("rho")
	u = clampf(rho * u + (1.0 - rho) * (_p("u_star") - _p("okun_k") * gap), _p("u_min"), _p("u_max"))
	wage_index *= 1.0 + (_p("w_pi") * expected_inflation + _p("w_u") * (_p("u_star") - u) + _p("w_demand") * wage_demand_share) / 12.0
	log.append([month, u, wage_index, gap, search_share, wage_demand_share, float(demand_scale.get("food_products", 1.0))])


## The economy's decision on one person's job this month (survey 2: employment is the economy's; the person supplies its search):
## separation at s, a find at f x the search factor (a searcher 1.6, the rest 0.6, T), a job change at CHANGE_P when the person looked
## for one; each a keyed draw on the person's id, and the person's pay, union and event follow from it. The new job's own pay is kept
## as the person's pay factor, so the yearly pay at the person's turn keeps it (it was lost there: the code review, 1a). Why a function here and not in
## the person module: the writer of employment is the labour market, as the ownership table says; the persons only read the outcome
static func person_month(p: RefCounted, i: int, s: float, f: float, counts: Dictionary) -> void:
	var h: PackedFloat64Array = rates(p, i, s, f)
	var m: int = p.month
	if h[0] > 0.0 and p.below("sep", i, m, 0, h[0]):
		var e0: Array = effect_loss(p)
		apply(p, i, int(e0[0]), float(e0[1]), "job_loss", counts)
	elif h[1] > 0.0 and p.below("find", i, m, 0, h[1]):
		var e1: Array = effect_find(p, i)
		apply(p, i, int(e1[0]), float(e1[1]), "job_found", counts)
	elif h[2] > 0.0 and p.below("change", i, m, 0, h[2]):
		var before: float = p.income[i]
		var e2: Array = effect_change(p, i, m)
		apply(p, i, int(e2[0]), float(e2[1]), "changed_job", counts)
		p.count_kind(counts, "changed_job:income_change", i, p.income[i] - before, "the economy's wage table redrawn (T)")


## The labour rule's rates for one holder this month (§14.1, T2.R): [separation, finding, job change], each read in this order and
## each only if the earlier did not happen; pure, so a person draws one keyed u against each and a point a binomial of its mass
static func rates(p: RefCounted, i: int, s: float, f: float) -> PackedFloat64Array:
	var e: int = p.employment[i]
	var at_work: bool = e == p.EMP_REGULAR or e == p.EMP_NONREGULAR
	return p.rone_out("rates", PackedFloat64Array([s if at_work else 0.0, f * (p.ACT.SEARCH_BOOST if p.search[i] == 1 else p.ACT.NO_SEARCH) if e == p.EMP_UNEMPLOYED else 0.0,
		p.ACT.CHANGE_P if at_work and p.search[i] == 2 else 0.0]))


## The probability that a job change takes a non-regular worker to a regular job (T, as Phase 2); pure
static func h_to_regular(p: RefCounted, i: int) -> float:
	return p.rone_out("h_to_regular", 0.3 if p.employment[i] == p.EMP_NONREGULAR else 0.0)


## The effects as values (§14.1): [the new employment, the job's own pay factor]; pure (the draws keyed on the holder's id)
static func effect_loss(p: RefCounted) -> Array:
	return [p.EMP_UNEMPLOYED, 1.0]


static func effect_find(p: RefCounted, i: int) -> Array:
	return [p.labour_from_rates(i), 1.0]


static func effect_change(p: RefCounted, i: int, m: int) -> Array:
	var e: int = p.employment[i]
	var hr: float = h_to_regular(p, i)
	if hr > 0.0 and p.below("toregular", i, m, 0, hr):
		e = p.EMP_REGULAR
	return [e, p.DM.exp(0.15 * p.normal("newwage", i, m))]


## The effects applied by the owner (employment and the pay factor are the labour market's): the person's pay re-read, its union, the
## event's reading
static func apply(p: RefCounted, i: int, emp: int, pf: float, kind: String, counts: Dictionary) -> void:
	p.employment[i] = emp
	p.pay_factor[i] = pf
	p.repay(i)
	p.GRP.new_job(p, i)
	p.event(i, kind, counts)


## A student of 22 enters the labour market (the person's yearly turn): its status from the economy's rates, its pay, its union
static func enter_work(p: RefCounted, i: int, counts: Dictionary) -> void:
	p.employment[i] = p.labour_from_rates(i)
	p.repay(i)
	p.GRP.new_job(p, i)
	p.event(i, "entered_work", counts)


func to_dict() -> Dictionary:
	return {"u": u, "wage_index": wage_index, "use_start": use_start, "search_share": search_share, "wage_demand_share": wage_demand_share, "demand_scale": demand_scale.duplicate(), "log": log.duplicate(true)}


func from_dict(d: Dictionary) -> void:
	u = float(d["u"])
	wage_index = float(d["wage_index"])
	use_start = float(d["use_start"])
	search_share = float(d["search_share"])
	wage_demand_share = float(d["wage_demand_share"])
	demand_scale = (d["demand_scale"] as Dictionary).duplicate()
	log = (d["log"] as Array).duplicate(true)
