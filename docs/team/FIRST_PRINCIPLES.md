# FIRST_PRINCIPLES — how to think about world rules and policy (owner order 2026-10-25)

Read this file when the owner says a principle / policy talk is starting, and before any proposal that adds, changes or removes a world rule (death, birth, food, disease, war, laws, defaults, flags).

Why: agents get anchored on recent work and old rules, and answer with stopgaps. If the owner just agrees, the stopgap ships. This file is the guard.

## 1. Goal first (re-read every time)
- Deep time: simulate humans from about 60,000 years ago, coarse (cheap) computation. (owner, 2026-10-25)
- When civilization appears, the world becomes one that can connect to LLMs. (owner, 2026-10-25)
- 初心 and the wider aim: `CLAUDE.md` top.
- If the goal here looks old or wrong, ask the owner. Do not fill it in yourself.

## 2. Build from principles first
Before you open old rules, write down:
1. What must be true in the world for this goal? (facts about real humans, real numbers with sources)
2. What does the goal need at this grain? (60,000 years, coarse: what can be dropped, what must stay)
3. A design that comes only from 1 and 2.

## 3. Then use old rules as reference only
Old rules, D-entries and existing switches may save work (owner allows this). They are not reasons by themselves.
For every old rule the proposal leans on, write:
- `rule:` id or `file:line`
- `made for:` the goal, era and scope when it was made
- `still holds for the goal in 1?` yes / no / unknown, and why
- `verdict:` keep / change / retire

## 4. Proposal format (all four parts)
- **Goal used:** one line from section 1
- **From principles:** the design from section 2
- **Old rules checked:** the table from section 3
- **Gap:** where the principle design and the old-rule design differ, and which one you recommend

## 5. Red flags (stop and redo if you see one)
- The proposal is only "turn on / off an existing switch".
- You cite an era or scale that is not the goal (for example "3000 BC" when the goal starts 60,000 years ago).
- The only reason is "rule X says so" or "the default changes only at release".
- The model's shape (per-person, per-age band, per-village) is assumed, not asked.

## 6. Worked example (2026-10-25, deep-time deaths)
- Stopgap answer: "turn on `demog_law` (forager life table); keep `hazard_law` careful because measles did not exist in 3000 BC".
- What was missed: the goal starts 60,000 years ago, not 3000 BC. The rules "change defaults only at tuning release" and "sourced laws only, no fitting to results" were made for the village era and the benchmark, and were not checked against the coarse deep-time goal. The per-age-band death shape in `sim/world/lod/lod_kernel.gd` was not questioned.
