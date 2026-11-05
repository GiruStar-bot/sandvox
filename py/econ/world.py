# The economy's world state: the twin of sim/modern/econ/world_state.gd (goods, money and contract ledgers, the market clearing)
import math

from core import detmath as DM
from core.gd import clampf, maxf, minf

from .data import load_json

INF = math.inf


def gkey(commodity, jurisdiction):
    return commodity + "|" + jurisdiction


class World:
    def __init__(self):
        self.commodities = {}
        self.goods = {}
        self.cash = {}
        self.contracts = []
        self.month = 0
        self.logistics = {}
        self.storage = {}
        self.cost_plus = {}
        self.env = {}
        self.transfers = []
        self.records = []
        self.error = ""
        # Check-only (E-c, A6): when a list, every goods posting appends [kind, key, quantity]; never saved or digested
        self.journal = None

    def create(self):
        c = load_json("commodities.json")
        if not isinstance(c, dict):
            self.error = "world_state: no commodities"
            return self.error
        self.commodities = c["commodities"]
        return ""

    def good(self, commodity, jurisdiction):
        k = gkey(commodity, jurisdiction)
        if k not in self.goods:
            self.goods[k] = {"produced": 0.0, "inventory": 0.0, "offered": 0.0, "demanded": 0.0, "traded": 0.0, "unmet": 0.0, "imported": 0.0,
                             "produced_last": 0.0, "traded_last": 0.0, "unmet_last": 0.0, "offered_by": {}, "traded_by": {}, "held_by": {},
                             "price": float(self.commodities.get(commodity, {}).get("start_price", 0.0))}
        return self.goods[k]

    def _rec(self, ledger, key, field, before, after, by, why):
        self.records.append([self.month, ledger, key, field, float(before), float(after), by, why])

    def produce(self, commodity, jurisdiction, qty, by, why):
        qty = float(qty)
        g = self.good(commodity, jurisdiction)
        self._rec("goods", gkey(commodity, jurisdiction), "inventory", g["inventory"], g["inventory"] + qty, by, why)
        g["produced"] += qty
        g["inventory"] += qty
        if self.journal is not None:
            self.journal.append(["produce", gkey(commodity, jurisdiction), qty])
        hb = g.get("held_by", {})
        hb[by] = float(hb.get(by, 0.0)) + qty
        g["held_by"] = hb

    def use_own(self, commodity, jurisdiction, qty, by, why):
        qty = float(qty)
        g = self.good(commodity, jurisdiction)
        hb = g.get("held_by", {})
        others = 0.0
        for h in hb:
            if h != by:
                others += float(hb[h])
        q = minf(qty, float(g["inventory"]) - others)
        if q <= 0.0:
            return
        self._rec("goods", gkey(commodity, jurisdiction), "inventory", g["inventory"], g["inventory"] - q, by, why)
        g["inventory"] -= q
        if self.journal is not None:
            self.journal.append(["use", gkey(commodity, jurisdiction), q])
        hb[by] = float(hb.get(by, 0.0)) - q
        g["held_by"] = hb

    def offer(self, commodity, jurisdiction, qty, by):
        qty = float(qty)
        g = self.good(commodity, jurisdiction)
        room = float(g["inventory"]) - float(g["offered"])
        q = minf(qty, room) if room > 0.0 else 0.0
        if q <= 0.0:
            return
        g["offered"] += q
        ob = g.get("offered_by", {})
        ob[by] = float(ob.get(by, 0.0)) + q
        g["offered_by"] = ob
        self._rec("goods", gkey(commodity, jurisdiction), "offered", 0.0, g["offered"], by, "offer")

    def demand(self, commodity, jurisdiction, qty, by):
        qty = float(qty)
        g = self.good(commodity, jurisdiction)
        g["demanded"] += qty
        self._rec("goods", gkey(commodity, jurisdiction), "demanded", 0.0, g["demanded"], by, "demand")

    def clear_markets(self):
        for k in self.goods:
            g = self.goods[k]
            c = k.split("|")[0]
            cap_l = float(self.logistics.get(c, INF))
            traded = minf(minf(float(g["offered"]), float(g["demanded"])), cap_l)
            why = "min(offered, demanded)"
            if traded == cap_l and cap_l < minf(float(g["offered"]), float(g["demanded"])):
                why = "logistics cap %.0f binds" % cap_l
            g["traded"] = traded
            g["unmet"] = maxf(0.0, float(g["demanded"]) - traded)
            self._rec("goods", k, "traded", 0.0, traded, "market", why)
            tb = {}
            ob = g.get("offered_by", {})
            for seller in ob:
                tb[seller] = traded * float(ob[seller]) / float(g["offered"]) if float(g["offered"]) > 0.0 else 0.0
            g["traded_by"] = tb
            g["inventory"] -= traded
            if self.journal is not None:
                self.journal.append(["trade", k, traded])
            hb = g.get("held_by", {})
            for seller in tb:
                if seller in hb:
                    hb[seller] = float(hb[seller]) - float(tb[seller])
            g["held_by"] = hb
            spec = self.commodities.get(c, {})
            speed = float(spec.get("adjust_speed", 0.0))
            g["offered_month"] = float(g["offered"])
            g["demanded_month"] = float(g["demanded"])
            if speed > 0.0 and c in self.storage:
                t = self.storable_target(c, float(g["inventory"]) + traded + float(g.get("in_transit", 0.0)))
                cap_s = float(spec.get("move_cap", 0.2))
                p0s = float(g["price"])
                move_s = clampf(speed * (float(t["target"]) / p0s - 1.0), -cap_s, cap_s)
                g["price"] = p0s * (1.0 + move_s)
                if abs(move_s) > 1e-12:
                    self._rec("goods", k, "price", p0s, g["price"], "market", "availability vs seasonal normal")
            elif speed > 0.0 and c in self.cost_plus and "unit_cost" in g:
                m_up = float(self.cost_plus[c]["markup"])
                target_c = (1.0 + m_up) * float(g["unit_cost"])
                cap_c = float(spec.get("move_cap", 0.2))
                p0c = float(g["price"])
                move_c = clampf(speed * (target_c / p0c - 1.0), -cap_c, cap_c)
                g["price"] = p0c * (1.0 + move_c)
                if abs(move_c) > 1e-12:
                    self._rec("goods", k, "price", p0c, g["price"], "market", "unit cost x (1 + markup)")
            elif speed > 0.0 and float(g["offered"]) > 0.0:
                excess = (float(g["demanded"]) - float(g["offered"])) / float(g["offered"])
                move = clampf(speed * excess, -float(spec.get("move_cap", 0.2)), float(spec.get("move_cap", 0.2)))
                p0 = float(g["price"])
                g["price"] = p0 * (1.0 + move)
                if abs(move) > 1e-12:
                    self._rec("goods", k, "price", p0, g["price"], "market", "excess demand")
            g["offered"] = 0.0
            g["demanded"] = 0.0
            g["offered_by"] = {}

    def storable_target(self, c, available):
        available = float(available)
        st = self.storage[c]
        hm = int(st["harvest_month"])
        ml = (hm - (self.month % 12 + 1) + 12) % 12
        ml = 12 if ml == 0 else ml
        r = float(st["reserve_t"])
        normal = r + (float(st["harvest_t"]) - r) * ml / 12.0 + float(st["import_t_month"]) * (1.0 + float(st["lead_months"]))
        delta = available - normal
        h = ml if delta < 0.0 else ml + 12
        x = maxf(0.05, 1.0 + delta / (float(st["use_t_month"]) * h))
        spec = self.commodities[c]
        e = float(spec["demand_elasticity"])
        target = float(spec["start_price"]) * DM.pow(x, 1.0 / e)
        return {"available": available, "normal": normal, "months_left": ml, "horizon": h, "x": x, "elasticity": e, "target": target}

    def fill_share(self, commodity, jurisdiction):
        g = self.good(commodity, jurisdiction)
        d = g["traded"] + g["unmet"]
        return g["traded"] / d if d > 0.0 else 1.0

    def pay(self, payer, payee, amount, why):
        amount = float(amount)
        if amount <= 0.0:
            return
        self.cash[payer] = float(self.cash.get(payer, 0.0)) - amount
        self.cash[payee] = float(self.cash.get(payee, 0.0)) + amount
        self.transfers.append([self.month, payer, payee, amount, why])
        self._rec("money", payer + ">" + payee, "cash", 0.0, amount, payer, why)

    def add_contract(self, buyer, seller, commodity, qty, price, due_month, kind):
        cid = len(self.contracts)
        self.contracts.append({"id": cid, "buyer": buyer, "seller": seller, "commodity": commodity, "quantity": float(qty), "price": float(price),
                               "due": int(due_month), "kind": kind, "settled": False})
        self._rec("contract", str(cid), "made", 0.0, qty, buyer, kind)
        return cid

    def record_note(self, ledger, key, field, before, after, by, why):
        self._rec(ledger, key, field, before, after, by, why)

    def next_month(self):
        self.month += 1
        for k in self.goods:
            g = self.goods[k]
            hist = g.get("price_hist", [])
            hist.append(g["price"])
            if len(hist) > 13:
                hist.pop(0)
            g["price_hist"] = hist
            g["price_prev"] = hist[len(hist) - 2] if len(hist) >= 2 else g["price"]
            g["price_12m"] = hist[0]
            g["offered_last"] = g.get("offered_month", 0.0)
            g["demanded_last"] = g.get("demanded_month", 0.0)
            g["produced_last"] = g["produced"]
            g["traded_last"] = g["traded"]
            g["unmet_last"] = g["unmet"]
            g["imported_last"] = g["imported"]
            g["produced"] = 0.0
            g["traded"] = 0.0
            g["unmet"] = 0.0
            g["imported"] = 0.0
