"""Friend (Alias registry) facet.

Wraps agent-bus alias / agent endpoints under ronin_alias_* and
ronin_agent_*. Write operations are guarded by check_write_auth.
"""

from __future__ import annotations

from typing import Any

from ronin_mcp.auth import AuthState, WriteAuthError, check_write_auth
from ronin_mcp.backends.agent_bus import AgentBusClient


def register(
    mcp: Any,
    auth: AuthState,
    bus: AgentBusClient,
    error_wrapper: Any,
) -> None:
    """Register ronin_alias_* and ronin_agent_* tools on the FastMCP server."""

    @mcp.tool()
    def ronin_alias_list(
        kind: str | None = None,
        as_agent_id: str | None = None,
    ) -> dict[str, Any]:
        """List all aliases (read)."""
        params: dict[str, Any] = {}
        if kind:
            params["kind"] = kind
        return error_wrapper(lambda: bus.get("/v1/aliases", params=params, as_agent_id=as_agent_id))

    @mcp.tool()
    def ronin_alias_resolve(
        alias: str,
        as_agent_id: str | None = None,
    ) -> dict[str, Any]:
        """Resolve alias -> agent_id (read)."""
        return error_wrapper(
            lambda: bus.get(f"/v1/aliases/{alias}", as_agent_id=as_agent_id)
        )

    @mcp.tool()
    def ronin_alias_register(
        alias: str,
        kind: str,
        agent_id: str,
        as_agent_id: str | None = None,
    ) -> dict[str, Any]:
        """Register alias (write; requires gd: prefix or RONIN_PROD_WRITE=1)."""
        def _do() -> dict[str, Any]:
            check_write_auth(auth, alias)
            return bus.post(
                "/v1/aliases",
                {"alias": alias, "kind": kind, "agent_id": agent_id},
                as_agent_id=as_agent_id,
            )
        return error_wrapper(_do)

    @mcp.tool()
    def ronin_alias_rebind(
        alias: str,
        agent_id: str,
        expected_current_agent_id: str,
        as_agent_id: str | None = None,
    ) -> dict[str, Any]:
        """Rebind alias (CAS) (write; requires gd: prefix or RONIN_PROD_WRITE=1)."""
        def _do() -> dict[str, Any]:
            check_write_auth(auth, alias)
            return bus.post(
                f"/v1/aliases/{alias}/rebind",
                {"agent_id": agent_id, "expected_current_agent_id": expected_current_agent_id},
                as_agent_id=as_agent_id,
            )
        return error_wrapper(_do)

    @mcp.tool()
    def ronin_agent_list(
        kind: str | None = None,
        as_agent_id: str | None = None,
    ) -> dict[str, Any]:
        """List agents (read)."""
        params: dict[str, Any] = {}
        if kind:
            params["kind"] = kind
        return error_wrapper(lambda: bus.get("/v1/agents", params=params, as_agent_id=as_agent_id))

    @mcp.tool()
    def ronin_agent_whoami(as_agent_id: str | None = None) -> dict[str, Any]:
        """Current identity (read)."""
        return error_wrapper(lambda: bus.get("/v1/agents/whoami", as_agent_id=as_agent_id))

    @mcp.tool()
    def ronin_agent_register(
        agent_id: str,
        display_name: str,
        kind: str = "agent",
        as_agent_id: str | None = None,
    ) -> dict[str, Any]:
        """Register agent (write; requires gd: prefix or RONIN_PROD_WRITE=1).

        The agent-bus gateway strips `token` from the response; we keep
        the same behavior so credentials never enter model context.
        """
        def _do() -> dict[str, Any]:
            check_write_auth(auth, agent_id)
            result = bus.post(
                "/v1/agents",
                {"agent_id": agent_id, "display_name": display_name, "kind": kind},
                as_agent_id=as_agent_id,
            )
            if isinstance(result, dict) and "token" in result:
                del result["token"]
            return result
        return error_wrapper(_do)
