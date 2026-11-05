# The other-country frame (Cpくん; D483, the owner; a plan only, with its rows declared before any code)

D483 asks for the frame that lets a second country run on the Python core after the persons merge. This document is the plan. Its
proving row is the first one to pass: **Japan run through the frame gives today's digests bit for bit**. Every Japan-specific
assumption becomes a value of a country's data, and the code path stays the one P2, Q-1, S0-a and I-1 already check. No code is
written before this plan is agreed.

## 1. The country's data: one schema, one loader
**Today's files**, read by name in py/:
- `data/modern/jpn/status_2024.json`: the cohort, life table and indicators;
- `data/modern/people/jpn_{people,tiers,households}_2024.json`: the persons' specs;
- `data/modern/polity/jpn_{prefectures,election,organs,laws}.json`;
- `data/modern/econ/crop_farming_jpn.json` and econ's `*_jpn.json`;
- `data/modern/jpn/cohort_2025-01-01.json` and `data/modern/jpn/flows_2023_2024/`: rule (D) and its inputs.

**The frame's layout:**
- `data/modern/<cc>/` holds a country's own files, each under one name fixed by the frame (`status.json`, `people.json`,
  `tiers.json`, `households.json`, `regions.json`, `polity/…`, `econ/…`, `start/` for its rule-(D)-like start inputs);
- `data/modern/<cc>/country.json` is the manifest. It gives every file's edition year and the country's cut-off (§2), and the
  per-country constants of §3, each with its source and a T/S/D label as SOURCES rows carry.

**The loader:** `py/country/` (new) has `load(cc) -> Country`.
- It reads the manifest and every file through `tiers.start.load.load_json` (Godot's reading: numbers as floats, then canon).
- It gives each layer its inputs by role: `country.status`, `country.people_spec`, `country.tiers_spec`, `country.regions`, …
- **No file name or country id appears in a layer's code.** Every `res://data/modern/people/%s_people_2024.json`,
  `polity/jpn_prefectures.json`, `"JPN"` literal and `status_%d` in py/ becomes a field of the Country.
- **Japan's files stay where they are:** `data/modern/jpn/country.json` names today's paths, so no Japan file moves and the
  oracles' data roots stay valid.

## 2. The cut-off and the seal, per country (D477 generalised)
- **Each country's manifest declares its cut-off date** (Japan: 2024-12-31) and its comparison year (Japan: 2025). It also names
  its sealed store (Japan: research-notes `reports/sealed/`).
- **Row F-seal:** every SOURCES row of a country carries a publication date on or before its cut-off. The loader refuses a
  manifest whose SOURCES has a later date, unless the row is labelled CHECK ONLY. This is the rule verifyくん's LA audit applies
  today, as a row.
- **Each country's start date is its cut-off + 1 day.** A rule-(D)-like ageing brings the latest in-window population base to that
  date, with the country's own flows, labelled F/D as Japan's are. The rule's code takes the country's tables. Its Japan-only
  parts are the 速報/概数 choice, 住基 and 人口推計, so a country declares its own sources for births, deaths and migration in its
  manifest.
- **The builders never read a country's sealed values**, as for Japan.

## 3. The Japan-specific assumptions in py/, which become per-country values

| Where (file:line, at 6e140b25 + this branch) | What is Japan's | Becomes |
|---|---|---|
| py/tiers/start/create.py:8-12, py/tiers/start/tconst.py:2, py/people/layer.py:22-23, py/people/hh_bind.py:16 | the spec and status file names (`%s_people_2024.json`, `polity/jpn_prefectures.json`, `status_%d`) | the Country's paths |
| py/tiers/start/create.py:51, 71, 82; py/tiers/start/p.py:106; py/econ/month.py:44; py/econ/actors.py:15, 23 | the key "JPN" as a default | the Country's id, no default |
| py/world/world.py:199-306; py/world/integrated.py:91-119 | the one entity "JPN" in the status, the polity, the chronicle and the labour glue | the run's country (or countries) |
| py/world/world.py:219; py/world/polity/election.py:16, organs.py:60, 74, public.py:21 | crop_farming_jpn, and the polity's files by key | the Country's polity and econ files |
| py/tiers/start/a_fit.py:42, 68, 429, 548; py/lchh/households.py:380, 454; py/tiers/start/age_d.py:27 | the regions as two-digit codes 01–47 ("%02d") | the regions' own codes from regions.json, formatted by the country's code width |
| py/core/keyed.py `pid(seed, region_id, …)`; people.gd's pid via `pref` | a person's id keyed on the prefecture code | the region index, so Japan keeps its codes (1–47) as the index; a new country numbers its regions 1..R |
| py/tiers/start/p.py:61, 75, 76, 94 (EMPLOYMENT, PENSION_AGE 65, HOUSEHOLD, EDUCATION) | Japan's categories: regular / non-regular work, a pension age of 65, the census's household types, three education levels | the Country's categories, with each rule's tables keyed by them; a country with other categories maps them in its manifest (D) |
| py/tiers/start/tconst.py:3-24 (BANDS, NTYPE, NEMP, NCLASS, ADULT_FROM 20, PEN_* kinds) | the tiers' bands and classes, adulthood at 20 (DINA's), Japan's pension kinds (basic, employee) | the Country's constants; the bands (5-year, 85+ open) and the cohort's 101 ages stay the frame's |
| py/people/loop_c.py:146, 153 (`month % 12 == 0`, `revision_month_index`) | the pension's January record and April revision | the Country's pension calendar (already in the spec for April) |
| py/people/loop_c.py:337, 340, 342 (ages 22, 15, 65) | entering work at 22 after study, school's end at 15, retirement at 65 | the Country's life-course ages |
| py/people/loop_c.py:420; py/lchh/life_course.py:641, 658 (`*_man_yen`) | money in 万円 | the Country's currency and unit, with the spec's values in it |
| py/tiers/start/age_d.py (all; :19-27, :96-113, :170-355) | rule (D)'s sources (人口推計, 速報/概数, 住基, R100) and months | a per-country start rule: the frame's ageing (birth-month groups, μ split, keyed rounding, the D-c/D-s/D-n/D-k rows) over a country's declared flows |
| py/world/integrated.py:91, py/econ (rice, 食糧法) | the state rice stock and its release law | a country's own instruments, declared in its polity and econ files |

