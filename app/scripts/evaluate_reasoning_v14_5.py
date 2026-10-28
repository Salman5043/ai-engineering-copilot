"""v14.5 paired evaluation: replay identical investigation evidence with/without architecture.

Input cases JSON: [{"id": "case1", "repository_id": "repo1", "question": "...",
 "evidence": [{"file": "pkg/api.py", "start_line": 1, "content": "..."}],
 "intent": "general_search", "expected_files": ["pkg/api.py"],
 "required_facts": ["optional human-judged fact"]}]

Default is evidence-only (no LLM calls). --run-llm invokes the existing agent
reasoner twice per case; it may incur API charges. No retrieval or indexing runs.
"""
from __future__ import annotations
import argparse
import copy
import json
from pathlib import Path
import re
from collections import Counter
import time
from typing import Any, Callable


def validate_cases(data: Any) -> list[dict[str, Any]]:
    if not isinstance(data, list) or not data:
        raise ValueError('Cases must be a non-empty JSON array')
    ids = set()
    for index, case in enumerate(data):
        if not isinstance(case, dict):
            raise ValueError(f'Case {index} must be an object')
        for key in ('id', 'repository_id', 'question'):
            if not isinstance(case.get(key), str) or not case[key].strip():
                raise ValueError(f'Case {index}: missing {key}')
        if case['id'] in ids:
            raise ValueError(f'Duplicate case ID: {case["id"]}')
        ids.add(case['id'])
        if not isinstance(case.get('evidence'), list) or not all(isinstance(x, dict) for x in case['evidence']):
            raise ValueError(f'Case {case["id"]}: evidence must be a list of objects')
        if not case['evidence']:
            raise ValueError(f'Case {case["id"]}: provide at least one real retrieved evidence record')
        if any('placeholder' in str(e.get('content', '')).lower() for e in case['evidence']):
            raise ValueError(f'Case {case["id"]}: replace placeholder evidence with real source code')
        for field in ('expected_files', 'required_facts'):
            if field in case and (not isinstance(case[field], list) or not all(isinstance(x, str) for x in case[field])):
                raise ValueError(f'Case {case["id"]}: {field} must be a list of strings')
    return data


def normalize_file(value: str) -> str:
    return value.replace('\\', '/').removeprefix('./')


def answer_indicators(answer: str, expected_files: list[str]) -> dict[str, Any]:
    """Transparent diagnostics, NOT correctness/faithfulness metrics."""
    normalized = answer.replace('\\', '/')
    matched = [p for p in expected_files if normalize_file(p) in normalized]
    return {
        'answer_characters': len(answer),
        'expected_file_mentions': len(matched),
        'expected_file_count': len(expected_files),
        'expected_file_mention_recall': round(len(matched) / len(expected_files), 4) if expected_files else None,
        'contains_line_reference': bool(re.search(r'(?i)(?:\.py:\d+|\bline(?:s)?\s+\d+)', answer)),
        'mentions_static_uncertainty': bool(re.search(r'(?i)\b(static|possible|not verified|cannot confirm|not guaranteed)\b', answer)),
    }


