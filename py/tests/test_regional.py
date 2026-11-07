# Roadmap axis J: regional dynamics.
#   python py/tests/test_regional.py
# The CLI ran national aggregates only (the Persons layer carries
# prefectures, the aggregate engine did not). This layer decomposes
# the national population into the 8 standard regions - MIC 2024
# population shares, census-based aged shares, internal-migration
# net rates, ISA foreign-resident distribution - and evolves it with
# the model's own yearly flows: births by a youth weight, deaths by
# an aging weight, international migrants by the foreign-resident
# distribution, and zero-sum inter-regional flows whose scale follows
# the jobs cycle. Depopulating regions age faster, and the resulting
# local fiscal stress feeds the local allocation tax (the phase's one
# deliberate feedback: baseline Debt/GDP 325.4 -> 328.3 at 25y;
# LAT_STRESS_PASS = 0 ablates it).
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import Kit  # noqa: E402  (puts py/ on the path)

import agent_env  # noqa: E402
import run_simulation as RS  # noqa: E402


def main():
    k = Kit("py/tests/test_regional.py")

    b = agent_env.run_episode(agent_env.null_policy, years=25, scenario="baseline")
    init = b["steps"][0]["obs"]["regions"]
    fin = b["steps"][-1]["obs"]["regions"]
    k.check(len(fin) == 8 and abs(sum(v["share"] for v in fin.values()) - 1.0) < 0.01
            and abs(sum(v["pop"] for v in fin.values()) - b["final"]["population"]) < 10,
            "J regions decompose the national population exactly (sum %d vs %d)"
            % (sum(v["pop"] for v in fin.values()), b["final"]["population"]))
    k.check(fin["kanto"]["share"] > init["kanto"]["share"] + 0.02
            and fin["tohoku"]["share"] < init["tohoku"]["share"] - 0.005,
            "J Tokyo concentration proceeds (Kanto %.1f%% -> %.1f%%, Tohoku %.1f%% -> %.1f%%)"
            % (init["kanto"]["share"] * 100, fin["kanto"]["share"] * 100,
               init["tohoku"]["share"] * 100, fin["tohoku"]["share"] * 100))
    ye = {s["year"]: s for s in b["steps"] if s["phase"] == "year_end"}
    k.check(fin["tohoku"]["aged"] > fin["kanto"]["aged"] + 0.08
            and ye[2049]["obs"]["row"]["local_stress"] > ye[2025]["obs"]["row"]["local_stress"] * 2,
            "J depopulating regions age faster (Tohoku %.1f%% vs Kanto %.1f%% aged) and local fiscal stress rises (%.2f -> %.2f)"
            % (fin["tohoku"]["aged"] * 100, fin["kanto"]["aged"] * 100,
               ye[2025]["obs"]["row"]["local_stress"], ye[2049]["obs"]["row"]["local_stress"]))

    saved = RS.LAT_STRESS_PASS
    RS.LAT_STRESS_PASS = 0.0
    try:
        ab = agent_env.run_episode(agent_env.null_policy, years=25, scenario="baseline")
    finally:
        RS.LAT_STRESS_PASS = saved
    k.check(ab["final"]["population"] == b["final"]["population"]
            and ab["final"]["debt_gdp"] < b["final"]["debt_gdp"],
            "J ablation: LAT_STRESS_PASS=0 keeps the population and removes the fiscal feedback (debt %.1f < %.1f)"
            % (ab["final"]["debt_gdp"], b["final"]["debt_gdp"]))

    k.finish()


if __name__ == "__main__":
    main()
