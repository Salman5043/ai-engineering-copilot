"""v14.8: source-grounded, human-reviewed paired answer evaluation.

No retrieval, model calls, or automatic correctness assertions. Use --init to
create review records, edit verdicts after inspecting source, then --score.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from collections import Counter

VERDICTS = ('correct', 'partially_correct', 'incorrect', 'insufficient_evidence')
SUPPORT = ('fully_supported', 'partially_supported', 'unsupported', 'insufficient_evidence')


def initialize(comparison: dict, dataset: list[dict]) -> dict:
    if not isinstance(comparison.get('cases'), list) or not isinstance(dataset, list):
        raise ValueError('Expected comparison.cases and dataset list')
    by_id = {c['id']: c for c in dataset}
    if len(by_id) != len(dataset):
        raise ValueError('Duplicate dataset case IDs')
    rows = []
    seen = set()
    for case in comparison['cases']:
        cid = case['id']
        if cid in seen or cid not in by_id:
            raise ValueError(f'Duplicate or unmatched comparison case: {cid}')
        seen.add(cid)
        reference = by_id[cid]
        reviews = {}
        for variant in ('baseline', 'enhanced'):
            answer = case.get(variant, {}).get('answer')
            reviews[variant] = {
                'answer': answer if isinstance(answer, str) else None,
                'correctness': None, 'grounding': None,
                'unsupported_runtime_claim': None,
                'required_facts_met': None,
                'source_locations_checked': [],
                'review_notes': '',
            }
        rows.append({
            'id': cid, 'question': case.get('question', reference.get('question')),
            'expected_files': reference.get('expected_files', []),
            'required_facts': reference.get('required_facts', []),
            'structural_reference': reference.get('review_metadata', {}),
            'added_architecture_evidence': case.get('enhanced', {}).get('added_evidence', []),
            'reviews': reviews,
        })
    return {'schema_version': '14.8', 'method': 'human_source_review',
            'instructions': [
                'Open the actual source files and architecture report; dataset expectations are review aids, not ground truth.',
                'For each answer set correctness to correct/partially_correct/incorrect/insufficient_evidence.',
                'Set grounding to fully_supported/partially_supported/unsupported/insufficient_evidence.',
                'Set unsupported_runtime_claim to true/false and required_facts_met to true/false, or leave null when unreviewed.',
                'Record inspected file:line references in source_locations_checked and explain judgments in review_notes.',
                'Static call resolution does not prove runtime execution; absence of a static edge does not prove no runtime path.',
            ], 'cases': rows}


def score(review: dict) -> dict:
    if review.get('schema_version') != '14.8' or not isinstance(review.get('cases'), list):
        raise ValueError('Expected v14.8 review document')
    totals = {}
    for variant in ('baseline', 'enhanced'):
        answered = reviewed = 0
        correctness = Counter()
        grounding = Counter()
        runtime_flags = 0
        facts_met = 0
        for case in review['cases']:
            r = case['reviews'][variant]
            if not isinstance(r.get('answer'), str):
                continue
            answered += 1
            c, g = r.get('correctness'), r.get('grounding')
            if c is None and g is None and r.get('unsupported_runtime_claim') is None and r.get('required_facts_met') is None:
                continue
            if c not in VERDICTS or g not in SUPPORT:
                raise ValueError(f"Incomplete/invalid verdict for {case['id']} {variant}")
            if not isinstance(r.get('unsupported_runtime_claim'), bool) or not isinstance(r.get('required_facts_met'), bool):
                raise ValueError(f"Incomplete boolean review for {case['id']} {variant}")
            if not r.get('source_locations_checked') or not str(r.get('review_notes', '')).strip():
                raise ValueError(f"Missing source inspection/notes for {case['id']} {variant}")
            reviewed += 1
            correctness[c] += 1
            grounding[g] += 1
            runtime_flags += int(r['unsupported_runtime_claim'])
            facts_met += int(r['required_facts_met'])
        totals[variant] = {
            'answers_available': answered, 'human_reviewed': reviewed,
            'correctness_counts': dict(correctness), 'grounding_counts': dict(grounding),
            'unsupported_runtime_claims': runtime_flags, 'required_facts_met': facts_met,
            'correct_rate_among_reviewed': round(correctness['correct']/reviewed, 4) if reviewed else None,
            'fully_grounded_rate_among_reviewed': round(grounding['fully_supported']/reviewed, 4) if reviewed else None,
        }
    paired = []
    for case in review['cases']:
        a, b = case['reviews']['baseline'], case['reviews']['enhanced']
        if a.get('correctness') in VERDICTS and b.get('correctness') in VERDICTS:
            paired.append((a['correctness'], b['correctness']))
    wins = sum(a != 'correct' and b == 'correct' for a, b in paired)
    losses = sum(a == 'correct' and b != 'correct' for a, b in paired)
    return {'schema_version': '14.8', 'cases': len(review['cases']), 'variants': totals,
            'paired_human_reviewed': len(paired), 'enhanced_correctness_wins': wins,
            'enhanced_correctness_losses': losses,
            'net_correctness_wins': wins-losses,
            'automatic_answer_correctness': None,
            'caution': 'Rates cover reviewed answers only; no automated ground-truth or statistical significance claim.'}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument('--init', action='store_true')
    g.add_argument('--score', action='store_true')
    p.add_argument('--comparison')
    p.add_argument('--dataset')
    p.add_argument('--review')
    p.add_argument('--output', required=True)
    args = p.parse_args()
    if args.init:
        if not args.comparison or not args.dataset:
            p.error('--init requires --comparison and --dataset')
        result = initialize(json.loads(Path(args.comparison).read_text(encoding='utf-8')),
                            json.loads(Path(args.dataset).read_text(encoding='utf-8')))
    else:
        if not args.review:
            p.error('--score requires --review')
        result = score(json.loads(Path(args.review).read_text(encoding='utf-8')))
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print(json.dumps({'output': str(out), 'cases': len(result['cases']) if isinstance(result['cases'], list) else result['cases'], 'mode': 'init' if args.init else 'score'}, indent=2))

if __name__ == '__main__':
    main()
