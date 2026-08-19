"""Facet 1: Alias registry (ronin_alias_* / ronin_agent_*)."""

from __future__ import annotations

from typing import Any

from ronin_mcp.auth import WriteAuthError, check_write_auth
from ronin_mcp.backends.agent_bus import AgentBusClient


def register(mcp: Any, *, bus: AgentBusClient, auth_state: dict[str, Any]) -> None:
    @mcp.tool()
    def ronin_alias_list(
        kind: str | None = None,
        as_agent_id: str | None = None,
    ) -> dict[str, Any]:
        """List all aliases."""
        params: dict[str, Any] = {}
        if kind:
            params["kind"] = kind
        return bus.get("/v1/aliases", params=params, as_agent_id=as_agent_id)

    @mcp.tool()
    def ronin_alias_resolve(alias: str, as_agent_id: str | None = None) -> dict[str, Any]:
        """Resolve an alias to its agent_id."""
        return bus.get(f"/v1/aliases/{alias}", as_agent_id=as_agent_id)

    @mcp.tool()
    def ronin_alias_register(
        alias: str,
        kind: str,
        agent_id: str,
        as_agent_id: str | None = None,
    ) -> dict[str, Any]:
        """Register an alias (requires gd: prefix or RONIN_PROD_WRITE=1)."""
        try:
            check_write_auth(auth_state, alias)
        except WriteAuthError as exc:
            return exc.as_error_dict()
        return bus.post(
            "/v1/aliases",
            {"alias": alias, "kind": kind, "agent_id": agent_id},
            as_agent_id=as_agent_id,
        )

    @mcp.tool()
    def ronin_alias_rebind(
        alias: str,
        agent_id: str,
        expected_current_agent_id: str,
        as_agent_id: str | None = None,
    ) -> dict[str, Any]:
        """Rebind an alias to a new agent (CAS)."""
        try:
            check_write_auth(auth_state, alias)
        except WriteAuthError as exc:
            return exc.as_error_dict()
        return bus.post(
            f"/v1/aliases/{alias}/rebind",
            {"agent_id": agent_id, "expected_current_agent_id": expected_current_agent_id},
            as_agent_id=as_agent_id,
        )

    @mcp.tool()
    def ronin_agent_list(
        kind: str | None = None,
        as_agent_id: str | None = None,
    ) -> dict[str, Any]:
        """List agents."""
        params: dict[str, Any] = {}
        if kind:
            params["kind"] = kind
        return bus.get("/v1/agents", params=params, as_agent_id=as_agent_id)

    @mcp.tool()
    def ronin_agent_whoami(as_agent_id: str | None = None) -> dict[str, Any]:
        """Return the current delegated identity."""
        return bus.get("/v1/agents/whoami", as_agent_id=as_agent_id)

    @mcp.tool()
    def ronin_agent_register(
        agent_id: str,
        display_name: str,
        kind: str = "agent",
        as_agent_id: str | None = None,
    ) -> dict[str, Any]:
        """Register an agent (requires gd: prefix or RONIN_PROD_WRITE=1)."""
        try:
            check_write_auth(auth_state, agent_id)
        except WriteAuthError as exc:
            return exc.as_error_dict()
        result = bus.post(
            "/v1/agents",
            {"agent_id": agent_id, "display_name": display_name, "kind": kind},
            as_agent_id=as_agent_id,
        )
        if "token" in result:
            del result["token"]
        return result
