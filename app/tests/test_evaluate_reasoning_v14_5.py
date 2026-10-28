from __future__ import annotations
import json
import pytest
from app.scripts.evaluate_reasoning_v14_5 import evaluate, validate_cases, answer_indicators


def cases():
    return [{'id':'c1','repository_id':'repoA','question':'How does handler call worker?',
             'evidence':[{'file':'pkg/api.py','content':'def handler(): return worker()'}],
             'expected_files':['pkg/api.py'], 'required_facts':['handler calls worker']}]


def fake_enrich(*, repository_id, query, evidence, reports):
    mapping = reports
    if repository_id in mapping:
        return evidence + [{'file':'pkg/api.py','content':'STATIC CALL EVIDENCE'}]
    return evidence


def test_evidence_only_and_environment_restoration(monkeypatch):
    monkeypatch.setenv('COPILOT_ARCHITECTURE_REPORTS_JSON', '{"inherited":"x"}')
    result = evaluate(cases(), reports={'repoA':'report.json'}, enrich=fake_enrich)
    assert result['mode'] == 'evidence_only'
    assert result['summary']['cases_with_added_architecture_evidence'] == 1
    assert result['cases'][0]['baseline']['evidence_count'] == 1
    assert result['cases'][0]['enhanced']['evidence_count'] == 2
    assert __import__('os').environ['COPILOT_ARCHITECTURE_REPORTS_JSON'] == '{"inherited":"x"}'


def test_llm_replay_receives_same_original_evidence():
    calls = []
    def fake_answer(*, query, intent, evidence):
        calls.append([x['content'] for x in evidence])
        return 'pkg/api.py:4 handler calls worker; static evidence is possible.'
    result = evaluate(cases(), reports={'repoA':'report.json'}, run_llm=True,
                      enrich=fake_enrich, answer_fn=fake_answer)
    assert len(calls) == 2
    assert calls[0] == ['def handler(): return worker()']
    assert len(calls[1]) == 2
    assert result['cases'][0]['enhanced']['indicators']['contains_line_reference']


def test_repo_isolation():
    result = evaluate(cases(), reports={'another':'report.json'}, enrich=fake_enrich)
    assert result['summary']['cases_with_added_architecture_evidence'] == 0


def test_duplicate_id_rejected():
    with pytest.raises(ValueError, match='Duplicate'):
        validate_cases(cases() + cases())


def test_invalid_evidence_rejected():
    c = cases()
    c[0]['evidence'] = 'not a list'
    with pytest.raises(ValueError, match='evidence'):
        validate_cases(c)


def test_indicators_not_correctness_claim():
    indicators = answer_indicators('pkg/api.py:9', ['pkg/api.py'])
    assert indicators['expected_file_mention_recall'] == 1.0
    assert 'correctness' not in indicators


def test_env_restored_after_failure(monkeypatch):
    monkeypatch.delenv('COPILOT_ARCHITECTURE_REPORTS_JSON', raising=False)
    def fail(**kwargs):
        raise RuntimeError('boom')
    with pytest.raises(RuntimeError):
        evaluate(cases(), reports={'repoA':'report.json'}, enrich=fail)
    assert 'COPILOT_ARCHITECTURE_REPORTS_JSON' not in __import__('os').environ


def test_reordered_evidence_is_not_counted_as_added():
    def reordered(*, repository_id, query, evidence, reports):
        return list(reversed(evidence))
    result = evaluate(cases(), reports={}, enrich=reordered)
    assert result['cases'][0]['enhanced']['added_evidence'] == []


def test_enrichment_cannot_remove_original_evidence():
    def remove(*, repository_id, query, evidence, reports):
        return []
    with pytest.raises(ValueError, match='removed or changed'):
        evaluate(cases(), reports={}, enrich=remove)


def test_placeholder_evidence_rejected():
    c = cases()
    c[0]['evidence'][0]['content'] = 'Example placeholder: source code'
    with pytest.raises(ValueError, match='placeholder'):
        validate_cases(c)
