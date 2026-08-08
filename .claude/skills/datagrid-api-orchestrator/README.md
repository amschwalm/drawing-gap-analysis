# Datagrid API Orchestrator

A self-contained toolkit that lets **Claude drive the Datagrid API** for you —
run many agent prompts in parallel, recover from stalled runs, search a
teamspace, and reach every Datagrid endpoint. Pure Python standard library: no
`pip install`, no external dependencies. Not tied to any organization, teamspace,
or agent — point it at any Datagrid workspace with an API key.

This is a Claude *skill*. Once installed, you don't call the scripts by hand —
you just ask Claude in plain language ("run these 5 prompts across my agents",
"profile my teamspace", "pull every record from the orders table") and it uses
this toolkit under the hood.

---

## 1. Install

Copy the whole `datagrid-api-orchestrator/` folder into either:

- `~/.claude/skills/` — available in every Claude Code session, or
- `<your-project>/.claude/skills/` — available only in that project.

(For **claude.ai**, zip the folder and upload it in Settings → Capabilities →
Skills, if your plan/workspace has Skills upload enabled.)

```
datagrid-api-orchestrator/
├── SKILL.md                 # what Claude reads to use the skill
├── README.md                # this file
├── scripts/
│   ├── datagrid_client.py   # API client wrapping every endpoint
│   ├── explore.py           # profile a teamspace
│   ├── orchestrate.py       # concurrent prompt runner + retries
│   └── .env.example         # copy to .env and add your key
└── references/
    ├── endpoints.md         # every endpoint (method, path, purpose)
    └── recipes.md           # a copy/paste snippet per endpoint group
```

## 2. Add your API key

Get a key from the Datagrid dashboard → **Settings → API keys**, then:

```bash
cd datagrid-api-orchestrator/scripts
cp .env.example .env
# open .env and set DATAGRID_API_KEY=dg_...   (optionally DATAGRID_TEAMSPACE=...)
```

**Never commit `.env` or paste your key into chat.** If a key leaks, rotate it in
the dashboard. The client reads the key from (in order): an explicit argument →
the `DATAGRID_API_KEY` environment variable → this `.env` file.

## 3. Smoke test (confirms you're wired up)

Any Python 3.8+ works.

```bash
python scripts/datagrid_client.py whoami
```

If it prints JSON with your org/user, you're good. Other quick checks:

```bash
python scripts/datagrid_client.py agents      # list your agents
python scripts/datagrid_client.py teamspaces   # list your teamspaces
python scripts/datagrid_client.py credits      # remaining credits
```

If `python` isn't found, try `python3` or `/usr/bin/python3`.

---

## Using it

### The easy way — just ask Claude

With the skill installed and the key set, say things like:

- "Profile my teamspace and show me what's in it."
- "Run this prompt across these two agents in parallel."
- "Here are 8 prompts — fan them out concurrently and give me the results."
- "That agent stalled — retry it and force it to return real values."
- "Pull every record from the orders table."

Claude runs the explore → dispatch pipeline and hands back the results.

### The manual way — run the scripts yourself

**Profile a teamspace** (read-only; discovers agents, knowledge, tables, and runs
an AI-search sweep):

```bash
python scripts/explore.py --teamspace "My Teamspace" --out profile
```

Read `profile/profile.md`, then fill the `prompt` fields in
`profile/jobs_template.json`.

**Run many prompts concurrently:**

```bash
python scripts/orchestrate.py --jobs profile/jobs_template.json --out results --concurrency 6
```

**Or fan a single prompt across several agents:**

```bash
python scripts/orchestrate.py \
  --agents "Agent A,Agent B" \
  --prompt "summarize the top risks in this project" \
  --teamspace "My Teamspace" \
  --out results --concurrency 6
```

Each job writes `results/<tag>.md` + `.json` the moment it finishes, plus a
`results/SUMMARY.md` table.

**For long runs, launch detached** so a short foreground timeout can't kill an
agent mid-run, then watch the output files:

```bash
nohup python scripts/orchestrate.py --jobs profile/jobs_template.json \
  --out results --concurrency 6 > results/run.log 2>&1 &
```

---

## Good to know

- **Teamspace scoping matters.** Agents are org-wide, but their *data* lives in a
  teamspace. If an agent "can't see your data", it's almost always scoped to the
  wrong teamspace — pass the right one.
- **Agent runs are slow** (minutes, sometimes >15). That's normal; the toolkit
  runs them in parallel and retries transient failures automatically.
- **Retry-on-stall is built in.** Agents sometimes stop early and ask you to
  retry; the orchestrator detects this and re-prompts the same conversation to
  force real output. Tune with `--max-retries`.
- **Credits.** `converse`, `ai_search`, and batch predictions cost credits —
  check `python scripts/datagrid_client.py credits` before a big fan-out.
- **Verify figures.** Treat agent output as a draft and reconcile numbers against
  the source system before external use.
- **Every endpoint is reachable.** See `references/endpoints.md` for the full map
  and `references/recipes.md` for a snippet per group. Anything not wrapped:
  `client.request("GET", "/some/path")`.

## Troubleshooting

| Symptom | Fix |
| --- | --- |
| `No API key` | Set `DATAGRID_API_KEY` in `scripts/.env` (or the environment). |
| `... -> 401` | Key is wrong/expired — regenerate in the dashboard. |
| Agent returns a "framework"/schema with no values | It stalled; the orchestrator auto-retries, or re-ask it to "execute the queries and return actual values." |
| Agent says a document is "not found" though it exists | The doc isn't in that agent's corpus — attach it via a job's `knowledge_ids` (get ids from `profile.json`). |
| Run killed after ~10–15 min | Launch detached with `nohup ... &` and poll the result files. |
| `429` errors | Rate-limited; the client backs off automatically. Lower `--concurrency`. |

Full API reference: <https://developers.datagrid.com/api-reference/>
