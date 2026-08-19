"""Ronin MCP server.

build_mcp_server composes the seven facets onto a single FastMCP
instance, sharing one AuthState and one backend client per backend.
The main() entrypoint reads config + token, builds the server, and
runs it over streamable-http bound to 127.0.0.1.

The server is transport-agnostic: tests call build_mcp_server with a
mock transport and use FastMCP's in-memory Client to exercise the
tools without booting any real backend.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from typing import Any, Callable

from ronin_mcp.auth import AuthState, WriteAuthError
from ronin_mcp.backends.agent_bus import AgentBusClient, BackendError
from ronin_mcp.backends.dev_dispatch import DevDispatchClient
from ronin_mcp.backends.pump_state import PumpStateClient
from ronin_mcp.backends.work_folder import WorkFolderClient
from ronin_mcp.config import load_config, resolve_gateway_token

MCP_INSTRUCTIONS = """Ronin MCP - aggregating facade for the ronin fleet control plane.

1. Read tools (list/get/resolve/events/whoami/read/stat/capabilities) are
   freely available to any authenticated caller.
2. Write tools (register/create/rebind/send/broadcast/approve/reject/start/
   steer/control/reconfigure/relock/add_member/remove_member/save/write/edit/
   delete/copy/rename/batch/evidence_put/evidence_migrate/append_progress/
   reconcile/reindex/consume) are guarded at the entrance.
3. gd: prefix marks test/dev resources; writes targeting gd: resources are
   allowed without explicit production authorization.
4. RONIN_PROD_WRITE=1 (or --prod-write) unlocks production writes outside the
   gd: namespace.
5. --ephemeral (or RONIN_EPHEMERAL=1) routes all writes to ephemeral backends
   and unlocks everything.
6. Gate approvals (ronin_gate_approve / ronin_gate_reject) ALWAYS require
   RONIN_PROD_WRITE=1, even for gd: developments, because they are B-class
   irreversible operations.
7. Tokens never enter model context: tool parameters never carry credentials,
   and tool return values never include token material.
"""


def build_mcp_server(
    config: dict[str, Any],
    *,
    bus_client: AgentBusClient | None = None,
    controller_client: DevDispatchClient | None = None,
    work_folder_client: WorkFolderClient | None = None,
    pump_client: PumpStateClient | None = None,
    error_wrapper: Callable[[Callable[[], Any]], Any] | None = None,
) -> Any:
    """Build a FastMCP server with all seven facets registered.

    Client injection is optional so tests can substitute doubles. When a
    client is None, build_mcp_server constructs the production client
    from the provided config.
    """
    try:
        from fastmcp import FastMCP
        from fastmcp.exceptions import ToolError
    except ImportError:
        print(
            "fastmcp not installed. Install with: uv sync --extra dev",
            file=sys.stderr,
        )
        sys.exit(1)

    mcp = FastMCP("ronin-mcp", instructions=MCP_INSTRUCTIONS)

    auth = AuthState.from_config(config)

    backends = config.get("backends", {})
    bus_cfg = backends.get("agent_bus", {})
    dd_cfg = backends.get("dev_dispatch", {})
    wf_cfg = backends.get("work_folder", {})
    pump_cfg = backends.get("pump_state", {})

    bus = bus_client or AgentBusClient(
        bus_cfg.get("url", "http://127.0.0.1:7490"),
        gateway_token=resolve_gateway_token(config),
    )
    controller = controller_client or DevDispatchClient(
        dd_cfg.get("url", "http://127.0.0.1:7460"),
    )
    work_folder = work_folder_client or WorkFolderClient(
        wf_cfg.get("mcp_url", "http://127.0.0.1:5605/mcp"),
    )
    pump = pump_client or PumpStateClient(
        pump_cfg.get("runs_root", "/data/ronin/runs"),
    )

    wrapper = error_wrapper or _make_error_wrapper(ToolError)

    from ronin_mcp.facets.alias import register as register_alias
    from ronin_mcp.facets.chatgroup import register as register_chatgroup
    from ronin_mcp.facets.development import register as register_development
    from ronin_mcp.facets.gate import register as register_gate
    from ronin_mcp.facets.messaging import register as register_messaging
    from ronin_mcp.facets.pump import register as register_pump
    from ronin_mcp.facets.work_folder import register as register_work_folder

    register_alias(mcp, auth, bus, wrapper)
    register_chatgroup(mcp, auth, bus, wrapper)
    register_messaging(mcp, auth, bus, wrapper)
    register_development(mcp, auth, controller, wrapper)
    register_gate(mcp, auth, controller, wrapper)
    register_pump(mcp, pump, wrapper)
    register_work_folder(mcp, auth, work_folder, wrapper)

    return mcp


def _make_error_wrapper(tool_error_cls: type) -> Callable[[Callable[[], Any]], Any]:
    """Wrap a callable so backend / auth errors surface as ToolError."""

    def _wrapper(fn: Callable[[], Any]) -> Any:
        try:
            return fn()
        except WriteAuthError as exc:
            raise tool_error_cls(
                json.dumps(exc.payload, ensure_ascii=False)
            ) from exc
        except BackendError as exc:
            raise tool_error_cls(str(exc)) from exc

    return _wrapper


def main() -> None:
    parser = argparse.ArgumentParser(prog="ronin-mcp")
    parser.add_argument(
        "--prod-write",
        action="store_true",
        help="Authorize production writes (non-gd: resources). "
        "Equivalent to RONIN_PROD_WRITE=1.",
    )
    parser.add_argument(
        "--ephemeral",
        action="store_true",
        help="Route all writes to ephemeral backends and unlock everything. "
        "Equivalent to RONIN_EPHEMERAL=1.",
    )
    parser.add_argument(
        "--config",
        default=None,
        help="Path to config.yaml (default: $RONIN_MCP_CONFIG or "
        "~/.config/ronin/config.yaml).",
    )
    args = parser.parse_args()

    config = load_config(args.config)
    if args.prod_write:
        config["auth"]["prod_write_enabled"] = True
    if args.ephemeral:
        config["auth"]["ephemeral"] = True

    if not config["auth"]["ephemeral"]:
        token = resolve_gateway_token(config)
        if not token or len(token) < 32:
            print(
                "RONIN_GATEWAY_TOKEN must be set and at least 32 characters "
                "(or backends.agent_bus.gateway_token_file must point to a "
                ">=32-char file) unless --ephemeral is used.",
                file=sys.stderr,
            )
            sys.exit(1)

    mcp = build_mcp_server(config)

    server_cfg = config.get("server", {})
    host = server_cfg.get("host", "127.0.0.1")
    port = server_cfg.get("port", 5609)

    _wait_for_backends(config)

    mcp.run(transport="streamable-http", host=host, port=port, path="/mcp")


def _wait_for_backends(config: dict[str, Any]) -> None:
    """Best-effort readiness probe for agent-bus (skip when unreachable).

    Production deployments list After=agent-bus-server.service in the
    systemd unit, so the bus is normally ready before ronin-mcp starts.
    We still poll /readyz for up to 30s to be resilient to restarts.
    """
    import httpx

    backends = config.get("backends", {})
    bus_url = backends.get("agent_bus", {}).get("url", "")
    if not bus_url:
        return
    client = httpx.Client(trust_env=False)
    deadline = time.time() + 30
    while time.time() < deadline:
        try:
            resp = client.get(f"{bus_url}/readyz", timeout=2.0)
            if resp.status_code == 200:
                return
        except Exception:
            pass
        time.sleep(0.5)
    # Continue starting anyway; tool calls will surface backend errors.


if __name__ == "__main__":
    main()
