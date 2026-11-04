extends RefCounted
## The actor interface (MODERN_PLAN 3; R55 brings the published decision rules for states without a seat). Every entity decides on the last
## day of each month, in entity order, by returning actions; the world checks them and applies them all or none (modern_world.gd). Actions:
##   {"act": "build", "kind": a project kind (modern_field PROJECT_KINDS), "size": > 0, "link_to": entity (transmission only)}
##   {"act": "licence", "good": a licensed good (modern_chain GOODS_LICENSED), "to": entity, "open": bool}
##   {"act": "order", "first": "dc" or "fab"}: which load a power deficit cuts first
## Rule sets: "none" (no action) and "placeholder" (until R55: the THEORY rules of MODERN_PLAN 3, stated, never fitted):
##   power: the load a year ahead (base demand then; DC load of the wanted IT within the capacity built and started; fab load of the
##     capacity built and started) less the supply a year ahead and every generation project started; a shortfall is built in the entity's
##     current mix (with no generation of its own: gas)
##   data centres: the wanted IT one DC lead time ahead, over the start's load factor, less the capacity built and started
##   fabs: the world's chip need one fab lead time ahead (the wanted IT's retirements and growth then, in chip-years a year) less the world's
##     fab capacity built and started, built by every fab entity in proportion to its current capacity
##   licences: only to answer, in kind, a licence closed against the entity: it closes to that issuer the good it holds the largest share
##     of; an answer is not answered again (tit for tat without escalation)
const DM = preload("res://sim/api/det_math.gd")
const MD = preload("res://sim/modern/modern_data.gd")
const MC = preload("res://sim/modern/modern_chain.gd")
# Why "placeholder" is kept beside r55: test_modern_actors' M4 checks of the THEORY rules read it, and r55 shares its _dc; removing it
# removes those checks (put to the PM)
const RULE_SETS: Array[String] = ["none", "placeholder", "r55"]
# R55 Q4's set (labels as R55 gives them; nothing fitted to C1-C20)
const CHERP_CAP := {"wind": 0.008, "solar": 0.006}   # S: Cherp 2021, the most a year's addition may be, as a share of supply
const COAL_AGE_YR := 40.0                            # S: empirical 35-46 yr; the field retires the start's coal at 1 / this a year (T: even ages)
const COUNTER_DAYS := 29                             # D: a counter-control is in force 29-42 days after the round it answers
const FOLLOW_DAYS := 309                             # D: allies' controls take effect 289-329 days after the leader's (the middle)
const CONTAGION := 0.02                              # S (food form, T for our goods): +2 pt a year per 100 pt of others' restricted share
# Why not a duration from export-restriction data: R56 has none; the nearest dated one is the sanctions median of about a year (R55, T)
const RESTRICT_DAYS := 365
const JOGMEC_DAYS := 60.0                            # S: Japan holds 60 days of its use of minerals (gallium here)
const LOGIT_GAMMA := -3.0                            # MA: GCAM's example between fuels (R55)
const MC_LOGIT: Array[String] = ["coal", "gas", "wind", "solar"]
const MONTH_ENDS: Array[int] = [31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334, 365]
# Why not act on a shortfall of any size: float noise in a balanced entity is ~1e-10 of its demand and would start empty projects
const NOISE := 1e-9

var rule_set: String = "placeholder"
var seen_closed: Dictionary = {}   # licence key -> true once its destination has looked at it
var answers: Dictionary = {}       # licence key -> true for licences closed as an answer
var costs: RefCounted = null      # modern_costs.gd with R56's costs (the r55 rule set); null: builds stay in the current mix
var fab: Dictionary = {}           # R57's fab growth inputs for the run's base year (r57.json); empty: no fab rule
var _learn: Dictionary = {}        # this month: source -> learning multiplier on capex
var plan: Dictionary = {}          # r55 energy: entity -> {source: MW to start at each month end of this year}
var queued: Array = []             # r55: [due day, entity, good, destination, "answer" | "follow"], in force on the first month end on or after the due day
var follows: Dictionary = {}       # licence key -> true for licences closed by following an ally
var seen_follow: Dictionary = {}   # "entity|licence key" -> true once that entity has weighed following it
var allies: Array = []             # entity -> {ally entity: true}, as of the run's start (R56 alliances; T: defence treaties and unions)
var in_regime := PackedByteArray() # entity -> 1 if in an export-control regime (Wassenaar) as of the start
var restrict_p: Dictionary = {}    # entity -> base chance a year of a new export restriction per good (R56; G20 states only)
var general: Dictionary = {}       # "entity|good" -> the day its general export restriction lifts
var _pend: Dictionary = {}         # this month: "entity|kind" -> size of unfinished projects (an entity's own actions only change its own)
var _fab_gap: float = 0.0
var _fab_now: float = 0.0


