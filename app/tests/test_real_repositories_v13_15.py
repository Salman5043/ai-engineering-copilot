"""v13.15: repository-agnostic real-source lexical benchmark tests."""
import pytest
from app.scripts.evaluate_real_repositories_v13_15 import extract_records, evaluate


def _repo(tmp_path, name, source):
    root = tmp_path / name
    root.mkdir()
    (root / 'main.py').write_text(source, encoding='utf-8')
    return root


def test_extracts_real_python_symbols_and_nested_methods(tmp_path):
    root = _repo(tmp_path, 'pkg', 'class Worker:\n    async def consume(self):\n        return 42\n')
    records, stats = extract_records(root)
    assert ('main.py', 'Worker', 'class') in {(r[0], r[1], r[2]) for r in records}
    assert ('main.py', 'Worker.consume', 'async_function') in {(r[0], r[1], r[2]) for r in records}
    assert stats['files_scanned'] == 1


def test_ignores_virtualenv_and_symlinks(tmp_path):
    root = _repo(tmp_path, 'pkg', 'def run(): pass\n')
    hidden = root / '.venv'
    hidden.mkdir()
    (hidden / 'hidden.py').write_text('def secret(): pass\n')
    records, _ = extract_records(root)
    assert all(r[0] == 'main.py' for r in records)


def test_real_code_evaluation_and_repository_isolation(tmp_path):
    a = _repo(tmp_path, 'first', 'def verify_token(token):\n    """Validate JWT signature"""\n    return token\n')
    b = _repo(tmp_path, 'second', 'def normalize_features(frame):\n    """Standardize numeric data"""\n    return frame\n')
    report = evaluate({'repositories': [
        {'id': 'one', 'path': str(a), 'cases': [{'query': 'Where is verify_token defined?', 'expected_file': 'main.py'}]},
        {'id': 'two', 'path': str(b), 'cases': [{'query': 'Where are numeric features standardized?', 'expected_file': 'main.py'}]},
    ]}, top_k=3)
    assert report['overall']['cases'] == 2
    assert report['overall']['file_hit_at_1'] == 1
    assert report['repository_isolation']


def test_rejects_missing_gold_label(tmp_path):
    a = _repo(tmp_path, 'first', 'def hello(): pass\n')
    with pytest.raises(ValueError, match='Gold file absent'):
        evaluate({'repositories': [{'id': 'one', 'path': str(a), 'cases': [
            {'query': 'hello', 'expected_file': 'missing.py'}]}]})


def test_rejects_duplicate_repository_ids(tmp_path):
    a = _repo(tmp_path, 'first', 'def hello(): pass\n')
    p = {'id': 'one', 'path': str(a), 'cases': [{'query': 'hello', 'expected_file': 'main.py'}]}
    with pytest.raises(ValueError, match='unique'):
        evaluate({'repositories': [p, p]})
