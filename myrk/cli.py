import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

from . import __version__
from .codegen_c import generate
from .lexer import MyrkError
from .parser import parse
from .semantics import check


def compile_source(path: Path) -> str:
    return generate(check(parse(path.read_text(encoding="utf-8"))))


def build(c_source: str, output: Path, compiler: str) -> None:
    with tempfile.TemporaryDirectory(prefix="myrk-build-") as temp:
        c_file = Path(temp) / "program.c"
        c_file.write_text(c_source, encoding="utf-8")
        command = [compiler, "-std=c11", "-O2", "-fwrapv", "-fno-fast-math",
                   "-ffp-contract=off", "-pthread", str(c_file), "-o", str(output)]
        completed = subprocess.run(command, text=True, capture_output=True)
        if completed.returncode:
            raise RuntimeError(f"native compiler failed:\n{completed.stderr.strip()}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="myrk", description="Myrk experimental native compiler")
    parser.add_argument("--version", action="version", version=f"myrk {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)
    for command in ("check", "emit-c", "build", "run"):
        subparser = sub.add_parser(command)
        subparser.add_argument("source", type=Path)
        if command == "build":
            subparser.add_argument("-o", "--output", type=Path)
    args = parser.parse_args(argv)
    source: Path = args.source
    try:
        c_source = compile_source(source)
        if args.command == "check":
            print(f"{source}: ok")
            return 0
        if args.command == "emit-c":
            print(c_source, end="")
            return 0
        compiler = os.environ.get("CC") or shutil.which("clang") or shutil.which("cc")
        if not compiler:
            raise RuntimeError("C compiler missing; install clang (Termux: pkg install clang)")
        if args.command == "build":
            output = args.output or source.with_suffix("")
            build(c_source, output.resolve(), compiler)
            print(output)
            return 0
        with tempfile.TemporaryDirectory(prefix="myrk-run-") as temp:
            output = Path(temp) / "program"
            build(c_source, output, compiler)
            return subprocess.run([str(output)]).returncode
    except MyrkError as error:
        print(f"{source}:{error.pos.line}:{error.pos.column}: error: {error.message}", file=sys.stderr)
        return 1
    except (OSError, UnicodeError, RuntimeError) as error:
        print(f"myrk: {error}", file=sys.stderr)
        return 1
