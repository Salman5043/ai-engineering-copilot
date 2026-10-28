"""v14.3: evidence-only architecture context for engineering questions.

Consumes v14.1 relationship JSON and optional existing retriever results. Does not
modify retrieval or claim that framework registrations are runtime calls.
"""
from __future__ import annotations
import argparse
from collections import defaultdict, deque
import json
from pathlib import Path
import re

STOP = {'the','and','for','with','from','where','what','which','does','how','this','that','into','when','are','is','to','of','a','an','in','on','it','code','function','file','module'}


def ident(d):
    return f"{d['file']}::{d['qualified_symbol']}"


def tokens(s):
    return {x for x in re.findall(r'[a-z][a-z0-9]*', re.sub(r'([a-z])([A-Z])', r'\1 \2', s).lower().replace('_', ' ')) if x not in STOP and len(x)>1}


def retrieve_hints(data):
    """Accept retriever's {'results': [...]} or a list; treat as hints only."""
    if data is None:
        return set()
    rows = data.get('results', []) if isinstance(data, dict) else data
    if not isinstance(rows, list):
        raise ValueError('retrieval results must be a list')
    hints = set()
    for r in rows:
        if not isinstance(r, dict):
            continue
        for obj in (r, r.get('metadata') or {}):
            for key in ('file_path','relative_path','file','path','source_file'):
                value = obj.get(key)
                if isinstance(value, str):
                    hints.add(value.replace('\\','/').removeprefix('./'))
    return hints


def reason(report, question, retrieval=None, source=None, target=None, max_depth=5, max_paths=5, max_symbols=12):
    if not isinstance(question, str) or not question.strip():
        raise ValueError('question is required')
    if max_depth < 0 or max_paths < 1 or max_symbols < 1:
        raise ValueError('invalid limits')
    definitions = {ident(d): d for d in report.get('definitions', [])}
    hints = retrieve_hints(retrieval)
    query_tokens = tokens(question)
    scores = {}
    for key, d in definitions.items():
        symbol_tokens = tokens(d['qualified_symbol'])
        file_tokens = tokens(d['file'])
        score = 4 * len(query_tokens & symbol_tokens) + len(query_tokens & file_tokens)
        if d['file'] in hints:
            score += 2
        if score:
            scores[key] = score
    ranked = sorted(scores, key=lambda k: (-scores[k], k))[:max_symbols]
    selected = set(ranked)
    if source is not None and source not in definitions:
        raise ValueError(f'Unknown source: {source}')
    if target is not None and target not in definitions:
        raise ValueError(f'Unknown target: {target}')
    if source:
        selected.add(source)
    if target:
        selected.add(target)

    graph = defaultdict(list)
    for r in report.get('resolved_calls', []):
        a = f"{r.get('source_file')}::{r.get('caller')}"
        b = f"{r.get('target_file')}::{r.get('target_symbol')}"
        if a not in definitions or b not in definitions:
            continue
        graph[a].append({'from': a, 'to': b, 'file': r['source_file'], 'line': r['line'],
                         'expression': r.get('expression'), 'confidence': r.get('confidence', 'unknown'),
                         'evidence': r.get('evidence', 'unknown'), 'kind': 'static_call'})
    for a in graph:
        graph[a].sort(key=lambda e: (e['to'], e['line']))

    paths = []
    if source and target:
        queue = deque([(source, [], frozenset([source]))])
        while queue and len(paths) < max_paths:
            current, edges, seen = queue.popleft()
            if current == target:
                paths.append({'nodes': [source]+[e['to'] for e in edges], 'edges': edges})
                continue
            if len(edges) >= max_depth:
                continue
            for edge in graph[current]:
                if edge['to'] not in seen:
                    queue.append((edge['to'], edges+[edge], seen | {edge['to']}))
    else:
        # Expose immediate call evidence around selected symbols, not a guessed path.
        pass

    related = []
    for a, edges in graph.items():
        for e in edges:
            if a in selected or e['to'] in selected:
                related.append(e)
    related.sort(key=lambda e: (e['file'], e['line'], e['from'], e['to']))
    # Import relationships are contextual evidence, never execution edges.
    imports = []
    for i in report.get('imports', []):
        if i.get('internal') and (i.get('file') in {definitions[k]['file'] for k in selected}):
            imports.append({'file': i['file'], 'line': i['line'], 'target_module': i['target'],
                            'imported_name': i.get('imported_name'), 'kind': 'import_not_call'})
    imports.sort(key=lambda i: (i['file'], i['line'], i['target_module']))
    return {
        'schema_version': '14.3', 'question': question,
        'answer_status': 'evidence_only_no_generated_answer',
        'retrieval_hint_files': sorted(hints),
        'matched_symbols': [{'id': k, 'score': scores.get(k, 0), 'file': definitions[k]['file'],
                             'line': definitions[k]['start_line'], 'kind': definitions[k]['kind']}
                            for k in sorted(selected, key=lambda k: (-scores.get(k, 0), k))],
        'related_static_calls': related[:100], 'internal_import_evidence': imports[:100],
        'path_query': {'source': source, 'target': target, 'found': bool(paths), 'paths': paths} if source and target else None,
        'limitations': [
            'Symbol matches are lexical hints, not proof of relevance.',
            'Only v14.1 resolved calls are path edges; imports are not calls.',
            'Framework registrations, callbacks, dependency injection and runtime paths are not inferred.',
            'No path found does not imply no runtime path exists.',
            'This produces structured evidence for a future reasoning agent, not a natural-language answer.'
        ]
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input', required=True, help='v14.1 JSON')
    p.add_argument('--question', required=True)
    p.add_argument('--retrieval', help='Optional existing retriever JSON output')
    p.add_argument('--source', help='Optional file.py::qualified_symbol')
    p.add_argument('--target', help='Optional file.py::qualified_symbol')
    p.add_argument('--max-depth', type=int, default=5)
    p.add_argument('--max-paths', type=int, default=5)
    p.add_argument('--output')
    a = p.parse_args()
    report = json.loads(Path(a.input).read_text(encoding='utf-8'))
    retrieval = json.loads(Path(a.retrieval).read_text(encoding='utf-8')) if a.retrieval else None
    result = reason(report, a.question, retrieval, a.source, a.target, a.max_depth, a.max_paths)
    rendered = json.dumps(result, indent=2, ensure_ascii=False)
    if a.output:
        path = Path(a.output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(rendered+'\n', encoding='utf-8')
    print(json.dumps({'matched_symbols': len(result['matched_symbols']), 'related_static_calls': len(result['related_static_calls']), 'paths': len(result['path_query']['paths']) if result['path_query'] else None, 'output': a.output}, indent=2))


if __name__ == '__main__':
    main()
