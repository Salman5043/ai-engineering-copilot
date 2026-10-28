from app.scripts import repository_paths_v14_2 as module
trace = module.trace

def fixture():
    return {'definitions': [
        {'file': 'a.py', 'qualified_symbol': 'start'},
        {'file': 'b.py', 'qualified_symbol': 'middle'},
        {'file': 'c.py', 'qualified_symbol': 'end'},
    ], 'resolved_calls': [
        {'source_file': 'a.py', 'caller': 'start', 'target_file': 'b.py', 'target_symbol': 'middle', 'line': 10, 'expression': 'middle', 'confidence': 'static'},
        {'source_file': 'b.py', 'caller': 'middle', 'target_file': 'c.py', 'target_symbol': 'end', 'line': 20, 'expression': 'end', 'confidence': 'static'},
        {'source_file': 'c.py', 'caller': 'end', 'target_file': 'a.py', 'target_symbol': 'start', 'line': 30, 'expression': 'start', 'confidence': 'static'},
        {'source_file': 'a.py', 'caller': '<module>', 'target_file': 'c.py', 'target_symbol': 'end', 'line': 1, 'expression': 'end', 'confidence': 'static'},
    ]}


def test_cross_file_path_and_evidence():
    result = trace(fixture(), 'a.py::start', 'c.py::end')
    assert result['found']
    assert result['paths'][0]['nodes'] == ['a.py::start', 'b.py::middle', 'c.py::end']
    assert [e['line'] for e in result['paths'][0]['edges']] == [10, 20]


def test_no_path_with_depth_limit():
    assert not trace(fixture(), 'a.py::start', 'c.py::end', max_depth=1)['found']


def test_cycle_does_not_loop():
    assert trace(fixture(), 'c.py::end', 'b.py::middle', max_depth=5)['found']


def test_unknown_definition_rejected():
    import pytest
    with pytest.raises(ValueError, match='Unknown definition'):
        trace(fixture(), 'a.py::missing', 'c.py::end')
