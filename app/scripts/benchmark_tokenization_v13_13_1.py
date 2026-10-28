"""Controlled A/B benchmark of v13.12 vs v13.13 lexical tokenization.

Copy both historical lexical retriever files into app/retrieval/benchmarks/.
Run: uv run python -m app.scripts.benchmark_tokenization_v13_13_1
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import random
import statistics
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DIR = ROOT / 'app' / 'retrieval' / 'benchmarks'


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f'Cannot load {path}')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def dataset(size: int, seed: int) -> list[tuple[str, str, str]]:
    rng = random.Random(seed)
    names = ['RetryConfig', 'HTTPRequestHandler', 'get_collection', 'XMLParser',
             'parseHTTPResponse', 'db_connection', 'a.b/c.py', 'camelCase99',
             'cache-invalidation', 'foo_bar_123', 'unicode_বাংলা', '']
    pieces = ['def retry_request():', 'class HTTPRequestHandler:',
              'return collection.get(where={"repository_id": repository_id})',
              'cache invalidation and refresh strategy', 'tokenizer HTTPResponse2',
              'for candidate in candidates: score += 0.45',
              'foo/bar/file_name.py', '# repeated code and identifiers']
    rows = []
    for index in range(size):
        symbol = rng.choice(names)
        path = f'app/{rng.choice(names)}/{index % 41}/module_{index % 13}.py'
        content = '\n'.join(rng.choices(pieces, k=rng.randrange(8, 55)))
        rows.append((symbol, path, content))
    return rows


def operations(mod):
    return {
        'meaningful_content': lambda row: mod._meaningful_tokens(row[2]),
        'meaningful_symbol': lambda row: mod._meaningful_tokens(row[0]),
        'symbol_normalized': lambda row: mod._meaningful_tokens(mod._CAMEL_BOUNDARY.sub(' ', row[0]))
            if mod.__name__.endswith('12') else mod._meaningful_tokens(row[0]),
        'candidate_preparation': lambda row: (
            mod._meaningful_tokens(mod._CAMEL_BOUNDARY.sub(' ', row[0]))
                if mod.__name__.endswith('12') else mod._meaningful_tokens(row[0]),
            mod._meaningful_tokens(row[1].replace('\\', '/')),
            mod._meaningful_tokens(row[2]),
        ),
    }


def measure(fn, rows, repetitions):
    times = []
    for _ in range(repetitions):
        begin = time.perf_counter_ns()
        for row in rows:
            fn(row)
        times.append((time.perf_counter_ns() - begin) / 1e6)
    return times


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--v12', type=Path, default=DEFAULT_DIR / 'lexical_retriever_v13_12.py')
    parser.add_argument('--v13', type=Path, default=DEFAULT_DIR / 'lexical_retriever_v13_13.py')
    parser.add_argument('--rows', type=int, default=500)
    parser.add_argument('--rounds', type=int, default=12)
    parser.add_argument('--seed', type=int, default=13131)
    parser.add_argument('--output', type=Path, default=ROOT / 'data/evaluation/v13_13_1_tokenization.json')
    args = parser.parse_args()
    if args.rows < 1 or args.rounds < 2:
        parser.error('--rows must be >= 1 and --rounds must be >= 2')
    for path in (args.v12, args.v13):
        if not path.is_file():
            parser.error(f'Missing historical implementation: {path}')
    v12 = load_module(args.v12, 'lexical_benchmark_v12')
    v13 = load_module(args.v13, 'lexical_benchmark_v13')
    rows = dataset(args.rows, args.seed)
    old_ops, new_ops = operations(v12), operations(v13)
    summary = {'rows': len(rows), 'rounds': args.rounds, 'seed': args.seed, 'operations': {}}
    for name in old_ops:
        a, b = old_ops[name], new_ops[name]
        for index, row in enumerate(rows):
            if a(row) != b(row):
                raise AssertionError(f'Output mismatch: {name}, row={index}, value={row[0]!r}')
        # Warm up both implementations; alternate ordering each pair to reduce bias.
        measure(a, rows, 2)
        measure(b, rows, 2)
        old_times, new_times = [], []
        for turn in range(args.rounds):
            if turn % 2:
                new_times.extend(measure(b, rows, 1))
                old_times.extend(measure(a, rows, 1))
            else:
                old_times.extend(measure(a, rows, 1))
                new_times.extend(measure(b, rows, 1))
        old_median = statistics.median(old_times)
        new_median = statistics.median(new_times)
        change = (new_median / old_median - 1) * 100 if old_median else 0.0
        summary['operations'][name] = {
            'v13_12_median_ms': round(old_median, 3),
            'v13_13_median_ms': round(new_median, 3),
            'change_pct': round(change, 2),
            'v13_12_samples_ms': [round(x, 3) for x in old_times],
            'v13_13_samples_ms': [round(x, 3) for x in new_times],
            'outputs_equal': True,
        }
        print(f'{name:24} v13.12={old_median:8.2f} ms | v13.13={new_median:8.2f} ms | change={change:+7.2f}%')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(summary, indent=2), encoding='utf-8')
    print(f'\nAll token outputs identical. Report: {args.output}')


if __name__ == '__main__':
    main()
