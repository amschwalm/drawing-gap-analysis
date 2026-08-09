#!/usr/bin/env python3
"""Prompt builders for drawing scale calibration and measurement.

Attach this skill to a drawing agent, then use these builders (or measure_sheets.py)
to force calibrate-then-measure takeoffs.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Mapping, Optional, Sequence


SCALING_PROMPT = """Scope: {project_scope}
You are reviewing ONE construction drawing sheet for SCALE CALIBRATION and
QUANTITATIVE MEASUREMENT ONLY.

Sheet:
- Number: {number}
- Title: {title}
- Revision: {revision}
- Set: {governing_set}
- Date: {date}

Known dimensions supplied by the caller (use as calibration hints; still verify on sheet):
{known_dimensions_block}

Measurement targets:
{measure_block}

INPUT RULES:
- If a file/image is attached, treat that attachment as the sheet of record.
- CALIBRATE before scaling. Prefer in-sheet dimension strings and labeled grid spacings over the title-block scale alone.
- Cross-check ≥2 independent rulers when available. If they disagree, report conflicts and lower confidence.
- Do not apply one view's scale to a different view on the same sheet (details often differ).
- Prefer an explicit dimension string over a scaled estimate when it answers the target.
- Do not invent grid spacing, scales, or endpoints. Mark unverified when calibration or endpoints are unclear.
- Ignore notes/schedules except where needed to identify a room name, grid id, or symbol.

TASK:
1) Calibrate page scale from gridlines / dimension strings / scale bar / stated scale.
2) Measure each target (room size/area, distances, clearances, linear footage) using the adopted scale.
3) If no targets were listed, measure major rooms and primary spans clearly visible on this sheet.

OUTPUT ONLY JSON:
{{
  "sheet": "{number}",
  "title": "{title}",
  "revision": "{revision}",
  "set": "{governing_set}",
  "scaling_reviewed": true,
  "calibration": {{
    "stated_scale": "as printed or null",
    "rulers": [
      {{
        "type": "dimension_string|grid_spacing|scale_bar|stated_scale",
        "label": "short label",
        "real_world": "e.g. 30'-0\\\"",
        "page_observation": "how page length was judged",
        "location": "where on sheet",
        "implies_scale": "optional"
      }}
    ],
    "adopted_scale": "what you used",
    "scale_factor": "explicit conversion",
    "confidence": "high|medium|low",
    "conflicts": []
  }},
  "measurements": [
    {{
      "id": "short_id",
      "target": "what was asked",
      "kind": "room|distance|clearance|linear_footage|area|span",
      "value": "primary value",
      "value_secondary": "optional e.g. sf",
      "units": "ft-in|sf|lf",
      "source": "scaled|dimension_string|mixed",
      "method": "how measured",
      "endpoints": ["from", "to"],
      "location": "grid/room/view",
      "confidence": "high|medium|low",
      "evidence": "exactly what was read or scaled"
    }}
  ],
  "unverified": [
    {{
      "item": "what could not be measured",
      "reason": "illegible|missing_dimension|no_reliable_scale|wrong/missing sheet image|ambiguous_endpoints|mixed_scale_view"
    }}
  ]
}}

Return JSON only.
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


def _format_known_dimensions(sheet: Mapping[str, Any]) -> str:
    known = sheet.get("known_dimensions") or sheet.get("known_grid_spacing") or []
    if isinstance(known, Mapping):
        # {"A-B": "30'-0\""} convenience form
        known = [{"label": k, "value": v} for k, v in known.items()]
    if not known:
        return "- (none supplied — calibrate only from sheet graphics)"
    lines: List[str] = []
    for i, item in enumerate(known, 1):
        if isinstance(item, Mapping):
            label = item.get("label") or item.get("name") or item.get("span") or f"ruler_{i}"
            value = item.get("value") or item.get("dimension") or item.get("real_world") or "?"
            lines.append(f"- {label}: {value}")
        else:
            lines.append(f"- {item}")
    return "\n".join(lines)


def _format_measure_targets(sheet: Mapping[str, Any]) -> str:
    targets = sheet.get("measure") or sheet.get("targets") or sheet.get("measurements") or []
    if not targets:
        return (
            "- (none supplied — calibrate, then measure major rooms and primary "
            "spans clearly visible on this sheet)"
        )
    lines: List[str] = []
    for i, t in enumerate(targets, 1):
        if isinstance(t, Mapping):
            label = t.get("target") or t.get("label") or t.get("id") or f"target_{i}"
            kind = t.get("kind")
            extra = f" [{kind}]" if kind else ""
            lines.append(f"{i}. {label}{extra}")
        else:
            lines.append(f"{i}. {t}")
    return "\n".join(lines)


def build_scaling_prompt(
    sheet: Mapping[str, Any],
    *,
    project_scope: str = "",
    template: Optional[str] = None,
) -> str:
    """Build the calibrate-then-measure prompt for one sheet."""
    fields = _sheet_fields(sheet, project_scope)
    fields["known_dimensions_block"] = _format_known_dimensions(sheet)
    fields["measure_block"] = _format_measure_targets(sheet)
    if sheet.get("scaling_prompt"):
        return str(sheet["scaling_prompt"]).format(**fields)
    return (template or SCALING_PROMPT).format(**fields)


def build_prompt_with_file(
    text_prompt: str,
    file_id: Optional[str] = None,
) -> Any:
    """Return converse prompt: plain string, or message with file attach."""
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


def build_prompt_with_files(
    text_prompt: str,
    file_ids: Sequence[str],
) -> Any:
    ids = [str(f) for f in file_ids if f]
    if not ids:
        return text_prompt
    content: List[Dict[str, Any]] = [{"type": "input_text", "text": text_prompt}]
    for fid in ids:
        content.append({"type": "input_file", "file_id": fid})
    return [{"role": "user", "content": content}]


def dumps_targets_preview(sheet: Mapping[str, Any]) -> str:
    """Small helper for logs / summaries."""
    targets = sheet.get("measure") or sheet.get("targets") or []
    try:
        return json.dumps(targets)[:200]
    except Exception:
        return str(targets)[:200]
