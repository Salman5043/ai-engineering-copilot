"""v13.17 non-mutating ranking diagnostics for the existing production retriever.

Run from repository root:
 uv run python -m app.scripts.evaluate_ranking_diagnostics_v13_17 --manifest data/evaluation/v13_15_hard_queries_candidate.json --output data/evaluation/v13_17_diagnostics.json

Indexes into an isolated temporary Chroma directory. No production ranking changes.
"""
from __future__ import annotations

import argparse
import json
import tempfile
import time
from collections import defaultdict
from pathlib import Path
from statistics import mean
from unittest.mock import patch


def norm(value):
    return str(value or '').replace('\\', '/')


def slim(candidate, include_content=False):
    meta = candidate.get('metadata') or {}
    result = {
        'file': norm(meta.get('file')),
        'symbol': meta.get('symbol'),
        'symbol_type': meta.get('symbol_type'),
        'start_line': meta.get('start_line'),
        'end_line': meta.get('end_line'),
        'score': candidate.get('score'),
        'semantic_score': candidate.get('semantic_score'),
        'distance': candidate.get('distance'),
        'lexical_score': candidate.get('lexical_score'),
        'bm25_score': candidate.get('bm25_score'),
        'ranking_signals': candidate.get('ranking_signals') or {},
    }
    if include_content:
        result['content_excerpt'] = str(candidate.get('content') or '')[:350]
    return result


def diagnose(manifest, top_k=10, chunk_k=100, max_candidates=12):
    from app.config import settings
    from app.ingestion.indexer import index_repository
    from app.retrieval import retriever

    projects = manifest.get('repositories') or []
    if not projects or len({p['id'] for p in projects}) != len(projects):
        raise ValueError('Manifest must have repositories with unique ids')
    if chunk_k < top_k or top_k < 1:
        raise ValueError('Require 1 <= top_k <= chunk_k')

    rows = []
    with tempfile.TemporaryDirectory(prefix='copilot-v13-17-', ignore_cleanup_errors=True) as tmp:
        with patch.object(settings, 'chroma_path', str(Path(tmp) / 'chroma')):
            for project in projects:
                root = Path(project['path']).resolve(strict=True)
                if not root.is_dir():
                    raise ValueError(f'Not a directory: {root}')
                print(f'Indexing {project["id"]}: {root}', flush=True)
                indexed = index_repository(root)
                rid = indexed['repository_id']
                for case in project['cases']:
                    expected = norm(case['expected_file'])
                    if not (root / expected).is_file():
                        raise ValueError(f'Expected file missing: {root / expected}')
                    captured = {}
                    original_merge = retriever._merge_candidates

                    def capture_merge(groups):
                        names = ['primary_semantic'] + [f'supplemental_semantic_{i}' for i in range(1, max(1, len(groups)-1))] + ['lexical']
                        sources = defaultdict(set)
                        counts = {}
                        for name, group in zip(names, groups):
                            counts[name] = len(group)
                            for item in group:
                                sources[retriever._candidate_key(item)].add(name)
                        merged = original_merge(groups)
                        captured['sources'] = sources
                        captured['stage_counts'] = counts
                        captured['merged'] = merged
                        return merged

                    start = time.perf_counter()
                    with patch.object(retriever, '_merge_candidates', side_effect=capture_merge):
                        response = retriever.retrieve(repository_id=rid, query=case['query'], top_k=chunk_k, language='python')
                    latency = (time.perf_counter() - start) * 1000
                    ranked = response['results']
                    files = []
                    file_best = {}
                    file_chunks = defaultdict(int)
                    for item in ranked:
                        meta = item.get('metadata') or {}
                        if meta.get('repository_id') != rid:
                            raise AssertionError('Repository isolation failure')
                        f = norm(meta.get('file'))
                        if not f:
                            continue
                        file_chunks[f] += 1
                        if f not in file_best:
                            files.append(f)
                            file_best[f] = item
                    rank = files.index(expected) + 1 if expected in files else None
                    # Preserve the score and signals of the highest-ranked chunk for each file.
                    top_files = [{**slim(file_best[f]), 'file_rank': i+1, 'returned_chunk_count': file_chunks[f]}
                                 for i, f in enumerate(files[:top_k])]
                    merged = captured.get('merged', [])
                    sources = captured.get('sources', {})
                    expected_candidates = [item for item in merged if norm((item.get('metadata') or {}).get('file')) == expected]
                    expected_source_counts = defaultdict(int)
                    for item in expected_candidates:
                        for source in sources.get(retriever._candidate_key(item), set()):
                            expected_source_counts[source] += 1
                    row = {
                        'repository': project['id'], 'query': case['query'], 'expected_file': expected,
                        'expected_file_rank': rank, 'latency_ms': round(latency, 3),
                        'intent': str(getattr(response.get('intent'), 'name', response.get('intent'))),
                        'returned_file_count': len(files), 'merged_chunk_count': len(merged),
                        'stage_candidate_counts': captured.get('stage_counts', {}),
                        'expected_file_candidate_counts_by_stage': dict(expected_source_counts),
                        'expected_file_merged_chunk_count': len(expected_candidates),
                        'expected_file_best_chunk': slim(file_best[expected], include_content=True) if expected in file_best else None,
                        'top_files': top_files,
                        'top_chunks': [{**slim(item, include_content=True),
                                        'sources': sorted(sources.get(retriever._candidate_key(item), set()))}
                                       for item in ranked[:max_candidates]],
                    }
                    rows.append(row)
                    print(f'  rank={rank or "MISS"} | {case["query"][:80]}', flush=True)
    return {
        'version': 'v13.17',
        'scope': 'diagnostic only; production retriever and reranker unchanged',
        'limitations': ['Top-file score is the highest-ranked returned chunk, not an independently computed file-level score.',
                        'Source provenance records candidate stage membership, not causal attribution of the final score.',
                        'Candidate count includes merged production-indexed chunks, not AST lexical-only records.',
                        'Labels and ambiguous questions must be independently reviewed.'],
        'overall': {'cases': len(rows), 'file_hit_at_1': mean(r['expected_file_rank'] == 1 for r in rows) if rows else 0,
                    'file_hit_at_10': mean(r['expected_file_rank'] is not None and r['expected_file_rank'] <= 10 for r in rows) if rows else 0,
                    'file_mrr': mean(1 / r['expected_file_rank'] if r['expected_file_rank'] else 0 for r in rows) if rows else 0,
                    'mean_latency_ms': mean(r['latency_ms'] for r in rows) if rows else 0},
        'repository_isolation': True,
        'results': rows,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--top-k', type=int, default=10)
    parser.add_argument('--chunk-k', type=int, default=100)
    parser.add_argument('--max-candidates', type=int, default=12)
    args = parser.parse_args()
    report = diagnose(json.loads(args.manifest.read_text(encoding='utf-8')), args.top_k, args.chunk_k, args.max_candidates)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False, default=str), encoding='utf-8')
    print('v13.17 ranking diagnostics:', report['overall'])
    print('Repository isolation: PASS')
    print('Report:', args.output)


if __name__ == '__main__':
    main()
