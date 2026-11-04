extends "res://tools/test/test_kit.gd"
## ISS tiered population T2.0, the primitives (ISS_TIERED_POPULATION.md §14, §13.1-§13.3; ISS_CHECKS.md DM-b, T2s-c, T2s-d's second
## half), declared before their code. The reference laws are computed here, apart from the code they check.
##   godot --headless --path . --script res://sim/modern/test_modern_t2_primitives.gd
## DM-b   the binomial draw: on the grid n 1..10^6 x p 10^-6..0.8, the sum of 10^5 keyed draws inside the exact Binomial(10^5 n, p)
##        interval at a 1% family rate (amended, M008); below n p q = 12 every draw is the exact law's quantile at its u (the inversion is
##        exact); at n p q >= 12 the total variation of the sampler's own law, read through binomial() itself (M008), against the exact
##        law <= 0.04; p above 1/2 read through n - X; the recorded bits at fixed (n, p, u) equal
## HG-b   the hypergeometric's normal branch at its switch (variance just above 12), K / N = 0.5 .. 10^-4: its own law, read through
##        hypergeometric() itself, against the exact pmf, TV <= 0.04 (M008)
## HG-a   the sequential conditional hypergeometric: no household-bundle gives more than it holds, the draws sum to d, and each
##        household-bundle's mean over 10^5 keyed draws within 4 SE of d n_h / N (the multivariate law's mean; amended, §R rule 4)
## T2s-c  (AMENDED, M025, TO_E 22:48) the keyed merge of the pair of least added variance w_i w_k (x_i - x_k)²: Σ masses unchanged
##        exactly; over 10^4 keyed merges of a fixed bundle, the mean of a test function (the mass-weighted share of points above 8 and the
##        mass-weighted mean of x^2) within 3 SE of its value before the merge
const TR = preload("res://sim/modern/people/tiers.gd")
const DM = preload("res://sim/api/det_math.gd")
const KEYED = preload("res://sim/earth_core/keyed.gd")
const DRAWS := 100000
const NS := [1, 3, 10, 30, 100, 1000, 10000, 100000, 1000000]
const PS := [1e-6, 1e-4, 1e-2, 0.1, 0.3, 0.5, 0.8]
const TV_TOL := 0.04
const SW_V := [8.0, 9.0, 10.0, 11.0, 11.99, 12.0, 12.5, 13.0]   # the switch cells' n p q (and the hypergeometric's variance), V108
const FAMILY_ALPHA := 0.01   # the family false-alarm rate of DM-b's mean row, declared before its run (§R rule 5)
## (n, p, u, draw), recorded at T2.0's first build and never edited after, as DM-n's bits
const BITS := [[1, 0.5, 0.3, 0], [10, 0.1, 0.95, 3], [100, 0.3, 0.5, 30], [1000, 0.01, 0.99, 18], [1000000, 1e-06, 0.7, 1], [1000000, 0.5, 0.123, 499420], [50, 0.8, 0.42, 40], [30, 0.5, 0.999999, 27], [200, 0.06, 0.0001, 2], [5000, 0.002, 0.5, 10]]


func _init() -> void:
	_binomial()
	_hypergeometric()
	_hg_switch()
	_merge()
	finish()


## The exact log pmf of the binomial (a Lanczos log-gamma, g = 7, nine terms: the reference, not the code under test)
func _lgamma(x: float) -> float:
	var c: Array = [0.99999999999980993, 676.5203681218851, -1259.1392167224028, 771.32342877765313, -176.61502916214059,
		12.507343278686905, -0.13857109526572012, 9.9843695780195716e-6, 1.5056327351493116e-7]
	if x < 0.5:
		return log(PI / sin(PI * x)) - _lgamma(1.0 - x)
	var z: float = x - 1.0
	var a: float = c[0]
	var t: float = z + 7.5
	for i: int in range(1, 9):
		a += float(c[i]) / (z + float(i))
	return 0.5 * log(2.0 * PI) + (z + 0.5) * log(t) - t + log(a)


func _log_pmf(n: int, p: float, k: int) -> float:
	return _lgamma(n + 1.0) - _lgamma(k + 1.0) - _lgamma(n - k + 1.0) + k * log(p) + (n - k) * log(1.0 - p)


