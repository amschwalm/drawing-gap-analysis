# Drawing Geometric Analysis

Claude **skill for geometry-first construction drawing review**. Attach it to
drawing agents (for example Datagrid **Drawing Revision Reviewer**) so sheet
analysis focuses on dimensions, clearances, alignments, and plan/section
mismatches — not notes-only triage.

Uses the sibling [`datagrid-api-orchestrator`](../datagrid-api-orchestrator)
skill for API transport and concurrency.

## Install / attach

Copy (or keep) the whole folder under:

- `<project>/.claude/skills/drawing-geometric-analysis/` — project agents, or
- `~/.claude/skills/drawing-geometric-analysis/` — all local Claude Code sessions

Also keep `datagrid-api-orchestrator` installed beside it. Configure the Datagrid
API key in that skill's `scripts/.env`.

For **claude.ai** Skills upload: zip this folder and upload under Settings →
Capabilities → Skills (if enabled). Enable it on the agent/session that reviews
drawings.

## Quick start

```bash
# geometry-only pass (what you attach for geometric analysis)
python scripts/analyze_sheets.py \
  --sheets sheets.json \
  --agent "Drawing Revision Reviewer" \
  --teamspace "KSA Demo" \
  --project-scope "5150 El Camino Real / The Harken Apartments" \
  --geometry-only \
  --out results_geometry --concurrency 16
```

`sheets.json` is a list of objects with at least `"number"`. Prefer `"file_id"`
for the exact sheet PDF/PNG.

## Layout

```
drawing-geometric-analysis/
├── SKILL.md                      # skill entry (attach this)
├── README.md
├── scripts/
│   ├── prompts.py                # geometry + pass-1 builders
│   └── analyze_sheets.py         # concurrent runner
└── references/
    ├── geometry-checklist.md
    └── output-schema.md
```

## Why a separate skill?

The Datagrid orchestrator is generic API plumbing. Geometric drawing analysis is
a domain skill you **attach to the drawing agent**. Keeping them separate means
you can enable geometry methodology on Drawing Revision Reviewer (or any similar
agent) without mixing it into every Datagrid workflow.
