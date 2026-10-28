from __future__ import annotations
import json

from app.agent.architecture_context_v14_4 import enrich_evidence


def _report():
    return {
        'definitions': [
            {'file':'pkg/api.py','qualified_symbol':'handle_request','start_line':2,'kind':'function'},
            {'file':'pkg/service.py','qualified_symbol':'build_response','start_line':3,'kind':'function'},
        ],
        'resolved_calls': [
            {'source_file':'pkg/api.py','caller':'handle_request',
             'target_file':'pkg/service.py','target_symbol':'build_response',
             'line':8,'expression':'build_response','confidence':'static','evidence':'direct_name_or_import'}
        ],
        'imports': [],
    }


def test_disabled_preserves_evidence(monkeypatch):
    monkeypatch.delenv('COPILOT_ARCHITECTURE_REPORTS_JSON', raising=False)
    original = [{'file':'pkg/api.py','content':'handle_request()'}]
    result = enrich_evidence(repository_id='repoA',query='handle request',evidence=original)
    assert result == original
    assert result is not original


def test_repo_isolation(monkeypatch, tmp_path):
    path = tmp_path / 'report.json'
    path.write_text(json.dumps(_report()), encoding='utf-8')
    monkeypatch.setenv('COPILOT_ARCHITECTURE_REPORTS_JSON', json.dumps({'repoA':str(path)}))
    original = [{'file':'pkg/api.py','content':'handle_request()'}]
    assert enrich_evidence(repository_id='repoB',query='handle request',evidence=original) == original


def test_adds_bounded_provenance(monkeypatch, tmp_path):
    path = tmp_path / 'report.json'
    path.write_text(json.dumps(_report()), encoding='utf-8')
    monkeypatch.setenv('COPILOT_ARCHITECTURE_REPORTS_JSON', json.dumps({'repoA':str(path)}))
    original = [{'file':'pkg/api.py','content':'handle_request()'}]
    result = enrich_evidence(repository_id='repoA',query='handle request',evidence=original)
    assert len(result) == 2
    assert result[1]['start_line'] == 8
    assert result[1]['source_tool'] == 'architecture_v14_4'
    assert 'not verified runtime' in result[1]['content']
    assert len(original) == 1
    assert len(enrich_evidence(repository_id='repoA',query='handle request',evidence=original,max_edges=0)) == 1


def test_requires_retrieved_file_overlap(monkeypatch, tmp_path):
    path = tmp_path / 'report.json'
    path.write_text(json.dumps(_report()), encoding='utf-8')
    monkeypatch.setenv('COPILOT_ARCHITECTURE_REPORTS_JSON', json.dumps({'repoA':str(path)}))
    original = [{'file':'unrelated/other.py','content':'some code'}]
    assert enrich_evidence(repository_id='repoA',query='handle request',evidence=original) == original
