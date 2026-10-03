from __future__ import annotations

from typing import Any


SYSTEM_PROMPT = """
You are an AI software engineer operating inside a
repository-aware code modification system.

Your job is to propose a safe, minimal code change
based ONLY on the repository evidence and file contents
provided by the application.

STRICT RULES:

1. Never invent repository files.
2. Only modify files explicitly supplied in the request.
3. Return complete proposed file contents.
4. Do not return partial snippets.
5. Preserve existing functionality unless the requested
   change requires modifying it.
6. Make the smallest reasonable change.
7. Do not modify configuration, dependencies, secrets,
   credentials, or unrelated files unless explicitly
   requested and supplied as editable files.
8. Do not modify .git or repository metadata.
9. Do not claim that tests pass unless test evidence
   explicitly demonstrates that.
10. Do not execute commands.
11. Do not write files.
12. If the supplied evidence is insufficient to safely
   implement the requested change, return an empty
   changes list and explain why in the description.
13. Every proposed file must contain its COMPLETE
   resulting content.
14. Preserve the existing coding style whenever possible.

The application will validate and review your proposal
before anything can be written to disk.
"""


def build_patch_prompt(
    *,
    query: str,
    repository_id: str,
    files: list[dict[str, Any]],
    evidence: list[dict[str, Any]],
) -> str:
    """
    Build the user prompt for LLM patch generation.
    """

    sections: list[str] = []

    sections.append(
        f"Repository ID: {repository_id}"
    )

    sections.append(
        f"Requested change:\n{query}"
    )

    sections.append(
        "\nFILES AVAILABLE FOR MODIFICATION:"
    )

    for file_data in files:
        sections.append(
            "\n"
            f"--- FILE: {file_data['path']} ---\n"
            f"{file_data['content']}\n"
            f"--- END FILE: {file_data['path']} ---"
        )

    sections.append(
        "\nREPOSITORY EVIDENCE:"
    )

    if not evidence:
        sections.append(
            "No additional evidence was provided."
        )
    else:
        for index, item in enumerate(
            evidence,
            start=1,
        ):
            sections.append(
                "\n"
                f"Evidence #{index}\n"
                f"Tool: {item.get('source_tool', '')}\n"
                f"File: {item.get('file', '')}\n"
                f"Lines: "
                f"{item.get('start_line', '')}-"
                f"{item.get('end_line', '')}\n"
                f"Symbol: {item.get('symbol', '')}\n"
                f"Content:\n"
                f"{item.get('content', '')}"
            )

    sections.append(
        "\n"
        "Generate the smallest safe change that addresses "
        "the requested change."
    )

    return "\n".join(sections)