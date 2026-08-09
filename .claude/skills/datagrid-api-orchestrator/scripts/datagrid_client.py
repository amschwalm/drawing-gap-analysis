#!/usr/bin/env python3
"""Stdlib-only Datagrid API client.

Import:
    from datagrid_client import DatagridClient
    c = DatagridClient(teamspace="My Teamspace")

CLI:
    python datagrid_client.py whoami|agents|teamspaces|credits|tools
"""

from __future__ import annotations

import argparse
import json
import mimetypes
import os
import sys
import time
import uuid
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Optional, Union
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

DEFAULT_BASE = "https://api.datagrid.com/v1"
DEFAULT_TIMEOUT = 120
DEFAULT_CONVERSE_TIMEOUT = 3600
DEFAULT_RETRIES = 4
SCRIPT_DIR = Path(__file__).resolve().parent


class DatagridError(RuntimeError):
    def __init__(self, message: str, status: Optional[int] = None, body: Any = None):
        super().__init__(message)
        self.status = status
        self.body = body


def _load_dotenv(path: Path) -> None:
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip("'").strip('"')
        if key and key not in os.environ:
            os.environ[key] = value


def resolve_api_key(explicit: Optional[str] = None) -> str:
    if explicit:
        return explicit.strip()
    for name in ("DATAGRID_API_KEY", "Datagrid_API_KEY"):
        val = os.environ.get(name)
        if val:
            return val.strip()
    _load_dotenv(SCRIPT_DIR / ".env")
    for name in ("DATAGRID_API_KEY", "Datagrid_API_KEY"):
        val = os.environ.get(name)
        if val:
            return val.strip()
    raise DatagridError(
        "No API key. Set DATAGRID_API_KEY (or Datagrid_API_KEY), pass api_key=, "
        "or put it in scripts/.env"
    )


def _json_dumps(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))


def _encode_multipart(
    fields: Dict[str, str], files: List[tuple]
) -> tuple:
    """files: list of (field_name, path). Returns (content_type, body_bytes)."""
    boundary = f"----dgboundary{uuid.uuid4().hex}"
    chunks: List[bytes] = []
    for name, value in fields.items():
        chunks.append(f"--{boundary}\r\n".encode())
        chunks.append(f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode())
        chunks.append(str(value).encode("utf-8"))
        chunks.append(b"\r\n")
    for field_name, path in files:
        p = Path(path)
        mime = mimetypes.guess_type(str(p))[0] or "application/octet-stream"
        chunks.append(f"--{boundary}\r\n".encode())
        chunks.append(
            (
                f'Content-Disposition: form-data; name="{field_name}"; '
                f'filename="{p.name}"\r\n'
                f"Content-Type: {mime}\r\n\r\n"
            ).encode()
        )
        chunks.append(p.read_bytes())
        chunks.append(b"\r\n")
    chunks.append(f"--{boundary}--\r\n".encode())
    return f"multipart/form-data; boundary={boundary}", b"".join(chunks)


