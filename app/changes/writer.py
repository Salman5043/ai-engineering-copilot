from __future__ import annotations

import os
import tempfile
from pathlib import Path


class AtomicWriteError(RuntimeError):
    """Raised when an atomic file write fails."""


def atomic_write(
    path: Path,
    content: str,
) -> None:
    """
    Atomically replace a file's contents.

    The new content is first written to a temporary
    file in the same directory and then replaced
    into position.

    This prevents partially-written target files.
    """

    path = path.resolve()

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    temp_path: Path | None = None

    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as temporary_file:
            temporary_file.write(content)
            temporary_file.flush()
            os.fsync(
                temporary_file.fileno()
            )

            temp_path = Path(
                temporary_file.name
            )

        os.replace(
            temp_path,
            path,
        )

        temp_path = None

    except Exception as exc:
        raise AtomicWriteError(
            f"Failed to atomically write: {path}"
        ) from exc

    finally:
        if (
            temp_path is not None
            and temp_path.exists()
        ):
            try:
                temp_path.unlink()
            except OSError:
                pass