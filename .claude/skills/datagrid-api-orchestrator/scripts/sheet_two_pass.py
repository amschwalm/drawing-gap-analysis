#!/usr/bin/env python3
"""Two-pass drawing sheet analysis helper (supplementary, not a full agent).

Pass 1 — Datagrid agent native review (whatever the agent is built to do).
Pass 2 — Hardcoded geometry-only validation (see geometry_pass.py).

Sheet list JSON (array):
  {
    "tag": "asheet_A7.03",          # optional; defaults from number
    "number": "A7.03",              # required
    "title": "WALL SECTIONS",
    "revision": "7",
    "set": "IFC SET",               # or governing_set
    "date": "2024-09-12",
    "file_id": "optional-file-id",  # attach sheet PDF/PNG when available
    "project_scope": "optional override",
    "pass1_prompt": "optional full override",
    "knowledge_ids": ["..."]        # optional per-sheet corpus
  }

Examples:
  python sheet_two_pass.py \\
    --sheets sheets.json \\
    --agent "Drawing Revision Reviewer" \\
    --teamspace "KSA Demo" \\
    --project-scope "5150 El Camino Real / The Harken Apartments" \\
    --out results_two_pass --concurrency 16

  # geometry pass only
  python sheet_two_pass.py --sheets sheets.json --agent-id ID --teamspace TS \\
    --geometry-only --out results_geom
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

from datagrid_client import DatagridClient, DatagridError
from geometry_pass import (
    build_geometry_prompt,
    build_pass1_prompt,
    build_prompt_with_file,
)


def _slug(s: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9._-]+", "_", (s or "").strip()).strip("_")
    return s[:80] or "sheet"


def _sheet_tag(sheet: Dict[str, Any]) -> str:
    if sheet.get("tag"):
        return _slug(str(sheet["tag"]))
    num = sheet.get("number") or sheet.get("sheet") or "sheet"
    return _slug(f"asheet_{num}")


def _resolve_agent_id(client: DatagridClient, job: Dict[str, Any], default_agent: Optional[str], default_id: Optional[str]) -> str:
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


def run_pass(
    client: DatagridClient,
    *,
    agent_id: str,
    prompt: Any,
    teamspace: Optional[str],
    knowledge_ids: Optional[List[str]],
    conversation_id: Optional[str] = None,
    chat_mode: Optional[str] = None,
    config: Optional[dict] = None,
) -> Dict[str, Any]:
    started = time.time()
    resp = client.converse(
        prompt,
        agent_id=agent_id,
        teamspace=teamspace,
        knowledge_ids=knowledge_ids or None,
        conversation_id=conversation_id,
        chat_mode=chat_mode,
        config=config,
    ) or {}
    return {
        "text": client.message_text(resp),
        "raw": resp,
        "conversation_id": resp.get("conversation_id"),
        "tool_calls_count": len(resp.get("tool_calls") or []),
        "credits_consumed": _safe_credits(resp),
        "elapsed_sec": round(time.time() - started, 2),
    }


def analyze_sheet_two_pass(
    client: DatagridClient,
    sheet: Dict[str, Any],
    *,
    agent_id: str,
    teamspace: Optional[str],
    project_scope: str,
    knowledge_ids: Optional[List[str]] = None,
    skip_pass1: bool = False,
    skip_geometry: bool = False,
    continue_conversation: bool = False,
    chat_mode: Optional[str] = None,
) -> Dict[str, Any]:
    """Run pass-1 agent review + pass-2 geometry validation for one sheet."""
    tag = _sheet_tag(sheet)
    number = sheet.get("number") or sheet.get("sheet")
    if not number:
        raise DatagridError(f"Sheet job {tag!r} missing number")

    scope = str(sheet.get("project_scope") or project_scope)
    kids = sheet.get("knowledge_ids") or knowledge_ids or []
    file_id = sheet.get("file_id")
    chat_mode = sheet.get("chat_mode") or chat_mode

    result: Dict[str, Any] = {
        "tag": tag,
        "sheet": {
            "number": number,
            "title": sheet.get("title"),
            "revision": sheet.get("revision") or sheet.get("latest_revision"),
            "set": sheet.get("governing_set") or sheet.get("set"),
            "date": sheet.get("date"),
            "file_id": file_id,
            "project_scope": scope,
        },
        "agent_id": agent_id,
        "teamspace": teamspace,
        "passes": {},
        "finished_at": None,
    }

    conversation_id = sheet.get("conversation_id")

    if not skip_pass1:
        p1_text = build_pass1_prompt(sheet, project_scope=scope)
        p1_prompt = build_prompt_with_file(p1_text, file_id)
        p1 = run_pass(
            client,
            agent_id=agent_id,
            prompt=p1_prompt,
            teamspace=teamspace,
            knowledge_ids=list(kids) if kids else None,
            conversation_id=conversation_id,
            chat_mode=chat_mode,
            config=sheet.get("config"),
        )
        result["passes"]["agent_native"] = p1
        if continue_conversation:
            conversation_id = p1.get("conversation_id") or conversation_id

    if not skip_geometry:
        p2_text = build_geometry_prompt(sheet, project_scope=scope)
        p2_prompt = build_prompt_with_file(p2_text, file_id)
        p2 = run_pass(
            client,
            agent_id=agent_id,
            prompt=p2_prompt,
            teamspace=teamspace,
            knowledge_ids=list(kids) if kids else None,
            conversation_id=conversation_id if continue_conversation else None,
            chat_mode=chat_mode,
            config=sheet.get("config"),
        )
        result["passes"]["geometry"] = p2

    result["finished_at"] = datetime.now(timezone.utc).isoformat()
    result["credits_consumed_total"] = sum(
        float(p.get("credits_consumed") or 0)
        for p in result["passes"].values()
        if isinstance(p.get("credits_consumed"), (int, float))
    )
    return result


def _write_result(out_dir: Path, result: Dict[str, Any]) -> None:
    tag = result["tag"]
    (out_dir / f"{tag}.json").write_text(
        json.dumps(result, indent=2, default=str), encoding="utf-8"
    )
    sheet = result.get("sheet") or {}
    lines = [
        f"# {tag}",
        "",
        f"- sheet: {sheet.get('number')} — {sheet.get('title')}",
        f"- revision/set: {sheet.get('revision')} / {sheet.get('set')}",
        f"- teamspace: {result.get('teamspace')}",
        f"- credits_total: {result.get('credits_consumed_total')}",
        "",
    ]
    for name, payload in (result.get("passes") or {}).items():
        lines += [
            f"## Pass: {name}",
            "",
            f"- tools: {payload.get('tool_calls_count')}",
            f"- credits: {payload.get('credits_consumed')}",
            f"- elapsed_sec: {payload.get('elapsed_sec')}",
            f"- conversation_id: `{payload.get('conversation_id')}`",
            "",
            payload.get("text") or "_empty_",
            "",
        ]
    (out_dir / f"{tag}.md").write_text("\n".join(lines), encoding="utf-8")


def _write_summary(out_dir: Path, results: List[Dict[str, Any]]) -> None:
    lines = [
        "# Two-pass sheet analysis summary",
        "",
        f"Sheets: {len(results)}",
        "",
        "| tag | sheet | pass1_tools | geom_tools | credits | elapsed_s |",
        "| --- | --- | ---: | ---: | ---: | ---: |",
    ]
    for r in sorted(results, key=lambda x: x.get("tag") or ""):
        p1 = (r.get("passes") or {}).get("agent_native") or {}
        p2 = (r.get("passes") or {}).get("geometry") or {}
        elapsed = float(p1.get("elapsed_sec") or 0) + float(p2.get("elapsed_sec") or 0)
        lines.append(
            "| {tag} | {sheet} | {p1t} | {p2t} | {credits} | {elapsed} |".format(
                tag=r.get("tag"),
                sheet=(r.get("sheet") or {}).get("number"),
                p1t=p1.get("tool_calls_count", ""),
                p2t=p2.get("tool_calls_count", ""),
                credits=r.get("credits_consumed_total"),
                elapsed=round(elapsed, 2),
            )
        )
    (out_dir / "SUMMARY.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(
        description="Two-pass drawing sheet analysis (agent native + geometry)"
    )
    p.add_argument("--sheets", required=True, help="JSON list of sheet objects")
    p.add_argument("--agent", default=None, help="Datagrid agent name")
    p.add_argument("--agent-id", default=None, help="Datagrid agent id")
    p.add_argument("--teamspace", default=None, help="Teamspace name or id")
    p.add_argument(
        "--project-scope",
        default="",
        help="Project scope sentence injected into both prompts",
    )
    p.add_argument(
        "--knowledge-ids",
        default="",
        help="Comma-separated knowledge ids attached to both passes",
    )
    p.add_argument("--out", default="results_two_pass", help="Output directory")
    p.add_argument("--concurrency", type=int, default=16)
    p.add_argument(
        "--continue-conversation",
        action="store_true",
        help="Run geometry pass in the same conversation as pass 1",
    )
    p.add_argument(
        "--geometry-only",
        action="store_true",
        help="Skip pass 1; run hardcoded geometry validation only",
    )
    p.add_argument(
        "--pass1-only",
        action="store_true",
        help="Skip geometry pass; run agent-native review only",
    )
    p.add_argument("--chat-mode", default=None)
    args = p.parse_args(argv)

    if args.geometry_only and args.pass1_only:
        print("Choose only one of --geometry-only / --pass1-only", file=sys.stderr)
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
        return analyze_sheet_two_pass(
            client,
            sheet,
            agent_id=agent_id,
            teamspace=sheet.get("teamspace") or args.teamspace,
            project_scope=args.project_scope
            or sheet.get("project_scope")
            or "the active project only",
            knowledge_ids=sheet.get("knowledge_ids") or knowledge_ids,
            skip_pass1=args.geometry_only,
            skip_geometry=args.pass1_only,
            continue_conversation=args.continue_conversation,
            chat_mode=args.chat_mode,
        )

    print(
        f"Two-pass analysis: {len(sheets)} sheet(s), concurrency={args.concurrency}, "
        f"pass1={'off' if args.geometry_only else 'on'}, "
        f"geometry={'off' if args.pass1_only else 'on'}"
    )
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
                    f"[ok] {result['tag']} credits={result.get('credits_consumed_total')} "
                    f"passes={list((result.get('passes') or {}).keys())}"
                )
            except Exception as e:
                msg = f"{tag}: {e}"
                errors.append(msg)
                print(f"[ERROR] {msg}", file=sys.stderr)
                (out_dir / f"{tag}.error.json").write_text(
                    json.dumps({"tag": tag, "error": str(e), "sheet": sheet}, indent=2, default=str),
                    encoding="utf-8",
                )

    _write_summary(out_dir, results)
    print(f"Wrote {out_dir}/SUMMARY.md ({len(results)} ok, {len(errors)} errors)")
    return 1 if errors and not results else 0


if __name__ == "__main__":
    sys.exit(main())
