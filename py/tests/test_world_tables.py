# W0-h, W0-j, W-el and W-mf3 (WORLD_PORT_PLAN §5) against the oracle's tables.json (WORLD_MODE=tables of oracle_dump_world.gd):
#   python py/tests/test_world_tables.py <tables dir>      (without a dir only W-mf3 runs)
import json
import os
import sys

from common import Kit
from world import canon as CANON
from world import hashes
from world import publish as MP
from world.data import ModernData
from world.gdtypes import dec, sha, bits
from world.polity.election import Election
from world.polity.organs import Organs

SALT = "0123456789abcdef0123456789abcdef"
GOODS = ["lithography", "photoresist", "silicon_wafers", "gallium", "neon", "chips"]


def main():
    d = sys.argv[1] if len(sys.argv) > 1 else ""
    kit = Kit("py/tests/test_world_tables.py")
    data = ModernData()
    kit.check(data.load_year(2024) == "", "the 2024 data loads: %s" % (data.error or "ok"))
    keys = data.keys
    a = [hashes.token(bytes.fromhex(SALT), v, k) for v in ("jpn", "test_b") for k in keys]
    b = [hashes.token(bytes.fromhex(SALT[:-2] + "ee"), v, k) for v in ("jpn", "test_b") for k in keys]
    kit.check(all(x != y for x, y in zip(a, b)), "W-mf3: the salt's last byte changed moves all %d tokens" % len(a))
    if not d:
        kit.finish()
    with open(os.path.join(d, "tables.json"), encoding="utf-8") as f:
        t = json.load(f)
    bad = []
    for i, (s, u, fb) in enumerate(t["restrict"]):
        want = "modern-restrict|%d|%s|%s|%d" % (2022 + i % 3, keys[(i * 7) % len(keys)], GOODS[i % len(GOODS)], 30 + i * 13)
        if s != want or hashes.u32(s) != u or bits(hashes.unit(s)) != int(fb["f"]):
            bad.append(i)
    kit.check(not bad, "W0-h restriction draws: %d of %d differ %s" % (len(bad), len(t["restrict"]), bad[:5]))
    bad2 = []
    for i, (k, fig, y, fb) in enumerate(t["publish"]):
        if bits(MP._unit(k, fig, y)) != int(fb["f"]):
            bad2.append(i)
    kit.check(not bad2, "W0-h publication estimates: %d of %d differ %s" % (len(bad2), len(t["publish"]), bad2[:5]))
    bad3 = [i for i, (s, v, k, tok) in enumerate(t["hmac"]) if hashes.token(bytes.fromhex(s), v, k) != tok]
    kit.check(not bad3, "W0-h view tokens: %d of %d differ %s" % (len(bad3), len(t["hmac"]), bad3[:5]))
    for name, how, want in t["files"]:
        p = "res://data/modern/" + name
        v = CANON.load_json_m(p) if how == "m" else (CANON.load_json(p) if how == "c" else CANON.parse_file(p))
        kit.check(sha(v) == want, "W0-j %s (%s): %s" % (name, how, "equal" if sha(v) == want else "differs"))
    el = Election()
    el.load_state("JPN")
    org = Organs()
    org.load_state("JPN")
    bad4 = []
    for row in t["election"]:
        shares = el.vote_shares(org.governing, 0.05 * float(row["a"]), float(row["u"]), 0.0)
        lo = el.run_lower_house(shares)
        up = el.run_upper_house(shares)
        des = Election.designate(lo["seats"], org.governing, org.house_total("house_of_representatives"), org.spec.get("partners", {}))
        des.pop("why")
        if sha({"shares": shares, "lower": lo, "upper": up, "designate": des}) != row["sha"]:
            bad4.append((row["a"], row["u"], shares == dec(row["shares"]), lo["seats"] == dec(row["lower_seats"]), up["composition"] == dec(row["upper"])))
    kit.check(not bad4, "W-el: %d of %d grid points differ (a, u, shares equal, lower seats equal, upper equal) %s" % (len(bad4), len(t["election"]), bad4[:4]))
    kit.finish()


if __name__ == "__main__":
    main()
