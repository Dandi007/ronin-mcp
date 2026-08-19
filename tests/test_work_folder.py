"""Work-folder facet (spec §面 5).

Exercises ronin_wf_* and ronin_fs_* against the FakeWorkFolderClient.
The fake records calls so tests can assert the facet forwarded the
right arguments to the work-folder MCP backend.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError


def _extract_text(result: Any) -> str:
    if hasattr(result, "content") and result.content:
        return result.content[0].text
    if hasattr(result, "text"):
        return result.text
    return str(result)


def _call(server: Any, tool: str, args: dict[str, Any]) -> dict[str, Any]:
    async def _run() -> dict[str, Any]:
        async with Client(server) as client:
            result = await client.call_tool(tool, args)
            return json.loads(_extract_text(result))
    return asyncio.run(_run())


@pytest.mark.timeout(30)
def test_wf_list(mcp_server_factory: Any, make_config: Any, fake_work_folder: Any) -> None:
    """wf_list calls the work-folder backend."""
    server = mcp_server_factory(make_config())
    _call(server, "ronin_wf_list", {"limit": 5})
    calls = [c for c in fake_work_folder.calls if c[0] == "wf_list"]
    assert len(calls) == 1
    assert calls[0][1]["limit"] == 5


@pytest.mark.timeout(30)
def test_wf_create_gd(mcp_server_factory: Any, make_config: Any, fake_work_folder: Any) -> None:
    """gd: wf_create is allowed without prod write."""
    server = mcp_server_factory(make_config())
    _call(server, "ronin_wf_create", {"topic": "gd:test-folder"})
    calls = [c for c in fake_work_folder.calls if c[0] == "wf_create"]
    assert len(calls) == 1
    assert calls[0][1]["topic"] == "gd:test-folder"


@pytest.mark.timeout(30)
def test_wf_create_rejected_non_gd(mcp_server_factory: Any, make_config: Any) -> None:
    """Non-gd: wf_create is rejected without prod write."""
    server = mcp_server_factory(make_config())

    async def _run() -> None:
        async with Client(server) as client:
            with pytest.raises(ToolError) as exc:
                await client.call_tool("ronin_wf_create", {"topic": "prod-folder"})
            assert "PROD_WRITE_NOT_AUTHORIZED" in str(exc.value)

    asyncio.run(_run())


@pytest.mark.timeout(30)
def test_wf_resume(mcp_server_factory: Any, make_config: Any, fake_work_folder: Any) -> None:
    """wf_resume calls the backend."""
    server = mcp_server_factory(make_config())
    _call(server, "ronin_wf_resume", {"folder_id": "gd:resume-folder"})
    calls = [c for c in fake_work_folder.calls if c[0] == "wf_resume"]
    assert len(calls) == 1
    assert calls[0][1]["folder_id"] == "gd:resume-folder"


@pytest.mark.timeout(30)
def test_wf_save_gd(mcp_server_factory: Any, make_config: Any, fake_work_folder: Any) -> None:
    """gd: wf_save is allowed."""
    server = mcp_server_factory(make_config())
    _call(server, "ronin_wf_save", {
        "folder_id": "gd:save-folder", "summary": "checkpoint",
    })
    calls = [c for c in fake_work_folder.calls if c[0] == "wf_save"]
    assert len(calls) == 1
    assert calls[0][1]["folder_id"] == "gd:save-folder"


@pytest.mark.timeout(30)
def test_wf_search(mcp_server_factory: Any, make_config: Any, fake_work_folder: Any) -> None:
    """wf_search is a read and calls the backend."""
    server = mcp_server_factory(make_config())
    _call(server, "ronin_wf_search", {"query": "test", "top_k": 3})
    calls = [c for c in fake_work_folder.calls if c[0] == "wf_search"]
    assert len(calls) == 1
    assert calls[0][1]["query"] == "test"


@pytest.mark.timeout(30)
def test_fs_list(mcp_server_factory: Any, make_config: Any, fake_work_folder: Any) -> None:
    """fs_list is a read."""
    server = mcp_server_factory(make_config())
    _call(server, "ronin_fs_list", {"folder_id": "gd:fs-folder", "dirname": "sub"})
    calls = [c for c in fake_work_folder.calls if c[0] == "fs_list"]
    assert len(calls) == 1
    assert calls[0][1]["folder_id"] == "gd:fs-folder"


@pytest.mark.timeout(30)
def test_fs_read(mcp_server_factory: Any, make_config: Any, fake_work_folder: Any) -> None:
    """fs_read is a read."""
    server = mcp_server_factory(make_config())
    _call(server, "ronin_fs_read", {"folder_id": "gd:read-folder", "filename": "file.txt"})
    calls = [c for c in fake_work_folder.calls if c[0] == "fs_read"]
    assert len(calls) == 1


@pytest.mark.timeout(30)
def test_fs_read_bytes(mcp_server_factory: Any, make_config: Any, fake_work_folder: Any) -> None:
    """fs_read_bytes is a read."""
    server = mcp_server_factory(make_config())
    _call(server, "ronin_fs_read_bytes", {"folder_id": "gd:rb-folder", "filename": "bin"})
    calls = [c for c in fake_work_folder.calls if c[0] == "fs_read_bytes"]
    assert len(calls) == 1


@pytest.mark.timeout(30)
def test_fs_stat(mcp_server_factory: Any, make_config: Any, fake_work_folder: Any) -> None:
    """fs_stat is a read."""
    server = mcp_server_factory(make_config())
    _call(server, "ronin_fs_stat", {"folder_id": "gd:stat-folder", "filename": "f"})
    calls = [c for c in fake_work_folder.calls if c[0] == "fs_stat"]
    assert len(calls) == 1


@pytest.mark.timeout(30)
def test_fs_resolve(mcp_server_factory: Any, make_config: Any, fake_work_folder: Any) -> None:
    """fs_resolve is a read."""
    server = mcp_server_factory(make_config())
    _call(server, "ronin_fs_resolve", {"folder_id": "gd:resolve-folder"})
    calls = [c for c in fake_work_folder.calls if c[0] == "fs_resolve"]
    assert len(calls) == 1


@pytest.mark.timeout(30)
def test_fs_create_gd(mcp_server_factory: Any, make_config: Any, fake_work_folder: Any) -> None:
    """gd: fs_create is allowed."""
    server = mcp_server_factory(make_config())
    _call(server, "ronin_fs_create", {
        "folder_id": "gd:create-folder", "filename": "new.txt", "content": "hi",
    })
    calls = [c for c in fake_work_folder.calls if c[0] == "fs_create"]
    assert len(calls) == 1


@pytest.mark.timeout(30)
def test_fs_write_gd(mcp_server_factory: Any, make_config: Any, fake_work_folder: Any) -> None:
    """gd: fs_write is allowed."""
    server = mcp_server_factory(make_config())
    _call(server, "ronin_fs_write", {
        "folder_id": "gd:write-folder", "filename": "w.txt", "content": "data",
    })
    calls = [c for c in fake_work_folder.calls if c[0] == "fs_write"]
    assert len(calls) == 1


@pytest.mark.timeout(30)
def test_fs_edit_gd(mcp_server_factory: Any, make_config: Any, fake_work_folder: Any) -> None:
    """gd: fs_edit is allowed."""
    server = mcp_server_factory(make_config())
    _call(server, "ronin_fs_edit", {
        "folder_id": "gd:edit-folder", "filename": "e.txt",
        "old_string": "a", "new_string": "b",
    })
    calls = [c for c in fake_work_folder.calls if c[0] == "fs_edit"]
    assert len(calls) == 1


@pytest.mark.timeout(30)
def test_fs_delete_gd(mcp_server_factory: Any, make_config: Any, fake_work_folder: Any) -> None:
    """gd: fs_delete is allowed."""
    server = mcp_server_factory(make_config())
    _call(server, "ronin_fs_delete", {
        "folder_id": "gd:del-folder", "filename": "d.txt",
    })
    calls = [c for c in fake_work_folder.calls if c[0] == "fs_delete"]
    assert len(calls) == 1


@pytest.mark.timeout(30)
def test_fs_copy_gd(mcp_server_factory: Any, make_config: Any, fake_work_folder: Any) -> None:
    """gd: fs_copy is allowed (auth on dest_folder_id)."""
    server = mcp_server_factory(make_config())
    _call(server, "ronin_fs_copy", {
        "source_folder_id": "gd:src", "source_filename": "s.txt",
        "dest_folder_id": "gd:dst", "dest_filename": "d.txt",
    })
    calls = [c for c in fake_work_folder.calls if c[0] == "fs_copy"]
    assert len(calls) == 1


@pytest.mark.timeout(30)
def test_fs_rename_gd(mcp_server_factory: Any, make_config: Any, fake_work_folder: Any) -> None:
    """gd: fs_rename is allowed (auth on dest_folder_id)."""
    server = mcp_server_factory(make_config())
    _call(server, "ronin_fs_rename", {
        "source_folder_id": "gd:src-r", "source_filename": "s.txt",
        "dest_folder_id": "gd:dst-r", "dest_filename": "d.txt",
    })
    calls = [c for c in fake_work_folder.calls if c[0] == "fs_rename"]
    assert len(calls) == 1


@pytest.mark.timeout(30)
def test_fs_batch_gd(mcp_server_factory: Any, make_config: Any, fake_work_folder: Any) -> None:
    """gd: fs_batch is allowed."""
    server = mcp_server_factory(make_config())
    _call(server, "ronin_fs_batch", {
        "folder_id": "gd:batch-folder",
        "operations": [{"op": "create", "filename": "a.txt", "content": "x"}],
    })
    calls = [c for c in fake_work_folder.calls if c[0] == "fs_batch"]
    assert len(calls) == 1


@pytest.mark.timeout(30)
def test_fs_capabilities(mcp_server_factory: Any, make_config: Any, fake_work_folder: Any) -> None:
    """fs_capabilities is a read."""
    server = mcp_server_factory(make_config())
    _call(server, "ronin_fs_capabilities", {})
    calls = [c for c in fake_work_folder.calls if c[0] == "fs_capabilities"]
    assert len(calls) == 1


@pytest.mark.timeout(30)
def test_wf_evidence_put_gd(mcp_server_factory: Any, make_config: Any, fake_work_folder: Any) -> None:
    """gd: wf_evidence_put is allowed."""
    server = mcp_server_factory(make_config())
    _call(server, "ronin_wf_evidence_put", {
        "folder_id": "gd:ev-folder", "filename": "ev.txt", "content": "evidence",
    })
    calls = [c for c in fake_work_folder.calls if c[0] == "wf_evidence_put"]
    assert len(calls) == 1


@pytest.mark.timeout(30)
def test_wf_append_progress_gd(mcp_server_factory: Any, make_config: Any, fake_work_folder: Any) -> None:
    """gd: wf_append_progress is allowed."""
    server = mcp_server_factory(make_config())
    _call(server, "ronin_wf_append_progress", {
        "folder_id": "gd:prog-folder", "entry": "did X",
        "source_session_id": "sess-1", "idempotency_key": "ik-prog-1",
    })
    calls = [c for c in fake_work_folder.calls if c[0] == "wf_append_progress"]
    assert len(calls) == 1


@pytest.mark.timeout(30)
def test_fs_write_rejected_non_gd(mcp_server_factory: Any, make_config: Any) -> None:
    """Non-gd: fs_write is rejected without prod write."""
    server = mcp_server_factory(make_config())

    async def _run() -> None:
        async with Client(server) as client:
            with pytest.raises(ToolError) as exc:
                await client.call_tool("ronin_fs_write", {
                    "folder_id": "prod-folder", "filename": "f", "content": "x",
                })
            assert "PROD_WRITE_NOT_AUTHORIZED" in str(exc.value)

    asyncio.run(_run())
