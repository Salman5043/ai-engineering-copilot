import pytest
from app.scripts.evaluate_answer_quality_v14_8 import initialize, score


def fixtures():
    comparison = {'cases': [{'id': 'c1', 'question': 'does A call B?',
                             'baseline': {'answer': 'maybe'},
                             'enhanced': {'answer': 'static edge A -> B', 'added_evidence': []}}]}
    dataset = [{'id': 'c1', 'question': 'does A call B?', 'expected_files': ['a.py'],
                'required_facts': ['A calls B']}]
    return comparison, dataset


def test_init_does_not_claim_correctness():
    r = initialize(*fixtures())
    assert r['cases'][0]['reviews']['enhanced']['correctness'] is None
    assert score(r)['automatic_answer_correctness'] is None


def test_score_empty_review():
    r = initialize(*fixtures())
    s = score(r)
    assert s['paired_human_reviewed'] == 0
    assert s['variants']['baseline']['correct_rate_among_reviewed'] is None


def test_reviewed_win():
    r = initialize(*fixtures())
    for variant, verdict in [('baseline', 'incorrect'), ('enhanced', 'correct')]:
        x = r['cases'][0]['reviews'][variant]
        x.update(correctness=verdict, grounding='fully_supported',
                 unsupported_runtime_claim=False, required_facts_met=True,
                 source_locations_checked=['a.py:10'], review_notes='Checked static edge')
    s = score(r)
    assert s['enhanced_correctness_wins'] == 1
    assert s['net_correctness_wins'] == 1


def test_incomplete_review_rejected():
    r = initialize(*fixtures())
    r['cases'][0]['reviews']['baseline']['correctness'] = 'correct'
    with pytest.raises(ValueError):
        score(r)


def test_unmatched_id_rejected():
    comparison, dataset = fixtures()
    comparison['cases'][0]['id'] = 'other'
    with pytest.raises(ValueError):
        initialize(comparison, dataset)


def test_missing_answer_not_reviewed():
    comparison, dataset = fixtures()
    comparison['cases'][0]['baseline'] = {}
    r = initialize(comparison, dataset)
    assert score(r)['variants']['baseline']['answers_available'] == 0
