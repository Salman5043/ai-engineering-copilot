from dataclasses import dataclass


@dataclass
class CodeChunk:
    content: str
    start_line: int
    end_line: int


def chunk_code(
    content: str,
    chunk_size: int = 1200,
    overlap: int = 200,
) -> list[CodeChunk]:

    if not content.strip():
        return []

    if overlap >= chunk_size:
        raise ValueError(
            "overlap must be smaller than chunk_size"
        )

    lines = content.splitlines()

    chunks: list[CodeChunk] = []

    current_lines: list[str] = []
    current_chars = 0
    start_line = 1

    for index, line in enumerate(lines, start=1):

        line_length = len(line) + 1

        if (
            current_lines
            and current_chars + line_length > chunk_size
        ):
            chunks.append(
                CodeChunk(
                    content="\n".join(current_lines),
                    start_line=start_line,
                    end_line=index - 1,
                )
            )

            overlap_lines: list[str] = []
            overlap_chars = 0

            for previous_line in reversed(current_lines):

                if overlap_chars + len(previous_line) + 1 > overlap:
                    break

                overlap_lines.insert(0, previous_line)
                overlap_chars += len(previous_line) + 1

            current_lines = overlap_lines
            current_chars = overlap_chars

            if overlap_lines:
                start_line = index - len(overlap_lines)
            else:
                start_line = index

        current_lines.append(line)
        current_chars += line_length

    if current_lines:
        chunks.append(
            CodeChunk(
                content="\n".join(current_lines),
                start_line=start_line,
                end_line=len(lines),
            )
        )

    return chunks