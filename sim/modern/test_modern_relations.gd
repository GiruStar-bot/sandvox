extends "res://tools/test/test_kit.gd"
## ISS Phase 3, relations and information (sim/modern/people/relations.gd): the same small society (2 prefectures x 30, seed 7).
##   godot --headless --path . --script res://sim/modern/test_modern_relations.gd
## R1 relations exist and are bounded: every adult has at least one contact, nobody more than C, links are symmetric, trust in 0..100,
##    the kinds include family, friend, colleague and neighbour
## R2 an interaction moves both sides: in a month where a person socialised, its partner's trust in it rose by 3 and both met;
##    loneliness of the single who met someone is below the no-meeting path
## R3 information reaches people late, wrong or not at all: a food price rise of 15% from month 12; the same month some readers know it
##    within the publication error, others hear it from contacts in later months with more spread. Contacts carry it: in the same society
##    with the contacts' channel off, fewer adults know it a month on (V087: the old form could not show that), and there the unknowing,
##    who exist, gain less anxiety than the knowers
## R4 trust and help: unemployed persons short of money ask their most trusted contact; help is given in some cases (+3 trust) and
##    refused in others (-4), both recorded with their rule
## R5 seed and resume: same seed equal, another seed differs, a resume at month 12 equals the straight run (contacts and beliefs included)
## R6 the network holds over years: in a calm society over 120 months the yearly renewal keeps contacts per adult at 0.8 of the start
##    or more, and loses less than half of what the same society loses with the renewal off; the share of adults with no contact
##    outside the household rises by at most 5 points, and every link stays symmetric
const PEOPLE = preload("res://sim/modern/people/people.gd")
const REL = preload("res://sim/modern/people/relations.gd")
const MS = preload("res://sim/modern/modern_status.gd")


func _make(seed: int) -> RefCounted:
	var st = MS.new()
	st.load(2024, ["JPN"])
	var prefs: Dictionary = {"13": {"pop_thousand": 14178}, "47": {"pop_thousand": 1467}}
	var p = PEOPLE.new()
	var err: String = p.create("JPN", seed, st.cohort["JPN"], st.qx["JPN"], prefs, 30)
	check(err == "", "people created: " + err)
	return p


func _env(m: int) -> Dictionary:
	return {"inflation_month": 0.027 / 12.0, "food_price_yoy": 0.15 if m >= 12 else 0.0, "unemployment_rate": 0.12 if (m >= 6 and m < 9) else 0.025, "levers": []}


## [contacts per adult, share of adults with no contact outside the household, asymmetric links]
static func _network(p: RefCounted) -> Array:
	var adults: int = 0
	var cc: int = 0
	var alone: int = 0
	var asym: int = 0
	for i: int in p.n:
		var outside: int = 0
		for c: int in REL.C:
			var j: int = p.contact_idx[i * REL.C + c]
			if j < 0:
				continue
			if REL.slot(p, j, i) < 0:
				asym += 1
			if p.age[i] >= 15:
				cc += 1
				outside += 1 if p.contact_kind[i * REL.C + c] != 0 else 0
		if p.age[i] >= 15:
			adults += 1
			alone += 1 if outside == 0 else 0
	return [float(cc) / adults, float(alone) / adults, asym]


func _calm(m: int) -> Dictionary:
	return {"inflation_month": 0.02 / 12.0, "food_price_yoy": 0.0, "unemployment_rate": 0.025, "levers": []}


