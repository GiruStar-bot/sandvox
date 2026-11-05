# The world layer's rows (WORLD_PORT_PLAN §5) against an oracle run of tools/py/oracle_dump_world.gd:
#   python py/tests/run_world.py <oracle run dir> [ROW]
#     W0-s, W1 / W2 (the per-field hashes at every day the oracle wrote), W2-i (enforcement on the replayed stocks), W-c (conservation)
#   env: WORLD_SAVE_AT=40,365,400 (W1-r / W2-r: the Python world saved and restored there), WORLD_NUDGE=31 (W-mf), WORLD_NUDGE_FOOD=3
#   (W-mf2), WORLD_LEAK=50 (W-c-mf2), WORLD_LEAK_F=31 (W-c-mf3), WORLD_BASE=<the no-case run's dir> (W2-p's drought); with no oracle dir (WORLD_YEAR, WORLD_DAYS, WORLD_PARAMS) the Python-only
#   rows run against the Python's own straight run
import json
import math
import os
import sys
import time

from common import Kit
from world import actors as MA
from world import canon as CANON
from world import world as WM
from world import ledger
from world.gdtypes import dec, load_state, sha, field_hashes, read_hashes, round_trip, day_digest, F64

U = 2.0 ** -53


def first_diff(a, b, path=""):
    if type(a) != type(b) and not (isinstance(a, list) and isinstance(b, list)):
        return "%s: type %s vs %s" % (path, type(a).__name__, type(b).__name__)
    if isinstance(a, dict):
        if set(a) != set(b):
            return "%s: keys only python %s, only oracle %s" % (path, sorted(set(a) - set(b), key=str)[:5], sorted(set(b) - set(a), key=str)[:5])
        for k in sorted(a, key=str):
            r = first_diff(a[k], b[k], "%s.%s" % (path, k))
            if r:
                return r
        return ""
    if isinstance(a, list):
        if len(a) != len(b) or type(a) != type(b):
            return "%s: %s len %d vs %s len %d" % (path, type(a).__name__, len(a), type(b).__name__, len(b))
        for i in range(len(a)):
            r = first_diff(a[i], b[i], "%s[%d]" % (path, i))
            if r:
                return r
        return ""
    if isinstance(a, float):
        return "" if (a == b and math.copysign(1, a) == math.copysign(1, b)) or (a != a and b != b) else "%s: %r vs %r" % (path, a, b)
    return "" if a == b else "%s: %r vs %r" % (path, a, b)


