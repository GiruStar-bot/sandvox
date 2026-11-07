# The agent environment (py/agent_env.py, Roadmap P0): the policy hook must
# not change the engine when it does nothing, and must actually move the
# world when it acts.
#   python py/tests/test_agent_env.py
import contextlib
import io
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import Kit  # noqa: E402  (puts py/ on the path)

import agent_env  # noqa: E402
import run_simulation as RS  # noqa: E402


def table_lines(text):
    return [ln for ln in text.splitlines() if "completed in" not in ln]


def main():
    k = Kit("py/tests/test_agent_env.py")

    # 1) Zero-change: a policy that never acts must reproduce the no-policy
    # run's printed output exactly (apart from the elapsed-time line).
    buf1 = io.StringIO()
    with contextlib.redirect_stdout(buf1):
        RS.run_simulation(years=10, scenario="baseline")
    buf2 = io.StringIO()
    with contextlib.redirect_stdout(buf2):
        RS.run_simulation(years=10, scenario="baseline", policy_fn=lambda obs: [])
    k.check(table_lines(buf1.getvalue()) == table_lines(buf2.getvalue()),
            "P0-inv a null policy_fn leaves the printed table identical to no policy_fn")

    # 2) Episode shape under the null policy: one initial observation plus
    # one per year end, no acts, full history.
    ep = agent_env.run_episode(agent_env.null_policy, years=10, scenario="baseline")
    k.check(len(ep["history"]) == 10 and len(ep["steps"]) == 11
            and all(s["acts"] == [] for s in ep["steps"])
            and ep["steps"][0]["phase"] == "initial"
            and ep["steps"][0]["obs"]["row"] is None
            and "pop_total" in ep["steps"][0]["obs"]["indicators"]
            and "child_allowance" in ep["steps"][0]["obs"]["lever_bounds"],
            "P0-shape null episode: 11 observations (initial + 10 year ends), no acts, 10 history rows")

    # 3) Actuation: setting child_allowance at the initial call goes through
    # the Cabinet/Diet path and moves births against the null episode.
    def splash(obs):
        if obs["phase"] == "initial":
            return [("child_allowance", 10000.0)]
        return []

    ep2 = agent_env.run_episode(splash, years=10, scenario="baseline")
    res = [r for s in ep2["steps"] for r in s["results"] if r["lever"] == "child_allowance"]
    births1 = sum(r["births"] for r in ep["history"])
    births2 = sum(r["births"] for r in ep2["history"])
    k.check(bool(res) and res[0]["status"] in ("executed", "bill"),
            "P0-act child_allowance act submitted through the policy path (%s)"
            % (res[0]["status"] if res else "no result recorded"))
    k.check(births2 > births1,
            "P0-act cum births over 10y rise under the allowance (%d -> %d)" % (births1, births2))
    k.finish()


if __name__ == "__main__":
    main()
