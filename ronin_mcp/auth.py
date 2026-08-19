"""Authorization guardrails for Ronin MCP write-surface tools.

Rules (in priority order):
1. Ephemeral mode -> all writes allowed (routed to ephemeral backends).
2. ``gd:`` prefix on the target -> write allowed (test/dev namespace).
3. Production write (non-``gd:``, non-ephemeral) -> requires explicit
   ``RONIN_PROD_WRITE=1`` / ``--prod-write`` authorization.
4. Gate approve/reject always require prod write (B-class irreversible).
"""

from __future__ import annotations

from typing import Any


class WriteAuthError(Exception):
    """Raised when a write-surface tool is not authorized.

    Carries a stable ``code`` and ``message`` matching the spec error model.
    """

    def __init__(self, code: str, message: str, *, http_status: int = 403) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.http_status = http_status
        self.details: dict[str, Any] = {"retryable": False}

    def as_error_dict(self) -> dict[str, Any]:
        return {"code": self.code, "message": self.message, "details": self.details}


def _is_gd(target: str) -> bool:
    return isinstance(target, str) and target.startswith("gd:")


def check_write_auth(
    auth_state: dict[str, Any],
    target: str,
    *,
    prod_write_required: bool = False,
) -> None:
    """Authorize a write-surface call against ``target``.

    ``target`` is the resource identity the write touches (alias, agent_id,
    channel_id, work_folder id, development name, ...). When the operation
    always requires prod write (e.g. gate approve/reject), pass
    ``prod_write_required=True``.
    """
    ephemeral = auth_state.get("ephemeral", False)
    prod_write = auth_state.get("prod_write_enabled", False)

    # Rule 1: ephemeral mode opens the entire write surface.
    if ephemeral:
        return

    # Rule 4: gate / B-class irreversible ops always require prod write,
    # even when the target is gd:-prefixed.
    if prod_write_required:
        if not prod_write:
            raise WriteAuthError(
                "GATE_REQUIRES_PROD_WRITE",
                "Gate approval requires RONIN_PROD_WRITE=1 or --prod-write. "
                "Use gd: prefix for test resources.",
            )
        return

    # Rule 2: gd: prefix is the test/dev namespace -> allowed.
    if _is_gd(target):
        return

    # Rule 3: production write requires explicit authorization.
    if not prod_write:
        raise WriteAuthError(
            "PROD_WRITE_NOT_AUTHORIZED",
            "Production write requires RONIN_PROD_WRITE=1 or --prod-write. "
            "Use gd: prefix for test resources.",
        )
