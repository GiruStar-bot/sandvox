# polity/public.gd: the cabinet's approval answering the food price, the unemployment change and the levers applied
from .. import canon as CANON
from ..data import exists
from .._core import gd
from ..gdtypes import deep

A_FOOD = 0.15
B_UNEMP = 0.02
EFFECT = {"consumption_tax_rate": -0.05, "child_allowance": 0.01, "fuel_subsidy": 0.01, "rice_stock_release": 0.005, "defence_budget_share": -0.005}
CARRY = 0.9


class Public:
    def __init__(self):
        self.prefectures = {}
        self.approval = 0.4
        self.shock = 0.0
        self.history = []

    def load_state(self, key, start_approval):
        p = "res://data/modern/polity/%s_prefectures.json" % key.lower()
        d = CANON.parse_file(p) if exists(p) else None
        if isinstance(d, dict):
            self.prefectures = d["prefectures"]
        self.approval = start_approval
        return ""

    def step(self, month, food_price_yoy, d_unemployment_pt, levers_applied):
        eff = 0.0
        for lid in levers_applied:
            eff += float(EFFECT.get(lid, 0.0))
        s = A_FOOD * (-food_price_yoy) + B_UNEMP * (-d_unemployment_pt) + eff
        self.shock = CARRY * self.shock + s
        self.approval = gd.clampf(self.approval + s, 0.05, 0.9)
        self.history.append([month, self.approval, food_price_yoy, d_unemployment_pt, eff])
        return self.approval

    def change_since(self, month):
        for row in self.history:
            if int(row[0]) == month:
                return self.approval - float(row[1])
        return 0.0

    def to_dict(self):
        return {"approval": self.approval, "shock": self.shock, "history": deep(self.history)}

    def from_dict(self, d):
        self.approval = float(d.get("approval", self.approval))
        self.shock = float(d.get("shock", 0.0))
        self.history = deep(d.get("history", []))
