# D-lev, D-lev-mf, D-lev-0 and D-lev-1 (WORLD_PORT_PLAN §5b): the mid-month lever departure, on the persons-on world made in Python
# (as W1-p) against INTEGRATED_MONTH_PLAN §7's forced oracle and §6's unforced one
#   python py/tests/run_dlev.py <forced oracle dir> <unforced oracle dir>
import json
import os
import struct
import sys

from common import Kit
from core.digest import read_hashes
from people.layer import Persons
from world import actors as MA
from world import integrated as IM
from world.gdtypes import sha
from world.world import World

SALT = "0123456789abcdef0123456789abcdef"


def month_end(m):
    return 365 * ((m - 1) // 12) + MA.MONTH_ENDS[(m - 1) % 12]


def bits(x):
    return struct.unpack("<q", struct.pack("<d", x))[0]


def make(window):
    p = {"view_salt": SALT, "people": True, "people_seed": 1, "people_per_prefecture": 200}
    if window:
        p["lever_window"] = window
    w = World()
    err = w.create(2024, p, None, IM.econ_factory(), Persons.create)
    if err:
        raise ValueError(err)
    return w


def diff(w, d, m, b):
    got = IM.hashes(w)
    got["persons"] = w.people.hashes()
    out = {}
    for mod in ("world", "econ", "persons"):
        want = read_hashes(os.path.join(d, "m%02d.b%02d.%s.sha.txt" % (m, b, mod)))
        out[mod] = [n for n in sorted(set(want) | set(got[mod])) if got[mod].get(n) != want.get(n) and not (mod == "world" and n == "params")]
    return out


def params_less_window(w, d, m):
    want = read_hashes(os.path.join(d, "m%02d.b05.world.sha.txt" % m))["params"]
    p = {k: v for k, v in w.params.items() if k != "lever_window"}
    return sha(p) == want


def run(window, d, months, forces):
    w = make(window)
    seen = []
    cur = [0]

    def hook(tag):
        seen.append((cur[0], tag, diff(w, d, cur[0], int(tag[1:]))))
    for m in range(1, months + 1):
        cur[0] = m
        IM.advance_forced(w, month_end(m), forces, hook)
    return w, seen


def eff_month(w, mi):
    for row in w.public.history:
        if int(row[0]) == mi:
            return row[4]
    return None


def main():
    df, du = sys.argv[1], sys.argv[2]
    kit = Kit("py/tests/run_dlev.py")
    forces = json.load(open(os.path.join(df, "force.json"), encoding="utf-8"))
    want_eff = 0.0
    want_eff += 0.005
    want_eff += 0.01
    w, seen = run("month", df, 5, forces)
    lev = w.people.env_seen.get(5, {}).get("levers")
    eff = eff_month(w, 4)
    kit.check(lev == ["rice_stock_release", "fuel_subsidy"] and eff is not None and bits(eff) == bits(want_eff),
              "D-lev the forced run with lever_window month: month 5's env levers %s, public's month-5 effects %r (want %r)" % (lev, eff, want_eff))
    firsts = [(m, t, b) for m, t, b in seen if any(b.values())]
    early = [x for x in firsts if x[0] < 5]
    f5 = next((x for x in firsts if x[0] == 5), None)
    w5 = next((x for x in firsts if x[0] == 5 and x[2]["world"]), None)
    kit.check(not early and f5 is not None and f5[1] == "b03" and f5[2]["persons"] and not f5[2]["world"] and not f5[2]["econ"]
              and w5 is not None and w5[1] == "b04" and {"public", "status.ind"} <= set(w5[2]["world"]),
              "D-lev-1 (AMENDED) months 1-4 equal the oracle but params (%s); month 5 first differs at %s in the persons only %s; the world first at %s: %s"
              % ("yes" if not early else "first %s %s" % early[0][:2], f5[1] if f5 else None, f5[2]["persons"][:4] if f5 else [], w5[1] if w5 else None,
                 w5[2]["world"][:6] if w5 else []))
    w2, _ = run(None, df, 5, forces)
    lev2 = w2.people.env_seen.get(5, {}).get("levers")
    eff2 = eff_month(w2, 4)
    kit.check(lev2 == [] and eff2 == 0.0, "D-lev-mf the old behaviour (no lever_window) fails D-lev: month 5's env levers %s, effects %r" % (lev2, eff2))
    w3, seen3 = run("month", du, 24, [])
    bad = [(m, t, b) for m, t, b in seen3 if any(b.values())]
    pl = all(params_less_window(w3, du, 24) for _ in [0])
    kit.check(not bad and pl, "D-lev-0 the unforced run with lever_window month: B1-B5 of 24 months equal the oracle in every world, econ and persons field but params%s; params less lever_window equal: %s"
              % ("" if not bad else "; first %s %s %s" % (bad[0][0], bad[0][1], {k: v[:4] for k, v in bad[0][2].items()}), pl))
    kit.finish()


if __name__ == "__main__":
    main()
