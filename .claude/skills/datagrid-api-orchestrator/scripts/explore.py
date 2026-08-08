#!/usr/bin/env python3
"""STAGE 1 — profile a Datagrid teamspace.

Usage:
  python explore.py --teamspace "My Teamspace" --out profile
  python explore.py --teamspace "My Teamspace" --out profile --queries probes.txt
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from datagrid_client import DatagridClient, DatagridError

DEFAULT_PROBES = [
    "What documents, drawings, specs, and reports exist in this teamspace?",
    "What tables and structured datasets are available, and what do they cover?",
    "What are the main projects, scopes, or workstreams represented in the data?",
    "What risks, gaps, open issues, or discrepancies appear across the knowledge?",
    "What schedules, budgets, change orders, or long-lead items are mentioned?",
]


def _safe_get(d: dict, *keys: str, default: Any = None) -> Any:
    cur: Any = d
    for k in keys:
        if not isinstance(cur, dict):
            return default
        cur = cur.get(k, default)
    return cur


def _load_queries(path: Optional[str]) -> List[str]:
    if not path:
        return list(DEFAULT_PROBES)
    lines = Path(path).read_text(encoding="utf-8").splitlines()
    queries = [ln.strip() for ln in lines if ln.strip() and not ln.strip().startswith("#")]
    return queries or list(DEFAULT_PROBES)


def _collect_knowledge(client: DatagridClient, teamspace: str) -> List[dict]:
    items: List[dict] = []
    for k in client.paginate("GET", "/knowledge", teamspace=teamspace, limit=100, max_items=1000):
        kid = k.get("id")
        detail = k
        if kid:
            try:
                detail = client.get_knowledge(kid) or k
            except DatagridError:
                detail = k
        items.append(detail)
    return items


def _collect_tables(client: DatagridClient, teamspace: str) -> List[dict]:
    tables: List[dict] = []
    try:
        for t in client.paginate("GET", "/tables", teamspace=teamspace, limit=100, max_items=500):
            tid = t.get("id")
            detail = t
            if tid:
                try:
                    detail = client.get_table(tid) or t
                except DatagridError:
                    detail = t
            tables.append(detail)
    except DatagridError as e:
        tables.append({"error": str(e)})
    return tables


def _collect_agents(client: DatagridClient) -> List[dict]:
    agents: List[dict] = []
    try:
        for a in client.paginate("GET", "/agents", limit=100, max_items=500):
            agents.append(
                {
                    "id": a.get("id"),
                    "name": a.get("name"),
                    "description": a.get("description") or a.get("system_prompt", "")[:240],
                }
            )
    except DatagridError as e:
        agents.append({"error": str(e)})
    return agents


def _run_search_sweep(
    client: DatagridClient, teamspace: str, queries: List[str]
) -> List[dict]:
    results = []
    for q in queries:
        entry: Dict[str, Any] = {"query": q}
        try:
            res = client.ai_search(q, teamspace=teamspace) or {}
            entry["answer"] = res.get("answer") or res.get("text") or client.message_text(res)
            sources = res.get("sources") or []
            entry["sources"] = [
                {
                    "index": s.get("index"),
                    "title": s.get("title") or s.get("name"),
                    "url": s.get("url"),
                    "id": s.get("id") or s.get("knowledge_id") or s.get("record_id"),
                }
                for s in sources
                if isinstance(s, dict)
            ]
        except DatagridError as e:
            entry["error"] = str(e)
        results.append(entry)
    return results


def _render_md(profile: dict) -> str:
    ts = profile["teamspace"]
    lines = [
        f"# Teamspace profile: {ts.get('name') or ts.get('id')}",
        "",
        f"Generated: {profile['generated_at']}",
        f"Teamspace id: `{ts.get('id')}`",
        "",
        "## Agents",
        "",
    ]
    agents = profile.get("agents") or []
    if not agents:
        lines.append("_No agents found._")
    for a in agents:
        if a.get("error"):
            lines.append(f"- Error listing agents: {a['error']}")
            continue
        lines.append(f"- **{a.get('name')}** (`{a.get('id')}`)")
        if a.get("description"):
            lines.append(f"  - {a['description'][:300]}")

    lines += ["", "## Knowledge", ""]
    knowledge = profile.get("knowledge") or []
    if not knowledge:
        lines.append("_No knowledge items._")
    for k in knowledge:
        status = k.get("status") or "?"
        lines.append(f"- **{k.get('name') or k.get('id')}** — status `{status}` — id `{k.get('id')}`")
        meta = k.get("metadata") or {}
        if isinstance(meta, dict) and meta:
            hint = meta.get("mime_type") or meta.get("type") or meta.get("source")
            if hint:
                lines.append(f"  - {hint}")

    lines += ["", "## Tables", ""]
    tables = profile.get("tables") or []
    if not tables:
        lines.append("_No tables._")
    for t in tables:
        if t.get("error"):
            lines.append(f"- Error listing tables: {t['error']}")
            continue
        lines.append(f"- **{t.get('name') or t.get('id')}** (`{t.get('id')}`)")

    lines += ["", "## AI search sweep", ""]
    for s in profile.get("search_sweep") or []:
        lines.append(f"### Query: {s.get('query')}")
        lines.append("")
        if s.get("error"):
            lines.append(f"_Error: {s['error']}_")
        else:
            lines.append(s.get("answer") or "_No answer._")
            sources = s.get("sources") or []
            if sources:
                lines.append("")
                lines.append("Sources:")
                for src in sources:
                    title = src.get("title") or src.get("id") or "source"
                    lines.append(f"- [{src.get('index')}] {title}")
        lines.append("")

    lines += [
        "## Next step",
        "",
        "Fill the `prompt` fields in `jobs_template.json` with concrete prompts that name",
        "the real documents/tables above, then run:",
        "",
        "```bash",
        "python scripts/orchestrate.py --jobs <out>/jobs_template.json --out results --concurrency 6",
        "```",
        "",
    ]
    return "\n".join(lines)


def _jobs_template(profile: dict) -> List[dict]:
    ts = profile["teamspace"]
    jobs = []
    for i, a in enumerate(profile.get("agents") or [], 1):
        if not a.get("id"):
            continue
        tag = f"job_{i:02d}_{(a.get('name') or 'agent').lower().replace(' ', '_')[:40]}"
        jobs.append(
            {
                "tag": tag,
                "agent": a.get("name"),
                "agent_id": a.get("id"),
                "teamspace": ts.get("name") or ts.get("id"),
                "prompt": "",
                "knowledge_ids": [],
                "max_retries": 2,
            }
        )
    if not jobs:
        jobs.append(
            {
                "tag": "job_01",
                "agent": "",
                "agent_id": "",
                "teamspace": ts.get("name") or ts.get("id"),
                "prompt": "",
                "knowledge_ids": [],
                "max_retries": 2,
            }
        )
    return jobs


def explore(teamspace: str, out_dir: Path, queries_file: Optional[str] = None) -> dict:
    client = DatagridClient(teamspace=teamspace)
    ts_obj = client.find_teamspace(teamspace) if not client._looks_like_id(teamspace) else {"id": teamspace, "name": teamspace}
    if not ts_obj:
        # still allow raw id
        ts_obj = {"id": teamspace, "name": teamspace}
    ts_id = ts_obj.get("id") or teamspace
    ts_name = ts_obj.get("name") or teamspace

    knowledge = _collect_knowledge(client, ts_id)
    tables = _collect_tables(client, ts_id)
    agents = _collect_agents(client)
    sweep = _run_search_sweep(client, ts_id, _load_queries(queries_file))

    profile = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "teamspace": {"id": ts_id, "name": ts_name},
        "agents": agents,
        "knowledge": [
            {
                "id": k.get("id"),
                "name": k.get("name"),
                "status": k.get("status"),
                "metadata": k.get("metadata"),
                "raw": k,
            }
            for k in knowledge
        ],
        "tables": tables,
        "search_sweep": sweep,
    }

    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "profile.json").write_text(json.dumps(profile, indent=2, default=str), encoding="utf-8")
    (out_dir / "profile.md").write_text(_render_md(profile), encoding="utf-8")
    jobs = _jobs_template(profile)
    (out_dir / "jobs_template.json").write_text(json.dumps(jobs, indent=2), encoding="utf-8")
    return profile


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(description="Profile a Datagrid teamspace")
    p.add_argument("--teamspace", required=True, help="Teamspace name or id")
    p.add_argument("--out", default="profile", help="Output directory")
    p.add_argument("--queries", default=None, help="Optional probes.txt (one query per line)")
    args = p.parse_args(argv)
    try:
        profile = explore(args.teamspace, Path(args.out), args.queries)
        print(f"Wrote {args.out}/profile.md, profile.json, jobs_template.json")
        print(f"Knowledge items: {len(profile.get('knowledge') or [])}")
        print(f"Tables: {len(profile.get('tables') or [])}")
        print(f"Agents: {len([a for a in (profile.get('agents') or []) if a.get('id')])}")
        return 0
    except DatagridError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
