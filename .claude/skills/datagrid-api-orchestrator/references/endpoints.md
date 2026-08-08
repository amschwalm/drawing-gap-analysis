# Datagrid API — complete endpoint reference

Base URL: `https://api.datagrid.com/v1` · Auth: `Authorization: Bearer <key>` ·
Teamspace scope: `Datagrid-Teamspace: <teamspace_id>` header.

Each row lists the client method in `datagrid_client.py`, the HTTP method + path,
what it does, and the doc slug under `https://developers.datagrid.com/api-reference/`.

**Path confidence:** ✅ = verified against the API reference / used successfully.
⚠️ = path follows standard REST convention for that resource (list/create/get/
update/delete under the resource root) but the exact sub-path or body wasn't
individually verified — confirm against the linked doc before a production
create/update. All endpoints are also reachable via `client.request(method, path)`.

## Identity & Credits
| client method | HTTP | path | purpose | conf |
| --- | --- | --- | --- | --- |
| `whoami()` | GET | `/identity` | authenticated caller identity | ✅ |
| `get_credits()` | GET | `/organization/credits` | credits for current billing period | ✅ |

## Agents
| client method | HTTP | path | purpose | conf |
| --- | --- | --- | --- | --- |
| `list_agents(search,limit,after,before)` | GET | `/agents` | list org agents | ✅ |
| `get_agent(id)` | GET | `/agents/{id}` | retrieve agent config | ✅ |
| `create_agent(**body)` | POST | `/agents` | create agent (name, tools, prompts, model…) | ✅ |
| `update_agent(id,**body)` | PATCH | `/agents/{id}` | update agent config | ⚠️ |
| `delete_agent(id)` | DELETE | `/agents/{id}` | delete agent | ⚠️ |
| `generate_agent(prompt)` | POST | `/agents/generate` | generate agent config from NL (prompt ≤2000 chars) | ✅ |
| `claim_agent(token)` | POST | `/agents/claim` | claim a generated agent template | ⚠️ |
| `find_agent(name)` | — | (helper) | resolve an agent by name → dict | ✅ |

## Converse
| client method | HTTP | path | purpose | conf |
| --- | --- | --- | --- | --- |
| `converse(prompt, agent_id, conversation_id, config, chat_mode, …)` | POST | `/converse` | talk to an agent | ✅ |
Body highlights: `prompt` (string or array of input items), `agent_id` |
`agent_routing`, `conversation_id`, `config` (corpus, system_prompt,
custom_prompt, planning_prompt, tools, disabled_tools, llm_model, agent_model,
temperature, mcp_servers), `chat_mode` (auto|full_agent|light_agent|llm_router),
`stream`, `generate_citations`, `generate_title`, `text.format` (structured
output JSON Schema), `secret_ids`, `reference_date`, `user`. Input item types:
`input_text`, `input_file`(file_id), `input_secret`, `input_knowledge`,
`input_page`. Response: `content[].text`, `tool_calls[]`, `reasoning[]`,
`citations[]`, `conversation_id`, `credits.consumed`, `generated_title`.
Docs: `converse/converse`, `/file-inputs`, `/knowledge-and-corpus`, `/mcp-servers`,
`/modes`, `/streaming`, `/structured-outputs`.

## Conversations
| client method | HTTP | path | purpose | conf |
| --- | --- | --- | --- | --- |
| `list_conversations(**p)` | GET | `/conversations` | list conversations | ⚠️ |
| `create_conversation(**b)` | POST | `/conversations` | create a conversation | ⚠️ |
| `get_conversation(cid)` | GET | `/conversations/{cid}` | retrieve conversation | ⚠️ |
| `update_conversation(cid,**b)` | PATCH | `/conversations/{cid}` | update properties | ⚠️ |
| `delete_conversation(cid)` | DELETE | `/conversations/{cid}` | delete conversation | ⚠️ |
| `list_messages(cid,**p)` | GET | `/conversations/{cid}/messages` | messages in conversation | ⚠️ |
| `get_message(cid,mid)` | GET | `/conversations/{cid}/messages/{mid}` | retrieve message | ⚠️ |

## Knowledge
| client method | HTTP | path | purpose | conf |
| --- | --- | --- | --- | --- |
| `list_knowledge(**p)` | GET | `/knowledge` | list knowledge (status: pending/partial/ready/failed) | ✅ |
| `get_knowledge(kid)` | GET | `/knowledge/{kid}` | retrieve knowledge by id | ✅ |
| `create_knowledge(file_paths,name,parent)` | POST | `/knowledge` | upload files (multipart) as knowledge | ✅ |
| `create_knowledge_from_connection(**b)` | POST | `/knowledge/connection` | ingest from a connection | ⚠️ |
| `update_knowledge(kid,**b)` | PATCH | `/knowledge/{kid}` | update attributes / sync | ⚠️ |
| `delete_knowledge(kid)` | DELETE | `/knowledge/{kid}` | delete knowledge | ⚠️ |
| `reindex_knowledge(kid)` | POST | `/knowledge/{kid}/reindex` | trigger full re-index | ⚠️ |

