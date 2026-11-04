class_name DetMath
extends RefCounted
## OS によらず同じビットの答えを出す数学（docs/team/DET_MATH.md）。sim の答えに入る計算は、組み込みの exp・log・pow・sin・cos・
## randfn・Vector2.angle_to・rotated の代わりにこれを使う。C++ の双子は native/the_world_native/src/det_math.h（同じ式・同じ順）。
## 使うのは足し算・掛け算・割り算・sqrt・floor（IEEE 754 で答えが1つに決まる）と、整数・ビットの操作だけ。
## 式は fdlibm（Sun、1993）の e_exp・e_log・k_sin・k_cos（FreeBSD 版）・s_atan・e_atan2。係数は fdlibm と同じ値を、ビットで書く。

## Why not 10進の定数: 係数を10進で書くと、読み（文字列→数）の実装の違いに頼ることになる。ビット（整数）から作れば、どこでも同じ数
## Why not 符号のビット付きの16進: GDScript の 0x8000… 以上の整数の字は int64 を溢れる。負の係数は正のビットから作って符号を変える
static func _f(bits: int) -> float:
	var b := PackedByteArray()
	b.resize(8)
	b.encode_s64(0, bits)
	return b.decode_double(0)

static var INVLN2: float = _f(0x3FF71547652B82FE)
static var LN2HI: float = _f(0x3FE62E42FEE00000)
static var LN2LO: float = _f(0x3DEA39EF35793C76)
static var EXP_HI: float = _f(0x40862E42FEFA39EF)
static var EXP_LO: float = -_f(0x40874910D52D3051)
static var P1: float = _f(0x3FC555555555553E)
static var P2: float = -_f(0x3F66C16C16BEBD93)
static var P3: float = _f(0x3F11566AAF25DE2C)
static var P4: float = -_f(0x3EBBBD41C5D26BF1)
static var P5: float = _f(0x3E66376972BEA4D0)

static var TWO54: float = _f(0x4350000000000000)
static var MIN_NORMAL: float = _f(0x0010000000000000)
static var THIRD: float = _f(0x3FD5555555555555)
static var LG1: float = _f(0x3FE5555555555593)
static var LG2: float = _f(0x3FD999999997FA04)
static var LG3: float = _f(0x3FD2492494229359)
static var LG4: float = _f(0x3FCC71C51D8E78AF)
static var LG5: float = _f(0x3FC7466496CB03DE)
static var LG6: float = _f(0x3FC39A09D078C69F)
static var LG7: float = _f(0x3FC2F112DF3E5244)

static var PIO4: float = _f(0x3FE921FB54442D18)
static var TWOM27: float = _f(0x3E40000000000000)
static var INVPIO2: float = _f(0x3FE45F306DC9C883)
static var PIO2_1: float = _f(0x3FF921FB54400000)
static var PIO2_2: float = _f(0x3DD0B4611A600000)
static var PIO2_2T: float = _f(0x3BA3198A2E037073)
static var PIO2_3: float = _f(0x3BA3198A2E000000)
static var PIO2_3T: float = _f(0x397B839A252049C1)
static var S1: float = -_f(0x3FC5555555555549)
static var S2: float = _f(0x3F8111111110F8A6)
static var S3: float = -_f(0x3F2A01A019C161D5)
static var S4: float = _f(0x3EC71DE357B1FE7D)
static var S5: float = -_f(0x3E5AE5E68A2B9CEB)
static var S6: float = _f(0x3DE5D93A5ACFD57C)
static var C1: float = _f(0x3FA555555555554C)
static var C2: float = -_f(0x3F56C16C16C15177)
static var C3: float = _f(0x3EFA01A019CB1590)
static var C4: float = -_f(0x3E927E4F809C52AD)
static var C5: float = _f(0x3E21EE9EBDB4B1C4)
static var C6: float = -_f(0x3DA8FAE9BE8838D4)

