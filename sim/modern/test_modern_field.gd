extends "res://tools/test/test_kit.gd"
## The modern field's daily step (MODERN_PLAN 2; sim/modern/modern_field.gd, modern_chain.gd).
##   godot --headless --path . --script res://sim/modern/test_modern_field.gd
## F1 the start is balanced: on the first day of 2024 no entity is short (recorded demand = generation + net imports), every DC and fab runs
## F2 power balance closes per entity on a short day (Germany at 70% of its supply, France 5 GW over): supply + net imports + links in - links out + storage out - spilled = demand - cuts -
##    unserved; DC load is cut before fab load, fab load before the rest (unserved within 1e-9 of demand counts as none)
## F3 links carry no more than their capacity, only from a surplus side to a deficit side, and what one side sends the other receives
## F4 licences cut only the licensed shares: closing every EU member's lithography to mainland China leaves China's fabs 11% of their input
##    (R53: 89% from the EU) and every other entity's 100%
## F5 chips: a producer's chips do not reach an ATP entity it closed, that ATP entity's chips do not reach a destination it closed, the rest
##    go by free capacity, and no chip is lost (a three-entity case worked by hand)
## F6 a project finishes on its day and not before (a 1 GW data centre in Japan, 912 days)
## F7 with nothing changed, a year on: no entity is short (ordinary load growth is met at the start's mix), and the servers that retire are
##    replaced (the world's IT in use within 0.5% of the start)
## F8 a state saved and restored mid-run gives the same digest as the run without the stop
## F9 R57's fab ramp and utilisation: a finished fab adds its capacity in nine equal steps over the ramp (none on the finishing day, all of it
##    274 days later), and while some wanted IT finds no chip the fabs run at the top utilisation (output x 0.95 / 0.86)
const MD = preload("res://sim/modern/modern_data.gd")
const MF = preload("res://sim/modern/modern_field.gd")
const MC = preload("res://sim/modern/modern_chain.gd")


func _field() -> RefCounted:
	var d = MD.new()
	d.load_year(2024)
	var f = MF.new()
	f.create(d)
	return f