This list comes from a grep of py/ (the ids, file names, region codes, units and calendar ages). The verify step re-reads each
layer for an assumption the grep cannot see, such as a rate fitted to Japan inside a spec. Those are data already, and they move
with their file.

## 4. The rows, declared before code
| Row | What it shows |
|---|---|
| **F-0 (the proving row)** | Japan through the frame gives today's digests bit for bit: P2's months 1–13 (f704874f… m01, 52f1fee9… m13); S0-a/S0-p at 19_weights; Q-1's 24 months; L 49/49 and Q-b 54/54; I-1cp's 24 months; the 2025-01 start's digest 02c960be…. Every row runs with the Country loaded from `data/modern/jpn/country.json`, and no layer reads a path by itself |
| F-load | the loader reads every file Japan's run reads today, and only those: a run under a file-access trace lists the same set before and after the frame |
| F-seal | §2: a SOURCES row dated after the cut-off makes the loader refuse, unless it is CHECK ONLY. The must-fail is one Japan row's date moved to 2025-01-02 |
| F-lit | lint_core gets a rule: a country id literal ("JPN"), a `_2024.json` path or a `"%02d"` region format in py/ outside py/country/ is a hit |
| F-new (the template for a new country, cc) | (a) F-load and F-seal on cc's manifest; (b) conservation (the start's population equals cc's start-rule total exactly; money and goods in E-c) and seeded determinism (the same seed gives one digest twice, on both platforms), the hard rows of D477; (c) the start rule's own D-c, D-s, D-n and D-k on cc's flows; (d) cc's cell checks as diagnostics, reported and not gating; (e) a smoke row of 13 months with no error and every non-finite value listed (Q-nan's helper rows) |
| F-mf | a must-fail: Japan's manifest with one constant changed (PENSION_AGE 65 to 66) makes F-0's Q-1 differ in employment and pension, so the frame is shown to carry the value it claims to carry |

**Done when** F-0, F-load, F-seal, F-lit and F-mf pass on Linux, and F-0 also on Windows (the PM). F-new is then the bar for each
new country.

## 5. Order and size
1. The loader and Japan's manifest (§1), with F-load and F-seal.
2. One layer at a time moved onto the Country, in the order tiers start, tiers month, persons, econ, world. After each, F-0's rows
   for that layer pass before the next layer moves.
3. F-lit last, when no literal is left.

The country's constants of §3 move in step 2 with the layer that reads them. Nothing is fitted; values only move from code to data,
which is why F-0 is bit for bit.

## 6. AMENDED (D483 as amended by the owner, modern 61d1b2f3): every country as a stub, and a ruler's seat in each
The aim is a world simulation, not Japan alone: a prototype of every country, with an LLM able to take any country's ruler seat.
This section plans a prototype of that prototype, so that January can start on countries at once. Code still starts after the
persons merge, and rows come before code.

### 6.1 The country registry, with a stub for every country
- **The source of the ids:** `data/modern/entities.json`, the field's 215 entities (193 UN members, 2 observers, 13 dependencies,
  7 regions), each with its ISO A3 key and English name. The registry is `data/modern/countries.json`, one row per entity:
  - `id` (the A3 key), `name_en`, `kind` (un_member, observer, dependency, region) and `macro`;
  - `status`: "filled" (Japan) or "stub";
  - for a stub, a `manifest` that points at `data/modern/stub/country.json`, a shared template.
