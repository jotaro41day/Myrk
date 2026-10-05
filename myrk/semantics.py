from dataclasses import dataclass
from fractions import Fraction

from .ir import Instruction, Module, Procedure, Value, PopulationSpec, UniformParameter
from .lexer import MyrkError
from .syntax import Expr, Function, Pos, Stmt
from .models import MODELS, STATE_QUERIES, QUERY_MODELS, canonical_model


TYPES = {"i32", "f32", "f64", "bool"}
NUMERIC = {"i32", "f32", "f64"}


@dataclass(frozen=True)
class Symbol:
    dtype: str
    cname: str
    mutable: bool
    kind: str = "scalar"
    model: str = ""


class Checker:
    def __init__(self, functions: tuple[Function, ...]):
        self.functions = functions
        self.signatures = {}
        self.next_symbol = 0
        self.scopes = []
        self.result = ""

    def type_name(self, name: str, pos: Pos) -> str:
        if name not in TYPES:
            raise MyrkError(pos, f"unknown type {name!r}; expected i32, f32, f64 or bool")
        return name

    def add_symbol(self, name: str, dtype: str, mutable: bool, pos: Pos, kind: str = "scalar", model: str = "") -> Symbol:
        if name in self.scopes[-1]:
            raise MyrkError(pos, f"duplicate declaration of {name!r}")
        symbol = Symbol(dtype, f"myrk_v_{self.next_symbol}", mutable, kind, model)
        self.next_symbol += 1
        self.scopes[-1][name] = symbol
        return symbol

    def lookup(self, name: str, pos: Pos) -> Symbol:
        for scope in reversed(self.scopes):
            if name in scope:
                return scope[name]
        raise MyrkError(pos, f"unknown variable {name!r}")

    def check(self) -> Module:
        for function in self.functions:
            if function.name in self.signatures or function.name in {"print", "step", "spikes", *STATE_QUERIES}:
                raise MyrkError(function.pos, f"duplicate or reserved function {function.name!r}")
            params = tuple(self.type_name(t, p) for _, t, p in function.params)
            result = self.type_name(function.result, function.pos)
            self.signatures[function.name] = (params, result)
        if "main" not in self.signatures or self.signatures["main"] != ((), "i32"):
            raise MyrkError(Pos(1, 1), "program needs fn main() -> i32")
        procedures = []
        for function in self.functions:
            self.scopes = [{}]
            self.result = function.result
            params = []
            for name, dtype, pos in function.params:
                symbol = self.add_symbol(name, dtype, False, pos)
                params.append((symbol.cname, dtype))
            body = self.block(function.body, nested=False)
            if not body or body[-1].op != "return":
                raise MyrkError(function.pos, f"function {function.name!r} must end with return")
            procedures.append(Procedure(function.name, tuple(params), function.result, body))
        return Module(tuple(procedures))

    def block(self, statements: tuple[Stmt, ...], nested: bool = True) -> tuple[Instruction, ...]:
        if nested:
            self.scopes.append({})
        result = tuple(self.statement(statement) for statement in statements)
        if nested:
            self.scopes.pop()
        return result

    def require(self, value: Value, dtype: str, pos: Pos) -> None:
        if value.dtype != dtype:
            raise MyrkError(pos, f"expected {dtype}, found {value.dtype}; use an explicitly typed value")

    def statement(self, statement: Stmt) -> Instruction:
        op = statement.kind
        if op == "population":
            name, model, dtype = statement.value
            canonical = canonical_model(model)
            if canonical is None:
                raise MyrkError(statement.pos, f"unknown neuron model {model!r}")
            model = canonical
            definition = MODELS[model]
            if dtype not in ("f32", "f64"):
                raise MyrkError(statement.pos, "population precision must be f32 or f64")
            params = dict(statement.args)
            if len(params) != len(statement.args):
                raise MyrkError(statement.pos, "duplicate population parameter")
            names = definition.parameters
            if set(params) != {"size", *names}:
                raise MyrkError(statement.pos, "population parameters must be size, " + ", ".join(names))
            size = self.expression(params["size"])
            self.require(size, "i32", size.pos)
            uniform = []
            for param in names:
                expr = params[param]
                value = self.expression(expr)
                self.require(value, dtype, value.pos)
                text, number = self.literal_float(expr, dtype)
                half_subnormal = Fraction(1, 2 ** (150 if dtype == "f32" else 1075))
                if param in definition.positive and number <= half_subnormal:
                    raise MyrkError(expr.pos, f"{param} must be positive in its precision")
                if param in definition.nonnegative and number < 0:
                    raise MyrkError(expr.pos, f"{param} must be nonnegative")
                uniform.append(UniformParameter(param, Value("constant", dtype, expr.pos, text)))
            symbol = self.add_symbol(name, dtype, False, statement.pos, "population", model)
            spec = PopulationSpec(symbol.cname, dtype, size, tuple(uniform), model=model,
                                  solver=definition.solver, states=definition.states)
            return Instruction(op, statement.pos, spec)
        if op == "step":
            symbol = self.population(statement.value, statement.pos)
            return Instruction(op, statement.pos, (symbol.cname, symbol.dtype, symbol.model))
        if op == "buffer":
            name, dtype = statement.value
            if dtype not in ("f32", "f64"):
                raise MyrkError(statement.pos, "buffer element must be f32 or f64")
            size = self.expression(statement.args[0])
            self.require(size, "i32", size.pos)
            symbol = self.add_symbol(name, dtype, True, statement.pos, "buffer")
            return Instruction(op, statement.pos, (symbol.cname, dtype), (size,))
        if op == "store":
            symbol, index = self.buffer_index(statement.value, statement.args[0], statement.pos)
            value = self.expression(statement.args[1])
            self.require(value, symbol.dtype, value.pos)
            return Instruction(op, statement.pos, symbol.cname, (index, value))
        if op == "declare":
            name, dtype, mutable = statement.value
            value = self.expression(statement.args[0])
            dtype = self.type_name(dtype, statement.pos) if dtype is not None else value.dtype
            self.require(value, dtype, statement.pos)
            symbol = self.add_symbol(name, dtype, mutable, statement.pos)
            return Instruction(op, statement.pos, (symbol.cname, dtype), (value,))
        if op == "assign":
            symbol = self.lookup(statement.value, statement.pos)
            if symbol.kind != "scalar":
                raise MyrkError(statement.pos, f"cannot assign a {symbol.kind}; assign an element")
            if not symbol.mutable:
                raise MyrkError(statement.pos, f"cannot assign to immutable variable {statement.value!r}; use 'var'")
            value = self.expression(statement.args[0])
            self.require(value, symbol.dtype, statement.pos)
            return Instruction(op, statement.pos, symbol.cname, (value,))
        if op == "return":
            value = self.expression(statement.args[0])
            self.require(value, self.result, statement.pos)
            return Instruction(op, statement.pos, args=(value,))
        if op == "print":
            value = self.expression(statement.args[0])
            return Instruction(op, statement.pos, args=(value,))
        if op == "for":
            start = self.expression(statement.args[0])
            end = self.expression(statement.args[1])
            self.require(start, "i32", statement.pos)
            self.require(end, "i32", statement.pos)
            self.scopes.append({})
            index = self.add_symbol(statement.value, "i32", False, statement.pos)
            body = self.block(statement.args[2], nested=False)
            self.scopes.pop()
            return Instruction(op, statement.pos, index.cname, (start, end, body))
        raise AssertionError(op)

    def buffer_index(self, name, expression, pos):
        symbol = self.lookup(name, pos)
        if symbol.kind != "buffer":
            raise MyrkError(pos, f"{name!r} is not a buffer")
        index = self.expression(expression)
        self.require(index, "i32", index.pos)
        return symbol, index

    def population(self, name, pos):
        symbol = self.lookup(name, pos)
        if symbol.kind != "population":
            raise MyrkError(pos, f"{name!r} is not a population")
        return symbol

    def literal_float(self, expr, dtype):
        sign = 1
        literal = expr
        if expr.kind == "unary" and expr.value == "-":
            sign, literal = -1, expr.args[0]
        if literal.kind != "float":
            raise MyrkError(expr.pos, "uniform parameter currently requires a floating literal")
        text = ("-" if sign < 0 else "") + literal.value.removesuffix("f32").removesuffix("f64")
        number = Fraction(text)
        # Exact round-to-nearest overflow midpoint; avoid decimal -> f64 -> f32.
        overflow = 2**128 - 2**103 if dtype == "f32" else 2**1024 - 2**970
        if abs(number) >= overflow:
            raise MyrkError(expr.pos, "uniform parameter must be finite in its precision")
        return text, number

    def expression(self, expr: Expr) -> Value:
        if expr.kind == "load":
            symbol, index = self.buffer_index(expr.value, expr.args[0], expr.pos)
            return Value("load", symbol.dtype, expr.pos, symbol.cname, (index,))
        if expr.kind == "int":
            number = int(expr.value)
            if number > 2147483647:
                raise MyrkError(expr.pos, "i32 literal is out of range")
            return Value("constant", "i32", expr.pos, number)
        if expr.kind == "float":
            text = expr.value
            dtype = "f32" if text.endswith("f32") else "f64"
            text = text.removesuffix("f32").removesuffix("f64")
            if not any(c in text for c in ".eE"):
                text += ".0"
            return Value("constant", dtype, expr.pos, text)
        if expr.kind == "bool":
            return Value("constant", "bool", expr.pos, expr.value)
        if expr.kind == "name":
            symbol = self.lookup(expr.value, expr.pos)
            if symbol.kind != "scalar":
                raise MyrkError(expr.pos, f"expected scalar, found {symbol.kind}")
            return Value("variable", symbol.dtype, expr.pos, symbol.cname)
        if expr.kind == "call":
            if expr.value in {"spikes", *STATE_QUERIES}:
                count = 1 if expr.value == "spikes" else 2
                if len(expr.args) != count or expr.args[0].kind != "name":
                    raise MyrkError(expr.pos, f"{expr.value} expects a population name and {count-1} indices")
                symbol = self.population(expr.args[0].value, expr.pos)
                required_model = QUERY_MODELS.get(expr.value)
                if required_model and symbol.model != required_model:
                    raise MyrkError(expr.pos, f"{expr.value} requires {required_model}, found {symbol.model}")
                args = ()
                if count == 2:
                    index = self.expression(expr.args[1])
                    self.require(index, "i32", index.pos)
                    args = (index,)
                return Value(expr.value, "i32" if count == 1 else symbol.dtype, expr.pos, symbol.cname, args)
            signature = self.signatures.get(expr.value)
            if signature is None:
                raise MyrkError(expr.pos, f"unknown function {expr.value!r}")
            params, result = signature
            if len(expr.args) != len(params):
                raise MyrkError(expr.pos, f"function {expr.value!r} expects {len(params)} arguments")
            args = tuple(self.expression(item) for item in expr.args)
            for arg, dtype in zip(args, params):
                self.require(arg, dtype, arg.pos)
            return Value("call", result, expr.pos, expr.value, args)
        if expr.kind == "unary":
            if expr.value == "-" and expr.args[0].kind == "int" and expr.args[0].value == "2147483648":
                return Value("constant", "i32", expr.pos, -2147483648)
            arg = self.expression(expr.args[0])
            if expr.value == "!" and arg.dtype != "bool":
                raise MyrkError(expr.pos, "'!' requires bool")
            if expr.value == "-" and arg.dtype not in NUMERIC:
                raise MyrkError(expr.pos, "unary '-' requires a number")
            return Value("unary", arg.dtype, expr.pos, expr.value, (arg,))
        if expr.kind == "binary":
            left = self.expression(expr.args[0])
            right = self.expression(expr.args[1])
            if left.dtype != right.dtype:
                raise MyrkError(expr.pos, f"type mismatch: {left.dtype} and {right.dtype}")
            operator = expr.value
            if operator in ("+", "-", "*", "/") and left.dtype not in NUMERIC:
                raise MyrkError(expr.pos, f"'{operator}' requires numbers")
            if operator == "%" and left.dtype != "i32":
                raise MyrkError(expr.pos, "'%' requires i32")
            if operator in ("<", "<=", ">", ">=") and left.dtype not in NUMERIC:
                raise MyrkError(expr.pos, f"'{operator}' requires numbers")
            dtype = "bool" if operator in ("==", "!=", "<", "<=", ">", ">=") else left.dtype
            return Value("binary", dtype, expr.pos, operator, (left, right))
        raise AssertionError(expr.kind)


def check(functions: tuple[Function, ...]) -> Module:
    return Checker(functions).check()
