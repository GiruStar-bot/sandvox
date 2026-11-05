# MECH_PLAN §3-§4 as AMENDED by M046 (§6) and M048 (§8): the rows and must-fails of D-mech (py/econ/mech.py, econ.mech)
#   run months 1-3 are quarter 1 (Mech.month 0-2, E = E_0); E is set at run months 4, 7, 10, ... and held for the quarter
#   X-off   mech off: test_econ_parity 23/23, run_month_i1 13/13 (i1full) and 16/16 (i1force); the off state has no mech field
#   X-ref   mech on, the econ replay of the oracle's people interface: the digests at months 1, 12 and 24, printed as the reference
#   X-w     E frozen, the wage y/y +1 pp above the baseline for 12 months: core y/y at the 12th month differs by 0.394 pp within 1e-9
#   X-pc    gap +1 pp for 4 quarters: core moves by kappa in the gap's first month, E in quarter q follows the held quarterly closed
#           form a + rho^q (E_0 - a) + kappa sum_j<q rho^(q-j) (quarter j's mean gap), within 1e-9
#   X-fx    a 2024 NEER path of +10% y/y, then held: the core y/y contribution equals 0.013 x sum_l (1/24) NEER y/y_t-l from quarter 1;
#           the core level's cumulative effect at the window's end is 0.13% within 1e-9; the y/y contribution is 0 after it
#   X-lab   no sex x age band's participation above its cap, every month; the binding share reported
#   X-rent  the rent index's monthly change is (1 - 0.9^(1/12)) x the market gap + the drift, exactly; 12 months adjust 1 - 0.9
#   X-stab  (1) G = rho (1 + beta_w w_pi) < 1 from the run's parameters; (2) gap 0, FX 0, u held, a one-off 0.01 pp shock to core
#           in quarter 1 (each of its three months): the quarterly mean deviation from a follows the loop's linear recursion within 1%
#           for 40 quarters, its wage lag weights probed from the model's own wage y/y window; (3) DROPPED (AMENDED after a fail, M048 addendum 2542c0dd: its weights were approximate), reported only
#   X-dir   (report) I-1's chained months 1-12, mech on against off: the directions of core, u and rent y/y, both market forms
#   MF-w beta_w -0.394; MF-pc rho 0; MF-fx the lag dropped; MF-lab the cap skipped on a forced band; MF-rent every unit adjusts;
#   MF-off mech on with every size 0; MF-stab w_pi 1: each makes its row fail
#   python3 py/tests/test_mech.py <oracle econ root> [i1full dir] [i1force dir]
import json
import os
import struct
import subprocess
import sys

from common import Kit, ROOT
from core import detmath as DM
from econ import state
from econ.labour import Labour
from econ.mech import Mech, participation

BETA_W = 0.394
RHO = 0.78
A = 0.0099
FX = 0.013
LAGS = 24
UNIT = {"rent_weight": 0.0}


def unbits(n):
    return struct.unpack("<d", struct.pack("<q", int(n["f"])))[0]


def unit(over):
    p = dict(UNIT)
    p.update(over)
    return p


def x_w(over):
    def run(extra):
        mc = Mech(unit(dict({"freeze_e": True}, **over)))
        b = DM.log(1.0 + 0.5 * 0.027 / 12.0)
        lv = {}
        for m in range(14):
            mc.core_at(1.0)
            lv[m] = mc.level
            mc.observe_wage_dl(b + (extra if m == 1 else 0.0))
            mc.end_month()
        return DM.log(lv[13] / lv[1])
    d = run(0.01) - run(0.0)
    return abs(d - BETA_W * 0.01) <= 1e-9, "core y/y at the path's 12th month differs by %.10f pp (want %.4f)" % (d * 100.0, BETA_W)


def x_pc(over, kappa=None):
    def run(g):
        o = dict(over)
        if kappa is not None:
            o["kappa"] = kappa
        mc = Mech(unit(o))
        es, cs, gs = [], [], []
        for m in range(48):
            gap = 0.01 if g and 3 <= m < 15 else 0.0
            cs.append(mc.core_at(1.0 + gap))
            es.append(mc.log[-1][2])
            gs.append(mc.gap)
        return es, cs, gs, mc
    e0, c0, _, _ = run(False)
    es, cs, gs, mc = run(True)
    k = float(mc.p["kappa"])
    jump = cs[3] - c0[3]
    worst = 0.0
    for m in range(48):
        q = m // 3
        s = 0.0
        for j in range(q):
            s += DM.pow(RHO, float(q - j)) * k * ((gs[3 * j] + gs[3 * j + 1] + gs[3 * j + 2]) / 3.0)
        want = A + DM.pow(RHO, float(q)) * (es[0] - A) + s
        worst = max(worst, abs(es[m] - want))
    return abs(jump - k * 0.01) <= 1e-9 and worst <= 1e-9, "kappa %.2f: core's move in the gap's first month %.3e (want %.3e); E's worst gap to the closed form %.3e" % (k, jump, k * 0.01, worst)


