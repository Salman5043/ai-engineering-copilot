"""Resumable paired LLM evaluation. Uses unchanged v14.5 evaluator per case.

Writes atomic checkpoints after each attempted answer; preserves successful answers.
Stops immediately on provider rate limits (no automatic retry).
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import time
from typing import Any, Callable

from app.scripts.evaluate_reasoning_v14_5 import validate_cases, answer_indicators


def _signature(case: dict[str, Any], reports: dict[str, str]) -> str:
    payload = {'case': case, 'reports': reports}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()


def _save(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + '.tmp')
    with temp.open('w', encoding='utf-8') as stream:
        json.dump(value, stream, indent=2, ensure_ascii=False)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temp, path)


def _rate_limited(error: str) -> bool:
    e = error.lower()
    return any(x in e for x in ('ratelimiterror', 'rate_limit_exceeded', 'rate limit reached', 'tokens per day', '429'))


def _summarize(result: dict[str, Any]) -> None:
    rows = result['cases']
    result['summary'] = {
        'cases': len(rows),
        'cases_with_added_architecture_evidence': sum(bool(r['enhanced'].get('added_evidence')) for r in rows),
        'baseline_enrichment_ms_total': round(sum(r['baseline'].get('enrichment_ms', 0) for r in rows), 3),
        'enhanced_enrichment_ms_total': round(sum(r['enhanced'].get('enrichment_ms', 0) for r in rows), 3),
        'llm_errors': sum('error' in r[v] for r in rows for v in ('baseline', 'enhanced')),
        'answers_completed': sum('answer' in r[v] for r in rows for v in ('baseline', 'enhanced')),
        'answers_pending': sum('answer' not in r[v] for r in rows for v in ('baseline', 'enhanced')),
        'complete_pairs': sum(all('answer' in r[v] for v in ('baseline', 'enhanced')) for r in rows),
    }


def run(*, cases: list[dict[str, Any]], reports: dict[str, str], output: Path,
        resume_from: Path | None = None, answer_fn: Callable[..., str] | None = None,
        enrich: Callable[..., list[dict[str, Any]]] | None = None,
        max_requests: int | None = None) -> dict[str, Any]:
    validate_cases(cases)
    if max_requests is not None and max_requests < 0:
        raise ValueError('max_requests must be nonnegative')
    if answer_fn is None:
        from app.agent.reasoner import generate_reasoned_answer
        answer_fn = generate_reasoned_answer
    previous = None
    if resume_from is not None:
        previous = json.loads(resume_from.read_text(encoding='utf-8-sig'))
        if previous.get('mode') != 'paired_llm_replay':
            raise ValueError('Resume file must contain paired_llm_replay results')
        old = previous.get('cases', [])
        if len(old) != len(cases) or [r.get('id') for r in old] != [c['id'] for c in cases]:
            raise ValueError('Resume case IDs/order differ from input; refusing to mix results')
        signatures = previous.get('case_signatures')
        if signatures is not None and signatures != {c['id']: _signature(c, reports) for c in cases}:
            raise ValueError('Input evidence/reports changed since checkpoint')
        # Legacy v14.5 file lacks signatures: verify its available identity and evidence counts.
        if signatures is None:
            for c, r in zip(cases, old):
                for field, expected in [('repository_id', c['repository_id']), ('question', c['question']),
                                        ('intent', c.get('intent', 'general_search'))]:
                    if r.get(field) != expected:
                        raise ValueError(f'Legacy resume mismatch: {c["id"]} {field}')
                if r.get('baseline', {}).get('evidence_count') != len(c['evidence']):
                    raise ValueError(f'Legacy resume evidence count mismatch: {c["id"]}')
    if previous is None:
        # Generate evidence-only rows, preserving the v14.5 baseline/enhanced comparison.
        if enrich is None:
            from app.agent.architecture_context_v14_4 import enrich_evidence
            enrich_fn = enrich_evidence
        else:
            enrich_fn = enrich
        rows = []
        from collections import Counter
        for c in cases:
            start = time.perf_counter()
            base = copy.deepcopy(c['evidence'])
            baseline_ms = (time.perf_counter() - start) * 1000
            start = time.perf_counter()
            enhanced = enrich_fn(repository_id=c['repository_id'], query=c['question'],
                                 evidence=copy.deepcopy(base), reports=reports)
            enhanced_ms = (time.perf_counter() - start) * 1000
            if not isinstance(enhanced, list) or not all(isinstance(x, dict) for x in enhanced):
                raise ValueError('Enrichment must return evidence dictionaries')
            remaining = Counter(json.dumps(x, sort_keys=True, default=str) for x in base)
            added = []
            for item in enhanced:
                key = json.dumps(item, sort_keys=True, default=str)
                if remaining[key]:
                    remaining[key] -= 1
                else:
                    added.append(item)
            if any(remaining.values()):
                raise ValueError('Enrichment removed or changed original evidence')
            rows.append({'id': c['id'], 'repository_id': c['repository_id'],
                         'question': c['question'], 'intent': c.get('intent', 'general_search'),
                         'expected_files': c.get('expected_files', []),
                         'required_facts_for_manual_review': c.get('required_facts', []),
                         'baseline': {'evidence_count': len(base), 'enrichment_ms': round(baseline_ms, 3)},
                         'enhanced': {'evidence_count': len(enhanced),
                                      'enrichment_ms': round(enhanced_ms, 3), 'added_evidence': added}})
        result = {'schema_version': '14.9.1', 'mode': 'paired_llm_replay',
                  'methodology': 'Same pre-collected evidence; architecture enrichment differs.',
                  'limitations': ['No retrieval or tool execution is measured.',
                                  'Human review is required for answer correctness.'],
                  'cases': rows}
    else:
        result = copy.deepcopy(previous)
    result['schema_version'] = '14.9.1'
    result['case_signatures'] = {c['id']: _signature(c, reports) for c in cases}
    result['resume_status'] = 'running'
    _summarize(result)
    _save(output, result)
    requests = 0
    for case, row in zip(cases, result['cases']):
        # For legacy resume, reconstruct exactly the enhanced evidence that was used.
        # We verify the additions by regenerating evidence via v14.5; no LLM calls here.
        if enrich is None:
            from app.agent.architecture_context_v14_4 import enrich_evidence
            enrich_fn = enrich_evidence
        else:
            enrich_fn = enrich
        for variant in ('baseline', 'enhanced'):
            if 'answer' in row[variant]:
                continue
            if max_requests is not None and requests >= max_requests:
                result['resume_status'] = 'paused_max_requests'
                _summarize(result)
                _save(output, result)
                return result
            if variant == 'baseline':
                evidence = copy.deepcopy(case['evidence'])
            else:
                evidence = enrich_fn(repository_id=case['repository_id'], query=case['question'],
                                     evidence=copy.deepcopy(case['evidence']), reports=reports)
                # Refuse to compare answers against a different architecture snapshot.
                original = row['enhanced'].get('added_evidence', [])
                base_serial = [json.dumps(x, sort_keys=True, default=str) for x in case['evidence']]
                from collections import Counter
                remaining = Counter(base_serial)
                additions = []
                for item in evidence:
                    key = json.dumps(item, sort_keys=True, default=str)
                    if remaining[key]:
                        remaining[key] -= 1
                    else:
                        additions.append(item)
                if any(remaining.values()) or additions != original:
                    raise ValueError(f'Architecture evidence changed for {case["id"]}; refusing resume')
            started = time.perf_counter()
            requests += 1
            try:
                answer = str(answer_fn(query=case['question'], intent=row['intent'], evidence=evidence))
                row[variant]['answer'] = answer
                row[variant]['indicators'] = answer_indicators(answer, row['expected_files'])
                row[variant].pop('error', None)
            except Exception as exc:
                error = f'{type(exc).__name__}: {exc}'
                row[variant]['error'] = error
                if _rate_limited(error):
                    result['resume_status'] = 'paused_rate_limit'
            row[variant]['llm_ms'] = round((time.perf_counter() - started) * 1000, 3)
            _summarize(result)
            _save(output, result)
            if result.get('resume_status') == 'paused_rate_limit':
                return result
    result['resume_status'] = 'complete'
    _summarize(result)
    _save(output, result)
    return result


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--cases', required=True)
    p.add_argument('--reports', required=True)
    p.add_argument('--output', required=True)
    p.add_argument('--resume-from', help='Existing v14.5 or v14.9.1 paired LLM JSON')
    p.add_argument('--max-requests', type=int, help='Optional cap on new LLM requests this run')
    args = p.parse_args()
    reports = json.loads(args.reports if args.reports.strip().startswith('{') else Path(args.reports).read_text(encoding='utf-8-sig'))
    cases = json.loads(Path(args.cases).read_text(encoding='utf-8-sig'))
    result = run(cases=cases, reports=reports, output=Path(args.output),
                 resume_from=Path(args.resume_from) if args.resume_from else None,
                 max_requests=args.max_requests)
    print(json.dumps({'output': args.output, 'resume_status': result['resume_status'],
                      **result['summary']}, indent=2))

if __name__ == '__main__':
    main()