class Conservation:
    # W-c (AMENDED A6, WORLD_PORT_PLAN §5): the shadow ledger of world/ledger.py over every stock the world posts to
    #   W-c-x exact: per entity, the link postings it received less those it sent equal its signed inflow in the links' shadows, and per entity with a status file the persons' double
    #     entry (cells + deaths − births posted − migration posted − the start) is 0 in rationals
    #   W-c-f per stock: |float − shadow| ≤ (1 + 2u)·B, B the stock's accumulated per-update bound
    #   reported, not gated: the frozen model's own float gap across links (a supplier's give against the sum of what it posted)
    FIELD = ("storage", "chips", "servers", "water_l", "storage_cap", "dc_it", "fab_cap")
    DERIVED = ("pop_total", "share_65plus", "debt_to_gdp", "defence_share_gdp", "physicians_per_100k")

    def __init__(self, w):
        self.L = ledger.Ledger()
        ledger.ACTIVE = self.L
        self.fails = []
        self.worst = 0.0
        self.gap_max = 0.0
        self.days = 0
        self.start_pop = {}
        self.attach(w)

    def attach(self, w):
        self.w = w
        L = self.L
        f = w.field
        for a in self.FIELD:
            for e, v in enumerate(getattr(f, a)):
                if (a, e) not in L.sh:
                    L.start((a, e), v)
        for i, v in enumerate(f.supply_built):
            L.sh.get(("supply_built", i)) is None and L.start(("supply_built", i), v)
        for i, v in enumerate(f.link_cap):
            L.sh.get(("link_cap", i)) is None and L.start(("link_cap", i), v)
        for i, v in enumerate(f.input_stock):
            L.sh.get(("input_stock", i)) is None and L.start(("input_stock", i), v)
        st = w.status
        for k in st.entities:
            if k in self.start_pop:
                continue
            self.start_pop[k] = sum(ledger.Fraction(v) for v in st.cohort[k])
            for i, v in enumerate(st.cohort[k]):
                L.start(("co", k, i), v)
            for acc in ("deaths", "born", "migrated"):
                L.start((acc, k), 0.0)
            ids = ["gov_debt_total", "ordinary_jgb", "niip", "external_assets", "foreign_residents"] + list(st.trend_day[k])
            for id_ in ids:
                if id_ in st.ind[k] and id_ not in self.DERIVED:
                    L.start(("ind", k, id_), st.ind[k][id_])

    def read(self, key):
        w = self.w
        f = w.field
        n = key[0]
        if n == "link_flow":
            return f.link_flow[key[1]]
        if n == "bal":
            return f._bal[key[1]]
        if n == "short":
            return f.unserved[key[1]]
        if n == "co":
            return w.status.cohort[key[1]][key[2]]
        if n == "ind":
            return w.status.ind[key[1]].get(key[2])
        if n in ("deaths", "born", "migrated"):
            return None
        return getattr(f, n)[key[1]]

    def before(self, w):
        self.L.gap = {}
        self.L.linkin = {}

    def after(self, w):
        self.days += 1
        bad, worst = self.L.check(self.read)
        self.worst = max(self.worst, worst)
        for b in bad[:3]:
            self.fails.append("W-c-f day %d %s" % (w.field.day, b))
        f = w.field
        inflow = {}
        for l in range(len(f.link_a)):
            x = self.L.sh[("link_flow", l)]
            inflow[f.link_b[l]] = inflow.get(f.link_b[l], 0) + x
            inflow[f.link_a[l]] = inflow.get(f.link_a[l], 0) - x
        for o, posted in self.L.linkin.items():
            if posted != inflow.get(o, 0):
                self.fails.append("W-c-x day %d entity %d: link postings %s, link flows %s" % (f.day, o, float(posted), float(inflow.get(o, 0))))
        for a, g in self.L.gap.items():
            self.gap_max = max(self.gap_max, abs(float(g)))
        L = self.L
        for k in w.status.entities:
            tot = sum(L.sh[("co", k, i)] for i in range(len(w.status.cohort[k])))
            r = tot + L.sh[("deaths", k)] - L.sh[("born", k)] - L.sh[("migrated", k)] - self.start_pop[k]
            if r != 0:
                self.fails.append("W-c-x day %d %s: the persons' double entry leaves %r" % (f.day, k, float(r)))


def sum_seq(xs):
    s = 0.0
    for x in xs:
        s += x
    return s


