# Geometry pass output schema

The geometry pass must return **JSON only**:

```json
{
  "sheet": "A7.03",
  "title": "WALL SECTIONS",
  "revision": "7",
  "set": "IFC SET",
  "geometry_reviewed": true,
  "views_inspected": ["plan", "section", "detail"],
  "findings": [
    {
      "issue": "short geometry conflict",
      "view": "plan|section|elevation|rcp|detail",
      "location": "grid / detail number / room / stair id",
      "measured_values": ["value A from X", "value B from Y"],
      "conflict": "why these values cannot both be true",
      "constructability_risk": "high|medium|low",
      "confidence": "high|medium|low",
      "evidence": "exactly what you read from the drawing"
    }
  ],
  "unverified": [
    {
      "item": "what could not be verified",
      "reason": "illegible|missing dimension|wrong/missing sheet image|ambiguous graphics"
    }
  ]
}
```

If no geometric conflicts are visible, return `"findings": []`.
Do not invent dimensions or clearances.