static func is_month_end(day: int) -> bool:
	return day > 0 and MONTH_ENDS.has(((day - 1) % 365) + 1)


## Reads, once a month before any entity decides, what the rules need from the world: unfinished projects and the world's fab gap
func begin_month(f: RefCounted) -> void:
	_learn = {}
	if costs != null:
		for src: String in ["solar", "wind"]:
			var s: int = MD.SOURCES.find(src)
			var now: float = 0.0
			var start: float = 0.0
			for e0: int in f.E:
				now += f.supply_of(e0, s)
				start += f.supply0[e0 * MD.SOURCES.size() + s]
			_learn[src] = costs.learning(src, now / start if start > 0.0 else 1.0)
	_pend = {}
	for p: Array in f.projects:
		var k: String = "%d|%s" % [int(p[0]), String(p[1])]
		_pend[k] = float(_pend.get(k, 0.0)) + float(p[2])
	var lead: int = int(f.data.lead_days["fab"]["days"])
	var cap: float = 0.0
	_fab_now = 0.0
	var life_yr: float = float(f.SERVER_LIFE_DAYS) / 365.0
	var need: float = 0.0
	for e: int in f.E:
		need += f.wanted_it(e, f.day + lead) * (1.0 / life_yr + DM.log(1.0 + f.cgrow[e])) / f.k_it
		cap += f.fab_cap[e] + _pending(e, "fab")
		_fab_now += f.fab_cap[e]
	_fab_gap = need - cap if need - cap > NOISE * need else 0.0


func _pending(e: int, kind: String) -> float:
	return float(_pend.get("%d|%s" % [e, kind], 0.0))


## The committed pipeline's mix (shares of the entity's new plants, entity x SOURCES): the start's coal, gas, wind and solar part shared by
## the same logit at the start's costs (T: the plants committed before the start were chosen by the rule the actors use), with wind and
## solar held to CHERP_CAP of the start's generation a year at the start's load growth; the other sources keep their start shares
func pipeline_mix(f: RefCounted) -> PackedFloat64Array:
	var S: int = MD.SOURCES.size()
	var out: PackedFloat64Array = f.mix.duplicate()
	for e: int in f.E:
		var part: float = 0.0
		for src: String in MC_LOGIT:
			part += f.mix[e * S + MD.SOURCES.find(src)]
		if part <= 0.0 and f.gen0[e] > 0.0:
			continue
		var wt := {}
		var tot: float = 0.0
		for src2: String in MC_LOGIT:
			if src2 == "wind" or src2 == "solar" or f.mix[e * S + MD.SOURCES.find(src2)] > 0.0:
				wt[src2] = DM.pow(costs.lcoe(e, src2), LOGIT_GAMMA)
				tot += float(wt[src2])
		var grow_yr: float = f.base0[e] * f.demand_growth[e]
		var spare: float = 0.0
		for src3: String in MC_LOGIT:
			var sh: float = part * float(wt.get(src3, 0.0)) / tot
			if CHERP_CAP.has(src3) and grow_yr > 0.0 and sh * grow_yr > float(CHERP_CAP[src3]) * f.gen0[e]:
				spare += sh - float(CHERP_CAP[src3]) * f.gen0[e] / grow_yr
				sh = float(CHERP_CAP[src3]) * f.gen0[e] / grow_yr
			out[e * S + MD.SOURCES.find(src3)] = sh
		if spare > 0.0:
			var rest: float = 0.0
			for src4: String in ["coal", "gas"]:
				rest += float(wt.get(src4, 0.0))
			if rest <= 0.0:
				out[e * S + MD.SOURCES.find("gas")] += spare
			else:
				for src5: String in ["coal", "gas"]:
					out[e * S + MD.SOURCES.find(src5)] += spare * float(wt.get(src5, 0.0)) / rest
	return out


## The month's actions of an entity without a seat (after begin_month)
func rule_actions(f: RefCounted, e: int) -> Array:
	if rule_set == "none":
		return []
	if rule_set == "r55":
		return _r55(f, e)
	var out: Array = []
	_power(f, e, out)
	_dc(f, e, out)
	_fab(f, e, out)
	_answers(f, e, out)
	return out


