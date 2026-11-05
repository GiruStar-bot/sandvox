# modern_chain.gd: the closed export licences, input availability and the day's chip distribution
from ._core import gd
from .gdtypes import F64

INPUTS = ["lithography", "photoresist", "silicon_wafers", "gallium", "neon"]
GOODS_LICENSED = ["lithography", "photoresist", "silicon_wafers", "gallium", "neon", "chips"]


def key(issuer, good, dest):
    return "%d|%s|%d" % (issuer, good, dest)


class Chain:
    INPUTS = INPUTS
    GOODS_LICENSED = GOODS_LICENSED

    def __init__(self):
        self.closed = {}

    def is_open(self, issuer, good, dest):
        return key(issuer, good, dest) not in self.closed

    def set_licence(self, issuer, good, dest, open_):
        k = key(issuer, good, dest)
        if open_:
            self.closed.pop(k, None)
        else:
            self.closed[k] = True

    def closed_rows(self):
        out = []
        for k in sorted(self.closed.keys()):
            p = k.split("|")
            out.append([int(p[0]), p[1], int(p[2])])
        return out

    def input_availability_by(self, data, E):
        out = F64([1.0] * (E * len(INPUTS)))
        for row in self.closed_rows():
            i = INPUTS.index(row[1]) if row[1] in INPUTS else -1
            if i >= 0:
                k = int(row[2]) * len(INPUTS) + i
                out[k] = gd.maxf(0.0, out[k] - data.share_of(int(row[0]), str(row[1])))
        return out

    def input_availability(self, data, E):
        out = F64([1.0] * E)
        lost = {}
        for row in self.closed_rows():
            g = str(row[1])
            if g not in INPUTS:
                continue
            kk = "%d|%s" % (int(row[2]), g)
            lost[kk] = float(lost.get(kk, 0.0)) + data.share_of(int(row[0]), g)
        for kk2 in lost:
            e = int(kk2.split("|")[0])
            out[e] = gd.minf(out[e], gd.maxf(0.0, 1.0 - float(lost[kk2])))
        return out

    def distribute(self, out, atp, free, stock):
        E = len(out)
        got = F64([0.0] * E)
        W = 0.0
        for e in range(E):
            W += out[e]
        if W <= 0.0:
            return got
        cut_to = {}
        cut_from = {}
        for row in self.closed_rows():
            if str(row[1]) != "chips":
                continue
            r0, r2 = int(row[0]), int(row[2])
            cut_to[r2] = float(cut_to.get(r2, 0.0)) + out[r0]
            stock[r0] += atp[r2] * out[r0]
            s = cut_from.get(r0, {})
            s[r2] = True
            cut_from[r0] = s
        free_all = 0.0
        for d in range(E):
            free_all += gd.maxf(0.0, free[d])
        open_p = 0.0
        for a in range(E):
            if atp[a] <= 0.0:
                continue
            p_a = atp[a] * gd.maxf(0.0, W - float(cut_to.get(a, 0.0)))
            if p_a <= 0.0:
                continue
            if a not in cut_from:
                open_p += p_a
                continue
            cuts = cut_from[a]
            tot = free_all
            for d2 in cuts:
                tot -= gd.maxf(0.0, free[int(d2)])
            if tot <= 0.0:
                stock[a] += p_a
                continue
            for d3 in range(E):
                if free[d3] > 0.0 and d3 not in cuts:
                    got[d3] += p_a * free[d3] / tot
        if open_p > 0.0:
            if free_all <= 0.0:
                for a2 in range(E):
                    if atp[a2] > 0.0 and a2 not in cut_from:
                        stock[a2] += atp[a2] * gd.maxf(0.0, W - float(cut_to.get(a2, 0.0)))
            else:
                for d4 in range(E):
                    if free[d4] > 0.0:
                        got[d4] += open_p * free[d4] / free_all
        return got

    def to_dict(self):
        return {"closed": sorted(self.closed.keys())}

    def from_dict(self, d):
        self.closed = {}
        for k in d.get("closed", []):
            self.closed[str(k)] = True
