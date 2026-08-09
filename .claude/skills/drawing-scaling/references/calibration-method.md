# Scale calibration method

Goal: convert page distance → real feet/inches **with evidence**, then measure
rooms, distances, and linear footage.

## Step 1 — Collect independent rulers (on this sheet only)

Prefer, in order:

1. **Drawn dimension strings** spanning a clear graphic length (best)
2. **Gridline spacing** with a labeled dimension (e.g. A→B = 30'-0")
3. **Graphic scale bar** (with units)
4. **Stated scale** in the title block / view (e.g. 1/8" = 1'-0") — use only
   after checking it against at least one drawn dimension when possible

Record each ruler as: what was measured on the page, the real-world value, and
where it was read.

## Step 2 — Calibrate

- Derive a scale factor (e.g. feet per inch of page, or feet per pixel if that
  is how you reason — be explicit).
- Prefer the **median** of agreeing rulers; if rulers disagree by more than
  ~2–3%, report a `scale_conflict` and lower confidence.
- Note whether the view is **enlarged detail**, **partial plan**, or has
  **mixed scales** on one sheet — never apply one view's scale to another view.

## Step 3 — Measure

For each target:

1. Identify endpoints on the graphics (grids, walls, faces, centerlines)
2. State whether the measurement is **interior clear**, **centerline**,
   **outside face**, etc.
3. Convert with the calibrated scale
4. When an explicit dimension string already answers the question, **prefer that
   string** and mark `source: "dimension_string"`
5. For areas: length × width with both legs evidenced; note irregular shapes
6. For linear footage: path definition (which face/centerline) + total

## Step 4 — Honesty rules

- Do **not** invent grid spacing or scales.
- If the sheet image is missing/illegible, put targets in `unverified`.
- If only the title-block scale is available (no confirming dim), mark
  `calibration.confidence: "low"` and say so.
- Distorted scans, photos of boards, and non-ortho crops invalidate page-scale
  takeoff — say so and fall back to printed dimensions only.
