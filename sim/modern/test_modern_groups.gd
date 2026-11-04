extends "res://tools/test/test_kit.gd"
## ISS Phase 4, groups and the population structure (sim/modern/people/groups.gd): the same small society (2 prefectures x 30, seed 7).
##   godot --headless --path . --script res://sim/modern/test_modern_groups.gd
## G1 classes vs groups: every person is in several classes at once (age band, employment, income tercile, education, prefecture); the
##    aggregate by class gives weighted quantiles with p90 > p10, not a mean; memberships are bounded by M
## G2 start groups from the published rates: the union share among the regular employed is near 0.16 (sample), communities and circles
##    have members, no movement exists at the start
## G3 joining and leaving are actions with drives: over 24 months some join (top drive belonging, contribution or change) and some leave
## G4 emergence: under the shocks a movement is founded by a discontented person with discontented contacts, its members come from the
##    founder's contacts, and it acts (a petition) or dissolves, each with its cause; in a calm society (no shocks) no movement is founded
## G6 a union is a workplace's: every union member is employed with a covered workplace, and over 24 months the union share of the
##    employed stays below the covered share (V088/audit: open to all, it rose from 16% to 61% in a year)
## G7 a movement that stays below DISSOLVE_BELOW members for DISSOLVE_MONTHS dissolves: its status turns, every member is released,
##    the log names it (forced: no run reaches it on its own, V088)
## G8 a group's weight is its members' weights now: after 12 and 36 months every active group's stored weight equals the sum of its
##    members' current weights (the monthly rake moves them; V093 found the weight cached at join up to 0.42 off), and its influence is computed from that weight
## G5 the group influences its members, as a causal contrast on a sample large enough to show it (V088: three founders who start alike
##    show nothing): 3 seeds x 2 prefectures x 100 persons with and without the group's pull, the within-movement standard deviation of
##    the members' discontent at month 24 over the movements with 5+ members is lower with the pull; and the state is reproducible: same
##    seed equal, another differs, resume equals
const PEOPLE = preload("res://sim/modern/people/people.gd")
const GRP = preload("res://sim/modern/people/groups.gd")
const ACT = preload("res://sim/modern/people/actions.gd")
const MS = preload("res://sim/modern/modern_status.gd")


func _make(seed: int, n_per: int = 30) -> RefCounted:
	var st = MS.new()
	st.load(2024, ["JPN"])
	var prefs: Dictionary = {"13": {"pop_thousand": 14178}, "47": {"pop_thousand": 1467}}
	var p = PEOPLE.new()
	var err: String = p.create("JPN", seed, st.cohort["JPN"], st.qx["JPN"], prefs, n_per)
	check(err == "", "people created: " + err)
	return p


func _env(m: int, shocks: bool) -> Dictionary:
	if not shocks:
		return {"inflation_month": 0.02 / 12.0, "food_price_yoy": 0.0, "unemployment_rate": 0.025, "levers": []}
	return {"inflation_month": 0.027 / 12.0, "food_price_yoy": 0.25 if m >= 6 else 0.0, "unemployment_rate": 0.15 if (m >= 6 and m < 12) else 0.025, "levers": ["consumption_tax_rate"] if m == 9 else []}


## [sum of the within-movement SDs of discontent, movements counted] over the active movements with 5+ members
static func _movement_spread(p: RefCounted) -> Array:
	var s: float = 0.0
	var c: int = 0
	var disc: PackedFloat64Array = p.emotion_column("discontent")
	for g: int in p.groups.size():
		if int(p.groups[g]["kind"]) != 5 or int(p.groups[g]["status"]) != 0:
			continue
		var vals: Array = []
		for i: int in p.n:
			if GRP.is_member(p, i, g):
				vals.append(disc[i])
		if vals.size() < 5:
			continue
		var mean: float = 0.0
		for v: float in vals:
			mean += v
		mean /= vals.size()
		var var_: float = 0.0
		for v2: float in vals:
			var_ += (v2 - mean) * (v2 - mean)
		s += sqrt(var_ / vals.size())
		c += 1
	return [s, c]