## Marks the licences an entity's actions close as answers (called by the world after it applied them)
func note_applied(e: int, actions: Array, answering: bool) -> void:
	for a: Dictionary in actions:
		if answering and String(a["act"]) == "licence" and not bool(a["open"]):
			if bool(a.get("answer", false)):
				answers[MC.key(e, String(a["good"]), int(a["to"]))] = true
			if bool(a.get("follow", false)):
				follows[MC.key(e, String(a["good"]), int(a["to"]))] = true


## Alliances and regimes in force at the run's start (no look-ahead: a later accession is a dated event, not an input)
func load_alliances(data: RefCounted, al: Dictionary) -> void:
	var E: int = data.entity_count()
	var start: String = "%04d-01-01" % data.base_year
	var orgs := {}
	in_regime = PackedByteArray()
	in_regime.resize(E)
	for r: Dictionary in al["rows"]:
		var e: int = data.index_of(String(r["iso3"]))
		if e < 0 or r["joined_by"] == null or String(r["joined_by"]) > start or (r["left"] != null and String(r["left"]) <= start):
			continue
		if (al["regimes"] as Array).has(String(r["org"])):
			in_regime[e] = 1
		elif (al["ally_types"] as Array).has(String(r["type"])) and not (al["not_allies"] as Array).has(String(r["org"])):
			var m: Dictionary = orgs.get(String(r["org"]), {})
			m[e] = true
			orgs[String(r["org"])] = m
	allies = []
	allies.resize(E)
	for e2: int in E:
		allies[e2] = {}
	for org: String in orgs:
		for a: int in orgs[org]:
			for b: int in orgs[org]:
				if a != b:
					allies[a][b] = true


func _power(f: RefCounted, e: int, out: Array) -> void:
	var S: int = MD.SOURCES.size()
	var ahead: int = f.day + 365
	var base_then: float = f.base0[e] * DM.pow(1.0 + f.demand_growth[e], float(ahead) / 365.0)
	var it_then: float = minf(f.wanted_it(e, ahead), (f.dc_it[e] + _pending(e, "dc")) * f.u_max)
	var load: float = base_then + it_then * f.pue[e] + (f.fab_cap[e] + _pending(e, "fab")) * f.fab_mw_per_unit
	var sup: float = f.net_imports[e] + (base_then - f.base0[e] if f.gen0[e] == 0.0 else 0.0)
	var cur := PackedFloat64Array()
	cur.resize(S)
	var cur_all: float = 0.0
	for s: int in S:
		var grown: float = f.supply0[e * S + s] + (base_then - f.base0[e]) * f.mix[e * S + s]
		sup += maxf(0.0, grown) + f.supply_built[e * S + s] + _pending(e, MD.SOURCES[s])
		cur[s] = f.supply_of(e, s)
		cur_all += cur[s]
	var short: float = load - sup
	if short <= NOISE * maxf(1.0, load):
		return
	if cur_all <= 0.0:
		out.append({"act": "build", "kind": "gas", "size": short})
		return
	for s2: int in S:
		if cur[s2] > 0.0:
			out.append({"act": "build", "kind": MD.SOURCES[s2], "size": short * cur[s2] / cur_all})


func _dc(f: RefCounted, e: int, out: Array) -> void:
	var lead: int = int(f.data.lead_days["dc"]["days"])
	var want_cap: float = f.wanted_it(e, f.day + lead) / f.u_max
	var gap: float = want_cap - f.dc_it[e] - _pending(e, "dc")
	if gap > NOISE * maxf(1.0, want_cap):
		out.append({"act": "build", "kind": "dc", "size": gap})


func _fab(f: RefCounted, e: int, out: Array) -> void:
	if f.fab_cap[e] > 0.0 and _fab_gap > 0.0:
		out.append({"act": "build", "kind": "fab", "size": _fab_gap * f.fab_cap[e] / _fab_now})


func _answers(f: RefCounted, e: int, out: Array) -> void:
	for row: Array in f.chain.closed_rows():
		if int(row[2]) != e:
			continue
		var k: String = MC.key(int(row[0]), String(row[1]), e)
		if seen_closed.has(k):
			continue
		seen_closed[k] = true
		var issuer: int = int(row[0])
		if answers.has(k):
			continue
		var best: String = ""
		var best_share: float = 0.0
		for g: String in MC.GOODS_LICENSED:
			var sh: float = f.data.share_of(e, "atp" if g == "chips" else g)
			if sh > best_share and f.chain.is_open(e, g, issuer):
				best = g
				best_share = sh
		if best != "":
			out.append({"act": "licence", "good": best, "to": issuer, "open": false, "answer": true})


