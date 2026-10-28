"""Conservative, read-only Python module and call relationship resolver.

Usage: python -m app.scripts.repository_relationships_v14_1 --root PATH --output FILE
No network, third-party packages, or changes to analyzed repositories.
"""
from __future__ import annotations
import argparse
import ast
import json
from collections import Counter
from pathlib import Path

from app.scripts.repository_architecture_v14_0 import analyze, _resolve_import


def resolve(root: Path) -> dict:
    inventory = analyze(root)
    root = Path(inventory['root'])
    modules = {x['module']: x['file'] for x in inventory['modules']}
    defs = {(modules_inv, d['qualified_symbol']): d for d in inventory['definitions']
            for modules_inv in [next((m for m, f in modules.items() if f == d['file']), '')]}
    relationships = []
    unresolved = []
    dependencies = []
    for module, file in sorted(modules.items()):
        path = root / file
        tree = ast.parse(path.read_text(encoding='utf-8-sig'), filename=file)
        is_package = path.name == '__init__.py'
        aliases = {}
        for node in tree.body:
            if isinstance(node, ast.Import):
                for alias in node.names:
                    aliases[alias.asname or alias.name.split('.')[0]] = (alias.name if alias.asname else alias.name.split('.')[0], None)
                    if alias.name in modules:
                        dependencies.append({'source': module, 'target': alias.name, 'line': node.lineno, 'kind': 'import'})
            elif isinstance(node, ast.ImportFrom):
                base = _resolve_import(module, node.level, node.module, is_package)
                for alias in node.names:
                    if alias.name == '*':
                        continue
                    candidate = f'{base}.{alias.name}' if base else alias.name
                    if candidate in modules:
                        aliases[alias.asname or alias.name] = (candidate, None)
                        dependencies.append({'source': module, 'target': candidate, 'line': node.lineno, 'kind': 'from_module'})
                    else:
                        aliases[alias.asname or alias.name] = (base, alias.name)
                        if base in modules:
                            dependencies.append({'source': module, 'target': base, 'line': node.lineno, 'kind': 'from_symbol'})

        class Walker(ast.NodeVisitor):
            def __init__(self):
                self.stack = []
                self.shadowed = []

            def visit_ClassDef(self, node):
                self.stack.append(node.name)
                self.shadowed.append(set())
                for child in node.body:
                    self.visit(child)
                self.shadowed.pop()
                self.stack.pop()

            def _function(self, node):
                self.stack.append(node.name)
                bound = {a.arg for a in [*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs]}
                if node.args.vararg: bound.add(node.args.vararg.arg)
                if node.args.kwarg: bound.add(node.args.kwarg.arg)
                # Locals shadow imports throughout function scope (Python compile-time semantics).
                for child in ast.walk(node):
                    if child is node: continue
                    if isinstance(child, ast.Name) and isinstance(child.ctx, (ast.Store, ast.Del)):
                        bound.add(child.id)
                    elif isinstance(child, (ast.Import, ast.ImportFrom)):
                        for a in child.names:
                            bound.add(a.asname or a.name.split('.')[0])
                self.shadowed.append(bound)
                for child in node.body: self.visit(child)
                self.shadowed.pop()
                self.stack.pop()

            visit_FunctionDef = _function
            visit_AsyncFunctionDef = _function

            def visit_Call(self, node):
                expr = node.func
                target = None
                reason = 'dynamic_or_ambiguous'
                if isinstance(expr, ast.Name):
                    name = expr.id
                    if not any(name in scope for scope in self.shadowed):
                        if name in aliases:
                            base, symbol = aliases[name]
                            if symbol and (base, symbol) in defs:
                                target = (base, symbol)
                            else:
                                reason = 'imported_target_not_locally_defined'
                        elif (module, name) in defs:
                            target = (module, name)
                        else:
                            reason = 'not_indexed_or_builtin'
                    else:
                        reason = 'locally_bound_name'
                elif isinstance(expr, ast.Attribute) and isinstance(expr.value, ast.Name):
                    base_name = expr.value.id
                    if base_name in {'self', 'cls'} and len(self.stack) >= 2:
                        candidate = f'{self.stack[-2]}.{expr.attr}'
                        if (module, candidate) in defs:
                            # self/cls may be rebound; treat as likely rather than proven.
                            target = (module, candidate)
                            reason = 'receiver_method_static_heuristic'
                    elif not any(base_name in scope for scope in self.shadowed) and base_name in aliases:
                        base, imported = aliases[base_name]
                        if imported is None and (base, expr.attr) in defs:
                            target = (base, expr.attr)
                        else:
                            reason = 'attribute_target_not_resolved'
                caller = '.'.join(self.stack) or '<module>'
                record = {'source_module': module, 'source_file': file, 'caller': caller,
                          'line': node.lineno, 'expression': ast.unparse(expr)}
                if target:
                    d = defs[target]
                    relationships.append({**record, 'target_module': target[0], 'target_file': d['file'],
                                          'target_symbol': target[1], 'target_line': d['start_line'],
                                          'confidence': 'heuristic' if reason == 'receiver_method_static_heuristic' else 'static',
                                          'evidence': reason if reason == 'receiver_method_static_heuristic' else 'direct_name_or_import'})
                else:
                    unresolved.append({**record, 'reason': reason})
                self.generic_visit(node)
        Walker().visit(tree)
    inventory['schema_version'] = '14.1'
    inventory['module_dependencies'] = dependencies
    inventory['resolved_calls'] = relationships
    inventory['unresolved_calls'] = unresolved
    inventory['relationship_summary'] = {'module_dependencies': len(dependencies),
                                         'resolved_calls': len(relationships),
                                         'unresolved_calls': len(unresolved),
                                         'confidence': dict(Counter(x['confidence'] for x in relationships))}
    inventory['limitations'].extend([
        'Only module-level imports are resolved; imports in nested scopes remain unresolved.',
        'Static call resolution does not prove runtime execution or account for monkeypatching.',
        'Class inheritance, instance type inference, wildcard imports, and dynamic dispatch are not resolved.',
        'Functions and methods with duplicate names in nested scopes may be ambiguous.',
    ])
    return inventory


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', required=True, type=Path)
    p.add_argument('--output', required=True, type=Path)
    args = p.parse_args()
    result = resolve(args.root)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding='utf-8')
    print(json.dumps({'inventory': result['summary'], 'relationships': result['relationship_summary']}, indent=2))
    print('Report:', args.output)


if __name__ == '__main__':
    main()
