"""Read-only, repository-agnostic Python architecture inventory.

Run: python -m app.scripts.repository_architecture_v14_0 --root PATH --output architecture.json
No external dependencies, no network calls, and no repository writes.
"""
from __future__ import annotations

import argparse
import ast
import json
import os
from collections import Counter
from pathlib import Path

SKIP_DIRS = {'.git', '.venv', 'venv', 'env', '__pycache__', 'node_modules', '.tox', '.mypy_cache', '.pytest_cache', 'dist', 'build', '.ruff_cache'}


def _dotted_path(path: Path) -> str:
    parts = list(path.with_suffix('').parts)
    if parts and parts[-1] == '__init__':
        parts.pop()
    return '.'.join(parts)


def _resolve_import(module: str, level: int, imported: str | None, is_package: bool) -> str:
    if level == 0:
        return imported or ''
    parts = module.split('.') if module else []
    if not is_package:
        parts = parts[:-1]
    up = level - 1
    parts = parts[:max(0, len(parts) - up)]
    return '.'.join([*parts, *([imported] if imported else [])])


def _name(expr: ast.AST) -> str | None:
    if isinstance(expr, ast.Name):
        return expr.id
    if isinstance(expr, ast.Attribute):
        base = _name(expr.value)
        return f'{base}.{expr.attr}' if base else None
    return None


class _Definitions(ast.NodeVisitor):
    def __init__(self, file: str):
        self.file = file
        self.stack: list[str] = []
        self.definitions: list[dict] = []
        self.calls: list[dict] = []

    def _enter(self, node: ast.AST, kind: str):
        qualified = '.'.join([*self.stack, node.name])
        self.definitions.append({'file': self.file, 'symbol': node.name,
                                 'qualified_symbol': qualified, 'kind': kind,
                                 'start_line': node.lineno, 'end_line': getattr(node, 'end_lineno', node.lineno)})
        self.stack.append(node.name)
        self.generic_visit(node)
        self.stack.pop()

    def visit_ClassDef(self, node):
        self._enter(node, 'class')

    def visit_FunctionDef(self, node):
        self._enter(node, 'method' if self.stack else 'function')

    def visit_AsyncFunctionDef(self, node):
        self._enter(node, 'async_method' if self.stack else 'async_function')

    def visit_Call(self, node):
        target = _name(node.func)
        if target:
            self.calls.append({'file': self.file, 'caller': '.'.join(self.stack) or '<module>',
                               'callee_expression': target, 'line': node.lineno,
                               'resolution': 'unresolved_static_expression'})
        self.generic_visit(node)


def analyze(root: Path, max_files: int = 20000, max_bytes: int = 2_000_000) -> dict:
    root = root.resolve(strict=True)
    if not root.is_dir():
        raise ValueError(f'Not a directory: {root}')
    files: list[Path] = []
    for directory, dirs, names in os.walk(root, followlinks=False):
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS and not (Path(directory) / d).is_symlink())
        for name in sorted(names):
            path = Path(directory) / name
            if name.endswith('.py') and not path.is_symlink():
                files.append(path)
                if len(files) > max_files:
                    raise ValueError(f'Python file limit exceeded ({max_files})')
    modules = {_dotted_path(p.relative_to(root)): p for p in files}
    result = {'schema_version': '14.0', 'root': str(root), 'modules': [], 'definitions': [],
              'imports': [], 'calls': [], 'errors': [], 'summary': {},
              'limitations': ['Calls are syntactic expressions, not proven runtime edges.',
                              'Dynamic imports, decorators, monkeypatching, and type inference are not resolved.',
                              'External dependencies are not indexed.']}
    for module, path in sorted(modules.items()):
        rel = path.relative_to(root).as_posix()
        try:
            if path.stat().st_size > max_bytes:
                result['errors'].append({'file': rel, 'reason': 'size_limit'})
                continue
            tree = ast.parse(path.read_text(encoding='utf-8-sig'), filename=rel)
        except (SyntaxError, UnicodeError, OSError, ValueError) as exc:
            result['errors'].append({'file': rel, 'reason': type(exc).__name__})
            continue
        visitor = _Definitions(rel)
        visitor.visit(tree)
        result['modules'].append({'module': module, 'file': rel})
        result['definitions'].extend(visitor.definitions)
        result['calls'].extend(visitor.calls)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    target = alias.name
                    result['imports'].append({'file': rel, 'source_module': module, 'target': target,
                                              'imported_name': None, 'line': node.lineno,
                                              'internal': target in modules or any(m.startswith(target + '.') for m in modules)})
            elif isinstance(node, ast.ImportFrom):
                base = _resolve_import(module, node.level, node.module, path.name == '__init__.py')
                for alias in node.names:
                    target = base + '.' + alias.name if base else alias.name
                    internal = target in modules or base in modules or any(m.startswith(base + '.') for m in modules)
                    result['imports'].append({'file': rel, 'source_module': module, 'target': base,
                                              'imported_name': alias.name, 'line': node.lineno,
                                              'internal': internal})
    result['summary'] = {'python_files_discovered': len(files), 'modules_parsed': len(result['modules']),
                         'definitions': len(result['definitions']), 'imports': len(result['imports']),
                         'internal_imports': sum(i['internal'] for i in result['imports']),
                         'syntactic_calls': len(result['calls']), 'errors': len(result['errors']),
                         'definition_kinds': dict(sorted(Counter(d['kind'] for d in result['definitions']).items()))}
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--max-files', type=int, default=20000)
    args = parser.parse_args()
    report = analyze(args.root, max_files=args.max_files)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')
    print(json.dumps(report['summary'], indent=2))
    print('Report:', args.output)


if __name__ == '__main__':
    main()
