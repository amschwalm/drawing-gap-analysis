#!/usr/bin/env python3
"""Prompt builders for drawing geometric analysis.

Attach this skill to a drawing agent, then use these builders (or analyze_sheets.py)
to force a graphics/dimension-focused pass.
"""

from __future__ import annotations

from typing import Any, Dict, Mapping, Optional


GEOMETRY_PASS_PROMPT = """Scope: {project_scope}
You are reviewing ONE architectural drawing sheet for GEOMETRY ONLY.

Sheet:
- Number: {number}
- Title: {title}
- Revision: {revision}
- Set: {governing_set}
- Date: {date}

INPUT RULES:
- Use ONLY this sheet's drawing content (plan/section/elevation/RCP/detail graphics and dimension strings).
- If a file/image is attached, treat that attachment as the sheet of record.
- Do NOT use general notes, legends, schedules, or keynotes unless needed to interpret a drawn dimension/symbol.
- Do NOT report process issues, design-build scope gaps, missing stamps, code boilerplate, or "coordinate with MEP/structural" unless you can point to a drawn geometric conflict.
- If you cannot visually/geometrically verify something, mark it unverified. Do not invent.

TASK:
Extract measurable geometry and find constructability conflicts visible in the drawing graphics.

Check for:
1. Dimension conflicts (two different values for the same condition)
2. Plan vs section/elevation mismatches on this sheet
3. Clearance problems (door swings, accessible clear floor, head height, ramp slope geometry)
4. Alignment issues (grids, walls, stairs, shafts, openings not lining up across views)
5. Stair/ramp geometry errors (riser/tread counts vs floor-to-floor height)
6. Ceiling/soffit height conflicts shown in RCP/section graphics
7. Threshold/step/slope geometry conflicts at transitions
8. Missing critical dimensions required to build the drawn condition

OUTPUT ONLY JSON:
{{
  "sheet": "{number}",
  "title": "{title}",
  "revision": "{revision}",
  "set": "{governing_set}",
  "geometry_reviewed": true,
  "views_inspected": ["plan", "section", "detail"],
  "findings": [
    {{
      "issue": "short geometry conflict",
      "view": "plan|section|elevation|rcp|detail",
      "location": "grid / detail number / room / stair id",
      "measured_values": ["value A from X", "value B from Y"],
      "conflict": "why these values cannot both be true",
      "constructability_risk": "high|medium|low",
      "confidence": "high|medium|low",
      "evidence": "exactly what you read from the drawing"
    }}
  ],
  "unverified": [
    {{
      "item": "what could not be verified",
      "reason": "illegible|missing dimension|wrong/missing sheet image|ambiguous graphics"
    }}
  ]
}}

If no geometric conflicts are visible, return "findings": [].
Return JSON only.
"""


DEFAULT_PASS1_PROMPT = """Scope: {project_scope}

Review this ONE drawing sheet using your normal drawing-review capabilities
(revision/constructability/coordination analysis as configured on the agent).

Sheet:
- Number: {number}
- Title: {title}
- Revision: {revision}
- Set: {governing_set}
- Date: {date}

Focus on this sheet only. Cite concrete evidence from the sheet.
If a file/image is attached, treat that attachment as the sheet of record.

Return concise structured findings (JSON if possible) with:
sheet, title, revision, set, issues[{{issue, location, related_sheets, constructability_risk, evidence}}].
If no issues, return issues:[].
"""


def _sheet_fields(sheet: Mapping[str, Any], project_scope: str) -> Dict[str, str]:
    return {
        "project_scope": project_scope
        or str(sheet.get("project_scope") or sheet.get("project") or "the active project only"),
        "number": str(sheet.get("number") or sheet.get("sheet") or ""),
        "title": str(sheet.get("title") or ""),
        "revision": str(
            sheet.get("revision")
            or sheet.get("latest_revision")
            or sheet.get("rev")
            or "?"
        ),
        "governing_set": str(
            sheet.get("governing_set") or sheet.get("set") or "most recent set"
        ),
        "date": str(sheet.get("date") or ""),
    }


def build_pass1_prompt(
    sheet: Mapping[str, Any],
    *,
    project_scope: str = "",
    template: Optional[str] = None,
) -> str:
    """Build the agent-native (pass 1) prompt for one sheet."""
    fields = _sheet_fields(sheet, project_scope)
    if sheet.get("pass1_prompt"):
        return str(sheet["pass1_prompt"]).format(**fields)
    return (template or DEFAULT_PASS1_PROMPT).format(**fields)


def build_geometry_prompt(
    sheet: Mapping[str, Any],
    *,
    project_scope: str = "",
    template: Optional[str] = None,
) -> str:
    """Build the geometry-only prompt for one sheet (attach this skill's core pass)."""
    fields = _sheet_fields(sheet, project_scope)
    if sheet.get("geometry_prompt"):
        return str(sheet["geometry_prompt"]).format(**fields)
    return (template or GEOMETRY_PASS_PROMPT).format(**fields)


def build_prompt_with_file(
    text_prompt: str,
    file_id: Optional[str] = None,
) -> Any:
    """Return converse prompt: plain string, or input item list with file attach."""
    if not file_id:
        return text_prompt
    return [
        {
            "role": "user",
            "content": [
                {"type": "input_text", "text": text_prompt},
                {"type": "input_file", "file_id": file_id},
            ],
        }
    ]
