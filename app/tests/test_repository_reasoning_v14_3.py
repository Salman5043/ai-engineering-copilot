"""Tests for app/scripts/repository_reasoning_v14_3.py."""
from app.scripts.repository_reasoning_v14_3 import reason
import pytest


def fixture():
    return {
        'definitions': [
            {'file':'api.py','qualified_symbol':'handle_request','start_line':3,'kind':'function'},
            {'file':'service.py','qualified_symbol':'generate_report','start_line':8,'kind':'function'},
            {'file':'service.py','qualified_symbol':'helper','start_line':20,'kind':'function'}],
        'resolved_calls': [
            {'source_file':'api.py','caller':'handle_request','target_file':'service.py','target_symbol':'generate_report','line':5,'expression':'generate_report','confidence':'static','evidence':'direct_name_or_import'}],
        'imports': [{'file':'api.py','target':'service','imported_name':'generate_report','line':1,'internal':True}]
    }


def test_path_evidence_and_import_separation():
    r = reason(fixture(), 'How does request generate report?', source='api.py::handle_request', target='service.py::generate_report')
    assert r['path_query']['found']
    assert r['path_query']['paths'][0]['edges'][0]['line'] == 5
    assert r['internal_import_evidence'][0]['kind'] == 'import_not_call'


def test_retrieval_hints_do_not_create_edges():
    r = reason(fixture(), 'unrelated', {'results':[{'metadata':{'file_path':'service.py'}}]})
    assert r['retrieval_hint_files'] == ['service.py']
    assert r['path_query'] is None


def test_no_invented_path():
    r = reason(fixture(), 'report', source='service.py::helper', target='api.py::handle_request')
    assert not r['path_query']['found']


def test_unknown_symbol_rejected():
    with pytest.raises(ValueError):
        reason(fixture(), 'report', source='unknown.py::x', target='api.py::handle_request')


def test_cycle_is_bounded():
    data = fixture()
    data['resolved_calls'].append({'source_file':'service.py','caller':'generate_report','target_file':'api.py','target_symbol':'handle_request','line':9})
    r = reason(data, 'report', source='api.py::handle_request', target='service.py::helper')
    assert not r['path_query']['found']
