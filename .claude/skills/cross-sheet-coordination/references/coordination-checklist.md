# Cross-sheet coordination checklist

Work on a **small bundle** (typically 2–4 sheets). Never claim you checked a
sheet that was not attached or provided.

## Always check

1. **Callout both-sides** — every section cut, detail bubble, elevation mark, or
   keynote that points to another sheet in the bundle exists on the target, with
   matching mark/number
2. **One-sided references** — mark on A with no target on B (or reverse)
3. **Plan ↔ section** — wall locations, openings, floor-to-floor, slab edges,
   stair/shaft positions that claim to be the same condition
4. **Plan ↔ RCP** — walls/grids vs ceiling breaks, soffits, fixture/diffuser
   conflicts with structure or partitions shown on plan
5. **Detail ↔ host** — detail applies to the condition called out; scale/assembly
   does not contradict the host plan/section
6. **Discipline interface** (when A + S/M/E in bundle) — penetrations, beam/slab
   depths, shaft sizes, equipment pads vs architectural openings
7. **Revision coherence** — same revision/set story across the paired sheets for
   the condition under review (flag if one sheet is clearly superseded)

## Do not report

- Generic "coordinate with X" with no specific mismatch
- Title-block / stamp admin issues
- Within-sheet note-only nits (use geometry skill for measurable single-sheet dims)
- Conflicts on sheets outside the bundle — list them under `unverified` /
  `missing_references` instead of inventing findings

## Evidence bar

Each finding needs:

- `sheets_involved` (numbers)
- What was read on **each** side (`evidence_by_sheet`)
- Why the two (or more) cannot both be true, or why a reference is broken
- `constructability_risk` + `confidence`

If a related sheet is missing from the bundle, add it to `missing_references`
rather than guessing its content.