## Search
| client method | HTTP | path | purpose | conf |
| --- | --- | --- | --- | --- |
| `ai_search(query,record_types,limit)` | POST | `/search/ai` | NL answer + numbered sources over teamspace | ✅ |
| `search_tree(query,**b)` | POST | `/search/tree` | hierarchical context tree results | ⚠️ |
| (deprecated) | POST | `/search` | legacy knowledge search — use ai_search | — |
`record_types`: `rows`, `tables`, `files`, `pages`, `cells`.

## Batch Predictions (async bulk extraction)
| client method | HTTP | path | purpose | conf |
| --- | --- | --- | --- | --- |
| `create_batch_prediction(model,items,prompt,output_schema,completion_window,metadata)` | POST | `/batch-predictions` | create async job (items 1–5000) | ✅ |
| `list_batch_predictions(**p)` | GET | `/batch-predictions` | list (reverse chronological) | ⚠️ |
| `get_batch_prediction(bid)` | GET | `/batch-predictions/{bid}` | retrieve job | ⚠️ |
| `get_batch_prediction_results(bid)` | GET | `/batch-predictions/{bid}/results` | stream NDJSON results (raw bytes) | ⚠️ |
| `cancel_batch_prediction(bid)` | POST | `/batch-predictions/{bid}/cancel` | request cancellation | ⚠️ |

## Connections / Providers / Connectors
| client method | HTTP | path | purpose | conf |
| --- | --- | --- | --- | --- |
| `list_connections(**p)` | GET | `/connections` | third-party connections | ⚠️ |
| `create_connection(**b)` | POST | `/connections` | create connection | ⚠️ |
| `get_connection(id)` | GET | `/connections/{id}` | retrieve | ⚠️ |
| `update_connection(id,**b)` | PATCH | `/connections/{id}` | update | ⚠️ |
| `delete_connection(id)` | DELETE | `/connections/{id}` | delete | ⚠️ |
| `list_connectors()` | GET | `/connectors` | available connectors catalog | ⚠️ |
| `list_connection_providers(**p)` | GET | `/connection-providers` | custom OAuth providers | ⚠️ |
| `create/get/update/delete_connection_provider` | POST/GET/PATCH/DELETE | `/connection-providers[/{id}]` | manage providers | ⚠️ |

## Data Views & Service Accounts
| client method | HTTP | path | purpose | conf |
| --- | --- | --- | --- | --- |
| `list_data_views(**p)` | GET | `/data-views` | list data views | ⚠️ |
| `create_data_view(**b)` | POST | `/data-views` | create controlled-access view | ⚠️ |
| `delete_data_view(id)` | DELETE | `/data-views/{id}` | remove view | ⚠️ |
| `list_service_accounts(**p)` | GET | `/service-accounts` | list service accounts | ⚠️ |
| `create_service_account(**b)` | POST | `/service-accounts` | create service account | ⚠️ |
| `delete_service_account(id)` | DELETE | `/service-accounts/{id}` | remove | ⚠️ |
| `get_service_account_credentials(id)` | GET | `/service-accounts/{id}/credentials` | fetch credentials | ⚠️ |

## Files
| client method | HTTP | path | purpose | conf |
| --- | --- | --- | --- | --- |
| `list_files(**p)` | GET | `/files` | list files | ⚠️ |
| `create_files(file_paths)` | POST | `/files` | upload files for agent input (multipart) | ⚠️ |
| `get_file(fid)` | GET | `/files/{fid}` | file metadata | ⚠️ |
| `get_file_content(fid)` | GET | `/files/{fid}/content` | file bytes (raw) | ⚠️ |
| `update_file(fid,**b)` | PATCH | `/files/{fid}` | update metadata | ⚠️ |
| `delete_file(fid)` | DELETE | `/files/{fid}` | delete file | ⚠️ |

## Tables & Records
| client method | HTTP | path | purpose | conf |
| --- | --- | --- | --- | --- |
| `list_tables(**p)` | GET | `/tables` | list tables | ⚠️ |
| `get_table(tid)` | GET | `/tables/{tid}` | retrieve table | ⚠️ |
| `list_records(tid,limit,next)` | GET | `/tables/{tid}/records` | records page (limit 1–1000, `next` cursor) | ✅ |
| `all_records(tid)` | — | (helper) | follow `next` to pull every record | ✅ |

