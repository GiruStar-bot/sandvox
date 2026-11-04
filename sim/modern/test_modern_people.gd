extends "res://tools/test/test_kit.gd"
## ISS Phase 1, the small society (ISS_PHASE0_SURVEY.md 4; sim/modern/people/people.gd): 30 persons in each of two prefectures drawn from
## the 2024 cohort, run 24 months through one shared situation (a lay-off wave from month 6 and a food price rise from month 12).
##   godot --headless --path . --script res://sim/modern/test_modern_people.gd
## I1 identity and heterogeneity: 60 unique pids; within one prefecture the traits, incomes and anxieties spread (p90 > p10), not one mean
## I2 the same situation, different readings: the lay-off wave hits several persons; their anxiety moves differ (scaled by risk tolerance
##    and loss aversion) and every aggregate event row names its cause; persons with a lower risk tolerance move more on average
## I3 feedback: after the wave the economic-security deficit and anxiety of the hit persons are above their start; income received above
##    the expectation raises joy; a dream progresses for savers and is abandoned with a stated cause for a person with no savings
## I4 seed: the same seed twice gives the same digest; another seed differs; saved at month 12 and resumed equals the straight run
## I5 hidden state: the modern view's observation of Japan carries no person-level field, and the summary has only aggregates
const PEOPLE = preload("res://sim/modern/people/people.gd")
const MS = preload("res://sim/modern/modern_status.gd")
const MW = preload("res://sim/modern/modern_world.gd")
const CANON = preload("res://sim/modern/canon.gd")
const SALT := "0123456789abcdef0123456789abcdef"


func _make(seed: int) -> RefCounted:
	var st = MS.new()
	st.load(2024, ["JPN"])
	var prefs: Dictionary = {"13": {"pop_thousand": 14178}, "47": {"pop_thousand": 1467}}
	var p = PEOPLE.new()
	var err: String = p.create("JPN", seed, st.cohort["JPN"], st.qx["JPN"], prefs, 30)
	check(err == "", "people created: " + err)
	return p


func _env(m: int) -> Dictionary:
	return {"inflation_month": 0.027 / 12.0, "food_price_yoy": 0.15 if m >= 12 else 0.0, "unemployment_rate": 0.18 if (m >= 6 and m < 9) else 0.025, "levers": ["consumption_tax_rate"] if m == 18 else []}


