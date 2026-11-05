# The monthly economy: the twin of sim/modern/econ/econ_month.gd (the month's order, expectations, the seeded shocks, held demand)
import copy

from core import detmath as DM
from core import keyed as KEYED
from core.gd import maxf, minf

from . import data
from .actors import Bank, CropFarming, FoodManufacturing, TradingHouse
from .mech import Mech
from .world import World, gkey


class EconMonth:
    def __init__(self):
        self.world = None
        self.actors = []
        self.bank = None
        self.core_inflation = 0.027
        self.final_demand = {}
        self.labour = None
        self.shocks = []
        self.error = ""
        self.mech = None

    def enable_mech(self, params=None):
        self.mech = Mech(params, self.core_inflation)
        if self.labour is not None:
            self.labour.caps = self.mech

    def trading_house(self):
        for a in self.actors:
            if a.id.startswith("trading_houses"):
                return a
        return None

    def release_state_rice(self, month, qty_t):
        th = self.trading_house()
        if th is None:
            return 0.0
        have = float(th.stocks.get("state_stock_rice", 0.0))
        q = minf(have, float(qty_t))
        if q <= 0.0:
            return 0.0
        th.stocks["state_stock_rice"] = have - q
        th.stocks["inv_rice"] = float(th.stocks.get("inv_rice", 0.0)) + q
        self.world.produce("rice", th.jurisdiction, q, th.id, "state stock release")
        th.note(month, "release_rice", q, "the government's release decision", "RELEASE")
        return q

    def create(self, jurisdiction="JPN"):
        j = jurisdiction.lower()
        self.world = World()
        self.error = self.world.create()
        if self.error != "":
            return self.error
        cf = CropFarming()
        self.error = cf.load_spec("crop_farming_%s.json" % j)
        if self.error != "":
            return self.error
        fm = FoodManufacturing()
        self.error = fm.load_spec("food_manufacturing_%s.json" % j)
        if self.error != "":
            return self.error
        self.actors = [cf, fm]
        if data.exists("trading_house_%s.json" % j):
            th = TradingHouse()
            self.error = th.load_spec("trading_house_%s.json" % j)
            if self.error != "":
                return self.error
            self.actors.append(th)
        if data.exists("banks_%s.json" % j):
            self.bank = Bank()
            self.error = self.bank.load_spec("banks_%s.json" % j)
            if self.error != "":
                return self.error
            self.world.cash[self.bank.id] = float(self.bank.stocks.get("cash_bn_jpy", 0.0))
        lg = data.load_json("logistics_%s.json" % j)
        if isinstance(lg, dict):
            for c in lg["cap_t_month"]:
                self.world.logistics[c] = float(lg["cap_t_month"][c]["value"])
        fd = data.load_json("final_demand_%s.json" % j)
        if isinstance(fd, dict):
            for c in fd["monthly"]:
                self.final_demand[c] = float(fd["monthly"][c]["value"])
        for a in self.actors:
            self.world.cash[a.id] = float(a.stocks.get("cash_bn_jpy", 0.0))
        for c in cf.crops:
            spec = cf.crops[c]
            h = float(spec["area_ha"]) * float(spec["yield_t_ha"])
            st = {"harvest_t": h, "reserve_t": h * float(spec.get("reserve_share", 0.0)), "harvest_month": int(spec["harvest_month"]),
                  "import_t_month": 0.0, "lead_months": 0}
            th0 = self.trading_house()
            if th0 is not None and c in th0.goods_spec and not bool(th0.goods_spec[c].get("to_state_stock", False)):
                st["import_t_month"] = float(th0.goods_spec[c].get("start_in_transit_t", 0.0))
                st["lead_months"] = int(th0.goods_spec[c].get("lead_months", 1))
            st["use_t_month"] = (h - float(st["reserve_t"])) / 12.0 + float(st["import_t_month"])
            self.world.storage[c] = st
        self.world.cost_plus["food_products"] = {"markup": float(self.world.commodities["food_products"]["start_price"]) / fm.unit_cost(self.world) - 1.0}
        inv = data.load_json("start_inventory_%s.json" % j)
        if isinstance(inv, dict):
            for c in inv["inventory"]:
                g = self.world.good(c, jurisdiction)
                g["inventory"] = float(inv["inventory"][c]["value"])
                if "last_harvest" in inv["inventory"][c]:
                    cf.last_harvest[c] = float(inv["inventory"][c]["last_harvest"])
        return ""

    def declare_shock(self, from_month, to_month, yield_factor, why):
        self.shocks.append({"from_month": int(from_month), "to_month": int(to_month), "yield_factor": dict(yield_factor), "why": why})

    def declare_cash_loss(self, month, actor_id, amount_bn, why):
        self.shocks.append({"from_month": int(month), "to_month": int(month), "cash_loss": {actor_id: float(amount_bn)}, "why": why})

    def seed_shocks(self, seed, years, name=""):
        sp = data.load_json(name if name != "" else "shocks_%s.json" % self.actors[0].jurisdiction.lower())
        if not isinstance(sp, dict):
            self.error = "econ: no seeded shocks"
            return
        cf = self.actors[0]
        for y in range(years):
            yf = {}
            why = []
            for c in sp["yield"]:
                r = sp["yield"][c]
                z = KEYED.normal(seed, "yield:" + c, y, 0, 0)
                f = DM.exp(float(r["sigma"]) * z)
                if KEYED.u(seed, "badyear:" + c, y, 0, 0) < float(r["bad_year_p"]):
                    f *= float(r["bad_year_factor"])
                    why.append("%s bad year" % c)
                yf[c] = f
            for c in yf:
                if c not in cf.crops:
                    continue
                hm = y * 12 + int(cf.crops[c]["harvest_month"]) - 1
                self.shocks.append({"from_month": hm, "to_month": hm, "yield_factor": {c: yf[c]}, "why": "seeded yield draw"})
            for who in sp.get("cash_loss", {}):
                r2 = sp["cash_loss"][who]
                if KEYED.u(seed, "loss:" + who, y, 0, 0) < float(r2["p_per_year"]):
                    m = y * 12 + KEYED.below(12, seed, "lossmonth:" + who, y, 0, 0)
                    self.shocks.append({"from_month": m, "to_month": m, "cash_loss": {who: float(r2["size_bn"])}, "why": "seeded loss event"})

    def _expectations(self):
        ex = {}
        for k in self.world.goods:
            g = self.world.goods[k]
            c = k.split("|")[0]
            lam = float(self.world.commodities.get(c, {}).get("forecast_lambda", 0.5))
            p = float(g["price"])
            pp = float(g.get("price_prev", p))
            ex[k] = p + lam * (p - pp)
        self.world.env["expected_price"] = ex

    def step(self):
        w = self.world
        m = w.month
        yf = {}
        for s in self.shocks:
            if m >= int(s["from_month"]) and m <= int(s["to_month"]):
                for c in s.get("yield_factor", {}):
                    yf[c] = float(yf.get(c, 1.0)) * float(s["yield_factor"][c])
                for who in s.get("cash_loss", {}):
                    w.pay(who, "losses", float(s["cash_loss"][who]), "declared loss")
        w.env = {"yield_factor": yf}
        if self.labour is not None:
            w.env["wage_index"] = self.labour.wage_index
        self._expectations()
        j = self.actors[0].jurisdiction
        fp = w.good("food_products", j)
        yoy = float(fp["price"]) / maxf(1e-9, float(fp.get("price_12m", fp["price"]))) - 1.0
        if self.mech is not None:
            self.core_inflation = self.mech.core_at(float(self.actors[1].stocks.get("capacity_use", 1.0)))
        w.env["inflation"] = 0.75 * self.core_inflation + 0.25 * yoy
        w.env["food_price_yoy"] = yoy
        if self.bank is not None:
            self.bank.plan(w, m)
        for a in self.actors:
            a.plan(w, m)
        for c in self.final_demand:
            g = w.good(c, j)
            e = float(w.commodities.get(c, {}).get("demand_elasticity", 0.0))
            if self.labour is not None and c in self.labour.demand_scale:
                e = 0.0
            p0 = float(w.commodities.get(c, {}).get("start_price", g["price"]))
            q = self.final_demand[c] * (DM.pow(float(g["price"]) / p0, e) if e != 0.0 and p0 > 0.0 else 1.0)
            if self.labour is not None and c in self.labour.demand_scale:
                sc = float(self.labour.demand_scale[c])
                if abs(sc - 1.0) > 1e-9:
                    w.record_note("goods", gkey(c, j), "final_demand_scale", 1.0, sc, "persons", "the persons' weighted consumption plan")
                q *= sc
            w.demand(c, j, q, "final_demand")
        w.clear_markets()
        if self.labour is not None and self.mech is None:
            self.labour.step(m, float(self.actors[1].stocks.get("capacity_use", 1.0)), float(w.env.get("inflation", 0.02)))
        elif self.labour is not None:
            # Why not the headline inflation into wages with mech on: M046's loop gain G = rho (1 + beta_w w_pi) has wages follow
            # w_pi x the expectations state E
            w0 = self.labour.wage_index
            self.labour.step(m, float(self.actors[1].stocks.get("capacity_use", 1.0)), self.mech.parts[0])
            self.mech.observe_wage(w0, self.labour.wage_index)
        for a in self.actors:
            a.settle(w, m)
        for a in self.actors:
            if a is not self.bank:
                a.pay_fixed_and_finance(w, m, self.bank, self.revenue_of(a))
        if self.bank is not None:
            self.bank.settle(w, m)
        if self.mech is not None:
            self.mech.end_month()
        w.next_month()

    def revenue_of(self, a):
        r = 0.0
        for t in self.world.transfers:
            if int(t[0]) == self.world.month and str(t[2]) == a.id and str(t[1]).startswith("market:"):
                r += float(t[3])
        return r

    def chronicle_rows(self, base_year, m):
        # Why not the actors' log rows too: they are text only, and the world reads only the goods' price rows
        out = []
        for r in self.world.records:
            if int(r[0]) == m:
                out.append({"month": m, "date": "%04d-%02d" % (base_year + m // 12, m % 12 + 1), "ledger": r[1], "key": r[2], "field": r[3],
                            "before": r[4], "after": r[5], "by": r[6], "why": r[7]})
        return out
