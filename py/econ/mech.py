import copy

from core import detmath as DM

PARAMS = {
    "beta_w": 0.394,
    "kappa": 0.0,
    "rho": 0.78,
    "anchor": 0.0099,
    "fx_pass": 0.013,
    "fx_lag_months": 24,
    "neer_dlog_2024": [0.0] * 12,
    "rent_weight": 0.158,
    "rent_keep_annual": 0.9,
    "rent_drift_annual": -0.007,
    "rent_yoy_2024_12": 0.003,
    "rent_gap_0": 0.0,
    "rent_market": "level",
    "rent_market_growth": 0.003,
    "caps": {"F30-59": 0.902, "M30-59": 0.954, "F60-69": 0.712, "M60-69": 0.853, "F70+": 0.254, "M70+": 0.254},
    "cap_on": True,
    "freeze_e": False,
}
LABELS = {
    "beta_w": "D: Sasaki-Yamamoto-Nakajima BoJ WP 23-E-9, linear 1991-2019; no (1 - z0) (M046)",
    "kappa": "direction only, held at 0 (M046: 0.11 double-counts the wage channel)",
    "rho": "D: Kurozumi-Oishi BoJ WP 22-E-3, quarterly: E set at each quarter's first month from the last quarter's mean of 12 x the monthly core log change, held 3 months (M048)",
    "anchor": "D: Kurozumi-Oishi 2010-19 (a pre-2022 sample; decides X-dir's direction)",
    "fx_pass": "D: WP 23-E-9 linear; 24 months uniform lag weights (Guess)",
    "neer_dlog_2024": "declared input: econ holds no NEER series (only trading_house's JPY/USD spot, held); default zero moves",
    "rent_weight": "D: imputed rent only (MIC 2020 base)",
    "rent_keep_annual": "D: Shimizu-Nishimura-Watanabe 2010; deterministic share (M046)",
    "rent_drift_annual": "D: MIC 2021, non-wooden ageing",
    "rent_yoy_2024_12": "D: national CPI rent +0.3% y/y Oct 2024 (R101, secondary report of MIC), 2024's monthly path uniform (T)",
    "rent_gap_0": "T: the index at the market at 2024-12",
    "rent_market": "T: 'level' held at 2024-12, or 'growth' at rent_market_growth a year",
    "rent_market_growth": "T: no sourced 2024 market rent path; the index's 2024 y/y",
    "caps": "T: JILPT Data series No. 284 scenario A 2040 rates (D) as caps",
}


def cap_bands(bands, caps, cap_on):
    out = {}
    pop_all = 0.0
    pop_bind = 0.0
    for b in bands:
        pop, emp, srch = float(bands[b][0]), float(bands[b][1]), float(bands[b][2])
        pop_all += pop
        if cap_on and b in caps and emp + srch > caps[b] * pop:
            room = caps[b] * pop
            srch = room - emp if room > emp else 0.0
            emp = emp if room > emp else room
            pop_bind += pop
        out[b] = [pop, emp, srch]
    return out, (pop_bind / pop_all if pop_all > 0.0 else 0.0)


def participation(row):
    return (row[1] + row[2]) / row[0] if row[0] > 0.0 else 0.0


class Mech:
    def __init__(self, params=None, core_0=0.027):
        self.p = copy.deepcopy(PARAMS)
        if params:
            self.p.update(copy.deepcopy(params))
        self.core_0 = float(core_0)
        self.theta = 1.0 - DM.pow(float(self.p["rent_keep_annual"]), 1.0 / 12.0)
        self.month = 0
        self.e = float("nan")
        self.core = self.core_0
        self.level = 1.0
        self.pi = float("nan")
        self.pi_q = []
        self.use_start = float("nan")
        self.gap = 0.0
        self.wage_dl = []
        self.wage_ref = 0.0
        self.rent_log = 0.0
        self.market_log = float(self.p["rent_gap_0"])
        self.rent_dl = [float(self.p["rent_yoy_2024_12"]) / 12.0] * 12
        self.rent_ref = self._sum(self.rent_dl)
        self.parts = [0.0, 0.0, 0.0, 0.0, 0.0]
        self.binding_share = -1.0
        self.log = []

    def var_names(self):
        return ["p", "month", "e", "core", "level", "pi", "pi_q", "use_start", "gap", "wage_dl", "wage_ref", "rent_log", "market_log", "rent_dl",
                "rent_ref", "parts", "binding_share", "log"]

    @staticmethod
    def _sum(xs):
        s = 0.0
        for x in xs:
            s += x
        return s

    def fx_rate(self, m):
        path = self.p["neer_dlog_2024"]
        lags = int(self.p["fx_lag_months"])
        s = 0.0
        for l in range(lags):
            j = m - l
            if -12 <= j <= -1:
                s += float(path[j + 12]) / lags
        return 12.0 * float(self.p["fx_pass"]) * s

    def wage_dev(self):
        return self._sum(self.wage_dl) - self.wage_ref if self.wage_dl else 0.0

    def rent_dev(self):
        return self._sum(self.rent_dl) - self.rent_ref

    def core_at(self, capacity_use, shock=0.0):
        if self.use_start != self.use_start:
            self.use_start = capacity_use
        self.gap = capacity_use - self.use_start
        p = self.p
        fx = self.fx_rate(self.month)
        if self.e != self.e:
            self.e = self.core_0 - float(p["kappa"]) * self.gap - fx
        elif self.month % 3 == 0 and len(self.pi_q) == 3:
            # Why not rho^(1/3) each month: with the wage feedback the gain compounds per period, to 1.102 a month (M048); the sourced 0.78
            # is a quarter's
            if not p["freeze_e"]:
                a = float(p["anchor"])
                self.e = a + float(p["rho"]) * ((self.pi_q[0] + self.pi_q[1] + self.pi_q[2]) / 3.0 - a)
            self.pi_q = []
        self.parts = [self.e, float(p["kappa"]) * self.gap, float(p["beta_w"]) * self.wage_dev(), fx, float(p["rent_weight"]) * self.rent_dev()]
        self.core = self._sum(self.parts) + shock
        prev = self.level
        self.level = prev * DM.exp(self.core / 12.0)
        self.pi = 12.0 * DM.log(self.level / prev)
        self.pi_q = self.pi_q + [self.pi]
        self.log.append([self.month, self.core, self.e] + self.parts[1:])
        return self.core

    def observe_wage(self, w_before, w_after):
        dl = DM.log(w_after / w_before)
        self.observe_wage_dl(dl)

    def observe_wage_dl(self, dl):
        # Why not a declared 2024 wage path: labour holds no wage history before its first step, so its first month's change stands for
        # 2024's (T), and the deviation starts at 0
        if not self.wage_dl:
            self.wage_dl = [dl] * 12
            self.wage_ref = self._sum(self.wage_dl)
            return
        self.wage_dl = self.wage_dl[1:] + [dl]

    def rent_step(self):
        if self.p["rent_market"] == "growth":
            self.market_log += float(self.p["rent_market_growth"]) / 12.0
        d = self.theta * (self.market_log - self.rent_log) + float(self.p["rent_drift_annual"]) / 12.0
        self.rent_log += d
        self.rent_dl = self.rent_dl[1:] + [d]
        return d

    def end_month(self):
        self.rent_step()
        self.month += 1

    def cap(self, bands):
        eff, share = cap_bands(bands, self.p["caps"], bool(self.p["cap_on"]))
        self.binding_share = share
        return eff
