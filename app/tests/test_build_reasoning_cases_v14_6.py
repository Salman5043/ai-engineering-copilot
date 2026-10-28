from app.scripts.build_reasoning_cases_v14_6 import build_cases, _evidence
import pytest


def report():
    return {
        'definitions': [
            {'file': 'pkg/a.py', 'qualified_symbol': 'start', 'start_line': 1},
            {'file': 'pkg/b.py', 'qualified_symbol': 'finish', 'start_line': 2},
            {'file': 'pkg/a.py', 'qualified_symbol': 'helper', 'start_line': 3},
        ],
        'resolved_calls': [
            {'source_file': 'pkg/a.py', 'caller': 'start', 'target_file': 'pkg/b.py', 'target_symbol': 'finish', 'line': 8},
            {'source_file': 'pkg/a.py', 'caller': 'start', 'target_file': 'pkg/a.py', 'target_symbol': 'helper', 'line': 9},
            {'source_file': 'pkg/a.py', 'caller': '<module>', 'target_file': 'pkg/b.py', 'target_symbol': 'finish', 'line': 10},
        ],
    }


def retriever(**kwargs):
    return {'results': [{'content': 'def start(): return 1', 'metadata': {'file': 'pkg/a.py', 'start_line': 1, 'repository_id': kwargs['repository_id']}}]}


def test_generates_v145_compatible_cases():
    cases, meta = build_cases(report(), repository_id='r1', retrieve_fn=retriever, max_cases=3)
    assert len(cases) == 3
    assert {c['review_metadata']['category'] for c in cases} == {'cross_file_call', 'direct_call', 'no_direct_static_edge'}
    assert all(c['evidence'][0]['repository_id'] == 'r1' for c in cases)
    assert meta['valid_static_edges'] == 2


def test_reproducible():
    a, _ = build_cases(report(), repository_id='r1', retrieve_fn=retriever)
    b, _ = build_cases(report(), repository_id='r1', retrieve_fn=retriever)
    assert a == b


def test_empty_evidence_skipped():
    cases, meta = build_cases(report(), repository_id='r1', retrieve_fn=lambda **kw: {'results': []})
    assert cases == []
    assert meta['skipped']


def test_repository_isolation():
    with pytest.raises(ValueError, match='another repository'):
        _evidence({'results': [{'content': 'code', 'metadata': {'file': 'x.py', 'repository_id': 'other'}}]}, 'r1', 5)


def test_bad_args():
    with pytest.raises(ValueError):
        build_cases(report(), repository_id='', retrieve_fn=retriever)


def test_metadata_normalization_and_dedup():
    data = {'results': [{'content': 'def x(): pass', 'metadata': {'file': 'pkg\\x.py', 'start_line': 2}}] * 2}
    assert len(_evidence(data, 'r', 5)) == 1
    assert _evidence(data, 'r', 5)[0]['file'] == 'pkg/x.py'


def test_no_fabricated_runtime_claims():
    cases, _ = build_cases(report(), repository_id='r1', retrieve_fn=retriever)
    assert all('runtime execution verified' not in c['question'] for c in cases)
    assert all(c['review_metadata']['requires_human_review'] for c in cases)
