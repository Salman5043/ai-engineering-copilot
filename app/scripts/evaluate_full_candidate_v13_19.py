"""v13.19 controlled full-candidate reranking study (non-production).

Runs production indexing/retrieval in isolated Chroma, intercepts the *complete*
merged candidate list, and compares file rankings on identical scored chunks.
Optional manifest case field `expected_symbol` enables symbol hit@1 metrics.
This is exploratory; validate on independent repositories before deployment.
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

from app.scripts.evaluate_offline_reranking_v13_18 import evidence_score


def normalized(value):
    return str(value or '').replace('\\', '/')


def metrics(rows, key):
    ranks = [r[key] for r in rows]
    return {
        'cases': len(rows),
        'file_hit_at_1': mean(r == 1 for r in ranks) if ranks else 0,
        'file_hit_at_5': mean(r is not None and r <= 5 for r in ranks) if ranks else 0,
        'file_hit_at_10': mean(r is not None and r <= 10 for r in ranks) if ranks else 0,
        'file_mrr': mean(1 / r if r else 0 for r in ranks) if ranks else 0,
    }


def unique_files(chunks):
    result = []
    seen = set()
    for c in chunks:
        file = normalized((c.get('metadata') or {}).get('file'))
        if file and file not in seen:
            seen.add(file)
            result.append(file)
    return result


def symbol_rank(chunks, expected_file, expected_symbol):
    if not expected_symbol:
        return None
    target = expected_symbol.strip()
    for rank, c in enumerate(chunks, 1):
        m = c.get('metadata') or {}
        if normalized(m.get('file')) == expected_file and target in {str(m.get('symbol') or ''), str(m.get('qualified_symbol') or '')}:
            return rank
    return None


def evaluate(manifest, chunk_k=100, export_candidates=True):
    from app.config import settings
    from app.ingestion.indexer import index_repository
    from app.retrieval import retriever

    projects = manifest.get('repositories') or []
    if not projects or len({p['id'] for p in projects}) != len(projects):
        raise ValueError('Manifest requires unique repository ids')
    rows = []
    repo_info = []
    with tempfile.TemporaryDirectory(prefix='copilot-v13-19-', ignore_cleanup_errors=True) as tmp:
        with patch.object(settings, 'chroma_path', str(Path(tmp) / 'chroma')):
            for project in projects:
                root = Path(project['path']).resolve(strict=True)
                if not root.is_dir():
                    raise ValueError(f'Not a directory: {root}')
                print(f'Indexing {project["id"]}: {root}', flush=True)
                indexed = index_repository(root)
                rid = indexed['repository_id']
                repo_info.append({'manifest_id': project['id'], 'repository_id': rid,
                                  'files': indexed.get('files'), 'chunks': indexed.get('chunks')})
                for case in project['cases']:
                    expected = normalized(case['expected_file'])
                    if not (root / expected).is_file():
                        raise ValueError(f'Missing expected file: {root / expected}')
                    captured = {}
                    original_rerank = retriever.rerank

                    def capture_rerank(*, candidates, parsed_query, intent, strategy):
                        ranked = original_rerank(candidates=candidates, parsed_query=parsed_query,
                                                 intent=intent, strategy=strategy)
                        captured['ranked'] = ranked
                        captured['candidate_count'] = len(candidates)
                        return ranked

                    t0 = time.perf_counter()
                    with patch.object(retriever, 'rerank', side_effect=capture_rerank):
                        response = retriever.retrieve(repository_id=rid, query=case['query'],
                                                      top_k=chunk_k, language='python')
                    elapsed = (time.perf_counter() - t0) * 1000
                    baseline = captured.get('ranked', [])  # all merged, scored chunks; not sliced by top_k
                    if not baseline:
                        raise RuntimeError('No candidates captured; verify retriever.rerank integration')
                    for c in baseline:
                        if (c.get('metadata') or {}).get('repository_id') != rid:
                            raise AssertionError('Repository isolation failure')
                    expected_symbol = case.get('expected_symbol')
                    row = {'repository': project['id'], 'query': case['query'],
                           'expected_file': expected, 'expected_symbol': expected_symbol,
                           'candidate_chunks': captured['candidate_count'],
                           'intent': str(getattr(response.get('intent'), 'name', '')),
                           'retrieval_latency_ms': round(elapsed, 3), 'variants': {}}
                    for variant in ('baseline', 'structural', 'lexical_discount'):
                        start = time.perf_counter()
                        if variant == 'baseline':
                            ordered = baseline
                        else:
                            ordered = sorted(baseline, key=lambda c: (
                                float(c.get('score') or 0) + evidence_score(case['query'], {
                                    **(c.get('metadata') or {}),
                                    'ranking_signals': c.get('ranking_signals') or {},
                                }, variant),
                                float(c.get('semantic_score') or 0),
                            ), reverse=True)
                        rerank_ms = (time.perf_counter() - start) * 1000
                        files = unique_files(ordered)
                        file_rank = files.index(expected) + 1 if expected in files else None
                        sym_rank = symbol_rank(ordered, expected, expected_symbol)
                        v = {'file_rank': file_rank, 'symbol_chunk_rank': sym_rank,
                             'file_top_10': files[:10], 'offline_sort_ms': round(rerank_ms, 3)}
                        if export_candidates:
                            v['ranked_chunks'] = [{
                                'file': normalized((c.get('metadata') or {}).get('file')),
                                'symbol': (c.get('metadata') or {}).get('symbol'),
                                'qualified_symbol': (c.get('metadata') or {}).get('qualified_symbol'),
                                'symbol_type': (c.get('metadata') or {}).get('symbol_type'),
                                'start_line': (c.get('metadata') or {}).get('start_line'),
                                'end_line': (c.get('metadata') or {}).get('end_line'),
                                'baseline_score': c.get('score'),
                                'ranking_signals': c.get('ranking_signals'),
                                'adjustment': round(evidence_score(case['query'], {
                                    **(c.get('metadata') or {}),
                                    'ranking_signals': c.get('ranking_signals') or {},
                                }, variant), 6),
                            } for c in ordered]
                        row['variants'][variant] = v
                    rows.append(row)
                    print(f'  {project["id"]}: baseline={row["variants"]["baseline"]["file_rank"]} '
                          f'lexical_discount={row["variants"]["lexical_discount"]["file_rank"]} '
                          f'candidates={len(baseline)} | {case["query"][:60]}', flush=True)
    summary = {}
    for variant in ('baseline', 'structural', 'lexical_discount'):
        rs = [{'rank': r['variants'][variant]['file_rank']} for r in rows]
        values = metrics(rs, 'rank')
        labeled = [r['variants'][variant]['symbol_chunk_rank'] for r in rows if r.get('expected_symbol')]
        values['symbol_labeled_cases'] = len(labeled)
        values['symbol_chunk_hit_at_1'] = mean(v == 1 for v in labeled) if labeled else None
        values['symbol_chunk_mrr'] = mean(1 / v if v else 0 for v in labeled) if labeled else None
        summary[variant] = values
    return {'version': 'v13.19', 'scope': 'identical complete production-scored candidates, offline reordering only',
            'limitations': ['Same-project results are in-sample; test on independent repositories.',
                            'This is chunk-level reordering with file rank defined by first occurrence.',
                            'Symbol metrics require independently reviewed expected_symbol labels.',
                            'Offline sorting time excludes full production reranking and embedding.',
                            'Temporary Chroma may leave locked files on Windows until process exit.'],
            'repository_isolation': True, 'repositories': repo_info, 'summary': summary, 'results': rows}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--chunk-k', type=int, default=100)
    parser.add_argument('--no-export-candidates', action='store_true')
    args = parser.parse_args()
    if args.chunk_k < 1:
        parser.error('--chunk-k must be >= 1')
    report = evaluate(json.loads(args.manifest.read_text(encoding='utf-8')),
                      chunk_k=args.chunk_k, export_candidates=not args.no_export_candidates)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False, default=str), encoding='utf-8')
    for variant, value in report['summary'].items():
        print(variant, value)
    print('Repository isolation: PASS')
    print('Report:', args.output)


if __name__ == '__main__':
    main()