def main():
    d = sys.argv[1] if len(sys.argv) > 1 and os.path.isdir(sys.argv[1]) else ""
    kit = Kit("py/tests/run_world.py")
    iface = None
    if d and os.path.exists(os.path.join(d, "iface.json")):
        iface = WM.load_iface(os.path.join(d, "iface.json"))
        year = int(iface["year"])
        days = int(iface["days"])
        params = dec(iface["params"])
    else:
        year = int(os.environ.get("WORLD_YEAR", "2022"))
        days = int(os.environ.get("WORLD_DAYS", "430"))
        params = CANON.parse(os.environ.get("WORLD_PARAMS", '{"compute_growth": 0.15}'))
        params.setdefault("view_salt", "0123456789abcdef0123456789abcdef")
    cases = list(iface.get("cases", [])) if iface else []
    save_at = [int(x) for x in os.environ.get("WORLD_SAVE_AT", "").split(",") if x]
    nudge = int(os.environ.get("WORLD_NUDGE", "-1"))
    leak = int(os.environ.get("WORLD_LEAK", "-1"))
    leak_f = int(os.environ.get("WORLD_LEAK_F", "-1"))
    WM.NUDGE_FOOD[0] = int(os.environ.get("WORLD_NUDGE_FOOD", "-1"))
    t0 = time.perf_counter()
    w = WM.World()
    err = w.create(year, params, iface)
    kit.check(err == "", "create %d: %s (%.1f s)" % (year, err or "ok", time.perf_counter() - t0))
    if err:
        kit.finish()
    days_checked = sorted(int(n[1:5]) for n in os.listdir(d) if n.endswith(".sha.txt")) if d else []
    own = {}
    cons = Conservation(w)
    first_bad = None

    def compare(day):
        nonlocal first_bad
        hs = field_hashes(w.tree())
        if not d:
            own[day] = hs
            return
        want = read_hashes(os.path.join(d, "d%04d.sha.txt" % day))
        bad = [n for n in sorted(set(want) | set(hs)) if hs.get(n) != want.get(n)]
        extra = ""
        if bad and os.path.isdir(os.path.join(d, "d%04d" % day)):
            ref = load_state(os.path.join(d, "d%04d" % day))
            mine = w.tree()
            extra = "; " + "; ".join(first_diff(mine.get(n), ref.get(n), n) for n in bad[:4])
        row = "W0-s" if day == 0 else ("W1" if year == 2022 else "W2")
        if leak >= 0 or leak_f >= 0:
            return
        if nudge >= 0:
            if day == nudge:
                kit.check(bool(bad) and bad[0] == "field.supply_built", "W-mf day %d: the nudged field differs first: %s" % (day, bad[:4]))
            return
        if WM.NUDGE_FOOD[0] >= 0:
            if bad and first_bad is None:
                first_bad = day
                kit.check(day == MA.MONTH_ENDS[WM.NUDGE_FOOD[0] - 1] and "public" in bad,
                          "W-mf2: the first differing day is %d (month %d's end is %d), fields %s" % (day, WM.NUDGE_FOOD[0], MA.MONTH_ENDS[WM.NUDGE_FOOD[0] - 1], bad[:6]))
            return
        kit.check(not bad, "%s day %d: digest %s, fields differing %d %s%s" % (row, day, day_digest(hs)[:16], len(bad), bad[:6], extra))
        if bad and first_bad is None:
            first_bad = day

    compare(0)
    for day in range(1, days + 1):
        cons.before(w)
        w.advance_to(day)
        cons.after(w)
        if day == leak and w.status.entities:
            k0 = w.status.entities[0]
            w.status.cohort[k0][80] += 1.0
            cons.L.add(("co", k0, 80), 1.0, w.status.cohort[k0][80])
        if day == leak_f:
            e0 = w.data.index_of("JPN")
            w.field.servers[e0] += 1.0
            cons.L.flt[("servers", e0)] = w.field.servers[e0]
        if day == 40 and "release" in cases:
            w.status.set_lever("JPN", "rice_stock_release", 100.0)
        if day == nudge:
            w.field.supply_built[0] = math.nextafter(w.field.supply_built[0], 1e300)
        if day in days_checked or (not d and (MA.is_month_end(day) or day == days)):
            compare(day)
            if first_bad is not None and nudge < 0 and WM.NUDGE_FOOD[0] < 0:
                break
        for vk in ("jpn", "test_b"):
            vp = os.path.join(d, "view_%s_d%04d.json" % (vk, day)) if d else ""
            if vp and os.path.exists(vp) and nudge < 0 and WM.NUDGE_FOOD[0] < 0:
                with open(vp, encoding="utf-8") as f:
                    ref = json.load(f)
                v = w.make_view(vk)
                obs = v.observe(w, w.data.index_of("JPN"))
                same = sha(obs) == ref["sha"]
                kit.check(same, "W-v %s day %d: the observation of JPN equals the oracle's%s" % (vk, day, "" if same else "; " + first_diff(obs, dec(ref["obs"]), "obs")))
        if day in save_at:
            st = round_trip(w.to_dict())
            w2 = WM.World.from_dict(st, iface)
            kit.check(w2.error == "" and field_hashes(w2.tree()) == field_hashes(w.tree()), "W%s-r day %d: the restored world's tree equals the saved one" % ("1" if year == 2022 else "2", day))
            w = w2
            cons.attach(w)
        if day % 100 == 0:
            print("day %d %.1f s" % (day, time.perf_counter() - t0), flush=True)
    if cases:
        ev = w.enforcement.events if w.enforcement is not None else []
        n_late = sum(1 for e in ev if e["kind"] == "late_charge")
        n_proc = sum(1 for e in ev if e["kind"] == "procedure_opened")
        rel = [r for r in w.chronicle.rows if r["kind"] == "release"]
        moved = False
        if "drought" in cases and os.environ.get("WORLD_BASE"):
            base = WM.load_iface(os.path.join(os.environ["WORLD_BASE"], "iface.json"))
            moved = any(a["food_price_yoy"] != b["food_price_yoy"] for a, b in zip(iface["month"][12:], base["month"][12:]))
        want = {"cost": n_late > 0 and n_proc > 0, "release": len(rel) > 0, "drought": moved}
        kit.check(all(want[c] for c in cases), "W2-p (AMENDED B1) the declared cases %s ran their paths: %d late charges, %d procedures opened, %d releases (rice %s t)"
                  % (cases, n_late, n_proc, len(rel), [r["facts"]["rice_t"] for r in rel][:3]))
    if w.econ is not None:
        kit.check(not w.econ.mismatch, "W2-i: enforcement on the replayed stocks equals the oracle's after-rows every month: %d differ %s" % (len(w.econ.mismatch), w.econ.mismatch[:2]))
    xf = [x for x in cons.fails if x.startswith("W-c-x")]
    ff = [x for x in cons.fails if x.startswith("W-c-f")]
    if leak >= 0 or nudge >= 0 or leak_f >= 0:
        if leak_f >= 0:
            e0 = w.data.index_of("JPN")
            hit = [x for x in ff if ("day %d " % (leak_f + 1)) in x and "('servers', %d)" % e0 in x and "differs from the last posting" not in x]
            kit.check(bool(hit), "W-c-mf3: 1 MW of JPN's servers moved at day %d as if posted, the shadow not, fails W-c-f at the next check and names it: %s" % (leak_f, hit[:1]))
        if leak >= 0:
            kit.check(any("double entry" in x and ("day %d " % (leak + 1)) in x for x in xf), "W-c-mf2: one person added to a cell with no counterpart at day %d breaks W-c-x at the next check: %s" % (leak, xf[:1]))
        if nudge >= 0:
            kit.check(any("supply_built" in x and ("day %d " % (nudge + 1)) in x for x in ff), "W-c-mf: supply_built[0] moved by one ulp with no posting at day %d fails W-c-f the next check: %s" % (nudge, ff[:1]))
        kit.finish()
    kit.check(not xf, "W-c-x: link postings equal link flows and the persons' double entry is exactly 0 on all %d days: %s" % (cons.days, xf[:3]))
    kit.check(not ff and cons.L.posts > 0, "W-c-f: every stock within (1 + 2u)·B of its shadow on all %d days, %d postings (worst %.3g of the bound): %s" % (cons.days, cons.L.posts, cons.worst, ff[:3]))
    print("W-c (reported): the frozen model's largest daily gap across links, give minus what a supplier posted: %.3g MW" % cons.gap_max)
    if not d:
        out = os.environ.get("WORLD_OWN_OUT")
        if out:
            with open(out, "w") as f:
                json.dump(own, f)
        print("python straight run: day %d digest %s" % (days, day_digest(own[max(own)])))
    print("elapsed %.1f s" % (time.perf_counter() - t0))
    kit.finish()


if __name__ == "__main__":
    main()
