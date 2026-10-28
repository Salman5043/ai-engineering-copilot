"""Summarize candidate scoring substage JSONL emitted by v13.11."""
import argparse
import json
import statistics
from pathlib import Path


def percentile(values, p):
    ordered = sorted(values)
    pos = (len(ordered) - 1) * p / 100
    low = int(pos)
    high = min(low + 1, len(ordered) - 1)
    return ordered[low] + (ordered[high] - ordered[low]) * (pos - low)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', default='data/evaluation/v13_11_lexical.jsonl')
    parser.add_argument('--output', default='data/evaluation/v13_11_candidate_summary.json')
    args = parser.parse_args()
    rows = [json.loads(line) for line in Path(args.input).read_text(encoding='utf-8').splitlines() if line.strip()]
    if not rows:
        parser.error('No profiling records found')
    names = ('query_preparation_ms', 'candidate_tokenization_ms',
             'candidate_score_core_ms', 'phrase_matching_ms', 'other_candidate_ms')
    summary = {'queries': len(rows), 'stages': {}}
    print(f'Queries: {len(rows)}')
    for name in names:
        values = [float(row['candidate_detail_ms'][name]) for row in rows]
        stats = {'mean_ms': round(statistics.mean(values), 2),
                 'p50_ms': round(percentile(values, 50), 2),
                 'p95_ms': round(percentile(values, 95), 2)}
        summary['stages'][name] = stats
        print(f'{name:30} mean={stats["mean_ms"]:8.2f} ms  p95={stats["p95_ms"]:8.2f} ms')
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(summary, indent=2), encoding='utf-8')
    print(f'Summary: {output}')


if __name__ == '__main__':
    main()
