extends RefCounted
## Elections at the prefecture grain (BLUEPRINT_v2 3-4; P6 with P8's first cut). The lower house: 289 single-member districts by
## prefecture and 176 proportional seats by 11 blocks (S: 公職選挙法 別表, 2022). Vote shares start from the last election's proportional
## shares (S) in every prefecture (T: no prefecture split yet); the governing parties' share moves with the retrospective evaluation
## (approval, unemployment, prices: the form is T until a published estimate for Japan replaces it); districts in a prefecture go to the
## parties by a cube-law-like bonus (T); proportional seats by d'Hondt (S). Turnout is the published one (S). Deterministic: no draw.
## Data: data/modern/polity/<state>_election.json. The result is a seat table per party, handed to organs.gd (the composition), and
## the PM designation follows (art. 67): the party or coalition with a majority; else the largest party as a minority government.
const DM = preload("res://sim/api/det_math.gd")
const CANON = preload("res://sim/modern/canon.gd")

var spec: Dictionary = {}
var error: String = ""


func load_state(key: String) -> String:
	var p: String = "res://data/modern/polity/%s_election.json" % key.to_lower()
	var d: Variant = CANON.load_json(p)
	if not (d is Dictionary):
		error = "election: no spec at " + p
		return error
	spec = d
	return ""


## National vote shares for this election: the base shares with the governing parties' swing from the retrospective evaluation
func vote_shares(governing: Array, d_approval: float, d_unemployment_pt: float, d_cpi_pt: float) -> Dictionary:
	var base: Dictionary = spec["vote_share_2024_10_27_pr"]
	var r: Dictionary = spec["vote_rule"]["retrospective_swing"]
	var factor: float = 1.0 + float(r["a"]) * d_approval + float(r["b"]) * d_unemployment_pt + float(r["c"]) * d_cpi_pt
	factor = clampf(factor, 0.5, 1.5)
	var out: Dictionary = {}
	var gov_before: float = 0.0
	var gov_after: float = 0.0
	for party: String in spec["parties"]:
		var s: float = float(base.get(party, 0.0))
		if governing.has(party):
			gov_before += s
			s *= factor
			gov_after += s
		out[party] = s
	# the opposition parties share what the governing ones lose or gain, in proportion to their own shares
	var opp_before: float = 1.0 - gov_before
	var opp_after: float = 1.0 - gov_after
	for party: String in out:
		if not governing.has(party) and opp_before > 0.0:
			out[party] = float(out[party]) * opp_after / opp_before
	return out


## d'Hondt over the parties for n seats
static func dhondt(shares: Dictionary, n: int) -> Dictionary:
	var seats: Dictionary = {}
	for p: String in shares:
		seats[p] = 0
	for i: int in n:
		var best: String = ""
		var best_q: float = -1.0
		var ks: Array = shares.keys()
		ks.sort()
		for p: String in ks:
			var q: float = float(shares[p]) / float(int(seats[p]) + 1)
			if q > best_q:
				best_q = q
				best = p
		seats[best] = int(seats[best]) + 1
	return seats


## The districts of one prefecture: share^k over the sum (k = 3, T), whole seats by the largest remainders
static func smd_split(shares: Dictionary, n: int, k: float) -> Dictionary:
	var w: Dictionary = {}
	var tot: float = 0.0
	for p: String in shares:
		var v: float = DM.pow(float(shares[p]), k)
		w[p] = v
		tot += v
	var seats: Dictionary = {}
	var rem: Array = []
	var given: int = 0
	var ks: Array = shares.keys()
	ks.sort()
	for p: String in ks:
		var exact: float = float(n) * float(w[p]) / tot if tot > 0.0 else 0.0
		seats[p] = int(floor(exact))
		given += int(seats[p])
		rem.append([exact - floor(exact), p])
	rem.sort_custom(func(a: Array, b: Array) -> bool: return float(a[0]) > float(b[0]) if float(a[0]) != float(b[0]) else String(a[1]) < String(b[1]))
	for i: int in n - given:
		seats[String(rem[i][1])] = int(seats[String(rem[i][1])]) + 1
	return seats


