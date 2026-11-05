# The ruler's seat for any registry country (FRAME_PLAN §6.2, the prototype): an observation of the country's persons and its
# levers, and the ruler's actions as the levers applied in the next month. Why over the persons and not py/world's View: the world
# (py/world/seats.py, view.py) holds Japan alone today; a stub has no field, polity or economy, and its persons' month is what runs
import hashlib

from tiers.start import load

STUB_HEADER = "stub: its numbers are placeholders (UNSOURCED, D483) and claim nothing about the country"


class RulerSeat:
    def __init__(self, c, persons, script=None):
        self.c = c
        self.persons = persons
        self.script = script
        self.levers = list(load.load_json(c.path("levers"))["levers"].keys())
        self.pending = []
        self.transcript = []

    def observe(self):
        p = self.persons.p
        pop = 0.0
        for code in sorted(p.pref_pop):
            pop += float(p.pref_pop[code])
        return {"country": self.c.id, "name": self.c.name_en, "status": self.c.status,
                "label": self.c.label if self.c.status == "stub" else "", "month": p.month, "population": pop,
                "summary": self.persons.summary(), "levers": list(self.levers)}

    @staticmethod
    def text_of(obs):
        head = "%s (%s), month %d" % (obs["name"], obs["country"], obs["month"])
        if obs["status"] == "stub":
            head += ": " + STUB_HEADER
        sm = obs["summary"]
        lines = [head, "population %.0f%s" % (obs["population"], " (placeholder)" if obs["status"] == "stub" else "")]
        for k in sorted(sm):
            lines.append("%s %r" % (k, sm[k]))
        lines.append("levers: " + ", ".join(obs["levers"]))
        return "\n".join(lines)

    def act(self, lever_ids):
        bad = [x for x in lever_ids if x not in self.levers]
        if bad:
            raise ValueError("country %s has no lever %s" % (self.c.id, bad))
        self.pending = list(lever_ids)

    def month(self, env):
        # One month: observe, the ruler acts (a script, or act() beforehand), the persons step with the levers in the env
        obs = self.observe()
        if self.script is not None:
            self.act(self.script(obs))
        e = dict(env)
        e["levers"] = list(self.pending)
        self.transcript.append({"month": obs["month"], "observation_md5": hashlib.md5(self.text_of(obs).encode("utf-8")).hexdigest(),
                                "actions": list(self.pending)})
        self.persons.step(e)
        self.pending = []
        return obs
