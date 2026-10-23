from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


def summarize(path: Path, prefix: str) -> dict:
    report = json.loads(path.read_text(encoding="utf-8"))
    results = report.get("results", [])
    if not isinstance(results, list):
        raise ValueError("Report must contain results list")
    selected = [r for r in results if str(r.get("case_id", "")).startswith(prefix)]
    passed = sum(bool(r.get("passed")) for r in selected)
    return {"cases": len(selected), "passed": passed, "pass_rate": passed / len(selected) if selected else None,
            "failed_ids": [r.get("case_id") for r in selected if not r.get("passed")]}


def main() -> int:
    parser = argparse.ArgumentParser(description="Run v13.1 draft benchmark and report old/new groups separately")
    parser.add_argument("--dataset", type=Path, default=Path("app/data/evaluation/retrieval_benchmark_v13_1_draft.json"))
    parser.add_argument("--output", type=Path, default=Path("data/evaluation/retrieval_report_v13_1_draft.json"))
    parser.add_argument("--top-k", type=int, default=10)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    command = [sys.executable, "-m", "app.scripts.evaluate_retrieval", "--dataset", str(args.dataset), "--top-k", str(args.top_k), "--output", str(args.output)]
    completed = subprocess.run(command, check=False)
    if not args.output.exists():
        return completed.returncode or 1
    baseline = summarize(args.output, "retrieval_")
    draft = summarize(args.output, "generalization_")
    print("\n=== v13.1 Cohort Summary ===")
    print("Original 11:", json.dumps(baseline))
    print("Draft paraphrases (labels not yet independently verified):", json.dumps(draft))
    print("WARNING: Draft paraphrases are not independent ground truth and must not be reported as validated coverage.")
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
