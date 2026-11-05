# The economy's state for the parity rows: the fields and digest of tools/py/oracle_dump_econ.gd (A1), and a month read from its tree
import hashlib

from core.digest import canon as _canon, load

from .actors import Bank, CropFarming, FoodManufacturing, TradingHouse
from .labour import Labour
from .month import EconMonth
from .world import World

ECON_VARS = ["core_inflation", "final_demand", "shocks"]
WORLD_VARS = ["commodities", "goods", "cash", "contracts", "month", "logistics", "storage", "cost_plus", "env", "transfers", "records"]
KINDS = {"crop_farming": CropFarming, "food_manufacturing": FoodManufacturing, "trading_houses": TradingHouse}


def fields(e):
    # The oracle's fields, the free text left out (oracle_dump_econ.gd's header): records' why, transfers' why, actor logs, shocks' why
    f = {}
    f["econ.core_inflation"] = e.core_inflation
    f["econ.final_demand"] = e.final_demand
    f["econ.shocks"] = [{k: v for k, v in s.items() if k != "why"} for s in e.shocks]
    w = e.world
    for n in WORLD_VARS:
        v = getattr(w, n)
        if n == "records":
            v = [r[:7] for r in v]
        elif n == "transfers":
            v = [t[:4] for t in v]
        f["world." + n] = v
    owners = [("actor." + a.id, a) for a in e.actors]
    if e.bank is not None:
        owners.append(("bank", e.bank))
    if e.labour is not None:
        owners.append(("labour", e.labour))
    if getattr(e, "mech", None) is not None:
        owners.append(("mech", e.mech))
    for name, o in owners:
        for n in o.var_names():
            if n == "log" and name != "labour":
                continue
            f[name + "." + n] = getattr(o, n)
    return f


def field_hashes(e):
    out = {}
    for n, v in fields(e).items():
        h = hashlib.sha256()
        _canon(h, v)
        out[n] = h.hexdigest()
    return out


def digest(e):
    hs = field_hashes(e)
    lines = "".join("%s %s\n" % (n, hs[n]) for n in sorted(hs))
    return hashlib.sha256(lines.encode("utf-8")).hexdigest(), hs


def read_hashes(path):
    out = {}
    with open(path, encoding="utf-8") as fh:
        for ln in fh:
            n, h = ln.split()
            out[n] = h
    return out


def load_tree(d):
    return load(d)


def from_tree(d):
    # A month built from the oracle's typed tree (A3: E1 starts from the oracle's month-0 state, not from the Python start)
    t = load(d)
    e = EconMonth()
    e.world = World()
    for n in WORLD_VARS:
        setattr(e.world, n, t["world." + n])
    e.world.records = [r + [""] for r in e.world.records]
    e.world.transfers = [x + [""] for x in e.world.transfers]
    e.core_inflation = t["econ.core_inflation"]
    e.final_demand = t["econ.final_demand"]
    e.shocks = [dict(s, why="") for s in t["econ.shocks"]]
    aids = [n[len("actor."):-len(".id")] for n in t if n.startswith("actor.") and n.endswith(".id")]
    actors = []
    # Why the kinds' order and not the tree's: create() builds crop farming, food manufacturing, then the trading houses, and the month
    # plans and settles them in that order
    for pre, cls in KINDS.items():
        for aid in aids:
            if aid.startswith(pre):
                a = cls()
                for n in a.var_names():
                    if n != "log":
                        setattr(a, n, t["actor.%s.%s" % (aid, n)])
                actors.append(a)
    e.actors = actors
    if "bank.id" in t:
        b = Bank()
        for n in b.var_names():
            if n != "log":
                setattr(b, n, t["bank." + n])
        e.bank = b
    if "labour.spec" in t:
        lb = Labour()
        for n in lb.var_names():
            setattr(lb, n, t["labour." + n])
        e.labour = lb
    if "mech.p" in t:
        e.enable_mech(t["mech.p"])
        for n in e.mech.var_names():
            if n != "log":
                setattr(e.mech, n, t["mech." + n])
        if "labour.bands" in t:
            e.labour.bands = t["labour.bands"]
    return e