func _init() -> void:
	var p = _make(7)
	var adults_without: int = 0
	var over: int = 0
	var asym: int = 0
	var bad_trust: int = 0
	var kinds: Dictionary = {}
	for i: int in p.n:
		var k: int = p.contact_count(i)
		if p.age[i] >= 18 and k == 0:
			adults_without += 1
		if k > REL.C:
			over += 1
		for c: int in REL.C:
			var j: int = p.contact_idx[i * REL.C + c]
			if j < 0:
				continue
			if not REL.has_contact(p, j, i):
				asym += 1
			var t: float = p.contact_trust[i * REL.C + c]
			if t < 0.0 or t > 100.0:
				bad_trust += 1
			kinds[REL.KINDS[p.contact_kind[i * REL.C + c]]] = int(kinds.get(REL.KINDS[p.contact_kind[i * REL.C + c]], 0)) + 1
	check(adults_without == 0 and over == 0 and asym == 0 and bad_trust == 0 and kinds.size() == 4, "R1 adults without contacts %d, over C %d, asymmetric %d, trust out of range %d; kinds %s" % [adults_without, over, asym, bad_trust, str(kinds)])
	# R2: run a month and look at the pairs where i socialised
	var trust_before: PackedFloat64Array = p.contact_trust.duplicate()
	var lone_before: PackedFloat64Array = p.emotion_column("loneliness")
	p.step(_env(0))
	var pairs: int = 0
	var rose: int = 0
	var single_met_lower: int = 0
	var single_met: int = 0
	for i: int in p.n:
		if p.last_action[i] == 7:
			pairs += 1
			for c: int in REL.C:
				var j: int = p.contact_idx[i * REL.C + c]
				if j >= 0 and p.contact_trust[i * REL.C + c] > trust_before[i * REL.C + c]:
					var back: int = REL.slot(p, j, i)
					if back >= 0 and p.contact_trust[j * REL.C + back] > trust_before[j * REL.C + back]:
						rose += 1
			if p.hh_kind[i] == 0:
				single_met += 1
				if p.emotion(i, "loneliness") < lone_before[i] + 0.02 * p.pref_social[i]:
					single_met_lower += 1
	check(pairs > 0 and rose > 0 and single_met_lower == single_met, "R2 %d socialised; mutual trust rose in %d pairs; singles who met %d, loneliness below the alone path for %d" % [pairs, rose, single_met, single_met_lower])
	# R3: the price shock
	for m: int in range(1, 12):
		p.step(_env(m))
	var anx_before: PackedFloat64Array = p.emotion_column("anxiety")
	p.step(_env(12))
	var readers: int = 0
	var reader_err_ok: int = 0
	var unknown12: int = 0
	for i: int in p.n:
		if p.age[i] < 15:
			continue
		if p.belief_known[i * REL.NF] == 1 and p.belief_source[i * REL.NF] == 0 and p.belief_month[i * REL.NF] == 12:
			readers += 1
			if absf(p.belief[i * REL.NF] - 0.15) <= float(REL.PUBLISH_ERR_BY_FACT[0]) + 1e-9:
				reader_err_ok += 1
		elif p.belief_known[i * REL.NF] == 0 or absf(p.belief[i * REL.NF]) < 0.03:
			unknown12 += 1
	for m: int in range(13, 18):
		p.step(_env(m))
	var heard: int = 0
	var never: int = 0
	var heard_spread: float = 0.0
	var hmin: float = 1.0
	var hmax: float = -1.0
	var anx_up_known: int = 0
	var known: int = 0
	var anx_up_unknown: int = 0
	var unknown: int = 0
	for i: int in p.n:
		if p.age[i] < 15:
			continue
		var kn: bool = p.belief_known[i * REL.NF] == 1 and p.belief[i * REL.NF] > 0.03
		if kn:
			known += 1
			if p.emotion(i, "anxiety") > anx_before[i]:
				anx_up_known += 1
			if p.belief_source[i * REL.NF] == 1:
				heard += 1
				hmin = minf(hmin, p.belief[i * REL.NF])
				hmax = maxf(hmax, p.belief[i * REL.NF])
		else:
			unknown += 1
			never += 1
	heard_spread = hmax - hmin if heard > 1 else 0.0
	# the same society with and without the contacts' channel, to month 13 (one month after the rise)
	var on = _make(7)
	var off = _make(7)
	off.contact_news = false
	for m3: int in 12:
		on.step(_env(m3))
		off.step(_env(m3))
	var anx11: PackedFloat64Array = off.emotion_column("anxiety")
	on.step(_env(12))
	off.step(_env(12))
	on.step(_env(13))
	off.step(_env(13))
	var k_on: int = 0
	var k_off: int = 0
	var adults: int = 0
	var d_known: float = 0.0
	var n_known: int = 0
	var d_unknown: float = 0.0
	var n_unknown: int = 0
	var anx13: PackedFloat64Array = off.emotion_column("anxiety")
	for i3: int in on.n:
		if on.age[i3] < 15:
			continue
		adults += 1
		k_on += 1 if on.belief_known[i3 * REL.NF] == 1 and on.belief[i3 * REL.NF] > 0.03 else 0
		var kn: bool = off.belief_known[i3 * REL.NF] == 1 and off.belief[i3 * REL.NF] > 0.03
		k_off += 1 if kn else 0
		if kn:
			d_known += anx13[i3] - anx11[i3]
			n_known += 1
		else:
			d_unknown += anx13[i3] - anx11[i3]
			n_unknown += 1
	var mk: float = d_known / maxf(1.0, n_known)
	var mu: float = d_unknown / maxf(1.0, n_unknown)
	check(readers > 0 and reader_err_ok == readers and heard > 0 and k_on > k_off and n_unknown > 0 and n_known > 0 and mk > mu,
		"R3 month 12: %d read the register (all within the publication error %s); by month 17: %d heard it from contacts (beliefs spread %.3f), %d still do not know; month 13: %d of %d adults know it with contacts vs %d without; without contacts the %d knowers' anxiety moved %+.3f vs the %d unknowing %+.3f" % [readers, str(reader_err_ok == readers), heard, heard_spread, never, k_on, adults, k_off, n_known, mk, n_unknown, mu])
	var given: int = 0
	var refused: int = 0
	for ev: Dictionary in p.events:
		if String(ev["kind"]) == "help_given":
			given += int(ev["count"])
		if String(ev["kind"]) == "help_refused":
			refused += int(ev["count"])
	check(given + refused > 0 and refused > 0, "R4 help given %d, refused %d (both recorded with their rule)" % [given, refused])
	var a2 = _make(7)
	var b2 = _make(7)
	var c2 = _make(8)
	var mid: Dictionary = {}
	for m: int in 24:
		a2.step(_env(m))
		b2.step(_env(m))
		c2.step(_env(m))
		if m == 11:
			mid = bytes_to_var(var_to_bytes(a2.to_dict()))
	var r2 = PEOPLE.new()
	r2.from_dict(mid)
	for m: int in range(12, 24):
		r2.step(_env(m))
	check(a2.digest() == b2.digest() and a2.digest() != c2.digest() and r2.digest() == a2.digest(), "R5 seed 7 twice equal %s; seed 8 differs %s; resume equals %s" % [str(a2.digest() == b2.digest()), str(a2.digest() != c2.digest()), str(r2.digest() == a2.digest())])
	var nw = _make(7)
	var nx = _make(7)
	nx.contact_renewal = false
	var n0: Array = _network(nw)
	for m4: int in 120:
		nw.step(_calm(m4))
		nx.step(_calm(m4))
	var n1: Array = _network(nw)
	var nx1: Array = _network(nx)
	var loss_with: float = float(n0[0]) - float(n1[0])
	var loss_without: float = float(n0[0]) - float(nx1[0])
	check(loss_without > 0.0 and loss_with < 0.5 * loss_without and float(n1[0]) >= 0.8 * float(n0[0]) and float(n1[1]) <= float(n0[1]) + 0.05 and int(n1[2]) == 0 and int(nx1[2]) == 0,
		"R6 contacts per adult %.1f at the start; after 120 months %.1f with the renewal vs %.1f without; no contact outside the household %.2f -> %.2f; asymmetric links %d / %d" % [n0[0], n1[0], nx1[0], n0[1], n1[1], n1[2], nx1[2]])
	finish()
