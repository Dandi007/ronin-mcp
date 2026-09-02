"""Chatgroup facet.

agent-bus has no native chatgroup table; this facet composes fanout
channels with the `chatgroup:` prefix convention. Members are managed
through channel subscribe/unsubscribe. The composition is hidden
behind ronin_chatgroup_* so callers see a chatgroup-shaped surface.

The caller passes a logical channel_id (e.g. `gd:test-group`); the
facet maps it to the agent-bus channel id `chatgroup:{channel_id}`
so the stored channel matches the `chatgroup:` prefix filter used by
ronin_chatgroup_list. The gd: auth check runs on the logical channel_id
the caller supplied, not the internal agent-bus id.
"""

from __future__ import annotations

from typing import Any

from ronin_mcp.auth import AuthState, check_write_auth
from ronin_mcp.backends.agent_bus import AgentBusClient

CHATGROUP_PREFIX = "chatgroup:"


def _bus_channel_id(channel_id: str) -> str:
    """Map a logical chatgroup id to the agent-bus channel id."""
    if channel_id.startswith(CHATGROUP_PREFIX):
        return channel_id
    return f"{CHATGROUP_PREFIX}{channel_id}"


def _auth_target(channel_id: str) -> str:
    """The logical chatgroup name used for gd: prefix auth checks.

    The caller supplies either a bare name (`gd:test-group`) or the
    full agent-bus channel id (`chatgroup:gd:test-group`); in both
    cases the gd: check runs against the logical name with the
    `chatgroup:` prefix stripped.
    """
    if channel_id.startswith(CHATGROUP_PREFIX):
        return channel_id[len(CHATGROUP_PREFIX):]
    return channel_id


def register(
    mcp: Any,
    auth: AuthState,
    bus: AgentBusClient,
    error_wrapper: Any,
) -> None:
    """Register ronin_chatgroup_* tools on the FastMCP server."""

    @mcp.tool()
    def ronin_chatgroup_create(
        channel_id: str,
        display_name: str | None = None,
        members: list[str] | None = None,
        as_agent_id: str | None = None,
    ) -> dict[str, Any]:
        """Create a chatgroup (write; requires gd: prefix or RONIN_PROD_WRITE=1).

        Backed by a fanout channel named `chatgroup:<channel_id>` with
        visibility='public'. Optional members are subscribed after
        channel creation.
        """
        def _do() -> dict[str, Any]:
            check_write_auth(auth, _auth_target(channel_id))
            bus_channel = _bus_channel_id(channel_id)
            result = bus.post(
                "/v1/channels",
                {
                    "channel_id": bus_channel,
                    "delivery_mode": "fanout",
                    "visibility": "public",
                    **({"metadata": {"display_name": display_name}} if display_name else {}),
                },
                as_agent_id=as_agent_id,
            )
            joined: list[str] = []
            for member in members or []:
                bus.post(
                    f"/v1/channels/{bus_channel}/subscribe",
                    {},
                    as_agent_id=member,
                )
                joined.append(member)
            if joined:
                result["members"] = joined
            result["channel_id"] = channel_id
            return result
        return error_wrapper(_do)

    @mcp.tool()
    def ronin_chatgroup_list(
        prefix: str | None = None,
        as_agent_id: str | None = None,
    ) -> dict[str, Any]:
        """List chatgroups (read; filters channels with `chatgroup:` prefix)."""
        effective_prefix = prefix or CHATGROUP_PREFIX
        params: dict[str, Any] = {"prefix": effective_prefix}
        return error_wrapper(
            lambda: bus.get("/v1/channels", params=params, as_agent_id=as_agent_id)
        )

    @mcp.tool()
    def ronin_chatgroup_get(
        channel_id: str,
        as_agent_id: str | None = None,
    ) -> dict[str, Any]:
        """Get chatgroup details (read)."""
        bus_channel = _bus_channel_id(channel_id)
        return error_wrapper(
            lambda: bus.get(f"/v1/channels/{bus_channel}", as_agent_id=as_agent_id)
        )

    @mcp.tool()
    def ronin_chatgroup_add_member(
        channel_id: str,
        agent_id: str,
        as_agent_id: str | None = None,
    ) -> dict[str, Any]:
        """Add a member (write; requires gd: prefix or RONIN_PROD_WRITE=1)."""
        def _do() -> dict[str, Any]:
            check_write_auth(auth, _auth_target(channel_id))
            bus_channel = _bus_channel_id(channel_id)
            return bus.post(
                f"/v1/channels/{bus_channel}/subscribe",
                {},
                as_agent_id=agent_id,
            )
        return error_wrapper(_do)

    @mcp.tool()
    def ronin_chatgroup_remove_member(
        channel_id: str,
        agent_id: str,
        as_agent_id: str | None = None,
    ) -> dict[str, Any]:
        """Remove a member (write; requires gd: prefix or RONIN_PROD_WRITE=1)."""
        def _do() -> dict[str, Any]:
            check_write_auth(auth, _auth_target(channel_id))
            bus_channel = _bus_channel_id(channel_id)
            return bus.delete(
                f"/v1/channels/{bus_channel}/subscribe",
                as_agent_id=agent_id,
            )
        return error_wrapper(_do)

    @mcp.tool()
    def ronin_chatgroup_send(
        channel_id: str,
        payload: dict[str, Any],
        idempotency_key: str,
        as_agent_id: str | None = None,
    ) -> dict[str, Any]:
        """Broadcast to a chatgroup (write; requires gd: prefix or RONIN_PROD_WRITE=1)."""
        def _do() -> dict[str, Any]:
            check_write_auth(auth, _auth_target(channel_id))
            bus_channel = _bus_channel_id(channel_id)
            return bus.post(
                f"/v1/channels/{bus_channel}/publish",
                {
                    "kind": "agent.msg.v1",
                    "payload": payload,
                    "idempotency_key": idempotency_key,
                },
                as_agent_id=as_agent_id,
            )
        return error_wrapper(_do)
