from dataclasses import dataclass


@dataclass(frozen=True)
class Pos:
    line: int
    column: int


@dataclass(frozen=True)
class Expr:
    kind: str
    pos: Pos
    value: object = None
    args: tuple = ()


@dataclass(frozen=True)
class Stmt:
    kind: str
    pos: Pos
    value: object = None
    args: tuple = ()


@dataclass(frozen=True)
class Function:
    name: str
    params: tuple
    result: str
    body: tuple
    pos: Pos
