import json
from pathlib import Path

from app.agent.architecture_context_v14_4 import enrich_evidence


def _report(tmp_path):
    report = {
        'definitions': [
            {'file': 'pkg/a.py', 'qualified_symbol': 'caller', 'kind': 'function', 'start_line': 1},
            {'file': 'pkg/b.py', 'qualified_symbol': 'callee', 'kind': 'function', 'start_line': 1},
            {'file': 'pkg/c.py', 'qualified_symbol': 'other', 'kind': 'function', 'start_line': 1},
        ],
        'resolved_calls': [
            {'source_file': 'pkg/a.py', 'caller': 'caller', 'target_file': 'pkg/b.py',
             'target_symbol': 'callee', 'line': 8, 'confidence': 'static'},
            {'source_file': 'pkg/a.py', 'caller': 'caller', 'target_file': 'pkg/c.py',
             'target_symbol': 'other', 'line': 9, 'confidence': 'static'},
        ],
    }
    path = tmp_path / 'report.json'
    path.write_text(json.dumps(report), encoding='utf-8')
    return {'any-repository': str(path)}


def test_exact_edge_without_retrieved_file(tmp_path):
    result = enrich_evidence(repository_id='any-repository',
        query='What call from pkg/a.py::caller to pkg/b.py::callee?',
        evidence=[{'file': 'unrelated.py', 'content': 'x'}],
        max_edges=1, reports=_report(tmp_path))
    assert len(result) == 2
    assert 'pkg/a.py::caller -> pkg/b.py::callee' in result[-1]['content']


def test_budget_prioritizes_exact_edge(tmp_path):
    result = enrich_evidence(repository_id='any-repository',
        query='pkg/a.py::caller to pkg/b.py::callee',
        evidence=[{'file': 'pkg/a.py', 'content': 'x'}],
        max_edges=1, reports=_report(tmp_path))
    assert len(result) == 2
    assert 'pkg/b.py::callee' in result[-1]['content']


def test_no_unverified_negative_claim(tmp_path):
    result = enrich_evidence(repository_id='any-repository',
        query='pkg/b.py::callee to pkg/a.py::caller',
        evidence=[{'file': 'unrelated.py', 'content': 'x'}],
        reports=_report(tmp_path))
    assert len(result) == 1


def test_unconfigured_repository_unchanged(tmp_path):
    original = [{'file': 'pkg/a.py', 'content': 'x'}]
    result = enrich_evidence(repository_id='unknown', query='pkg/a.py::caller',
        evidence=original, reports=_report(tmp_path))
    assert result == original and result is not original


def test_no_mutation(tmp_path):
    original = [{'file': 'pkg/a.py', 'content': 'x'}]
    enrich_evidence(repository_id='any-repository',
        query='pkg/a.py::caller to pkg/b.py::callee',
        evidence=original, reports=_report(tmp_path))
    assert original == [{'file': 'pkg/a.py', 'content': 'x'}]


def test_no_contextual_edge_from_unretrieved_file(tmp_path):
    result = enrich_evidence(repository_id='any-repository',
        query='How does caller work?',
        evidence=[{'file': 'unrelated.py', 'content': 'x'}],
        reports=_report(tmp_path))
    assert len(result) == 1


def test_zero_budget(tmp_path):
    result = enrich_evidence(repository_id='any-repository',
        query='pkg/a.py::caller to pkg/b.py::callee',
        evidence=[{'file': 'pkg/a.py'}], max_edges=0, reports=_report(tmp_path))
    assert len(result) == 1
