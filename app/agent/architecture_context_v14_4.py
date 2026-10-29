"""Optional, repository-scoped architecture evidence for agent answers.

Configure COPILOT_ARCHITECTURE_REPORTS_JSON as a JSON object mapping repository
IDs to v14.1 report paths. Unconfigured repositories retain old behavior.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

from app.scripts.repository_reasoning_v14_3 import reason


def _report_for(repository_id: str, reports: dict[str, str] | None = None) -> dict[str, Any] | None:
    if reports is None:
        mapping_text = os.getenv('COPILOT_ARCHITECTURE_REPORTS_JSON', '')
        if not mapping_text:
            return None
        mapping = json.loads(mapping_text)
    else:
        mapping = reports
    if not isinstance(mapping, dict):
        raise ValueError('Architecture report configuration must be a JSON object')
    location = mapping.get(repository_id)
    if not isinstance(location, str) or not location:
        return None
    report = json.loads(Path(location).read_text(encoding='utf-8'))
    if not isinstance(report, dict) or not isinstance(report.get('definitions'), list):
        raise ValueError('Invalid v14.1 architecture report')
    return report


# Match explicit file.py::qualified_symbol references, not repository-specific names.
_SYMBOL_REF = re.compile(r"(?<![\w/.-])([\w./\\-]+\.py)::([A-Za-z_][\w.]*)")


def _normalized(path: str) -> str:
    return path.replace('\\', '/').removeprefix('./')


def _query_symbols(query: str, definitions: list[dict[str, Any]]) -> list[str]:
    """Resolve explicit file::symbol mentions against report definitions."""
    available = {
        f"{_normalized(d['file'])}::{d['qualified_symbol']}"
        for d in definitions
        if isinstance(d, dict) and isinstance(d.get('file'), str)
        and isinstance(d.get('qualified_symbol'), str)
    }
    result = []
    for file, symbol in _SYMBOL_REF.findall(query):
        ref = f"{_normalized(file)}::{symbol}"
        if ref in available and ref not in result:
            result.append(ref)
    return result


def _edge_records(report: dict[str, Any]) -> list[dict[str, Any]]:
    """Read only resolved static calls; imports are not execution edges."""
    known = {
        f"{_normalized(d['file'])}::{d['qualified_symbol']}"
        for d in report.get('definitions', [])
        if isinstance(d, dict) and isinstance(d.get('file'), str)
        and isinstance(d.get('qualified_symbol'), str)
    }
    result = []
    for r in report.get('resolved_calls', []):
        if not isinstance(r, dict):
            continue
        if not all(isinstance(r.get(k), str) for k in
                   ('source_file', 'caller', 'target_file', 'target_symbol')):
            continue
        a = f"{_normalized(r['source_file'])}::{r['caller']}"
        b = f"{_normalized(r['target_file'])}::{r['target_symbol']}"
        line = r.get('line')
        if a not in known or b not in known or type(line) is not int or line < 1:
            continue
        result.append({'from': a, 'to': b, 'file': _normalized(r['source_file']),
                       'line': line, 'expression': r.get('expression', ''),
                       'confidence': r.get('confidence', 'unknown'),
                       'evidence': r.get('evidence', 'unknown')})
    return result


def enrich_evidence(
    *, repository_id: str, query: str, evidence: list[dict[str, Any]],
    max_edges: int = 12, reports: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    """Prioritize explicitly requested verified static edges within an evidence budget.

    Exact edges may be added without a retrieved-file match because both endpoints
    are explicitly named in the question and verified in the repository report.
    Contextual edges still require a retrieved-file match. No negative edges are
    inferred. Original evidence and production retrieval remain untouched.
    """
    if not repository_id or not evidence or max_edges <= 0:
        return list(evidence)
    report = _report_for(repository_id, reports=reports)
    if report is None:
        return list(evidence)

    requested = _query_symbols(query, report['definitions'])
    retrieved_files = {
        _normalized(e['file']) for e in evidence
        if isinstance(e, dict) and isinstance(e.get('file'), str)
    }
    edges = _edge_records(report)
    exact = []
    if len(requested) >= 2:
        # Only the first two explicit symbols define the requested pair.
        source, target = requested[:2]
        exact = [e for e in edges if e['from'] == source and e['to'] == target]

    hints = {'results': [{'metadata': {'file': file}} for file in retrieved_files]}
    analysis = reason(report, query, retrieval=hints)
    # Contextual candidates must overlap original retrieval; exact verified
    # requested edges are the sole exception.
    contextual = [e for e in analysis['related_static_calls']
                  if _normalized(str(e.get('file', ''))) in retrieved_files]

    def relevance(edge: dict[str, Any]) -> tuple[int, int, str, int, str]:
        """Deterministic: requested endpoint, retrieved endpoint, lexical fit."""
        src, dst = str(edge.get('from', '')), str(edge.get('to', ''))
        endpoints = {src, dst}
        endpoint_score = sum(1 for ref in requested if ref in endpoints)
        files = {ref.split('::', 1)[0] for ref in endpoints}
        overlap = len(files & retrieved_files)
        # Lexical scoring only breaks ties; it never displaces an exact edge.
        query_terms = set(re.findall(r'[a-z][a-z0-9_]+', query.lower()))
        edge_terms = set(re.findall(r'[a-z][a-z0-9_]+', (src + ' ' + dst).lower()))
        lexical = len(query_terms & edge_terms)
        return (-endpoint_score, -overlap, -lexical, str(edge.get('file', '')), int(edge.get('line', 0)), src + dst)

    contextual.sort(key=relevance)

    extras: list[dict[str, Any]] = []
    seen: set[tuple[Any, ...]] = set()
    # Deduplicate by logical relationship, not by call-site line. This keeps
    # the earliest/highest-priority provenance when multiple sites agree.
    for edge in exact + contextual:
        file = _normalized(str(edge.get('file', '')))
        line = edge.get('line')
        if type(line) is not int or line < 1:
            continue
        key = (edge.get('from'), edge.get('to'))
        if key in seen:
            continue
        seen.add(key)
        content = (
            'STATIC CALL EVIDENCE (not verified runtime execution): '
            f"{edge['from']} -> {edge['to']}; "
            f"expression={edge.get('expression', '')}; "
            f"confidence={edge.get('confidence', 'unknown')}; "
            f"resolver_evidence={edge.get('evidence', 'unknown')}. "
            'Imports and framework registrations are not execution edges.'
        )
        extras.append({
            'content': content, 'file': file, 'start_line': line,
            'end_line': line, 'symbol': edge.get('from'),
            'symbol_type': 'static_call_relationship',
            'source_tool': 'architecture_v14_4', 'repository_id': repository_id,
        })
        if len(extras) >= max_edges:
            break
    return list(evidence) + extras
