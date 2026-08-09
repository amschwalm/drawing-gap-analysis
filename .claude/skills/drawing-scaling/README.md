# Drawing Scaling

Claude **skill for calibrated drawing measurement**. Attach it to drawing agents
so they derive real-world sizes from gridlines, in-sheet dimensions, and
graphic/stated scales — room sizes, distances, clearances, linear footage.

Uses sibling [`datagrid-api-orchestrator`](../datagrid-api-orchestrator) for
transport.

## Install / attach

Keep under `<project>/.claude/skills/drawing-scaling/` (or `~/.claude/skills/`).
Enable on the Drawing Revision Reviewer session for takeoff / sizing work.

## Quick start

```bash
python scripts/measure_sheets.py \
  --sheets sheets.json \
  --agent "Drawing Revision Reviewer" \
  --teamspace "KSA Demo" \
  --project-scope "5150 El Camino Real / The Harken Apartments" \
  --out results_scaling --concurrency 16
```

Prefer `"file_id"` on each sheet. Optional `"measure"` list and
`"known_dimensions"` improve targeting and calibration.

## Layout

```
drawing-scaling/
├── SKILL.md
├── README.md
├── scripts/
│   ├── prompts.py
│   └── measure_sheets.py
└── references/
    ├── calibration-method.md
    └── output-schema.md
```
