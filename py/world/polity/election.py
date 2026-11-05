# polity/election.gd: the national swing, the lower house (districts by prefecture, d'Hondt blocks), the upper-house half, designation
import functools
import math

from .. import canon as CANON
from ..data import exists
from .._core import DM, gd


class Election:
    def __init__(self):
        self.spec = {}
        self.error = ""

    def load_state(self, key):
        p = "res://data/modern/polity/%s_election.json" % key.lower()
        d = CANON.load_json(p) if exists(p) else None
        if not isinstance(d, dict):
            self.error = "election: no spec at " + p
            return self.error
        self.spec = d
        return ""

    def vote_shares(self, governing, d_approval, d_unemployment_pt, d_cpi_pt):
        base = self.spec["vote_share_2024_10_27_pr"]
        r = self.spec["vote_rule"]["retrospective_swing"]
        factor = 1.0 + float(r["a"]) * d_approval + float(r["b"]) * d_unemployment_pt + float(r["c"]) * d_cpi_pt
        factor = gd.clampf(factor, 0.5, 1.5)
        out = {}
        gov_before = 0.0
        gov_after = 0.0
        for party in self.spec["parties"]:
            s = float(base.get(party, 0.0))
            if party in governing:
                gov_before += s
                s *= factor
                gov_after += s
            out[party] = s
        opp_before = 1.0 - gov_before
        opp_after = 1.0 - gov_after
        for party in out:
            if party not in governing and opp_before > 0.0:
                out[party] = float(out[party]) * opp_after / opp_before
        return out

    @staticmethod
    def dhondt(shares, n):
        seats = {p: 0 for p in shares}
        ks = sorted(shares.keys())
        for _ in range(n):
            best = ""
            best_q = -1.0
            for p in ks:
                q = float(shares[p]) / float(int(seats[p]) + 1)
                if q > best_q:
                    best_q = q
                    best = p
            seats[best] = int(seats[best]) + 1
        return seats

    @staticmethod
    def smd_split(shares, n, k):
        w = {}
        tot = 0.0
        for p in shares:
            v = DM.pow(float(shares[p]), k)
            w[p] = v
            tot += v
        seats = {}
        rem = []
        given = 0
        for p in sorted(shares.keys()):
            exact = float(n) * float(w[p]) / tot if tot > 0.0 else 0.0
            seats[p] = int(math.floor(exact))
            given += int(seats[p])
            rem.append([exact - float(math.floor(exact)), p])

        def cmp(a, b):
            if float(a[0]) != float(b[0]):
                return -1 if float(a[0]) > float(b[0]) else 1
            return -1 if a[1] < b[1] else (1 if a[1] > b[1] else 0)
        rem.sort(key=functools.cmp_to_key(cmp))
        for i in range(n - given):
            seats[str(rem[i][1])] = int(seats[str(rem[i][1])]) + 1
        return seats

    def run_lower_house(self, shares):
        H = self.spec["houses"]["house_of_representatives"]
        k = 3.0
        total = {p: 0 for p in self.spec["parties"]}
        by_pref = {}
        for pref in self.spec["smd_by_prefecture"]:
            s = self.smd_split(shares, int(self.spec["smd_by_prefecture"][pref]), k)
            by_pref[pref] = s
            for p in s:
                total[p] = int(total[p]) + int(s[p])
        by_block = {}
        for b in H["blocks"]:
            s2 = self.dhondt(shares, int(H["blocks"][b]["seats"]))
            by_block[b] = s2
            for p in s2:
                total[p] = int(total[p]) + int(s2[p])
        return {"seats": total, "districts": by_pref, "blocks": by_block, "turnout": float(self.spec["turnout"]["value"]), "shares": dict(shares)}

    @staticmethod
    def designate(seats, governing, total, partners):
        gov = 0
        for p in governing:
            gov += int(seats.get(p, 0))
        if gov * 2 > total:
            return {"governing": list(governing), "majority": True, "why": "the governing bloc keeps the majority"}
        largest = ""
        for p in seats:
            if largest == "" or int(seats[p]) > int(seats[largest]) or (int(seats[p]) == int(seats[largest]) and p < largest):
                largest = p
        bloc = [largest]
        n = int(seats[largest])
        for q in partners.get(largest, []):
            bloc.append(q)
            n += int(seats.get(q, 0))
        return {"governing": bloc, "majority": n * 2 > total, "why": "the largest party%s" % (" with its partner" if len(bloc) > 1 else " alone, a minority government")}

    def run_upper_house(self, shares):
        H = self.spec["houses"]["house_of_councillors"]
        elected = {p: 0 for p in self.spec["parties"]}
        by_pref = {}
        for pref in sorted(H["district_seats_per_election"].keys()):
            n = int(H["district_seats_per_election"][pref])
            s = self.smd_split(shares, n, 3.0) if n == 1 else self.dhondt(shares, n)
            by_pref[pref] = s
            for p in s:
                elected[p] = int(elected[p]) + int(s[p])
        pr = self.dhondt(shares, int(H["pr"]))
        for p in pr:
            elected[p] = int(elected[p]) + int(pr[p])
        composition = {}
        for p in elected:
            composition[p] = int(elected[p]) + int(H["continuing_half_2022"].get(p, 0))
        return {"elected": elected, "districts": by_pref, "pr": pr, "composition": composition, "shares": dict(shares)}
