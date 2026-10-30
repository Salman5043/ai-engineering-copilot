import json
from pathlib import Path
from app.scripts.evaluate_reasoning_v14_9_1 import run

CASES = [{'id': 'c1', 'repository_id': 'repo', 'question': 'A to B?', 'intent': 'general_search',
          'evidence': [{'file': 'a.py', 'content': 'def a(): pass'}], 'expected_files': ['a.py']}]

def enrich(**kwargs):
    return kwargs['evidence'] + [{'file': 'a.py', 'content': 'edge A -> B'}]

def test_complete_and_skip_on_resume(tmp_path):
    output = tmp_path / 'output.json'
    calls = []
    def answer(**kwargs):
        calls.append(kwargs)
        return 'answer'
    first = run(cases=CASES, reports={}, output=output, enrich=enrich, answer_fn=answer)
    assert first['summary']['answers_completed'] == 2
    assert first['summary']['complete_pairs'] == 1
    second = run(cases=CASES, reports={}, output=output, resume_from=output,
                 enrich=enrich, answer_fn=answer)
    assert len(calls) == 2
    assert second['resume_status'] == 'complete'

def test_rate_limit_pauses_and_resumes(tmp_path):
    output = tmp_path / 'output.json'
    calls = []
    def fail_once(**kwargs):
        calls.append(1)
        if len(calls) == 2:
            raise RuntimeError('429 rate_limit_exceeded')
        return 'ok'
    first = run(cases=CASES, reports={}, output=output, enrich=enrich, answer_fn=fail_once)
    assert first['resume_status'] == 'paused_rate_limit'
    assert first['summary']['answers_completed'] == 1
    second = run(cases=CASES, reports={}, output=output, resume_from=output,
                 enrich=enrich, answer_fn=fail_once)
    assert second['summary']['answers_completed'] == 2
    assert second['summary']['llm_errors'] == 0
    assert len(calls) == 3

def test_max_requests(tmp_path):
    output = tmp_path / 'output.json'
    first = run(cases=CASES, reports={}, output=output, enrich=enrich,
                answer_fn=lambda **kwargs: 'ok', max_requests=1)
    assert first['resume_status'] == 'paused_max_requests'
    assert first['summary']['answers_pending'] == 1

def test_changed_inputs_refused(tmp_path):
    output = tmp_path / 'output.json'
    run(cases=CASES, reports={}, output=output, enrich=enrich,
        answer_fn=lambda **kwargs: 'ok')
    changed = json.loads(json.dumps(CASES))
    changed[0]['evidence'][0]['content'] = 'different'
    try:
        run(cases=changed, reports={}, output=output, resume_from=output,
            enrich=enrich, answer_fn=lambda **kwargs: 'ok')
    except ValueError as exc:
        assert 'changed' in str(exc)
    else:
        assert False

def test_legacy_partial_resume(tmp_path):
    output = tmp_path / 'legacy.json'
    legacy = run(cases=CASES, reports={}, output=tmp_path/'seed.json', enrich=enrich,
                 answer_fn=lambda **kwargs: 'saved')
    legacy.pop('case_signatures')
    legacy['cases'][0]['enhanced'].pop('answer')
    legacy['cases'][0]['baseline']['answer'] = 'saved'
    output.write_text(json.dumps(legacy))
    calls = []
    def answer(**kwargs):
        calls.append(1)
        return 'new'
    result = run(cases=CASES, reports={}, output=tmp_path/'out.json', resume_from=output,
                 enrich=enrich, answer_fn=answer)
    assert result['cases'][0]['baseline']['answer'] == 'saved'
    assert result['cases'][0]['enhanced']['answer'] == 'new'
    assert len(calls) == 1
