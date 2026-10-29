import json
from app.agent.architecture_context_v14_4 import enrich_evidence


def _mapping(tmp_path):
    defs = [{'file': f'pkg/{name}.py', 'qualified_symbol': name,
             'kind': 'function', 'start_line': 1} for name in 'abcde']
    calls = [
        {'source_file': 'pkg/a.py', 'caller': 'a', 'target_file': 'pkg/b.py', 'target_symbol': 'b', 'line': 8},
        {'source_file': 'pkg/a.py', 'caller': 'a', 'target_file': 'pkg/b.py', 'target_symbol': 'b', 'line': 12},
        {'source_file': 'pkg/a.py', 'caller': 'a', 'target_file': 'pkg/c.py', 'target_symbol': 'c', 'line': 15},
        {'source_file': 'pkg/d.py', 'caller': 'd', 'target_file': 'pkg/e.py', 'target_symbol': 'e', 'line': 21},
    ]
    p = tmp_path / 'report.json'
    p.write_text(json.dumps({'definitions': defs, 'resolved_calls': calls}), encoding='utf8')
    return {'repo': str(p)}


def test_exact_edge_survives_one_edge_budget(tmp_path):
    r = enrich_evidence(repository_id='repo', query='pkg/a.py::a to pkg/b.py::b',
                        evidence=[{'file': 'pkg/d.py', 'content': 'x'}],
                        max_edges=1, reports=_mapping(tmp_path))
    assert len(r) == 2
    assert 'pkg/a.py::a -> pkg/b.py::b' in r[-1]['content']


def test_duplicate_sites_collapse(tmp_path):
    r = enrich_evidence(repository_id='repo', query='pkg/a.py::a to pkg/b.py::b',
                        evidence=[{'file': 'pkg/a.py', 'content': 'x'}],
                        max_edges=8, reports=_mapping(tmp_path))
    edges = [e for e in r if e.get('symbol_type') == 'static_call_relationship']
    assert sum('pkg/a.py::a -> pkg/b.py::b' in e['content'] for e in edges) == 1
    assert next(e for e in edges if 'pkg/b.py::b' in e['content'])['start_line'] == 8


def test_contextual_never_leaks_unretrieved_file(tmp_path):
    r = enrich_evidence(repository_id='repo', query='Explain function a',
                        evidence=[{'file': 'pkg/a.py', 'content': 'x'}],
                        reports=_mapping(tmp_path))
    assert all(e['file'] == 'pkg/a.py' for e in r)


def test_source_tool_backward_compatible(tmp_path):
    r = enrich_evidence(repository_id='repo', query='pkg/a.py::a to pkg/b.py::b',
                        evidence=[{'file': 'pkg/a.py', 'content': 'x'}],
                        reports=_mapping(tmp_path))
    assert all(e['source_tool'] == 'architecture_v14_4' for e in r[1:])


def test_original_input_unchanged(tmp_path):
    original = [{'file': 'pkg/a.py', 'content': 'x'}]
    enrich_evidence(repository_id='repo', query='pkg/a.py::a to pkg/b.py::b',
                    evidence=original, reports=_mapping(tmp_path))
    assert original == [{'file': 'pkg/a.py', 'content': 'x'}]


def test_budget_zero(tmp_path):
    original = [{'file': 'pkg/a.py', 'content': 'x'}]
    assert enrich_evidence(repository_id='repo', query='pkg/a.py::a to pkg/b.py::b',
                           evidence=original, max_edges=0, reports=_mapping(tmp_path)) == original