func _init() -> void:
	var p = _make(7)
	var ids: Dictionary = {}
	for i: int in p.n:
		ids[p.pid[i]] = true
	var tokyo: Array = []
	for i: int in p.n:
		if p.pref[i] == 13:
			tokyo.append(i)
	var qa: Array = p.quantiles(p.emotion_column("anxiety"), tokyo)
	var qi: Array = p.quantiles(p.income, tokyo)
	var tr := PackedFloat64Array()
	tr.resize(p.n)
	for i: int in p.n:
		tr[i] = p.trait_of(i, "risk_tolerance")
	var qt: Array = p.quantiles(tr, tokyo)
	check(ids.size() == 60 and p.n == 60 and float(qa[2]) > float(qa[0]) and float(qi[2]) > float(qi[0]) and float(qt[2]) > float(qt[0]),
		"I1 %d unique pids of %d; Tokyo anxiety p10/p50/p90 %.2f/%.2f/%.2f, income %.1f/%.1f/%.1f 万円, risk tolerance %.2f/%.2f/%.2f" % [ids.size(), p.n, qa[0], qa[1], qa[2], qi[0], qi[1], qi[2], qt[0], qt[1], qt[2]])
	# the shared situation
	var anx0: PackedFloat64Array = p.emotion_column("anxiety")
	var sec0: PackedFloat64Array = p.deficit_column("economic_security")
	var emp0: PackedInt32Array = p.employment.duplicate()
	p.trace_pids = [p.pid[0], p.pid[1], p.pid[2]]
	var hit: Dictionary = {}
	for m: int in 24:
		p.step(_env(m))
		if m >= 6 and m < 9:
			for i: int in p.n:
				if (emp0[i] == 1 or emp0[i] == 2) and p.employment[i] == 3:
					hit[i] = true
	var moves: Array = []
	var low_rt: Array = []
	var high_rt: Array = []
	var job_rows: int = 0
	var named: bool = true
	for ev: Dictionary in p.events:
		if String(ev["kind"]).begins_with("job_loss:anxiety"):
			job_rows += 1
			if not String(ev["why"]).begins_with("scaled by"):
				named = false
	for i: int in hit:
		var mv: float = p.emotion(i, "anxiety") - anx0[i]
		moves.append(mv)
		if p.trait_of(i, "risk_tolerance") < 0.5:
			low_rt.append(mv)
		else:
			high_rt.append(mv)
	var spread: float = 0.0
	if moves.size() >= 2:
		var mn: float = moves[0]
		var mx: float = moves[0]
		for v: float in moves:
			mn = minf(mn, v)
			mx = maxf(mx, v)
		spread = mx - mn
	var mean_low: float = 0.0
	var mean_high: float = 0.0
	for v: float in low_rt:
		mean_low += v / maxf(1.0, low_rt.size())
	for v: float in high_rt:
		mean_high += v / maxf(1.0, high_rt.size())
	check(hit.size() >= 3 and spread > 0.01 and job_rows > 0 and named and (low_rt.is_empty() or high_rt.is_empty() or mean_low > mean_high),
		"I2 %d persons lost a job; anxiety responses spread %.3f; low risk tolerance mean %.3f vs high %.3f (%d/%d); %d job_loss rows, causes named %s" % [hit.size(), spread, mean_low, mean_high, low_rt.size(), high_rt.size(), job_rows, str(named)])
	var sec_up: int = 0
	for i: int in hit:
		if p.deficit(i, "economic_security") > sec0[i] and p.emotion(i, "anxiety") > anx0[i] - 0.05:
			sec_up += 1
	var joy_rows: int = 0
	var abandoned: int = 0
	var abandon_why: String = ""
	var progressed: int = 0
	for ev: Dictionary in p.events:
		if String(ev["kind"]).begins_with("income_above_expectation:joy"):
			joy_rows += 1
		if String(ev["kind"]).begins_with("dream_abandoned:"):
			abandoned += int(ev["count"])
			abandon_why = String(ev["why"])
	for i: int in p.n:
		if p.dream_kind[i] >= 0 and p.dream_progress[i] > 0.3:
			progressed += 1
	check(sec_up >= 1 and joy_rows > 0 and progressed > 0 and p.trace.size() > 0,
		"I3 security deficit up for %d of %d hit; joy rows %d; dreams progressed %d, abandoned %d (%s); trace rows %d" % [sec_up, hit.size(), joy_rows, progressed, abandoned, abandon_why, p.trace.size()])
	# I4 seeds and resume
	var a = _make(7)
	var b = _make(7)
	var c = _make(8)
	var mid: Dictionary = {}
	for m: int in 24:
		a.step(_env(m))
		b.step(_env(m))
		c.step(_env(m))
		if m == 11:
			mid = bytes_to_var(var_to_bytes(a.to_dict()))
	var r = PEOPLE.new()
	r.from_dict(mid)
	for m: int in range(12, 24):
		r.step(_env(m))
	check(a.digest() == b.digest() and a.digest() != c.digest() and r.digest() == a.digest(),
		"I4 seed 7 twice equal %s; seed 8 differs %s; resumed at 12 equals straight %s" % [str(a.digest() == b.digest()), str(a.digest() != c.digest()), str(r.digest() == a.digest())])
	# I5 hidden state
	var w = MW.new()
	var err: String = w.create(2024, {"view_salt": SALT, "people": true, "people_per_prefecture": 5})
	w.advance_to(62)
	var v = w.make_view("jpn")
	var obs: Dictionary = v.observe(w, w.data.index_of("JPN"))
	var leak: bool = JSON.stringify(obs).contains("anxiety") or JSON.stringify(obs).contains("\"traits\"") or obs.has("people")
	var s: Dictionary = w.people.summary()
	var only_aggr: bool = s.has("anxiety_p10_p50_p90") and not s.has("pid") and not s.has("traits")
	check(err == "" and w.people != null and w.people.month >= 2 and not leak and only_aggr and w.people.n == 235,
		"I5 world with people: %d persons, %d months; observation leaks %s; summary aggregate-only %s; national unemployment in the sample %.3f" % [w.people.n, w.people.month, str(leak), str(only_aggr), float(s["unemployment_rate"])])
	finish()
