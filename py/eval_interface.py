# Evaluation interface for the examination-style training design
# (user decision 2026-11-07, ROADMAP_V3 phase B).
#
# The environment gives the AI no reward - not "reward not yet
# defined", but none, as a design decision. A third party (the
# examiner) sets a challenge, the examinee answers with a policy
# proposal, the environment simulates the proposal's consequences,
# and the examiner evaluates the answer OUTSIDE the environment.
# This module is the environment side of that loop: three formats
# and the two operations over them. No evaluation criterion, score,
# ranking or welfare notion appears anywhere in it.
#
# CHALLENGE (examiner -> examinee), built by build_challenge():
#   {"id": str,
#    "prompt": str,                 # the question, carried verbatim
#    "setup": {scenario, years, full_mode, n_per, shocks,
#              randomize, seed, index},
#    "constraints": {allowed_levers?, forbidden_levers?, max_acts?,
#                    notes?},        # structural limits of the exam
#    "lever_catalogue": {lever_id: {min, max, unit, status}},
#    "current_levers": {lever_id: value},
#    "observation_history": [yearly rows under the do-nothing policy]}
# The observation history is the situation the examinee reasons
# from: what the simulated country does if nobody acts.
#
# PROPOSAL (examinee -> environment):
#   {"acts": [{"lever": lever_id, "value": number,
#              "when": "initial" | <year>}],
#    "rationale": str}
# "when" names the decision point: "initial" = before the first
# simulated day; a year Y = the year-end decision point of year Y
# (in force from Y+1). The rationale is part of the format because
# the examiner reads it; the environment carries it verbatim into
# the record and never interprets or scores it.
#
# EXAMINATION RECORD (environment -> examiner), from run_examination():
#   {"challenge_id", "valid", "problems" (when invalid),
#    "challenge": {id, prompt, setup, constraints},
#    "proposal": <verbatim>, "draws": {randomized parameter draws},
#    "acts_outcome": [{year, phase, lever, value, result}],
#    "years": [yearly rows], "final": <last yearly row>, "sha256"}
# The record is the evidence: what was asked, what was proposed,
# what the Diet did with each act, and what then happened - complete
# enough to re-run and to judge without trusting the environment.
#
# Validation here is STRUCTURAL only: known lever ids, numeric
# values inside the catalogue bounds, constraint compliance, a
# rationale present. Whether a proposal is GOOD is the examiner's
# judgement and is deliberately not computable from this module.
#
# Two measured properties of the engine make this interface load-
# bearing (evaluability report on the merged main, 2026-11-07):
# (1) The engine does NOT enforce lever bounds: an act of
#     child_allowance=100,000 (catalogue max 10,000) was enacted and
#     applied at face value, as was consumption_tax_rate=-0.05.
#     Bounds in the observation are advisory only, so the bounds
#     check in validate_proposal() is the enforcement point of the
#     examination: out-of-bounds proposals are invalid and are never
#     simulated. (Unknown lever ids, by contrast, the engine itself
#     rejects.)
# (2) In standard mode (full_mode=False) law-bound proposals can
#     carry no numeric signal at all: a consumption-tax act was
#     billed and rejected every year for 25 years (fixed minority
#     Diet, no elections), leaving the trajectory bit-identical to
#     doing nothing. Challenges meant to evaluate law-type proposals
#     must therefore use setup full_mode=True; build_challenge()
#     attaches an explicit mode_note whenever it does not.
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import agent_env  # noqa: E402
import episode_runner as ER  # noqa: E402

_SETUP_KEYS = ("scenario", "years", "full_mode", "n_per", "shocks",
               "randomize", "seed", "index")

STANDARD_MODE_NOTE = (
    "standard mode (full_mode=False): law-bound proposals are decided by a "
    "fixed Diet composition with no elections; measured on the merged main "
    "(2026-11-07), a consumption-tax proposal was billed and rejected every "
    "year for 25 years with zero numeric signal. Set setup.full_mode=True "
    "to evaluate law-type proposals.")


def _mode_note(setup):
    return None if setup.get("full_mode") else STANDARD_MODE_NOTE


def _norm_setup(setup):
    s = {"scenario": "baseline", "years": 25, "full_mode": False, "n_per": 2,
         "shocks": None, "randomize": False, "seed": 1, "index": 0}
    for k in _SETUP_KEYS:
        if k in (setup or {}):
            s[k] = setup[k]
    return s


def _env_for(setup):
    overrides, draws = (ER.sample_overrides(setup["seed"], setup["index"])
                        if setup.get("randomize") else (None, {}))
    env = agent_env.SandvoxEnv(
        years=setup["years"], scenario=setup["scenario"],
        full_mode=setup["full_mode"], n_per=setup["n_per"],
        shocks=setup["shocks"], feedback_params=overrides)
    return env, draws


def _year_rows(history):
    return [{k: row.get(k) for k in ER._YEAR_FIELDS} for row in history]


