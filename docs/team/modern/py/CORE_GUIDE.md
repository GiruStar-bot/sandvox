# Writing a rule on the Python core (for Eくん; D476 (d))

The tiers' core now lives in `py/tiers/`. GDScript is frozen at T2.2c as the oracle of what is already built. From T2.3 on, a rule is
written in Python first, and **the pure path is the specification** of what is new. This page is how to write one so it stays
deterministic, platform-independent and checkable. The project's rules hold: declare before code, flags off by default. D477 (the
owner, 2026-11-03) changes three things:
- the inputs come from sources up to 2024-12, the run starts at 2025-01, and success is read against the real 2025;
- effective rules and numbers may be fitted to data up to 2024-12, labelled, and never to the 2025 test, whose list and values are
  sealed before the comparison;
- conservation and seeded determinism stay hard rules, as does the parity of the core's paths, while cell-level checks become
  diagnostics (reported, not gating).

## 1. The two paths

| path | file | what it is |
|---|---|---|
| pure | `py/tiers/month.py` | the line-by-line twin of tiers.gd's month and the place a new rule is first written: plain Python, the state as lists and typed `array`s |
| Numba | `py/tiers/month_nb.py` + `nbk.py` | the same month with the hot loops compiled; it must give the pure path's digest bit for bit |

Write the rule in `month.py` first. Port it to the Numba path only once its checks pass, and show the two digests equal (§5).

## 2. State access

- **The state is a `St`.** Each `tr_*` field of people.gd is an attribute of the same name. Packed int arrays are Python lists of
  int, tr_points' fields are typed `array`s ('d', 'f', 'i', 'q'), and dictionaries are dicts. Index it as tiers.gd does:
  `(g * AGE_SLOTS + sl) * NS + sb` for a cell, `g * 4 * NG + k * NG + gr` for T.
- **One writer per datum** (ISS_TIERED §13.8): a rule writes only the arrays it owns. A rate function (`h(state) → p`) writes
  nothing. Its effect is applied by the owner.
- A field whose kind is float32 is written through `_pt_set`, which rounds as Godot's PackedFloat32Array does.
- **New fields** go through `St` (and `tree()` / `field()`), so they enter the save and the digest. A field that is only a tally
  goes in `tr_margins`, which the digest leaves out.
