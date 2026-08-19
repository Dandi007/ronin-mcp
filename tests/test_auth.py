"""Tests for the write-surface authorization guardrails (spec 判据 1)."""

from __future__ import annotations

import pytest

from ronin_mcp.auth import WriteAuthError, check_write_auth


class TestEphemeralMode:
    def test_ephemeral_allows_any_target(self) -> None:
        state = {"ephemeral": True, "prod_write_enabled": False}
        check_write_auth(state, "production-alias")
        check_write_auth(state, "gd:test")
        check_write_auth(state, "anything")

    def test_ephemeral_allows_gate_without_prod_write(self) -> None:
        state = {"ephemeral": True, "prod_write_enabled": False}
        check_write_auth(state, "gd:dev", prod_write_required=True)


class TestGdPrefix:
    def test_gd_prefix_allowed_without_prod_write(self) -> None:
        state = {"ephemeral": False, "prod_write_enabled": False}
        check_write_auth(state, "gd:test-alias")
        check_write_auth(state, "gd:test-bot")
        check_write_auth(state, "gd:test-group")

    def test_gd_prefix_gate_still_requires_prod_write(self) -> None:
        state = {"ephemeral": False, "prod_write_enabled": False}
        with pytest.raises(WriteAuthError) as exc_info:
            check_write_auth(state, "gd:dev", prod_write_required=True)
        assert exc_info.value.code == "GATE_REQUIRES_PROD_WRITE"

    def test_gd_prefix_gate_allowed_with_prod_write(self) -> None:
        state = {"ephemeral": False, "prod_write_enabled": True}
        check_write_auth(state, "gd:dev", prod_write_required=True)


class TestProductionWrite:
    def test_prod_write_rejected_without_auth(self) -> None:
        state = {"ephemeral": False, "prod_write_enabled": False}
        with pytest.raises(WriteAuthError) as exc_info:
            check_write_auth(state, "production-alias")
        assert exc_info.value.code == "PROD_WRITE_NOT_AUTHORIZED"
        assert "RONIN_PROD_WRITE=1" in exc_info.value.message

    def test_prod_write_allowed_with_auth(self) -> None:
        state = {"ephemeral": False, "prod_write_enabled": True}
        check_write_auth(state, "production-alias")

    def test_gate_rejected_without_prod_write(self) -> None:
        state = {"ephemeral": False, "prod_write_enabled": False}
        with pytest.raises(WriteAuthError) as exc_info:
            check_write_auth(state, "production-dev", prod_write_required=True)
        assert exc_info.value.code == "GATE_REQUIRES_PROD_WRITE"


class TestErrorShape:
    def test_error_dict_shape(self) -> None:
        err = WriteAuthError("PROD_WRITE_NOT_AUTHORIZED", "msg")
        d = err.as_error_dict()
        assert d == {
            "code": "PROD_WRITE_NOT_AUTHORIZED",
            "message": "msg",
            "details": {"retryable": False},
        }
        assert err.http_status == 403
