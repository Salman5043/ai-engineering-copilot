"""Summarize optional v13.9 lexical-stage JSONL timing records."""
import argparse
import json
import statistics
from pathlib import Path


def percentile(values, percentage):
    if not values:
        return 0.0
    ordered = sorted(values)
    index = (len(ordered) - 1) * percentage / 100
    lower = int(index)
    upper = min(lower + 1, len(ordered) - 1)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (index - lower)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="data/evaluation/v13_9_lexical.jsonl")
    parser.add_argument("--output", default="data/evaluation/v13_9_lexical_summary.json")
    args = parser.parse_args()
    source = Path(args.input)
    if not source.is_file():
        parser.error(f"Input file does not exist: {source}")
    records = []
    for line in source.read_text(encoding="utf-8").splitlines():
        if line.strip():
            records.append(json.loads(line))
    if not records:
        parser.error("No profiling records found.")
    stages = ("collection_get_ms", "candidate_scoring_ms", "bm25_ms",
              "normalization_sort_ms", "total_ms")
    summary = {"queries": len(records), "stages": {}}
    print(f"Queries: {len(records)}")
    for stage in stages:
        values = [float(row[stage]) for row in records]
        stats = {"mean_ms": round(statistics.mean(values), 2),
                 "p50_ms": round(percentile(values, 50), 2),
                 "p95_ms": round(percentile(values, 95), 2)}
        summary["stages"][stage] = stats
        print(f"{stage:25} mean={stats['mean_ms']:9.2f} ms  "
              f"p50={stats['p50_ms']:9.2f} ms  p95={stats['p95_ms']:9.2f} ms")
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"Summary: {output}")


if __name__ == "__main__":
    main()