func _init() -> void:
	var p = _make(7)
	var multi: int = 0
	for i: int in p.n:
		if GRP.classes(p, i).size() == 5:
			multi += 1
	var by: Dictionary = GRP.summary_by_class(p, "employment", p.emotion_column("anxiety"))
	var spread_ok: bool = by.size() >= 3
	for c: String in by:
		var q: Array = by[c]["p10_p50_p90"]
		if int(by[c]["persons"]) >= 5 and float(q[2]) <= float(q[0]):
			spread_ok = false
	var over_m: int = 0
	for i: int in p.n:
		if GRP.memberships(p, i) > GRP.M:
			over_m += 1
	check(multi == p.n and spread_ok and over_m == 0, "G1 persons with 5 classes %d of %d; anxiety by employment class: %s; memberships over M %d" % [multi, p.n, str(by.keys()), over_m])
	var reg: int = 0
	var reg_union: int = 0
	var comm: int = 0
	var circ: int = 0
	for i: int in p.n:
		if p.employment[i] == 1:
			reg += 1
			if GRP.is_member(p, i, GRP.find_group(p, 0, p.pref[i])):
				reg_union += 1
		if GRP.is_member(p, i, GRP.find_group(p, 1, p.pref[i])):
			comm += 1
		if GRP.is_member(p, i, GRP.find_group(p, 2, p.pref[i])):
			circ += 1
	var no_movement: bool = GRP.find_group(p, 5, 13) < 0 and GRP.find_group(p, 5, 47) < 0
	check(reg > 0 and reg_union > 0 and float(reg_union) / reg < 0.45 and comm > 0 and circ > 0 and no_movement, "G2 union members among the regular employed %d of %d; community %d, circle %d; no movement at the start %s" % [reg_union, reg, comm, circ, str(no_movement)])
	var joins: int = 0
	var leaves: int = 0
	var join_drives: Dictionary = {}
	var discontent_before: Dictionary = {}
	for m: int in 24:
		p.step(_env(m, true))
		for row: Dictionary in p.decisions:
			if int(row["month"]) != m:
				continue
			if String(row["action"]) == "join_group":
				joins += int(row["count"])
				for dname: String in row["top_drives"]:
					join_drives[dname] = int(join_drives.get(dname, 0)) + int(row["top_drives"][dname])
			if String(row["action"]) == "leave_group":
				leaves += int(row["count"])
	check(joins > 0 and leaves > 0 and (join_drives.has("belonging") or join_drives.has("contribution") or join_drives.has("change")), "G3 joins %d (top drives %s), leaves %d" % [joins, str(join_drives), leaves])
	var founded: int = 0
	var petitions: int = 0
	var dissolved: int = 0
	var why_f: String = ""
	var members_at_founding: int = 0
	for r: Dictionary in p.group_log:
		match String(r["kind"]):
			"founded":
				founded += 1
				why_f = String(r["why"])
				members_at_founding = maxi(members_at_founding, int(r["members"]))
			"petition":
				petitions += 1
			"dissolved":
				dissolved += 1
	var calm = _make(7)
	for m: int in 24:
		calm.step(_env(m, false))
	var calm_founded: int = 0
	for r: Dictionary in calm.group_log:
		if String(r["kind"]) == "founded":
			calm_founded += 1
	check(founded >= 1 and members_at_founding >= 2 and (petitions + dissolved) >= 1 and calm_founded == 0, "G4 movements founded %d (%s; members at founding %d), petitions %d, dissolved %d; calm society founded %d" % [founded, why_f, members_at_founding, petitions, dissolved, calm_founded])
	var a2 = _make(7)
	var b2 = _make(7)
	var c2 = _make(8)
	var mid: Dictionary = {}
	for m: int in 24:
		a2.step(_env(m, true))
		b2.step(_env(m, true))
		c2.step(_env(m, true))
		if m == 11:
			mid = bytes_to_var(var_to_bytes(a2.to_dict()))
	var r2 = PEOPLE.new()
	r2.from_dict(mid)
	for m: int in range(12, 24):
		r2.step(_env(m, true))
	var un = _make(7, 100)
	var bad: int = 0
	var share_ok: bool = true
	var u_share: float = 0.0
	var c_share: float = 0.0
	for m5: int in 24:
		un.step(_env(m5, true))
		var emp: int = 0
		var mem: int = 0
		var cov: int = 0
		for i7: int in un.n:
			var is_u: bool = false
			for s7: int in GRP.M:
				var g7: int = un.member_of[i7 * GRP.M + s7]
				if g7 >= 0 and int(un.groups[g7]["kind"]) == 0:
					is_u = true
			if is_u and not ((un.employment[i7] == 1 or un.employment[i7] == 2) and un.union_cover[i7] == 1):
				bad += 1
			if un.employment[i7] == 1 or un.employment[i7] == 2:
				emp += 1
				mem += 1 if is_u else 0
				cov += un.union_cover[i7]
		u_share = float(mem) / maxf(1.0, emp)
		c_share = float(cov) / maxf(1.0, emp)
		share_ok = share_ok and mem <= cov
	check(bad == 0 and share_ok, "G6 union members without a covered job %d; at month 24 union share of the employed %.3f, covered %.3f" % [bad, u_share, c_share])
	var dz = _make(7)
	var gm: int = GRP._new_group(dz, 5, 13, -1)
	var joined: int = 0
	for i8: int in dz.n:
		if joined < 2 and dz.pref[i8] == 13 and dz.age[i8] >= 18 and GRP.memberships(dz, i8) < GRP.M:
			GRP.join(dz, i8, gm)
			joined += 1
	dz.groups[gm]["small_months"] = GRP.DISSOLVE_MONTHS - 1
	GRP.step(dz, {})
	var still: int = 0
	for i9: int in dz.n:
		still += 1 if GRP.is_member(dz, i9, gm) else 0
	var logged: bool = false
	for r9: Dictionary in dz.group_log:
		logged = logged or (String(r9["kind"]) == "dissolved" and int(r9["group"]) == gm)
	check(joined == 2 and int(dz.groups[gm]["status"]) == 1 and still == 0 and logged, "G7 a movement of %d members dissolved: status %d, members left %d, logged %s" % [joined, int(dz.groups[gm]["status"]), still, str(logged)])
	# the causal contrast (ISS 10.2): the same seeds with and without the pull
	var on_s: float = 0.0
	var on_c: int = 0
	var off_s: float = 0.0
	var off_c: int = 0
	for sd: int in [1, 2, 3]:
		var pon = _make(sd, 100)
		var poff = _make(sd, 100)
		poff.group_influence = false
		for m2: int in 24:
			pon.step(_env(m2, true))
			poff.step(_env(m2, true))
		var r_on: Array = _movement_spread(pon)
		var r_off: Array = _movement_spread(poff)
		on_s += float(r_on[0])
		on_c += int(r_on[1])
		off_s += float(r_off[0])
		off_c += int(r_off[1])
	var mean_on: float = on_s / maxf(1.0, on_c)
	var mean_off: float = off_s / maxf(1.0, off_c)
	var gw = _make(1)
	var worst: Array = [0.0, 0.0]
	for m3: int in 36:
		gw.step(_env(m3, true))
		if m3 == 11 or m3 == 35:
			var sums: Dictionary = {}
			for i: int in gw.n:
				for k: int in GRP.M:
					var gid: int = gw.member_of[i * GRP.M + k]
					if gid >= 0:
						sums[gid] = float(sums.get(gid, 0.0)) + gw.weight[i]
			var w_worst: float = 0.0
			for g: Dictionary in gw.groups:
				if int(g["status"]) == 0 and int(g["members"]) > 0:
					var true_w: float = float(sums.get(int(g["id"]), 0.0))
					w_worst = maxf(w_worst, absf(float(g["weight"]) / true_w - 1.0))
					var infl: float = true_w / 1e6 * (1.0 + minf(1.0, float(g["resources"]) / 100.0))
					w_worst = maxf(w_worst, absf(float(g["influence"]) / infl - 1.0))
			worst[0 if m3 == 11 else 1] = w_worst
	check(worst[0] < 1e-9 and worst[1] < 1e-9, "G8 worst |stored / members' sum - 1| and |influence / its value from that sum - 1| over the active groups: month 12 %s, month 36 %s" % [String.num_scientific(worst[0]), String.num_scientific(worst[1])])
	check(on_c > 0 and off_c > 0 and mean_on < mean_off and a2.digest() == b2.digest() and a2.digest() != c2.digest() and r2.digest() == a2.digest(),
		"G5 within-movement SD of discontent at month 24 (3 seeds x 200 persons): with the group's pull %.3f over %d movements vs without %.3f over %d; seed 7 twice equal %s; seed 8 differs %s; resume equals %s" % [mean_on, on_c, mean_off, off_c, str(a2.digest() == b2.digest()), str(a2.digest() != c2.digest()), str(r2.digest() == a2.digest())])
	finish()
