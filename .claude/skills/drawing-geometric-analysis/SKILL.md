---
name: drawing-geometric-analysis
description: "Geometry-first constructability review of construction drawing sheets — dimensions, clearances, alignments, stair/ramp geometry, plan/section mismatches. Use when the user wants geometric validation, a geometry-only pass, dimension conflict finding, or two-pass drawing review (agent-native + geometry) on architectural/MEP/structural sheets. Attach this skill to drawing agents (e.g. Drawing Revision Reviewer) so they force a graphics/dimension-focused analysis instead of notes-only triage. Trigger on phrases like geometry pass, check dimensions, clearance conflicts, plan vs section mismatch, stair geometry, or analyze these sheets geometrically."
---

# Drawing Geometric Analysis

A **Claude skill you attach to drawing-review agents** to force geometry-first
sheet analysis: measurable conflicts visible in plan/section/elevation/RCP/detail
graphics — not notes, legends, schedules, or process boilerplate.

Transport uses the sibling
[`datagrid-api-orchestrator`](../datagrid-api-orchestrator) skill (API client +
concurrent runner). This skill owns the **geometry methodology, prompts, and
sheet runners**.

```
drawing-geometric-analysis/
├── SKILL.md
├── README.md
├── scripts/
│   ├── prompts.py          # geometry + pass-1 prompt builders
│   └── analyze_sheets.py   # concurrent geometry / two-pass runner
└── references/
    ├── geometry-checklist.md
    └── output-schema.md
```

## When to attach this skill

Attach (or enable) this skill whenever the agent should do **drawing geometry**
work, especially:

- Drawing Revision Reviewer / similar constructability agents
- One-sheet-at-a-time architectural sweeps
- Follow-ups after a notes-heavy agent pass that missed dimensions/clearances

Without this skill, drawing agents often triage notes and schedules and skip
true geometric verification. With it attached, Claude (or the runner) injects
the hardcoded geometry prompt and expects JSON findings with measured values.

## Setup

1. Keep [`datagrid-api-orchestrator`](../datagrid-api-orchestrator) installed
   beside this skill (same `.claude/skills/` tree).
2. Configure `DATAGRID_API_KEY` (or `Datagrid_API_KEY`) via that skill's
   `scripts/.env` or the environment.
3. Smoke: `python ../datagrid-api-orchestrator/scripts/datagrid_client.py whoami`

## Core workflow

**Geometry-only (recommended when attaching for geometric analysis):**
```bash
python scripts/analyze_sheets.py \
  --sheets sheets.json \
  --agent "Drawing Revision Reviewer" \
  --teamspace "KSA Demo" \
  --project-scope "5150 El Camino Real / The Harken Apartments" \
  --geometry-only \
  --out results_geometry --concurrency 16
```

**Two-pass (agent-native review, then geometry validation):**
```bash
python scripts/analyze_sheets.py \
  --sheets sheets.json \
  --agent "Drawing Revision Reviewer" \
  --teamspace "KSA Demo" \
  --project-scope "5150 El Camino Real / The Harken Apartments" \
  --out results_two_pass --concurrency 16
```

Sheet JSON objects need at least `number`. Prefer `file_id` so the sheet PDF/PNG
is attached as the sheet of record. See the header of `analyze_sheets.py`.

## What "geometry-only" means

The prompt (see `scripts/prompts.py` and `references/geometry-checklist.md`)
requires the agent to:

1. Use **only** drawing graphics and dimension strings on that sheet
2. Ignore general notes / schedules / keynotes unless needed to read a symbol
3. Report conflicts with **measured values** and evidence, or mark unverified
4. Return **JSON only** matching `references/output-schema.md`

Never invent geometry. If the sheet image is missing or illegible, put items in
`unverified` — do not fabricate clearances or dimensions.

## Prompting without the runner

If you already have a conversation with a drawing agent, paste the geometry
prompt from `build_geometry_prompt(...)` (or the template in `prompts.py`) and
attach the sheet file. One sheet per call. Prefer concurrency via
`analyze_sheets.py` for batches.

## Relationship to other skills

| Concern | Skill |
| --- | --- |
| Auth, teamspaces, explore, generic concurrent converse | `datagrid-api-orchestrator` |
| Within-sheet geometry / dimensions | **this skill** |
| Between-sheet callouts & plan↔section interfaces | [`cross-sheet-coordination`](../cross-sheet-coordination) |

Do not bury geometry methodology inside the generic Datagrid orchestrator —
attach **this** skill to the drawing agent workflow instead.
