"""Ronin MCP server.

build_mcp_server composes the four live facets (alias, chatgroup,
messaging, work folder) onto a single FastMCP instance, sharing one
AuthState and one backend client per backend. The main() entrypoint
reads config + token, builds the server, and runs it over
streamable-http bound to 127.0.0.1.

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

from starlette.requests import Request
from starlette.responses import PlainTextResponse

from ronin_mcp.auth import AuthState, WriteAuthError
from ronin_mcp.backends.agent_bus import AgentBusClient, BackendError
from ronin_mcp.backends.work_folder import WorkFolderClient
from ronin_mcp.config import load_config, resolve_gateway_token

MCP_INSTRUCTIONS = """Ronin MCP - aggregating facade for the ronin fleet control plane.

1. Read tools (list/get/resolve/events/whoami/read/stat/capabilities) are
   freely available to any authenticated caller.
2. Write tools (register/create/rebind/send/broadcast/add_member/remove_member/
   save/write/edit/delete/copy/rename/batch/evidence_put/evidence_migrate/
   append_progress/reconcile/reindex/consume) are guarded at the entrance.
3. gd: prefix marks test/dev resources; writes targeting gd: resources are
   allowed without explicit production authorization.
4. RONIN_PROD_WRITE=1 (or --prod-write) unlocks production writes outside the
   gd: namespace.
5. Fleet-wide / B-class operations (broadcast / reconcile / reindex) ALWAYS
   require RONIN_PROD_WRITE=1, even for gd: resources, because they are
   irreversible operations.
6. --ephemeral (or RONIN_EPHEMERAL=1) routes all writes to ephemeral backends
   and unlocks everything.
7. Tokens never enter model context: tool parameters never carry credentials,
   and tool return values never include token material.
"""


def build_mcp_server(
    config: dict[str, Any],
    *,
    bus_client: AgentBusClient | None = None,
    work_folder_client: WorkFolderClient | None = None,
    error_wrapper: Callable[[Callable[[], Any]], Any] | None = None,
    ephemeral_runtime: Any = None,
) -> Any:
    """Build a FastMCP server with the four live facets registered.

    Client injection is optional so tests can substitute doubles. When a
    client is None, build_mcp_server constructs the production client
    from the provided config.

    In ephemeral mode (``config['auth']['ephemeral']`` is True) the
    server routes ALL writes to the ephemeral backends owned by the
    supplied ``ephemeral_runtime`` — never to the configured (potentially
    production) backend URLs. The caller is responsible for starting the
    ``EphemeralRuntime`` (it is injected here so the server build is
    deterministic and testable).
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

    _register_metrics_route(mcp)

    auth = AuthState.from_config(config)

    backends = config.get("backends", {})
    bus_cfg = backends.get("agent_bus", {})
    wf_cfg = backends.get("work_folder", {})

    if auth.ephemeral and ephemeral_runtime is not None:
        # Spec 判据 1 rule 1: route ALL writes to --ephemeral backends.
        bus = bus_client or AgentBusClient(
            ephemeral_runtime.bus_url,
            gateway_token=ephemeral_runtime.bus_gateway_token,
        )
        work_folder = work_folder_client or _build_ephemeral_work_folder(ephemeral_runtime)
    else:
        bus = bus_client or AgentBusClient(
            bus_cfg.get("url", "http://127.0.0.1:7490"),
            gateway_token=resolve_gateway_token(config),
        )
        work_folder = work_folder_client or WorkFolderClient(
            wf_cfg.get("mcp_url", "http://127.0.0.1:5605/mcp"),
        )

    wrapper = error_wrapper or _make_error_wrapper(ToolError)
    async_wrapper = _make_async_error_wrapper(ToolError)

    from ronin_mcp.facets.alias import register as register_alias
    from ronin_mcp.facets.chatgroup import register as register_chatgroup
    from ronin_mcp.facets.messaging import register as register_messaging
    from ronin_mcp.facets.work_folder import register as register_work_folder

    register_alias(mcp, auth, bus, wrapper)
    register_chatgroup(mcp, auth, bus, wrapper)
    register_messaging(mcp, auth, bus, wrapper)
    register_work_folder(mcp, auth, work_folder, async_wrapper)

    return mcp


class _ServerIntrospection:
    """Synchronous ``list_tools`` view over a FastMCP server.

    FastMCP's ``list_tools`` is an async function, but acceptance-style
    introspection wants a plain synchronous ``create_server().list_tools()``
    call. This thin proxy forwards every attribute to the underlying
    server and exposes a synchronous ``list_tools()`` that runs the async
    one in a fresh event loop. Other server capabilities (``run``,
    ``http_app``, ...) are forwarded unchanged.
    """

    def __init__(self, server: Any) -> None:
        self._server = server

    def __getattr__(self, name: str) -> Any:
        return getattr(self._server, name)

    def list_tools(self) -> list[Any]:
        import asyncio

        return asyncio.run(self._server.list_tools())


