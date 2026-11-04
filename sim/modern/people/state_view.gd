extends RefCounted
## The state view (ISS_TIERED_POPULATION §14.1 T2.R 4″, V110 (2)): one accessor over a person (the persons' arrays at i) or a point
## (tr_points at g) for month_values and its helpers. A field is read by name and position at base = index x its stride (people.fields()),
## always from the owner's current array. A point's contacts, groups and beliefs are given by its caller (POINT_SKIP)
## Why not a cached array per field: a packed array is copied on write, so a cached one goes stale once its owner writes it

const GRP = preload("res://sim/modern/people/groups.gd")
static var _strides: Dictionary = {}

var p: RefCounted
var idx: int
var is_point: bool
var given: Dictionary
var stride: Dictionary


static func strides_of(o: RefCounted) -> Dictionary:
	if _strides.is_empty():
		for fl: Array in o.fields():
			_strides[String(fl[0])] = int(fl[2])
	return _strides


## The view of person i (SV.new().of_person(p, i))
func of_person(o: RefCounted, i: int) -> RefCounted:
	p = o
	idx = i
	is_point = false
	stride = strides_of(o)
	return self


## The view of point g; given holds the fields a point does not carry, each an array of its stride ("belief", "belief_known", "met"),
## and "contacts", "memberships", "in_movement"
func of_point(o: RefCounted, g: int, given_values: Dictionary) -> RefCounted:
	p = o
	idx = g
	is_point = true
	given = given_values
	stride = strides_of(o)
	return self


func f(name: String, k: int = 0) -> float:
	if is_point:
		if given.has(name):
			return float(given[name][k])
		return float(p.tr_points[name][idx * int(stride[name]) + k])
	return float(p.get(name)[idx * int(stride[name]) + k])


func n(name: String, k: int = 0) -> int:
	if is_point:
		if given.has(name):
			return int(given[name][k])
		return int(p.tr_points[name][idx * int(stride[name]) + k])
	return int(p.get(name)[idx * int(stride[name]) + k])


func contacts() -> int:
	return int(given["contacts"]) if is_point else p.contact_count(idx)


func memberships() -> int:
	return int(given["memberships"]) if is_point else GRP.memberships(p, idx)


func in_movement() -> bool:
	return bool(given["in_movement"]) if is_point else p.in_movement(idx)