- **No timing in the state** (the PM, from Eくん's T2s-fr finding): wall-clock values never enter a `tr_*` field, `tr_margins`
  included. Times go to `p.timing` (the Numba month's per-stage seconds), which is not a `tr_*` attribute: it is never saved or
  digested, and `run_month.py` prints it as the timing log. So a full-state hash of the core is deterministic with no exclusions.
  The oracle's `tr_margins["t22"]["usec*"]` is why its full state differs run to run.

## 3. Draws and math

- **Keyed draws only:** `keyed.u(seed_v, tag, a, b, c)`, `keyed.below(n, …)`, `keyed.normal(…)`. Never `random` or
  `numpy.random`. In a loop, take the tag's head once (`hd = keyed.head(seed_v, tag)`) and draw
  `float(keyed.h64(hd, a, b, c) >> 11) / keyed.TWO53`. In Numba it is `nb.u_from(np.uint64(hd), a, b, c)`. Key products (id × NS …)
  are Python ints, or int64 in Numba.
- **Samplers:** `prims.binomial`, `hypergeometric`, `hypergeometric_split`, `split_holds`, `largest_keyed`, `dep_round`,
  `systematic`, `cap_to`. Their Numba twins are in `nb.py`.
- **DetMath only:** `detmath.exp`, `log`, `pow`, `inv_normal`, `sin`, `cos` (`nb.exp`, `nb.log`, `nb.pow_`, `nb.inv_normal` in
  Numba). Never `math.exp/log/pow`, `np.exp/log/power` or `**` on floats: they are the platform's libm, which is what split the oracle
  across platforms (b93433a7). `+ − × ÷`, `math.sqrt`, `floor` and `ceil` are exact and allowed.
- **GDScript's semantics** where Python's differ (`py/tiers/gd.py`):
  - `idiv` / `imod` for integer `/` and `%` with a negative operand;
  - `gd_round` (half away from zero) in place of `round`;
  - `maxf`, `minf`, `clampi` and `clampf`, which keep Godot's operand on a tie;
  - `int(x)` truncates in both languages.

## 4. Sums, orders and containers

- **Float sums** run in one declared order: a loop, or `np.cumsum`. Never `np.sum`, `np.mean`, `math.fsum`, `@`, `np.dot` or any
  BLAS call on a value that reaches the state or a tally: pairwise and vector reductions change the last bits. Integer sums may use
  NumPy in any order, below 2⁵³ when they pass through a float.
- **Sorts** need a total order: give every sort key a unique last element, such as the index. Then any sort agrees with Godot's.
  A sort with ties is a bug.
- **Dicts** keep insertion order. If iteration order can change a result, say in the code why it cannot, or iterate sorted keys.
- **Narrow types** (CORE_LAYOUT_PLAN §2) are storage only: compute in int64, and a new narrowed field needs its overflow proof in
  that plan before its code.

## 5. Tests

- **The convention** is `py/tests/common.py`'s `Kit`: one `ok` / `FAIL` line per check and a final `RESULT {json}`, as test_kit.gd's.
  Checks are declared in ISS_CHECKS before their code. A test states *what* is right; the code states *how*.
- **Equality rows:**
  - `py/tests/run_month.py <dir> <months>` compares a run with the per-field hashes and tallies in `<dir>`. Up to T2.2c those are
    the GDScript oracle's, written by `tools/py/oracle_dump.gd`.
  - From T2.3 on they are the pure path's: the same script with `TIERS_NB=1` compares the Numba path with them.
  - A new rule lands with its pure digests recorded at months 1, 12 and 13 (the January turn), and the Numba port must reproduce
    them.
- **Known failures name the row and the read year:** an entry is `ROW@yN` (for example `T2s-dt@y1`; `@mN` for a monthly read). It
  excuses that row only at that year, so the same row failing at another year is a FAIL. An entry also carries its cause, its owner
  and its date, as the GDScript registry's do. Why not by row name alone (tools/test/known_failures.json, Eくん's note in TO_PM
  (112)): an entry registered for year 1 would also excuse the row's year-5 or year-10 FAIL. A Python test prints each check's label
  starting with its `ROW@yN`, so the runner matches the label exactly.
- **Windows:** the PM runs the rows on the owner's PC (Python 3.14.2, NumPy 2.4.1, numba 0.68.1). Any new dependency needs the
  owner's OK first.
- **Times and memory:** run alone; `run_month.py` prints each month's time, and `month_nb`'s `p.timing` gives the per-stage times (never saved or digested).

## 6. One package for the tiers and econ (proposed to Eくん; nothing moves until agreed)

| directory | holds | who |
|---|---|---|
| `py/core/` | what both layers share: `keyed.py`, `detmath.py`, `gd.py`, `prims.py`, `nb.py` (their Numba twins), and `digest.py` (the typed-tree codec, `Packed`, the per-field hash) taken out of `tiers/state.py` | Cpくん; a change here re-runs both layers' rows |
| `py/tiers/` | `month.py`, `month_nb.py`, `nbk.py`, `state.py` (St, fields, tree) | Cpくん |
| `py/econ/` | econ's pure twin of `sim/modern/econ/*.gd` first, its Numba path only if it is needed; its own `state.py` on `core/digest.py` | Eくん |
| `py/tests/` | one runner and one `Kit`; the files are named by layer (`test_t*`, `test_e*`) | each owner, for their own layer |

- **Why one `core/`, not a copy in each layer:** two copies of keyed or DetMath could drift by one bit, and the digests would part
  for a reason neither layer's rows can name.
- **The move is its own commit with no logic change.** After it, P0/P1 and P2 + P2c (13 months, both paths) must still be
  identical. It lands when no GDScript national run is going, so the rows can run alone.
- **Econ's digest** is a second digest beside the tiers', defined the same way (per-field SHA-256 over the canonical bytes, a month
  digest over the "name hex" lines). The oracle's side is a mode of `tools/py/oracle_dump.gd` or its own dump script, as Eくん
  prefers.
- **What I review on econ's core side:** draws only through `core/keyed`, math only through `core/detmath`, every float sum in a
  declared order (§4), sorts with a total order, narrow types only with their proof (CORE_LAYOUT_PLAN §2), no timing in the
  state, and the digest's bytes equal to the oracle's.