func _binomial() -> void:
	var bad_mean: int = 0
	var bad_exact: int = 0
	var bad_tv: int = 0
	var txt: String = ""
	for cell: Array in _cells():
		if true:
			var n: int = int(cell[0])
			var p: float = float(cell[1])
			var q: float = 1.0 - p
			var sum: float = 0.0
			var exact_ok: bool = true
			for j: int in DRAWS:
				var u: float = KEYED.u(1, "dm_b", n, int(p * 1e9), j)
				var x: int = TR.binomial(n, p, u)
				sum += x
				if n * p * q < TR.BINOM_SWITCH and j < 2000 and x != _quantile(n, p, u):
					exact_ok = false
			var iv: Array = _interval(n * DRAWS, p, FAMILY_ALPHA / float(_cells().size()))
			if sum < float(iv[0]) or sum > float(iv[1]):
				bad_mean += 1
			if n * p * q < TR.BINOM_SWITCH:
				if not exact_ok:
					bad_exact += 1
			else:
				var tv: float = _tv(n, p)
				if tv > TV_TOL:
					bad_tv += 1
				txt += " (%d, %s) TV %.4f;" % [n, str(p), tv]
	check(bad_mean == 0 and bad_exact == 0 and bad_tv == 0, "DM-b (AMENDED, M008, V108) the binomial draw over %d cells (the grid and the switch cells) x %d keyed u: sums outside the exact Binomial(10^5 n, p) interval at a 1%% family rate %d; cells below n p q = 12 off the exact quantile %d; cells at n p q >= 12 with total variation above %.2f %d:%s" % [_cells().size(), DRAWS, bad_mean, bad_exact, TV_TOL, bad_tv, txt])
	var bad_bits: int = 0
	for b: Array in BITS:
		if TR.binomial(int(b[0]), float(b[1]), float(b[2])) != int(b[3]):
			bad_bits += 1
	check(not BITS.is_empty() and bad_bits == 0, "DM-b recorded bits: %d of %d differ" % [bad_bits, BITS.size()])


## The grid's cells and the switch cells (V108): n p q at 8 .. 13 around the switch for p = 10^-4, 0.01, 0.5 and 0.8
func _cells() -> Array:
	var out: Array = []
	for n: int in NS:
		for p: float in PS:
			out.append([n, p])
	for v: float in SW_V:
		for p2: float in [1e-4, 0.01, 0.5, 0.8]:
			out.append([int(ceil(v / (p2 * (1.0 - p2)))), p2])
	return out


## The exact law's quantile at u: the least k with F(k) >= u, by the pmf in log space summed in index order
func _quantile(n: int, p: float, u: float) -> int:
	var acc: float = 0.0
	for k: int in n + 1:
		acc += exp(_log_pmf(n, p, k))
		if acc >= u:
			return k
	return n


## The sampler's own law at n p q >= 12 against the exact law, read through the code (M008): P(X <= k) is the least u at which
## binomial(n, p, u) exceeds k, found by bisection on u
func _tv(n: int, p: float) -> float:
	var mu: float = n * p
	var sd: float = sqrt(n * p * (1.0 - p))
	var lo: int = maxi(0, int(floor(mu - 9.0 * sd)))
	var hi: int = mini(n, int(ceil(mu + 9.0 * sd)))
	var tv: float = 0.0
	var g_prev: float = 0.0 if lo == 0 else _boundary(func(u: float) -> int: return TR.binomial(n, p, u), lo - 1)
	var e_in: float = 0.0
	for k: int in range(lo, hi + 1):
		var g: float = 1.0 if k == n else _boundary(func(u: float) -> int: return TR.binomial(n, p, u), k)
		var e: float = exp(_log_pmf(n, p, k))
		e_in += e
		tv += absf((g - g_prev) - e)
		g_prev = g
	tv += absf(1.0 - g_prev) + absf(1.0 - e_in)
	return 0.5 * tv


## The least u in [0, 1) at which draw(u) exceeds k (the sampler's CDF at k), by bisection: the draws are non-decreasing in u
func _boundary(draw: Callable, k: int) -> float:
	var a: float = 0.0
	var b: float = 1.0
	for it: int in 60:
		var m: float = 0.5 * (a + b)
		if int(draw.call(m)) <= k:
			a = m
		else:
			b = m
	return 0.5 * (a + b)


