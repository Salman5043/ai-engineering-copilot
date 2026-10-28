from pathlib import Path
import pytest
from app.scripts.repository_architecture_v14_0 import analyze


def test_cross_module_import_and_symbols(tmp_path: Path):
    pkg = tmp_path / 'demo'
    pkg.mkdir()
    (pkg / '__init__.py').write_text('')
    (pkg / 'logic.py').write_text('def calculate():\n    return 42\n')
    (pkg / 'api.py').write_text('from .logic import calculate\n\nclass Service:\n    def run(self):\n        return calculate()\n')
    report = analyze(tmp_path)
    assert report['summary']['modules_parsed'] == 3
    assert any(x['internal'] and x['target'] == 'demo.logic' for x in report['imports'])
    assert any(x['qualified_symbol'] == 'Service.run' for x in report['definitions'])
    assert any(x['callee_expression'] == 'calculate' for x in report['calls'])


def test_excludes_virtualenv_and_records_syntax_errors(tmp_path: Path):
    (tmp_path / '.venv').mkdir()
    (tmp_path / '.venv' / 'ignored.py').write_text('def ignored(): pass')
    (tmp_path / 'bad.py').write_text('def broken(:')
    report = analyze(tmp_path)
    assert report['summary']['python_files_discovered'] == 1
    assert report['summary']['errors'] == 1


def test_no_external_symlink_traversal(tmp_path: Path):
    outside = tmp_path.parent / 'outside_private.py'
    outside.write_text('PRIVATE = True\n', encoding='utf-8')
    try:
        (tmp_path / 'external.py').symlink_to(outside)
    except (OSError, NotImplementedError) as exc:
        pytest.skip(f'Symlink creation unavailable in this environment: {exc}')
    assert analyze(tmp_path)['summary']['python_files_discovered'] == 0