## R55 Q4 (the rule actors read only their own state and what is public: the licences closed against them; R55 Q2):
##   energy, decided at the first month end of each year and started in twelfths at each month end of that year (R55: decide yearly, apply
##     monthly): how much, per source of the entity's current mix: its share of the load (less contracted imports) one lead time of that
##     source and a year ahead, less its own supply then and its own projects started, closed in the year (lambda = 1, MA; the share rule T).
##     Which source (R55, with R56's costs): the coal, gas, wind and solar part of that is shared by a logit over each one's LCOE^LOGIT_GAMMA
##     (MA) at the entity's WACC with Wright learning (modern_costs.gd); wind and solar are open to every entity, coal and gas to those that
##     have them; nuclear, hydro, oil, bioenergy and other renewables keep their share (T: R56 gives no resource or policy limits for them).
##     Wind and solar a year at most CHERP_CAP of the
##     entity's supply (S), the rest to the other sources by their shares (with none, gas). The cost logit, learning and WACC wait on a
##     technology cost table (NF in R55); the reserve margin needs capacity and peak data (Ember capacity, blocked): energy terms here.
##   data centres: halls for the wanted IT one DC lead time ahead (Q5 growth), paused while the entity's grid binds: its DC load was cut
##     this month or its supply one DC lead time ahead falls short (T, from the Ireland/Singapore pattern)
##   licences: a closure against the entity is answered in kind (the good it holds most of, closed to the issuer), in force COUNTER_DAYS
##     after it is seen (D); an answer is not answered again. R55's 0.4x value match needs trade values (BACI, blocked).
##     Coalition following (R55, with R56's dated alliances): see _follow.
##   fabs (R57): a year's capacity bought by the spending rule (_fab_year), started in twelfths with the energy plan
func _r55(f: RefCounted, e: int) -> Array:
	var out: Array = []
	var S: int = MD.SOURCES.size()
	if (f.day - 1) % 365 == 30:
		plan[e] = _energy_year(f, e, S)
		if not fab.is_empty() and f.fab_cap[e] > 0.0:
			plan[e]["fab"] = _fab_year(f, e) / 12.0
	var p: Dictionary = plan.get(e, {})
	for src: String in p:
		if float(p[src]) > 0.0:
			out.append({"act": "build", "kind": src, "size": float(p[src])})
	var dc_lead: int = int(f.data.lead_days["dc"]["days"])
	var binds: bool = f.dc_served[e] < 1.0 or _gap(f, e, f.day + dc_lead) > NOISE * maxf(1.0, f.demand[e])
	if not binds:
		_dc(f, e, out)
	for row: Array in f.chain.closed_rows():
		if int(row[2]) != e:
			continue
		var k: String = MC.key(int(row[0]), String(row[1]), e)
		if seen_closed.has(k):
			continue
		seen_closed[k] = true
		if answers.has(k) or general.has("%d|%s" % [int(row[0]), String(row[1])]):
			continue
		var best: String = _best_good(f, e, int(row[0]))
		if best != "":
			queued.append([f.day + COUNTER_DAYS, e, best, int(row[0]), "answer"])
	if not allies.is_empty():
		_follow(f, e)
	if restrict_p.has(e):
		_restrict(f, e, out)
	var left: Array = []
	for q: Array in queued:
		if int(q[1]) == e and int(q[0]) <= f.day:
			if f.chain.is_open(e, String(q[2]), int(q[3])):
				var act := {"act": "licence", "good": String(q[2]), "to": int(q[3]), "open": false}
				act[String(q[4])] = true
				out.append(act)
		else:
			left.append(q)
	queued = left
	return out