static var ATANHI: PackedFloat64Array = PackedFloat64Array([_f(0x3FDDAC670561BB4F), _f(0x3FE921FB54442D18), _f(0x3FEF730BD281F69B), _f(0x3FF921FB54442D18)])
static var ATANLO: PackedFloat64Array = PackedFloat64Array([_f(0x3C7A2B7F222F65E2), _f(0x3C81A62633145C07), _f(0x3C7007887AF0CBBD), _f(0x3C91A62633145C07)])
static var AT0: float = _f(0x3FD555555555550D)
static var AT1: float = -_f(0x3FC999999998EBC4)
static var AT2: float = _f(0x3FC24924920083FF)
static var AT3: float = -_f(0x3FBC71C6FE231671)
static var AT4: float = _f(0x3FB745CDC54C206E)
static var AT5: float = -_f(0x3FB3B0F2AF749A6D)
static var AT6: float = _f(0x3FB10D66A0D03D51)
static var AT7: float = -_f(0x3FADDE2D52DEFD9A)
static var AT8: float = _f(0x3FA97B4B24760DEB)
static var AT9: float = -_f(0x3FA2B4442C6A6C2F)
static var AT10: float = _f(0x3F90AD3AE322DA11)
static var PI_: float = _f(0x400921FB54442D18)
static var PI_LO: float = _f(0x3CA1A62633145C07)
static var TWO66: float = _f(0x4410000000000000)
static var TWO60: float = _f(0x43B0000000000000)
static var TWOM29: float = _f(0x3E20000000000000)

## 2^k（k = -1074..1023）。添字は k + P2_OFF
const P2_OFF := 1074
static var _P2: PackedFloat64Array = _make_p2()
static func _make_p2() -> PackedFloat64Array:
	var bits := PackedInt64Array()
	bits.resize(1074 + 1024)
	for k in range(-1074, 1024):
		bits[k + P2_OFF] = (1 << (k + 1074)) if k < -1022 else ((k + 1023) << 52)
	return bits.to_byte_array().to_float64_array()

static func exp(x: float) -> float:
	if x != x: return x
	if x > EXP_HI: return INF
	if x < EXP_LO: return 0.0
	var dk: float = floor(x * INVLN2 + 0.5)
	var hi: float = x - dk * LN2HI
	var lo: float = dk * LN2LO
	var r: float = hi - lo
	var t: float = r * r
	var c: float = r - t * (P1 + t * (P2 + t * (P3 + t * (P4 + t * P5))))
	if dk == 0.0:
		return 1.0 - ((r * c) / (c - 2.0) - r)
	var y: float = 1.0 - ((lo - (r * c) / (2.0 - c)) - hi)
	var k: int = int(dk)
	if k > 1023: return (y * 2.0) * _P2[1023 + P2_OFF]
	if k < -1022: return (y * _P2[k + 1000 + P2_OFF]) * _P2[-1000 + P2_OFF]
	return y * _P2[k + P2_OFF]

static func log(x: float) -> float:
	if not (x > 0.0):
		return -INF if x == 0.0 else NAN
	if x == INF: return x
	var k: int = 0
	if x < MIN_NORMAL:
		x *= TWO54
		k = -54
	# Why not static の8バイトの箱を使い回す（前の作り）: 地形のスレッドと主スレッドが同時に log を呼ぶと、片方のビットがもう片方に混ざる
	var bb := PackedByteArray()
	bb.resize(8)
	bb.encode_double(0, x)
	var hx: int = bb.decode_s64(0) >> 32
	var ex: int = (hx >> 20) - 1023
	hx &= 0xfffff
	var i: int = (hx + 0x95f64) & 0x100000
	ex += i >> 20
	k += ex
	var f: float = x * _P2[P2_OFF - ex] - 1.0
	if ((hx + 2) & 0xfffff) < 3:
		if f == 0.0:
			if k == 0: return 0.0
			var dk0: float = float(k)
			return dk0 * LN2HI + dk0 * LN2LO
		var r0: float = f * f * (0.5 - THIRD * f)
		if k == 0: return f - r0
		var dk1: float = float(k)
		return dk1 * LN2HI - ((r0 - dk1 * LN2LO) - f)
	var s: float = f / (2.0 + f)
	var dk: float = float(k)
	var z: float = s * s
	var w: float = z * z
	var t1: float = w * (LG2 + w * (LG4 + w * LG6))
	var t2: float = z * (LG1 + w * (LG3 + w * (LG5 + w * LG7)))
	var r: float = t2 + t1
	if ((hx - 0x6147a) | (0x6b851 - hx)) > 0:
		var hfsq: float = 0.5 * f * f
		if k == 0: return f - (hfsq - s * (hfsq + r))
		return dk * LN2HI - ((hfsq - (s * (hfsq + r) + dk * LN2LO)) - f)
	if k == 0: return f - s * (f - r)
	return dk * LN2HI - ((s * (f - r) - dk * LN2LO) - f)

