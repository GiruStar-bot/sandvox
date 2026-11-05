# W-c's shadow ledger (WORLD_PORT_PLAN §5, AMENDED A6 as ECON_PORT_PLAN's, M039): every posting the world makes to a stock is replayed
# in exact rationals beside the float stock, with the stock's accumulated rounding bound. Check-only: the state stays the oracle's floats.
# Why not A5's 2·n·u·Σ|t_k| on a day's residual: it bounds the residual's own sum, not the rounding inside the stocks (M039 §1)
from fractions import Fraction

U = Fraction(1, 2 ** 53)
ACTIVE = None


class Ledger:
    def __init__(self):
        self.sh = {}
        self.bnd = {}
        self.flt = {}
        self.posts = 0
        self.gap = {}
        self.linkin = {}

    def start(self, key, v):
        self.sh[key] = Fraction(v)
        self.bnd[key] = Fraction(0)
        self.flt[key] = v

    def add(self, key, y, after):
        # after = fl(before + y): its error is at most u·|after|, added to the stock's carried error
        if key not in self.sh:
            return
        self.sh[key] += Fraction(y)
        self.bnd[key] += U * abs(Fraction(after))
        self.flt[key] = after
        self.posts += 1

    def mul(self, key, f, after):
        # after = fl(before · f): the carried error scales by |f|, plus u·|after|
        if key not in self.sh:
            return
        self.sh[key] *= Fraction(f)
        self.bnd[key] = abs(Fraction(f)) * self.bnd[key] + U * abs(Fraction(after))
        self.flt[key] = after
        self.posts += 1

    def merge(self, key, src, after):
        # after = fl(stock + src's float): the shadow takes src's shadow, so a move between stocks stays exact in rationals
        if key not in self.sh:
            return
        self.sh[key] += self.sh[src]
        self.bnd[key] += self.bnd[src] + U * abs(Fraction(after))
        self.flt[key] = after
        self.posts += 1

    def move(self, key, src):
        self.sh[key] = self.sh[src]
        self.bnd[key] = self.bnd[src]
        self.flt[key] = self.flt[src]

    def check(self, read):
        # W-c-f: |float − shadow| ≤ (1 + 2u)·B per stock, where read(key) is the stock as the world holds it now (a write with no
        # posting shows here, since the posted float then differs from the held one)
        bad = []
        worst = 0.0
        for key in self.sh:
            v = read(key)
            if v is None:
                continue
            if v != self.flt[key]:
                bad.append((key, "the held float differs from the last posting", v, self.flt[key]))
                continue
            err = abs(Fraction(v) - self.sh[key])
            lim = (1 + 2 * U) * self.bnd[key]
            if err > lim:
                bad.append((key, float(err), float(lim)))
            elif lim > 0:
                worst = max(worst, float(err / lim))
        return bad, worst
