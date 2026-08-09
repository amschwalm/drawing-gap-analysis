#!/usr/bin/env python3
"""Prompt builders for cross-sheet coordination analysis.

Attach this skill to a drawing agent, then use these builders (or analyze_pairs.py)
to force both-sides verification of callouts and interfaces.
"""

from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional, Sequence


COORDINATION_PROMPT = """Scope: {project_scope}
You are reviewing a SMALL BUNDLE of related construction drawing sheets for
CROSS-SHEET COORDINATION ONLY.

Bundle:
- Tag: {tag}
- Relation: {relation}
- Focus: {focus}

Sheets in this bundle (these are the ONLY sheets you may cite as reviewed):
{sheets_block}

INPUT RULES:
- Open and use EVERY sheet listed above. If a file/image is attached for a sheet, that attachment is the sheet of record.
- Trace references BOTH directions (plan→section/detail and reverse).
- Do NOT invent content for sheets outside this bundle. Put those under missing_references / unverified.
- Do NOT report process boilerplate, missing stamps, or generic "coordinate with MEP" without a concrete mismatch between sheets in this bundle.
- If something cannot be verified, mark it unverified. Do not invent.

TASK:
Find broken references and constructability conflicts that only appear when sheets are compared.

Check for:
1. Callout / section cut / detail bubble mismatches (mark exists on one side only, or wrong target)
2. Plan vs section mismatches (walls, openings, floor-to-floor, stairs/shafts)
3. Plan vs RCP mismatches (when both are in the bundle)
4. Detail vs host condition contradictions
5. Discipline interface conflicts when A + S/M/E sheets are bundled
6. Revision/set incoherence for the same condition across the bundle

OUTPUT ONLY JSON:
{{
  "tag": "{tag}",
  "relation": "{relation}",
  "sheets_reviewed": [{sheet_numbers_json}],
  "coordination_reviewed": true,
  "findings": [
    {{
      "issue": "short coordination conflict or broken reference",
      "category": "callout|dimension|alignment|opening|discipline_interface|revision",
      "sheets_involved": ["sheet", "sheet"],
      "location": "grid / mark / detail / room / stair id",
      "evidence_by_sheet": {{"SHEET": "what was read"}},
      "conflict": "why these cannot both be true, or how the reference is broken",
      "constructability_risk": "high|medium|low",
      "confidence": "high|medium|low"
    }}
  ],
  "missing_references": [
    {{
      "from_sheet": "SHEET",
      "reference": "mark/detail",
      "expected_sheet": "SHEET",
      "reason": "not_in_bundle|not_found_on_target|illegible"
    }}
  ],
  "unverified": [
    {{
      "item": "what could not be verified",
      "reason": "illegible|missing_sheet_image|ambiguous_graphics|outside_bundle"
    }}
  ]
}}

If no coordination conflicts are visible in this bundle, return "findings": [].
Return JSON only.
"""


def _sheet_line(sheet: Mapping[str, Any], index: int) -> str:
    number = sheet.get("number") or sheet.get("sheet") or f"sheet_{index}"
    title = sheet.get("title") or ""
    role = sheet.get("role") or sheet.get("relation") or ""
    revision = (
        sheet.get("revision")
        or sheet.get("latest_revision")
        or sheet.get("rev")
        or "?"
    )
    governing_set = sheet.get("governing_set") or sheet.get("set") or "most recent set"
    date = sheet.get("date") or ""
    file_note = "attached" if sheet.get("file_id") else "no file_id — use teamspace retrieval carefully"
    return (
        f"{index}. Number: {number}\n"
        f"   Title: {title}\n"
        f"   Role: {role or 'unspecified'}\n"
        f"   Revision/Set/Date: {revision} / {governing_set} / {date}\n"
        f"   File: {file_note}"
    )


def _normalize_sheets(job: Mapping[str, Any]) -> List[Dict[str, Any]]:
    sheets = job.get("sheets")
    if isinstance(sheets, list) and sheets:
        return [dict(s) for s in sheets if isinstance(s, Mapping)]

    # Convenience: anchor + related[]
    out: List[Dict[str, Any]] = []
    anchor = job.get("anchor")
    if isinstance(anchor, Mapping):
        a = dict(anchor)
        a.setdefault("role", "anchor")
        out.append(a)
    related = job.get("related") or []
    if isinstance(related, list):
        for item in related:
            if isinstance(item, Mapping):
                r = dict(item)
                r.setdefault("role", r.get("relation") or "related")
                out.append(r)
    return out


def bundle_fields(job: Mapping[str, Any], project_scope: str = "") -> Dict[str, str]:
    sheets = _normalize_sheets(job)
    numbers = [
        str(s.get("number") or s.get("sheet") or "")
        for s in sheets
        if (s.get("number") or s.get("sheet"))
    ]
    sheets_block = "\n".join(_sheet_line(s, i + 1) for i, s in enumerate(sheets))
    sheet_numbers_json = ", ".join(f'"{n}"' for n in numbers)
    return {
        "project_scope": project_scope
        or str(job.get("project_scope") or job.get("project") or "the active project only"),
        "tag": str(job.get("tag") or ("coord_" + "_".join(numbers[:3] if numbers else ["bundle"]))),
        "relation": str(job.get("relation") or job.get("relation_hint") or "related_sheets"),
        "focus": str(job.get("focus") or "all callouts and matching conditions across the bundle"),
        "sheets_block": sheets_block or "(no sheets listed)",
        "sheet_numbers_json": sheet_numbers_json or '""',
    }


def build_coordination_prompt(
    job: Mapping[str, Any],
    *,
    project_scope: str = "",
    template: Optional[str] = None,
) -> str:
    """Build the cross-sheet coordination prompt for one pair/bundle job."""
    fields = bundle_fields(job, project_scope)
    if job.get("coordination_prompt"):
        return str(job["coordination_prompt"]).format(**fields)
    return (template or COORDINATION_PROMPT).format(**fields)


def build_prompt_with_files(
    text_prompt: str,
    sheets: Sequence[Mapping[str, Any]],
) -> Any:
    """Return converse prompt with all available sheet file attachments."""
    file_ids = []
    for s in sheets:
        fid = s.get("file_id")
        if fid and str(fid) not in file_ids:
            file_ids.append(str(fid))
    if not file_ids:
        return text_prompt
    content: List[Dict[str, Any]] = [{"type": "input_text", "text": text_prompt}]
    for fid in file_ids:
        content.append({"type": "input_file", "file_id": fid})
    return [{"role": "user", "content": content}]


def iter_sheets(job: Mapping[str, Any]) -> List[Dict[str, Any]]:
    """Public helper: normalized sheet list for a job."""
    return _normalize_sheets(job)