## 指数が整数（|y| ≤ 64）なら掛け算を重ねる（答えがちょうど表せる数なら、ちょうどその数。2^10 = 1024 など）。誤差は相対 1.5e-14 まで。
## ほかは exp(y・log x)。誤差は |y・log x| の1単位（ulp）ほど（答えが溢れない範囲で相対 2e-13 まで）。
## Why not いつも exp(y・log x): 整数の答えが 1023.9999… になり、int() で切ると1つ違う
## Why not 倍精度を2つ重ねた log（libm の pow の作り）: 線（相対 1e-12）に要らず、重さが2倍になる
static func pow(x: float, y: float) -> float:
	if y == 0.0 or x == 1.0: return 1.0
	if y == 1.0: return x
	if y == 2.0: return x * x
	if y == 0.5 and x > 0.0 and x < INF: return sqrt(x)
	if x != x or y != y: return NAN
	if floor(y) == y and absf(y) <= 64.0:
		var n: int = int(absf(y))
		var acc: float = 1.0
		var b: float = x
		while true:
			if n & 1: acc *= b
			n >>= 1
			if n == 0: break
			b *= b
		return 1.0 / acc if y < 0.0 else acc
	var neg: bool = false
	var ax: float = x
	if x < 0.0:
		if floor(y) != y: return NAN
		ax = -x
		neg = absf(y) < TWO54 and floor(y * 0.5) != y * 0.5
	var r: float
	if ax == 0.0:
		r = 0.0 if y > 0.0 else INF
	elif ax == INF:
		r = INF if y > 0.0 else 0.0
	else:
		r = DetMath.exp(y * DetMath.log(ax))
	return -r if neg else r

## |x| > π/4 の sin（shift 0）・cos（shift 1）: x = n・π/2 + (y0 + y1) に分けて、(n + shift) の象限で _ksin・_kcos を選ぶ。
## |x| < 2^20・π/2 で fdlibm と同じ精度（それより大きい x も答えは1つに決まるが、粗い）
## Why not 大きな x の Payne–Hanek: sim の角は 0〜2π と Box–Muller の 2π・u だけ
## Why not 余りを static の _ry0・_ry1 に返す（前の作り）: 地形のスレッドと主スレッドが同時に sin・cos を呼ぶと、片方の余りがもう片方に混ざった（map1b、R015 の Rhône の木）
static func _reduced(x: float, shift: int) -> float:
	var fn: float = floor(x * INVPIO2 + 0.5)
	var t: float = x - fn * PIO2_1
	var w: float = fn * PIO2_2
	var r: float = t - w
	w = fn * PIO2_2T - ((t - r) - w)
	t = r
	w = fn * PIO2_3
	r = t - w
	w = fn * PIO2_3T - ((t - r) - w)
	var y0: float = r - w
	var y1: float = (r - y0) - w
	var n: int = (int(fn) + shift) & 3
	if n == 0: return _ksin(y0, y1)
	if n == 1: return _kcos(y0, y1)
	if n == 2: return -_ksin(y0, y1)
	return -_kcos(y0, y1)

static func _ksin(x: float, y: float) -> float:
	var z: float = x * x
	var w: float = z * z
	var r: float = S2 + z * (S3 + z * S4) + z * w * (S5 + z * S6)
	var v: float = z * x
	return x - ((z * (0.5 * y - v * r) - y) - v * S1)

static func _kcos(x: float, y: float) -> float:
	var z: float = x * x
	var w: float = z * z
	var r: float = z * (C1 + z * (C2 + z * C3)) + w * w * (C4 + z * (C5 + z * C6))
	var hz: float = 0.5 * z
	w = 1.0 - hz
	return w + (((1.0 - w) - hz) + (z * r - x * y))

static func sin(x: float) -> float:
	var ax: float = absf(x)
	if ax <= PIO4:
		return x if ax < TWOM27 else _ksin(x, 0.0)
	if not (ax < INF): return NAN
	return _reduced(x, 0)

