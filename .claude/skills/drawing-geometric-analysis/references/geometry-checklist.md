# Geometry checklist (per sheet)

Use this when reviewing **one** drawing sheet. Graphics and dimension strings
only unless a note is required to interpret a symbol.

## Always check

1. **Dimension conflicts** — two different values for the same condition
2. **Plan vs section/elevation** mismatches on this sheet
3. **Clearances** — door swings, accessible clear floor, head height, ramp slope
4. **Alignment** — grids, walls, stairs, shafts, openings across views
5. **Stair/ramp geometry** — riser/tread counts vs floor-to-floor height
6. **Ceiling/soffit heights** shown in RCP/section graphics
7. **Threshold / step / slope** geometry at transitions
8. **Missing critical dimensions** required to build the drawn condition

## Do not report (unless tied to drawn geometry)

- Design-build process / RFI boilerplate
- Missing stamps or title-block admin
- Generic "coordinate with MEP/structural" without a drawn conflict
- Schedule/note discrepancies with no graphic conflict

## Evidence bar

Every finding needs:

- `measured_values` read from the drawing
- `conflict` explaining why both cannot be true (or why a value is missing)
- `evidence` naming the view/detail/grid where it was read
- `confidence` reflecting legibility and whether the sheet file was attached

If you cannot verify, use `unverified` with reason:
`illegible` | `missing dimension` | `wrong/missing sheet image` | `ambiguous graphics`.
