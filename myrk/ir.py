from dataclasses import dataclass

from .syntax import Pos


@dataclass(frozen=True)
class Value:
    op: str
    dtype: str
    pos: Pos
    data: object = None
    args: tuple = ()


@dataclass(frozen=True)
class Instruction:
    op: str
    pos: Pos
    data: object = None
    args: tuple = ()


@dataclass(frozen=True)
class Procedure:
    name: str
    params: tuple
    result: str
    body: tuple


@dataclass(frozen=True)
class Module:
    procedures: tuple[Procedure, ...]
