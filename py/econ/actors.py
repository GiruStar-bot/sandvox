# The economy's actors: the twins of sim/modern/econ/actor.gd, crop_farming.gd, food_manufacturing.gd, trading_house.gd, banks.gd
import copy
import math

from core.gd import clampf, maxf, maxi, minf

from .data import load_json
from .world import INF, gkey


class Actor:
    def __init__(self):
        self.id = ""
        self.kind = ""
        self.jurisdiction = "JPN"
        self.stocks = {}
        self.params = {}
        self.log = []

    def setup(self, spec):
        self.id = str(spec["id"])
        self.kind = str(spec["kind"])
        self.jurisdiction = str(spec.get("jurisdiction", "JPN"))
        self.stocks = copy.deepcopy(spec.get("stocks", {}))
        self.params = copy.deepcopy(spec.get("params", {}))

    def p(self, name):
        return float(self.params[name]["value"])

    def note(self, month, what, value, rule, reason):
        self.log.append([month, self.id, what, float(value), rule, reason])

    def plan(self, world, month):
        pass

    def settle(self, world, month):
        pass

    def fixed_cost(self, world):
        fixed = float(self.stocks.get("fixed_costs_bn_month", 0.0))
        if "wage_share_of_fixed" in self.params and "wage_index" in world.env:
            fixed *= 1.0 + self.p("wage_share_of_fixed") * (float(world.env["wage_index"]) - 1.0)
        return fixed

    def pay_fixed_and_finance(self, world, month, bank, monthly_revenue):
        fixed = self.fixed_cost(world)
        if fixed <= 0.0:
            return
        floor_ = fixed * float(self.stocks.get("working_floor_months", 1.0))
        cash = float(world.cash.get(self.id, 0.0))
        if cash - fixed < floor_ and bank is not None:
            got = bank.request_loan(world, month, self.id, floor_ + fixed - cash, monthly_revenue)
            self.note(month, "loan_request", floor_ + fixed - cash, "cash below the working floor", "got %.1f" % got)
        cash = float(world.cash.get(self.id, 0.0))
        paid = clampf(cash, 0.0, fixed)
        if paid > 0.0:
            world.pay(self.id, "other_sectors_and_households", paid, "fixed costs of " + self.id)
        if paid < fixed:
            self.note(month, "arrears", fixed - paid, "cash short", "ARREARS")
            self.stocks["arrears"] = float(self.stocks.get("arrears", 0.0)) + fixed - paid

    def var_names(self):
        return ["id", "kind", "jurisdiction", "stocks", "params", "log"]


class CropFarming(Actor):
    def __init__(self):
        super().__init__()
        self.crops = {}
        self.inputs_per_ha = {}
        self.last_harvest = {}

    def var_names(self):
        return super().var_names() + ["crops", "inputs_per_ha", "last_harvest"]

    def load_spec(self, name):
        d = load_json(name)
        if not isinstance(d, dict):
            return "crop_farming: no spec at " + name
        self.setup(d)
        self.crops = copy.deepcopy(d["crops"])
        self.inputs_per_ha = copy.deepcopy(d.get("inputs_per_ha", {}))
        return ""

    def plan(self, world, month):
        cal_month = month % 12 + 1
        for c in self.crops:
            spec = self.crops[c]
            if int(spec["harvest_month"]) == cal_month:
                weather = float(world.env.get("yield_factor", {}).get(c, 1.0))
                harvest = float(spec["area_ha"]) * float(spec["yield_t_ha"]) * weather
                used = float(self.last_harvest.get(c, 0.0)) * float(spec.get("reserve_share", 0.0))
                if used > 0.0:
                    world.use_own(c, self.jurisdiction, used, self.id, "seed and own use")
                world.produce(c, self.jurisdiction, harvest, self.id, "harvest")
                self.last_harvest[c] = harvest
                self.note(month, "harvest_" + c, harvest, "area x yield x weather", "harvest month")
            g = world.good(c, self.jurisdiction)
            reserve = float(self.last_harvest.get(c, 0.0)) * float(spec.get("reserve_share", 0.0))
            months_left = (int(spec["harvest_month"]) - cal_month + 12) % 12
            months_left = 12 if months_left == 0 else months_left
            others = 0.0
            for ob_id in g.get("held_by", {}):
                if ob_id != self.id:
                    others += float(g["held_by"][ob_id])
            saleable = maxf(0.0, float(g["inventory"]) - others - reserve)
            offer = saleable / float(months_left)
            if offer > 0.0:
                world.offer(c, self.jurisdiction, offer, self.id)
                self.note(month, "offer_" + c, offer, "saleable / months to the next harvest", "")
            if (int(spec["sow_month"]) - 1 + 12) % 12 + 1 == cal_month or (int(spec["sow_month"]) == 1 and cal_month == 12):
                for inp in self.inputs_per_ha:
                    need = float(spec["area_ha"]) * float(self.inputs_per_ha[inp]["value"])
                    world.demand(inp, self.jurisdiction, need, self.id)
                    self.note(month, "demand_" + inp + "_" + c, need, "area x requirement per ha", "before sowing " + c)

    def settle(self, world, month):
        for c in self.crops:
            g = world.good(c, self.jurisdiction)
            sold = float(g.get("traded_by", {}).get(self.id, 0.0))
            if sold > 0.0:
                world.pay("market:" + c, self.id, sold * float(g["price"]), "sales of " + c)
                self.note(month, "sold_" + c, sold, "market clearing", "at the held price")


