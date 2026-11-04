extends SceneTree
## The ISS audit's long run (ISS_AUDIT_BRIEF.md §1-2, ISS_CHECKS.md): the modern world with the persons on, run year by year, writing one
## JSON line per year of the aggregates the checks read. No check is judged here; the lines are read against ISS_CHECKS.md afterwards.
##   godot --headless --path . --script res://tools/modern/iss_audit_run.gd -- [--n 200] [--years 10] [--seed 1] [--shock_seed -1] [--people 1]
##       --out <file.jsonl> [--resume 1]
## shock_seed < 0: no weather draws (the calm run); otherwise econ_month.seed_shocks(shock_seed) over the run's years.
## After each year's line the world is saved to <out>.ckpt; --resume 1 continues from it, keeping only the lines up to its year. Why a
## checkpoint: the cloud container was reclaimed twice during the 20-year runs, and a resumed world equals the straight run (E5).
const MW = preload("res://sim/modern/modern_world.gd")
const MA = preload("res://sim/modern/modern_actors.gd")


func _init() -> void:
	var a := {"n": "200", "years": "10", "seed": "1", "shock_seed": "-1", "people": "1", "out": "", "resume": "0"}
	var args: PackedStringArray = OS.get_cmdline_user_args()
	for i: int in range(0, args.size() - 1, 2):
		a[args[i].trim_prefix("--")] = args[i + 1]
	var years: int = int(a["years"])
	var p := {"view_salt": "0123456789abcdef0123456789abcdef"}
	if a["people"] == "1":
		p["people"] = true
		p["people_seed"] = int(a["seed"])
		p["people_per_prefecture"] = int(a["n"])
	if int(a["shock_seed"]) >= 0:
		p["shock_seed"] = int(a["shock_seed"])
		p["shock_years"] = years + 1
	var ckpt: String = String(a["out"]) + ".ckpt"
	var w = null
	var y0: int = 0
	var start_pref := {}
	var kept: PackedStringArray = PackedStringArray()
	if a["resume"] == "1" and FileAccess.file_exists(ckpt):
		var st: Dictionary = bytes_to_var(FileAccess.get_file_as_bytes(ckpt))
		w = MW.from_dict(st["world"])
		y0 = int(st["year"])
		start_pref = st["start_pref"]
		for line: String in FileAccess.get_file_as_string(String(a["out"])).split("\n", false):
			if int((JSON.parse_string(line) as Dictionary)["year"]) <= y0:
				kept.append(line)
		print("RESUME from year %d (%d lines kept)" % [y0, kept.size()])
	else:
		w = MW.new()
		var err: String = w.create(2024, p)
		if err != "":
			print("ERROR ", err)
			quit(1)
			return
		if w.people != null:
			start_pref = _pref_pop(w.people)
	var fo := FileAccess.open(String(a["out"]), FileAccess.WRITE)
	for line: String in kept:
		fo.store_line(line)
	var t0: int = Time.get_ticks_msec()
	# the start (year 0), for the checks against the start (Y11, Y12): the persons' state before the first month
	if y0 == 0 and w.people != null:
		var row0 := {"year": 0, "day": w.field.day, "elapsed_s": 0.0}
		_persons(w, row0, w.people.decisions.size(), w.people.events.size(), w.people.group_log.size(), start_pref)
		fo.store_line(JSON.stringify(row0))
	for y: int in range(y0, years):
		var dec0: int = w.people.decisions.size() if w.people != null else 0
		var ev0: int = w.people.events.size() if w.people != null else 0
		var gl0: int = w.people.group_log.size() if w.people != null else 0
		var lab0: int = w.econ.labour.log.size() if w.econ.labour != null else 0
		var hist0: int = w.public.history.size() if w.public != null else 0
		var use_min: float = INF
		var px_min := {}
		var px_max := {}
		for m: int in 12:
			# Why the calendar's month ends and not (m + 1) x 365 / 12: the persons' month (and its rake) runs at the month end, and a read a
			# day off saw the previous rake (V093's one-month lag)
			w.advance_to(y * 365 + MA.MONTH_ENDS[m])
			use_min = minf(use_min, float(w.econ.actors[1].stocks.get("capacity_use", 1.0)))
			for c: String in ["rice", "wheat", "soybeans", "vegetables", "food_products"]:
				var r: float = float(w.econ.world.good(c, "JPN")["price"]) / float(w.econ.world.commodities[c]["start_price"])
				px_min[c] = minf(float(px_min.get(c, INF)), r)
				px_max[c] = maxf(float(px_max.get(c, -INF)), r)
		var row := {"year": y + 1, "day": w.field.day, "elapsed_s": (Time.get_ticks_msec() - t0) / 1000.0, "capacity_use_min": use_min, "price_min": px_min, "price_max": px_max,
			"food_price": float(w.econ.world.good("food_products", "JPN")["price"]), "status_unemployment": w.status.value("JPN", "unemployment_rate"),
			"approval_months": [], "digest": w.digest().left(16), "inflation_env": float(w.econ.world.env.get("inflation", NAN))}
		if w.public != null:
			for h: Array in w.public.history.slice(hist0):
				row["approval_months"].append(float(h[1]))
		if w.econ.labour != null:
			var us: float = 0.0
			var rows: Array = w.econ.labour.log.slice(lab0)
			for r2: Array in rows:
				us += float(r2[1])
			row["labour_u_mean"] = us / maxf(1.0, float(rows.size()))
			row["wage_index"] = w.econ.labour.wage_index
			row["food_demand_scale"] = float(rows[-1][6]) if rows.size() > 0 else 1.0
		if w.people != null:
			_persons(w, row, dec0, ev0, gl0, start_pref)
		fo.store_line(JSON.stringify(row))
		fo.flush()
		var fc := FileAccess.open(ckpt + ".tmp", FileAccess.WRITE)
		fc.store_buffer(var_to_bytes({"world": w.to_dict(), "year": y + 1, "start_pref": start_pref}))
		fc.close()
		DirAccess.rename_absolute(ckpt + ".tmp", ckpt)
		print("YEAR %d done %.0f s" % [y + 1, row["elapsed_s"]])
	fo.close()
	print("AUDIT_RUN done; world %s" % w.digest().left(16))
	quit(0)


