"""v14.6: Build reviewable v14.5 evaluation cases from a v14.1 report.

The production retriever is called but never modified. Ground-truth labels
are structural hints, NOT assertions about runtime execution or answer quality.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Callable


def _norm(path: Any) -> str:
    return str(path or '').replace('\\', '/').removeprefix('./')


def _definitions(report: dict[str, Any]) -> dict[str, dict[str, Any]]:
    result = {}
    for item in report.get('definitions', []):
        if not isinstance(item, dict):
            continue
        file, symbol = _norm(item.get('file')), item.get('qualified_symbol') or item.get('symbol')
        if file.endswith('.py') and isinstance(symbol, str) and symbol and item.get('start_line'):
            result[f'{file}::{symbol}'] = item
    return result


def _edges(report: dict[str, Any], definitions: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    edges = []
    seen = set()
    for edge in report.get('resolved_calls', []):
        if not isinstance(edge, dict):
            continue
        source = f"{_norm(edge.get('source_file'))}::{edge.get('caller')}"
        target = f"{_norm(edge.get('target_file'))}::{edge.get('target_symbol')}"
        if source not in definitions or target not in definitions:
            continue
        line = edge.get('line')
        if not isinstance(line, int) or line < 1:
            continue
        key = (source, target, line)
        if key in seen:
            continue
        seen.add(key)
        edges.append({'source': source, 'target': target, 'file': _norm(edge.get('source_file')), 'line': line})
    return sorted(edges, key=lambda e: (e['source'], e['target'], e['line']))


def _evidence(results: Any, repository_id: str, limit: int) -> list[dict[str, Any]]:
    if isinstance(results, dict):
        results = results.get('results', [])
    if not isinstance(results, list):
        raise ValueError('Retriever must return a list or a dict containing results')
    evidence = []
    seen = set()
    for item in results:
        if not isinstance(item, dict):
            continue
        meta = item.get('metadata') or {}
        if not isinstance(meta, dict):
            continue
        if meta.get('repository_id') not in (None, '', repository_id):
            raise ValueError('Retriever returned evidence from another repository')
        content = item.get('content') or item.get('document')
        file = _norm(meta.get('file') or item.get('file'))
        if not isinstance(content, str) or not content.strip() or not file:
            continue
        if 'placeholder' in content.lower():
            continue
        start = meta.get('start_line') or item.get('start_line')
        end = meta.get('end_line') or item.get('end_line')
        row = {'file': file, 'content': content, 'repository_id': repository_id}
        if isinstance(start, int) and start > 0:
            row['start_line'] = start
        if isinstance(end, int) and end > 0:
            row['end_line'] = end
        if meta.get('symbol'):
            row['symbol'] = str(meta['symbol'])
        key = (file, row.get('start_line'), content)
        if key not in seen:
            seen.add(key)
            evidence.append(row)
        if len(evidence) >= limit:
            break
    return evidence


def build_cases(
    report: dict[str, Any], *, repository_id: str,
    retrieve_fn: Callable[..., Any], max_cases: int = 20, top_k: int = 8,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if not repository_id.strip() or max_cases < 1 or top_k < 1:
        raise ValueError('repository_id, max_cases and top_k must be positive/nonempty')
    definitions = _definitions(report)
    edges = _edges(report, definitions)
    candidates = []
    used = set()
    # Balanced round-robin: cross-file edges first, then same-file edges.
    for category, subset in (
        ('cross_file_call', [e for e in edges if e['source'].split('::')[0] != e['target'].split('::')[0]]),
        ('direct_call', [e for e in edges if e['source'].split('::')[0] == e['target'].split('::')[0]]),
    ):
        for edge in subset:
            pair = (edge['source'], edge['target'])
            if pair in used:
                continue
            used.add(pair)
            candidates.append({
                'category': category,
                'question': f"What static call relationship exists between {edge['source']} and {edge['target']}?",
                'expected_files': sorted({edge['source'].split('::')[0], edge['target'].split('::')[0]}),
                'structural_reference': {'relationship': 'resolved_static_call', **edge},
            })
    # Disconnected pairs are selected from the same report; no assertion of
    # runtime disconnection, only absence of a direct resolved edge.
    linked = {(e['source'], e['target']) for e in edges}
    keys = sorted(definitions)
    for a in keys:
        for b in keys:
            if a == b or (a, b) in linked or a.split('::')[0] == b.split('::')[0]:
                continue
            candidates.append({
                'category': 'no_direct_static_edge',
                'question': f"Is there a verified direct static call from {a} to {b}? Explain the evidence limits.",
                'expected_files': sorted({a.split('::')[0], b.split('::')[0]}),
                'structural_reference': {'relationship': 'no_direct_resolved_edge', 'source': a, 'target': b},
            })
            break
        if sum(c['category'] == 'no_direct_static_edge' for c in candidates) >= max(2, max_cases // 4):
            break
    # Interleave categories to prevent early truncation selecting only calls.
    buckets = {kind: [c for c in candidates if c['category'] == kind]
               for kind in ('cross_file_call', 'direct_call', 'no_direct_static_edge')}
    ordered = []
    while any(buckets.values()):
        for kind in buckets:
            if buckets[kind]:
                ordered.append(buckets[kind].pop(0))
    cases, skipped = [], []
    for candidate in ordered:
        if len(cases) >= max_cases:
            break
        response = retrieve_fn(repository_id=repository_id, query=candidate['question'], top_k=top_k)
        evidence = _evidence(response, repository_id, top_k)
        if not evidence:
            skipped.append({'category': candidate['category'], 'reason': 'no_valid_retrieval_evidence'})
            continue
        case = {
            'id': f"v14_6_{len(cases) + 1:03d}", 'repository_id': repository_id,
            'question': candidate['question'], 'intent': 'general_search',
            'evidence': evidence, 'expected_files': candidate['expected_files'],
            'required_facts': [],
            'review_metadata': {
                'category': candidate['category'],
                'structural_reference': candidate['structural_reference'],
                'requires_human_review': True,
                'expected_files_are_not_correctness_labels': True,
            },
        }
        cases.append(case)
    return cases, {
        'schema_version': '14.6', 'repository_id': repository_id,
        'definitions': len(definitions), 'valid_static_edges': len(edges),
        'generated_cases': len(cases), 'skipped': skipped,
        'limitations': [
            'Cases are sampled from resolved static relationships, not runtime traces.',
            'A missing direct static edge does not establish absence of a runtime call.',
            'Retrieved evidence may not contain the expected files; review before evaluation.',
            'Generated questions and reference hints are not independently verified answer labels.',
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', required=True, help='v14.1 relationships JSON')
    parser.add_argument('--repository-id', required=True)
    parser.add_argument('--output', required=True, help='v14.5-compatible cases JSON')
    parser.add_argument('--manifest', help='optional generation metadata JSON')
    parser.add_argument('--max-cases', type=int, default=20)
    parser.add_argument('--top-k', type=int, default=8)
    args = parser.parse_args()
    from app.retrieval.retriever import retrieve
    report = json.loads(Path(args.report).read_text(encoding='utf-8'))
    cases, manifest = build_cases(report, repository_id=args.repository_id,
                                  retrieve_fn=retrieve, max_cases=args.max_cases, top_k=args.top_k)
    if not cases:
        raise SystemExit('No cases with real retrieval evidence; check repository ID and index')
    target = Path(args.output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(cases, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    manifest_path = Path(args.manifest) if args.manifest else target.with_name(target.stem + '_manifest.json')
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print(json.dumps({'cases': len(cases), 'output': str(target), 'manifest': str(manifest_path)}, indent=2))


if __name__ == '__main__':
    main()
