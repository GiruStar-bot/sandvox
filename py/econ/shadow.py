# E-c's shadow ledger (ECON_PORT_PLAN AMENDED A6, M039): the month's records replayed in exact rationals beside the port's floats
#   money: each transfer record [month, payer, payee, amount] posted twice in Fraction(amount), which is exact
#   goods: each posting the world journals (produce, use, trade) applied to the good's inventory in Fraction
# E-c-x: the shadow's totals conserve exactly. E-c-f: each float balance is within its accumulated bound of the shadow.
# Check-only: it reads the state and never writes it.
from fractions import Fraction

U = Fraction(1, 2 ** 53)


class Shadow:
    def __init__(self, e):
        w = e.world
        self.cash = {a: Fraction(v) for a, v in w.cash.items()}
        self.fcash = dict(w.cash)
        self.bound = {a: Fraction(0) for a in w.cash}
        self.cash0 = sum(self.cash.values(), Fraction(0))
        self.inv = {k: Fraction(g["inventory"]) for k, g in w.goods.items()}
        self.finv = {k: float(g["inventory"]) for k, g in w.goods.items()}
        self.ibound = {k: Fraction(0) for k in w.goods}
        self.inv0 = dict(self.inv)
        self.flow = {}
        self.seen = len(w.transfers)
        w.journal = []

    def _post(self, a, delta_f):
        # the float update as the port posts it, its rounding bound u x |balance after|, and the exact update
        if a not in self.cash:
            self.cash[a] = Fraction(0)
            self.fcash[a] = 0.0
            self.bound[a] = Fraction(0)
        self.fcash[a] = self.fcash[a] + delta_f
        self.bound[a] += U * abs(Fraction(self.fcash[a]))
        self.cash[a] += Fraction(delta_f)

    def month(self, e):
        w = e.world
        for t in w.transfers[self.seen:]:
            amount = float(t[3])
            self._post(str(t[1]), -amount)
            self._post(str(t[2]), amount)
        self.seen = len(w.transfers)
        for row in w.journal:
            kind, k, q = row[0], row[1], float(row[2])
            if k not in self.inv:
                self.inv[k] = Fraction(0)
                self.finv[k] = 0.0
                self.ibound[k] = Fraction(0)
                self.inv0[k] = Fraction(0)
            sign = 1.0 if kind == "produce" else -1.0
            self.finv[k] = self.finv[k] + q if sign > 0 else self.finv[k] - q
            self.ibound[k] += U * abs(Fraction(self.finv[k]))
            self.inv[k] += Fraction(q) if sign > 0 else -Fraction(q)
            fl = self.flow.setdefault(k, {"produce": Fraction(0), "use": Fraction(0), "trade": Fraction(0)})
            fl[kind] += Fraction(q)
        w.journal = []

    def exact(self):
        # E-c-x: money total and each good's produced - used - traded - delta inventory, exactly
        money = sum(self.cash.values(), Fraction(0)) - self.cash0
        goods = {}
        for k in self.inv:
            fl = self.flow.get(k, {"produce": Fraction(0), "use": Fraction(0), "trade": Fraction(0)})
            goods[k] = fl["produce"] - fl["use"] - fl["trade"] - (self.inv[k] - self.inv0[k])
        return money, goods

    def float_gaps(self, e):
        # E-c-f: per account and per good, |float - shadow| against (1 + 2u) x the accumulated bound; the worst ratio and its owner
        worst = (0.0, "")
        bad = []
        for a, v in e.world.cash.items():
            s = self.cash.get(a, Fraction(0))
            gap = abs(Fraction(v) - s)
            b = (1 + 2 * U) * self.bound.get(a, Fraction(0))
            r = float(gap / b) if b > 0 else (0.0 if gap == 0 else float("inf"))
            if r > worst[0]:
                worst = (r, "cash " + a)
            if gap > b:
                bad.append(("cash", a, float(gap), float(b)))
        for k, g in e.world.goods.items():
            s = self.inv.get(k, Fraction(0))
            gap = abs(Fraction(g["inventory"]) - s)
            b = (1 + 2 * U) * self.ibound.get(k, Fraction(0))
            r = float(gap / b) if b > 0 else (0.0 if gap == 0 else float("inf"))
            if r > worst[0]:
                worst = (r, "inventory " + k)
            if gap > b:
                bad.append(("inventory", k, float(gap), float(b)))
        return bad, worst
