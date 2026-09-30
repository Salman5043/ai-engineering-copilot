from __future__ import annotations

from pathlib import Path

import pytest

from app.config import settings
from app.developer_tools.filesystem import RepositoryFileSystem
from app.developer_tools.registry import (
    DEVELOPER_TOOL_REGISTRY,
    list_files,
    read_file,
    repository_structure,
    search_text,
)


@pytest.fixture
def test_repository(tmp_path, monkeypatch):
    repository_root = tmp_path / "test_repo"

    repository_root.mkdir()

    (repository_root / "app").mkdir()
    (repository_root / "tests").mkdir()
    (repository_root / ".git").mkdir()

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

    (repository_root / ".git" / "ignored.txt").write_text(
        "should not be searched",
        encoding="utf-8",
    )

    monkeypatch.setattr(
        settings,
        "repository_root",
        str(tmp_path),
    )

    return repository_root


def test_repository_filesystem_initializes(test_repository):
    filesystem = RepositoryFileSystem("test_repo")

    assert filesystem.root == test_repository.resolve()


def test_list_directory(test_repository):
    filesystem = RepositoryFileSystem("test_repo")

    entries = filesystem.list_directory("app")

    paths = {entry.path for entry in entries}

    assert "app/main.py" in paths
    assert "app/config.py" in paths


def test_read_file(test_repository):
    result = read_file(
        repository_id="test_repo",
        path="app/main.py",
    )

    assert result.path == "app/main.py"
    assert "def hello()" in result.content


def test_read_file_line_range(test_repository):
    result = read_file(
        repository_id="test_repo",
        path="app/main.py",
        start_line=1,
        end_line=1,
    )

    assert result.content == "def hello():"


def test_path_escape_is_blocked(test_repository):
    filesystem = RepositoryFileSystem("test_repo")

    with pytest.raises(ValueError, match="escapes repository"):
        filesystem.resolve_path("../../outside.txt")


def test_absolute_path_escape_is_blocked(test_repository):
    filesystem = RepositoryFileSystem("test_repo")

    outside = Path(test_repository).parent / "outside.txt"

    with pytest.raises(ValueError, match="escapes repository"):
        filesystem.resolve_path(str(outside))


def test_search_text(test_repository):
    result = search_text(
        repository_id="test_repo",
        query="hello",
    )

    assert result.query == "hello"
    assert len(result.matches) == 3

    matched_paths = {
        match.path
        for match in result.matches
    }

    assert "app/main.py" in matched_paths
    assert "tests/test_main.py" in matched_paths


def test_search_is_case_insensitive_by_default(test_repository):
    result = search_text(
        repository_id="test_repo",
        query="DEBUG",
    )

    assert len(result.matches) == 1
    assert result.matches[0].path == "app/config.py"


def test_search_respects_case_sensitive_mode(test_repository):
    result = search_text(
        repository_id="test_repo",
        query="debug",
        case_sensitive=True,
    )

    assert len(result.matches) == 0


def test_search_ignores_git_directory(test_repository):
    result = search_text(
        repository_id="test_repo",
        query="should not be searched",
    )

    assert len(result.matches) == 0


def test_repository_structure(test_repository):
    result = repository_structure(
        repository_id="test_repo",
    )

    assert result.repository_id == "test_repo"
    assert "app/main.py" in result.files
    assert "app/config.py" in result.files
    assert "tests/test_main.py" in result.files


def test_max_search_results(test_repository):
    result = search_text(
        repository_id="test_repo",
        query="return",
        max_results=1,
    )

    assert len(result.matches) <= 1


def test_registry_contains_developer_tools():
    expected = {
        "read_file",
        "list_files",
        "search_text",
        "repository_structure",
    }

    assert expected.issubset(
        DEVELOPER_TOOL_REGISTRY.keys()
    )


def test_unknown_repository_is_rejected():
    with pytest.raises(FileNotFoundError):
        RepositoryFileSystem(
            "repository_that_does_not_exist"
        )