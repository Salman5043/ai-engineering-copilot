"""v13.11 fine-grained profiling regression tests."""
import json
from types import SimpleNamespace
from app.retrieval import lexical_retriever as lr


def test_detailed_profile_preserves_results(monkeypatch, tmp_path):
    class Collection:
        def get(self, **kwargs):
            return {
                'documents': ['retry retryConfig implementation', 'another unrelated document'],
                'metadatas': [
                    {'file': 'src/retry.py', 'symbol': 'retryConfig', 'symbol_type': 'function'},
                    {'file': 'src/other.py', 'symbol': 'other', 'symbol_type': 'class'},
                ],
            }
    monkeypatch.setattr(lr, 'get_collection', lambda: Collection())
    query = SimpleNamespace(raw_query='retry implementation', keywords=['retry'],
                            identifiers=['retryConfig'], definition_targets=['retry'])
    monkeypatch.delenv('COPILOT_LEXICAL_PROFILE_JSONL', raising=False)
    baseline = lr.lexical_search(repository_id='test-repo', parsed_query=query)
    destination = tmp_path / 'profile.jsonl'
    monkeypatch.setenv('COPILOT_LEXICAL_PROFILE_JSONL', str(destination))
    actual = lr.lexical_search(repository_id='test-repo', parsed_query=query)
    assert actual == baseline
    data = json.loads(destination.read_text().strip())
    detail = data['candidate_detail_ms']
    assert data['candidate_count'] == 2
    assert set(detail) == {'query_preparation_ms', 'candidate_tokenization_ms',
                           'candidate_score_core_ms', 'phrase_matching_ms', 'other_candidate_ms'}
    assert all(value >= 0 for value in detail.values())
    assert abs(sum(detail.values()) - data['candidate_scoring_ms']) < 0.02
