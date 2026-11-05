# modern_seats.gd: scripted and replay seats (the observation md5 is Python's text, not in parity: WORLD_PORT_PLAN §5)
import hashlib

from .gdtypes import deep
from .view import View


class Seat:
    def __init__(self):
        self.view = None
        self.mode = ""
        self.script_fn = None
        self.transcript = []
        self.replay_from = []
        self.diverged = 0

    @staticmethod
    def scripted(v, fn):
        s = Seat()
        s.view = v
        s.mode = "scripted"
        s.script_fn = fn
        return s

    @staticmethod
    def replay(v, earlier):
        s = Seat()
        s.view = v
        s.mode = "replay"
        s.replay_from = deep(earlier)
        return s

    def actions(self, w, e):
        obs = self.view.observe(w, e)
        md5 = hashlib.md5(View.text_of(obs).encode("utf-8")).hexdigest()
        if self.mode == "scripted":
            answer = self.script_fn(obs)
        else:
            row = {}
            for r in self.replay_from:
                if int(r["day"]) == w.field.day:
                    row = r
                    break
            if not row:
                self.transcript.append({"day": w.field.day, "obs_md5": md5, "answer": []})
                return {"actions": [], "error": "the transcript has no answer for day %d" % w.field.day}
            self.diverged += 0 if str(row["obs_md5"]) == md5 else 1
            answer = deep(row["answer"])
        self.transcript.append({"day": w.field.day, "obs_md5": md5, "answer": deep(answer) if isinstance(answer, list) else answer})
        if not isinstance(answer, list):
            return {"actions": [], "error": "the answer is not a list"}
        out = []
        for a in answer:
            m = self.view.to_world(a)
            if "error" in m:
                return {"actions": [], "error": str(m["error"])}
            out.append(m)
        return {"actions": out, "error": ""}
