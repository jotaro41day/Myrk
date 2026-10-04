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


@dataclass(frozen=True)
class UniformParameter:
    name: str
    value: Value
    uniformity: str = "uniform"


@dataclass(frozen=True)
class PopulationSpec:
    name: str
    precision: str
    size: Value
    parameters: tuple[UniformParameter, ...]
    model: str = "Izhikevich"
    solver: str = "euler_simultaneous"
    layout: str = "soa"