class FoodManufacturing(Actor):
    def __init__(self):
        super().__init__()
        self.inputs = {}
        self.self_use = 0.0
        self.planned = 0.0
        self.output = 0.0
        self.input_fill = {}
        self.projects = []

    def var_names(self):
        return super().var_names() + ["inputs", "self_use", "planned", "output", "input_fill", "projects"]

    def load_spec(self, name):
        d = load_json(name)
        if not isinstance(d, dict):
            return "food_manufacturing: no spec at " + name
        self.setup(d)
        self.inputs = copy.deepcopy(d["inputs"])
        self.self_use = float(d.get("self_use_coef", 0.0))
        return ""

    def unit_cost(self, world):
        inp = 0.0
        for c in self.inputs:
            inp += float(self.inputs[c]["coef"]) * float(world.good(c, self.jurisdiction)["price"])
        cap = float(self.stocks["capacity_bn_jpy_month"])
        return (inp + self.fixed_cost(world) / cap) / (1.0 - self.self_use)

    def plan(self, world, month):
        world.good("food_products", self.jurisdiction)["unit_cost"] = self.unit_cost(world)
        cap = float(self.stocks["capacity_bn_jpy_month"])
        expect = float(self.stocks.get("demand_expectation", cap * (1.0 - self.self_use)))
        still = []
        for pr in self.projects:
            if int(pr["finish_month"]) <= month:
                self.stocks["capacity_bn_jpy_month"] = float(self.stocks["capacity_bn_jpy_month"]) + float(pr["add_bn_month"])
                cap = float(self.stocks["capacity_bn_jpy_month"])
                self.note(month, "capacity", cap, "project finished", "INVEST done")
            else:
                still.append(pr)
        self.projects = still
        proc_factor = 0.8 if int(self.stocks.get("procedure_until", -1)) > month else 1.0
        g0 = world.good("food_products", self.jurisdiction)
        target_inv = float(self.stocks.get("inventory_target_months", 0.5)) * expect
        gap = maxf(0.0, target_inv - float(g0["inventory"]))
        self.planned = minf(cap * proc_factor, (expect + gap) / (1.0 - self.self_use))
        use_hist = self.stocks.get("use_hist", [])
        if (len(use_hist) >= 3 and float(use_hist[-1]) >= 0.95 and float(use_hist[-2]) >= 0.95 and float(use_hist[-3]) >= 0.95
                and expect / (1.0 - self.self_use) > 1.02 * cap and not self.projects):
            add = 0.05 * cap
            cost = add * float(self.stocks.get("capex_per_bn_month_capacity", 18.0))
            self.projects.append({"add_bn_month": add, "finish_month": month + 12, "cost_bn": cost, "start_month": month})
            world.pay(self.id, "capital_goods", cost, "capacity project")
            self.note(month, "invest", cost, "3 months >= 95% use and expected demand above capacity", "INVEST")
        for c in self.inputs:
            need = self.planned * float(self.inputs[c]["coef"]) * float(self.inputs[c].get("domestic_share", 1.0))
            if need > 0.0:
                world.demand(c, self.jurisdiction, need, self.id)
        self.note(month, "planned_output", self.planned, "min(capacity, demand expectation)", "")
        g = world.good("food_products", self.jurisdiction)
        offer_qty = maxf(float(g["inventory"]) - target_inv, minf(float(g["inventory"]), expect))
        if offer_qty > 0.0:
            world.offer("food_products", self.jurisdiction, offer_qty, self.id)

    def settle(self, world, month):
        fill = 1.0
        scarcest = ""
        self.input_fill = {}
        for c in self.inputs:
            share = float(self.inputs[c].get("domestic_share", 1.0))
            f = 1.0 if bool(self.inputs[c].get("external", False)) else share * world.fill_share(c, self.jurisdiction) + (1.0 - share)
            self.input_fill[c] = f
            if f < fill:
                fill = f
                scarcest = c
        self.output = self.planned * fill
        world.produce("food_products", self.jurisdiction, self.output * (1.0 - self.self_use), self.id, "gross x input fill, less own use")
        self.note(month, "output", self.output, "planned x min input fill", "scarcest input: " + (scarcest if scarcest != "" else "none"))
        for c in self.inputs:
            g = world.good(c, self.jurisdiction)
            if not bool(self.inputs[c].get("external", False)):
                bought = self.planned * float(self.inputs[c]["coef"]) * float(self.inputs[c].get("domestic_share", 1.0)) * world.fill_share(c, self.jurisdiction)
            else:
                bought = self.planned * float(self.inputs[c]["coef"])
            if bought > 0.0:
                world.pay(self.id, "market:" + c, bought * float(g["price"]), "purchase of " + c)
        gp = world.good("food_products", self.jurisdiction)
        sold = float(gp["traded"])
        if sold > 0.0:
            world.pay("market:food_products", self.id, sold * float(gp["price"]), "sales of food products")
        seen = sold + float(gp["unmet"])
        self.stocks["demand_expectation"] = seen if seen > 0.0 else float(self.stocks.get("demand_expectation", self.planned))
        self.stocks["capacity_use"] = self.output / maxf(1e-9, float(self.stocks["capacity_bn_jpy_month"]))
        uh = self.stocks.get("use_hist", [])
        uh.append(self.stocks["capacity_use"])
        if len(uh) > 12:
            uh.pop(0)
        self.stocks["use_hist"] = uh


