"""FastMCP gateway for Ronin MCP.

A single aggregating MCP server over agent-bus HTTP, loop-engine Controller
HTTP, katana-work-folder MCP, and the pump-state filesystem. Write-surface
guardrails (gd: prefix / ephemeral / prod-write) are enforced at the entry.
"""

from __future__ import annotations

import os
import sys
from typing import Any

from ronin_mcp.config import load_config, resolve_auth_state

MCP_INSTRUCTIONS = """Ronin MCP Gateway - Instructions for external agents:

1. Read-surface tools are free; every write-surface tool is guarded at the
   entrance.
2. Test/dev resources use the `gd:` prefix and are writable without extra
   authorization; production writes require RONIN_PROD_WRITE=1 / --prod-write.
3. Ephemeral mode (--ephemeral / RONIN_EPHEMERAL=1) opens the full write
   surface against ephemeral backends.
4. Gate approve/reject are B-class irreversible and ALWAYS require
   RONIN_PROD_WRITE=1, even for gd: developments.
5. Token material never enters model context; ronin-mcp delegates on behalf
   of agents via X-Bus-On-Behalf-Of / X-Operator-Identity.
6. This gateway binds 127.0.0.1; it can impersonate any non-admin agent
   that can reach it, same as the agent-bus trust boundary.
7. Do not mutate production data without explicit prod-write authorization;
   prefer gd: namespaces for exercises and smoke tests.
"""


def build_mcp_server(
    config: dict[str, Any],
    *,
    auth_state: dict[str, Any] | None = None,
    bus_client: Any | None = None,
    controller_client: Any | None = None,
    work_folder_client: Any | None = None,
    pump_client: Any | None = None,
) -> Any:
    """Build the FastMCP server.

    Backend clients default to real HTTP/MCP clients built from config. Tests
    may inject fakes via the keyword arguments. ``auth_state`` defaults to
    the config + environment resolved state.
    """
    try:
        from fastmcp import FastMCP
    except ImportError:
        print("fastmcp not installed. Install with: uv sync --extra dev", file=sys.stderr)
        sys.exit(1)

    mcp = FastMCP("ronin-mcp", instructions=MCP_INSTRUCTIONS)

    if auth_state is None:
        auth_state = resolve_auth_state(config)

    backends = config.get("backends", {})

    if bus_client is None:
        from ronin_mcp.backends.agent_bus import AgentBusClient

        ab = backends.get("agent_bus", {})
        token_file = ab.get("gateway_token_file", "")
        gateway_token = os.environ.get("BUS_GATEWAY_TOKEN", "")
        if not gateway_token and token_file:
            gateway_token = os.environ.get("RONIN_BUS_GATEWAY_TOKEN", "")
            if not gateway_token:
                from ronin_mcp.config import load_gateway_token

                if token_file and os.path.exists(token_file):
                    gateway_token = load_gateway_token(token_file)
        bus_client = AgentBusClient(
            ab.get("url", "http://127.0.0.1:7490"),
            gateway_token or "x" * 32,
        )

    if controller_client is None:
        from ronin_mcp.backends.dev_dispatch import DevDispatchClient

        dd = backends.get("dev_dispatch", {})
        controller_client = DevDispatchClient(dd.get("url", "http://127.0.0.1:7460"))

    if work_folder_client is None:
        from ronin_mcp.backends.work_folder import WorkFolderClient

        wf = backends.get("work_folder", {})
        work_folder_client = WorkFolderClient(wf.get("mcp_url", "http://127.0.0.1:5605/mcp"))

    if pump_client is None:
        from ronin_mcp.backends.pump_state import PumpStateClient

        ps = backends.get("pump_state", {})
        pump_client = PumpStateClient(ps.get("runs_root", "/data/ronin/runs"))

    from ronin_mcp.facets.alias import register as register_alias
    from ronin_mcp.facets.chatgroup import register as register_chatgroup
    from ronin_mcp.facets.development import register as register_development
    from ronin_mcp.facets.gate import register as register_gate
    from ronin_mcp.facets.messaging import register as register_messaging
    from ronin_mcp.facets.pump import register as register_pump
    from ronin_mcp.facets.work_folder import register as register_work_folder

    register_alias(mcp, bus=bus_client, auth_state=auth_state)
    register_chatgroup(mcp, bus=bus_client, auth_state=auth_state)
    register_messaging(mcp, bus=bus_client, auth_state=auth_state)
    register_development(mcp, controller=controller_client, auth_state=auth_state)
    register_work_folder(mcp, wf=work_folder_client, auth_state=auth_state)
    register_pump(mcp, pump=pump_client)
    register_gate(mcp, controller=controller_client, auth_state=auth_state)

    return mcp


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Ronin MCP gateway")
    parser.add_argument("--ephemeral", action="store_true", help="route writes to ephemeral backends")
    parser.add_argument("--prod-write", action="store_true", help="authorize production writes")
    parser.add_argument("--config", default=None, help="config.yaml path")
    args = parser.parse_args()

    config = load_config(args.config)

    if args.ephemeral:
        config.setdefault("auth", {})["ephemeral"] = True
    if args.prod_write:
        config.setdefault("auth", {})["prod_write_enabled"] = True

    auth_state = resolve_auth_state(config)
    mcp = build_mcp_server(config, auth_state=auth_state)

    server_cfg = config.get("server", {})
    host = server_cfg.get("host", "127.0.0.1")
    port = int(server_cfg.get("port", 5609))

    mcp.run(transport="streamable-http", host=host, port=port, path="/mcp")


if __name__ == "__main__":
    main()
