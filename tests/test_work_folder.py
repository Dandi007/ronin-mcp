"""Tests for the work-folder facet (ronin_wf_* / ronin_fs_*)."""

from __future__ import annotations

import asyncio

import pytest

from tests.conftest import _make_server


def _call(mcp, name: str, args: dict) -> dict:
    result = asyncio.run(mcp.call_tool(name, args))
    sc = result.structured_content
    if sc is not None:
        return sc if isinstance(sc, dict) else {"result": sc}
    return {"text": result.content[0].text if result.content else ""}


class TestWfGuardrails:
    def test_gd_create_proceeds(self, fake_wf) -> None:
        mcp = _make_server(wf=fake_wf)
        out = _call(mcp, "ronin_wf_create", {"topic": "gd:test", "idempotency_key": "ik"})
        assert out.get("ok") is True
        name, args = fake_wf.calls[-1]
        assert name == "wf_create"
        assert args == {"topic": "gd:test", "idempotency_key": "ik"}

    def test_prod_create_rejected(self, fake_wf) -> None:
        mcp = _make_server(wf=fake_wf)
        out = _call(mcp, "ronin_wf_create", {"topic": "production"})
        assert out["code"] == "PROD_WRITE_NOT_AUTHORIZED"
        assert fake_wf.calls == []

    def test_gd_save_proceeds(self, fake_wf) -> None:
        mcp = _make_server(wf=fake_wf)
        out = _call(mcp, "ronin_wf_save", {"folder_id": "gd:f1", "summary": "s"})
        assert out.get("ok") is True
        name, args = fake_wf.calls[-1]
        assert name == "wf_save"
        assert args["folder_id"] == "gd:f1"

    def test_prod_save_rejected(self, fake_wf) -> None:
        mcp = _make_server(wf=fake_wf)
        out = _call(mcp, "ronin_wf_save", {"folder_id": "prod-f1"})
        assert out["code"] == "PROD_WRITE_NOT_AUTHORIZED"

    def test_gd_evidence_put(self, fake_wf) -> None:
        mcp = _make_server(wf=fake_wf)
        out = _call(mcp, "ronin_wf_evidence_put", {
            "folder_id": "gd:f1", "filename": "ev.txt", "content": "data",
        })
        assert out.get("ok") is True
        name, args = fake_wf.calls[-1]
        assert name == "wf_evidence_put"
        assert args["content"] == "data"

    def test_gd_fs_create(self, fake_wf) -> None:
        mcp = _make_server(wf=fake_wf)
        out = _call(mcp, "ronin_fs_create", {
            "folder_id": "gd:f1", "filename": "a.txt", "content": "x",
        })
        assert out.get("ok") is True
        name, args = fake_wf.calls[-1]
        assert name == "fs_create"

    def test_prod_fs_write_rejected(self, fake_wf) -> None:
        mcp = _make_server(wf=fake_wf)
        out = _call(mcp, "ronin_fs_write", {
            "folder_id": "prod-f1", "filename": "a.txt", "content": "x",
        })
        assert out["code"] == "PROD_WRITE_NOT_AUTHORIZED"

    def test_gd_fs_edit(self, fake_wf) -> None:
        mcp = _make_server(wf=fake_wf)
        _call(mcp, "ronin_fs_edit", {
            "folder_id": "gd:f1", "filename": "a.txt",
            "old_string": "x", "new_string": "y",
        })
        name, args = fake_wf.calls[-1]
        assert name == "fs_edit"
        assert args["replace_all"] is False

    def test_gd_fs_batch(self, fake_wf) -> None:
        mcp = _make_server(wf=fake_wf)
        _call(mcp, "ronin_fs_batch", {
            "folder_id": "gd:f1", "operations": [{"op": "x"}],
        })
        name, args = fake_wf.calls[-1]
        assert name == "fs_batch"
        assert args["operations"] == [{"op": "x"}]


class TestWfReadTools:
    def test_wf_list(self, fake_wf) -> None:
        mcp = _make_server(wf=fake_wf)
        _call(mcp, "ronin_wf_list", {"limit": 5})
        name, args = fake_wf.calls[-1]
        assert name == "wf_list"
        assert args == {"limit": 5}

    def test_wf_search(self, fake_wf) -> None:
        mcp = _make_server(wf=fake_wf)
        _call(mcp, "ronin_wf_search", {"query": "q", "top_k": 3})
        name, args = fake_wf.calls[-1]
        assert args == {"query": "q", "top_k": 3}

    def test_fs_read(self, fake_wf) -> None:
        mcp = _make_server(wf=fake_wf)
        _call(mcp, "ronin_fs_read", {"folder_id": "gd:f1", "filename": "a.txt", "limit": 10})
        name, args = fake_wf.calls[-1]
        assert name == "fs_read"
        assert args["limit"] == 10

    def test_fs_capabilities(self, fake_wf) -> None:
        mcp = _make_server(wf=fake_wf)
        _call(mcp, "ronin_fs_capabilities", {})
        name, args = fake_wf.calls[-1]
        assert name == "fs_capabilities"
        assert args == {}

    def test_fs_resolve(self, fake_wf) -> None:
        mcp = _make_server(wf=fake_wf)
        _call(mcp, "ronin_fs_resolve", {"folder_id": "gd:f1"})
        name, args = fake_wf.calls[-1]
        assert name == "fs_resolve"
        assert args == {"folder_id": "gd:f1"}

    def test_wf_resume(self, fake_wf) -> None:
        mcp = _make_server(wf=fake_wf)
        _call(mcp, "ronin_wf_resume", {"folder_id": "gd:f1"})
        name, args = fake_wf.calls[-1]
        assert name == "wf_resume"

    def test_fs_copy_checks_dest(self, fake_wf) -> None:
        mcp = _make_server(wf=fake_wf)
        out = _call(mcp, "ronin_fs_copy", {
            "source_folder_id": "gd:f1", "source_filename": "a",
            "dest_folder_id": "prod-f2", "dest_filename": "b",
        })
        assert out["code"] == "PROD_WRITE_NOT_AUTHORIZED"

    def test_gd_fs_copy_proceeds(self, fake_wf) -> None:
        mcp = _make_server(wf=fake_wf)
        out = _call(mcp, "ronin_fs_copy", {
            "source_folder_id": "gd:f1", "source_filename": "a",
            "dest_folder_id": "gd:f2", "dest_filename": "b",
        })
        assert out.get("ok") is True
