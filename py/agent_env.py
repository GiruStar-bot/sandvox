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
# There is NO reward here, by design (user decision 2026-11-07,
# ROADMAP_V3): the environment never scores the policy. The design is
# examination-style - a third party sets a challenge, the examinee
# answers with a policy proposal, and the third party evaluates the
# answer externally. The environment's duties are presenting the
# situation, accepting proposals, and simulating their consequences
# faithfully and fast; the input/output formats for that loop live in
# py/eval_interface.py. Keeping every value judgement outside the
# environment also removes the internal-reward Goodhart channel by
# construction.
#
# feedback_params= forwards parameter overrides to the engine (the
# domain-randomization surface used by py/episode_runner.py).
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
                 coalition_pass=False, params_path=None, usa_tariff=None, shocks=None,
                 chn_tariff=None, eu_tariff=None, feedback_params=None):
        self.years = years
        self.scenario = scenario
        self.full_mode = full_mode
        self.n_per = n_per
        self.coalition_pass = coalition_pass
        self.params_path = params_path
        self.usa_tariff = usa_tariff
        self.chn_tariff = chn_tariff
        self.eu_tariff = eu_tariff
        self.shocks = shocks
        self.feedback_params = feedback_params

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
            usa_tariff=self.usa_tariff,
            chn_tariff=self.chn_tariff,
            eu_tariff=self.eu_tariff,
            shocks=self.shocks,
            feedback_params=self.feedback_params,
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


def random_shock_schedule(seed, years=25, prob=0.22):
    """A seeded shock library (Roadmap P4): sample a deterministic shock
    schedule for one episode. The engine itself never samples - a schedule
    is data, and the same (seed, years, prob) always yields the same one,
    so episodes are exactly reproducible while varying across seeds.
    Magnitude ranges are declared training choices, not estimates."""
    import random  # lint-ok: keyed Random(seed) draws only - the seeded schedule library

    rng = random.Random(seed)
    menu = [
        ("energy_price", 20.0, 80.0, 6, 18),
        ("food_price", 10.0, 40.0, 6, 24),
        ("disaster", 0.5, 3.0, 12, 12),
        ("foreign_recession", 10.0, 30.0, 9, 24),
        ("pandemic", 2.0, 5.0, 12, 30),
    ]
    out = []
    for y in range(years):
        if rng.random() < prob:
            kind, lo, hi, mlo, mhi = menu[rng.randrange(len(menu))]
            spec = {
                "kind": kind,
                "start": [2025 + y, rng.randrange(1, 13)],
                "months": rng.randrange(mlo, mhi + 1),
                "mag": round(rng.uniform(lo, hi), 2),
            }
            if kind == "pandemic":
                spec["hazard_x"] = 0.3
                spec["mig_scale"] = 0.2
            out.append(spec)
    return out
