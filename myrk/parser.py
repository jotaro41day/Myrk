from .lexer import MyrkError, Token, lex
from .syntax import Expr, Function, Stmt


PRECEDENCE = {"==": 1, "!=": 1, "<": 1, "<=": 1, ">": 1, ">=": 1,
              "+": 2, "-": 2, "*": 3, "/": 3, "%": 3}


class Parser:
    def __init__(self, source: str):
        self.tokens = lex(source)
        self.index = 0

    @property
    def current(self) -> Token:
        return self.tokens[self.index]

    def take(self, kind: str) -> Token:
        token = self.current
        if token.kind != kind:
            raise MyrkError(token.pos, f"expected {kind!r}, found {token.text or 'end of file'!r}")
        self.index += 1
        return token

    def match(self, kind: str) -> bool:
        if self.current.kind == kind:
            self.index += 1
            return True
        return False

    def name(self) -> Token:
        return self.take("ident")

    def program(self) -> tuple[Function, ...]:
        functions = []
        while self.current.kind != "eof":
            keyword = self.name()
            if keyword.text != "fn":
                raise MyrkError(keyword.pos, "expected 'fn'")
            name = self.name()
            self.take("(")
            params = []
            if self.current.kind != ")":
                while True:
                    param = self.name()
                    self.take(":")
                    params.append((param.text, self.name().text, param.pos))
                    if not self.match(","):
                        break
            self.take(")")
            self.take("->")
            result = self.name().text
            body = self.block()
            functions.append(Function(name.text, tuple(params), result, body, name.pos))
        return tuple(functions)

    def block(self) -> tuple[Stmt, ...]:
        self.take("{")
        body = []
        while self.current.kind != "}":
            if self.current.kind == "eof":
                raise MyrkError(self.current.pos, "expected '}' before end of file")
            body.append(self.statement())
        self.take("}")
        return tuple(body)

    def statement(self) -> Stmt:
        token = self.current
        if token.kind != "ident":
            raise MyrkError(token.pos, "expected a statement")
        self.index += 1
        if token.text in ("let", "var"):
            name = self.name()
            self.take(":")
            dtype = self.name().text
            self.take("=")
            value = self.expression()
            self.take(";")
            return Stmt("declare", token.pos, (name.text, dtype, token.text == "var"), (value,))
        if token.text == "return":
            value = self.expression()
            self.take(";")
            return Stmt("return", token.pos, args=(value,))
        if token.text == "print":
            self.take("(")
            value = self.expression()
            self.take(")")
            self.take(";")
            return Stmt("print", token.pos, args=(value,))
        if token.text == "for":
            index = self.name()
            if self.name().text != "in":
                raise MyrkError(index.pos, "expected 'in' after loop variable")
            start = self.expression()
            self.take("..")
            end = self.expression()
            body = self.block()
            return Stmt("for", token.pos, index.text, (start, end, body))
        self.take("=")
        value = self.expression()
        self.take(";")
        return Stmt("assign", token.pos, token.text, (value,))

    def expression(self, minimum: int = 0) -> Expr:
        token = self.current
        self.index += 1
        if token.kind in ("int", "float"):
            left = Expr(token.kind, token.pos, token.text)
        elif token.kind == "ident":
            if token.text in ("true", "false"):
                left = Expr("bool", token.pos, token.text == "true")
            elif self.match("("):
                args = []
                if self.current.kind != ")":
                    while True:
                        args.append(self.expression())
                        if not self.match(","):
                            break
                self.take(")")
                left = Expr("call", token.pos, token.text, tuple(args))
            else:
                left = Expr("name", token.pos, token.text)
        elif token.kind in ("-", "!"):
            left = Expr("unary", token.pos, token.kind, (self.expression(4),))
        elif token.kind == "(":
            left = self.expression()
            self.take(")")
        else:
            raise MyrkError(token.pos, "expected an expression")
        while self.current.kind in PRECEDENCE and PRECEDENCE[self.current.kind] >= minimum:
            operator = self.current
            self.index += 1
            right = self.expression(PRECEDENCE[operator.kind] + 1)
            left = Expr("binary", operator.pos, operator.kind, (left, right))
        return left


def parse(source: str) -> tuple[Function, ...]:
    return Parser(source).program()