def build_challenge(setup, prompt="", constraints=None, challenge_id="exam-1"):
    """Run the setup under the do-nothing policy and package the
    situation as a challenge: observation history, lever catalogue
    and current values, plus the examiner's prompt and constraints."""
    setup = _norm_setup(setup)
    env, _draws = _env_for(setup)
    seen = {}

    def probe(obs):
        if "first" not in seen:
            seen["first"] = obs
        return []

    ep = env.run(probe)
    first = seen["first"]
    return {
        "id": challenge_id,
        "prompt": prompt,
        "setup": setup,
        "mode_note": _mode_note(setup),
        "constraints": constraints or {},
        "lever_catalogue": first["lever_bounds"],
        "current_levers": first["levers"],
        "observation_history": _year_rows(ep["history"]),
    }


def validate_proposal(proposal, challenge):
    """Structural validation only. Returns a list of problems;
    an empty list means the proposal is well-formed and may be run.
    Nothing here judges the proposal's merit."""
    problems = []
    if not isinstance(proposal, dict):
        return ["proposal must be an object with 'acts' and 'rationale'"]
    rationale = proposal.get("rationale")
    if not isinstance(rationale, str) or not rationale.strip():
        problems.append("rationale is required and must be a non-empty string "
                        "(carried into the record for the examiner; never scored here)")
    acts = proposal.get("acts")
    if not isinstance(acts, list):
        problems.append("acts must be a list")
        acts = []
    cons = challenge.get("constraints") or {}
    allowed = cons.get("allowed_levers")
    forbidden = set(cons.get("forbidden_levers") or [])
    max_acts = cons.get("max_acts")
    if max_acts is not None and len(acts) > int(max_acts):
        problems.append("acts count %d exceeds the challenge constraint max_acts=%s"
                        % (len(acts), max_acts))
    catalogue = challenge.get("lever_catalogue") or {}
    valid_years = {row["year"] for row in challenge.get("observation_history") or []}
    for i, a in enumerate(acts):
        if not isinstance(a, dict):
            problems.append("act %d must be an object" % i)
            continue
        lid = a.get("lever")
        if lid not in catalogue:
            problems.append("act %d: unknown lever %r" % (i, lid))
            continue
        if allowed is not None and lid not in allowed:
            problems.append("act %d: lever %s is outside the challenge's allowed_levers" % (i, lid))
        if lid in forbidden:
            problems.append("act %d: lever %s is forbidden by the challenge constraints" % (i, lid))
        v = a.get("value")
        if not isinstance(v, (int, float)) or isinstance(v, bool):
            problems.append("act %d: value for %s must be a number" % (i, lid))
        else:
            b = catalogue[lid]
            if isinstance(b.get("min"), (int, float)) and v < b["min"]:
                problems.append("act %d: value %s for %s is below its catalogue minimum %s"
                                % (i, v, lid, b["min"]))
            if isinstance(b.get("max"), (int, float)) and v > b["max"]:
                problems.append("act %d: value %s for %s exceeds its catalogue maximum %s"
                                % (i, v, lid, b["max"]))
        w = a.get("when", "initial")
        if w != "initial" and w not in valid_years:
            problems.append("act %d: 'when' must be \"initial\" or one of the challenge years %s"
                            % (i, sorted(valid_years)))
    return problems


class _ProposalPolicy:
    """Submits the proposal's acts at their named decision points,
    through the ordinary policy path (Cabinet/Diet included)."""

    def __init__(self, acts):
        self.acts = acts

    def __call__(self, obs):
        out = []
        for a in self.acts:
            w = a.get("when", "initial")
            if obs["phase"] == "initial" and w == "initial":
                out.append((a["lever"], float(a["value"])))
            elif obs["phase"] == "year_end" and w == obs["year"]:
                out.append((a["lever"], float(a["value"])))
        return out


def _result_text(r):
    if isinstance(r, dict):
        for k in ("status", "result", "outcome"):
            if k in r:
                return str(r[k])
        return str(sorted(r.items()))
    return str(r)


def run_examination(challenge, proposal):
    """Validate the proposal against the challenge and, if it is
    well-formed, simulate it and return the examination record (the
    evidence the examiner evaluates). An invalid proposal is not
    simulated; the record then carries the structural problems."""
    problems = validate_proposal(proposal, challenge)
    rec = {"challenge_id": challenge["id"], "valid": not problems}
    if problems:
        rec["problems"] = problems
        return rec
    setup = _norm_setup(challenge["setup"])
    env, draws = _env_for(setup)
    ep = env.run(_ProposalPolicy(proposal["acts"]))
    outcomes = []
    for s in ep["steps"]:
        results = s.get("results") or []
        for j, (lid, val) in enumerate(s["acts"]):
            outcomes.append({
                "year": s["year"], "phase": s["phase"], "lever": lid, "value": val,
                "result": _result_text(results[j]) if j < len(results) else None,
            })
    years = _year_rows(ep["history"])
    rec.update({
        "challenge": {"id": challenge["id"], "prompt": challenge.get("prompt"),
                      "setup": setup, "mode_note": _mode_note(setup),
                      "constraints": challenge.get("constraints") or {}},
        "proposal": proposal,
        "draws": draws,
        "acts_outcome": outcomes,
        "years": years,
        "final": ep["final"],
        "sha256": ER.result_digest(ep["final"], years),
    })
    return rec
