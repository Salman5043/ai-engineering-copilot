from dataclasses import dataclass, field


@dataclass
class CodeSymbol:
    name: str
    symbol_type: str
    start_line: int
    end_line: int
    parent: str | None = None
    signature: str | None = None
    children: list[str] = field(default_factory=list)


@dataclass
class ParsedCode:
    language: str
    symbols: list[CodeSymbol]
    imports: list[str]