"""v13.15: evaluate lexical retrieval against actual local Python repositories.

No downloads, index mutation, embeddings, or full-pipeline claims. Gold labels
must be supplied by a human, ideally without inspecting retrieval results.

Example:
 uv run python -m app.scripts.evaluate_real_repositories_v13_15 \
   --manifest data/evaluation/v13_15_manifest.json \
   --output data/evaluation/v13_15_results.json --top-k 10
"""
from __future__ import annotations

import argparse
import ast
import json
import time
from collections import defaultdict
from pathlib import Path
from statistics import mean
from unittest.mock import patch

SKIP_DIRS = {'.git', '.venv', 'venv', '__pycache__', '.tox', '.mypy_cache', '.pytest_cache', 'node_modules', 'build', 'dist'}
MAX_FILE_BYTES = 1_000_000


def extract_records(root: Path, max_files: int = 2000) -> tuple[list[tuple[str, str, str, str]], dict]:
    """Create deterministic AST symbol records from real on-disk Python code."""
    root = root.resolve(strict=True)
    if not root.is_dir():
        raise ValueError(f'Not a directory: {root}')
    records = []
    stats = {'files_scanned': 0, 'files_skipped': 0, 'syntax_errors': 0, 'records': 0}
    candidates = sorted(p for p in root.rglob('*.py') if not any(x in SKIP_DIRS for x in p.relative_to(root).parts[:-1]))
    for path in candidates:
        if stats['files_scanned'] >= max_files:
            stats['files_skipped'] += 1
            continue
        if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_FILE_BYTES:
            stats['files_skipped'] += 1
            continue
        stats['files_scanned'] += 1
        rel = path.relative_to(root).as_posix()
        try:
            source = path.read_text(encoding='utf-8-sig')
            tree = ast.parse(source, filename=rel)
        except (UnicodeError, SyntaxError, OSError):
            stats['syntax_errors'] += 1
            continue
        lines = source.splitlines(keepends=True)
        # Includes module-level code and module docstring for discovery.
        records.append((rel, path.stem, 'module', source[:15000]))
        def walk(body, owner=''):
            for node in body:
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    name = f'{owner}.{node.name}' if owner else node.name
                    kind = 'class' if isinstance(node, ast.ClassDef) else ('async_function' if isinstance(node, ast.AsyncFunctionDef) else 'function')
                    start = min([node.lineno] + [d.lineno for d in getattr(node, 'decorator_list', [])])
                    end = getattr(node, 'end_lineno', node.lineno)
                    records.append((rel, name, kind, ''.join(lines[start - 1:end])))
                    if isinstance(node, ast.ClassDef):
                        walk(node.body, name)
        walk(tree.body)
    stats['records'] = len(records)
    return records, stats


class LocalCollection:
    def __init__(self, records_by_id):
        self.records_by_id = records_by_id
        self.calls = []

    def get(self, *, where, include):
        if set(where) != {'repository_id'}:
            raise AssertionError('Missing repository isolation filter')
        if not {'documents', 'metadatas'} <= set(include):
            raise AssertionError('Missing required collection fields')
        repo = where['repository_id']
        self.calls.append(repo)
        rows = self.records_by_id.get(repo, [])
        return {'documents': [r[3] for r in rows], 'metadatas': [
            {'file': r[0], 'symbol': r[1], 'symbol_type': r[2], 'language': 'python', 'repository_id': repo}
            for r in rows]}


def evaluate(manifest: dict, top_k: int = 10, max_files: int = 2000) -> dict:
    if top_k < 1 or max_files < 1:
        raise ValueError('top_k and max_files must be positive')
    from app.retrieval import lexical_retriever
    from app.retrieval.query_parser import parse_query

    projects = manifest.get('repositories', [])
    if not projects or not isinstance(projects, list):
        raise ValueError('manifest.repositories must be a nonempty list')
    ids = [p['id'] for p in projects]
    if len(set(ids)) != len(ids):
        raise ValueError('Repository IDs must be unique')
    rows_by_id, metadata = {}, {}
    for p in projects:
        rows_by_id[p['id']], metadata[p['id']] = extract_records(Path(p['path']), max_files=max_files)
        if not p.get('cases'):
            raise ValueError(f'Repository {p["id"]} needs independently labeled cases')
    collection = LocalCollection(rows_by_id)
    results = []
    with patch.object(lexical_retriever, 'get_collection', return_value=collection):
        for p in projects:
            for case in p['cases']:
                expected = case['expected_file'].replace('\\', '/')
                if expected.startswith('/') or '..' in Path(expected).parts:
                    raise ValueError('expected_file must be repository-relative')
                if expected not in {r[0] for r in rows_by_id[p['id']]}:
                    raise ValueError(f'Gold file absent from indexed records: {p["id"]}/{expected}')
                start = time.perf_counter()
                found = lexical_retriever.lexical_search(
                    repository_id=p['id'], parsed_query=parse_query(case['query']),
                    top_k=top_k, language='python')
                elapsed = (time.perf_counter() - start) * 1000
                returned = [str(x['metadata']['file']).replace('\\', '/') for x in found]
                if any(x['metadata'].get('repository_id') != p['id'] for x in found):
                    raise AssertionError('Cross-repository result leaked')
                rank = returned.index(expected) + 1 if expected in returned else None
                results.append({'repository': p['id'], 'query': case['query'],
                                'expected_file': expected, 'returned_files': returned,
                                'rank': rank, 'hit_at_1': rank == 1, 'hit_at_k': rank is not None,
                                'reciprocal_rank': 1 / rank if rank else 0, 'latency_ms': elapsed})
    def summarize(items):
        return {'cases': len(items), 'file_hit_at_1': mean(x['hit_at_1'] for x in items),
                'file_hit_at_k': mean(x['hit_at_k'] for x in items),
                'file_mrr': mean(x['reciprocal_rank'] for x in items),
                'mean_latency_ms': mean(x['latency_ms'] for x in items)}
    return {'version': 'v13.15', 'scope': 'real-local-repository AST-derived lexical retrieval only',
            'limitations': ['Not full indexing/vector/hybrid/reranking pipeline',
                            'Gold labels require independent human review',
                            'AST records are a benchmark adapter, not production index chunks'],
            'top_k': top_k, 'overall': summarize(results),
            'per_repository': {rid: {**summarize([x for x in results if x['repository'] == rid]), **metadata[rid]} for rid in ids},
            'repository_isolation': True, 'results': results}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--top-k', type=int, default=10)
    parser.add_argument('--max-files', type=int, default=2000)
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text(encoding='utf-8'))
    report = evaluate(manifest, top_k=args.top_k, max_files=args.max_files)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print('v13.15 real-local-repository lexical evaluation')
    for repo, item in report['per_repository'].items():
        print(f'  {repo}: n={item["cases"]}, hit@1={item["file_hit_at_1"]:.1%}, hit@{args.top_k}={item["file_hit_at_k"]:.1%}, MRR={item["file_mrr"]:.3f}, files={item["files_scanned"]}')
    print('Overall:', report['overall'])
    print('Repository isolation: PASS')
    print('Report:', args.output)


if __name__ == '__main__':
    main()
