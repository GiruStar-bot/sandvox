# modern_chronicle.gd: the record (output only; hashed in this port's digest without its why: WORLD_PORT_PLAN §2)
from ._core import gd
from .gdtypes import deep

KINDS = ["shortage", "project_done", "licence", "lever_set", "lever_applied", "lever_refused", "decision", "status_line", "year_close", "seat_refused", "election"]
_MD = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]


def date_of(base_year, day):
    y = base_year + day // 365
    doy = day % 365
    m = 0
    while m < 11 and doy >= _MD[m]:
        doy -= _MD[m]
        m += 1
    return "%04d-%02d-%02d" % (y, m + 1, doy + 1)


class Chronicle:
    def __init__(self):
        self.rows = []
        self.base_year = 0
        self._last_shortage = {}

    def create(self, year):
        self.base_year = year
        self.rows = []

    def add(self, day, kind, place, who, facts, why=""):
        self.rows.append({"day": day, "date": date_of(self.base_year, day), "kind": kind, "place": place, "who": who, "facts": facts, "why": why})

    def observe_field(self, f, keys):
        for e in range(f.E):
            short = f.unserved[e] > 1e-6 * gd.maxf(1.0, f.demand[e]) or f.dc_served[e] < 1.0 - 1e-9
            k = keys[e]
            if short and k not in self._last_shortage:
                self._last_shortage[k] = f.day
                self.add(f.day, "shortage", k, "field", {"unserved_mw": f.unserved[e], "dc_served": f.dc_served[e], "fab_served": f.fab_served[e]},
                         "demand above supply, links and storage; DC cut first" if f.fab_first[e] == 0 else "demand above supply; fab cut first")
            elif not short and k in self._last_shortage:
                self.add(f.day, "shortage", k, "field", {"ended_after_days": f.day - int(self._last_shortage[k])}, "supply met demand again")
                del self._last_shortage[k]

    def to_dict(self):
        return {"rows": deep(self.rows), "last_shortage": dict(self._last_shortage)}

    def from_dict(self, d):
        self.rows = deep(d.get("rows", []))
        self._last_shortage = dict(d.get("last_shortage", {}))