static func cos(x: float) -> float:
	var ax: float = absf(x)
	if ax <= PIO4:
		return 1.0 if ax < TWOM27 else _kcos(x, 0.0)
	if not (ax < INF): return NAN
	return _reduced(x, 1)

static func atan(x: float) -> float:
	if x != x: return x
	var ax: float = absf(x)
	var neg: bool = x < 0.0
	if ax >= TWO66:
		return ATANHI[3] + ATANLO[3] if x > 0.0 else -ATANHI[3] - ATANLO[3]
	var id: int = -1
	if ax < 0.4375:
		if ax < TWOM29: return x
	else:
		x = ax
		if ax < 1.1875:
			if ax < 0.6875:
				id = 0
				x = (2.0 * x - 1.0) / (2.0 + x)
			else:
				id = 1
				x = (x - 1.0) / (x + 1.0)
		elif ax < 2.4375:
			id = 2
			x = (x - 1.5) / (1.0 + 1.5 * x)
		else:
			id = 3
			x = -1.0 / x
	var z: float = x * x
	var w: float = z * z
	var s1: float = z * (AT0 + w * (AT2 + w * (AT4 + w * (AT6 + w * (AT8 + w * AT10)))))
	var s2: float = w * (AT1 + w * (AT3 + w * (AT5 + w * (AT7 + w * AT9))))
	if id < 0: return x - x * (s1 + s2)
	var zz: float = ATANHI[id] - ((x * (s1 + s2) - ATANLO[id]) - x)
	return -zz if neg else zz

static func atan2(y: float, x: float) -> float:
	if x != x or y != y: return x + y
	if x == 1.0: return DetMath.atan(y)
	var m: int = (2 if (x < 0.0 or (x == 0.0 and 1.0 / x < 0.0)) else 0) + (1 if (y < 0.0 or (y == 0.0 and 1.0 / y < 0.0)) else 0)
	if y == 0.0:
		if m < 2: return y
		return PI_ if m == 2 else -PI_
	if x == 0.0:
		return -ATANHI[3] - ATANLO[3] if y < 0.0 else ATANHI[3] + ATANLO[3]
	if x == INF or x == -INF:
		if y == INF or y == -INF:
			var q: float = ATANHI[1] + ATANLO[1]
			if m == 0: return q
			if m == 1: return -q
			if m == 2: return 3.0 * q
			return -3.0 * q
		if m < 2: return y * 0.0   # Why not -0.0 の字: GDScript の字の読みで +0.0 になる
		if m == 2: return PI_
		return -PI_
	if y == INF or y == -INF:
		return -ATANHI[3] - ATANLO[3] if y < 0.0 else ATANHI[3] + ATANLO[3]
	var ay: float = absf(y)
	var ax: float = absf(x)
	var z: float
	if ay > ax * TWO60:
		z = ATANHI[3] + 0.5 * PI_LO
	elif x < 0.0 and ay * TWO60 < ax:
		z = 0.0
	else:
		z = DetMath.atan(ay / ax)
	if m == 0: return z
	if m == 1: return -z
	if m == 2: return PI_ - (z - PI_LO)
	return (z - PI_LO) - PI_

