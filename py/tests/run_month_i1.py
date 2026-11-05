# INTEGRATED_MONTH_PLAN §3's rows against tools/py/oracle_dump_month.gd's run:
#   I-0   the oracle's hooked copy equals the plain advance_to at every month end
#   I-1   from each MONTH_FULL month's oracle state, one Python month with every module real but the persons (the stub): at B1-B5 every
#         world and econ field equals the oracle's
#   I-1c  24 Python months chained from month 0 (no reload of the world or econ): every B5 equals the oracle's
#   I-env the env the world and econ hand the persons at M8 equals the oracle's bits, every month of I-1c
#   I-c   E-c (ECON A6-A8) on py/econ inside the integrated month, every month of I-1c
#   I-mf  must-fail: M9 before M4-M8 in month 2; B4's first differing field is the public's approval
#   I-mf2 must-fail: the month-1 supply handed to econ in month 2; B2's first differing econ fields are labour's
#   (§7, when the oracle dir has a force.json with a rice release) I-rel: the release case ran (one release at its month, both levers
#         applied); I-mf3 must-fail: the glue's tonnes per kt 1000.5 in the release month from the oracle's state before it; B1 first,
#         econ and the chronicle
#   python3 py/tests/run_month_i1.py <oracle dir> [months]
import json
import os
import struct
import sys

from common import Kit
from core.digest import read_hashes
from econ import state as ES
from econ.shadow import Shadow
from world import actors as MA
from world import integrated as IM
from world.gdtypes import dec


def unbits(node):
    return struct.unpack("<d", struct.pack("<q", int(node["f"])))[0]


def bits(x):
    return struct.unpack("<q", struct.pack("<d", x))[0]


