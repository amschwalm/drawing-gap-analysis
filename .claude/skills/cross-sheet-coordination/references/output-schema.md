# Cross-sheet coordination output schema

Return **JSON only**:

```json
{
  "tag": "coord_A2.01_A7.03",
  "relation": "plan_to_section",
  "sheets_reviewed": ["A2.01", "A7.03"],
  "coordination_reviewed": true,
  "findings": [
    {
      "issue": "short coordination conflict or broken reference",
      "category": "callout|dimension|alignment|opening|discipline_interface|revision",
      "sheets_involved": ["A2.01", "A7.03"],
      "location": "grid / mark / detail / room / stair id",
      "evidence_by_sheet": {
        "A2.01": "what was read on this sheet",
        "A7.03": "what was read on this sheet"
      },
      "conflict": "why these cannot both be true, or how the reference is broken",
      "constructability_risk": "high|medium|low",
      "confidence": "high|medium|low"
    }
  ],
  "missing_references": [
    {
      "from_sheet": "A2.01",
      "reference": "1/A7.12",
      "expected_sheet": "A7.12",
      "reason": "not_in_bundle|not_found_on_target|illegible"
    }
  ],
  "unverified": [
    {
      "item": "what could not be verified",
      "reason": "illegible|missing_sheet_image|ambiguous_graphics|outside_bundle"
    }
  ]
}
```

If coordination looks clean for the provided bundle, return `"findings": []`.
Do not invent content for sheets that were not provided.
