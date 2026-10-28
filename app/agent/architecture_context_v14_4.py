"""Optional, repository-scoped architecture evidence for agent answers.

Configure COPILOT_ARCHITECTURE_REPORTS_JSON as a JSON object mapping repository
IDs to v14.1 report paths. Unconfigured repositories retain old behavior.
"""
from __future__ import annotations

import json
import os
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


def enrich_evidence(
    *, repository_id: str, query: str, evidence: list[dict[str, Any]],
    max_edges: int = 12, reports: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    """Return a new evidence list, adding bounded static-call records only.

    No additional retrieval is performed. Failures are handled by the caller;
    this function never modifies the input list.
    """
    if not repository_id or not evidence or max_edges <= 0:
        return list(evidence)
    report = _report_for(repository_id, reports=reports)
    if report is None:
        return list(evidence)

    hints = {'results': [
        {'metadata': {'file': e.get('file')}} for e in evidence
        if isinstance(e.get('file'), str) and e.get('file')
    ]}
    analysis = reason(report, query, retrieval=hints)
    # Require a connection to actually retrieved files. Lexical matches alone
    # are insufficient to attach architecture claims to an answer.
    retrieved_files = {str(e.get('file', '')).replace('\\', '/').removeprefix('./')
                       for e in evidence}
    extras: list[dict[str, Any]] = []
    seen = set()
    for edge in analysis['related_static_calls']:
        file = str(edge.get('file', '')).replace('\\', '/')
        if file not in retrieved_files:
            continue
        line = edge.get('line')
        if not isinstance(line, int) or line < 1:
            continue
        key = (file, line, edge.get('from'), edge.get('to'))
        if key in seen:
            continue
        seen.add(key)
        content = (
            f"STATIC CALL EVIDENCE (not verified runtime execution): "
            f"{edge['from']} -> {edge['to']}; "
            f"expression={edge.get('expression', '')}; "
            f"confidence={edge.get('confidence', 'unknown')}; "
            f"resolver_evidence={edge.get('evidence', 'unknown')}. "
            "Imports and framework registrations are not execution edges."
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