func _pref_pop(p: RefCounted) -> Dictionary:
	var out := {}
	for i: int in p.n:
		out[p.pref[i]] = float(out.get(p.pref[i], 0.0)) + p.weight[i]
	return out


func _persons(w: RefCounted, row: Dictionary, dec0: int, ev0: int, gl0: int, start_pref: Dictionary) -> void:
	var p = w.people
	var sm: Dictionary = p.summary()
	for k: String in ["real_income_p10_p50_p90", "anxiety_p10_p50_p90", "discontent_p10_p50_p90", "hope_p10_p50_p90", "joy_p10_p50_p90", "trust_p10_p50_p90"]:
		if sm.has(k):
			row[k] = sm[k]
	row["pressure_mean"] = sm["pressure_mean"]
	row["sample_unemployment"] = sm["unemployment_rate"]
	# age structure: sample (weighted) vs the status cohort, bands 0-14, 15-64, 65+
	var sb := [0.0, 0.0, 0.0]
	var tw: float = 0.0
	for i: int in p.n:
		sb[0 if p.age[i] < 15 else (1 if p.age[i] < 65 else 2)] += p.weight[i]
		tw += p.weight[i]
	var cb := [0.0, 0.0, 0.0]
	var co: PackedFloat64Array = w.status.cohort["JPN"]
	var ct: float = 0.0
	for ag: int in 101:
		for sx: int in 2:
			var v: float = co[ag * 2 + sx]
			cb[0 if ag < 15 else (1 if ag < 65 else 2)] += v
			ct += v
	row["age_bands_sample"] = [sb[0] / tw, sb[1] / tw, sb[2] / tw]
	row["age_bands_cohort"] = [cb[0] / ct, cb[1] / ct, cb[2] / ct]
	# prefecture drift: the largest relative change of a prefecture's weighted population since the start
	var now: Dictionary = _pref_pop(p)
	var worst: float = 0.0
	var worst_pref: int = -1
	for code: int in start_pref:
		var rel: float = float(now.get(code, 0.0)) / float(start_pref[code]) - 1.0
		if absf(rel) > absf(worst):
			worst = rel
			worst_pref = code
	row["pref_drift_worst"] = worst
	row["pref_drift_worst_code"] = worst_pref
	row["tokyo_persons"] = 0
	for i: int in p.n:
		if p.pref[i] == 13:
			row["tokyo_persons"] += 1
	# employment structure
	var emp := [0.0, 0.0]
	var nonreg := [0.0, 0.0]
	var adults: float = 0.0
	var no_outside: float = 0.0
	var memb: float = 0.0
	var contacts: float = 0.0
	var union_emp: float = 0.0
	var employees: float = 0.0
	var dream := [0.0, 0.0, 0.0, 0.0]   # none, active, achieved, abandoned
	var p16: float = 0.0
	var none16: float = 0.0
	var inc_emp: float = 0.0
	var spend_emp: float = 0.0
	var spend_single: Array = [0.0, 0.0]
	var spend_two: Array = [0.0, 0.0]
	for i: int in p.n:
		var e: int = p.employment[i]
		if e == 1 or e == 2:
			emp[p.sex[i]] += p.weight[i]
			if e == 2:
				nonreg[p.sex[i]] += p.weight[i]
			employees += p.weight[i]
			for m: int in p.GRP.M:
				var g: int = p.member_of[i * p.GRP.M + m]
				if g >= 0 and int(p.groups[g]["kind"]) == 0:
					union_emp += p.weight[i]
					break
		if p.age[i] >= 16:
			p16 += p.weight[i]
			if p.contact_count(i) == 0:
				none16 += p.weight[i]
		if p.age[i] < 18:
			continue
		adults += p.weight[i]
		memb += p.weight[i] * p.GRP.memberships(p, i)
		var outside: int = 0
		var cc: int = 0
		for c: int in p.REL.C:
			if p.contact_idx[i * p.REL.C + c] >= 0:
				cc += 1
				if p.contact_kind[i * p.REL.C + c] != 0:
					outside += 1
		contacts += p.weight[i] * cc
		if outside == 0:
			no_outside += p.weight[i]
		dream[0 if p.dream_kind[i] < 0 else 1 + p.dream_status[i]] += p.weight[i]
		var spend: float = p.cost_of_living(i) * [0.85, 1.0, 1.2][p.plan[i]]
		if (e == 1 or e == 2) and p.age[i] >= 22:
			inc_emp += p.weight[i] * p.income[i] * (1.0 if p.hh_kind[i] == 0 else minf(p.hh_size[i], 2.0))
			spend_emp += p.weight[i] * spend
		if p.hh_kind[i] == 0:
			spend_single[0] += p.weight[i] * spend
			spend_single[1] += p.weight[i]
		else:
			spend_two[0] += p.weight[i] * spend
			spend_two[1] += p.weight[i]
	row["non_regular_share_men_women"] = [nonreg[0] / maxf(1.0, emp[0]), nonreg[1] / maxf(1.0, emp[1])]
	row["union_share_of_employees"] = union_emp / maxf(1.0, employees)
	row["memberships_per_adult"] = memb / adults
	row["contacts_per_adult"] = contacts / adults
	row["no_contact_outside_household_share"] = no_outside / adults
	# X9's quantity (ISS_CHECKS.md): persons 16+ with no contact of any kind; every model contact lives outside the person's household
	row["no_contact_any_share_16plus"] = none16 / maxf(1.0, p16)
	# X11's quantity: the employed persons' household saving rate, 1 - planned spending / household income (the household income as
	# people.gd's deficits read it: own income x 1 for singles, x min(household size, 2) otherwise)
	row["saving_rate_employed"] = 1.0 - spend_emp / maxf(1e-9, inc_emp)
	row["dream_none_active_achieved_abandoned"] = [dream[0] / adults, dream[1] / adults, dream[2] / adults, dream[3] / adults]
	row["planned_spending_single_two_plus_man_yen"] = [spend_single[0] / maxf(1.0, spend_single[1]), spend_two[0] / maxf(1.0, spend_two[1])]
	var mv: int = 0
	var gsize := {}
	for g2: Dictionary in p.groups:
		if int(g2["status"]) == 0 and int(g2["members"]) > 0:
			var kn: String = p.GRP.KINDS[int(g2["kind"])]
			gsize[kn] = int(gsize.get(kn, 0)) + int(g2["members"])
			if int(g2["kind"]) == 5:
				mv += 1
	row["movements"] = mv
	row["group_members_by_kind"] = gsize
	var pet: int = 0
	var wd: int = 0
	for r: Dictionary in p.group_log.slice(gl0):
		pet += 1 if String(r["kind"]) == "petition" else 0
		wd += 1 if String(r["kind"]) == "wage_demand" else 0
	row["petitions"] = pet
	row["wage_demands"] = wd
	var acts := {}
	var tot: float = 0.0
	for r3: Dictionary in p.decisions.slice(dec0):
		acts[String(r3["action"])] = float(acts.get(String(r3["action"]), 0.0)) + float(r3["weight"])
		tot += float(r3["weight"])
	for k2: String in acts:
		acts[k2] = float(acts[k2]) / tot
	row["action_shares_year"] = acts
	var evs := {}
	for ev: Dictionary in p.events.slice(ev0):
		var k3: String = String(ev["kind"])
		if k3 in ["job_loss:anxiety", "job_found:relief", "changed_job:income_change", "help_given", "help_refused", "met_contact:joy", "died:", "petition", "dream_achieved:joy", "dream_abandoned:sadness"]:
			evs[k3] = float(evs.get(k3, 0.0)) + float(ev["weight"])
	row["event_weights_year"] = evs
	row["job_change_rate_year"] = float(evs.get("changed_job:income_change", 0.0)) / maxf(1.0, employees)
