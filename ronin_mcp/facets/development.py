"""Development (dd dispatch) facet.

This facet is retired. The tools stay registered (visible and callable
in ``tools/list``) but every invocation is refused with an explicit,
structured ``RETIRED`` rejection (see ``ronin_mcp.disposition``). The dd
dispatch lifecycle is no longer owned by ronin-mcp; retiring it quietly
by dropping the tools would leave callers hitting ``Unknown tool``, and
keeping the backend path would leave it failing like an operational
fault — neither is acceptable, so the entrance returns ``RETIRED``.
"""

from __future__ import annotations

from typing import Any

from ronin_mcp.auth import AuthState
from ronin_mcp.backends.dev_dispatch import DevDispatchClient
from ronin_mcp.disposition import retire


def register(
    mcp: Any,
    auth: AuthState,
    controller: DevDispatchClient,
    error_wrapper: Any,
) -> None:
    """Register the (retired) ronin_dev_* tools on the FastMCP server.

    Registration is preserved so the tools remain visible; invocation
    returns a structured ``RETIRED`` rejection.
    """

    @mcp.tool()
    def ronin_dev_list(
        state: str | None = None,
        repo: str | None = None,
        limit: int = 20,
        cursor: str | None = None,
    ) -> dict[str, Any]:
        """List developments (read) — retired."""
        return error_wrapper(lambda: retire("ronin_dev_list"))

    @mcp.tool()
    def ronin_dev_get(development_id: str) -> dict[str, Any]:
        """Get a development's full state (read) — retired."""
        return error_wrapper(lambda: retire("ronin_dev_get"))

    @mcp.tool()
    def ronin_dev_events(
        development_id: str,
        after: str | None = None,
        limit: int = 100,
    ) -> dict[str, Any]:
        """Get development events (read; incremental polling) — retired."""
        return error_wrapper(lambda: retire("ronin_dev_events"))

    @mcp.tool()
    def ronin_dev_evidence(development_id: str) -> dict[str, Any]:
        """Export the receipt/evidence chain (read) — retired."""
        return error_wrapper(lambda: retire("ronin_dev_evidence"))

    @mcp.tool()
    def ronin_dev_create(
        name: str,
        goal: str,
        idempotency_key: str,
        reason: str,
        initial_handoff: dict[str, Any],
        phase: str = "development",
        acceptance_commands: list[dict[str, Any]] | None = None,
        setup_commands: list[dict[str, Any]] | None = None,
        host_verify_commands: list[dict[str, Any]] | None = None,
        profile: str = "default",
        policy: str = "isolated-release-auto",
        work_folder: str | None = None,
        role_target_patch: dict[str, Any] | None = None,
        auto_start: bool = False,
        max_attempts: int | None = None,
        as_agent_id: str | None = None,
    ) -> dict[str, Any]:
        """Create a attempt-context v1 development (write) — retired."""
        return error_wrapper(lambda: retire("ronin_dev_create"))

    @mcp.tool()
    def ronin_dev_start(
        development_id: str,
        idempotency_key: str,
        expected_revision: int,
        reason: str = "",
        as_agent_id: str | None = None,
    ) -> dict[str, Any]:
        """Start a BOOTSTRAPPING development (write) — retired."""
        return error_wrapper(lambda: retire("ronin_dev_start"))

    @mcp.tool()
    def ronin_dev_steer(
        development_id: str,
        instruction: str,
        idempotency_key: str,
        expected_revision: int,
        reason: str = "",
        urgency: str = "next_safe_boundary",
        as_agent_id: str | None = None,
    ) -> dict[str, Any]:
        """Steer a development (write) — retired."""
        return error_wrapper(lambda: retire("ronin_dev_steer"))

    @mcp.tool()
    def ronin_dev_reconfigure(
        development_id: str,
        idempotency_key: str,
        expected_revision: int,
        reason: str = "",
        profile: str | None = None,
        role_target_patch: dict[str, Any] | None = None,
        policy: str | None = None,
        acceptance_commands: list[dict[str, Any]] | None = None,
        setup_commands: list[dict[str, Any]] | None = None,
        as_agent_id: str | None = None,
    ) -> dict[str, Any]:
        """Reconfigure a development (write) — retired."""
        return error_wrapper(lambda: retire("ronin_dev_reconfigure"))

    @mcp.tool()
    def ronin_dev_control(
        development_id: str,
        action: str,
        idempotency_key: str,
        expected_revision: int,
        reason: str = "",
        as_agent_id: str | None = None,
    ) -> dict[str, Any]:
        """Pause / resume / cancel a development (write) — retired."""
        return error_wrapper(lambda: retire("ronin_dev_control"))

    @mcp.tool()
    def ronin_dev_relock(
        development_id: str,
        plugin_commit: str,
        idempotency_key: str,
        expected_revision: int,
        reason: str = "",
        as_agent_id: str | None = None,
    ) -> dict[str, Any]:
        """Relock a development to a new plugin commit (write) — retired."""
        return error_wrapper(lambda: retire("ronin_dev_relock"))