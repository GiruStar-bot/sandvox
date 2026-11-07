# Roadmap v3 phase B: the evaluation interface (examination-style
# design, user decision 2026-11-07 - the environment gives no reward;
# a third party sets challenges, the AI proposes, a third party
# evaluates). These checks pin the three formats and the environment's
# side of the loop: faithful presentation, structural validation,
# faithful simulation, evidence records.
#   python py/tests/test_eval_interface.py
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import Kit  # noqa: E402  (puts py/ on the path)

import eval_interface as EI  # noqa: E402


def main():
    k = Kit("py/tests/test_eval_interface.py")

    ch = EI.build_challenge({"years": 5, "scenario": "baseline", "n_per": 2},
                            prompt="Debt/GDP is on a rising path. Propose measures.",
                            constraints={"max_acts": 3},
                            challenge_id="t-1")
    k.check(len(ch["observation_history"]) == 5
            and "consumption_tax_rate" in ch["lever_catalogue"]
            and isinstance(ch["lever_catalogue"]["consumption_tax_rate"]["max"], (int, float))
            and ch["constraints"] == {"max_acts": 3} and ch["prompt"].startswith("Debt/GDP"),
            "E challenge carries the do-nothing observation history, the lever catalogue with bounds, the prompt and the constraints")

    good = {"acts": [{"lever": "consumption_tax_rate", "value": 0.13, "when": "initial"}],
            "rationale": "Raise consumption tax to slow debt growth."}
    k.check(EI.validate_proposal(good, ch) == [],
            "E a well-formed proposal (lever bundle + rationale) validates clean")

    bounded = next(lid for lid, b in ch["lever_catalogue"].items()
                   if isinstance(b.get("max"), (int, float)))
    bad_cases = [
        ({"acts": [{"lever": "no_such_lever", "value": 1.0}], "rationale": "x"}, "unknown lever"),
        ({"acts": [{"lever": bounded, "value": ch["lever_catalogue"][bounded]["max"] + 1.0}], "rationale": "x"}, "out-of-bounds value"),
        # The two cases measured on the merged main (2026-11-07): the engine
        # itself enacted both at face value, so the interface must refuse them.
        ({"acts": [{"lever": "child_allowance", "value": 100000.0}], "rationale": "x"}, "child_allowance at 10x its catalogue max"),
        ({"acts": [{"lever": "consumption_tax_rate", "value": -0.05}], "rationale": "x"}, "negative consumption tax rate"),
        ({"acts": [{"lever": "consumption_tax_rate", "value": 0.13}]}, "missing rationale"),
        ({"acts": [{"lever": "consumption_tax_rate", "value": 0.13, "when": 1900}], "rationale": "x"}, "when outside the challenge years"),
        ({"acts": [{"lever": "consumption_tax_rate", "value": 0.13}] * 4, "rationale": "x"}, "max_acts constraint"),
    ]
    all_flagged = True
    for prop, _name in bad_cases:
        if not EI.validate_proposal(prop, ch):
            all_flagged = False
    ch_forbid = dict(ch, constraints={"forbidden_levers": ["consumption_tax_rate"]})
    all_flagged &= bool(EI.validate_proposal(good, ch_forbid))
    k.check(all_flagged,
            "E structural validation flags unknown levers, out-of-bounds values, missing rationale, bad timing and constraint violations - and nothing else")

    rec = EI.run_examination(ch, good)
    rec2 = EI.run_examination(ch, good)
    k.check(rec["valid"] and rec["sha256"] == rec2["sha256"],
            "E the same challenge + proposal reproduces the same record hash exactly")
    # Sensitivity probe: the P0-verified actuation channel (child_allowance
    # at the initial call moves births over 10y). A consumption-tax act on
    # the same path becomes a Diet bill under the minority government and
    # leaves the trajectory unchanged - checked as record evidence below,
    # which is the honest behaviour of the Diet-mediated engine.
    ch10 = EI.build_challenge({"years": 10, "scenario": "baseline", "n_per": 2}, challenge_id="t-10")
    splash = {"acts": [{"lever": "child_allowance", "value": 10000.0, "when": "initial"}],
              "rationale": "Maximum child allowance to lift births."}
    rec_s = EI.run_examination(ch10, splash)
    rec_e = EI.run_examination(ch10, {"acts": [], "rationale": "Do nothing."})
    births_s = sum(r["births"] for r in rec_s["years"])
    births_e = sum(r["births"] for r in rec_e["years"])
    k.check(rec_s["sha256"] != rec_e["sha256"] and births_s > births_e,
            "E policy sensitivity: an actuating proposal moves the trajectory (10y births %d -> %d)" % (births_e, births_s))
    k.check(rec["proposal"]["rationale"] == good["rationale"]
            and len(rec["acts_outcome"]) >= 1
            and rec["acts_outcome"][0]["lever"] == "consumption_tax_rate"
            and rec["acts_outcome"][0]["result"] is not None,
            "E the record carries the proposal and rationale verbatim and the Diet outcome of each act, as evidence for the examiner")
    bad_rec = EI.run_examination(ch, {"acts": [{"lever": "nope", "value": 1.0}], "rationale": "x"})
    k.check(bad_rec["valid"] is False and bad_rec["problems"] and "final" not in bad_rec,
            "E an invalid proposal is not simulated; the record carries the structural problems instead")

    k.check(isinstance(ch.get("mode_note"), str) and "full_mode" in ch["mode_note"]
            and rec["challenge"]["mode_note"] == ch["mode_note"],
            "E a standard-mode challenge carries the explicit mode note (law-type proposals show no numeric signal without elections) and the record echoes it")
    ch_full = EI.build_challenge({"years": 3, "scenario": "baseline", "n_per": 2, "full_mode": True},
                                 challenge_id="t-full")
    k.check(ch_full["mode_note"] is None,
            "E a full_mode challenge needs no mode note (elections give law-type proposals a real path)")

    ch_r = EI.build_challenge({"years": 5, "scenario": "baseline", "n_per": 2,
                               "randomize": True, "seed": 11, "index": 0},
                              challenge_id="t-rand")
    rec_r = EI.run_examination(ch_r, {"acts": [], "rationale": "Observe under drawn parameters."})
    k.check(len(rec_r["draws"]) > 0,
            "E a randomized challenge's record carries the parameter draws (the examiner sees the exact conditions)")

    ch25 = EI.build_challenge({"years": 25, "scenario": "baseline", "n_per": 2}, challenge_id="t-base")
    base = EI.run_examination(ch25, {"acts": [], "rationale": "Baseline examination."})
    k.check(base["final"]["population"] == 100644584 and abs(base["final"]["debt_gdp"] - 334.0) < 0.05,
            "E an empty proposal on the default challenge reproduces the merged baseline exactly (pop %d, debt %.1f)"
            % (base["final"]["population"], base["final"]["debt_gdp"]))

    k.finish()


if __name__ == "__main__":
    main()
