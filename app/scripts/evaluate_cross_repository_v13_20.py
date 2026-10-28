"""v13.20 cross-repository, paired ranking validation.

Runs the existing v13.19 complete-candidate evaluator without modifying production.
Manifest entries need id, path, split ('development' or 'holdout'), and cases.
Holdout cases should have independently reviewed expected_file and expected_symbol.
No automatic claims of independence are made: the split is supplied by the user.
"""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from statistics import mean

from app.scripts.evaluate_full_candidate_v13_19 import evaluate

VARIANTS = ('baseline', 'structural', 'lexical_discount')


def safe_rate(values):
    return mean(values) if values else None


def summarize(rows, variant):
    ranked = [r['variants'][variant] for r in rows]
    ranks = [v['file_rank'] for v in ranked]
    labeled = [v['symbol_chunk_rank'] for r, v in zip(rows, ranked) if r.get('expected_symbol')]
    return {
        'cases': len(rows),
        'file_hit_at_1': safe_rate([r == 1 for r in ranks]),
        'file_hit_at_5': safe_rate([r is not None and r <= 5 for r in ranks]),
        'file_hit_at_10': safe_rate([r is not None and r <= 10 for r in ranks]),
        'file_mrr': safe_rate([1 / r if r else 0 for r in ranks]),
        'symbol_labeled_cases': len(labeled),
        'symbol_chunk_hit_at_1': safe_rate([r == 1 for r in labeled]),
        'symbol_chunk_mrr': safe_rate([1 / r if r else 0 for r in labeled]),
    }


def paired(rows, candidate='lexical_discount'):
    changes = []
    for r in rows:
        a = r['variants']['baseline']
        b = r['variants'][candidate]
        old = a['file_rank']
        new = b['file_rank']
        old_sym = a['symbol_chunk_rank']
        new_sym = b['symbol_chunk_rank']
        changes.append({
            'repository': r['repository'], 'query': r['query'],
            'expected_file': r['expected_file'], 'expected_symbol': r.get('expected_symbol'),
            'baseline_file_rank': old, 'experimental_file_rank': new,
            'file_hit1_improved': old != 1 and new == 1,
            'file_hit1_regressed': old == 1 and new != 1,
            'baseline_symbol_chunk_rank': old_sym,
            'experimental_symbol_chunk_rank': new_sym,
            'symbol_hit1_improved': bool(r.get('expected_symbol')) and old_sym != 1 and new_sym == 1,
            'symbol_hit1_regressed': bool(r.get('expected_symbol')) and old_sym == 1 and new_sym != 1,
        })
    return {
        'file_hit1_improvements': sum(x['file_hit1_improved'] for x in changes),
        'file_hit1_regressions': sum(x['file_hit1_regressed'] for x in changes),
        'symbol_hit1_improvements': sum(x['symbol_hit1_improved'] for x in changes),
        'symbol_hit1_regressions': sum(x['symbol_hit1_regressed'] for x in changes),
        'changed_cases': [x for x in changes if x['baseline_file_rank'] != x['experimental_file_rank'] or (x['expected_symbol'] and x['baseline_symbol_chunk_rank'] != x['experimental_symbol_chunk_rank'])],
    }


def validate_manifest(manifest):
    repos = manifest.get('repositories') or []
    if not repos:
        raise ValueError('Manifest requires repositories')
    ids = set()
    for p in repos:
        rid = p.get('id')
        if not isinstance(rid, str) or not rid.strip() or rid in ids:
            raise ValueError(f'Invalid or duplicate repository id: {rid!r}')
        ids.add(rid)
        if p.get('split') not in {'development', 'holdout'}:
            raise ValueError(f'{rid}: split must be development or holdout')
        if not p.get('path') or not p.get('cases'):
            raise ValueError(f'{rid}: path and nonempty cases are required')
        seen = set()
        for c in p['cases']:
            for key in ('query', 'expected_file'):
                if not isinstance(c.get(key), str) or not c[key].strip():
                    raise ValueError(f'{rid}: missing {key}')
            if c['query'].casefold() in seen:
                raise ValueError(f'{rid}: duplicate query: {c["query"]}')
            seen.add(c['query'].casefold())
            if c.get('expected_symbol') is not None and not isinstance(c['expected_symbol'], str):
                raise ValueError(f'{rid}: expected_symbol must be a string')
    return repos


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--chunk-k', type=int, default=100)
    parser.add_argument('--no-export-candidates', action='store_true')
    args = parser.parse_args()
    if args.chunk_k < 1:
        parser.error('--chunk-k must be >= 1')
    manifest = json.loads(args.manifest.read_text(encoding='utf-8'))
    projects = validate_manifest(manifest)
    split_by_id = {p['id']: p['split'] for p in projects}
    report = evaluate(manifest, chunk_k=args.chunk_k, export_candidates=not args.no_export_candidates)
    for row in report['results']:
        row['split'] = split_by_id[row['repository']]
    buckets = defaultdict(list)
    for row in report['results']:
        buckets['all'].append(row)
        buckets[row['split']].append(row)
        buckets[f"repository:{row['repository']}"].append(row)
    summaries = {}
    for group, rows in buckets.items():
        summaries[group] = {
            'variants': {v: summarize(rows, v) for v in VARIANTS},
            'paired_lexical_discount': paired(rows),
        }
    holdout_repos = [p for p in projects if p['split'] == 'holdout']
    holdout_rows = buckets.get('holdout', [])
    symbol_labeled = sum(bool(r.get('expected_symbol')) for r in holdout_rows)
    status = {
        'holdout_repository_count': len(holdout_repos),
        'holdout_case_count': len(holdout_rows),
        'holdout_symbol_labeled_cases': symbol_labeled,
        'has_at_least_two_holdout_repositories': len(holdout_repos) >= 2,
        'all_holdout_cases_symbol_labeled': bool(holdout_rows) and symbol_labeled == len(holdout_rows),
        'production_ready': False,
        'reason': 'This diagnostic cannot certify independent labeling, representative sampling, or production readiness.',
    }
    report.update({
        'version': 'v13.20',
        'validation_status': status,
        'grouped_summary': summaries,
        'limitations': report.get('limitations', []) + [
            'Development/holdout designation is supplied by the manifest and not independently verified.',
            'Symbol hit@1 measures first ranked chunk, not first unique file.',
            'No changes to production ranking or index.',
            'Results from the same repository are correlated; do not treat cases as independent samples.',
        ],
    })
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False, default=str), encoding='utf-8')
    for group, value in summaries.items():
        base = value['variants']['baseline']
        exp = value['variants']['lexical_discount']
        p = value['paired_lexical_discount']
        print(f'{group}: n={base["cases"]} baseline_hit1={base["file_hit_at_1"]:.3f} '
              f'experiment_hit1={exp["file_hit_at_1"]:.3f} '
              f'improved={p["file_hit1_improvements"]} regressed={p["file_hit1_regressions"]} '
              f'symbol_labels={exp["symbol_labeled_cases"]}', flush=True)
    print('Validation status:', status)
    print('Report:', args.output)


if __name__ == '__main__':
    main()