## Teamspaces & Users/Invites
| client method | HTTP | path | purpose | conf |
| --- | --- | --- | --- | --- |
| `list_teamspaces(**p)` | GET | `/organization/teamspaces` | list teamspaces | ✅ |
| `get_teamspace(tid)` | GET | `/organization/teamspaces/{tid}` | retrieve | ⚠️ |
| `create_teamspace(**b)` | POST | `/organization/teamspaces` | create | ⚠️ |
| `update_teamspace(tid,**b)` | PATCH | `/organization/teamspaces/{tid}` | update name/access | ⚠️ |
| `find_teamspace(name)` | — | (helper) | resolve teamspace by name → dict | ✅ |
| `list_teamspace_users / get / update / delete` | GET/GET/PATCH/DELETE | `/organization/teamspaces/{tid}/users[/{uid}]` | manage members | ⚠️ |
| `list_teamspace_invites / invite_user / get / delete` | GET/POST/GET/DELETE | `/organization/teamspaces/{tid}/invites[/{iid}]` | manage invites | ⚠️ |
Note: to scope any request to a teamspace, pass `teamspace=` (uses the
`Datagrid-Teamspace` header) — that's the documented `scope-to-teamspace` mechanism.

## MCP Servers
| client method | HTTP | path | purpose | conf |
| --- | --- | --- | --- | --- |
| `list_mcp_servers(**p)` | GET | `/mcp-servers` | list registered MCP servers | ⚠️ |
| `create/get/update/delete_mcp_server` | POST/GET/PATCH/DELETE | `/mcp-servers[/{id}]` | manage MCP servers (teamspace scope) | ⚠️ |

## Memory
| client method | HTTP | path | purpose | conf |
| --- | --- | --- | --- | --- |
| `list_memory(**p)` | GET | `/memory` | list user memories (per user+agent) | ⚠️ |
| `create_memory(**b)` | POST | `/memory` | create user memory | ⚠️ |
| `delete_memory(id)` | DELETE | `/memory/{id}` | delete memory | ⚠️ |

## Pages
| client method | HTTP | path | purpose | conf |
| --- | --- | --- | --- | --- |
| `list_pages(**p)` | GET | `/pages` | list pages | ⚠️ |
| `create/get/update/delete_page` | POST/GET/PATCH/DELETE | `/pages[/{id}]` | manage pages (delete requires no children) | ⚠️ |

## Secrets
| client method | HTTP | path | purpose | conf |
| --- | --- | --- | --- | --- |
| `list_secrets(**p)` | GET | `/secrets` | list secrets | ⚠️ |
| `create_secret(**b)` | POST | `/secrets` | create secret for converse | ⚠️ |
| `get_secret(id)` | GET | `/secrets/{id}` | retrieve | ⚠️ |
| `delete_secret(id)` | DELETE | `/secrets/{id}` | delete | ⚠️ |
Secrets are referenced in converse via `secret_ids` or `input_secret` items.

## Tools
| client method | HTTP | path | purpose | conf |
| --- | --- | --- | --- | --- |
| `list_tools()` | GET | `/tools` | available agent tools | ⚠️ |
| `get_tool(id)` | GET | `/tools/{id}` | retrieve tool | ⚠️ |

## Users (org)
| client method | HTTP | path | purpose | conf |
| --- | --- | --- | --- | --- |
| `list_users(**p)` | GET | `/users` | org users | ⚠️ |
| `get_user(id)` | GET | `/users/{id}` | retrieve user | ⚠️ |
| `update_user(id,**b)` | PATCH | `/users/{id}` | update org permissions | ⚠️ |

## Webhooks
| client method | HTTP | path | purpose | conf |
| --- | --- | --- | --- | --- |
| `list_webhooks(**p)` | GET | `/webhooks` | list subscriptions | ⚠️ |
| `create_webhook(**b)` | POST | `/webhooks` | create HTTPS subscription | ⚠️ |
| `get/update/delete_webhook` | GET/PATCH/DELETE | `/webhooks/{id}` | manage subscription | ⚠️ |
| `list_active_webhooks_for_event(event)` | GET | `/webhooks/active?event=` | enabled hooks for an event | ⚠️ |

## Voice (not wrapped — WebSocket/real-time)
Voice is a real-time WebSocket flow (`start-voice-session`, `voice`,
`list/retrieve/acknowledge voice-orchestrator-task`, iOS integration). It doesn't
fit the request/response client; use `client.request(...)` for the REST parts
(e.g. voice orchestrator tasks) and the docs for the WS handshake.
Docs: `voice/*`.

## Rate limits
On 429 the client honors `Retry-After` and backs off; 5xx retried with
exponential backoff (default 4 attempts). Doc: `rate-limits`.
