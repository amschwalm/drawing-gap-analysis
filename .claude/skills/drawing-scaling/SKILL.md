---
name: drawing-scaling
description: "Calibrate construction drawing page scale from gridlines, in-sheet dimension strings, and graphic/stated scales, then measure real-world sizes — room dimensions/areas, distances, clearances, and linear footage. Use when the user wants to scale a sheet, measure rooms, get distances between features, compute wall/corridor LF, or convert page measurements to feet/inches. Attach this skill to drawing agents so they calibrate before measuring instead of guessing from the title-block scale alone. Trigger on phrases like scale the drawing, measure this room, linear footage, how far, calibrate gridlines, or what size is."
---

# Drawing Scaling

A **Claude skill you attach to drawing-review agents** to force **scale
calibration before measurement**: use gridlines, drawn dimension strings, and
graphic/stated scales to convert page distance into real feet/inches — then
report room sizes, distances, clearances, and linear footage.

Transport uses sibling
[`datagrid-api-orchestrator`](../datagrid-api-orchestrator). Pair with
[`drawing-geometric-analysis`](../drawing-geometric-analysis) for conflict
finding; this skill owns **quantitative takeoff from calibrated scale**.

```
drawing-scaling/
├── SKILL.md
├── README.md
├── scripts/
│   ├── prompts.py           # calibration + measurement prompt builders
│   └── measure_sheets.py    # concurrent sheet scaling runner
└── references/
    ├── calibration-method.md
    └── output-schema.md
```

## When to attach this skill

- "How big is room X?" / "What's the LF of this corridor?"
- Takeoffs from plans/sections/elevations when CAD is unavailable
- Checking whether a clearance or span matches a claimed dimension
- Anytime the agent must **not** trust the title-block scale alone

## Setup

1. Keep `datagrid-api-orchestrator` installed beside this skill.
2. Configure `DATAGRID_API_KEY` / `Datagrid_API_KEY`.
3. Smoke: `python ../datagrid-api-orchestrator/scripts/datagrid_client.py whoami`

## Core workflow

```bash
python scripts/measure_sheets.py \
  --sheets sheets.json \
  --agent "Drawing Revision Reviewer" \
  --teamspace "KSA Demo" \
  --project-scope "5150 El Camino Real / The Harken Apartments" \
  --out results_scaling --concurrency 16
```

Sheet JSON needs at least `number`. Prefer `file_id`. Optional fields:

```json
{
  "number": "A2.01",
  "title": "LEVEL 2 FLOOR PLAN",
  "file_id": "...",
  "measure": [
    "Room 201 interior clear size and area",
    "Corridor LF from grid A to D on south run",
    "Distance door 201A swing to opposite wall"
  ],
  "known_dimensions": [
    {"label": "grid A to B", "value": "30'-0\""}
  ]
}
```

If `measure` is omitted, the agent calibrates and reports major room sizes /
primary spans visible on the sheet.

## Method (must follow)

See `references/calibration-method.md`. Short version:

1. **Collect rulers** — graphic scale bar, stated scale, grid spacing dims,
   long dimension strings on the sheet
2. **Calibrate** — derive feet-per-page-unit (or inches-per-inch) from ≥2
   independent rulers when possible; report agreement / conflict
3. **Measure** — apply the calibrated scale to targets; show raw page
   observation + converted real-world value
4. **Never invent** — if scale cannot be calibrated, return measurements only
   from explicit dimension strings, and mark scaled estimates `unverified`

Return **JSON only** per `references/output-schema.md`.

## Relationship to other skills

| Concern | Skill |
| --- | --- |
| Datagrid API / concurrency | `datagrid-api-orchestrator` |
| Geometry conflicts (mismatched dims) | `drawing-geometric-analysis` |
| Between-sheet callouts | `cross-sheet-coordination` |
| Calibrated size / distance / LF takeoff | **this skill** |