def evaluate(
    cases: list[dict[str, Any]], *, reports: dict[str, str],
    run_llm: bool = False,
    enrich: Callable[..., list[dict[str, Any]]] | None = None,
    answer_fn: Callable[..., str] | None = None,
) -> dict[str, Any]:
    """Compare the same evidence; no retriever changes, no agent tool calls.

    Injection points allow tests to avoid importing application dependencies.
    """
    validate_cases(cases)
    if not isinstance(reports, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in reports.items()):
        raise ValueError('reports must map repository IDs to report paths')
    if enrich is None:
        from app.agent.architecture_context_v14_4 import enrich_evidence
        enrich = enrich_evidence
    if run_llm and answer_fn is None:
        from app.agent.reasoner import generate_reasoned_answer
        answer_fn = generate_reasoned_answer
    output = []
    for case in cases:
        base = copy.deepcopy(case['evidence'])
        question, repo = case['question'], case['repository_id']
        t0 = time.perf_counter()
        baseline_evidence = copy.deepcopy(base)
        baseline_enrich_ms = (time.perf_counter() - t0) * 1000
        t1 = time.perf_counter()
        # Call the v14.4 enrichment with an explicit report map. No process-wide
        # environment mutation; suitable for concurrent evaluators.
        enhanced_evidence = enrich(
            repository_id=repo, query=question, evidence=copy.deepcopy(base),
            reports=reports,
        )
        enhanced_enrich_ms = (time.perf_counter() - t1) * 1000
        if not isinstance(enhanced_evidence, list) or not all(isinstance(x, dict) for x in enhanced_evidence):
            raise ValueError(f'Case {case["id"]}: enrichment must return a list of evidence dictionaries')
        # Multiset difference works even if enrichment reorders original records.
        remaining = Counter(json.dumps(e, sort_keys=True, default=str) for e in base)
        added = []
        for item in enhanced_evidence:
            key = json.dumps(item, sort_keys=True, default=str)
            if remaining[key]:
                remaining[key] -= 1
            else:
                added.append(item)
        if any(remaining.values()):
            raise ValueError(f'Case {case["id"]}: enrichment removed or changed original evidence')
        row: dict[str, Any] = {
            'id': case['id'], 'repository_id': repo, 'question': question,
            'intent': case.get('intent', 'general_search'),
            'expected_files': case.get('expected_files', []),
            'required_facts_for_manual_review': case.get('required_facts', []),
            'baseline': {'evidence_count': len(baseline_evidence), 'enrichment_ms': round(baseline_enrich_ms, 3)},
            'enhanced': {'evidence_count': len(enhanced_evidence), 'enrichment_ms': round(enhanced_enrich_ms, 3),
                         'added_evidence': added},
        }
        if run_llm:
            for label, evidence in [('baseline', baseline_evidence), ('enhanced', enhanced_evidence)]:
                t2 = time.perf_counter()
                try:
                    answer = answer_fn(query=question, intent=row['intent'], evidence=evidence)
                    row[label]['answer'] = str(answer)
                    row[label]['indicators'] = answer_indicators(str(answer), row['expected_files'])
                except Exception as exc:
                    row[label]['error'] = f'{type(exc).__name__}: {exc}'
                row[label]['llm_ms'] = round((time.perf_counter() - t2) * 1000, 3)
        output.append(row)
    return {
        'schema_version': '14.5', 'mode': 'paired_llm_replay' if run_llm else 'evidence_only',
        'methodology': 'Same pre-collected evidence and question; only architecture enrichment differs. LLM answers may be nondeterministic.',
        'limitations': [
            'No retrieval, agent planning, or tool execution is measured.',
            'File mentions and line references are proxies, not correctness or grounding scores.',
            'Manual source-code review is required for correctness, unsupported claims, completeness and required facts.',
            'LLM output may vary between runs; repeat trials for reliable comparisons.',
        ],
        'cases': output,
        'summary': {
            'cases': len(output),
            'cases_with_added_architecture_evidence': sum(bool(r['enhanced']['added_evidence']) for r in output),
            'baseline_enrichment_ms_total': round(sum(r['baseline']['enrichment_ms'] for r in output), 3),
            'enhanced_enrichment_ms_total': round(sum(r['enhanced']['enrichment_ms'] for r in output), 3),
            'llm_errors': sum('error' in r[variant] for r in output for variant in ('baseline', 'enhanced')),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cases', required=True, help='JSON list of cases containing already-collected evidence')
    parser.add_argument('--reports', required=True, help='JSON object mapping repository IDs to v14.1 report paths, or path to JSON file')
    parser.add_argument('--output', required=True)
    parser.add_argument('--run-llm', action='store_true', help='Call existing LLM twice per case; may incur charges')
    args = parser.parse_args()
    raw_reports = args.reports.strip()
    reports = json.loads(
        raw_reports
        if raw_reports.startswith("{")
        else Path(raw_reports).read_text(encoding="utf-8-sig")
    )
    cases = json.loads(Path(args.cases).read_text(encoding='utf-8'))
    result = evaluate(cases, reports=reports, run_llm=args.run_llm)
    target = Path(args.output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print(json.dumps({'output': str(target), 'mode': result['mode'], **result['summary']}, indent=2))


if __name__ == '__main__':
    main()