## New general export restrictions (R56 base rate, R55 contagion; G20 states): each month, for each good the entity holds a share of, a
## chance (base + CONTAGION x others' restricted share of the good) / 12, drawn from a hash of the base year, the entity, the good and the
## day (deterministic, no seed); a restriction closes the good to every destination for RESTRICT_DAYS and is then lifted. Others' restricted
## share counts general restrictions only (public measures; R55 Q2)
func _restrict(f: RefCounted, e: int, out: Array) -> void:
	for g: String in MC.GOODS_LICENSED:
		var gk: String = "%d|%s" % [e, g]
		if general.has(gk):
			if int(general[gk]) <= f.day:
				general.erase(gk)
				for d: int in f.E:
					if d != e and not f.chain.is_open(e, g, d):
						out.append({"act": "licence", "good": g, "to": d, "open": true})
			continue
		var mine: float = f.data.share_of(e, "atp" if g == "chips" else g)
		if mine <= 0.0:
			continue
		var others: float = 0.0
		for k: String in general:
			var p: PackedStringArray = k.split("|")
			if p[1] == g and int(p[0]) != e:
				others += f.data.share_of(int(p[0]), "atp" if g == "chips" else g)
		var chance: float = (float(restrict_p[e]) + CONTAGION * others / maxf(1e-12, 1.0 - mine)) / 12.0
		var u: float = float(("modern-restrict|%d|%s|%s|%d" % [f.data.base_year, f.data.keys[e], g, f.day]).sha256_buffer().decode_u32(0)) / 4294967296.0
		if u < chance:
			general[gk] = f.day + RESTRICT_DAYS
			for d2: int in f.E:
				if d2 != e and f.chain.is_open(e, g, d2):
					out.append({"act": "licence", "good": g, "to": d2, "open": false, "general": true})


## Coalition following (R55, D): an ally of a leader's control, in Wassenaar, holding a share of the good and not allied with the target,
## closes the same good to the same target FOLLOW_DAYS after it saw the control; answers and follows are not followed (T: only a leader's
## own control, else every alliance chain would carry it on)
func _follow(f: RefCounted, e: int) -> void:
	if in_regime[e] == 0:
		return
	for row: Array in f.chain.closed_rows():
		var leader: int = int(row[0])
		var target: int = int(row[2])
		var g: String = String(row[1])
		if leader == e or target == e:
			continue
		var k: String = MC.key(leader, g, target)
		if answers.has(k) or follows.has(k) or general.has("%d|%s" % [leader, g]):
			continue
		var fk: String = "%d|%s" % [e, k]
		if seen_follow.has(fk):
			continue
		seen_follow[fk] = true
		if (allies[e] as Dictionary).has(leader) and not (allies[e] as Dictionary).has(target) \
				and f.data.share_of(e, "atp" if g == "chips" else g) > 0.0 and f.chain.is_open(e, g, target):
			queued.append([f.day + FOLLOW_DAYS, e, g, target, "follow"])


## R57's spending rule (T as R57 declares), from the entity's own figures only: a year's fab capex = KAPPA x its revenue (its fab output a
## year at the start's price per unit: the world's 2021 revenue per world output, T: no price in the field) / (1 - its region's public
## share); the capacity it buys = capex / cost per wspm / the world's start capacity in wspm (field units)
func _fab_year(f: RefCounted, e: int) -> float:
	var out_yr: float = f.fab_out[e] * 365.0
	var macro: String = String(f.data.MACROS[f.data.macro[e]])
	var capex: float = float(fab["kappa"]) * float(fab["revenue"]) * out_yr / (1.0 - float(fab["public_share"][macro]))
	return capex / float(fab["cost_per_wspm"]) / float(fab["world_wspm"])


func _best_good(f: RefCounted, e: int, issuer: int) -> String:
	var best: String = ""
	var best_share: float = 0.0
	for g: String in MC.GOODS_LICENSED:
		var sh: float = f.data.share_of(e, "atp" if g == "chips" else g)
		if sh > best_share and f.chain.is_open(e, g, issuer):
			best = g
			best_share = sh
	return best


## The entity's load on a day ahead: base demand then, the wanted IT within the halls built and started, the fabs built and started
func _load(f: RefCounted, e: int, at: int) -> float:
	var it_then: float = minf(f.wanted_it(e, at), (f.dc_it[e] + _pending(e, "dc")) * f.u_max)
	return f.base_demand(e, at) + it_then * f.pue[e] + (f.fab_cap[e] + _pending(e, "fab")) * f.fab_mw_per_unit


## The entity's load less its supply on a day ahead, every project it started counted as built
func _gap(f: RefCounted, e: int, at: int) -> float:
	var S: int = MD.SOURCES.size()
	var load: float = _load(f, e, at)
	var sup: float = f.imports_of(e, at)
	for s: int in S:
		sup += f.supply_at(e, s, at) + _pending(e, MD.SOURCES[s])
	return load - sup


