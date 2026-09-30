from __future__ import annotations

from pathlib import Path

import pytest

from app.config import settings
from app.developer_tools.registry import (
    DEVELOPER_TOOL_REGISTRY,
)
from app.mcp_server.tools import (
    mcp_list_files,
    mcp_read_file,
    mcp_repository_structure,
    mcp_search_text,
)


@pytest.fixture
def test_repository(tmp_path, monkeypatch):
    repository_root = tmp_path / "test_repo"

    repository_root.mkdir()

    (repository_root / "app").mkdir()
    (repository_root / "tests").mkdir()

    (repository_root / "app" / "main.py").write_text(
        "def hello():\n"
        "    return 'hello'\n",
        encoding="utf-8",
    )

    (repository_root / "app" / "config.py").write_text(
        "DEBUG = True\n"
        "PORT = 8000\n",
        encoding="utf-8",
    )

    (repository_root / "tests" / "test_main.py").write_text(
        "def test_hello():\n"
        "    assert True\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(
        settings,
        "repository_root",
        str(tmp_path),
    )

    return repository_root


def test_mcp_read_file(test_repository):
    result = mcp_read_file(
        repository_id="test_repo",
        path="app/main.py",
    )

    assert result["path"] == "app/main.py"
    assert "def hello()" in result["content"]


def test_mcp_read_file_line_range(test_repository):
    result = mcp_read_file(
        repository_id="test_repo",
        path="app/main.py",
        start_line=1,
        end_line=1,
    )

    assert result["content"] == "def hello():"


def test_mcp_list_files(test_repository):
    result = mcp_list_files(
        repository_id="test_repo",
        path="app",
    )

    paths = {
        item["path"]
        for item in result
    }

    assert "app/main.py" in paths
    assert "app/config.py" in paths


def test_mcp_search_text(test_repository):
    result = mcp_search_text(
        repository_id="test_repo",
        query="hello",
    )

    assert result["query"] == "hello"
    assert len(result["matches"]) == 3


def test_mcp_repository_structure(test_repository):
    result = mcp_repository_structure(
        repository_id="test_repo",
    )

    assert result["repository_id"] == "test_repo"
    assert "app/main.py" in result["files"]
    assert "app/config.py" in result["files"]
    assert "tests/test_main.py" in result["files"]


def test_mcp_read_file_blocks_path_escape(test_repository):
    with pytest.raises(ValueError, match="escapes repository"):
        mcp_read_file(
            repository_id="test_repo",
            path="../../outside.txt",
        )


def test_mcp_search_uses_existing_registry(test_repository):
    assert "read_file" in DEVELOPER_TOOL_REGISTRY
    assert "list_files" in DEVELOPER_TOOL_REGISTRY
    assert "search_text" in DEVELOPER_TOOL_REGISTRY
    assert "repository_structure" in DEVELOPER_TOOL_REGISTRY


def test_mcp_tools_are_importable():
    from app.mcp_server.server import mcp

    assert mcp is not None