#!/usr/bin/env python3
"""Concurrent cross-sheet coordination runner.

Attaches coordination methodology to a Datagrid drawing agent.
Transport comes from sibling skill datagrid-api-orchestrator.

Pairs JSON (array of bundles):
  {
    "tag": "coord_A2.01_A7.03",
    "relation": "plan_to_section",
    "focus": "wall sections at grids B/3–D/5",
    "sheets": [
      {"number": "A2.01", "title": "LEVEL 2 FLOOR PLAN", "role": "plan", "file_id": "..."},
      {"number": "A7.03", "title": "WALL SECTIONS", "role": "section", "file_id": "..."}
    ],
    "project_scope": "optional override",
    "knowledge_ids": ["..."]
  }

Also accepts {"anchor": {...}, "related": [{...}, ...]} instead of "sheets".

Examples:
  python analyze_pairs.py \\
    --pairs pairs.json \\
    --agent "Drawing Revision Reviewer" \\
    --teamspace "KSA Demo" \\
    --project-scope "5150 El Camino Real / The Harken Apartments" \\
    --out results_cross_sheet --concurrency 16
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
from prompts import (  # noqa: E402
    build_coordination_prompt,
    build_prompt_with_files,
    bundle_fields,
    iter_sheets,
)


def _slug(s: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9._-]+", "_", (s or "").strip()).strip("_")
    return s[:80] or "bundle"


def _bundle_tag(job: Dict[str, Any]) -> str:
    if job.get("tag"):
        return _slug(str(job["tag"]))
    sheets = iter_sheets(job)
    nums = [str(s.get("number") or s.get("sheet")) for s in sheets if s.get("number") or s.get("sheet")]
    if nums:
        return _slug("coord_" + "_".join(nums[:4]))
    return "coord_bundle"


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
        raise DatagridError("Provide --agent / --agent-id or per-job agent/agent_id")
    found = client.find_agent(str(name))
    if not found:
        raise DatagridError(f"Agent not found: {name!r}")
    return found["id"]


def _safe_credits(resp: dict) -> Any:
    credits = resp.get("credits") or {}
    if isinstance(credits, dict):
        return credits.get("consumed", credits)
    return credits


def analyze_bundle(
    client: DatagridClient,
    job: Dict[str, Any],
    *,
    agent_id: str,
    teamspace: Optional[str],
    project_scope: str,
    knowledge_ids: Optional[List[str]] = None,
    chat_mode: Optional[str] = None,
) -> Dict[str, Any]:
    """Run one cross-sheet coordination converse call for a sheet bundle."""
    tag = _bundle_tag(job)
    sheets = iter_sheets(job)
    if len(sheets) < 2:
        raise DatagridError(
            f"Bundle {tag!r} needs at least 2 sheets (got {len(sheets)}). "
            "Use sheets[] or anchor+related[]."
        )
    for i, s in enumerate(sheets):
        if not (s.get("number") or s.get("sheet")):
            raise DatagridError(f"Bundle {tag!r} sheet[{i}] missing number")

    scope = str(job.get("project_scope") or project_scope)
    kids = job.get("knowledge_ids") or knowledge_ids or []
    chat_mode = job.get("chat_mode") or chat_mode
    fields = bundle_fields(job, scope)

    text_prompt = build_coordination_prompt(job, project_scope=scope)
    prompt = build_prompt_with_files(text_prompt, sheets)

    started = time.time()
    resp = client.converse(
        prompt,
        agent_id=agent_id,
        teamspace=teamspace,
        knowledge_ids=list(kids) if kids else None,
        conversation_id=job.get("conversation_id"),
        chat_mode=chat_mode,
        config=job.get("config"),
    ) or {}

    return {
        "tag": tag,
        "relation": fields["relation"],
        "focus": fields["focus"],
        "sheets": [
            {
                "number": s.get("number") or s.get("sheet"),
                "title": s.get("title"),
                "role": s.get("role"),
                "revision": s.get("revision") or s.get("latest_revision"),
                "set": s.get("governing_set") or s.get("set"),
                "file_id": s.get("file_id"),
            }
            for s in sheets
        ],
        "agent_id": agent_id,
        "teamspace": teamspace,
        "project_scope": scope,
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
    sheet_nums = ", ".join(
        str(s.get("number")) for s in (result.get("sheets") or []) if s.get("number")
    )
    lines = [
        f"# {tag}",
        "",
        f"- relation: {result.get('relation')}",
        f"- focus: {result.get('focus')}",
        f"- sheets: {sheet_nums}",
        f"- teamspace: {result.get('teamspace')}",
        f"- tools: {result.get('tool_calls_count')}",
        f"- credits: {result.get('credits_consumed')}",
        f"- elapsed_sec: {result.get('elapsed_sec')}",
        f"- conversation_id: `{result.get('conversation_id')}`",
        "",
        "## Coordination output",
        "",
        result.get("text") or "_empty_",
        "",
    ]
    (out_dir / f"{tag}.md").write_text("\n".join(lines), encoding="utf-8")


def _write_summary(out_dir: Path, results: List[Dict[str, Any]]) -> None:
    lines = [
        "# Cross-sheet coordination summary",
        "",
        f"Bundles: {len(results)}",
        "",
        "| tag | relation | sheets | tools | credits | elapsed_s |",
        "| --- | --- | --- | ---: | ---: | ---: |",
    ]
    for r in sorted(results, key=lambda x: x.get("tag") or ""):
        sheets = ", ".join(
            str(s.get("number")) for s in (r.get("sheets") or []) if s.get("number")
        )
        lines.append(
            "| {tag} | {relation} | {sheets} | {tools} | {credits} | {elapsed} |".format(
                tag=r.get("tag"),
                relation=r.get("relation"),
                sheets=sheets,
                tools=r.get("tool_calls_count"),
                credits=r.get("credits_consumed"),
                elapsed=r.get("elapsed_sec"),
            )
        )
    (out_dir / "SUMMARY.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(description="Cross-sheet coordination analysis")
    p.add_argument("--pairs", required=True, help="JSON list of sheet pair/bundle jobs")
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
    p.add_argument("--out", default="results_cross_sheet", help="Output directory")
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

    jobs = json.loads(Path(args.pairs).read_text(encoding="utf-8"))
    if not isinstance(jobs, list) or not jobs:
        print("--pairs must be a non-empty JSON list", file=sys.stderr)
        return 2

    knowledge_ids = [x.strip() for x in args.knowledge_ids.split(",") if x.strip()]
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    results: List[Dict[str, Any]] = []
    errors: List[str] = []

    def _worker(job: Dict[str, Any]) -> Dict[str, Any]:
        client = DatagridClient(teamspace=job.get("teamspace") or args.teamspace)
        agent_id = _resolve_agent_id(client, job, args.agent, args.agent_id)
        return analyze_bundle(
            client,
            job,
            agent_id=agent_id,
            teamspace=job.get("teamspace") or args.teamspace,
            project_scope=args.project_scope
            or job.get("project_scope")
            or "the active project only",
            knowledge_ids=job.get("knowledge_ids") or knowledge_ids,
            chat_mode=args.chat_mode,
        )

    print(f"Cross-sheet coordination: {len(jobs)} bundle(s), concurrency={args.concurrency}")
    with ThreadPoolExecutor(max_workers=max(1, args.concurrency)) as pool:
        futures = {pool.submit(_worker, j): j for j in jobs}
        for fut in as_completed(futures):
            job = futures[fut]
            tag = _bundle_tag(job)
            try:
                result = fut.result()
                _write_result(out_dir, result)
                results.append(result)
                print(
                    f"[ok] {result['tag']} credits={result.get('credits_consumed')} "
                    f"sheets={[s.get('number') for s in result.get('sheets') or []]}"
                )
            except Exception as e:
                msg = f"{tag}: {e}"
                errors.append(msg)
                print(f"[ERROR] {msg}", file=sys.stderr)
                (out_dir / f"{tag}.error.json").write_text(
                    json.dumps(
                        {"tag": tag, "error": str(e), "job": job},
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
