# modern_view.gd: one state's view (HMAC-SHA256 tokens under the run's salt, the own truth, others as published)
from . import canon as CANON
from . import data as MD
from . import hashes
from .chain import GOODS_LICENSED
from .field import PROJECT_KINDS
from .data import exists
from ._core import DM

MONTH_DAYS = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]


def date_of(base_year, day):
    y = base_year + day // 365
    d = day % 365
    m = 0
    while d >= MONTH_DAYS[m]:
        d -= MONTH_DAYS[m]
        m += 1
    return "%04d-%02d-%02d" % (y, m + 1, d + 1)


class View:
    def __init__(self):
        self.key = ""
        self.spec = {}
        self.error = ""
        self._token = {}
        self._entity = {}

    def load_view(self, view_key, data, salt):
        self.key = view_key
        if len(salt) < 16:
            self.error = "modern view: a view needs the run's secret salt (16 bytes or more)"
            return self.error
        p = "res://data/modern/views/%s.json" % view_key
        v = CANON.load_json_m(p) if exists(p) else None
        if not isinstance(v, dict):
            self.error = "modern view: no view " + view_key
            return self.error
        self.spec = v
        for e in range(data.entity_count()):
            k = data.keys[e]
            if self.kind_of(k) == "unknown":
                continue
            tok = hashes.token(salt, self.key, k)
            self._token[k] = tok
            self._entity[tok] = e
        return ""

    def kind_of(self, entity_key):
        return str(self.spec["entities"].get(entity_key, {}).get("kind", "unknown"))

    def token_of(self, entity_key):
        return str(self._token.get(entity_key, ""))

    def entity_of(self, tok):
        return int(self._entity.get(tok, -1))

    def _row(self, w, e):
        k = w.data.keys[e]
        r = self.spec["entities"][k]
        out = {"token": self._token[k], "name": str(r["name"]), "kind": str(r["kind"])}
        if "of" in r and r["of"] is not None and str(r["of"]) in self._token:
            out["of"] = self._token[str(r["of"])]
        return out

    def observe(self, w, me):
        f = w.field
        d = w.data
        S = len(MD.SOURCES)
        day = f.day
        own = self._row(w, me)
        sup = {}
        for s in range(S):
            sup[MD.SOURCES[s]] = f.supply_of(me, s)
        own["figures"] = {"population": w.population(me), "gdp": d.gdp[me] * DM.pow(1.0 + d.gdp_growth[me], float(day - 182) / 365.0),
                          "demand_mw": f.demand[me], "supply_mw": sup, "contracted_imports_mw": f.imports_of(me), "storage_mwh": f.storage[me],
                          "storage_capacity_mwh": f.storage_cap[me], "dc_capacity_it_mw": f.dc_it[me], "servers_it_mw": f.servers[me], "chips_held": f.chips[me],
                          "fab_capacity": f.fab_cap[me], "fab_output_day": f.fab_out[me], "dc_served": f.dc_served[me], "fab_served": f.fab_served[me],
                          "unserved_mw": f.unserved[me], "dc_water_l": f.water_l[me], "cut_first": "fab" if f.fab_first[me] == 1 else "dc"}
        projects = []
        for p in f.projects:
            if int(p[0]) != me:
                continue
            pr = {"kind": str(p[1]), "size": float(p[2]), "started": date_of(d.base_year, int(p[3])), "finishes": date_of(d.base_year, int(p[4]))}
            if int(p[5]) >= 0:
                other = f.link_b[int(p[5])] if f.link_a[int(p[5])] == me else f.link_a[int(p[5])]
                if d.keys[other] not in self._token:
                    continue
                pr["link_to"] = self._token[d.keys[other]]
            projects.append(pr)
        own["projects"] = projects
        if w.status is not None and w.status.has(d.keys[me]):
            st = dict(w.status.ind[d.keys[me]])
            own["statuses"] = {i: st[i] for i in sorted(st.keys())}
            own["menu"] = w.status.menu(d.keys[me])
        links = []
        for l in f.links_of[me]:
            o = f.link_b[l] if f.link_a[l] == me else f.link_a[l]
            if d.keys[o] not in self._token:
                continue
            links.append({"to": self._token[d.keys[o]], "capacity_mw": f.link_cap[l], "flow_out_mw": f.link_flow[l] if f.link_a[l] == me else -f.link_flow[l]})
        links.sort(key=lambda x: str(x["to"]))
        own["links"] = links
        others = []
        for e in range(f.E):
            if e == me or d.keys[e] not in self._token:
                continue
            r = self._row(w, e)
            pub = {}
            for fig in w.register.FIGURES:
                v = w.register.published(fig, e, day)
                if v:
                    pub[fig] = v
            r["published"] = pub
            others.append(r)
        others.sort(key=lambda x: str(x["token"]))
        lic = []
        for row in f.chain.closed_rows():
            ki = d.keys[int(row[0])]
            kd = d.keys[int(row[2])]
            if ki in self._token and kd in self._token:
                lic.append({"from": self._token[ki], "good": str(row[1]), "to": self._token[kd]})
        lic.sort(key=lambda x: "%s|%s|%s" % (x["from"], x["good"], x["to"]))
        claims = []
        for c in self.spec["claims"]:
            if str(c["administered_by"]) in self._token:
                claims.append({"label": str(c["label"]), "administered_by": self._token[str(c["administered_by"])]})
        return {"view": self.key, "date": date_of(d.base_year, day), "self": own, "others": others, "licences_closed": lic, "claims": claims,
                "sources": list(MD.SOURCES), "goods_licensed": list(GOODS_LICENSED), "project_kinds": list(PROJECT_KINDS)}

    @staticmethod
    def text_of(obs):
        # Why not Godot's text: JSON.stringify writes floats by Godot's own digits; this text is Python's (WORLD_PORT_PLAN §5, seats)
        import json
        return json.dumps(obs, indent="\t", sort_keys=True, ensure_ascii=False)

    def to_world(self, a):
        if not isinstance(a, dict):
            return {"error": "not an action"}
        act = dict(a)
        for field_name in ("to", "link_to"):
            if field_name in act:
                e = self.entity_of(str(act[field_name]))
                if e < 0:
                    return {"error": "unknown token " + str(act[field_name])}
                act[field_name] = e
        return act