static var PPND_A := PackedFloat64Array([_f(0x400B18D91E9EEF75), _f(0x4060A4888B1A436E), _f(0x409ECE5D2213C0CC), _f(0x40CAD1D8CD4EE71D), _f(0x40E66C3E869B752A), _f(0x40F06C1C55B78F20), _f(0x40E052D26B2E45E4), _f(0x40A39A296F7D925E)])
static var PPND_B := PackedFloat64Array([_f(0x3FF0000000000000), _f(0x4045281B386E1AB5), _f(0x4085797EFDC8B3F7), _f(0x40B512322E75C89F), _f(0x40D4B772D5D65266), _f(0x40E3317CAA64F4BE), _f(0x40DC0E457CB1AE76), _f(0x40B46A7ECA984B69)])
static var PPND_C := PackedFloat64Array([_f(0x3FF6C665FDE9526A), _f(0x4012857748CAB19B), _f(0x401713F71462256A), _f(0x400D2ECB1A3D02C4), _f(0x3FF453CC085375B2), _f(0x3FCEF2ABB9B85C37), _f(0x3F9744EB6C45EC67), _f(0x3F49615AC0B7ACE9)])
static var PPND_D := PackedFloat64Array([_f(0x3FF0000000000000), _f(0x40006CEFBB46A449), _f(0x3FFAD278E6526633), _f(0x3FE61292F23385C9), _f(0x3FC2F5123394F040), _f(0x3F8F207A7EAB17BF), _f(0x3F41F18CBFDF2728), _f(0x3E120D3F686439E4)])
static var PPND_E := PackedFloat64Array([_f(0x401AA1B1C13EE526), _f(0x4015DAEA6E875003), _f(0x3FFC8EA6461FA445), _f(0x3FD2FAD9315255CF), _f(0x3F9B2B41193B4EE7), _f(0x3F545C1908425345), _f(0x3EFC6EC6CC59E02A), _f(0x3E8AFB74D693BF93)])
static var PPND_F := PackedFloat64Array([_f(0x3FF0000000000000), _f(0x3FE331D34FC7D77F), _f(0x3FC186EB183443FB), _f(0x3F8E76F93215462A), _f(0x3F49C8BC979DC5D7), _f(0x3EF35C2C496374BF), _f(0x3E831446F740B9E0), _f(0x3CE269BFF1F8C190)])
static var PPND_Q: float = _f(0x3FDB333333333333)
static var PPND_R: float = _f(0x3FC71EB851EB851F)
static var PPND_S: float = _f(0x3FF999999999999A)
static var PPND_LO: float = _f(0x3C90000000000000)
static var PPND_HI: float = _f(0x3FEFFFFFFFFFFFFF)

static func _poly8(c: PackedFloat64Array, x: float) -> float:
	var r: float = c[7]
	for k: int in range(6, -1, -1):
		r = r * x + c[k]
	return r

## 正規分布の逆関数（Wichura 1988、AS 241 の PPND16）。使うのは上の log と sqrt だけ。p ≤ 0 は 2^-54、p ≥ 1 は 1 − 2^-53 と読む（鍵の u は
## 2^-53 の確率でちょうど 0）。相対誤差は 1e-15 未満（試験の表）
## Why not p をいつも [2^-54, 1 − 2^-53] に寄せる: 2^-54 より小さい確率（二項の裾など）の答えが −8.29 で止まる
## Why not Acklam の近似に Newton を1回: Newton には Φ（erfc）が要り、3つ目の関数とその双子が増える（M001 F7）
static func inv_normal(p: float) -> float:
	var pc: float = PPND_LO if p <= 0.0 else (PPND_HI if p >= 1.0 else p)
	var q: float = pc - 0.5
	if absf(q) <= PPND_Q:
		var r: float = PPND_R - q * q
		return q * _poly8(PPND_A, r) / _poly8(PPND_B, r)
	var t: float = pc if q < 0.0 else 1.0 - pc
	t = sqrt(-DetMath.log(t))
	var v: float
	if t <= 5.0:
		t -= PPND_S
		v = _poly8(PPND_C, t) / _poly8(PPND_D, t)
	else:
		t -= 5.0
		v = _poly8(PPND_E, t) / _poly8(PPND_F, t)
	return -v if q < 0.0 else v

## 正規分布（Box–Muller）。RandomNumberGenerator.randf は整数の PCG から作るので OS によらず同じ。引く数は2つ
## Why not rng.randfn: 中で OS の数学の庫の log・cos を使う
static func randfn(rng: RandomNumberGenerator, mean: float = 0.0, deviation: float = 1.0) -> float:
	var u1: float = rng.randf()
	var u2: float = rng.randf()
	if u1 <= 0.0: u1 = _P2[-32 + P2_OFF]
	return mean + deviation * (DetMath.cos(TAU * u2) * sqrt(-2.0 * DetMath.log(u1)))

## Vector2.angle_to の代わり（v から u への角、-π..π）
static func angle_to(v: Vector2, u: Vector2) -> float:
	return DetMath.atan2(v.x * u.y - v.y * u.x, v.x * u.x + v.y * u.y)

## Vector2.rotated の代わり
static func rotated(v: Vector2, a: float) -> Vector2:
	var s: float = DetMath.sin(a)
	var c: float = DetMath.cos(a)
	return Vector2(v.x * c - v.y * s, v.x * s + v.y * c)
