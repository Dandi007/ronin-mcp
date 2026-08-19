"""Messaging facet (single-send / broadcast / inbox).

ronin_msg_send publishes to the agent:{alias} channel.
ronin_msg_broadcast always requires prod write (broadcasts to all
online human principals).
ronin_inbox_consume is a write (side-effect: claims messages under
lease) but ack/nack/renew are not guarded (they operate on already-
claimed deliveries).
"""

from __future__ import annotations

from typing import Any

from ronin_mcp.auth import AuthState, check_write_auth
from ronin_mcp.backends.agent_bus import AgentBusClient


def register(
    mcp: Any,
    auth: AuthState,
    bus: AgentBusClient,
    error_wrapper: Any,
) -> None:
    """Register ronin_msg_* and ronin_inbox_* tools on the FastMCP server."""

    @mcp.tool()
    def ronin_msg_send(
        alias: str,
        payload: dict[str, Any],
        idempotency_key: str,
        from_alias: str | None = None,
        as_agent_id: str | None = None,
    ) -> dict[str, Any]:
        """Send agent.msg.v1 to an alias (write; gd: prefix or RONIN_PROD_WRITE=1)."""
        def _do() -> dict[str, Any]:
            check_write_auth(auth, alias)
            body: dict[str, Any] = {
                "kind": "agent.msg.v1",
                "payload": payload,
                "idempotency_key": idempotency_key,
            }
            if from_alias:
                body["from_alias"] = from_alias
            return bus.post(
                f"/v1/channels/agent:{alias}/publish",
                body,
                as_agent_id=as_agent_id,
            )
        return error_wrapper(_do)

    @mcp.tool()
    def ronin_msg_broadcast(
        payload: dict[str, Any],
        idempotency_key: str,
        as_agent_id: str | None = None,
    ) -> dict[str, Any]:
        """Broadcast to online human principals (write; ALWAYS requires RONIN_PROD_WRITE=1)."""
        def _do() -> dict[str, Any]:
            check_write_auth(auth, "broadcast", prod_write_required=True)
            return bus.post(
                "/v1/broadcast",
                {"payload": payload, "idempotency_key": idempotency_key},
                as_agent_id=as_agent_id,
            )
        return error_wrapper(_do)

    @mcp.tool()
    def ronin_inbox_consume(
        alias: str | None = None,
        max_messages: int = 100,
        lease_ms: int | None = None,
        as_agent_id: str | None = None,
    ) -> dict[str, Any]:
        """Consume an inbox (write; side-effect: claims messages under lease).

        The alias (or as_agent_id when alias is None) is the auth target.
        """
        def _do() -> dict[str, Any]:
            target = alias or as_agent_id or ""
            check_write_auth(auth, target)
            effective_alias = alias or (as_agent_id or "")
            body: dict[str, Any] = {"max_messages": max_messages}
            if lease_ms:
                body["lease_ms"] = lease_ms
            return bus.post(
                f"/v1/channels/agent:{effective_alias}/consume",
                body,
                as_agent_id=as_agent_id,
            )
        return error_wrapper(_do)

    @mcp.tool()
    def ronin_inbox_ack(
        delivery_id: str,
        lease_token: str,
        result: dict[str, Any] | None = None,
        as_agent_id: str | None = None,
    ) -> dict[str, Any]:
        """Ack a delivery (write; not guarded — operates on own claim)."""
        body: dict[str, Any] = {"lease_token": lease_token}
        if result:
            body["result"] = result
        return error_wrapper(
            lambda: bus.post(
                f"/v1/deliveries/{delivery_id}/ack",
                body,
                as_agent_id=as_agent_id,
            )
        )

    @mcp.tool()
    def ronin_inbox_nack(
        delivery_id: str,
        lease_token: str,
        reason: str = "",
        retry_in_ms: int = 0,
        as_agent_id: str | None = None,
    ) -> dict[str, Any]:
        """Nack a delivery (write; not guarded)."""
        return error_wrapper(
            lambda: bus.post(
                f"/v1/deliveries/{delivery_id}/nack",
                {
                    "lease_token": lease_token,
                    "reason": reason,
                    "retry_in_ms": retry_in_ms,
                },
                as_agent_id=as_agent_id,
            )
        )

    @mcp.tool()
    def ronin_inbox_renew(
        delivery_id: str,
        lease_token: str,
        lease_ms: int | None = None,
        as_agent_id: str | None = None,
    ) -> dict[str, Any]:
        """Renew a lease (write; not guarded)."""
        body: dict[str, Any] = {"lease_token": lease_token}
        if lease_ms:
            body["lease_ms"] = lease_ms
        return error_wrapper(
            lambda: bus.post(
                f"/v1/deliveries/{delivery_id}/renew",
                body,
                as_agent_id=as_agent_id,
            )
        )

    @mcp.tool()
    def ronin_msg_read(
        channel_id: str,
        after_seq: int = 0,
        kind: str | None = None,
        limit: int = 100,
        as_agent_id: str | None = None,
    ) -> dict[str, Any]:
        """Read channel message history (read)."""
        params: dict[str, Any] = {"after_seq": after_seq, "limit": limit}
        if kind:
            params["kind"] = kind
        return error_wrapper(
            lambda: bus.get(
                f"/v1/channels/{channel_id}/messages",
                params=params,
                as_agent_id=as_agent_id,
            )
        )

    @mcp.tool()
    def ronin_msg_events(
        after: int = 0,
        channel_id: str | None = None,
        limit: int = 100,
        as_agent_id: str | None = None,
    ) -> dict[str, Any]:
        """Read bus event stream (read)."""
        params: dict[str, Any] = {"after": after, "limit": limit}
        if channel_id:
            params["channel_id"] = channel_id
        return error_wrapper(
            lambda: bus.get("/v1/events", params=params, as_agent_id=as_agent_id)
        )
