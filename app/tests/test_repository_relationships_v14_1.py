from pathlib import Path
from app.scripts.repository_relationships_v14_1 import resolve


def test_cross_module_calls_and_aliases(tmp_path: Path):
    (tmp_path / 'alpha.py').write_text('def target():\n    return 1\n', encoding='utf-8')
    (tmp_path / 'beta.py').write_text('from alpha import target as run\n\ndef execute():\n    return run()\n', encoding='utf-8')
    result = resolve(tmp_path)
    assert any(c['target_module'] == 'alpha' and c['target_symbol'] == 'target'
               and c['caller'] == 'execute' for c in result['resolved_calls'])
    assert any(d['source'] == 'beta' and d['target'] == 'alpha' for d in result['module_dependencies'])


def test_shadowed_import_does_not_resolve(tmp_path: Path):
    (tmp_path / 'alpha.py').write_text('def target():\n    pass\n', encoding='utf-8')
    (tmp_path / 'beta.py').write_text('from alpha import target\ndef execute(target):\n    target()\n', encoding='utf-8')
    result = resolve(tmp_path)
    assert not any(c['caller'] == 'execute' for c in result['resolved_calls'])


def test_self_method_heuristic(tmp_path: Path):
    (tmp_path / 'alpha.py').write_text('class Engine:\n    def start(self):\n        self.run()\n    def run(self):\n        pass\n', encoding='utf-8')
    result = resolve(tmp_path)
    assert any(c['target_symbol'] == 'Engine.run' and c['confidence'] == 'heuristic'
               for c in result['resolved_calls'])