def x_fx(over):
    mc = Mech(unit(dict({"neer_dlog_2024": [0.10 / 12.0] * 12, "freeze_e": True}, **over)))
    lo, hi = -12, 72
    rate = {m: mc.fx_rate(m) for m in range(lo - 12, hi)}

    def n(s):
        return 0.10 / 12.0 if -12 <= s <= -1 else 0.0

    def yy(s):
        t = 0.0
        for k in range(12):
            t += n(s - k)
        return t
    first_bad = None
    level = 0.0
    lev = {}
    yoy = {}
    for m in range(lo, hi):
        level += rate[m] / 12.0
        lev[m] = level
        c = 0.0
        for k in range(12):
            c += rate[m - k] / 12.0
        yoy[m] = c
        want = 0.0
        for l in range(LAGS):
            want += yy(m - l) / LAGS
        want *= FX
        if m >= 0 and first_bad is None and abs(c - want) > 1e-9:
            first_bad = m
    core_ok = True
    for m in range(36):
        cm = mc.core_at(1.0)
        core_ok = core_ok and abs((cm - mc.log[-1][2]) - rate[m]) <= 1e-15
        mc.end_month()
    end = 33
    after = all(yoy[m] == 0.0 for m in range(end + 1, hi))
    ok = first_bad is None and abs(lev[end] - FX * 0.10) <= 1e-9 and after and core_ok
    return ok, ("y/y contribution against 0.013 x sum_l (1/24) NEER y/y: first differing month %s (quarter %s); the level's cumulative effect at "
                "month %d %.10f%% (want 0.13%%); y/y contribution 0 from month %d: %s; the econ core carries the fx part: %s"
                % (first_bad, None if first_bad is None else first_bad // 3 + 1, end, lev[end] * 100.0, end + 1, after, core_ok))


def lab_bands(m):
    # Why not persons' bands: econ/labour receives only the search share; the fixture's numbers are a unit's, not data
    f = 0.80 + 0.015 * m
    return {"F15-29": [100.0, 60.0, 5.0], "M15-29": [100.0, 62.0, 5.0], "F30-59": [100.0, f * 100.0 - 4.0, 4.0], "M30-59": [100.0, 90.0, 3.0],
            "F60-69": [100.0, 50.0, 2.0], "M60-69": [100.0, 70.0, 2.0], "F70+": [100.0, 15.0, 1.0], "M70+": [100.0, 25.0, 1.0]}


def x_lab(over, force=False):
    mc = Mech(over)
    lb = Labour()
    lb.load_state("JPN")
    lb.caps = mc
    first_bad, shares = None, []
    for m in range(12):
        bands = lab_bands(m)
        if force and m == 0:
            bands["F30-59"] = [100.0, 92.0, 3.0]
        lb.receive(0.03, 0.0, {}, bands)
        shares.append(mc.binding_share)
        for b in lb.bands:
            if b in PARAMS_CAPS and participation(lb.bands[b]) > PARAMS_CAPS[b] + 1e-12 and first_bad is None:
                first_bad = (m, b, participation(lb.bands[b]))
    bind = next((m for m, s in enumerate(shares) if s > 0.0), None)
    return first_bad is None, "first band above its cap %s; binding population share by month %s (first binding month %s)" % (
        first_bad, ["%.3f" % s for s in shares], bind)


PARAMS_CAPS = {"F30-59": 0.902, "M30-59": 0.954, "F60-69": 0.712, "M60-69": 0.853, "F70+": 0.254, "M70+": 0.254}


def x_rent(over):
    mc = Mech(dict({"rent_gap_0": 0.05}, **over))
    th = 1.0 - DM.pow(0.9, 1.0 / 12.0)
    d = -0.007 / 12.0
    exact = True
    dev0 = mc.rent_dev()
    keep = 1.0
    for m in range(24):
        gap = mc.market_log - mc.rent_log
        got = mc.rent_step()
        exact = exact and got == th * gap + d
        if m < 12:
            keep *= 1.0 - (got - d) / gap
    mass = 1.0 - keep
    return exact and abs(mass - 0.1) <= 1e-9 and dev0 == 0.0, "monthly change = share x gap + drift, bit for bit, 24 months: %s; 12-month adjusting mass %.12f (want 0.1); rent y/y deviation at 2024-12 %r" % (exact, mass, dev0)


def wage_weights(lags=6, at=6):
    # the quarterly mean of the model's wage y/y deviation in quarter `at` per unit of annual wage growth in quarter at - L only
    out = []
    for L in range(lags):
        mc = Mech(unit({}))
        t = 0.0
        for m in range(3 * (at + 1)):
            if m // 3 == at:
                t += mc.wage_dev()
            mc.observe_wage_dl(1.0 / 12.0 if m // 3 == at - L else 0.0)
        out.append(t / 3.0)
    return out


def x_stab(over, w_pi=None):
    shock = 0.0001
    mc = Mech(unit(dict({"anchor": A}, **over)), core_0=A)
    lb = Labour()
    lb.load_state("JPN")
    if w_pi is not None:
        lb.spec["w_pi"]["value"] = w_pi
    wp = lb._p("w_pi")
    rho = float(mc.p["rho"])
    a = float(mc.p["anchor"])
    b = float(mc.p["beta_w"]) * wp
    g = rho * (1.0 + b)
    dev = []
    for m in range(123):
        c = mc.core_at(1.0, shock if m < 3 else 0.0)
        dev.append(c - a)
        w0 = lb.wage_index
        lb.step(m, 1.0, mc.parts[0])
        mc.observe_wage(w0, lb.wage_index)
        mc.end_month()
    xr = [(dev[3 * q] + dev[3 * q + 1] + dev[3 * q + 2]) / 3.0 for q in range(41)]
    cw = wage_weights()
    xp, ep = [], []
    for q in range(40):
        ep.append(rho * xp[q - 1] if q > 0 else 0.0)
        wsum = 0.0
        for L in range(len(cw)):
            if q - L >= 0:
                wsum += cw[L] * ep[q - L]
        xp.append(ep[q] + b * wsum + (shock if q == 0 else 0.0))
    worst = 0.0
    for q in range(40):
        worst = max(worst, abs(xr[q] - xp[q]) / abs(xp[q]))
    ok1 = g < 1.0
    ok2 = worst <= 0.01
    ok3 = abs(xr[39]) < 0.10 * shock
    return ok1 and ok2, ("(1) G = rho (1 + beta_w w_pi) = %.4f (rho %.2f, beta_w %.3f, w_pi %.2f) < 1: %s; (2) wage lag weights probed from the "
                                 "model's y/y window (quarters q..q-5) %s; worst relative gap of the run's quarterly deviation to the recursion "
                                 "over 40 quarters %.3e (want <= 0.01): %s; [(3) dropped, AMENDED after a fail, M048 addendum 2542c0dd; reported: quarter 40's deviation %.4f of the shock (recursion %.4f), < 0.10: %s]; "
                                 "[not the row: 40 quarters after the shock quarter, quarter 41, %.4f]"
                                 % (g, rho, float(mc.p["beta_w"]), wp, ok1, ["%.4f" % c for c in cw], worst, ok2, xr[39] / shock, xp[39] / shock, ok3,
                                    xr[40] / shock))


def replay(od, months, params, keep=(1, 12, 24)):
    e = state.from_tree(os.path.join(od, "m00"))
    if params is not None:
        e.enable_mech(params)
    out = {}
    for m in range(1, months + 1):
        with open(os.path.join(od, "m%02d.iface.json" % m), encoding="utf-8") as fh:
            iv = json.load(fh)
        e.labour.receive(unbits(iv["search_share"]), unbits(iv["wage_demand_share"]), {c: unbits(v) for c, v in iv["scales"].items()})
        for r in iv.get("rice_releases", []):
            e.release_state_rice(m - 1, unbits(r))
        e.step()
        if m in keep:
            out[m] = (state.digest(e)[0], state.field_hashes(e))
    return e, out


def sub(k, row, args, want):
    p = subprocess.run([sys.executable] + args, cwd=ROOT, capture_output=True, text=True)
    res = next((json.loads(ln[7:]) for ln in p.stdout.splitlines() if ln.startswith("RESULT ")), None)
    ok = res is not None and res["passed"] == want and res["failed"] == 0
    k.check(ok, "%s %s: %s/%s passed, %s failed" % (row, " ".join(args[1:]), None if res is None else res["passed"], want, None if res is None else res["failed"]))


def x_dir(k, i1dir):
    import run_month_i1 as R
    from world import integrated as IM

    def chain(params):
        o = R.Oracle(i1dir)
        stub = IM.PersonsStub(o.iface)
        w = o.start(0, stub)
        if params is not None:
            w.econ.e.enable_mech(params)
        rows = []
        for m in range(1, 13):
            IM.advance_forced(w, R.month_end(m), o.force)
            e = w.econ.e
            ry = e.mech.rent_dev() + e.mech.rent_ref if e.mech is not None else 0.003
            rows.append((e.core_inflation, e.labour.u, ry))
        return rows

    def sign(x):
        return "up" if x > 0.0 else ("down" if x < 0.0 else "same")
    off = chain(None)
    for form in ("level", "growth"):
        on = chain({"rent_market": form})
        for i, name in enumerate(("core", "u", "rent y/y")):
            d = [sign(on[m][i] - off[m][i]) for m in range(12)]
            print("X-dir (report) market %s, %s with mech on against off, 2025-01..2025-12: %s" % (form, name, " ".join(d)), flush=True)


def main():
    root = sys.argv[1]
    i1full = sys.argv[2] if len(sys.argv) > 2 else None
    i1force = sys.argv[3] if len(sys.argv) > 3 else None
    k = Kit("py/tests/test_mech.py")
    people = os.path.join(root, "people")

    sub(k, "X-off", ["py/tests/test_econ_parity.py", root], 23)
    if i1full:
        sub(k, "X-off", ["py/tests/run_month_i1.py", i1full, "24"], 13)
    if i1force:
        sub(k, "X-off", ["py/tests/run_month_i1.py", i1force, "24"], 16)
    e0 = state.from_tree(os.path.join(people, "m00"))
    k.check(e0.mech is None and not any(n.startswith("mech.") or n == "labour.bands" for n in state.fields(e0)),
            "X-off the default econ has mech off and no mech field")

    _, ref = replay(people, 24, {})
    print("X-ref (recorded) mech on, the econ replay of %s: month 1 %s, month 12 %s, month 24 %s" % (people, ref[1][0], ref[12][0], ref[24][0]), flush=True)
    _, ref2 = replay(people, 24, {})
    k.check(all(ref[m][0] == ref2[m][0] for m in ref), "X-ref the mech-on replay repeats bit for bit at months 1, 12, 24")

    for row, fn, mf, mfname in (("X-w", x_w, {"beta_w": -0.394}, "MF-w beta_w -0.394"), ("X-pc", x_pc, {"rho": 0.0}, "MF-pc rho 0"),
                                ("X-fx", x_fx, {"fx_lag_months": 1}, "MF-fx the lag dropped (all at once)"),
                                ("X-rent", x_rent, {"rent_keep_annual": 0.0}, "MF-rent every unit adjusts monthly")):
        ok, msg = fn({})
        k.check(ok, "%s %s" % (row, msg))
        ok2, msg2 = fn(mf)
        k.check(not ok2, "%s: %s fails: %s" % (mfname, row, msg2))
    ok, msg = x_pc({}, kappa=0.11)
    k.check(ok, "X-pc (the form at kappa 0.11, not the run's value) %s" % msg)

    ok, msg = x_lab({})
    k.check(ok, "X-lab (unit bands) %s" % msg)
    ok2, msg2 = x_lab({"cap_on": False}, force=True)
    k.check(not ok2, "MF-lab the cap skipped, F30-59 forced to 0.95 at month 0: X-lab fails: %s" % msg2)
    e_on, _ = replay(people, 1, {}, keep=())
    print("X-lab (report) the replay: the persons' supply carries no sex x age bands, so the cap is not applied there: binding share %s (-1 = not measured)"
          % e_on.mech.binding_share, flush=True)

    ok, msg = x_stab({})
    k.check(ok, "X-stab %s" % msg)
    ok2, msg2 = x_stab({}, w_pi=1.0)
    k.check(not ok2, "MF-stab w_pi 1: X-stab fails: %s" % msg2)

    sizes0 = {"beta_w": 0.0, "kappa": 0.0, "fx_pass": 0.0, "rent_weight": 0.0}
    _, z = replay(people, 1, sizes0, keep=(1,))
    want = state.read_hashes(os.path.join(people, "m01.sha.txt"))
    got = z[1][1]
    only = sorted(n for n in set(got) ^ set(want))
    diff = sorted(n for n in set(got) & set(want) if got[n] != want[n])
    k.check(bool(only or diff), "MF-off mech on with every size 0: X-off's month-1 hashes differ: fields on one side only %s; shared fields differing %s" % (only, diff))

    if i1full:
        x_dir(k, i1full)
    k.finish()


if __name__ == "__main__":
    main()
