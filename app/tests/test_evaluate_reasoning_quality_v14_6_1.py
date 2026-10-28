from app.scripts.evaluate_reasoning_quality_v14_6_1 import evaluate, symbols

def sample(label='resolved_static_call', include=True):
    src='src/a.py::alpha'; dst='src/b.py::beta'
    return ({'cases':[{'id':'one','question':f'What relationship exists between {src} and {dst}?',
        'baseline':{'answer':'No evidence of a call.'},
        'enhanced':{'answer':'alpha directly calls beta.', 'added_evidence':[
            {'content':f'STATIC CALL EVIDENCE (not verified runtime execution): {src} -> {dst}; confidence=static;'}] if include else []}}]},
        [{'id':'one','review_metadata':{'structural_reference':{'relationship':label,'source':src,'target':dst}}}])

def test_symbols():
    assert symbols('x/a.py::hello to x/b.py::world') == ['x/a.py::hello','x/b.py::world']

def test_exact_edge():
    c,d=sample(); r=evaluate(c,d)
    assert r['summary']['resolved_edge_cases_with_exact_edge_in_enrichment']==1

def test_missing_edge_flag():
    c,d=sample(include=False); r=evaluate(c,d)
    assert 'expected_resolved_edge_missing_from_enrichment' in r['cases'][0]['review_flags']

def test_negative_reference_not_counted_positive():
    c,d=sample(label='no_direct_resolved_edge', include=False); r=evaluate(c,d)
    assert r['summary']['resolved_edge_cases']==0

def test_no_ground_truth_not_scored():
    c,_=sample(); r=evaluate(c)
    assert r['summary']['automatic_answer_correctness'] is None
    assert 'structural_reference_not_supplied' in r['cases'][0]['review_flags']

def test_empty_answers():
    c,d=sample(); c['cases'][0]['baseline']={}; r=evaluate(c,d)
    assert 'baseline_missing_answer' in r['cases'][0]['review_flags']

def test_overclaim_flag():
    c,d=sample(); c['cases'][0]['enhanced']['answer']='No other dynamic paths are involved.'
    assert 'enhanced_possible_overclaim_review' in evaluate(c,d)['cases'][0]['review_flags']