- **A stub's placeholder sizes:** its population is a placeholder, labelled **UNSOURCED** in the row and in every output that shows
  it. It comes from one formula over a single number per stub (a round population figure, a placeholder, not a fact), and the
  persons and tiers sizes are scaled from it. Every placeholder value carries the label `"UNSOURCED (stub, D483)"` in SOURCES, and
  F-seal accepts UNSOURCED rows only for a country whose status is "stub".
- **Not modelled for a stub:** its prefectures or regions (one region), its tiers' fitted tables (Japan's shapes are used, labelled
  UNSOURCED), its economy's actors (none), its polity (one office, the ruler's), and its elections (none). A stub claims nothing
  about its country.

### 6.2 The ruler's seat and the view, per country
- **Today:** the seat is py/world/seats.py (`Seat.scripted`, `Seat.replay`, transcribed from modern_seats.gd) over py/world/view.py
  (`View.load_view(view_key, …)`, `observe(w, me)`), with Japan's view in `data/modern/views/jpn.json`.
- **The frame's seat:** `seat_for(country_id, mode)` builds a Seat for any registry id. Its view is the country's `views/<id>.json`
  if the manifest names one; otherwise it is the stub view, `data/modern/views/stub.json`.
  - **What the stub view holds:** the country's own indicators (its placeholders, labelled UNSOURCED), the world's public
    entities, and the ruler's levers.
  - **The stub's levers:** the same lever ids as Japan's that need no polity of their own (a budget lever and a policy-rate lever),
    each with its response function's defaults. Japan's levers stay Japan's.
- **The LLM's side:** the seat gives an observation (View.text_of) and takes actions (to_world) as today. A stub country's seat
  works the same way and is labelled "stub: its numbers are placeholders" in the observation's header.

**AMENDED with the first code (the prototype seat):** the seat built now, `py/country/seat.py` `RulerSeat`, works over the country's
persons and not over py/world's View. That view holds Japan alone today, and a stub has no field, polity or economy to observe.
- **What the seat does:** it observes the country's id and name, its status, its population (a placeholder for a stub), the
  persons' summary and its levers. It gives the observation as text, its header naming the country, with the UNSOURCED label for a
  stub. It takes the ruler's levers and applies them in the next month's env.
- **The stub's levers** are `data/modern/stub/levers.json`: the three ids the persons' month reads with no polity of its own (a
  tax rise, a child allowance, a fuel subsidy). Japan's are its own levers.json.
- **Japan's world seat** (py/world/seats.py) is unchanged. Generalising it to every country is January's work, once a country has
  a world to observe.

### 6.3 Japan stays the one filled country
Japan's manifest is today's files, as §1 says. **F-0 is unchanged and stays the proving row:** Japan through the frame, with the
other 214 countries registered as stubs and not run, gives today's digests bit for bit. A second form, F-0w, runs Japan with every
stub also stepped in the same world. Japan's digests must still be equal, because a stub reads no state of Japan's and writes none.

