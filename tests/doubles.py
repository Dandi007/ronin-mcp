"""In-process HTTP double for agent-bus.

The double binds a ThreadingHTTPServer on 127.0.0.1 with an OS-assigned
port so the production httpx.Client in ronin_mcp.backends.* can talk to
it over real TCP — this exercises the full request/response path
(headers, error wrapping) without booting any real backend process.

The double is intentionally minimal: it implements only the endpoint
surface that ronin_mcp facets touch, with a small in-memory store. It is
NOT a spec-complete replica of agent-bus.
"""

from __future__ import annotations

import json
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, urlparse


def _new_id(prefix: str = "") -> str:
    return f"{prefix}{uuid.uuid4().hex[:12]}"


class _Handler(BaseHTTPRequestHandler):
    """Shared handler base class with JSON helpers + auth stub."""

    server_state: dict[str, Any] = {}

    def _send_json(self, status: int, body: Any) -> None:
        data = json.dumps(body, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _read_body(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        if length == 0:
            return {}
        raw = self.rfile.read(length)
        try:
            data = json.loads(raw)
        except ValueError:
            return {}
        return data if isinstance(data, dict) else {}

    def _on_behalf(self) -> str | None:
        return self.headers.get("X-Bus-On-Behalf-Of") or self.headers.get("X-Operator-Identity")

    def _bearer_token(self) -> str:
        auth = self.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            return auth[7:]
        return ""

    def log_message(self, format: str, *args: object) -> None:
        self.server_state.setdefault("requests", []).append(self.command + " " + self.path)
        pass


class AgentBusDoubleHandler(_Handler):
    """Minimal agent-bus HTTP surface used by ronin_mcp facets."""

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")
        params = parse_qs(parsed.query)
        store = self.server_state["store"]

        if path == "/healthz" or path == "/readyz":
            self._send_json(200, {"status": "ok"})
            return
        if path == "/v1/agents/whoami":
            on_behalf = self._on_behalf()
            agent_id = on_behalf or "ronin-mcp"
            self._send_json(200, {"agent_id": agent_id, "is_admin": False, "kind": "service"})
            return
        if path == "/v1/agents":
            kind = params.get("kind", [None])[0]
            agents = list(store["agents"].values())
            if kind:
                agents = [a for a in agents if a.get("kind") == kind]
            self._send_json(200, {"agents": agents})
            return
        if path == "/v1/aliases":
            kind = params.get("kind", [None])[0]
            aliases = list(store["aliases"].values())
            if kind:
                aliases = [a for a in aliases if a.get("kind") == kind]
            self._send_json(200, {"aliases": aliases})
            return
        if path == "/v1/channels":
            prefix = params.get("prefix", [None])[0]
            mode = params.get("mode", [None])[0]
            channels = list(store["channels"].values())
            if prefix:
                channels = [c for c in channels if c["channel_id"].startswith(prefix)]
            if mode:
                channels = [c for c in channels if c.get("delivery_mode") == mode]
            self._send_json(200, {"channels": [_public_channel(c) for c in channels]})
            return
        segs = path.strip("/").split("/")
        if len(segs) == 3 and segs[0] == "v1" and segs[1] == "aliases":
            alias = segs[2]
            entry = store["aliases"].get(alias)
            if entry is None:
                self._send_json(404, {"code": "NOT_FOUND", "message": f"Alias {alias} not found"})
                return
            self._send_json(200, entry)
            return
        if len(segs) == 3 and segs[0] == "v1" and segs[1] == "channels":
            channel_id = segs[2]
            channel = store["channels"].get(channel_id)
            if channel is None:
                self._send_json(404, {"code": "NOT_FOUND", "message": "channel not found"})
                return
            self._send_json(200, _public_channel(channel))
            return
        if len(segs) == 4 and segs[0] == "v1" and segs[1] == "channels" and segs[3] == "messages":
            channel_id = segs[2]
            msgs = [m for m in store["messages"] if m["channel_id"] == channel_id]
            self._send_json(200, {"messages": msgs})
            return
        if path == "/v1/events":
            self._send_json(200, {"events": list(store["events"])})
            return
        self._send_json(404, {"code": "NOT_FOUND", "message": f"unknown path {path}"})

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")
        store = self.server_state["store"]
        on_behalf = self._on_behalf()

        if path == "/v1/agents":
            body = self._read_body()
            agent_id = body.get("agent_id") or _new_id("agent-")
            kind = body.get("kind", "agent")
            agent = {
                "agent_id": agent_id,
                "display_name": body.get("display_name", ""),
                "kind": kind,
                "inbox_channel_id": f"agent:{agent_id}",
            }
            store["agents"][agent_id] = agent
            self._send_json(200, agent)
            return
        if path == "/v1/aliases":
            body = self._read_body()
            alias = body.get("alias", "")
            kind = body.get("kind", "named")
            agent_id = body.get("agent_id", "")
            entry = {
                "alias": alias,
                "kind": kind,
                "current_agent_id": agent_id,
                "via": "mcp-gateway" if on_behalf else "http",
            }
            store["aliases"][alias] = entry
            self._send_json(200, entry)
            return
        segs = path.strip("/").split("/")
        if len(segs) == 4 and segs[0] == "v1" and segs[1] == "aliases" and segs[3] == "rebind":
            alias = segs[2]
            body = self._read_body()
            existing = store["aliases"].get(alias)
            if existing is None:
                self._send_json(404, {"code": "NOT_FOUND", "message": "alias not found"})
                return
            existing["current_agent_id"] = body.get("agent_id", "")
            self._send_json(200, existing)
            return
        if path == "/v1/channels":
            body = self._read_body()
            channel_id = body.get("channel_id", "")
            channel = {
                "channel_id": channel_id,
                "delivery_mode": body.get("delivery_mode", "fanout"),
                "visibility": body.get("visibility", "public"),
                "metadata": body.get("metadata", {}),
                "subscribers": set(),
            }
            store["channels"][channel_id] = channel
            self._send_json(200, _public_channel(channel))
            return
        if len(segs) == 4 and segs[0] == "v1" and segs[1] == "channels" and segs[3] == "subscribe":
            channel_id = segs[2]
            channel = store["channels"].get(channel_id)
            if channel is None:
                self._send_json(404, {"code": "NOT_FOUND", "message": "channel not found"})
                return
            channel["subscribers"].add(on_behalf or "anonymous")
            self._send_json(200, {"channel_id": channel_id, "subscribed": True})
            return
        if len(segs) == 4 and segs[0] == "v1" and segs[1] == "channels" and segs[3] == "publish":
            channel_id = segs[2]
            body = self._read_body()
            idempotency_key = body.get("idempotency_key", "")
            if idempotency_key in store["idempotent"]:
                self._send_json(
                    200, {"message_id": store["idempotent"][idempotency_key], "duplicate": True}
                )
                return
            message_id = _new_id("msg-")
            delivery_id = _new_id("del-")
            lease_token = _new_id("lease-")
            message = {
                "message_id": message_id,
                "channel_id": channel_id,
                "kind": body.get("kind", "agent.msg.v1"),
                "payload": body.get("payload", {}),
                "idempotency_key": idempotency_key,
            }
            store["messages"].append(message)
            store["deliveries"][delivery_id] = {
                "delivery_id": delivery_id,
                "channel_id": channel_id,
                "message": message,
                "lease_token": lease_token,
                "state": "delivered",
            }
            store["idempotent"][idempotency_key] = message_id
            store["events"].append({
                "type": "published",
                "channel_id": channel_id,
                "agent_id": on_behalf or "anonymous",
                "payload": {"via": "ronin-mcp", "principal_agent_id": "ronin-mcp"},
            })
            self._send_json(200, {"message_id": message_id})
            return
        if len(segs) == 4 and segs[0] == "v1" and segs[1] == "channels" and segs[3] == "consume":
            channel_id = segs[2]
            body = self._read_body()
            max_messages = body.get("max_messages", 100)
            deliveries = []
            for did, d in list(store["deliveries"].items()):
                if d["channel_id"] == channel_id and d["state"] == "delivered":
                    d["state"] = "leased"
                    d["lease_owner"] = on_behalf or "anonymous"
                    deliveries.append({
                        "delivery_id": did,
                        "lease_token": d["lease_token"],
                        "message": d["message"],
                    })
                    if len(deliveries) >= max_messages:
                        break
            self._send_json(200, {"deliveries": deliveries})
            return
        if path == "/v1/broadcast":
            body = self._read_body()
            self._send_json(200, {"broadcast_id": _new_id("bc-"), "recipients": 0})
            return
        segs = path.strip("/").split("/")
        if len(segs) == 4 and segs[0] == "v1" and segs[1] == "deliveries":
            did = segs[2]
            action = segs[3]
            delivery = store["deliveries"].get(did)
            if delivery is None:
                self._send_json(404, {"code": "NOT_FOUND", "message": "delivery not found"})
                return
            body = self._read_body()
            lease_token = body.get("lease_token", "")
            if lease_token != delivery["lease_token"]:
                self._send_json(403, {"code": "FORBIDDEN", "message": "lease_token mismatch"})
                return
            if action == "ack":
                delivery["state"] = "acked"
                self._send_json(200, {"state": "acked", "delivery_id": did})
                return
            if action == "nack":
                delivery["state"] = "nacked"
                self._send_json(200, {"state": "nacked", "delivery_id": did})
                return
            if action == "renew":
                self._send_json(200, {"state": "leased", "delivery_id": did})
                return
        self._send_json(404, {"code": "NOT_FOUND", "message": f"unknown path {path}"})

    def do_DELETE(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")
        store = self.server_state["store"]
        on_behalf = self._on_behalf()
        segs = path.strip("/").split("/")
        if len(segs) == 4 and segs[0] == "v1" and segs[1] == "channels" and segs[3] == "subscribe":
            channel_id = segs[2]
            channel = store["channels"].get(channel_id)
            if channel is None:
                self._send_json(404, {"code": "NOT_FOUND", "message": "channel not found"})
                return
            channel["subscribers"].discard(on_behalf or "anonymous")
            self._send_json(200, {"channel_id": channel_id, "subscribed": False})
            return
        self._send_json(404, {"code": "NOT_FOUND", "message": f"unknown path {path}"})


def _public_channel(channel: dict[str, Any]) -> dict[str, Any]:
    return {
        "channel_id": channel["channel_id"],
        "delivery_mode": channel["delivery_mode"],
        "visibility": channel["visibility"],
        "metadata": channel.get("metadata", {}),
        "subscribers": sorted(channel.get("subscribers", set())),
    }


class _DoubleServer:
    """Run a handler on a ThreadingHTTPServer bound to an OS-assigned port."""

    def __init__(self, handler_cls: type[_Handler], initial_state: dict[str, Any]) -> None:
        self._handler_cls = handler_cls
        self._state = initial_state
        self._server: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None

    @property
    def url(self) -> str:
        assert self._server is not None, "double not started"
        host, port = self._server.server_address
        return f"http://{host}:{port}"

    @property
    def store(self) -> dict[str, Any]:
        return self._state["store"]

    @property
    def requests(self) -> list[str]:
        """Every request line (e.g. "GET /v1/agents") the double has served."""
        return self._state.setdefault("requests", [])

    def start(self) -> None:
        handler_cls = self._handler_cls
        state = self._state

        class _Bound(handler_cls):
            server_state = state

        self._server = ThreadingHTTPServer(("127.0.0.1", 0), _Bound)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        # Give the server a beat to bind.
        deadline = time.time() + 2.0
        while time.time() < deadline:
            if self._server.server_address[1] != 0:
                return
            time.sleep(0.01)

    def stop(self) -> None:
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
        if self._thread is not None:
            self._thread.join(timeout=5)


def make_bus_double(token: str = "test-gateway-token-32-chars-minimum!") -> _DoubleServer:
    """Build an agent-bus HTTP double with an empty in-memory store."""
    state = {
        "store": {
            "agents": {},
            "aliases": {},
            "channels": {},
            "messages": [],
            "deliveries": {},
            "idempotent": {},
            "events": [],
        },
        "token": token,
    }
    return _DoubleServer(AgentBusDoubleHandler, state)
