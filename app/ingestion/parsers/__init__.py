from pathlib import Path

from app.ingestion.parsers.base import ParsedCode
from app.ingestion.parsers.python_parser import parse_python


def parse_code(
    source: str,
    file_path: str | Path,
) -> ParsedCode | None:

    path = Path(file_path)

    if path.suffix.lower() == ".py":
        try:
            return parse_python(source)
        except SyntaxError:
            return None

    return None