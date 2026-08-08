# Datagrid recipes — one concrete action per endpoint group

Copy/paste-able snippets. All assume you're running from the skill's `scripts/`
folder (so `.env` is picked up) or have `DATAGRID_API_KEY` in your environment:
```python
import sys; sys.path.insert(0, "scripts")
from datagrid_client import DatagridClient
c = DatagridClient(teamspace="My Teamspace")   # name, id, or omit
```

## Identity & credits
```python
c.whoami()                       # who is this key? (org, user)
c.get_credits()                  # credits consumed / remaining this period — check before big fan-outs
```

## Agents — discover, inspect, create, generate
```python
[ (a["id"], a["name"]) for a in c.list_agents().get("data", []) ]   # list all
c.find_agent("My Analysis Agent")                                   # resolve by name
c.get_agent(agent_id)                                               # full config: tools, prompts, corpus, mcp_servers
c.generate_agent("An agent that reviews spec sheets and flags noncompliant parts")
c.create_agent(name="My Agent", agent_model="magpie-2.5",
               tools=[{"name":"data_analysis"},{"name":"semantic_search"}],
               system_prompt="…", planning_prompt="…")
```

## Converse — single turn, structured output, multi-turn
```python
r = c.converse("show me all open orders", agent_id=agent_id, teamspace=ts)
print(c.message_text(r), r["conversation_id"], r["credits"]["consumed"])

# continue the SAME conversation (schemas/context reused):
r2 = c.converse("now total them by category", agent_id=agent_id,
                conversation_id=r["conversation_id"], teamspace=ts)

# force JSON output that matches a schema:
r3 = c.converse("extract part number and quantity for each line item", agent_id=agent_id, teamspace=ts,
                text={"format":{"type":"json_schema","name":"items",
                      "schema":{"type":"object","properties":{
                        "items":{"type":"array","items":{"type":"object","properties":{
                          "part":{"type":"string"},"qty":{"type":"number"}}}}}}}})

# attach a file / knowledge / page as input (array prompt):
r4 = c.converse([{"type":"input_text","text":"Summarize this document"},
                 {"type":"input_file","file_id":file_id}], agent_id=agent_id, teamspace=ts)
```
For bulk/parallel converse use `orchestrate.py` (handles concurrency + retry-on-stall).

## Conversations — browse history
```python
c.list_conversations(limit=20)
c.list_messages(conversation_id)          # every turn
c.get_message(conversation_id, message_id)
c.update_conversation(conversation_id, name="Q3 review")
```

## AI search — profile a teamspace before writing prompts
```python
res = c.ai_search("what part catalogs, spec sheets, and orders exist?")
print(res["answer"])                       # NL answer with [1][2] citations
for s in res["sources"]: print(s["index"], s["title"], s.get("url"))
c.ai_search("totals by category", record_types=["tables","rows"])
c.search_tree("change orders")             # hierarchical context tree
```
Use this FIRST to discover documents/records, then reference them in agent prompts.

## Knowledge — list, retrieve, create, reindex
```python
[ (k["id"], k["name"], k["status"]) for k in c.list_knowledge().get("data", []) ]
c.get_knowledge(kid)                                  # retrieve one
c.create_knowledge(["/path/spec.pdf","/path/log.csv"], name="Project docs")  # upload (multipart)
c.create_knowledge_from_connection(connection_id=conn_id, ...)   # ingest from a connection
c.reindex_knowledge(kid)                              # re-index after source changes
# status flow: pending -> partial -> ready (or failed). Poll list_knowledge until ready.
```

## Files — upload inputs, fetch content
```python
up = c.create_files(["/path/drawing.pdf"])           # -> file id(s) for converse input_file
c.list_files(); c.get_file(fid)
open("out.pdf","wb").write(c.get_file_content(fid))   # download bytes
```

## Tables & records — pull structured data
```python
[ (t["id"], t.get("name")) for t in c.list_tables().get("data", []) ]
c.get_table(tid)                                      # schema / metadata
rows = list(c.all_records(tid, max_items=1000))       # auto-paginate via `next` cursor
```

## Batch predictions — async extraction over many files
```python
job = c.create_batch_prediction(
    model="claude-opus-4-8",
    items=[{"file_id": f} for f in file_ids],         # 1–5000 items
    prompt="Extract the PO number, vendor, and total.",
    output_schema={"type":"object","properties":{
        "po":{"type":"string"},"vendor":{"type":"string"},"total":{"type":"number"}}})
c.get_batch_prediction(job["id"])                     # poll status
ndjson = c.get_batch_prediction_results(job["id"])    # raw NDJSON bytes when terminal
c.cancel_batch_prediction(job["id"])                  # if needed
```

## Connections / connectors — integrations
```python
c.list_connectors()                                   # what can I connect to?
c.list_connections()                                  # what's already connected
c.create_connection(...)                              # confirm body vs docs
```

## Teamspaces & members
```python
[ (t["id"], t["name"]) for t in c.list_teamspaces(limit=100).get("data", []) ]
c.find_teamspace("My Teamspace")
c.list_teamspace_users(tid)
c.invite_user(tid, email="teammate@corp.com", role="member")   # confirm body vs docs
```

## Pages, secrets, memory, MCP servers, tools, webhooks, users
```python
c.list_pages(); c.create_page(title="Runbook", ...)
c.list_secrets(); c.create_secret(name="MY_TOKEN", value="…")   # ref via secret_ids in converse
c.list_memory(); c.create_memory(...); c.delete_memory(mid)
c.list_mcp_servers(); c.create_mcp_server(name="…", url="…")
c.list_tools(); c.get_tool("data_analysis")
c.list_webhooks(); c.create_webhook(url="https://…", events=[...])
c.list_users(); c.get_user(uid)
```

## Data views & service accounts — controlled programmatic access
```python
sa = c.create_service_account(name="reporting")
c.get_service_account_credentials(sa["id"])
c.create_data_view(...)                               # scoped access to specific data
```

## Anything not wrapped, or to confirm a path
```python
c.request("GET", "/some/endpoint", params={"limit": 10})
c.request("POST", "/some/endpoint", body={"field": "value"})
```
For ⚠️-marked paths in `endpoints.md`, verify the request body against the linked
doc at `https://developers.datagrid.com/api-reference/<slug>` before a
create/update you depend on.
