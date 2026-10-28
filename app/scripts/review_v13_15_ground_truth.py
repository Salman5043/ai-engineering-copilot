"""Read-only evidence printer for proposed retrieval labels.

Run from repository root:
  uv run python app/scripts/review_v13_15_ground_truth.py --review data/evaluation/v13_15_hard_queries_review.json
This does not certify labels; a human must review the printed code.
"""
import argparse
import ast
import json
from pathlib import Path


def find_symbol(tree, name):
    return [node for node in ast.walk(tree) if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--review', type=Path, required=True)
    parser.add_argument('--context-lines', type=int, default=8)
    args = parser.parse_args()
    data = json.loads(args.review.read_text(encoding='utf-8'))
    root = Path(data['repository']).resolve(strict=True)
    for i, case in enumerate(data['cases'], 1):
        path = (root / case['expected_file']).resolve(strict=True)
        if not path.is_relative_to(root):
            raise ValueError('Expected file escapes repository')
        src = path.read_text(encoding='utf-8-sig')
        nodes = find_symbol(ast.parse(src, filename=str(path)), case['symbol_to_review'])
        print(f'\n[{i}] QUESTION: {case["query"]}\nFILE: {case["expected_file"]}\nSYMBOL: {case["symbol_to_review"]}')
        if len(nodes) != 1:
            print(f'REVIEW REQUIRED: expected one matching symbol, found {len(nodes)}')
            continue
        node = nodes[0]
        lines = src.splitlines()
        start = max(1, node.lineno - args.context_lines)
        end = min(len(lines), node.end_lineno if node.end_lineno - node.lineno <= 65 else node.lineno + 65)
        for lineno in range(start, end + 1):
            print(f'{lineno:>5} | {lines[lineno - 1]}')
        print('CHECK: Does the implementation support the question? If not, edit/remove this case.')
    print('\nAll labels remain provisional until independently reviewed.')


if __name__ == '__main__':
    main()
