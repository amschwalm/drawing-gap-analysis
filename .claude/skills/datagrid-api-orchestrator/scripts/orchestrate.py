#!/usr/bin/env python3
"""STAGE 3 — concurrent Datagrid agent runner with retry-on-stall.

Job schema (JSON list):
  {
    "tag": "unique-name",                 # required for output filenames
    "agent": "Agent Name",                # name OR
    "agent_id": "agt_...",                # id
    "prompt": "...",                      # required
    "teamspace": "Name or id",            # optional (falls back to --teamspace / env)
    "conversation_id": "...",             # optional: continue an existing conversation
    "knowledge_ids": ["kn_..."],          # optional: attach to config.corpus
    "max_retries": 2,                     # optional per-job override
    "chat_mode": "full_agent",            # optional
    "config": {}                          # optional converse config override
  }

Examples:
  python orchestrate.py --jobs jobs.json --out results --concurrency 16
  python orchestrate.py --agents "A,B" --prompt "..." --teamspace "TS" --out results
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

STALL_PATTERNS = [
    r"\bplease retry\b",
    r"\btry again\b",
    r"\bi (couldn't|could not|wasn't able to) (retrieve|access|find|get)\b",
    r"\bunable to retrieve\b",
    r"\bdata gap\b",
    r"\bframework\b",
    r"\bschema(s)? (only|retrieved|loaded)\b",
    r"\bno (real )?values?\b",
    r"\bnot (able|enough) to (complete|finish|execute)\b",
    r"\bre-?run\b",
    r"\bask me to continue\b",
    r"\[pending\]",
    r"\[placeholder",
    r"\bto be determined\b",
    r"\bto be populated\b",
]

NUDGE = (
    "You stopped after retrieving schemas or outlining a framework. "
    "Now EXECUTE the queries and return the actual values, each with its source. "
    "Don't return a framework or schema. Don't ask me to retry — complete the work."
)


def _is_stalled(text: str, tool_calls: list, min_tools: int = 2) -> bool:
    if not text:
        return True
    low = text.lower()
    if any(re.search(p, low) for p in STALL_PATTERNS):
        # retry language with few tools is the classic stall
        if len(tool_calls or []) <= min_tools:
            return True
        # even with more tools, explicit "please retry" is a stall
        if re.search(r"\b(please retry|try again|re-?run)\b", low):
            return True
    # very short "framework" style answers with almost no tools
    if len(tool_calls or []) <= 1 and len(text) < 400 and "schema" in low:
        return True
    return False


def _slug(s: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9._-]+", "_", s.strip()).strip("_")
    return s[:80] or "job"


def _load_jobs(args: argparse.Namespace) -> List[dict]:
    if args.jobs:
        data = json.loads(Path(args.jobs).read_text(encoding="utf-8"))
        if not isinstance(data, list):
            raise SystemExit("--jobs must be a JSON list")
        return data
    if not args.agents or not args.prompt:
        raise SystemExit("Provide --jobs, or both --agents and --prompt")
    agents = [a.strip() for a in args.agents.split(",") if a.strip()]
    jobs = []
    for a in agents:
        jobs.append(
            {
                "tag": _slug(a),
                "agent": a,
                "prompt": args.prompt,
                "teamspace": args.teamspace,
            }
        )
    return jobs


def _resolve_agent_id(client: DatagridClient, job: dict) -> str:
    if job.get("agent_id"):
        return job["agent_id"]
    name = job.get("agent") or job.get("agent_name")
    if not name:
        raise DatagridError(f"Job {job.get('tag')!r} missing agent/agent_id")
    found = client.find_agent(name)
    if not found:
        raise DatagridError(f"Agent not found: {name!r}")
    return found["id"]


def run_job(
    client: DatagridClient,
    job: dict,
    *,
    default_teamspace: Optional[str],
    default_retries: int,
) -> dict:
    tag = _slug(str(job.get("tag") or job.get("agent") or "job"))
    started = time.time()
    teamspace = job.get("teamspace") or default_teamspace
    max_retries = int(job.get("max_retries", default_retries))
    agent_id = _resolve_agent_id(client, job)
    prompt = job.get("prompt")
    if not prompt:
        raise DatagridError(f"Job {tag!r} has empty prompt")

    conversation_id = job.get("conversation_id")
    knowledge_ids = job.get("knowledge_ids") or []
    config = job.get("config")
    chat_mode = job.get("chat_mode")

    retries = 0
    stalled = False
    last_resp: Dict[str, Any] = {}
    text = ""
    tool_calls: list = []
    history: List[dict] = []

    while True:
        resp = client.converse(
            prompt if retries == 0 else NUDGE,
            agent_id=agent_id,
            conversation_id=conversation_id,
            config=config,
            chat_mode=chat_mode,
            teamspace=teamspace,
            knowledge_ids=knowledge_ids or None,
        )
        last_resp = resp or {}
        conversation_id = last_resp.get("conversation_id") or conversation_id
        text = client.message_text(last_resp)
        tool_calls = last_resp.get("tool_calls") or []
        history.append(
            {
                "attempt": retries + 1,
                "prompt": prompt if retries == 0 else NUDGE,
                "chars": len(text),
                "tool_calls": len(tool_calls),
                "credits": _safe_credits(last_resp),
            }
        )
        if not _is_stalled(text, tool_calls):
            stalled = False
            break
        if retries >= max_retries:
            stalled = True
            break
        retries += 1

    elapsed = round(time.time() - started, 2)
    result = {
        "tag": tag,
        "agent": job.get("agent"),
        "agent_id": agent_id,
        "teamspace": teamspace,
        "prompt": prompt,
        "conversation_id": conversation_id,
        "text": text,
        "tool_calls_count": len(tool_calls),
        "tool_calls": tool_calls,
        "credits_consumed": _safe_credits(last_resp),
        "retries": retries,
        "stalled": stalled,
        "elapsed_sec": elapsed,
        "history": history,
        "raw": last_resp,
        "finished_at": datetime.now(timezone.utc).isoformat(),
    }
    return result


def _safe_credits(resp: dict) -> Any:
    credits = resp.get("credits") or {}
    if isinstance(credits, dict):
        return credits.get("consumed", credits)
    return credits


def _write_result(out_dir: Path, result: dict) -> None:
    tag = result["tag"]
    (out_dir / f"{tag}.json").write_text(
        json.dumps(result, indent=2, default=str), encoding="utf-8"
    )
    md = [
        f"# {tag}",
        "",
        f"- agent: {result.get('agent')} (`{result.get('agent_id')}`)",
        f"- teamspace: {result.get('teamspace')}",
        f"- retries: {result.get('retries')}",
        f"- stalled: {result.get('stalled')}",
        f"- tools: {result.get('tool_calls_count')}",
        f"- credits: {result.get('credits_consumed')}",
        f"- elapsed_sec: {result.get('elapsed_sec')}",
        f"- conversation_id: `{result.get('conversation_id')}`",
        "",
        "## Prompt",
        "",
        (result.get("prompt") if isinstance(result.get("prompt"), str) else json.dumps(result.get("prompt"), indent=2, default=str)) or "",
        "",
        "## Response",
        "",
        result.get("text") or "_empty_",
        "",
    ]
    (out_dir / f"{tag}.md").write_text("\n".join(md), encoding="utf-8")


def _write_summary(out_dir: Path, results: List[dict]) -> None:
    lines = [
        "# Orchestration summary",
        "",
        f"Jobs: {len(results)}",
        "",
        "| tag | agent | tools | retries | stalled | credits | chars | elapsed_s |",
        "| --- | --- | ---: | ---: | --- | ---: | ---: | ---: |",
    ]
    for r in results:
        lines.append(
            "| {tag} | {agent} | {tools} | {retries} | {stalled} | {credits} | {chars} | {elapsed} |".format(
                tag=r.get("tag"),
                agent=(r.get("agent") or r.get("agent_id") or "")[:40],
                tools=r.get("tool_calls_count"),
                retries=r.get("retries"),
                stalled="yes" if r.get("stalled") else "no",
                credits=r.get("credits_consumed"),
                chars=len(r.get("text") or ""),
                elapsed=r.get("elapsed_sec"),
            )
        )
    stalled = [r for r in results if r.get("stalled")]
    if stalled:
        lines += ["", "## Stalled jobs", ""]
        for r in stalled:
            lines.append(f"- `{r.get('tag')}` — narrow the prompt and re-run")
    (out_dir / "SUMMARY.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(description="Run Datagrid agent prompts concurrently")
    p.add_argument("--jobs", help="Path to jobs.json list")
    p.add_argument("--agents", help="Comma-separated agent names (with --prompt)")
    p.add_argument("--prompt", help="Single prompt to fan across --agents")
    p.add_argument("--teamspace", default=None, help="Default teamspace name or id")
    p.add_argument("--out", default="results", help="Output directory")
    p.add_argument("--concurrency", type=int, default=16)
    p.add_argument("--max-retries", type=int, default=2)
    args = p.parse_args(argv)

    jobs = _load_jobs(args)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    # one client per worker thread via initializer pattern — create per job for simplicity
    results: List[dict] = []
    errors: List[str] = []

    def _worker(job: dict) -> dict:
        client = DatagridClient(teamspace=job.get("teamspace") or args.teamspace)
        return run_job(
            client,
            job,
            default_teamspace=args.teamspace,
            default_retries=args.max_retries,
        )

    print(f"Dispatching {len(jobs)} job(s) with concurrency={args.concurrency}")
    with ThreadPoolExecutor(max_workers=max(1, args.concurrency)) as pool:
        futures = {pool.submit(_worker, job): job for job in jobs}
        for fut in as_completed(futures):
            job = futures[fut]
            tag = job.get("tag") or job.get("agent") or "?"
            try:
                result = fut.result()
                _write_result(out_dir, result)
                results.append(result)
                flag = "STALLED" if result.get("stalled") else "ok"
                print(
                    f"[{flag}] {result['tag']} tools={result['tool_calls_count']} "
                    f"retries={result['retries']} chars={len(result.get('text') or '')}"
                )
            except Exception as e:
                msg = f"{tag}: {e}"
                errors.append(msg)
                print(f"[ERROR] {msg}", file=sys.stderr)
                err_path = out_dir / f"{_slug(str(tag))}.error.json"
                err_path.write_text(
                    json.dumps(
                        {"tag": tag, "error": str(e), "job": job},
                        indent=2,
                        default=str,
                    ),
                    encoding="utf-8",
                )

    results.sort(key=lambda r: r.get("tag") or "")
    _write_summary(out_dir, results)
    print(f"Wrote {out_dir}/SUMMARY.md ({len(results)} ok, {len(errors)} errors)")
    return 1 if errors and not results else 0


if __name__ == "__main__":
    sys.exit(main())
