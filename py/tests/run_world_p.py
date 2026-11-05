# W1-p and W1-p-mf (WORLD_PORT_PLAN §5, AMENDED B2): the persons-on world made wholly in Python (py/world, py/econ, py/people's
# layer.Persons) and stepped by py/world/integrated.py for 24 months; at month 0's B5 and every month's B5 each world, econ and persons
# field against oracle_dump_month.gd's hashes
#   python py/tests/run_world_p.py <oracle_month dir> [months]      WORLD_PEOPLE_SEED=2 for W1-p-mf
import os
import sys
import time

from common import Kit
from core.digest import read_hashes
from people.layer import Persons
from world import actors as MA
from world import integrated as IM
from world.world import World

SALT = "0123456789abcdef0123456789abcdef"


def month_end(m):
    return 365 * ((m - 1) // 12) + MA.MONTH_ENDS[(m - 1) % 12]


def diff(w, d, m):
    got = IM.hashes(w)
    got["persons"] = w.people.hashes()
    out = {}
    for mod in ("world", "econ", "persons"):
        want = read_hashes(os.path.join(d, "m%02d.b05.%s.sha.txt" % (m, mod)))
        out[mod] = [n for n in sorted(set(want) | set(got[mod])) if got[mod].get(n) != want.get(n)]
    return out


def main():
    d = sys.argv[1]
    months = int(sys.argv[2]) if len(sys.argv) > 2 else 24
    seed = int(os.environ.get("WORLD_PEOPLE_SEED", "1"))
    kit = Kit("py/tests/run_world_p.py")
    t0 = time.perf_counter()
    w = World()
    err = w.create(2024, {"view_salt": SALT, "people": True, "people_seed": seed, "people_per_prefecture": 200}, None,
                   IM.econ_factory(), Persons.create)
    kit.check(err == "", "W1-p create: %s (%.1f s)" % (err or "ok", time.perf_counter() - t0))
    if err:
        kit.finish()
    b = diff(w, d, 0)
    if seed != 1:
        kit.check(bool(b["persons"]) and "params" in b["world"], "W1-p-mf people_seed %d: month 0's B5 differs in the persons (%d fields, %s) and the world %s"
                  % (seed, len(b["persons"]), b["persons"][:3], b["world"][:3]))
        kit.finish()
    kit.check(not any(b.values()), "W1-p month 0 B5: world %s econ %s persons %s" % (b["world"][:4], b["econ"][:4], b["persons"][:4]))
    for m in range(1, months + 1):
        t1 = time.perf_counter()
        IM.advance_to(w, month_end(m))
        b = diff(w, d, m)
        kit.check(not any(b.values()), "W1-p month %d B5 (%.1f s): world %s econ %s persons %s" % (m, time.perf_counter() - t1, b["world"][:4], b["econ"][:4], b["persons"][:4]))
        if any(b.values()):
            break
    kit.finish()


if __name__ == "__main__":
    main()
