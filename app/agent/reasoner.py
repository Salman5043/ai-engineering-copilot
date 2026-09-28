from __future__ import annotations

from typing import Any

from app.agent.llm import get_llm


SYSTEM_PROMPT = """
You are an AI software engineering investigation assistant.

Your job is to answer developer questions about a software repository
using ONLY the investigation evidence provided to you.

Rules:

1. Do not invent repository facts.
2. Do not claim that code exists unless supported by evidence.
3. Prefer direct source-code evidence over assumptions.
4. Mention file paths and line ranges when available.
5. Explain relationships between relevant pieces of code.
6. If the evidence is insufficient, explicitly say that the available
   evidence is insufficient.
7. Do not pretend that you inspected files that are not present in the
   evidence.
8. Keep the answer technically precise.
9. When appropriate, provide a concise investigation summary followed
   by the relevant implementation details.
"""


def _format_evidence(
    evidence: list[dict[str, Any]],
) -> str:
    if not evidence:
        return "No repository evidence was collected."

    sections: list[str] = []

    for index, item in enumerate(evidence, start=1):
        file = item.get("file", "")
        start_line = item.get("start_line")
        end_line = item.get("end_line")

        location = file

        if start_line is not None:
            location += f":{start_line}"

            if end_line is not None:
                location += f"-{end_line}"

        symbol = item.get("symbol")
        symbol_type = item.get("symbol_type")

        metadata = []

        if symbol:
            metadata.append(
                f"symbol={symbol}"
            )

        if symbol_type:
            metadata.append(
                f"type={symbol_type}"
            )

        source_tool = item.get("source_tool")

        if source_tool:
            metadata.append(
                f"tool={source_tool}"
            )

        metadata_text = ""

        if metadata:
            metadata_text = (
                " (" + ", ".join(metadata) + ")"
            )

        content = item.get("content", "")

        sections.append(
            f"""Evidence {index}
Location: {location}{metadata_text}

```text
{content}
```"""
        )

    return "\n\n".join(sections)


def build_reasoning_prompt(
    *,
    query: str,
    intent: str,
    evidence: list[dict[str, Any]],
) -> str:
    evidence_text = _format_evidence(evidence)

    return f"""
Developer question:

{query}

Detected investigation intent:

{intent}

Repository evidence:

{evidence_text}

Based strictly on the evidence above, answer the developer's question.

Your answer should:

- directly answer the question
- identify relevant files
- identify relevant symbols when available
- explain the relationship between the evidence
- mention line ranges when available
- clearly distinguish direct evidence from reasonable interpretation
- state when evidence is insufficient
"""


def generate_reasoned_answer(
    *,
    query: str,
    intent: str,
    evidence: list[dict[str, Any]],
) -> str:
    llm = get_llm()

    prompt = build_reasoning_prompt(
        query=query,
        intent=intent,
        evidence=evidence,
    )

    response = llm.invoke(
        [
            (
                "system",
                SYSTEM_PROMPT,
            ),
            (
                "human",
                prompt,
            ),
        ]
    )

    content = response.content

    if isinstance(content, str):
        return content.strip()

    return str(content).strip()