func _init() -> void:
	var f = _field()
	var E: int = f.E
	f.step()
	var short_n: int = 0
	var cut_n: int = 0
	for e: int in E:
		short_n += 1 if f.unserved[e] > 1e-6 * maxf(1.0, f.demand[e]) else 0
		cut_n += 1 if f.dc_served[e] < 1.0 - 1e-9 or f.fab_served[e] < 1.0 - 1e-9 else 0
	check(short_n == 0 and cut_n == 0, "F1 the first day: %d entities short, %d with DC or fab cut" % [short_n, cut_n])

	var g = _field()
	var deu: int = g.data.index_of("DEU")
	var S: int = MD.SOURCES.size()
	for s: int in S:
		g.supply0[deu * S + s] *= 0.7
	g.storage_cap[deu] = 24.0 * 2000.0
	g.supply_built[g.data.index_of("FRA") * S + MD.SOURCES.find("nuclear")] = 5000.0
	g.storage[deu] = 24.0 * 2000.0
	var sup := PackedFloat64Array()
	var imp := PackedFloat64Array()
	var dl := PackedFloat64Array()
	var fl := PackedFloat64Array()
	for e2: int in E:
		sup.append(g.supply_total(e2))
		imp.append(g.imports_of(e2))
		dl.append(g.dc_load(e2))
		fl.append(g.fab_load(e2))
	g.step()
	var net_in := PackedFloat64Array()
	net_in.resize(E)
	var cap_ok: bool = true
	var dir_ok: bool = true
	for l: int in g.link_a.size():
		var x: float = g.link_flow[l]
		net_in[g.link_b[l]] += x
		net_in[g.link_a[l]] -= x
		cap_ok = cap_ok and absf(x) <= g.link_cap[l] * (1.0 + 1e-12)
		if x != 0.0:
			var to: int = g.link_b[l] if x > 0.0 else g.link_a[l]
			var fr: int = g.link_a[l] if x > 0.0 else g.link_b[l]
			dir_ok = dir_ok and sup[fr] + imp[fr] > g.demand[fr] and sup[to] + imp[to] < g.demand[to]
	var worst: float = 0.0
	var order_ok: bool = true
	for e3: int in E:
		var cut_dc: float = dl[e3] * (1.0 - g.dc_served[e3])
		var cut_fab: float = fl[e3] * (1.0 - g.fab_served[e3])
		var lhs: float = sup[e3] + imp[e3] + net_in[e3] + g.discharge[e3] - g.spilled[e3]
		var rhs: float = g.demand[e3] - cut_dc - cut_fab - g.unserved[e3]
		worst = maxf(worst, absf(lhs - rhs) / maxf(1.0, g.demand[e3]))
		var none_unserved: bool = g.unserved[e3] <= 1e-9 * maxf(1.0, g.demand[e3])
		order_ok = order_ok and (g.fab_served[e3] == 1.0 or g.dc_served[e3] == 0.0) and (none_unserved or g.fab_served[e3] == 0.0)
	var linked: float = 0.0
	for l2: int in g.links_of[deu]:
		linked += absf(g.link_flow[l2])
	check(worst < 1e-9 and order_ok and g.dc_served[deu] < 1.0 and linked > 0.0 and g.discharge[deu] == 2000.0,
		"F2 balance closes (worst %s of demand); Germany at 70%% supply, France 5 GW over: %.0f MW from neighbours, 2,000 MW from storage, DC served %.3f, fab %.3f"
		% [String.num_scientific(worst), linked, g.dc_served[deu], g.fab_served[deu]])
	var sum_in: float = 0.0
	for e4: int in E:
		sum_in += net_in[e4]
	check(cap_ok and dir_ok and absf(sum_in) < 1e-6, "F3 links within capacity, surplus to deficit only, net %s MW over the world" % String.num_scientific(sum_in))

	var h = _field()
	var chn: int = h.data.index_of("CHN")
	for e5: int in E:
		if MD.MACROS[h.data.macro[e5]] == "EU" and h.data.share_of(e5, "lithography") > 0.0:
			h.chain.set_licence(e5, "lithography", chn, false)
	var av: PackedFloat64Array = h.chain.input_availability(h.data, E)
	var others_ok: bool = true
	for e6: int in E:
		others_ok = others_ok and (e6 == chn or av[e6] == 1.0)
	check(absf(av[chn] - 0.11) < 1e-12 and others_ok, "F4 China's fab inputs %.4f with the EU's lithography closed; every other entity 1" % av[chn])

	var c = MC.new()
	c.set_licence(0, "chips", 2, false)
	var stock := PackedFloat64Array([0.0, 0.0, 0.0])
	var got: PackedFloat64Array = c.distribute(PackedFloat64Array([0.5, 0.5, 0.0]), PackedFloat64Array([0.5, 0.0, 0.5]),
		PackedFloat64Array([1.0, 1.0, 2.0]), stock)
	var want := PackedFloat64Array([0.3125, 0.3125, 0.125])
	var hand_ok: bool = absf(stock[0] - 0.25) < 1e-15 and stock[1] == 0.0 and stock[2] == 0.0
	for i: int in 3:
		hand_ok = hand_ok and absf(got[i] - want[i]) < 1e-15
	check(hand_ok and absf(got[0] + got[1] + got[2] + stock[0] - 1.0) < 1e-15,
		"F5 chips by hand: got %s, held by the producer %.4f" % [str(got), stock[0]])

	var p = _field()
	var jpn: int = p.data.index_of("JPN")
	var cap0: float = p.dc_it[jpn]
	var fin: int = p.add_project(jpn, "dc", 1000.0)
	p.advance(fin - 1)
	var before: float = p.dc_it[jpn]
	p.step()
	check(fin == 912 and before == cap0 and absf(p.dc_it[jpn] - cap0 - 1000.0) < 1e-9,
		"F6 Japan's 1 GW data centre finishes on day %d (IT capacity %.0f MW the day before, %.0f MW on the day)" % [fin, before, p.dc_it[jpn]])

	var q = _field()
	var used0: float = 0.0
	for e7: int in E:
		used0 += q.servers[e7]
	var t0: int = Time.get_ticks_usec()
	q.advance(365)
	var ms_day: float = float(Time.get_ticks_usec() - t0) / 1000.0 / 365.0
	var used1: float = 0.0
	var short1: int = 0
	for e8: int in E:
		used1 += q.servers[e8]
		short1 += 1 if q.dc_served[e8] < 1.0 - 1e-9 or q.fab_served[e8] < 1.0 - 1e-9 or q.unserved[e8] > 1e-6 * maxf(1.0, q.demand[e8]) else 0
	check(short1 == 0 and absf(used1 / used0 - 1.0) < 0.005, "F7 a year on: %d entities short; world IT in use %.0f MW at the start, %.0f MW" % [short1,
		used0, used1])

	var a = _field()
	var b = _field()
	for r in [a, b]:
		r.add_project(r.data.index_of("USA"), "solar", 500.0)
		r.advance(40)
		r.chain.set_licence(r.data.index_of("USA"), "chips", r.data.index_of("CHN"), false)
		r.add_project(r.data.index_of("IND"), "storage", 4000.0)
	a.advance(20)
	var saved: PackedByteArray = var_to_bytes(b.to_dict())
	var b2 = _field()
	b2.from_dict(bytes_to_var(saved))
	b2.advance(20)
	check(a.digest() == b2.digest() and a.day == 60, "F8 resume: %s straight, %s after a stop at day 40" % [a.digest().left(16), b2.digest().left(16)])
	var rf = _field()
	rf.util_base = 0.86
	rf.util_top = 0.95
	rf.fab_ramp_days = 274
	var tw9: int = rf.data.index_of("TWN")
	var cap9: float = rf.fab_cap[tw9]
	var fin9: int = rf.add_project(tw9, "fab", 0.09)
	rf.advance(fin9)
	var at_fin: float = rf.fab_cap[tw9] - cap9
	rf.advance(274)
	var at_full: float = rf.fab_cap[tw9] - cap9
	var out_base: float = rf.fab_out[tw9]
	rf.chip_short = true
	rf.step()
	var ratio: float = rf.fab_out[tw9] / out_base
	check(at_fin == 0.0 and absf(at_full - 0.09) < 1e-12 and absf(ratio - 0.95 / 0.86) < 1e-9,
		"F9 fab of 0.09: %.3f added on its finishing day, %.3f after 274 days; output x%.4f while chips are short" % [at_fin, at_full, ratio])
	metric("ms_per_day", ms_day)
	finish()
