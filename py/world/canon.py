# canon.gd: the data files' floats snapped through integer arithmetic (V082), json read as Godot's parser does (every number a float)
import json
import math

from .gdtypes import is_finite

ROOT = __import__("os").path.abspath(__import__("os").path.join(__import__("os").path.dirname(__file__), "..", ".."))


def res(path):
    return path.replace("res://", ROOT + "/") if path.startswith("res://") else path


def _floor(x):
    return float(math.floor(x))


def canon_f(x):
    if not is_finite(x):
        return x
    if abs(x) >= 1e7:
        r = _floor(x + 0.5)
        return r if abs(x - r) < 1e-3 else x
    return _floor(x * 1e9 + 0.5) / 1e9


def canon(v):
    if type(v) is float:
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


def parse(text):
    # Why parse_int=float: Godot's JSON gives every number as a float (ECON A2), and the int/float tag is in the digest
    return json.loads(text, parse_int=float)


def parse_file(path):
    with open(res(path), encoding="utf-8") as f:
        return parse(f.read())


def load_json(path):
    return canon(parse_file(path))


def canon_m(v):
    if type(v) is float:
        return _floor(v + 0.5) if is_finite(v) and abs(v) >= 1e7 else canon_f(v)
    if isinstance(v, dict):
        for k in list(v.keys()):
            v[k] = canon_m(v[k])
        return v
    if isinstance(v, list):
        for i in range(len(v)):
            v[i] = canon_m(v[i])
        return v
    return v


def load_json_m(path):
    return canon_m(parse_file(path))
