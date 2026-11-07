# The agent environment over the endogenous policy simulation (Roadmap P0).
#
# run_simulation.py is the engine room: Status + Polity + Persons + EconMonth
# with Diet-mediated lever submission. This module gives an external policy
# (an LLM, a heuristic, a learned policy) the standard environment shape:
#
#   obs  = {"year", "phase", "indicators" (the 101-indicator state vector),
#           "levers" (current values), "lever_bounds" (min/max/unit/status),
#           "row" (last yearly summary row, None at the initial call)}
#   acts = [(lever_id, value), ...] or {lever_id: value}
#
# The policy is called once before the first simulated day (phase "initial",
# after the scenario's own lever plan is submitted) and at every year end
# (phase "year_end"). Acts go through the same Cabinet/Diet path as scenario
# levers (submit_policy_lever): an act can be EXECUTED, become a BILL, or be
# REFUSED, and bill/refused acts join the pending platform that a later
# election majority can enact. Nothing about the engine changes when no
# policy is attached: policy_fn=None reproduces the CLI exactly.
#
# Reward is deliberately NOT defined here. What counts as a good outcome
# (population, fiscal sustainability, welfare, a composite) is a values
# decision for the environment's owner; the episode record carries the full
# trajectory so any reward function can be computed from it afterwards.
import contextlib
import io
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import run_simulation as RS


def null_policy(obs):
    """The do-nothing policy: never acts. An episode under it must reproduce
    the corresponding scenario run exactly."""
    return []


class _Bridge:
    """Callable policy wrapper that records the episode as it runs."""

    def __init__(self, policy):
        self.policy = policy
        self.steps = []
        self._pending = None

    def __call__(self, obs):
        acts = self.policy(obs) or []
        if isinstance(acts, dict):
            acts = list(acts.items())
        acts = [(str(lid), float(val)) for lid, val in acts]
        self._pending = {"year": obs["year"], "phase": obs["phase"], "obs": obs, "acts": acts, "results": []}
        self.steps.append(self._pending)
        return acts

    def report(self, year, phase, results):
        if self._pending is not None and self._pending["year"] == year and self._pending["phase"] == phase:
            self._pending["results"] = results


class SandvoxEnv:
    """One environment instance = one episode configuration.

    policy: callable(obs) -> acts. See module docstring for the shapes.
    """

    def __init__(self, years=25, scenario="baseline", full_mode=False, n_per=2,
                 coalition_pass=False, params_path=None):
        self.years = years
        self.scenario = scenario
        self.full_mode = full_mode
        self.n_per = n_per
        self.coalition_pass = coalition_pass
        self.params_path = params_path

    def run(self, policy, quiet=True):
        """Run one episode. Returns {"history", "steps", "final"} where
        history is run_simulation's yearly rows, steps is the recorded
        observe/act/result trace, and final is the last yearly row."""
        bridge = _Bridge(policy)
        kwargs = dict(
            years=self.years,
            scenario=self.scenario,
            full_mode=self.full_mode,
            n_per=self.n_per,
            coalition_pass=self.coalition_pass,
            params_path=self.params_path,
            policy_fn=bridge,
        )
        if quiet:
            with contextlib.redirect_stdout(io.StringIO()):
                history = RS.run_simulation(**kwargs)
        else:
            history = RS.run_simulation(**kwargs)
        return {"history": history, "steps": bridge.steps, "final": history[-1] if history else None}


def run_episode(policy, **env_kwargs):
    return SandvoxEnv(**env_kwargs).run(policy)
