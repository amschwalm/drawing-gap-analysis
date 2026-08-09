# Cross-Sheet Coordination

Claude **skill for between-sheet drawing coordination**. Attach it to drawing
agents so they verify callouts, section cuts, and plan↔section/RCP consistency
on **both sides**, instead of reviewing sheets in isolation.

Uses sibling [`datagrid-api-orchestrator`](../datagrid-api-orchestrator) for
transport. Complements
[`drawing-geometric-analysis`](../drawing-geometric-analysis) (within-sheet
geometry).

## Install / attach

Keep under `<project>/.claude/skills/cross-sheet-coordination/` (or
`~/.claude/skills/`). Enable it on the Drawing Revision Reviewer session when
running coordination sweeps.

## Quick start

```bash
python scripts/analyze_pairs.py \
  --pairs pairs.json \
  --agent "Drawing Revision Reviewer" \
  --teamspace "KSA Demo" \
  --project-scope "5150 El Camino Real / The Harken Apartments" \
  --out results_cross_sheet --concurrency 16
```

`pairs.json` is a list of bundles; each bundle has 2–4 `sheets` with at least
`number`. Prefer `file_id` on every sheet.

## Layout

```
cross-sheet-coordination/
├── SKILL.md
├── README.md
├── scripts/
│   ├── prompts.py
│   └── analyze_pairs.py
└── references/
    ├── coordination-checklist.md
    └── output-schema.md
```
