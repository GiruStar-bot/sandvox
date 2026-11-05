# Laplace's Sandvox

**A simulated Japan, built only from information published up to 31 December 2024, run forward from January 2025, to test whether it produces the phenomena that really happened in 2025.**

The aim is an environment for training and evaluating AI agents that has *predictive validity*: if a world made only from pre-2025 data grows the same kinds of 2025 phenomena from the inside, it is a better place for AI to learn about, and act in, human society. The long-term aim is the whole world.

> Status: **early, research code (pre-alpha).** The model's move from GDScript to Python is complete (November 2026), and a first frame for every country, where an AI agent can take a country's ruler seat, is in place with Japan as the only filled country. Development pauses again until January 2027. The blind 2025 comparison has **not** been run yet, and no result is claimed. The test will be pre-registered before it is run.

## The idea in four rules

1. **Cut-off.** Every input was published on or before 2024-12-31. Every numeric leaf in `data/modern/` names its source and publication date in `data/modern/SOURCES_D477.csv`; a leaf with no date counts as a failure.
2. **Sealed answers.** The real 2025 values for the comparison were collected by a separate researcher and are kept outside this repository. The people who build the model do not read them.
3. **Endogenous phenomena only.** The comparison scores what the society produces by itself (prices, employment, births, households, migration and so on). External shocks (disasters, foreign policy decisions) are left out of the score.
4. **Physics-style, not curve-fitting.** The model is a population of people, households, firms and institutions with simple, sourced rules. Gates are conservation laws and phenomena; cell-by-cell matches are diagnostics, not targets.

## What is here

| Path | Contents |
|---|---|
| `py/` | The Python port (NumPy, optional Numba), where all new work is written. `py/core` holds the deterministic primitives; `py/tiers` the population tiers; `py/lchh` life course and households; `py/econ` the economy; `py/world` polity, laws and the world layer; `py/people` persons, relations and groups; `py/tiers/start` builds the 2025-01 start; `py/country` is the frame for every country (a registry of 215 countries, stubs marked UNSOURCED except Japan, a ruler seat per country, and a loader that refuses sealed or later-dated inputs). Each module reproduces the frozen GDScript reference bit for bit through recorded interfaces (SHA-256 per field per month; tests in `py/tests/`, oracle dump scripts in `tools/py/`), and `py/world/integrated.py` chains them into one month. |
| `sim/modern/` | The reference model in GDScript (Godot 4, headless): people, households, the national population tiers, economy, polity, views. Frozen as the parity oracle. |
| `sim/api/det_math.gd`, `sim/earth_core/keyed.gd` | Deterministic maths and keyed random numbers. Every number that enters the answer goes through them, so runs are reproducible across machines (`docs/team/DET_MATH.md`). |
| `data/modern/` | Input data for Japan at the start (2025-01): population by single age, sex and prefecture, households, labour, food, trade, banks, polity, and more, with sources. See `DATA_SOURCES.md` for terms. |
| `tools/` | Data builders (`tools/modern/build_*.py`), long runs, and the test runner. |
| `docs/team/` | The deterministic-maths spec (`DET_MATH.md`), the rules for writing on the Python core (`modern/py/CORE_GUIDE.md`, checked by `tools/py/lint_core.py`), the verifier's rubric (`verify/VERIFY_RUBRIC.md`), first principles and test notes. The design notes, declared checks and audits are not published yet: they quote 2025 values that must stay sealed until the comparison. |

Comments in the code refer to internal notes (decision numbers such as D477, report numbers such as R96) that are not public yet.

## Running

Python core (tested with Python 3.14 and NumPy 2.4):

```
pip install -r py/requirements.txt
python py/tests/test_p01_primitives.py        # deterministic maths and sampling match the reference
python py/tests/test_lint_core.py             # the core's rules are checked, and the checker catches planted faults
```

The module parity tests (`py/tests/run_*.py`) read oracle dumps made by `tools/py/oracle_dump_*.gd` on the reference model.

Reference model (Godot 4.7, headless, Linux or Windows):

```
godot --headless --path . --import
tools/run_tests.sh --tier smoke
```

Runs that load the national tiers need about 11-12 GB of memory each; run them one at a time. Month-by-month parity between the Python core and the reference is checked with `tools/py/oracle_dump.gd` and `py/tests/run_month.py`.

## How it is built

The project is designed and directed by one person and built with a team of AI coding agents (Claude Code): builders, a verifier, a mathematician and a researcher, each with written rules. Checks are declared before code is written, results are not tuned to the checks, and amended checks are marked AMENDED.

## Licence

- Code and our own documents: [Apache License 2.0](LICENSE).
- Input data keeps the terms of each publisher. Two tables whose terms do not allow redistribution are not included. Details and attributions: [DATA_SOURCES.md](DATA_SOURCES.md).

## 日本語の概要

2024 年 12 月 31 日までに公表された情報だけで日本の社会を作り、2025 年 1 月から動かします。そして、現実の 2025 年に起きた現象と似た現象が、社会の中から生まれるかを確かめます。AI の訓練と評価に使える世界をつくることが目的です。将来は世界全体を対象にします。今は研究の初期段階で、2025 年との比較はまだ行っていません。比較は事前登録してから行います。
