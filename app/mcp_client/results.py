from __future__ import annotations

from typing import Any


def normalize_mcp_result(
    result: Any,
) -> dict[str, Any]:
    """
    Convert an MCP CallToolResult into a predictable
    application-level dictionary.
    """

    structured_content = getattr(
        result,
        "structured_content",
        None,
    )

    is_error = bool(
        getattr(
            result,
            "is_error",
            False,
        )
    )

    content = getattr(
        result,
        "content",
        [],
    )

    normalized_content: list[dict[str, Any]] = []

    for item in content:
        item_type = getattr(
            item,
            "type",
            None,
        )

        if item_type == "text":
            normalized_content.append(
                {
                    "type": "text",
                    "text": getattr(
                        item,
                        "text",
                        "",
                    ),
                }
            )
        else:
            normalized_content.append(
                {
                    "type": item_type,
                    "data": str(item),
                }
            )

    return {
        "is_error": is_error,
        "content": normalized_content,
        "structured_content": structured_content,
    }