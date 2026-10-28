"""v14.2: trace bounded, evidence-backed static call paths from v14.1 JSON.

No code execution, source modification, or runtime-flow claims.
"""
from __future__ import annotations
import argparse
from collections import defaultdict, deque
import json
from pathlib import Path


def node_id(file: str, symbol: str) -> str:
    return f"{file}::{symbol}"


def trace(report: dict, source: str, target: str, max_depth: int = 8, max_paths: int = 20) -> dict:
    if max_depth < 0 or max_paths < 1:
        raise ValueError("max_depth must be >= 0 and max_paths >= 1")
    definitions = {node_id(d['file'], d['qualified_symbol']): d for d in report['definitions']}
    if source not in definitions or target not in definitions:
        missing = [n for n in (source, target) if n not in definitions]
        raise ValueError(f"Unknown definition(s): {missing}. Use file.py::qualified_symbol")
    edges = defaultdict(list)
    seen = set()
    for r in report.get('resolved_calls', []):
        caller = node_id(r['source_file'], r['caller'])
        callee = node_id(r['target_file'], r['target_symbol'])
        if caller not in definitions or callee not in definitions:
            continue  # module-level calls are not attached to an executable definition
        key = (caller, callee, r['line'], r['expression'])
        if key in seen:
            continue
        seen.add(key)
        edges[caller].append({'from': caller, 'to': callee, 'file': r['source_file'],
                              'line': r['line'], 'expression': r['expression'],
                              'confidence': r.get('confidence', 'unknown'),
                              'evidence': r.get('evidence', 'unknown')})
    for items in edges.values():
        items.sort(key=lambda e: (e['to'], e['line'], e['expression']))
    queue = deque([(source, [], frozenset({source}))])
    paths = []
    while queue and len(paths) < max_paths:
        current, path, visited = queue.popleft()
        if current == target:
            paths.append({'nodes': [source] + [e['to'] for e in path], 'edges': path})
            continue
        if len(path) >= max_depth:
            continue
        for edge in edges[current]:
            if edge['to'] not in visited:
                queue.append((edge['to'], path + [edge], visited | {edge['to']}))
    return {'schema_version': '14.2', 'source': source, 'target': target,
            'path_type': 'possible_static_call_chain', 'paths': paths,
            'found': bool(paths), 'max_depth': max_depth, 'max_paths': max_paths,
            'limitations': ['Only v14.1 resolved calls are traversed.',
                            'Framework callbacks, registrations, dynamic dispatch, and runtime behavior are not inferred.',
                            'A missing path does not establish that no runtime path exists.']}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', required=True, help='v14.1 relationships JSON')
    parser.add_argument('--source', required=True, help='file.py::qualified_symbol')
    parser.add_argument('--target', required=True, help='file.py::qualified_symbol')
    parser.add_argument('--output', help='Optional output JSON')
    parser.add_argument('--max-depth', type=int, default=8)
    parser.add_argument('--max-paths', type=int, default=20)
    args = parser.parse_args()
    report = json.loads(Path(args.input).read_text(encoding='utf-8'))
    result = trace(report, args.source, args.target, args.max_depth, args.max_paths)
    rendered = json.dumps(result, indent=2)
    print(rendered)
    if args.output:
        destination = Path(args.output)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(rendered + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