class TradingHouse(Actor):
    def __init__(self):
        super().__init__()
        self.goods_spec = {}
        self.fx_jpy_usd = 150.0
        self.orders = []
        self.last_margin = {}

    def var_names(self):
        return super().var_names() + ["goods_spec", "fx_jpy_usd", "orders", "last_margin"]

    def load_spec(self, name):
        d = load_json(name)
        if not isinstance(d, dict):
            return "trading_house: no spec at " + name
        self.setup(d)
        self.goods_spec = copy.deepcopy(d["goods"])
        self.fx_jpy_usd = float(d["fx_jpy_usd"]["value"])
        for c in self.goods_spec:
            q = float(self.goods_spec[c].get("start_in_transit_t", 0.0))
            if q > 0.0:
                self.orders.append({"commodity": c, "qty": q, "arrive_month": 0, "order_month": -1, "cost_bn": q * self.landed_cost_bn_per_t(c)})
        return ""

    def landed_cost_bn_per_t(self, c):
        g = self.goods_spec[c]
        return (float(g["foreign_price_usd_t"]) + float(g["freight_usd_t"])) * self.fx_jpy_usd / 1e9 + float(g["tariff_jpy_t"]) / 1e9

    def plan(self, world, month):
        still = []
        arrived = {}
        for o in self.orders:
            if int(o["arrive_month"]) <= month:
                oc = str(o["commodity"])
                if bool(self.goods_spec[oc].get("to_state_stock", False)):
                    self.stocks["state_stock_" + oc] = float(self.stocks.get("state_stock_" + oc, 0.0)) + float(o["qty"])
                    self.note(month, "state_stock_" + oc, float(self.stocks["state_stock_" + oc]), "quota import to the state's stock", "ARRIVE state stock")
                    continue
                world.produce(oc, self.jurisdiction, float(o["qty"]), self.id, "import arrived")
                g0 = world.good(oc, self.jurisdiction)
                g0["imported"] += float(o["qty"])
                self.stocks["inv_" + oc] = float(self.stocks.get("inv_" + oc, 0.0)) + float(o["qty"])
                arrived[oc] = float(arrived.get(oc, 0.0)) + float(o["qty"])
                self.note(month, "arrive_" + oc, float(o["qty"]), "lead time over", "ARRIVE")
            else:
                still.append(o)
        self.orders = still
        for c in self.goods_spec:
            g = world.good(c, self.jurisdiction)
            own = float(self.stocks.get("inv_" + c, 0.0))
            if own > 0.0:
                world.offer(c, self.jurisdiction, own, self.id)
            cost = self.landed_cost_bn_per_t(c)
            p_exp = float(world.env.get("expected_price", {}).get(gkey(c, self.jurisdiction), g["price"]))
            margin = p_exp - cost
            self.last_margin[c] = margin
            if margin <= 0.0 and not bool(self.goods_spec[c].get("state_trading", False)):
                self.note(month, "margin_" + c, margin, "domestic price - landed cost", "MARGIN_NEG")
                continue
            in_transit = self._in_transit(c)
            sold_last = float(g.get("traded_by", {}).get(self.id, self.goods_spec[c].get("start_in_transit_t", 0.0)))
            carried = maxf(0.0, own - float(arrived.get(c, 0.0)))
            want = maxf(0.0, sold_last + float(g["unmet_last"]) - carried - in_transit)
            if bool(self.goods_spec[c].get("to_state_stock", False)):
                want = float(self.goods_spec[c]["foreign_capacity_t_month"])
            cap_f = float(self.goods_spec[c]["foreign_capacity_t_month"])
            cap_l = float(world.logistics.get(c, INF))
            cash = float(world.cash.get(self.id, 0.0))
            afford = cash / cost if cost > 0.0 else INF
            qty = minf(minf(want, cap_f), minf(cap_l, afford))
            if qty <= 0.0:
                self.note(month, "order_" + c, 0.0, "nothing wanted", "ORDER none")
                continue
            lead = int(self.goods_spec[c].get("lead_months", 1))
            self.orders.append({"commodity": c, "qty": qty, "arrive_month": month + lead, "order_month": month, "cost_bn": qty * cost})
            world.pay(self.id, "foreign:" + c, qty * cost, "import order of " + c)
            world.add_contract(self.id, "foreign:" + c, c, qty, cost, month + lead, "forward")
            self.note(month, "order_" + c, qty, "min(want, foreign cap, logistics, cash)", "ORDER")
        for c in self.goods_spec:
            if not bool(self.goods_spec[c].get("to_state_stock", False)):
                world.good(c, self.jurisdiction)["in_transit"] = self._in_transit(c)

    def _in_transit(self, c):
        q = 0.0
        for o in self.orders:
            if str(o["commodity"]) == c:
                q += float(o["qty"])
        return q

    def settle(self, world, month):
        for c in self.goods_spec:
            g = world.good(c, self.jurisdiction)
            sold = float(g.get("traded_by", {}).get(self.id, 0.0))
            if sold > 0.0:
                self.stocks["inv_" + c] = float(self.stocks.get("inv_" + c, 0.0)) - sold
                world.pay("market:" + c, self.id, sold * float(g["price"]), "sales of imported " + c)
                self.note(month, "sold_" + c, sold, "market clearing", "")