class DatagridClient:
    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        teamspace: Optional[str] = None,
        timeout: Optional[float] = None,
        converse_timeout: Optional[float] = None,
        max_retries: int = DEFAULT_RETRIES,
    ):
        _load_dotenv(SCRIPT_DIR / ".env")
        self.api_key = resolve_api_key(api_key)
        self.base_url = (base_url or os.environ.get("DATAGRID_API_BASE") or DEFAULT_BASE).rstrip("/")
        self.timeout = float(timeout or os.environ.get("DATAGRID_TIMEOUT") or DEFAULT_TIMEOUT)
        self.converse_timeout = float(
            converse_timeout
            or os.environ.get("DATAGRID_CONVERSE_TIMEOUT")
            or DEFAULT_CONVERSE_TIMEOUT
        )
        self.max_retries = max_retries
        self._teamspace_raw = teamspace or os.environ.get("DATAGRID_TEAMSPACE")
        self._teamspace_id: Optional[str] = None
        self._resolving_teamspace = False
        self._agent_cache: Dict[str, dict] = {}
        self._teamspace_cache: Dict[str, dict] = {}

    # ---- HTTP core ---------------------------------------------------------

    def _resolve_teamspace_header(self, teamspace: Optional[str] = None) -> Optional[str]:
        raw = teamspace if teamspace is not None else self._teamspace_raw
        if not raw:
            return None
        if self._looks_like_id(raw):
            return raw
        if self._teamspace_id and (
            teamspace is None or str(teamspace).strip().lower() == str(self._teamspace_raw or "").strip().lower()
        ):
            return self._teamspace_id
        # Avoid recursion: name lookup itself must not send Datagrid-Teamspace.
        if self._resolving_teamspace:
            return None
        self._resolving_teamspace = True
        try:
            found = self.find_teamspace(raw)
        finally:
            self._resolving_teamspace = False
        if not found:
            raise DatagridError(f"Teamspace not found by name: {raw!r}")
        if teamspace is None or str(teamspace).strip().lower() == str(self._teamspace_raw or "").strip().lower():
            self._teamspace_id = found["id"]
        return found["id"]

    @staticmethod
    def _looks_like_id(value: str) -> bool:
        # UUID-ish ids; names usually contain spaces or are short words.
        v = value.strip()
        if " " in v or len(v) < 8:
            return False
        return "-" in v or v.replace("_", "").isalnum()

    def request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        body: Any = None,
        teamspace: Optional[str] = None,
        timeout: Optional[float] = None,
        raw: bool = False,
        headers: Optional[Dict[str, str]] = None,
        data: Optional[bytes] = None,
        content_type: Optional[str] = None,
        skip_teamspace: bool = False,
    ) -> Any:
        if not path.startswith("/"):
            path = "/" + path
        url = self.base_url + path
        if params:
            clean = {k: v for k, v in params.items() if v is not None}
            if clean:
                url += "?" + urlencode(clean, doseq=True)

        hdrs = {
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "application/json",
            "User-Agent": "datagrid-api-orchestrator/1.0",
        }
        # Org-level listing used for name resolution should not require a teamspace header.
        if not skip_teamspace and not self._resolving_teamspace:
            ts = self._resolve_teamspace_header(teamspace)
            if ts:
                hdrs["Datagrid-Teamspace"] = ts
        if headers:
            hdrs.update(headers)

        payload: Optional[bytes] = data
        if body is not None and payload is None:
            payload = _json_dumps(body).encode("utf-8")
            hdrs["Content-Type"] = "application/json"
        elif content_type and payload is not None:
            hdrs["Content-Type"] = content_type

        last_err: Optional[Exception] = None
        attempts = max(1, self.max_retries)
        for attempt in range(attempts):
            req = Request(url, data=payload, headers=hdrs, method=method.upper())
            try:
                with urlopen(req, timeout=timeout or self.timeout) as resp:
                    content = resp.read()
                    if raw:
                        return content
                    if not content:
                        return None
                    ctype = resp.headers.get("Content-Type", "")
                    if "application/json" in ctype or content[:1] in (b"{", b"["):
                        return json.loads(content.decode("utf-8"))
                    return content.decode("utf-8", errors="replace")
            except HTTPError as e:
                err_body = e.read()
                parsed: Any
                try:
                    parsed = json.loads(err_body.decode("utf-8"))
                except Exception:
                    parsed = err_body.decode("utf-8", errors="replace")
                retryable = e.code in (429, 500, 502, 503, 504)
                if retryable and attempt < attempts - 1:
                    wait = e.headers.get("Retry-After")
                    delay = float(wait) if wait and str(wait).isdigit() else min(2 ** attempt, 60)
                    time.sleep(delay)
                    last_err = DatagridError(f"{method} {path} -> {e.code}", e.code, parsed)
                    continue
                raise DatagridError(f"{method} {path} -> {e.code}: {parsed}", e.code, parsed) from e
            except URLError as e:
                if attempt < attempts - 1:
                    time.sleep(min(2 ** attempt, 60))
                    last_err = e
                    continue
                raise DatagridError(f"{method} {path} network error: {e}") from e
        raise DatagridError(f"{method} {path} failed after retries: {last_err}")

    # ---- helpers -----------------------------------------------------------

    @staticmethod
    def message_text(response: dict) -> str:
        parts = []
        for item in response.get("content") or []:
            if isinstance(item, dict):
                text = item.get("text")
                if text:
                    parts.append(text)
            elif isinstance(item, str):
                parts.append(item)
        if parts:
            return "\n".join(parts)
        # fallback shapes
        for key in ("answer", "message", "text", "output"):
            if isinstance(response.get(key), str):
                return response[key]
        return ""

    def paginate(
        self,
        method: str,
        path: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        teamspace: Optional[str] = None,
        limit: int = 100,
        max_items: Optional[int] = None,
        cursor_param: str = "after",
        skip_teamspace: bool = False,
    ) -> Iterator[dict]:
        params = dict(params or {})
        params.setdefault("limit", limit)
        yielded = 0
        while True:
            page = self.request(
                method,
                path,
                params=params,
                teamspace=teamspace,
                skip_teamspace=skip_teamspace,
            ) or {}
            data = page.get("data") if isinstance(page, dict) else page
            if not isinstance(data, list):
                return
            for item in data:
                yield item
                yielded += 1
                if max_items is not None and yielded >= max_items:
                    return
            if not isinstance(page, dict):
                return
            nxt = page.get("next") or page.get("next_cursor") or (page.get("paging") or {}).get("next")
            if not nxt and page.get("has_more") and data:
                nxt = data[-1].get("id")
            if not nxt:
                return
            params = dict(params)
            params[cursor_param] = nxt

    # ---- Identity & credits ------------------------------------------------

    def whoami(self) -> dict:
        return self.request("GET", "/identity")

    def get_credits(self) -> dict:
        return self.request("GET", "/organization/credits")

    # ---- Agents ------------------------------------------------------------

    def list_agents(
        self,
        search: Optional[str] = None,
        limit: int = 100,
        after: Optional[str] = None,
        before: Optional[str] = None,
        **params: Any,
    ) -> dict:
        q = {"search": search, "limit": limit, "after": after, "before": before, **params}
        return self.request("GET", "/agents", params=q)

    def get_agent(self, agent_id: str) -> dict:
        return self.request("GET", f"/agents/{agent_id}")

    def create_agent(self, **body: Any) -> dict:
        return self.request("POST", "/agents", body=body)

    def update_agent(self, agent_id: str, **body: Any) -> dict:
        return self.request("PATCH", f"/agents/{agent_id}", body=body)

    def delete_agent(self, agent_id: str) -> Any:
        return self.request("DELETE", f"/agents/{agent_id}")

    def generate_agent(self, prompt: str) -> dict:
        return self.request("POST", "/agents/generate", body={"prompt": prompt})

    def claim_agent(self, token: str) -> dict:
        return self.request("POST", "/agents/claim", body={"claim_token": token})

    def find_agent(self, name: str) -> Optional[dict]:
        key = name.strip().lower()
        if key in self._agent_cache:
            return self._agent_cache[key]
        page = self.list_agents(search=name, limit=100) or {}
        for a in page.get("data") or []:
            aname = (a.get("name") or "").strip()
            self._agent_cache[aname.lower()] = a
            if aname.lower() == key:
                return a
        # broader scan if search was too narrow
        for a in self.paginate("GET", "/agents", limit=100, max_items=500):
            aname = (a.get("name") or "").strip()
            self._agent_cache[aname.lower()] = a
            if aname.lower() == key:
                return a
        return None

    # ---- Converse ----------------------------------------------------------

    def converse(
        self,
        prompt: Union[str, list],
        *,
        agent_id: Optional[str] = None,
        conversation_id: Optional[str] = None,
        config: Optional[dict] = None,
        chat_mode: Optional[str] = None,
        teamspace: Optional[str] = None,
        knowledge_ids: Optional[List[str]] = None,
        secret_ids: Optional[List[str]] = None,
        stream: bool = False,
        generate_citations: Optional[bool] = None,
        generate_title: Optional[bool] = None,
        text: Optional[dict] = None,
        agent_routing: Optional[dict] = None,
        reference_date: Optional[str] = None,
        user: Optional[Any] = None,
        **extra: Any,
    ) -> dict:
        body: Dict[str, Any] = {"prompt": prompt, **extra}
        if agent_id is not None:
            body["agent_id"] = agent_id
        if conversation_id is not None:
            body["conversation_id"] = conversation_id
        cfg = dict(config or {})
        if knowledge_ids:
            corpus = list(cfg.get("corpus") or [])
            existing = set()
            for item in corpus:
                if isinstance(item, dict) and item.get("knowledge_id"):
                    existing.add(item["knowledge_id"])
                elif isinstance(item, str):
                    existing.add(item)
            for kid in knowledge_ids:
                if kid in existing:
                    continue
                corpus.append({"type": "knowledge", "knowledge_id": kid})
                existing.add(kid)
            cfg["corpus"] = corpus
        if cfg:
            body["config"] = cfg
        if chat_mode is not None:
            body["chat_mode"] = chat_mode
        if secret_ids is not None:
            body["secret_ids"] = secret_ids
        if stream:
            body["stream"] = True
        if generate_citations is not None:
            body["generate_citations"] = generate_citations
        if generate_title is not None:
            body["generate_title"] = generate_title
        if text is not None:
            body["text"] = text
        if agent_routing is not None:
            body["agent_routing"] = agent_routing
        if reference_date is not None:
            body["reference_date"] = reference_date
        if user is not None:
            body["user"] = user
        return self.request(
            "POST",
            "/converse",
            body=body,
            teamspace=teamspace,
            timeout=self.converse_timeout,
        )

    # ---- Conversations -----------------------------------------------------

    def list_conversations(self, **params: Any) -> dict:
        return self.request("GET", "/conversations", params=params)

    def create_conversation(self, **body: Any) -> dict:
        return self.request("POST", "/conversations", body=body)

    def get_conversation(self, cid: str) -> dict:
        return self.request("GET", f"/conversations/{cid}")

    def update_conversation(self, cid: str, **body: Any) -> dict:
        return self.request("PATCH", f"/conversations/{cid}", body=body)

    def delete_conversation(self, cid: str) -> Any:
        return self.request("DELETE", f"/conversations/{cid}")

    def list_messages(self, cid: str, **params: Any) -> dict:
        return self.request("GET", f"/conversations/{cid}/messages", params=params)

    def get_message(self, cid: str, mid: str) -> dict:
        return self.request("GET", f"/conversations/{cid}/messages/{mid}")

    # ---- Knowledge ---------------------------------------------------------

    def list_knowledge(self, **params: Any) -> dict:
        return self.request("GET", "/knowledge", params=params)

    def get_knowledge(self, kid: str) -> dict:
        return self.request("GET", f"/knowledge/{kid}")

    def create_knowledge(
        self,
        file_paths: List[str],
        name: Optional[str] = None,
        parent: Optional[str] = None,
        teamspace: Optional[str] = None,
    ) -> dict:
        fields: Dict[str, str] = {}
        if name:
            fields["name"] = name
        if parent:
            fields["parent"] = parent
        files = [("files", p) for p in file_paths]
        ctype, data = _encode_multipart(fields, files)
        return self.request(
            "POST",
            "/knowledge",
            data=data,
            content_type=ctype,
            teamspace=teamspace,
        )

    def create_knowledge_from_connection(self, **body: Any) -> dict:
        # Official path is /knowledge/connect
        return self.request("POST", "/knowledge/connect", body=body)

    def update_knowledge(self, kid: str, **body: Any) -> dict:
        return self.request("PATCH", f"/knowledge/{kid}", body=body)

    def delete_knowledge(self, kid: str) -> Any:
        return self.request("DELETE", f"/knowledge/{kid}")

    def reindex_knowledge(self, kid: str) -> Any:
        return self.request("POST", f"/knowledge/{kid}/reindex")

    # ---- Search ------------------------------------------------------------

    def ai_search(
        self,
        query: str,
        record_types: Optional[List[str]] = None,
        limit: Optional[int] = None,
        teamspace: Optional[str] = None,
        **extra: Any,
    ) -> dict:
        body: Dict[str, Any] = {"query": query, **extra}
        if record_types is not None:
            body["record_types"] = record_types
        if limit is not None:
            body["limit"] = limit
        return self.request("POST", "/search/ai", body=body, teamspace=teamspace)

    def search_tree(self, query: str, **body: Any) -> dict:
        payload = {"query": query, **body}
        return self.request("POST", "/search/tree", body=payload)

    # ---- Batch predictions -------------------------------------------------

    def create_batch_prediction(
        self,
        model: str,
        items: list,
        prompt: str,
        output_schema: dict,
        completion_window: Optional[str] = None,
        metadata: Optional[dict] = None,
        **extra: Any,
    ) -> dict:
        body: Dict[str, Any] = {
            "model": model,
            "items": items,
            "prompt": prompt,
            "output_schema": output_schema,
            **extra,
        }
        if completion_window is not None:
            body["completion_window"] = completion_window
        if metadata is not None:
            body["metadata"] = metadata
        return self.request("POST", "/batch-predictions", body=body)

    def list_batch_predictions(self, **params: Any) -> dict:
        return self.request("GET", "/batch-predictions", params=params)

    def get_batch_prediction(self, bid: str) -> dict:
        return self.request("GET", f"/batch-predictions/{bid}")

    def get_batch_prediction_results(self, bid: str) -> bytes:
        return self.request("GET", f"/batch-predictions/{bid}/results", raw=True)

    def cancel_batch_prediction(self, bid: str) -> dict:
        return self.request("POST", f"/batch-predictions/{bid}/cancel")

    # ---- Connections / providers / connectors ------------------------------

    def list_connections(self, **params: Any) -> dict:
        return self.request("GET", "/connections", params=params)

    def create_connection(self, **body: Any) -> dict:
        return self.request("POST", "/connections", body=body)

    def get_connection(self, cid: str) -> dict:
        return self.request("GET", f"/connections/{cid}")

    def update_connection(self, cid: str, **body: Any) -> dict:
        return self.request("PATCH", f"/connections/{cid}", body=body)

    def delete_connection(self, cid: str) -> Any:
        return self.request("DELETE", f"/connections/{cid}")

    def list_connectors(self, **params: Any) -> dict:
        return self.request("GET", "/connectors", params=params)

    def list_connection_providers(self, **params: Any) -> dict:
        return self.request("GET", "/connection-providers", params=params)

    def create_connection_provider(self, **body: Any) -> dict:
        return self.request("POST", "/connection-providers", body=body)

    def get_connection_provider(self, pid: str) -> dict:
        return self.request("GET", f"/connection-providers/{pid}")

    def update_connection_provider(self, pid: str, **body: Any) -> dict:
        return self.request("PATCH", f"/connection-providers/{pid}", body=body)

    def delete_connection_provider(self, pid: str) -> Any:
        return self.request("DELETE", f"/connection-providers/{pid}")

    # ---- Data views & service accounts -------------------------------------

    def list_data_views(self, **params: Any) -> dict:
        return self.request("GET", "/data-views", params=params)

    def create_data_view(self, **body: Any) -> dict:
        return self.request("POST", "/data-views", body=body)

    def delete_data_view(self, vid: str) -> Any:
        return self.request("DELETE", f"/data-views/{vid}")

    def list_service_accounts(self, **params: Any) -> dict:
        return self.request("GET", "/service-accounts", params=params)

    def create_service_account(self, **body: Any) -> dict:
        return self.request("POST", "/service-accounts", body=body)

    def delete_service_account(self, sid: str) -> Any:
        return self.request("DELETE", f"/service-accounts/{sid}")

    def get_service_account_credentials(self, sid: str) -> dict:
        return self.request("GET", f"/service-accounts/{sid}/credentials")

    # ---- Files -------------------------------------------------------------

    def list_files(self, **params: Any) -> dict:
        return self.request("GET", "/files", params=params)

    def create_files(self, file_paths: List[str], teamspace: Optional[str] = None) -> dict:
        # API expects multipart field name "file" (singular). Upload one-by-one
        # when multiple paths are provided so each part uses the correct field.
        if len(file_paths) == 1:
            ctype, data = _encode_multipart({}, [("file", file_paths[0])])
            return self.request(
                "POST", "/files", data=data, content_type=ctype, teamspace=teamspace
            )
        results = []
        for path in file_paths:
            ctype, data = _encode_multipart({}, [("file", path)])
            results.append(
                self.request(
                    "POST", "/files", data=data, content_type=ctype, teamspace=teamspace
                )
            )
        return {"object": "list", "data": results}

    def get_file(self, fid: str) -> dict:
        return self.request("GET", f"/files/{fid}")

    def get_file_content(self, fid: str) -> bytes:
        return self.request("GET", f"/files/{fid}/content", raw=True)

    def update_file(self, fid: str, **body: Any) -> dict:
        return self.request("PATCH", f"/files/{fid}", body=body)

    def delete_file(self, fid: str) -> Any:
        return self.request("DELETE", f"/files/{fid}")

    # ---- Tables & records --------------------------------------------------

    def list_tables(self, **params: Any) -> dict:
        return self.request("GET", "/tables", params=params)

    def get_table(self, tid: str) -> dict:
        return self.request("GET", f"/tables/{tid}")

    def list_records(
        self,
        tid: str,
        limit: int = 100,
        next: Optional[str] = None,
        **params: Any,
    ) -> dict:
        q = {"limit": limit, "next": next, **params}
        return self.request("GET", f"/tables/{tid}/records", params=q)

    def all_records(
        self, tid: str, max_items: Optional[int] = None, limit: int = 100
    ) -> Iterator[dict]:
        cursor = None
        yielded = 0
        while True:
            page = self.list_records(tid, limit=limit, next=cursor) or {}
            rows = page.get("data") if isinstance(page, dict) else page
            if not isinstance(rows, list):
                return
            for row in rows:
                yield row
                yielded += 1
                if max_items is not None and yielded >= max_items:
                    return
            cursor = page.get("next") if isinstance(page, dict) else None
            if not cursor:
                return

    # ---- Teamspaces & users ------------------------------------------------

    def list_teamspaces(self, **params: Any) -> dict:
        return self.request(
            "GET", "/organization/teamspaces", params=params, skip_teamspace=True
        )

    def get_teamspace(self, tid: str) -> dict:
        return self.request("GET", f"/organization/teamspaces/{tid}", skip_teamspace=True)

    def create_teamspace(self, **body: Any) -> dict:
        return self.request("POST", "/organization/teamspaces", body=body, skip_teamspace=True)

    def update_teamspace(self, tid: str, **body: Any) -> dict:
        return self.request(
            "PATCH", f"/organization/teamspaces/{tid}", body=body, skip_teamspace=True
        )

    def find_teamspace(self, name: str) -> Optional[dict]:
        key = name.strip().lower()
        if key in self._teamspace_cache:
            return self._teamspace_cache[key]
        after = None
        while True:
            page = self.list_teamspaces(limit=100, after=after) or {}
            for t in page.get("data") or []:
                tname = (t.get("name") or "").strip()
                self._teamspace_cache[tname.lower()] = t
                if tname.lower() == key:
                    return t
            data = page.get("data") or []
            if not page.get("has_more") or not data:
                break
            after = data[-1].get("id")
            if not after:
                break
        return None

    def list_teamspace_users(self, tid: str, **params: Any) -> dict:
        return self.request("GET", f"/organization/teamspaces/{tid}/users", params=params)

    def get_teamspace_user(self, tid: str, uid: str) -> dict:
        return self.request("GET", f"/organization/teamspaces/{tid}/users/{uid}")

    def update_teamspace_user(self, tid: str, uid: str, **body: Any) -> dict:
        return self.request("PATCH", f"/organization/teamspaces/{tid}/users/{uid}", body=body)

    def delete_teamspace_user(self, tid: str, uid: str) -> Any:
        return self.request("DELETE", f"/organization/teamspaces/{tid}/users/{uid}")

    def list_teamspace_invites(self, tid: str, **params: Any) -> dict:
        return self.request("GET", f"/organization/teamspaces/{tid}/invites", params=params)

    def invite_user(self, tid: str, **body: Any) -> dict:
        return self.request("POST", f"/organization/teamspaces/{tid}/invites", body=body)

    def get_teamspace_invite(self, tid: str, iid: str) -> dict:
        return self.request("GET", f"/organization/teamspaces/{tid}/invites/{iid}")

    def delete_teamspace_invite(self, tid: str, iid: str) -> Any:
        return self.request("DELETE", f"/organization/teamspaces/{tid}/invites/{iid}")

    # ---- MCP servers -------------------------------------------------------

    def list_mcp_servers(self, **params: Any) -> dict:
        return self.request("GET", "/mcp-servers", params=params)

    def create_mcp_server(self, **body: Any) -> dict:
        return self.request("POST", "/mcp-servers", body=body)

    def get_mcp_server(self, sid: str) -> dict:
        return self.request("GET", f"/mcp-servers/{sid}")

    def update_mcp_server(self, sid: str, **body: Any) -> dict:
        return self.request("PATCH", f"/mcp-servers/{sid}", body=body)

    def delete_mcp_server(self, sid: str) -> Any:
        return self.request("DELETE", f"/mcp-servers/{sid}")

    # ---- Memory / pages / secrets / tools / users / webhooks ---------------

    def list_memory(self, **params: Any) -> dict:
        return self.request("GET", "/memory", params=params)

    def create_memory(self, **body: Any) -> dict:
        return self.request("POST", "/memory", body=body)

    def delete_memory(self, mid: str) -> Any:
        return self.request("DELETE", f"/memory/{mid}")

    def list_pages(self, **params: Any) -> dict:
        return self.request("GET", "/pages", params=params)

    def create_page(self, **body: Any) -> dict:
        return self.request("POST", "/pages", body=body)

    def get_page(self, pid: str) -> dict:
        return self.request("GET", f"/pages/{pid}")

    def update_page(self, pid: str, **body: Any) -> dict:
        return self.request("PATCH", f"/pages/{pid}", body=body)

    def delete_page(self, pid: str) -> Any:
        return self.request("DELETE", f"/pages/{pid}")

    def list_secrets(self, **params: Any) -> dict:
        return self.request("GET", "/secrets", params=params)

    def create_secret(self, **body: Any) -> dict:
        return self.request("POST", "/secrets", body=body)

    def get_secret(self, sid: str) -> dict:
        return self.request("GET", f"/secrets/{sid}")

    def delete_secret(self, sid: str) -> Any:
        return self.request("DELETE", f"/secrets/{sid}")

    def list_tools(self) -> dict:
        return self.request("GET", "/tools")

    def get_tool(self, tid: str) -> dict:
        return self.request("GET", f"/tools/{tid}")

    def list_users(self, **params: Any) -> dict:
        return self.request("GET", "/users", params=params)

    def get_user(self, uid: str) -> dict:
        return self.request("GET", f"/users/{uid}")

    def update_user(self, uid: str, **body: Any) -> dict:
        return self.request("PATCH", f"/users/{uid}", body=body)

    def list_webhooks(self, **params: Any) -> dict:
        return self.request("GET", "/webhooks", params=params)

    def create_webhook(self, **body: Any) -> dict:
        return self.request("POST", "/webhooks", body=body)

    def get_webhook(self, wid: str) -> dict:
        return self.request("GET", f"/webhooks/{wid}")

    def update_webhook(self, wid: str, **body: Any) -> dict:
        return self.request("PATCH", f"/webhooks/{wid}", body=body)

    def delete_webhook(self, wid: str) -> Any:
        return self.request("DELETE", f"/webhooks/{wid}")

    def list_active_webhooks_for_event(self, event: str) -> dict:
        return self.request("GET", "/webhooks/active", params={"event": event})


def _print_json(obj: Any) -> None:
    print(json.dumps(obj, indent=2, ensure_ascii=False, default=str))


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Datagrid API client CLI")
    parser.add_argument(
        "command",
        choices=["whoami", "agents", "teamspaces", "credits", "tools"],
        help="Quick smoke-test command",
    )
    parser.add_argument("--teamspace", default=None, help="Teamspace name or id")
    args = parser.parse_args(argv)

    try:
        client = DatagridClient(teamspace=args.teamspace)
        if args.command == "whoami":
            _print_json(client.whoami())
        elif args.command == "agents":
            _print_json(client.list_agents(limit=100))
        elif args.command == "teamspaces":
            _print_json(client.list_teamspaces(limit=100))
        elif args.command == "credits":
            _print_json(client.get_credits())
        elif args.command == "tools":
            _print_json(client.list_tools())
        return 0
    except DatagridError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