### 6.4 What is claimed for a stub country: one month runs without error
| Row | What it shows |
|---|---|
| F-reg | the registry has 215 rows, one per entities.json entity, ids unique, Japan the only "filled"; every stub's placeholder rows are labelled UNSOURCED |
| F-stub | each of the 214 stubs builds its start and steps one month (persons on a small sample, tiers on its one region, its seat observed once) with no error and every non-finite value listed (Q-nan's helper rows). Nothing else is claimed |
| F-seat | a seat built for Japan and for three stubs (one UN member, one dependency, one region) gives an observation whose header names the country and, for a stub, the UNSOURCED label; a scripted action on each is applied with no error |
| F-0w | Japan's F-0 digests are unchanged with the 214 stubs stepped in the same world |
| F-iso | a must-fail: a stub made to write one of Japan's indicators makes F-0w differ, which shows F-0w would see a leak |

**Done when** F-reg, F-stub, F-seat, F-0w and F-iso pass, beside §4's rows. Filling a country later means replacing its stub
manifest with its own sourced files and meeting F-new (§4) for it.

## 7. The files the frame changes (lint_core's scope, R7)
py/country/__init__.py, py/country/seat.py, tools/py/country_registry.py, data/modern/countries.json, data/modern/jpn/country.json,
data/modern/stub/country.json, data/modern/stub/regions.json, data/modern/stub/levers.json, py/tests/test_country.py; the layers that
now read their files through the Country: py/tiers/start/create.py, py/tiers/start/persons.py (p.PENSION_AGE, F-mf), py/people/layer.py, py/people/hh_bind.py,
py/tests/test_start_2025.py, py/tests/test_persons_layer.py; docs/team/modern/py/FRAME_PLAN.md. D480 3(b)'s M037b work (START_PORT_PLAN §9) is not on the frame's branch: its code was taken out after d68b2757 (V019b, the PM), and a branch for it can be cut from d68b2757, where its tests and the flag stand as last run.

## 8. AMENDED after the frame's three rounds: the rows' state, and what is left for the January restart
- **Pass** (py/tests/test_country.py, 12/12): F-reg, F-stub (215 countries, one month under a seat, no error), F-seat, F-seal, F-load,
  F-0w, F-iso, F-lit and F-mf. F-0 (Japan bit for bit through the frame) passes on S0-a, S0-c, L, Q-b, I-1 and rule (D).
- **F-lit, as built:** a ratchet, not yet the lint rule. A country literal ("JPN", a "_2024.json" file name, a "%02d" region format)
  may appear outside py/country only in the files not yet moved, listed in test_country.py's NOT_MOVED: py/world/world.py,
  py/world/integrated.py, py/econ/actors.py, py/econ/month.py, py/lchh/households.py, py/tiers/start/a_fit.py (the "%02d" region keys),
  py/tiers/start/age_d.py (rule (D)'s Japan sources), py/tiers/start/create.py (the "JPN" defaults), py/tiers/start/p.py (state's
  default), py/tiers/start/tconst.py (the oracle's SPEC). 47 literals remain. A literal in any other file fails. The lint rule comes
  when the list is empty.
- **F-mf, AMENDED:** the pension age comes from the manifest (`constants.pension_age`, into `p.PENSION_AGE`), and 66 makes the tiers
  start differ at 06_class. The persons' sample does not read it, because people.gd reads PENSION_AGE only with tiers on. `_year`'s
  retirement at 65 (py/people/loop_c.py, people.gd's literal) is a constant still to move.
- **Left for the January restart (the open list):**
  1. the world and econ onto the Country (py/world/world.py, integrated.py, py/econ), so a run's country is not "JPN" by name;
  2. the region codes as the regions' own (a_fit, py/lchh), the life-course ages (15, 22, 65), the currency unit, and the pension
     calendar into the manifest;
  3. rule (D) as a per-country start rule over declared flows;
  4. Q-1's 24 months through the frame, and F-0 on Windows;
  5. F-seal on a machine-readable edition column in SOURCES (150 rows have no ISO date);
  6. a world for a stub, so py/world's View and seat serve any country.
- **Known limit of the seal (V019c, the PM):** refuse_sealed resolves a path (./, ../, //, the case, symlinks: F-seal-l's rows) but
  reads only the name it resolves to, so a hard link inside data/ to a sealed file is served under its innocent name. Low risk:
  sealed files never sit in this tree (D477, research-notes reports/sealed/), so there is nothing here to hard-link to. Why not
  check inodes: a hard link has no target name, so refusing it would need every sealed file's inode, which this tree does not have.
