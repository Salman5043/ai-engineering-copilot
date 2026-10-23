from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.evaluation.dataset_loader import (
    load_retrieval_dataset,
)
from app.evaluation.reports import (
    report_to_dict,
)
from app.evaluation.retrieval_adapter import (
    real_repository_retriever,
)
from app.evaluation.runner import (
    EvaluationRunner,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Run the AI Engineering Copilot "
            "retrieval benchmark."
        )
    )

    parser.add_argument(
        "--dataset",
        type=Path,
        default=Path(
            "data/evaluation/"
            "retrieval_benchmark.json"
        ),
    )

    parser.add_argument(
        "--top-k",
        type=int,
        default=5,
    )

    parser.add_argument(
        "--output",
        type=Path,
        default=Path(
            "data/evaluation/"
            "retrieval_report.json"
        ),
    )

    args = parser.parse_args()

    cases = load_retrieval_dataset(
        args.dataset
    )

    runner = EvaluationRunner(
        real_repository_retriever,
        top_k=args.top_k,
    )

    report = runner.evaluate(cases)

    payload = report_to_dict(
        report
    )

    args.output.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    args.output.write_text(
        json.dumps(
            payload,
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )

    print()
    print(
        "=== Retrieval Benchmark ==="
    )
    print(
        f"Cases: {report.total_cases}"
    )
    print(
        f"Passed: {report.passed_cases}"
    )
    print(
        f"Failed: {report.failed_cases}"
    )
    print(
        f"Pass Rate: "
        f"{report.pass_rate:.2%}"
    )
    print(
        f"Overall Score: "
        f"{report.overall_score:.4f}"
    )

    print()
    print("Metrics:")

    for name, value in (
        report.metrics.items()
    ):
        print(
            f"  {name}: {value:.4f}"
        )

    print()
    print(
        f"Report written to: "
        f"{args.output}"
    )

    if report.failed_cases:
        print()
        print("Failed cases:")

        for result in report.results:
            if result.passed:
                continue

            print(
                f"  {result.case_id}: "
                f"{result.score:.4f}"
            )

            for error in result.errors:
                print(
                    f"    ERROR: {error}"
                )


if __name__ == "__main__":
    main()