def create_server(config: dict[str, Any] | None = None) -> Any:
    """Build the ronin-mcp server from the standard config resolution path.

    When ``config`` is omitted the default config (deep-merged with any
    user config file / environment overrides) is loaded via
    ``load_config()``. Returns a proxy exposing a synchronous
    ``list_tools()`` for server-level introspection (e.g.
    ``create_server().list_tools()``).
    """
    if config is None:
        config = load_config()
    return _ServerIntrospection(build_mcp_server(config))


def _register_metrics_route(mcp: Any) -> None:
    """Register a process-local /metrics endpoint (Prometheus text).

    The endpoint is auth-free and never touches any backend/facet: it
    only reports that this ronin-mcp process is up. It is registered on
    the FastMCP instance so it appears on the ASGI app produced by
    ``http_app()`` (and on the production streamable-http app in
    ``main()``), alongside the unchanged ``/mcp`` and facet routes.
    """
    METRICS_BODY = "# TYPE ronin_mcp_up gauge\nronin_mcp_up 1\n"
    METRICS_MEDIA_TYPE = "text/plain; version=0.0.4; charset=utf-8"

    @mcp.custom_route("/metrics", methods=["GET"], include_in_schema=False)
    async def _metrics(request: Request) -> PlainTextResponse:
        return PlainTextResponse(METRICS_BODY, media_type=METRICS_MEDIA_TYPE)


def _build_ephemeral_work_folder(ephemeral_runtime: Any) -> Any:
    """Build a temp-dir-backed work-folder client for ephemeral mode.

    Spec 判据 1 rule 1: work-folder writes must route to a temp dir,
    never to the production katana-work-folder MCP.
    """
    from ronin_mcp.ephemeral import TempDirWorkFolderClient

    return TempDirWorkFolderClient(ephemeral_runtime.work_folder_root)


def _make_error_wrapper(tool_error_cls: type) -> Callable[[Callable[[], Any]], Any]:
    """Wrap a callable so backend / auth errors surface as ToolError.

    Auth and backend errors are serialized as the canonical structured
    envelope required by spec §错误模型 so callers can parse the
    ``{code, message, details: {retryable}}`` shape from the ToolError
    message:

        WriteAuthError  -> {"code": "PROD_WRITE_NOT_AUTHORIZED", ...}
        BackendError    -> {"code": "BACKEND_ERROR" | "BACKEND_UNAVAILABLE",
                            "message": ..., "details": {"retryable": bool}}
    """

    def _wrapper(fn: Callable[[], Any]) -> Any:
        try:
            return fn()
        except WriteAuthError as exc:
            raise tool_error_cls(
                json.dumps(exc.payload, ensure_ascii=False)
            ) from exc
        except BackendError as exc:
            raise tool_error_cls(
                json.dumps(exc.envelope, ensure_ascii=False)
            ) from exc

    return _wrapper


def _make_async_error_wrapper(tool_error_cls: type) -> Callable[[Callable[[], Any]], Any]:
    """Async analogue of ``_make_error_wrapper``.

    The work-folder facet tools are ``async def`` and call the backend's
    async ``call()`` entry directly. This wrapper awaits the given
    coroutine producer and converts the same exception shapes (auth /
    backend) into the canonical structured ToolError envelope.
    """

    async def _wrapper(fn: Callable[[], Any]) -> Any:
        try:
            return await fn()
        except WriteAuthError as exc:
            raise tool_error_cls(
                json.dumps(exc.payload, ensure_ascii=False)
            ) from exc
        except BackendError as exc:
            raise tool_error_cls(
                json.dumps(exc.envelope, ensure_ascii=False)
            ) from exc

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

    # Spec 判据 1 rule 1 + 判据 3: --ephemeral must start temporary
    # agent-bus + Controller instances and route ALL writes to them,
    # never to the configured (potentially production) backend URLs. The
    # ephemeral runtime owns the temp resources and cleans them up on
    # process exit (including via atexit so signal kills still clean up).
    ephemeral_runtime: Any = None
    if config["auth"]["ephemeral"]:
        from ronin_mcp.ephemeral import EphemeralRuntime

        ephemeral_runtime = EphemeralRuntime().start()

    try:
        mcp = build_mcp_server(config, ephemeral_runtime=ephemeral_runtime)

        server_cfg = config.get("server", {})
        host = server_cfg.get("host", "127.0.0.1")
        port = server_cfg.get("port", 5609)

        if not config["auth"]["ephemeral"]:
            _wait_for_backends(config)

        mcp.run(transport="streamable-http", host=host, port=port, path="/mcp")
    finally:
        if ephemeral_runtime is not None:
            ephemeral_runtime.close()


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
