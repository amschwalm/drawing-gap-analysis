# Drawing scaling output schema

Return **JSON only**:

```json
{
  "sheet": "A2.01",
  "title": "LEVEL 2 FLOOR PLAN",
  "revision": "7",
  "set": "IFC SET",
  "scaling_reviewed": true,
  "calibration": {
    "stated_scale": "1/8\" = 1'-0\"",
    "rulers": [
      {
        "type": "dimension_string|grid_spacing|scale_bar|stated_scale",
        "label": "grid A to B",
        "real_world": "30'-0\"",
        "page_observation": "how the page length was judged",
        "location": "where on the sheet",
        "implies_scale": "optional derived statement"
      }
    ],
    "adopted_scale": "1/8\" = 1'-0\" (confirmed by grid A–B dim)",
    "scale_factor": "explicit conversion used",
    "confidence": "high|medium|low",
    "conflicts": []
  },
  "measurements": [
    {
      "id": "room_201",
      "target": "Room 201 interior clear size and area",
      "kind": "room|distance|clearance|linear_footage|area|span",
      "value": "12'-4\" x 14'-0\"",
      "value_secondary": "172 sf",
      "units": "ft-in|sf|lf",
      "source": "scaled|dimension_string|mixed",
      "method": "calibrated scale from grid A–B; interior face to face",
      "endpoints": ["west wall face", "east wall face"],
      "location": "Room 201 / grids B-C / 2-3",
      "confidence": "high|medium|low",
      "evidence": "exactly what was read or scaled from the drawing"
    }
  ],
  "unverified": [
    {
      "item": "what could not be measured",
      "reason": "illegible|missing_dimension|no_reliable_scale|wrong/missing sheet image|ambiguous_endpoints|mixed_scale_view"
    }
  ]
}
```

If calibration fails, still return any explicit dimension-string values with
`source: "dimension_string"` and put scaled targets in `unverified`.
