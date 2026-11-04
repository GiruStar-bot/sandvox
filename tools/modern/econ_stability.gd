extends SceneTree
## The S-stage stability criterion (ISS_AUDIT.md §8, declared before the storable-goods price rule ran): the economy with the persons off,
## seeded weather and loss events, per seed and month. A month is outside when a storable good's price is not positive and finite, below
## 0.5 or above 2.0 of its start, or food output is below 0.5 of the month's planned output or of the start's output. A month is exempt
## when a declared shock is active or ended within the previous 12 months: a bad-year yield draw (an ordinary yield draw is not a shock
## here, or every month would be exempt), a loss event, the declared drought. One JSON line per seed; no check is judged here.
##   godot --headless --path . --script res://tools/modern/econ_stability.gd -- [--seeds 1-20] [--months 36] [--drought 12:23:0.6] --out <f>
const EM = preload("res://sim/modern/econ/econ_month.gd")
const STORABLE := ["rice", "wheat", "soybeans", "vegetables"]


func _init() -> void:
	var a := {"seeds": "1-20", "months": "36", "drought": "", "out": ""}
	var args: PackedStringArray = OS.get_cmdline_user_args()
	for i: int in range(0, args.size() - 1, 2):
		a[args[i].trim_prefix("--")] = args[i + 1]
	var sr: PackedStringArray = String(a["seeds"]).split("-")
	var months: int = int(a["months"])
	var fo := FileAccess.open(String(a["out"]), FileAccess.WRITE)
	for seed: int in range(int(sr[0]), int(sr[sr.size() - 1]) + 1):
		var e = EM.new()
		if e.create("JPN") != "":
			print("ERROR ", e.error)
			quit(1)
			return
		if String(a["drought"]) != "":
			var p: PackedStringArray = String(a["drought"]).split(":")
			e.declare_shock(int(p[0]), int(p[1]), {"rice": float(p[2]), "vegetables": float(p[2])}, "declared drought")
		e.seed_shocks(seed, months / 12 + 1)
		var exempt := {}
		for s: Dictionary in e.shocks:
			var shock: bool = s.has("cash_loss") or String(s["why"]) == "declared drought"
			for c: String in s.get("yield_factor", {}):
				shock = shock or String(s["why"]).contains(c + " bad year")
			if shock:
				for m: int in range(int(s["from_month"]), int(s["to_month"]) + 13):
					exempt[m] = true
		var fm = e.actors[1]
		var start_out: float = float(fm.stocks["capacity_bn_jpy_month"])
		var outside := 0
		var outside_all := 0
		var broken := 0
		var worst := {}
		var why_out: PackedStringArray = PackedStringArray()
		var pmin := {}
		var pmax := {}
		var fill_min: float = INF
		for i: int in months:
			var m: int = e.world.month
			e.step()
			var bad: PackedStringArray = PackedStringArray()
			for c: String in STORABLE:
				var r: float = float(e.world.good(c, "JPN")["price"]) / float(e.world.commodities[c]["start_price"])
				if is_nan(r) or is_inf(r) or r <= 0.0:
					broken += 1
					bad.append("%s price %s" % [c, str(r)])
					continue
				pmin[c] = minf(float(pmin.get(c, INF)), r)
				pmax[c] = maxf(float(pmax.get(c, -INF)), r)
				if r < 0.5 or r > 2.0:
					bad.append("%s %.2f" % [c, r])
			var of: float = float(fm.output) / maxf(1e-9, float(fm.planned))
			var os: float = float(fm.output) / start_out
			fill_min = minf(fill_min, minf(of, os))
			if of < 0.5 or os < 0.5:
				bad.append("food output %.2f of plan, %.2f of start" % [of, os])
			if bad.size() > 0:
				outside_all += 1
				if not exempt.has(m):
					outside += 1
					if why_out.size() < 6:
						why_out.append("m%d: %s" % [m, ", ".join(bad)])
		var row := {"seed": seed, "months": months, "outside": outside, "outside_incl_exempt": outside_all, "not_finite_or_positive": broken,
			"exempt_months": exempt.size(), "price_min": pmin, "price_max": pmax, "food_output_min": fill_min, "first_outside": why_out,
			"digest": e.digest().left(16)}
		fo.store_line(JSON.stringify(row))
		print("seed %d outside %d (incl. exempt %d) broken %d" % [seed, outside, outside_all, broken])
	fo.close()
	quit(0)
