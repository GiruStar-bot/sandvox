extends RefCounted
## Export licences and the compute chain's flows (MODERN_PLAN 2; R53 Q2-Q3). A licence is (issuer entity, good, destination entity); every
## licence is open unless closed here, so only the closed ones are kept (sorted keys, saved).
##   input availability of a fab at e for input good g = 1 - sum over issuers j that closed (j, g, e) of j's share of g (no substitution within
##   the horizon except by projects: THEORY); the fab runs at the Leontief minimum over INPUTS
##   chips: a day's fab output of every producer goes to the ATP entities by ATP share (a producer's chips do not reach an ATP entity it closed
##   "chips" to; that part stays in the producer's stock), and each ATP entity's packaged chips go to the destinations it has not closed "chips" to, in proportion to their free DC
##   capacity; what finds no free capacity stays as that destination's stock (or, with no destination at all, the ATP entity's)
const MD = preload("res://sim/modern/modern_data.gd")
const INPUTS: Array[String] = ["lithography", "photoresist", "silicon_wafers", "gallium", "neon"]
const GOODS_LICENSED: Array[String] = ["lithography", "photoresist", "silicon_wafers", "gallium", "neon", "chips"]

var closed: Dictionary = {}   # "issuer|good|dest" (entity indices) -> true


static func key(issuer: int, good: String, dest: int) -> String:
	return "%d|%s|%d" % [issuer, good, dest]


func is_open(issuer: int, good: String, dest: int) -> bool:
	return not closed.has(key(issuer, good, dest))


func set_licence(issuer: int, good: String, dest: int, open: bool) -> void:
	var k: String = key(issuer, good, dest)
	if open:
		closed.erase(k)
	else:
		closed[k] = true


## The closed licences in key order, as [issuer, good, dest]
func closed_rows() -> Array:
	var out: Array = []
	var ks: Array = closed.keys()
	ks.sort()
	for k: String in ks:
		var p: PackedStringArray = k.split("|")
		out.append([int(p[0]), p[1], int(p[2])])
	return out


## Per entity and input (entity x INPUTS) the share of the input's supply whose issuer licenses that entity
func input_availability_by(data: RefCounted, E: int) -> PackedFloat64Array:
	var out := PackedFloat64Array()
	out.resize(E * INPUTS.size())
	out.fill(1.0)
	for row: Array in closed_rows():
		var i: int = INPUTS.find(String(row[1]))
		if i >= 0:
			var k: int = int(row[2]) * INPUTS.size() + i
			out[k] = maxf(0.0, out[k] - data.share_of(int(row[0]), String(row[1])))
	return out


## Per entity the input availability of its fabs (Leontief minimum over INPUTS)
func input_availability(data: RefCounted, E: int) -> PackedFloat64Array:
	var out := PackedFloat64Array()
	out.resize(E)
	out.fill(1.0)
	var lost := {}
	for row: Array in closed_rows():
		var g: String = String(row[1])
		if not INPUTS.has(g):
			continue
		var kk: String = "%d|%s" % [int(row[2]), g]
		lost[kk] = float(lost.get(kk, 0.0)) + data.share_of(int(row[0]), g)
	for kk2: String in lost:
		var p: PackedStringArray = kk2.split("|")
		var e: int = int(p[0])
		out[e] = minf(out[e], maxf(0.0, 1.0 - float(lost[kk2])))
	return out


## Distributes the day's chips: out[e] produced, atp[a] ATP shares, free[d] free DC capacity (IT MW); returns per entity the chips received
## (by destination) and adds what finds no capacity to stock
func distribute(out: PackedFloat64Array, atp: PackedFloat64Array, free: PackedFloat64Array, stock: PackedFloat64Array) -> PackedFloat64Array:
	var E: int = out.size()
	var got := PackedFloat64Array()
	got.resize(E)
	var W: float = 0.0
	for e: int in E:
		W += out[e]
	if W <= 0.0:
		return got
	var cut_to := {}    # ATP entity -> chips its producers withhold
	var cut_from := {}  # ATP entity -> {dest: true} it withholds
	for row: Array in closed_rows():
		if String(row[1]) != "chips":
			continue
		cut_to[int(row[2])] = float(cut_to.get(int(row[2]), 0.0)) + out[int(row[0])]
		stock[int(row[0])] += atp[int(row[2])] * out[int(row[0])]
		var s: Dictionary = cut_from.get(int(row[0]), {})
		s[int(row[2])] = true
		cut_from[int(row[0])] = s
	var free_all: float = 0.0
	for d: int in E:
		free_all += maxf(0.0, free[d])
	# Why not a share-out per ATP entity: those that closed no destination all split by the same free capacity, so they go out once
	var open_p: float = 0.0
	for a: int in E:
		if atp[a] <= 0.0:
			continue
		var p_a: float = atp[a] * maxf(0.0, W - float(cut_to.get(a, 0.0)))
		if p_a <= 0.0:
			continue
		if not cut_from.has(a):
			open_p += p_a
			continue
		var cuts: Dictionary = cut_from[a]
		var tot: float = free_all
		for d2: Variant in cuts:
			tot -= maxf(0.0, free[int(d2)])
		if tot <= 0.0:
			stock[a] += p_a
			continue
		for d3: int in E:
			if free[d3] > 0.0 and not cuts.has(d3):
				got[d3] += p_a * free[d3] / tot
	if open_p > 0.0:
		if free_all <= 0.0:
			for a2: int in E:
				if atp[a2] > 0.0 and not cut_from.has(a2):
					stock[a2] += atp[a2] * maxf(0.0, W - float(cut_to.get(a2, 0.0)))
		else:
			for d4: int in E:
				if free[d4] > 0.0:
					got[d4] += open_p * free[d4] / free_all
	return got


func to_dict() -> Dictionary:
	var ks: Array = closed.keys()
	ks.sort()
	return {"closed": ks}


func from_dict(d: Dictionary) -> void:
	closed = {}
	for k: Variant in d.get("closed", []):
		closed[String(k)] = true
