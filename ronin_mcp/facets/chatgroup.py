"""Facet 2: Chatgroup (ronin_chatgroup_*).

Implemented as fanout channels with the ``chatgroup:`` prefix, per the spec
naming convention. Member add/remove maps to subscribe/unsubscribe. The
``gd:`` authorization check applies to the user-provided ``channel_id``
(test/dev namespace), before the ``chatgroup:`` bus prefix is applied.
"""

from __future__ import annotations

from typing import Any

from ronin_mcp.auth import WriteAuthError, check_write_auth
from ronin_mcp.backends.agent_bus import AgentBusClient

_CHATGROUP_PREFIX = "chatgroup:"


def _full_channel_id(channel_id: str) -> str:
    if channel_id.startswith(_CHATGROUP_PREFIX):
        return channel_id
    return f"{_CHATGROUP_PREFIX}{channel_id}"


def register(mcp: Any, *, bus: AgentBusClient, auth_state: dict[str, Any]) -> None:
    @mcp.tool()
    def ronin_chatgroup_create(
        channel_id: str,
        display_name: str | None = None,
        members: list[str] | None = None,
        as_agent_id: str | None = None,
    ) -> dict[str, Any]:
        """Create a chatgroup (requires gd: prefix or RONIN_PROD_WRITE=1)."""
        try:
            check_write_auth(auth_state, channel_id)
        except WriteAuthError as exc:
            return exc.as_error_dict()
        full = _full_channel_id(channel_id)
        metadata: dict[str, Any] = {}
        if display_name:
            metadata["display_name"] = display_name
        result = bus.post(
            "/v1/channels",
            {
                "channel_id": full,
                "delivery_mode": "fanout",
                "visibility": "public",
                "metadata": metadata,
            },
            as_agent_id=as_agent_id,
        )
        for member in members or []:
            bus.post(
                f"/v1/channels/{full}/subscribe",
                {},
                as_agent_id=member or as_agent_id,
            )
        return result

    @mcp.tool()
    def ronin_chatgroup_list(
        prefix: str | None = None,
        as_agent_id: str | None = None,
    ) -> dict[str, Any]:
        """List chatgroups (filters chatgroup: prefix channels)."""
        params: dict[str, Any] = {"prefix": prefix or _CHATGROUP_PREFIX}
        return bus.get("/v1/channels", params=params, as_agent_id=as_agent_id)

    @mcp.tool()
    def ronin_chatgroup_get(
        channel_id: str,
        as_agent_id: str | None = None,
    ) -> dict[str, Any]:
        """Get chatgroup details."""
        full = _full_channel_id(channel_id)
        return bus.get(f"/v1/channels/{full}", as_agent_id=as_agent_id)

    @mcp.tool()
    def ronin_chatgroup_add_member(
        channel_id: str,
        agent_id: str,
        as_agent_id: str | None = None,
    ) -> dict[str, Any]:
        """Add a member (requires gd: prefix or RONIN_PROD_WRITE=1)."""
        try:
            check_write_auth(auth_state, channel_id)
        except WriteAuthError as exc:
            return exc.as_error_dict()
        full = _full_channel_id(channel_id)
        return bus.post(
            f"/v1/channels/{full}/subscribe",
            {},
            as_agent_id=agent_id or as_agent_id,
        )

    @mcp.tool()
    def ronin_chatgroup_remove_member(
        channel_id: str,
        agent_id: str,
        as_agent_id: str | None = None,
    ) -> dict[str, Any]:
        """Remove a member (requires gd: prefix or RONIN_PROD_WRITE=1)."""
        try:
            check_write_auth(auth_state, channel_id)
        except WriteAuthError as exc:
            return exc.as_error_dict()
        full = _full_channel_id(channel_id)
        return bus.delete(
            f"/v1/channels/{full}/subscribe",
            as_agent_id=agent_id or as_agent_id,
        )

    @mcp.tool()
    def ronin_chatgroup_send(
        channel_id: str,
        payload: dict[str, Any],
        idempotency_key: str,
        as_agent_id: str | None = None,
    ) -> dict[str, Any]:
        """Broadcast a message to a chatgroup (requires gd: or RONIN_PROD_WRITE=1)."""
        try:
            check_write_auth(auth_state, channel_id)
        except WriteAuthError as exc:
            return exc.as_error_dict()
        full = _full_channel_id(channel_id)
        return bus.post(
            f"/v1/channels/{full}/publish",
            {"kind": "message", "payload": payload, "idempotency_key": idempotency_key},
            as_agent_id=as_agent_id,
        )