## The whole lower-house election: seats by party, with the districts and the blocks itemised
func run_lower_house(shares: Dictionary) -> Dictionary:
	var H: Dictionary = spec["houses"]["house_of_representatives"]
	var k: float = 3.0
	var total: Dictionary = {}
	for p: String in spec["parties"]:
		total[p] = 0
	var by_pref: Dictionary = {}
	for pref: String in spec["smd_by_prefecture"]:
		var s: Dictionary = smd_split(shares, int(spec["smd_by_prefecture"][pref]), k)
		by_pref[pref] = s
		for p: String in s:
			total[p] = int(total[p]) + int(s[p])
	var by_block: Dictionary = {}
	for b: String in H["blocks"]:
		var s2: Dictionary = dhondt(shares, int(H["blocks"][b]["seats"]))
		by_block[b] = s2
		for p: String in s2:
			total[p] = int(total[p]) + int(s2[p])
	return {"seats": total, "districts": by_pref, "blocks": by_block, "turnout": float(spec["turnout"]["value"]), "shares": shares.duplicate()}


## Who governs after the election (art. 67): the governing bloc if it keeps a majority; else the largest party, with its partner if that
## makes a majority; else the largest party alone as a minority government (T: coalition bargaining beyond the standing partner is S4')
static func designate(seats: Dictionary, governing: Array, total: int, partners: Dictionary) -> Dictionary:
	var gov: int = 0
	for p: String in governing:
		gov += int(seats.get(p, 0))
	if gov * 2 > total:
		return {"governing": governing.duplicate(), "majority": true, "why": "the governing bloc keeps the majority"}
	var largest: String = ""
	for p: String in seats:
		if largest == "" or int(seats[p]) > int(seats[largest]) or (int(seats[p]) == int(seats[largest]) and p < largest):
			largest = p
	var bloc: Array = [largest]
	var n: int = int(seats[largest])
	for q: String in partners.get(largest, []):
		bloc.append(q)
		n += int(seats.get(q, 0))
	return {"governing": bloc, "majority": n * 2 > total, "why": "the largest party%s" % (" with its partner" if bloc.size() > 1 else " alone, a minority government")}


## The upper-house half election (S4', P6): 74 prefectural-district seats (S: 別表第三; the merged districts counted once) and 50
## proportional seats on a national list by d'Hondt (S). A one-seat district goes by the same rule as a lower-house district; a multi-seat
## district by d'Hondt (T: the real rule is SNTV; d'Hondt stands in until candidate counts are loaded). The new half joins the continuing
## half (S) for the house's composition of 248.
func run_upper_house(shares: Dictionary) -> Dictionary:
	var H: Dictionary = spec["houses"]["house_of_councillors"]
	var elected: Dictionary = {}
	for p: String in spec["parties"]:
		elected[p] = 0
	var by_pref: Dictionary = {}
	var keys: Array = (H["district_seats_per_election"] as Dictionary).keys()
	keys.sort()
	for pref: String in keys:
		var n: int = int(H["district_seats_per_election"][pref])
		var s: Dictionary = smd_split(shares, n, 3.0) if n == 1 else dhondt(shares, n)
		by_pref[pref] = s
		for p: String in s:
			elected[p] = int(elected[p]) + int(s[p])
	var pr: Dictionary = dhondt(shares, int(H["pr"]))
	for p: String in pr:
		elected[p] = int(elected[p]) + int(pr[p])
	var composition: Dictionary = {}
	for p: String in elected:
		composition[p] = int(elected[p]) + int((H["continuing_half_2022"] as Dictionary).get(p, 0))
	return {"elected": elected, "districts": by_pref, "pr": pr, "composition": composition, "shares": shares.duplicate()}
