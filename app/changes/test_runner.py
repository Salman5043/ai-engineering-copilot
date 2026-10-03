from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

from app.changes.models import (
    TestResult,
    VerificationStatus,
)


class TestExecutionError(RuntimeError):
    """
    Raised when the test process cannot be started.
    """
    __test__ = False

class TestRunner:
    """
    Safely executes repository tests.

    The runner does not use shell=True and therefore
    does not execute an arbitrary shell command.

    Python tests are executed through the current
    Python interpreter.
    """
    __test__ = False

    def __init__(
        self,
        repository_root: Path,
        timeout_seconds: float = 300.0,
    ) -> None:
        self.repository_root = (
            repository_root.resolve()
        )

        self.timeout_seconds = (
            timeout_seconds
        )

    def build_command(
        self,
        tests: list[str],
    ) -> list[str]:
        """
        Build a controlled pytest command.
        """

        if not tests:
            raise TestExecutionError(
                "No tests were supplied."
            )

        return [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            *tests,
        ]

    def run(
        self,
        tests: list[str],
    ) -> TestResult:
        """
        Execute the selected tests.
        """

        command = self.build_command(
            tests
        )

        started = time.perf_counter()

        try:
            process = subprocess.run(
                command,
                cwd=self.repository_root,
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
                shell=False,
            )

        except subprocess.TimeoutExpired as exc:
            duration = (
                time.perf_counter()
                - started
            )

            stdout = (
                exc.stdout
                if isinstance(
                    exc.stdout,
                    str,
                )
                else ""
            )

            stderr = (
                exc.stderr
                if isinstance(
                    exc.stderr,
                    str,
                )
                else ""
            )

            return TestResult(
                command=command,
                status=(
                    VerificationStatus.TIMED_OUT
                ),
                return_code=None,
                stdout=stdout,
                stderr=stderr,
                duration_seconds=duration,
                timed_out=True,
            )

        except OSError as exc:
            raise TestExecutionError(
                "Unable to start test process."
            ) from exc

        duration = (
            time.perf_counter()
            - started
        )

        if process.returncode == 0:
            status = (
                VerificationStatus.PASSED
            )
        else:
            status = (
                VerificationStatus.FAILED
            )

        return TestResult(
            command=command,
            status=status,
            return_code=process.returncode,
            stdout=process.stdout,
            stderr=process.stderr,
            duration_seconds=duration,
            timed_out=False,
        )