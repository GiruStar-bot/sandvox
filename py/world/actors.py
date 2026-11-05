# modern_actors.gd: the rule actors (none, placeholder, r55), the alliances and the hashed restriction draw
from . import data as MD
from . import hashes
from .chain import GOODS_LICENSED, key as lic_key
from ._core import DM, gd
from .gdtypes import F64, U8, deep

RULE_SETS = ["none", "placeholder", "r55"]
CHERP_CAP = {"wind": 0.008, "solar": 0.006}
COAL_AGE_YR = 40.0
COUNTER_DAYS = 29
FOLLOW_DAYS = 309
CONTAGION = 0.02
RESTRICT_DAYS = 365
JOGMEC_DAYS = 60.0
LOGIT_GAMMA = -3.0
MC_LOGIT = ["coal", "gas", "wind", "solar"]
MONTH_ENDS = [31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334, 365]
NOISE = 1e-9


def is_month_end(day):
    return day > 0 and (((day - 1) % 365) + 1) in MONTH_ENDS


def _src(g):
    return "atp" if g == "chips" else g


class Actors:
    def __init__(self):
        self.rule_set = "placeholder"
        self.seen_closed = {}
        self.answers = {}
        self.costs = None
        self.fab = {}
        self._learn = {}
        self.plan = {}
        self.queued = []
        self.follows = {}
        self.seen_follow = {}
        self.allies = []
        self.in_regime = U8()
        self.restrict_p = {}
        self.general = {}
        self._pend = {}
        self._fab_gap = 0.0
        self._fab_now = 0.0

    def begin_month(self, f):
        self._learn = {}
        S = len(MD.SOURCES)
        if self.costs is not None:
            for src in ("solar", "wind"):
                s = MD.SOURCES.index(src)
                now = 0.0
                start = 0.0
                for e0 in range(f.E):
                    now += f.supply_of(e0, s)
                    start += f.supply0[e0 * S + s]
                self._learn[src] = self.costs.learning(src, now / start if start > 0.0 else 1.0)
        self._pend = {}
        for p in f.projects:
            k = "%d|%s" % (int(p[0]), str(p[1]))
            self._pend[k] = float(self._pend.get(k, 0.0)) + float(p[2])
        lead = int(f.data.lead_days["fab"]["days"])
        cap = 0.0
        self._fab_now = 0.0
        life_yr = float(f.SERVER_LIFE_DAYS) / 365.0
        need = 0.0
        for e in range(f.E):
            need += f.wanted_it(e, f.day + lead) * (1.0 / life_yr + DM.log(1.0 + f.cgrow[e])) / f.k_it
            cap += f.fab_cap[e] + self._pending(e, "fab")
            self._fab_now += f.fab_cap[e]
        self._fab_gap = need - cap if need - cap > NOISE * need else 0.0

    def _pending(self, e, kind):
        return float(self._pend.get("%d|%s" % (e, kind), 0.0))

    def pipeline_mix(self, f):
        S = len(MD.SOURCES)
        out = F64(f.mix)
        for e in range(f.E):
            part = 0.0
            for src in MC_LOGIT:
                part += f.mix[e * S + MD.SOURCES.index(src)]
            if part <= 0.0 and f.gen0[e] > 0.0:
                continue
            wt = {}
            tot = 0.0
            for src2 in MC_LOGIT:
                if src2 == "wind" or src2 == "solar" or f.mix[e * S + MD.SOURCES.index(src2)] > 0.0:
                    wt[src2] = DM.pow(self.costs.lcoe(e, src2), LOGIT_GAMMA)
                    tot += float(wt[src2])
            grow_yr = f.base0[e] * f.demand_growth[e]
            spare = 0.0
            for src3 in MC_LOGIT:
                sh = part * float(wt.get(src3, 0.0)) / tot
                if src3 in CHERP_CAP and grow_yr > 0.0 and sh * grow_yr > float(CHERP_CAP[src3]) * f.gen0[e]:
                    spare += sh - float(CHERP_CAP[src3]) * f.gen0[e] / grow_yr
                    sh = float(CHERP_CAP[src3]) * f.gen0[e] / grow_yr
                out[e * S + MD.SOURCES.index(src3)] = sh
            if spare > 0.0:
                rest = 0.0
                for src4 in ("coal", "gas"):
                    rest += float(wt.get(src4, 0.0))
                if rest <= 0.0:
                    out[e * S + MD.SOURCES.index("gas")] += spare
                else:
                    for src5 in ("coal", "gas"):
                        out[e * S + MD.SOURCES.index(src5)] += spare * float(wt.get(src5, 0.0)) / rest
        return out

    def rule_actions(self, f, e):
        if self.rule_set == "none":
            return []
        if self.rule_set == "r55":
            return self._r55(f, e)
        out = []
        self._power(f, e, out)
        self._dc(f, e, out)
        self._fab(f, e, out)
        self._answers(f, e, out)
        return out

    def note_applied(self, e, actions, answering):
        for a in actions:
            if answering and str(a["act"]) == "licence" and not bool(a["open"]):
                if bool(a.get("answer", False)):
                    self.answers[lic_key(e, str(a["good"]), int(a["to"]))] = True
                if bool(a.get("follow", False)):
                    self.follows[lic_key(e, str(a["good"]), int(a["to"]))] = True

    def load_alliances(self, data, al):
        E = data.entity_count()
        start = "%04d-01-01" % data.base_year
        orgs = {}
        self.in_regime = U8([0] * E)
        for r in al["rows"]:
            e = data.index_of(str(r["iso3"]))
            if e < 0 or r["joined_by"] is None or str(r["joined_by"]) > start or (r["left"] is not None and str(r["left"]) <= start):
                continue
            if str(r["org"]) in al["regimes"]:
                self.in_regime[e] = 1
            elif str(r["type"]) in al["ally_types"] and str(r["org"]) not in al["not_allies"]:
                m = orgs.get(str(r["org"]), {})
                m[e] = True
                orgs[str(r["org"])] = m
        self.allies = [{} for _ in range(E)]
        for org in orgs:
            for a in orgs[org]:
                for b in orgs[org]:
                    if a != b:
                        self.allies[a][b] = True

    def _power(self, f, e, out):
        S = len(MD.SOURCES)
        ahead = f.day + 365
        base_then = f.base0[e] * DM.pow(1.0 + f.demand_growth[e], float(ahead) / 365.0)
        it_then = gd.minf(f.wanted_it(e, ahead), (f.dc_it[e] + self._pending(e, "dc")) * f.u_max)
        load = base_then + it_then * f.pue[e] + (f.fab_cap[e] + self._pending(e, "fab")) * f.fab_mw_per_unit
        sup = f.net_imports[e] + (base_then - f.base0[e] if f.gen0[e] == 0.0 else 0.0)
        cur = [0.0] * S
        cur_all = 0.0
        for s in range(S):
            grown = f.supply0[e * S + s] + (base_then - f.base0[e]) * f.mix[e * S + s]
            sup += gd.maxf(0.0, grown) + f.supply_built[e * S + s] + self._pending(e, MD.SOURCES[s])
            cur[s] = f.supply_of(e, s)
            cur_all += cur[s]
        short = load - sup
        if short <= NOISE * gd.maxf(1.0, load):
            return
        if cur_all <= 0.0:
            out.append({"act": "build", "kind": "gas", "size": short})
            return
        for s2 in range(S):
            if cur[s2] > 0.0:
                out.append({"act": "build", "kind": MD.SOURCES[s2], "size": short * cur[s2] / cur_all})

    def _dc(self, f, e, out):
        lead = int(f.data.lead_days["dc"]["days"])
        want_cap = f.wanted_it(e, f.day + lead) / f.u_max
        gap = want_cap - f.dc_it[e] - self._pending(e, "dc")
        if gap > NOISE * gd.maxf(1.0, want_cap):
            out.append({"act": "build", "kind": "dc", "size": gap})

    def _fab(self, f, e, out):
        if f.fab_cap[e] > 0.0 and self._fab_gap > 0.0:
            out.append({"act": "build", "kind": "fab", "size": self._fab_gap * f.fab_cap[e] / self._fab_now})

    def _answers(self, f, e, out):
        for row in f.chain.closed_rows():
            if int(row[2]) != e:
                continue
            k = lic_key(int(row[0]), str(row[1]), e)
            if k in self.seen_closed:
                continue
            self.seen_closed[k] = True
            issuer = int(row[0])
            if k in self.answers:
                continue
            best = self._best_good(f, e, issuer)
            if best != "":
                out.append({"act": "licence", "good": best, "to": issuer, "open": False, "answer": True})

    def _r55(self, f, e):
        out = []
        S = len(MD.SOURCES)
        if (f.day - 1) % 365 == 30:
            self.plan[e] = self._energy_year(f, e, S)
            if self.fab and f.fab_cap[e] > 0.0:
                self.plan[e]["fab"] = self._fab_year(f, e) / 12.0
        p = self.plan.get(e, {})
        for src in p:
            if float(p[src]) > 0.0:
                out.append({"act": "build", "kind": src, "size": float(p[src])})
        dc_lead = int(f.data.lead_days["dc"]["days"])
        binds = f.dc_served[e] < 1.0 or self._gap(f, e, f.day + dc_lead) > NOISE * gd.maxf(1.0, f.demand[e])
        if not binds:
            self._dc(f, e, out)
        for row in f.chain.closed_rows():
            if int(row[2]) != e:
                continue
            k = lic_key(int(row[0]), str(row[1]), e)
            if k in self.seen_closed:
                continue
            self.seen_closed[k] = True
            if k in self.answers or ("%d|%s" % (int(row[0]), str(row[1]))) in self.general:
                continue
            best = self._best_good(f, e, int(row[0]))
            if best != "":
                self.queued.append([f.day + COUNTER_DAYS, e, best, int(row[0]), "answer"])
        if self.allies:
            self._follow(f, e)
        if e in self.restrict_p:
            self._restrict(f, e, out)
        left = []
        for q in self.queued:
            if int(q[1]) == e and int(q[0]) <= f.day:
                if f.chain.is_open(e, str(q[2]), int(q[3])):
                    act = {"act": "licence", "good": str(q[2]), "to": int(q[3]), "open": False}
                    act[str(q[4])] = True
                    out.append(act)
            else:
                left.append(q)
        self.queued = left
        return out

    def _restrict(self, f, e, out):
        for g in GOODS_LICENSED:
            gk = "%d|%s" % (e, g)
            if gk in self.general:
                if int(self.general[gk]) <= f.day:
                    del self.general[gk]
                    for d in range(f.E):
                        if d != e and not f.chain.is_open(e, g, d):
                            out.append({"act": "licence", "good": g, "to": d, "open": True})
                continue
            mine = f.data.share_of(e, _src(g))
            if mine <= 0.0:
                continue
            others = 0.0
            for k in self.general:
                p = k.split("|")
                if p[1] == g and int(p[0]) != e:
                    others += f.data.share_of(int(p[0]), _src(g))
            chance = (float(self.restrict_p[e]) + CONTAGION * others / gd.maxf(1e-12, 1.0 - mine)) / 12.0
            u = hashes.unit("modern-restrict|%d|%s|%s|%d" % (f.data.base_year, f.data.keys[e], g, f.day))
            if u < chance:
                self.general[gk] = f.day + RESTRICT_DAYS
                for d2 in range(f.E):
                    if d2 != e and f.chain.is_open(e, g, d2):
                        out.append({"act": "licence", "good": g, "to": d2, "open": False, "general": True})

    def _follow(self, f, e):
        if self.in_regime[e] == 0:
            return
        for row in f.chain.closed_rows():
            leader = int(row[0])
            target = int(row[2])
            g = str(row[1])
            if leader == e or target == e:
                continue
            k = lic_key(leader, g, target)
            if k in self.answers or k in self.follows or ("%d|%s" % (leader, g)) in self.general:
                continue
            fk = "%d|%s" % (e, k)
            if fk in self.seen_follow:
                continue
            self.seen_follow[fk] = True
            if leader in self.allies[e] and target not in self.allies[e] \
                    and f.data.share_of(e, _src(g)) > 0.0 and f.chain.is_open(e, g, target):
                self.queued.append([f.day + FOLLOW_DAYS, e, g, target, "follow"])

    def _fab_year(self, f, e):
        out_yr = f.fab_out[e] * 365.0
        macro = str(f.data.MACROS[f.data.macro[e]])
        capex = float(self.fab["kappa"]) * float(self.fab["revenue"]) * out_yr / (1.0 - float(self.fab["public_share"][macro]))
        return capex / float(self.fab["cost_per_wspm"]) / float(self.fab["world_wspm"])

    def _best_good(self, f, e, issuer):
        best = ""
        best_share = 0.0
        for g in GOODS_LICENSED:
            sh = f.data.share_of(e, _src(g))
            if sh > best_share and f.chain.is_open(e, g, issuer):
                best = g
                best_share = sh
        return best

    def _load(self, f, e, at):
        it_then = gd.minf(f.wanted_it(e, at), (f.dc_it[e] + self._pending(e, "dc")) * f.u_max)
        return f.base_demand(e, at) + it_then * f.pue[e] + (f.fab_cap[e] + self._pending(e, "fab")) * f.fab_mw_per_unit

    def _gap(self, f, e, at):
        S = len(MD.SOURCES)
        load = self._load(f, e, at)
        sup = f.imports_of(e, at)
        for s in range(S):
            sup += f.supply_at(e, s, at) + self._pending(e, MD.SOURCES[s])
        return load - sup

    def _energy_year(self, f, e, S):
        cur = [0.0] * S
        all_ = 0.0
        for s in range(S):
            cur[s] = f.supply_of(e, s)
            all_ += cur[s]
        need = {}
        for s2 in range(S):
            src = MD.SOURCES[s2]
            w = cur[s2] / all_ if all_ > 0.0 else (1.0 if src == "gas" else 0.0)
            if w <= 0.0:
                continue
            h = f.day + int(f.data.lead_days[src]["days"]) + 365
            need[src] = gd.maxf(0.0, w * (self._load(f, e, h) - f.imports_of(e, h)) - f.supply_at(e, s2, h) - self._pending(e, src))
        wt = {}
        if self.costs is not None:
            q = 0.0
            for src2 in MC_LOGIT:
                q += float(need.get(src2, 0.0))
                need.pop(src2, None)
            tot = 0.0
            for src3 in MC_LOGIT:
                if src3 == "wind" or src3 == "solar" or cur[MD.SOURCES.index(src3)] > 0.0:
                    wt[src3] = DM.pow(self.costs.lcoe(e, src3, float(self._learn.get(src3, 1.0))), LOGIT_GAMMA)
                    tot += float(wt[src3])
            for src4 in wt:
                wt[src4] = float(wt[src4]) / tot
                need[src4] = q * float(wt[src4])
        else:
            for s3 in range(S):
                if MD.SOURCES[s3] in need:
                    wt[MD.SOURCES[s3]] = cur[s3]
        add = {}
        spare = 0.0
        for src5 in need:
            a = float(need[src5])
            if src5 in CHERP_CAP and a > float(CHERP_CAP[src5]) * all_:
                spare += a - float(CHERP_CAP[src5]) * all_
                a = float(CHERP_CAP[src5]) * all_
            add[src5] = a
        if spare > 0.0:
            rest = 0.0
            for src6 in wt:
                rest += float(wt[src6]) if src6 not in CHERP_CAP else 0.0
            for src7 in wt:
                if src7 not in CHERP_CAP and rest > 0.0:
                    add[src7] = float(add.get(src7, 0.0)) + spare * float(wt[src7]) / rest
            if rest <= 0.0:
                add["gas"] = float(add.get("gas", 0.0)) + spare
        monthly = {}
        for src8 in add:
            if float(add[src8]) > NOISE * gd.maxf(1.0, all_):
                monthly[src8] = float(add[src8]) / 12.0
        return monthly

    def to_dict(self):
        pl = {}
        for k in sorted(self.plan.keys()):
            pl[k] = dict(self.plan[k])
        gn = {}
        for k6 in sorted(self.general.keys()):
            gn[k6] = int(self.general[k6])
        return {"rule_set": self.rule_set, "seen_closed": sorted(self.seen_closed.keys()), "answers": sorted(self.answers.keys()), "plan": pl,
                "queued": deep(self.queued), "follows": sorted(self.follows.keys()), "seen_follow": sorted(self.seen_follow.keys()), "general": gn}

    def from_dict(self, d):
        self.rule_set = str(d["rule_set"])
        self.seen_closed = {str(k): True for k in d["seen_closed"]}
        self.answers = {str(k): True for k in d["answers"]}
        self.plan = {}
        for k3 in d.get("plan", {}):
            self.plan[int(k3)] = dict(d["plan"][k3])
        self.queued = deep(d.get("queued", []))
        self.follows = {str(k): True for k in d.get("follows", [])}
        self.seen_follow = {str(k): True for k in d.get("seen_follow", [])}
        self.general = {str(k): int(d["general"][k]) for k in d.get("general", {})}
