class_name EarthKeyed
extends RefCounted
## Keyed, stateless draws and ids of the Earth core (EARTH_CORE_ARCH section 2). Every value is a pure function of its arguments.
# Why not RandomNumberGenerator: its result depends on how many draws came before, so promote would depend on call order (T060 B3)
# Why not hash() alone: it is 32 bits; two hashes under different tags are joined so a million persons do not collide

const ID_MASK := (1 << 62) - 1
const GOLD := -7046029254386353131
const MIX1 := -4658895280553007687
const MIX2 := -7723592293110705685
const FNV_OFFSET := -3750763034362895579
const FNV_PRIME := 1099511628211
# Why not hash(): its output is the engine's own and may change with a build; the mixer below is integer arithmetic only (splitmix64 finaliser, FNV-1a for tags), so a value is the same on every machine and engine version


static func _shr(x: int, n: int) -> int:
	return (x >> n) & ((1 << (64 - n)) - 1)


static func _mix(x: int) -> int:
	x = (x ^ _shr(x, 30)) * MIX1
	x = (x ^ _shr(x, 27)) * MIX2
	return x ^ _shr(x, 31)


static func _tag(tag: String) -> int:
	var h: int = FNV_OFFSET
	for byte: int in tag.to_utf8_buffer():
		h = (h ^ byte) * FNV_PRIME
	return h


static func _h64(seed_v: int, tag: String, a: int, b: int, c: int) -> int:
	var h: int = _mix(seed_v + GOLD)
	h = _mix(h ^ _tag(tag))
	h = _mix(h + a * GOLD)
	h = _mix(h + b * GOLD)
	return _mix(h + c * GOLD)


## 53 random bits
static func raw(seed_v: int, tag: String, a: int = 0, b: int = 0, c: int = 0) -> int:
	return _shr(_h64(seed_v, tag, a, b, c), 11)


## Uniform in [0, 1), 53 bits
static func u(seed_v: int, tag: String, a: int = 0, b: int = 0, c: int = 0) -> float:
	return float(raw(seed_v, tag, a, b, c)) / 9007199254740992.0


## Integer in [0, n)
static func below(n: int, seed_v: int, tag: String, a: int = 0, b: int = 0, c: int = 0) -> int:
	return int(floor(u(seed_v, tag, a, b, c) * float(n))) if n > 0 else 0


## Standard normal from two keyed uniforms (Box-Muller via DetMath so the last bit is the same on every machine)
static func normal(seed_v: int, tag: String, a: int = 0, b: int = 0, c: int = 0) -> float:
	var u1: float = maxf(u(seed_v, tag + "/1", a, b, c), 1e-12)
	var u2: float = u(seed_v, tag + "/2", a, b, c)
	return sqrt(-2.0 * DetMath.log(u1)) * DetMath.cos(6.283185307179586 * u2)


## Person identity: 62-bit, stable for (seed, region id, birth slot year, sex, k)
static func pid(seed_v: int, region_id: int, slot_year: int, sex: int, k: int) -> int:
	var h: int = _mix(_h64(seed_v, "pid", region_id, slot_year, sex) + k * GOLD)
	return h & ID_MASK