## The two-sided interval of a Binomial(m, p) sum at level a: exact by the pmf (log space) below a variance of 10^4, the normal's
## quantiles above (the normal's error there is far below a's scale)
func _interval(m: int, p: float, a: float) -> Array:
	var mu: float = float(m) * p
	var v: float = mu * (1.0 - p)
	if v >= 1e4:
		var z: float = DM.inv_normal(1.0 - 0.5 * a)
		return [mu - z * sqrt(v) - 1.0, mu + z * sqrt(v) + 1.0]
	var lo: int = maxi(0, int(floor(mu - 12.0 * sqrt(v) - 20.0)))
	var hi: int = mini(m, int(ceil(mu + 12.0 * sqrt(v) + 20.0)))
	var acc: float = 0.0
	var low: int = lo
	var up: int = hi
	var found_low: bool = false
	for k: int in range(lo, hi + 1):
		acc += exp(_log_pmf(m, p, k))
		if not found_low and acc > 0.5 * a:
			low = k
			found_low = true
		if acc >= 1.0 - 0.5 * a:
			up = k
			break
	return [low, up]


func _hypergeometric() -> void:
	var holds := PackedInt64Array([3, 0, 17, 250, 1, 40, 9, 1200])
	var big_n: int = 0
	for h: int in holds:
		big_n += h
	var bad: int = 0
	var sums := PackedFloat64Array()
	sums.resize(holds.size())
	var reps: int = 100000
	for d: int in [1, 7, 300, big_n]:
		sums.fill(0.0)
		for r: int in reps:
			var x: PackedInt64Array = TR.hypergeometric_split(holds, d, 1, "hg_a", d * 100000 + r)
			var tot: int = 0
			for h2: int in holds.size():
				if x[h2] > holds[h2] or x[h2] < 0:
					bad += 1
				tot += x[h2]
				sums[h2] += float(x[h2])
			if tot != d:
				bad += 1
		for h3: int in holds.size():
			var m: float = sums[h3] / reps
			var want: float = float(d) * float(holds[h3]) / float(big_n)
			var var_x: float = float(d) * float(holds[h3]) / big_n * (1.0 - float(holds[h3]) / big_n) * float(big_n - d) / maxf(1.0, big_n - 1.0)
			if absf(m - want) > 4.0 * sqrt(var_x / reps) + 1e-12:
				bad += 1
	check(bad == 0, "HG-a (AMENDED, §R rule 4) the sequential conditional hypergeometric over d = 1, 7, 300 and all of N = %d, %d keyed draws each: draws above a holding, below 0 or not summing to d, and means beyond 4 SE: %d" % [big_n, reps, bad])


func _hg_switch() -> void:
	var n: int = 1000000
	var bad: int = 0
	var bad_exact: int = 0
	var txt: String = ""
	var cells: Array = []
	for frac: float in [0.5, 0.1, 0.01, 1e-3, 1e-4]:
		cells.append([frac, TR.BINOM_SWITCH])
	for v: float in SW_V:
		for frac2: float in [1e-4, 0.01, 0.5]:
			cells.append([frac2, v])
	for c: Array in cells:
		var frac: float = float(c[0])
		var target: float = float(c[1])
		var k: int = int(round(frac * n))
		var d: int = _hg_d(n, k, target)
		var var_x: float = _hg_var(n, k, d)
		if var_x < TR.BINOM_SWITCH:
			for j2: int in 2000:
				var u: float = KEYED.u(1, "hg_b", d, k, j2)
				if TR.hypergeometric(n, k, d, u) != _hg_quantile(n, k, d, u):
					bad_exact += 1
					break
			continue
		var mean: float = float(d) * k / n
		var sd: float = sqrt(var_x)
		var lo: int = maxi(0, int(floor(mean - 9.0 * sd)))
		var hi: int = mini(mini(d, k), int(ceil(mean + 9.0 * sd)))
		var g_prev: float = 0.0 if lo == 0 else _boundary(func(u: float) -> int: return TR.hypergeometric(n, k, d, u), lo - 1)
		var tv: float = 0.0
		var e_in: float = 0.0
		for x: int in range(lo, hi + 1):
			var g: float = _boundary(func(u: float) -> int: return TR.hypergeometric(n, k, d, u), x)
			var e: float = exp(_hg_log_pmf(n, k, d, x))
			e_in += e
			tv += absf((g - g_prev) - e)
			g_prev = g
		tv += absf(1.0 - g_prev) + absf(1.0 - e_in)
		tv *= 0.5
		if tv > TV_TOL:
			bad += 1
		txt += " K/N %s var %.2f TV %.4f;" % [str(frac), var_x, tv]
	check(bad == 0 and bad_exact == 0, "HG-b (V108) the hypergeometric around its switch (N 10^6, %d cells): below the switch, cells off the exact quantile %d; at and above it, cells with TV above %.2f %d:%s" % [cells.size(), bad_exact, TV_TOL, bad, txt])


