# VERIFY_RUBRIC — what every V report answers (PM, 2026-11-05, owner OK)

Why: until now the checks lived in each V brief and drifted between briefs. A V brief now says "per VERIFY_RUBRIC, plus: <extras>".
Every V report has one line per row: `R<n>: PASS | FAIL | N/A — <evidence: file:line, commit, count, or the command run>`.
A row marked N/A gives its reason. A FAIL names the smallest fix; the verifier never applies it.

| row | question | how |
|---|---|---|
| R1 | Do the rows pass on **your own** oracle output? | Dump on your box from the named modern commit; run the rows on the builder's head. Never reuse the builder's dump. |
| R2 | Do the declared must-fails detect? | Run them; each must FAIL for the reason it names. |
| R3 | Does at least one mutation of **your own** per rule area get caught? | Plant it in a copy; name the row that caught it. A survivor is either a gap (FAIL) or an equivalent mutant (say why). |
| R4 | Does every rule path run at least once? | Line trace over the whole row run (sys.monitoring or trace). List lines never run, each classed: proven unreachable (proof) / guard / unused helper / gap (FAIL). |
| R5 | Is any check vacuous? | Look for checks that cannot fail (`kit.check(True, ...)`, a compare of a value with itself, a row whose input never reaches the code). |
| R6 | Does the code keep CORE_GUIDE? | `python tools/py/lint_core.py` gives hits=0. List every **new** `# lint-ok:` line in the diff with its reason; each one needs the PM's OK (an OVERRIDE), so the builder cannot grant it alone. |
| R7 | Does the change stay in scope? | `python tools/py/lint_core.py --base <modern commit> --plan <the port's PLAN>`: every changed file outside docs/ is named in the plan; every new state field is declared in the plan before its code. |
| R8 | Does D477 hold? | No input dated after 2024-12-31 (D477_checks LA rows); no sealed 2025 value read; MANIFEST re-hashed after any data change. |
| R9 | Is the report findable? | Commit subject starts `PING PM: V<nnn>`; the report is under docs/team/verify/reports/; dumps under dumps/<module>/<commit>/. |

## Scale of a check (PM, 2026-11-05)
- A new port or any change of behaviour: all rows.
- A change that only adds tests, or removes lines proven never to run: the PM reads the diff and merges; no V report. The verifier is asked only if the PM's read finds a doubt.

## lint_core false hits
- A hit that the code really needs (CORE_GUIDE allows it, or the rule is too broad) is marked on its line `# lint-ok: <reason>` and listed under R6 for the PM.
- If the rule itself is wrong, say so in the report (FYI to the PM) with the line; the PM changes lint_core.py and its test (py/tests/test_lint_core.py). Never work around the lint by rewriting code to dodge the pattern.
