"""v13.16: isolated production-index + hybrid retrieval evaluation.

Run from the AI Engineering Copilot project root:
  uv run python -m app.scripts.evaluate_full_pipeline_v13_16 \
    --manifest data/evaluation/v13_15_hard_queries_candidate.json \
    --output data/evaluation/v13_16_full_pipeline.json

Uses a TEMPORARY Chroma directory and leaves the configured production DB alone.
Does not mutate production source files or retrieval logic.
"""
from __future__ import annotations

import argparse
import json
import tempfile
import time
from pathlib import Path
from statistics import mean
from unittest.mock import patch


def unique_files(results, repository_id):
    files = []
    seen = set()
    for result in results:
        meta = result.get('metadata') or {}
        if meta.get('repository_id') != repository_id:
            raise AssertionError(f'Cross-repository result: {meta.get("repository_id")!r} != {repository_id!r}')
        file = str(meta.get('file', '')).replace('\\', '/')
        if file and file not in seen:
            seen.add(file)
            files.append(file)
    return files


def summary(rows, k):
    if not rows:
        return {'cases': 0}
    return {
        'cases': len(rows),
        'file_hit_at_1': mean(r['rank'] == 1 for r in rows),
        f'file_hit_at_{k}': mean(r['rank'] is not None and r['rank'] <= k for r in rows),
        'file_mrr': mean(1 / r['rank'] if r['rank'] else 0 for r in rows),
        'mean_latency_ms': mean(r['latency_ms'] for r in rows),
    }


def evaluate(manifest, top_k=10, chunk_k=100):
    if top_k < 1 or chunk_k < top_k:
        raise ValueError('Require 1 <= top_k <= chunk_k')
    projects = manifest.get('repositories', [])
    if not projects or len({p['id'] for p in projects}) != len(projects):
        raise ValueError('Nonempty repositories with unique ids required')

    from app.config import settings
    from app.ingestion.indexer import index_repository
    from app.retrieval.retriever import retrieve
    from app.retrieval.vector_store import get_collection

    rows = []
    indexed = {}
    # Chroma may keep mmap handles open on Windows after retrieval.
    # Ignore only temporary-directory cleanup errors so the evaluation report
    # can still be written; never delete the user's configured Chroma DB.
    with tempfile.TemporaryDirectory(prefix='copilot-v13-16-', ignore_cleanup_errors=True) as tmp:
        # Patch the singleton settings instance read by vector_store.get_client().
        with patch.object(settings, 'chroma_path', str(Path(tmp) / 'chroma')):
            for project in projects:
                root = Path(project['path']).resolve(strict=True)
                if not root.is_dir():
                    raise ValueError(f'Not a directory: {root}')
                if not project.get('cases'):
                    raise ValueError(f'No labeled cases: {project["id"]}')
                print(f'Indexing {project["id"]}: {root}', flush=True)
                result = index_repository(root)
                rid = result['repository_id']  # production-generated id, not manifest alias
                indexed[project['id']] = {**result, 'manifest_id': project['id']}
                if result['chunks'] < 1:
                    raise ValueError(f'No chunks indexed: {root}')

                # Explicitly verify that repository metadata exists in isolated collection.
                count = len(get_collection().get(where={'repository_id': rid}, include=['metadatas'])['ids'])
                if count == 0:
                    raise AssertionError(f'No indexed records for {rid}')

                for case in project['cases']:
                    expected = str(case['expected_file']).replace('\\', '/')
                    if expected.startswith('/') or '..' in Path(expected).parts:
                        raise ValueError('Expected files must be repository-relative')
                    if not (root / expected).is_file():
                        raise ValueError(f'Expected file does not exist: {root / expected}')
                    start = time.perf_counter()
                    response = retrieve(repository_id=rid, query=case['query'], top_k=chunk_k, language='python')
                    latency = (time.perf_counter() - start) * 1000
                    files = unique_files(response['results'], rid)
                    rank = files.index(expected) + 1 if expected in files else None
                    rows.append({
                        'repository': project['id'], 'query': case['query'],
                        'expected_file': expected, 'rank': rank,
                        'returned_files': files[:top_k], 'latency_ms': latency,
                    })
                    print(f'  rank={rank or "MISS"} {case["query"][:75]}', flush=True)

    return {
        'version': 'v13.16',
        'scope': 'production indexing, embedding, hybrid retrieval and reranking in temporary Chroma DB',
        'top_k_files': top_k, 'retrieved_chunks_per_query': chunk_k,
        'limitations': [
            'Ground-truth labels must be reviewed independently.',
            'The v13.15 lexical baseline uses AST-derived records, whereas this test uses production chunks: scores are not a controlled ablation.',
            'A small repository cannot establish cross-project generalization.',
            'Embedding-model download may be required on first run.',
            'On Windows, Chroma may retain temporary files until the process exits; leftover copilot-v13-16-* directories can be removed after exit.',
        ],
        'overall': summary(rows, top_k),
        'per_repository': {p['id']: {**summary([r for r in rows if r['repository'] == p['id']], top_k), **indexed[p['id']]} for p in projects},
        'repository_isolation': True,
        'results': rows,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--top-k', type=int, default=10)
    parser.add_argument('--chunk-k', type=int, default=100)
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text(encoding='utf-8'))
    report = evaluate(manifest, top_k=args.top_k, chunk_k=args.chunk_k)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print('v13.16 full-pipeline evaluation:', report['overall'])
    print('Repository isolation: PASS')
    print('Report:', args.output)


if __name__ == '__main__':
    main()