def month_end(m):
    return 365 * ((m - 1) // 12) + MA.MONTH_ENDS[(m - 1) % 12]


class Oracle:
    def __init__(self, d):
        self.d = d
        self._iface = {}
        fp = os.path.join(d, "force.json")
        self.force = json.load(open(fp, encoding="utf-8")) if os.path.exists(fp) else []

    def iface(self, m):
        if m not in self._iface:
            with open(os.path.join(self.d, "m%02d.iface.json" % m), encoding="utf-8") as f:
                raw = json.load(f)
            s = raw["supply"]
            raw["supply"] = {"search_share": unbits(s["search_share"]), "wage_demand_share": unbits(s["wage_demand_share"]),
                             "scales": {c: unbits(v) for c, v in s["scales"].items()}}
            raw["summary"] = dec(raw["summary"])
            self._iface[m] = raw
        return self._iface[m]

    def hashes(self, m, b, mod):
        return read_hashes(os.path.join(self.d, "m%02d.b%02d.%s.sha.txt" % (m, b, mod)))

    def start(self, m, persons):
        e = ES.from_tree(os.path.join(self.d, "m%02d_econ" % m))
        return IM.from_oracle(os.path.join(self.d, "m%02d_world" % m), e, persons)


def compare(o, m, w, tag):
    b = int(tag[1:])
    got = IM.hashes(w)
    bad = {}
    for mod in ("world", "econ"):
        want = o.hashes(m, b, mod)
        bad[mod] = sorted(n for n in set(want) | set(got[mod]) if want.get(n) != got[mod].get(n))
    return bad


def one_month(o, m0, order=None, supply_month=None):
    stub = IM.PersonsStub(lambda mm: o.iface(supply_month if (supply_month and mm == m0 + 1) else mm))
    stub.month = m0
    w = o.start(m0, stub)
    seen = []

    def hook(tag):
        seen.append((tag, compare(o, m0 + 1, w, tag)))
    IM.advance_forced(w, month_end(m0 + 1), o.force, hook, order)
    return seen


def main():
    od = sys.argv[1]
    months = int(sys.argv[2]) if len(sys.argv) > 2 else 24
    o = Oracle(od)
    k = Kit("py/tests/run_month_i1.py")
    i0 = []
    for m in range(1, months + 1):
        plain = open(os.path.join(od, "m%02d.plain.sha.txt" % m), encoding="utf-8").read()
        hooked = "".join(head + open(os.path.join(od, "m%02d.b05.%s.sha.txt" % (m, mod)), encoding="utf-8").read()
                         for head, mod in (("WORLD\n", "world"), ("ECON\n", "econ"), ("PERSONS\n", "persons")))
        if plain != hooked:
            i0.append(m)
    k.check(not i0, "I-0 the oracle's hooked month equals the plain advance_to at months 1-%d: differing %s" % (months, i0))
    full = sorted(int(n[1:3]) for n in os.listdir(od) if n.endswith("_world"))
    for m0 in full:
        if m0 + 1 > months:
            continue
        seen = one_month(o, m0)
        firsts = [(t, b) for t, b in seen if b["world"] or b["econ"]]
        k.check(not firsts and len(seen) == 5, "I-1 month %d from the oracle's month-%d state: B1-B5 world and econ equal the oracle's%s"
                % (m0 + 1, m0, "" if not firsts else "; first at %s: world %s econ %s" % (firsts[0][0], firsts[0][1]["world"][:3], firsts[0][1]["econ"][:3])))
    stub = IM.PersonsStub(o.iface)
    w = o.start(0, stub)
    sh = Shadow(w.econ.e)
    bad_c, bad_env, bad_ec, worst = [], [], [], (0.0, "")
    for m in range(1, months + 1):
        IM.advance_forced(w, month_end(m), o.force)
        got = IM.hashes(w)
        for mod in ("world", "econ"):
            if got[mod] != o.hashes(m, 5, mod):
                bad_c.append((m, mod, sorted(n for n in got[mod] if got[mod][n] != o.hashes(m, 5, mod).get(n))[:3]))
        env, want = stub.env_seen.get(m), o.iface(m)["env"]
        same = env is not None and all(bits(env[n]) == int(want[n]["f"]) for n in ("inflation_month", "food_price_yoy", "unemployment_rate", "wage_index")) \
            and list(env["levers"]) == list(want["levers"])
        if not same:
            bad_env.append(m)
        sh.month(w.econ.e)
        money, goods = sh.exact()
        gaps, wst = sh.float_gaps(w.econ.e)
        worst = max(worst, wst)
        if money != 0 or any(v != 0 for v in goods.values()) or gaps:
            bad_ec.append(m)
        if bad_c and len(bad_c) > 3:
            break
    k.check(not bad_c, "I-1c %d chained Python months: every B5 world and econ field equals the oracle's%s" % (months, "" if not bad_c else "; first %s" % (bad_c[0],)))
    k.check(not bad_env, "I-env the env handed to the persons at M8 equals the oracle's bits every month: differing months %s" % bad_env)
    k.check(not bad_ec, "I-c E-c inside the integrated month every month: failing months %s; worst gap / bound %.3g at %s" % (bad_ec, worst[0], worst[1]))
    if 1 in full:
        seen = one_month(o, 1, order="s4_first")
        first = next(((tg, bb) for tg, bb in seen if bb["world"] or bb["econ"]), None)
        b4 = dict(seen).get("b04", {"world": [], "econ": []})
        ok = bool(b4["world"] or b4["econ"]) and first is not None and bool({"public", "status.ind"} & set(first[1]["world"]))
        k.check(ok, "I-mf M9 before M4-M8 in month 2: B4 differs %s; the first differing boundary %s, its world fields %s (predicted: the public's approval)"
                % (bool(b4["world"] or b4["econ"]), first[0] if first else None, first[1]["world"][:5] if first else []))
        seen = one_month(o, 1, supply_month=1)
        first2 = next(((tg, bb) for tg, bb in seen if bb["world"] or bb["econ"]), None)
        ok2 = first2 is not None and first2[0] == "b02" and bool({"labour.search_share", "labour.wage_demand_share"} & set(first2[1]["econ"]))
        k.check(ok2, "I-mf2 the month-1 supply in month 2: the first differing boundary %s, its econ fields %s (predicted: B2, labour's supply fields)"
                % (first2[0] if first2 else None, first2[1]["econ"][:6] if first2 else []))
    else:
        k.check(False, "I-mf / I-mf2 need the oracle's month-1 state (MONTH_FULL)")
    rice = [f for f in o.force if f[2] == "rice_stock_release"]
    if rice:
        fd = int(rice[0][0])
        lead = 30
        mr = next(m for m in range(1, months + 1) if month_end(m) >= fd + lead)
        rel = o.iface(mr)["releases"]
        lv = [str(r[2]) for r in o.iface(mr)["levers"]]
        want = [f[2] for f in o.force]
        ok = len(rel) == 1 and int(rel[0][0]) == fd + lead and unbits(rel[0][2]) == float(rice[0][3]) * 1000.0 and sorted(lv) == sorted(want) \
            and all(not o.iface(m)["releases"] for m in range(1, months + 1) if m != mr)
        k.check(ok, "I-rel (AMENDED) the release case ran: month %d's releases %s, levers applied in the month %s (declared: one release on day %d asking %.0f t; levers %s); "
                "the env's levers %s (only those applied on the month's last day reach it)"
                % (mr, [(r[0], r[1], unbits(r[2]), unbits(r[3])) for r in rel], lv, fd + lead, float(rice[0][3]) * 1000.0, want, o.iface(mr)["env"]["levers"]))
        if mr - 1 in full:
            IM.RELEASE_T_PER_KT = 1000.5
            try:
                seen = one_month(o, mr - 1)
            finally:
                IM.RELEASE_T_PER_KT = 1000.0
            first3 = next(((tg, bb) for tg, bb in seen if bb["world"] or bb["econ"]), None)
            ok3 = first3 is not None and first3[0] == "b01" and bool(first3[1]["econ"]) and "chronicle" in first3[1]["world"]
            k.check(ok3, "I-mf3 V015's mutation (1000.5 t per kt) in month %d: the first differing boundary %s, its econ fields %s, world fields %s "
                    "(predicted: B1, econ's rice and the chronicle)" % (mr, first3[0] if first3 else None, first3[1]["econ"][:6] if first3 else [],
                                                                          first3[1]["world"][:6] if first3 else []))
        else:
            k.check(False, "I-mf3 needs the oracle's month-%d state (MONTH_FULL)" % (mr - 1))
    k.finish()


if __name__ == "__main__":
    main()