## The least d whose variance reaches the target
func _hg_d(n: int, k: int, target: float) -> int:
	var lo: int = 1
	var hi: int = n / 2
	while lo < hi:
		var m: int = (lo + hi) / 2
		if _hg_var(n, k, m) >= target:
			hi = m
		else:
			lo = m + 1
	return lo


func _hg_log_pmf(n: int, k: int, d: int, x: int) -> float:
	return _lgamma(k + 1.0) - _lgamma(x + 1.0) - _lgamma(k - x + 1.0) + _lgamma(n - k + 1.0) - _lgamma(d - x + 1.0) - _lgamma(n - k - d + x + 1.0) - (_lgamma(n + 1.0) - _lgamma(d + 1.0) - _lgamma(n - d + 1.0))


func _hg_quantile(n: int, k: int, d: int, u: float) -> int:
	var acc: float = 0.0
	for x: int in mini(d, k) + 1:
		acc += exp(_hg_log_pmf(n, k, d, x))
		if acc >= u:
			return x
	return mini(d, k)


func _hg_var(n: int, k: int, d: int) -> float:
	return float(d) * k / n * (1.0 - float(k) / n) * float(n - d) / float(n - 1)


func _merge() -> void:
	var w := PackedInt64Array([5, 2, 900, 3, 40, 2, 77])
	var x := PackedFloat64Array([1.0, 9.0, 3.0, 12.0, 0.5, 7.0, 4.0])
	var f0: Array = _fns(w, x)
	var reps: int = 10000
	var s := PackedFloat64Array([0, 0])
	var s2 := PackedFloat64Array([0, 0])
	var bad_mass: int = 0
	for r: int in reps:
		var out: Array = TR.merge_least(w, x, 1, "t2s_c", r)
		var w2: PackedInt64Array = out[0]
		var tot: int = 0
		for m: int in w2:
			tot += m
		if tot != 1029 or w2.size() != w.size() - 1:
			bad_mass += 1
		var f: Array = _fns(w2, out[1])
		for k: int in 2:
			s[k] += float(f[k])
			s2[k] += float(f[k]) * float(f[k])
	var txt: String = ""
	var bad: int = 0
	for k2: int in 2:
		var mean: float = s[k2] / reps
		var sd: float = sqrt(maxf(0.0, s2[k2] / reps - mean * mean))
		if absf(mean - float(f0[k2])) > 3.0 * sd / sqrt(reps) + 1e-12:
			bad += 1
		txt += " %.5f against %.5f (3 SE %.5f);" % [mean, float(f0[k2]), 3.0 * sd / sqrt(reps)]
	check(bad_mass == 0 and bad == 0, "T2s-c (AMENDED, M025) the keyed merge of the least-added-variance pair over %d merges: masses off %d; the test functions (share above 8; mean of x^2):%s" % [reps, bad_mass, txt])


func _fns(w: PackedInt64Array, x: PackedFloat64Array) -> Array:
	var tw: float = 0.0
	var above: float = 0.0
	var sq: float = 0.0
	for i: int in w.size():
		tw += float(w[i])
		above += float(w[i]) if x[i] > 8.0 else 0.0
		sq += float(w[i]) * x[i] * x[i]
	return [above / tw, sq / tw]
