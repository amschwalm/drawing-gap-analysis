#!/usr/bin/env python3
"""Concurrent drawing scale calibration + measurement runner.

Attaches scaling methodology to a Datagrid drawing agent.
Transport comes from sibling skill datagrid-api-orchestrator.

Sheet list JSON (array):
  {
    "tag": "scale_A2.01",             # optional
    "number": "A2.01",                # required
    "title": "LEVEL 2 FLOOR PLAN",
    "revision": "7",
    "set": "IFC SET",
    "file_id": "optional-file-id",
    "measure": [
      "Room 201 interior clear size and area",
      "Corridor LF grid A to D south run"
    ],
    "known_dimensions": [
      {"label": "grid A to B", "value": "30'-0\\\""}
    ],
    "project_scope": "optional override",
    "knowledge_ids": ["..."]
  }

Examples:
  python measure_sheets.py \\
    --sheets sheets.json \\
    --agent "Drawing Revision Reviewer" \\
    --teamspace "KSA Demo" \\
    --project-scope "5150 El Camino Real / The Harken Apartments" \\
    --out results_scaling --concurrency 16
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

SCRIPT_DIR = Path(__file__).resolve().parent
SKILLS_DIR = SCRIPT_DIR.parents[1]
ORCH_SCRIPTS = SKILLS_DIR / "datagrid-api-orchestrator" / "scripts"
if str(ORCH_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(ORCH_SCRIPTS))
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from datagrid_client import DatagridClient, DatagridError  # noqa: E402
from prompts import build_prompt_with_file, build_scaling_prompt  # noqa: E402


def _slug(s: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9._-]+", "_", (s or "").strip()).strip("_")
    return s[:80] or "sheet"


def _sheet_tag(sheet: Dict[str, Any]) -> str:
    if sheet.get("tag"):
        return _slug(str(sheet["tag"]))
    num = sheet.get("number") or sheet.get("sheet") or "sheet"
    return _slug(f"scale_{num}")


def _resolve_agent_id(
    client: DatagridClient,
    job: Dict[str, Any],
    default_agent: Optional[str],
    default_id: Optional[str],
) -> str:
    if job.get("agent_id") or default_id:
        return str(job.get("agent_id") or default_id)
    name = job.get("agent") or default_agent
    if not name:
        raise DatagridError("Provide --agent / --agent-id or per-sheet agent/agent_id")
    found = client.find_agent(str(name))
    if not found:
        raise DatagridError(f"Agent not found: {name!r}")
    return found["id"]


def _safe_credits(resp: dict) -> Any:
    credits = resp.get("credits") or {}
    if isinstance(credits, dict):
        return credits.get("consumed", credits)
    return credits


def measure_sheet(
    client: DatagridClient,
    sheet: Dict[str, Any],
    *,
    agent_id: str,
    teamspace: Optional[str],
    project_scope: str,
    knowledge_ids: Optional[List[str]] = None,
    chat_mode: Optional[str] = None,
) -> Dict[str, Any]:
    """Run one calibrate-then-measure converse call for a sheet."""
    tag = _sheet_tag(sheet)
    number = sheet.get("number") or sheet.get("sheet")
    if not number:
        raise DatagridError(f"Sheet job {tag!r} missing number")

    scope = str(sheet.get("project_scope") or project_scope)
    kids = sheet.get("knowledge_ids") or knowledge_ids or []
    file_id = sheet.get("file_id")
    chat_mode = sheet.get("chat_mode") or chat_mode

    text_prompt = build_scaling_prompt(sheet, project_scope=scope)
    prompt = build_prompt_with_file(text_prompt, file_id)

    started = time.time()
    resp = client.converse(
        prompt,
        agent_id=agent_id,
        teamspace=teamspace,
        knowledge_ids=list(kids) if kids else None,
        conversation_id=sheet.get("conversation_id"),
        chat_mode=chat_mode,
        config=sheet.get("config"),
    ) or {}

    return {
        "tag": tag,
        "sheet": {
            "number": number,
            "title": sheet.get("title"),
            "revision": sheet.get("revision") or sheet.get("latest_revision"),
            "set": sheet.get("governing_set") or sheet.get("set"),
            "date": sheet.get("date"),
            "file_id": file_id,
            "project_scope": scope,
            "measure": sheet.get("measure") or sheet.get("targets") or [],
            "known_dimensions": sheet.get("known_dimensions")
            or sheet.get("known_grid_spacing")
            or [],
        },
        "agent_id": agent_id,
        "teamspace": teamspace,
        "text": client.message_text(resp),
        "raw": resp,
        "conversation_id": resp.get("conversation_id"),
        "tool_calls_count": len(resp.get("tool_calls") or []),
        "credits_consumed": _safe_credits(resp),
        "elapsed_sec": round(time.time() - started, 2),
        "finished_at": datetime.now(timezone.utc).isoformat(),
    }


def _write_result(out_dir: Path, result: Dict[str, Any]) -> None:
    tag = result["tag"]
    (out_dir / f"{tag}.json").write_text(
        json.dumps(result, indent=2, default=str), encoding="utf-8"
    )
    sheet = result.get("sheet") or {}
    targets = sheet.get("measure") or []
    target_preview = ", ".join(
        (t.get("target") if isinstance(t, dict) else str(t)) for t in targets[:4]
    )
    lines = [
        f"# {tag}",
        "",
        f"- sheet: {sheet.get('number')} — {sheet.get('title')}",
        f"- revision/set: {sheet.get('revision')} / {sheet.get('set')}",
        f"- targets: {target_preview or '(auto major rooms/spans)'}",
        f"- teamspace: {result.get('teamspace')}",
        f"- tools: {result.get('tool_calls_count')}",
        f"- credits: {result.get('credits_consumed')}",
        f"- elapsed_sec: {result.get('elapsed_sec')}",
        f"- conversation_id: `{result.get('conversation_id')}`",
        "",
        "## Scaling output",
        "",
        result.get("text") or "_empty_",
        "",
    ]
    (out_dir / f"{tag}.md").write_text("\n".join(lines), encoding="utf-8")


def _write_summary(out_dir: Path, results: List[Dict[str, Any]]) -> None:
    lines = [
        "# Drawing scaling summary",
        "",
        f"Sheets: {len(results)}",
        "",
        "| tag | sheet | targets | tools | credits | elapsed_s |",
        "| --- | --- | ---: | ---: | ---: | ---: |",
    ]
    for r in sorted(results, key=lambda x: x.get("tag") or ""):
        sheet = r.get("sheet") or {}
        n_targets = len(sheet.get("measure") or [])
        lines.append(
            "| {tag} | {sheet} | {targets} | {tools} | {credits} | {elapsed} |".format(
                tag=r.get("tag"),
                sheet=sheet.get("number"),
                targets=n_targets if n_targets else "auto",
                tools=r.get("tool_calls_count"),
                credits=r.get("credits_consumed"),
                elapsed=r.get("elapsed_sec"),
            )
        )
    (out_dir / "SUMMARY.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(
        description="Drawing scale calibration and measurement"
    )
    p.add_argument("--sheets", required=True, help="JSON list of sheet objects")
    p.add_argument("--agent", default=None, help="Datagrid agent name")
    p.add_argument("--agent-id", default=None, help="Datagrid agent id")
    p.add_argument("--teamspace", default=None, help="Teamspace name or id")
    p.add_argument(
        "--project-scope",
        default="",
        help="Project scope sentence injected into prompts",
    )
    p.add_argument(
        "--knowledge-ids",
        default="",
        help="Comma-separated knowledge ids attached to each job",
    )
    p.add_argument("--out", default="results_scaling", help="Output directory")
    p.add_argument("--concurrency", type=int, default=16)
    p.add_argument("--chat-mode", default=None)
    args = p.parse_args(argv)

    if not ORCH_SCRIPTS.is_dir():
        print(
            f"Missing sibling skill scripts at {ORCH_SCRIPTS}. "
            "Install datagrid-api-orchestrator beside this skill.",
            file=sys.stderr,
        )
        return 2

    sheets = json.loads(Path(args.sheets).read_text(encoding="utf-8"))
    if not isinstance(sheets, list) or not sheets:
        print("--sheets must be a non-empty JSON list", file=sys.stderr)
        return 2

    knowledge_ids = [x.strip() for x in args.knowledge_ids.split(",") if x.strip()]
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    results: List[Dict[str, Any]] = []
    errors: List[str] = []

    def _worker(sheet: Dict[str, Any]) -> Dict[str, Any]:
        client = DatagridClient(teamspace=sheet.get("teamspace") or args.teamspace)
        agent_id = _resolve_agent_id(client, sheet, args.agent, args.agent_id)
        return measure_sheet(
            client,
            sheet,
            agent_id=agent_id,
            teamspace=sheet.get("teamspace") or args.teamspace,
            project_scope=args.project_scope
            or sheet.get("project_scope")
            or "the active project only",
            knowledge_ids=sheet.get("knowledge_ids") or knowledge_ids,
            chat_mode=args.chat_mode,
        )

    print(f"Drawing scaling: {len(sheets)} sheet(s), concurrency={args.concurrency}")
    with ThreadPoolExecutor(max_workers=max(1, args.concurrency)) as pool:
        futures = {pool.submit(_worker, s): s for s in sheets}
        for fut in as_completed(futures):
            sheet = futures[fut]
            tag = _sheet_tag(sheet)
            try:
                result = fut.result()
                _write_result(out_dir, result)
                results.append(result)
                print(
                    f"[ok] {result['tag']} credits={result.get('credits_consumed')} "
                    f"sheet={(result.get('sheet') or {}).get('number')}"
                )
            except Exception as e:
                msg = f"{tag}: {e}"
                errors.append(msg)
                print(f"[ERROR] {msg}", file=sys.stderr)
                (out_dir / f"{tag}.error.json").write_text(
                    json.dumps(
                        {"tag": tag, "error": str(e), "sheet": sheet},
                        indent=2,
                        default=str,
                    ),
                    encoding="utf-8",
                )

    _write_summary(out_dir, results)
    print(f"Wrote {out_dir}/SUMMARY.md ({len(results)} ok, {len(errors)} errors)")
    return 1 if errors and not results else 0


if __name__ == "__main__":
    sys.exit(main())
