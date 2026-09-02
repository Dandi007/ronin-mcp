"""Gate-approval facet (B-class irreversible operations) — retired.

The gate approval tools stay registered (visible and callable in
``tools/list``) but every invocation is refused with a structured
``RETIRED`` rejection (see ``ronin_mcp.disposition``). Gate approval is
no longer owned by ronin-mcp; dropping the tools would surface
``Unknown tool`` and keeping the backend path would surface it as an
operational fault, so the entrance returns ``RETIRED`` instead.
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
    """Register the (retired) ronin_gate_* tools on the FastMCP server."""

    @mcp.tool()
    def ronin_gate_approve(
        development_id: str,
        gate_id: str,
        idempotency_key: str,
        expected_revision: int,
        operator_identity: str,
        reason: str = "",
    ) -> dict[str, Any]:
        """Approve a gate (write; ALWAYS requires RONIN_PROD_WRITE=1) — retired."""
        return error_wrapper(lambda: retire("ronin_gate_approve"))

    @mcp.tool()
    def ronin_gate_reject(
        development_id: str,
        gate_id: str,
        idempotency_key: str,
        expected_revision: int,
        operator_identity: str,
        reason: str = "",
    ) -> dict[str, Any]:
        """Reject a gate (write; ALWAYS requires RONIN_PROD_WRITE=1) — retired."""
        return error_wrapper(lambda: retire("ronin_gate_reject"))