"""Summarize opt-in retriever stage timings from JSONL. No extra dependencies.

Run: uv run python -m app.scripts.profile_retrieval_v13_7 --input data/evaluation/v13_7_profile.jsonl
"""
from __future__ import annotations
import argparse
import json
import statistics
from pathlib import Path


def percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    values = sorted(values)
    index = (len(values) - 1) * p / 100
    low = int(index)
    high = min(low + 1, len(values) - 1)
    return values[low] + (values[high] - values[low]) * (index - low)


def summarize(path: Path) -> dict:
    records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not records:
        raise ValueError("No profiling records found")
    stages = sorted({name for record in records for name in record["stages_ms"]})
    rows = []
    for stage in stages:
        vals = [float(record["stages_ms"].get(stage, 0)) for record in records]
        rows.append({"stage": stage, "mean_ms": round(statistics.mean(vals), 2),
                     "p50_ms": round(percentile(vals, 50), 2), "p95_ms": round(percentile(vals, 95), 2)})
    rows.sort(key=lambda item: item["mean_ms"], reverse=True)
    totals = [float(record["total_ms"]) for record in records]
    return {"queries": len(records), "total_p50_ms": round(percentile(totals, 50), 2),
            "total_p95_ms": round(percentile(totals, 95), 2), "stages": rows,
            "mean_supplemental_searches": round(statistics.mean(record["supplemental_searches"] for record in records), 2),
            "mean_merged_candidates": round(statistics.mean(record["merged_candidates"] for record in records), 2)}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=Path("data/evaluation/v13_7_profile.jsonl"))
    parser.add_argument("--output", type=Path, default=Path("data/evaluation/v13_7_profile_summary.json"))
    args = parser.parse_args()
    result = summarize(args.input)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(f"Queries: {result['queries']} | P50: {result['total_p50_ms']} ms | P95: {result['total_p95_ms']} ms")
    for row in result["stages"]:
        print(f"{row['stage']:<28} mean={row['mean_ms']:>9.2f} ms  p95={row['p95_ms']:>9.2f} ms")
    print(f"Summary: {args.output}")


if __name__ == "__main__":
    main()
