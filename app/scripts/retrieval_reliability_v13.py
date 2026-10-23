"""Repeat the existing retrieval benchmark and enforce conservative v12 regression gates.

Run from the repository root:
 uv run python -m app.scripts.retrieval_reliability_v13 --runs 3
"""
from __future__ import annotations

import argparse
import json
import math
import statistics
import subprocess
import sys
from pathlib import Path


def percentile(values: list[float], p: float) -> float:
    """Linear-interpolated percentile, without third-party dependencies."""
    if not values:
        return 0.0
    ordered = sorted(values)
    position = (len(ordered) - 1) * p / 100
    lower = math.floor(position)
    upper = math.ceil(position)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def run_benchmark(dataset: Path, output: Path, top_k: int) -> dict:
    cmd = [sys.executable, '-m', 'app.scripts.evaluate_retrieval',
           '--dataset', str(dataset), '--top-k', str(top_k), '--output', str(output)]
    subprocess.run(cmd, check=True)
    return json.loads(output.read_text(encoding='utf-8'))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dataset', type=Path, default=Path('app/data/evaluation/retrieval_benchmark.json'))
    parser.add_argument('--runs', type=int, default=3)
    parser.add_argument('--top-k', type=int, default=10)
    parser.add_argument('--output-dir', type=Path, default=Path('data/evaluation/v13_reliability'))
    parser.add_argument('--min-file-hit-at-1', type=float, default=1.0)
    parser.add_argument('--min-file-hit-at-5', type=float, default=1.0)
    parser.add_argument('--min-pass-rate', type=float, default=1.0)
    parser.add_argument('--min-legacy-score', type=float, default=0.6773)
    parser.add_argument('--legacy-score-tolerance', type=float, default=0.00005,
                        help='Tolerance for a baseline rounded to four decimal places')
    args = parser.parse_args()
    if args.legacy_score_tolerance < 0:
        parser.error('--legacy-score-tolerance must be nonnegative')
    if args.runs < 1 or args.top_k < 1:
        parser.error('--runs and --top-k must be positive')
    args.output_dir.mkdir(parents=True, exist_ok=True)
    reports = []
    latencies = []
    failures = []
    for index in range(args.runs):
        path = args.output_dir / f'run_{index + 1:02}.json'
        report = run_benchmark(args.dataset, path, args.top_k)
        reports.append(report)
        metrics = report.get('metrics') or {}
        count = report.get('total_cases', len(report.get('results', [])))
        passed = report.get('passed_cases', 0)
        pass_rate = passed / count if count else 0.0
        gates = {
            'pass_rate': (pass_rate, args.min_pass_rate),
            'file_hit_at_1': (metrics.get('file_hit_at_1', 0.0), args.min_file_hit_at_1),
            'file_hit_at_5': (metrics.get('file_hit_at_5', 0.0), args.min_file_hit_at_5),
            'legacy_score': (metrics.get('legacy_score', 0.0), args.min_legacy_score),
        }
        for name, (value, threshold) in gates.items():
            tolerance = args.legacy_score_tolerance if name == 'legacy_score' else 1e-6
            if value + tolerance < threshold:
                failures.append(
                    f'run {index+1}: {name} {value:.8f} < {threshold:.8f} '
                    f'(tolerance={tolerance:.8f})'
                )
        for result in report.get('results', []):
            latency = (result.get('metrics') or {}).get('latency_ms')
            if isinstance(latency, (int, float)):
                latencies.append(float(latency))
        print(f'Run {index+1}/{args.runs}: pass={pass_rate:.2%}, file_hit@1={metrics.get("file_hit_at_1", 0):.4f}')
    summary = {
        'runs': args.runs,
        'dataset': str(args.dataset),
        'top_k': args.top_k,
        'cases_per_run': [r.get('total_cases', len(r.get('results', []))) for r in reports],
        'latency_samples': len(latencies),
        'latency_ms_p50': percentile(latencies, 50),
        'latency_ms_p95': percentile(latencies, 95),
        'latency_ms_mean': statistics.mean(latencies) if latencies else 0.0,
        'failures': failures,
        'passed': not failures,
    }
    summary_path = args.output_dir / 'summary.json'
    summary_path.write_text(json.dumps(summary, indent=2), encoding='utf-8')
    print(f'P50: {summary["latency_ms_p50"]:.1f} ms | P95: {summary["latency_ms_p95"]:.1f} ms')
    print(f'Summary: {summary_path}')
    if failures:
        for failure in failures:
            print('REGRESSION:', failure, file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