class Bank(Actor):
    def __init__(self):
        super().__init__()
        self.loans = []
        self.score = {}
        self.policy_rate = 0.0025
        self.policy_path = []
        self.spread_by_score = []
        self.term_months = 60
        self.floor_months = 1.0
        self.minted = 0.0
        self.equity0 = 0.0
        self.rule = "taylor"

    def var_names(self):
        return super().var_names() + ["loans", "score", "policy_rate", "policy_path", "spread_by_score", "term_months", "floor_months", "minted",
                                      "equity0", "rule"]

    def load_spec(self, name):
        d = load_json(name)
        if not isinstance(d, dict):
            return "banks: no spec at " + name
        self.setup(d)
        self.policy_rate = float(d["policy_rate"]["value"])
        self.policy_path = copy.deepcopy(d.get("policy_path", []))
        self.spread_by_score = copy.deepcopy(d["spread_by_score"])
        self.term_months = int(d["term_months"]["value"])
        self.floor_months = float(d["floor_months"]["value"])
        self.equity0 = float(self.stocks.get("cash_bn_jpy", 0.0))
        return ""

    def rate_for(self, s):
        spread = float(self.spread_by_score[0][1])
        for row in self.spread_by_score:
            if s >= float(row[0]):
                spread = float(row[1])
        return self.policy_rate + spread

    def debt_of(self, borrower):
        t = 0.0
        for L in self.loans:
            if str(L["borrower"]) == borrower and str(L["status"]) == "open":
                t += float(L["remaining"])
        return t

    def plan(self, world, month):
        on_path = False
        last_path = -1
        for row in self.policy_path:
            last_path = maxi(last_path, int(row[0]))
            if int(row[0]) == month:
                self.policy_rate = float(row[1])
                on_path = True
                self.note(month, "policy_rate", self.policy_rate, "published path", "central bank")
        if not on_path and month > last_path and self.rule == "taylor" and (month - last_path) % 3 == 0:
            pi = float(world.env.get("inflation", 0.02))
            target = maxf(0.0, pi + 0.5 * (pi - 0.02))
            step = clampf(target - self.policy_rate, -0.0025, 0.0025)
            if abs(step) >= 0.00125:
                self.policy_rate += step
                self.note(month, "policy_rate", self.policy_rate, "Taylor-type rule", "central bank")

    def request_loan(self, world, month, borrower, amount, monthly_revenue):
        amount = float(amount)
        sc = self.score.get(borrower, {"score": 1.0, "cut_off_until": -1})
        if int(sc["cut_off_until"]) > month:
            self.note(month, "refuse_" + borrower, amount, "cut off after a default", "REFUSE")
            return 0.0
        debt = self.debt_of(borrower) + amount
        r = self.rate_for(float(sc["score"]))
        service = debt / float(self.term_months) + debt * r / 12.0
        s = clampf(1.0 - service / maxf(monthly_revenue, 1e-9), 0.0, 1.0)
        if s < 0.2:
            self.note(month, "refuse_" + borrower, amount, "debt service above 80% of revenue", "REFUSE")
            return 0.0
        sc["score"] = s
        self.score[borrower] = sc
        L = {"id": len(self.loans), "borrower": borrower, "principal": amount, "remaining": amount, "rate": self.rate_for(s), "term": self.term_months,
             "start_month": month, "paid": 0.0, "status": "open"}
        self.loans.append(L)
        own = float(world.cash.get(self.id, 0.0))
        if own < amount:
            world.pay("central_bank", self.id, amount - own, "funding the bank (minted)")
            self.minted += amount - own
            self.note(month, "mint", amount - own, "lender of last resort", "MINT")
        world.pay(self.id, borrower, amount, "loan")
        self.note(month, "loan_" + borrower, amount, "min score 0.2; rate = policy + spread by score", "LOAN")
        return amount

    def settle(self, world, month):
        for L in self.loans:
            if str(L["status"]) != "open":
                continue
            b = str(L["borrower"])
            instalment = float(L["principal"]) / float(L["term"])
            interest = float(L["remaining"]) * float(L["rate"]) / 12.0
            due = minf(float(L["remaining"]), instalment) + interest
            cash = float(world.cash.get(b, 0.0))
            if cash >= due:
                world.pay(b, self.id, due, "loan instalment + interest")
                L["remaining"] = float(L["remaining"]) - minf(float(L["remaining"]), instalment)
                L["paid"] = float(L["paid"]) + due
                if float(L["remaining"]) <= 1e-9:
                    L["status"] = "repaid"
                self.note(month, "pay_" + b, due, "equal principal + interest", "PAY")
            else:
                L["status"] = "default"
                sc = self.score.get(b, {"score": 1.0, "cut_off_until": -1})
                sc["score"] = 0.0
                sc["cut_off_until"] = month + 12
                self.score[b] = sc
                self.stocks["write_offs"] = float(self.stocks.get("write_offs", 0.0)) + float(L["remaining"])
                self.note(month, "default_" + b, float(L["remaining"]), "cash below the instalment", "DEFAULT")
