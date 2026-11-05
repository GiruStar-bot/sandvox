# The start's inputs read as Godot reads them: JSON.parse_string gives every number as a float, then canon.gd's canon walk snaps it
# (canon_f). Why parse_int=float: Godot has no JSON ints, so spec["harvest_month"] is 12.0 there, and an int here would hash and
# divide differently (ECON_PORT_PLAN review, change 2)
import json
import math
import os

# START_DATA_ROOT: the tree whose data/ the start reads. Step (a) reads the frozen oracle's (a worktree at cd165891), because the
# data on modern has moved since (R96e)
ROOT = os.environ.get("START_DATA_ROOT") or os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))


def canon_f(x):
    if not math.isfinite(x):
        return x
    if abs(x) >= 1e7:
        r = float(math.floor(x + 0.5))
        return r if abs(x - r) < 1e-3 else x
    return float(math.floor(x * 1e9 + 0.5)) / 1e9


def canon(v):
    if isinstance(v, float):
        return canon_f(v)
    if isinstance(v, dict):
        for k in list(v.keys()):
            v[k] = canon(v[k])
        return v
    if isinstance(v, list):
        for i in range(len(v)):
            v[i] = canon(v[i])
        return v
    return v


def load_json(res_path):
    # res_path as GDScript names it (res://...), read from the repository root
    path = os.path.join(ROOT, res_path[len("res://"):]) if res_path.startswith("res://") else res_path
    with open(path, encoding="utf-8") as f:
        return canon(json.load(f, parse_int=float))