func _energy_year(f: RefCounted, e: int, S: int) -> Dictionary:
	var cur := PackedFloat64Array()
	cur.resize(S)
	var all: float = 0.0
	for s: int in S:
		cur[s] = f.supply_of(e, s)
		all += cur[s]
	var need := {}
	for s2: int in S:
		var src: String = MD.SOURCES[s2]
		var w: float = cur[s2] / all if all > 0.0 else (1.0 if src == "gas" else 0.0)
		if w <= 0.0:
			continue
		# Why not w x the entity's whole gap: that gap counts the other sources' pipelines, still growing at that horizon, so a short-lead
		# source under-builds once its own pipeline ends (Armenia's DC load was cut to 0 by 2025); each source keeps its share of the load
		# instead. Why the horizon a year past the lead time: the year's last twelfth starts in December (T)
		var h: int = f.day + int(f.data.lead_days[src]["days"]) + 365
		need[src] = maxf(0.0, w * (_load(f, e, h) - f.imports_of(e, h)) - f.supply_at(e, s2, h) - _pending(e, src))
	var wt := {}
	if costs != null:
		var q: float = 0.0
		for src2: String in MC_LOGIT:
			q += float(need.get(src2, 0.0))
			need.erase(src2)
		var tot: float = 0.0
		for src3: String in MC_LOGIT:
			if src3 == "wind" or src3 == "solar" or cur[MD.SOURCES.find(src3)] > 0.0:
				wt[src3] = DM.pow(costs.lcoe(e, src3, float(_learn.get(src3, 1.0))), LOGIT_GAMMA)
				tot += float(wt[src3])
		for src4: String in wt:
			wt[src4] = float(wt[src4]) / tot
			need[src4] = q * float(wt[src4])
	else:
		for s3: int in S:
			if need.has(MD.SOURCES[s3]):
				wt[MD.SOURCES[s3]] = cur[s3]
	var add := {}
	var spare: float = 0.0
	for src5: String in need:
		var a: float = float(need[src5])
		if CHERP_CAP.has(src5) and a > float(CHERP_CAP[src5]) * all:
			spare += a - float(CHERP_CAP[src5]) * all
			a = float(CHERP_CAP[src5]) * all
		add[src5] = a
	if spare > 0.0:
		var rest: float = 0.0
		for src6: String in wt:
			rest += float(wt[src6]) if not CHERP_CAP.has(src6) else 0.0
		for src7: String in wt:
			if not CHERP_CAP.has(src7) and rest > 0.0:
				add[src7] = float(add.get(src7, 0.0)) + spare * float(wt[src7]) / rest
		if rest <= 0.0:
			add["gas"] = float(add.get("gas", 0.0)) + spare
	var monthly := {}
	for src8: String in add:
		if float(add[src8]) > NOISE * maxf(1.0, all):
			monthly[src8] = float(add[src8]) / 12.0
	return monthly


func to_dict() -> Dictionary:
	var a: Array = seen_closed.keys()
	a.sort()
	var b: Array = answers.keys()
	b.sort()
	var pk: Array = plan.keys()
	pk.sort()
	var pl := {}
	for k: int in pk:
		pl[k] = (plan[k] as Dictionary).duplicate()
	var fo: Array = follows.keys()
	fo.sort()
	var sf: Array = seen_follow.keys()
	sf.sort()
	var gk: Array = general.keys()
	gk.sort()
	var gn := {}
	for k6: String in gk:
		gn[k6] = int(general[k6])
	return {"rule_set": rule_set, "seen_closed": a, "answers": b, "plan": pl, "queued": queued.duplicate(true), "follows": fo, "seen_follow": sf,
		"general": gn}


func from_dict(d: Dictionary) -> void:
	rule_set = String(d["rule_set"])
	seen_closed = {}
	for k: Variant in d["seen_closed"]:
		seen_closed[String(k)] = true
	answers = {}
	for k2: Variant in d["answers"]:
		answers[String(k2)] = true
	plan = {}
	for k3: Variant in d.get("plan", {}):
		plan[int(k3)] = (d["plan"][k3] as Dictionary).duplicate()
	queued = (d.get("queued", []) as Array).duplicate(true)
	follows = {}
	for k4: Variant in d.get("follows", []):
		follows[String(k4)] = true
	seen_follow = {}
	for k5: Variant in d.get("seen_follow", []):
		seen_follow[String(k5)] = true
	general = {}
	for k7: Variant in d.get("general", {}):
		general[String(k7)] = int(d["general"][k7])
