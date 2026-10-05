from dataclasses import dataclass

from .syntax import Pos


class MyrkError(Exception):
    def __init__(self, pos: Pos, message: str):
        self.pos = pos
        self.message = message
        super().__init__(message)


@dataclass(frozen=True)
class Token:
    kind: str
    text: str
    pos: Pos


def lex(source: str) -> list[Token]:
    tokens = []
    i = 0
    line = 1
    column = 1
    n = len(source)
    while i < n:
        char = source[i]
        if char in " \t\r":
            i += 1
            column += 1
            continue
        if char == "\n":
            i += 1
            line += 1
            column = 1
            continue
        if source.startswith("//", i):
            while i < n and source[i] != "\n":
                i += 1
                column += 1
            continue
        pos = Pos(line, column)
        start = i
        if source.startswith("/*", i):
            depth = 1
            i += 2
            column += 2
            while i < n and depth:
                if source.startswith("/*", i) or source.startswith("*/", i):
                    depth += 1 if source.startswith("/*", i) else -1
                    i += 2
                    column += 2
                elif source[i] == "\n":
                    i += 1
                    line += 1
                    column = 1
                else:
                    i += 1
                    column += 1
            if depth:
                raise MyrkError(pos, "unterminated block comment")
            continue
        if char.isascii() and (char.isalpha() or char == "_"):
            i += 1
            while i < n and source[i].isascii() and (source[i].isalnum() or source[i] == "_"):
                i += 1
            kind = "ident"
        elif char.isascii() and char.isdigit():
            i += 1
            while i < n and source[i].isascii() and source[i].isdigit():
                i += 1
            kind = "int"
            if i + 1 < n and source[i] == "." and source[i + 1].isascii() and source[i + 1].isdigit():
                kind = "float"
                i += 1
                while i < n and source[i].isascii() and source[i].isdigit():
                    i += 1
            if i < n and source[i] in "eE":
                kind = "float"
                i += 1
                if i < n and source[i] in "+-":
                    i += 1
                exponent_start = i
                while i < n and source[i].isascii() and source[i].isdigit():
                    i += 1
                if i == exponent_start:
                    raise MyrkError(pos, "floating exponent requires decimal digits")
            if source.startswith("f32", i) or source.startswith("f64", i):
                kind = "float"
                i += 3
        else:
            pair = source[i:i + 2]
            if pair in ("->", "..", "==", "!=", "<=", ">=", "&&", "||",
                        "+=", "-=", "*=", "/=", "%="):
                i += 2
                kind = pair
            elif char in "{}[]():;,+-*/%=<>!":
                i += 1
                kind = char
            else:
                raise MyrkError(pos, f"unexpected character {char!r}")
        tokens.append(Token(kind, source[start:i], pos))
        column += i - start
    tokens.append(Token("eof", "", Pos(line, column)))
    return tokens
