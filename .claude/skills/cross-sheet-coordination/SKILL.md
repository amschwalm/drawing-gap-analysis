---
name: cross-sheet-coordination
description: "Cross-sheet constructability coordination for construction drawings — verify callouts, section cuts, detail references, plan↔RCP/section mismatches, and A/S/M/E interfaces across paired sheets. Use when the user wants cross-sheet verification, coordination between plan and section, missing referenced details, or multi-sheet conflict finding. Attach this skill to drawing agents (e.g. Drawing Revision Reviewer) so they check both sides of every reference instead of reviewing sheets in isolation. Trigger on phrases like cross-sheet, coordination, plan vs section, missing detail callout, related sheets, or verify references across sheets."
---

# Cross-Sheet Coordination

A **Claude skill you attach to drawing-review agents** to force verification
**across paired sheets**: callouts, section cuts, detail bubbles, plan↔section /
plan↔RCP consistency, and discipline interfaces — not single-sheet isolation.

Transport uses the sibling
[`datagrid-api-orchestrator`](../datagrid-api-orchestrator) skill. Pair this with
[`drawing-geometric-analysis`](../drawing-geometric-analysis) for within-sheet
geometry; this skill owns **between-sheet** methodology.

```
cross-sheet-coordination/
├── SKILL.md
├── README.md
├── scripts/
│   ├── prompts.py          # coordination prompt builders
│   └── analyze_pairs.py    # concurrent pair/bundle runner
└── references/
    ├── coordination-checklist.md
    └── output-schema.md
```

## When to attach this skill

- After (or beside) a one-sheet geometry pass
- When Drawing Revision Reviewer invents "related sheets" without opening them
- Plan ↔ wall section / stair section / RCP bundles
- Architectural ↔ structural / MEP interface checks

## Setup

1. Keep `datagrid-api-orchestrator` installed beside this skill.
2. Configure `DATAGRID_API_KEY` / `Datagrid_API_KEY` via that skill's `.env`.
3. Smoke: `python ../datagrid-api-orchestrator/scripts/datagrid_client.py whoami`

## Core workflow

Jobs are **sheet pairs or small bundles** (2–4 sheets), not one sheet alone:

```bash
python scripts/analyze_pairs.py \
  --pairs pairs.json \
  --agent "Drawing Revision Reviewer" \
  --teamspace "KSA Demo" \
  --project-scope "5150 El Camino Real / The Harken Apartments" \
  --out results_cross_sheet --concurrency 16
```

Example `pairs.json` entry:

```json
{
  "tag": "coord_A2.01_A7.03",
  "relation": "plan_to_section",
  "focus": "wall sections and floor-to-floor at grids B/3–D/5",
  "sheets": [
    {"number": "A2.01", "title": "LEVEL 2 FLOOR PLAN", "role": "plan", "file_id": "..."},
    {"number": "A7.03", "title": "WALL SECTIONS", "role": "section", "file_id": "..."}
  ]
}
```

Prefer `file_id` on every sheet so both sides attach. See `analyze_pairs.py`
header for the full schema.

## What the agent must do

See `references/coordination-checklist.md`. In short:

1. Open **every** sheet in the bundle (attachments are sheets of record)
2. Trace callouts / section marks / detail bubbles **both directions**
3. Compare dimensions, alignments, and openings that claim to be the same condition
4. Flag missing referenced sheets/details and one-sided references
5. Return **JSON only** per `references/output-schema.md`

Do not invent content on a sheet that was not provided. Mark `unverified` when a
referenced sheet is absent or illegible.

## Relationship to other skills

| Concern | Skill |
| --- | --- |
| Datagrid API / concurrency | `datagrid-api-orchestrator` |
| Within-sheet geometry / dimensions | `drawing-geometric-analysis` |
| Between-sheet callouts & interfaces | **this skill** |
| Calibrated size / distance / LF takeoff | [`drawing-scaling`](../drawing-scaling) |
