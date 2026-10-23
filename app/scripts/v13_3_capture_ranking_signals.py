"""Capture production reranker signals without changing ranking behavior.

Run: uv run python -m app.scripts.v13_3_capture_ranking_signals --top-k 10
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from app.retrieval.retriever import retrieve


def capture(dataset: Path, output: Path, top_k: int) -> tuple[int, int]:
    payload = json.loads(dataset.read_text(encoding="utf-8"))
    rows = []
    below_first = 0
    for case in payload["cases"]:
        response = retrieve(repository_id=case["repository_id"], query=case["query"], top_k=top_k)
        results = response["results"]
        expected_files = {str(item["file"]).replace("\\", "/").lower() for item in case["expected_evidence"]}
        rank = next((i for i, item in enumerate(results, 1) if str(item.get("metadata", {}).get("file", item.get("file", ""))).replace("\\", "/").lower() in expected_files), None)
        if rank != 1:
            below_first += 1
        for index, item in enumerate(results, 1):
            meta = item.get("metadata") or {}
            file_path = str(meta.get("file", item.get("file", "")))
            row = {
                "case_id": case["case_id"], "query": case["query"],
                "expected_files": "; ".join(sorted(expected_files)),
                "expected_file_rank": rank if rank is not None else "missing",
                "rank": index, "file": file_path,
                "symbol": meta.get("symbol", item.get("symbol", "")),
                "score": item.get("score"),
                "semantic_score": item.get("semantic_score"),
                "is_expected_file": file_path.replace("\\", "/").lower() in expected_files,
            }
            signals = item.get("ranking_signals") or {}
            for key, value in signals.items():
                if isinstance(value, (int, float, str, bool)):
                    row["signal_" + key] = value
            rows.append(row)
    output.parent.mkdir(parents=True, exist_ok=True)
    fields = list(dict.fromkeys(key for row in rows for key in row))
    with output.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    return len(payload["cases"]), below_first


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, default=Path("app/data/evaluation/retrieval_benchmark_v13_1_draft.json"))
    parser.add_argument("--output", type=Path, default=Path("data/evaluation/v13_3/ranking_signals.csv"))
    parser.add_argument("--top-k", type=int, default=10)
    args = parser.parse_args()
    if args.top_k < 1:
        parser.error("--top-k must be positive")
    count, below_first = capture(args.dataset, args.output, args.top_k)
    print(f"Cases: {count} | Expected file not at rank 1: {below_first}")
    print(f"Detailed signal report: {args.output}")


if __name__ == "__main__":
    main()
