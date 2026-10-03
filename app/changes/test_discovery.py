from __future__ import annotations

from pathlib import Path


TEST_DIRECTORIES = {
    "test",
    "tests",
}


def discover_tests(
    repository_root: Path,
) -> list[str]:
    """
    Discover likely test files without executing them.
    """

    results: list[str] = []

    if not repository_root.exists():
        return results

    for path in repository_root.rglob("*"):
        if not path.is_file():
            continue

        relative = path.relative_to(
            repository_root
        )

        parts = {
            part.lower()
            for part in relative.parts
        }

        name = path.name.lower()

        is_test_directory = bool(
            parts.intersection(
                TEST_DIRECTORIES
            )
        )

        is_test_file = (
            name.startswith("test_")
            or name.endswith("_test.py")
        )

        if is_test_directory or is_test_file:
            results.append(
                relative.as_posix()
            )

    return sorted(
        set(results)
    )