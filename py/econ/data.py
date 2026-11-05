# The econ data files as the oracle reads them (ECON_PORT_PLAN A2): every JSON number a float, every float snapped by canon.gd's rule
import json
import math
import os

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
ECON_DIR = os.path.join(ROOT, "data", "modern", "econ")


def canon_f(x):
    if not math.isfinite(x):
        return x
    if abs(x) >= 1e7:
        r = math.floor(x + 0.5)
        return float(r) if abs(x - r) < 1e-3 else x
    return math.floor(x * 1e9 + 0.5) / 1e9


def canon(v):
    if isinstance(v, float):
        return canon_f(v)
    if isinstance(v, dict):
        return {k: canon(x) for k, x in v.items()}
    if isinstance(v, list):
        return [canon(x) for x in v]
    return v


def load_json(name):
    path = os.path.join(ECON_DIR, name)
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        return canon(json.load(f, parse_int=float))


def exists(name):
    return os.path.exists(os.path.join(ECON_DIR, name))
