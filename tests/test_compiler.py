from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from myrk.cli import build, compile_source
from myrk.codegen_c import generate
from myrk.lexer import MyrkError, lex
from myrk.parser import parse
from myrk.semantics import check


class FrontendTests(unittest.TestCase):
    def test_lexer_locations(self):
        tokens = lex("fn main() -> i32 {\n  print(42);\n}")
        self.assertEqual((tokens[0].text, tokens[0].pos.line, tokens[0].pos.column), ("fn", 1, 1))
        self.assertEqual((tokens[7].text, tokens[7].pos.line), ("print", 2))

    def test_precedence_in_ir(self):
        module = check(parse("fn main() -> i32 { print(1 + 2 * 3); return 0; }"))
        expr = module.procedures[0].body[0].args[0]
        self.assertEqual(expr.data, "+")
        self.assertEqual(expr.args[1].data, "*")

    def test_type_mismatch(self):
        with self.assertRaisesRegex(MyrkError, "expected f32, found f64"):
            check(parse("fn main() -> i32 { let x: f32 = 1.0; return 0; }"))

    def test_immutable_assignment(self):
        with self.assertRaisesRegex(MyrkError, "immutable variable"):
            check(parse("fn main() -> i32 { let x: i32 = 1; x = 2; return 0; }"))

    def test_missing_name(self):
        with self.assertRaisesRegex(MyrkError, "unknown variable"):
            check(parse("fn main() -> i32 { print(x); return 0; }"))

    def test_bad_character_location(self):
        with self.assertRaises(MyrkError) as raised:
            parse("fn main() -> i32 {\n@\n}")
        self.assertEqual((raised.exception.pos.line, raised.exception.pos.column), (2, 1))

    def test_ir_is_typed(self):
        module = check(parse("fn main() -> i32 { print(1.5f32 * 2.0f32); return 0; }"))
        self.assertEqual(module.procedures[0].body[0].args[0].dtype, "f32")
        self.assertIn("1.5f", generate(module))

    def test_i32_minimum_literal(self):
        module = check(parse("fn main() -> i32 { print(-2147483648); return 0; }"))
        self.assertEqual(module.procedures[0].body[0].args[0].data, -2147483648)

    def test_i32_positive_literal_overflow(self):
        with self.assertRaisesRegex(MyrkError, "out of range"):
            check(parse("fn main() -> i32 { print(2147483648); return 0; }"))


@unittest.skipUnless(shutil.which("cc") or shutil.which("clang"), "native C compiler required")
class NativeTests(unittest.TestCase):
    def run_example(self, name):
        source = compile_source(Path("examples") / name)
        with tempfile.TemporaryDirectory() as directory:
            executable = Path(directory) / "program"
            build(source, executable, shutil.which("clang") or shutil.which("cc"))
            return subprocess.run([str(executable)], text=True, capture_output=True)

    def test_hello(self):
        result = self.run_example("hello.myrk")
        self.assertEqual((result.returncode, result.stdout), (0, "42\n"))

    def test_loop_and_function(self):
        result = self.run_example("sum.myrk")
        self.assertEqual((result.returncode, result.stdout), (0, "45\n"))

    def test_numeric(self):
        result = self.run_example("numeric.myrk")
        self.assertEqual((result.returncode, result.stdout), (0, "2.25\n3.75\ntrue\n"))

    def test_division_by_zero_traps(self):
        source = generate(check(parse("fn main() -> i32 { print(1 / 0); return 0; }")))
        with tempfile.TemporaryDirectory() as directory:
            executable = Path(directory) / "program"
            build(source, executable, shutil.which("clang") or shutil.which("cc"))
            result = subprocess.run([str(executable)], text=True, capture_output=True)
        self.assertEqual(result.returncode, 70)
        self.assertIn("invalid i32 division", result.stderr)

    def test_calls_evaluate_left_to_right(self):
        source = generate(check(parse("""
fn echo(n: i32) -> i32 { print(n); return n; }
fn main() -> i32 { print(echo(1) + echo(2)); return 0; }
""")))
        with tempfile.TemporaryDirectory() as directory:
            executable = Path(directory) / "program"
            build(source, executable, shutil.which("clang") or shutil.which("cc"))
            result = subprocess.run([str(executable)], text=True, capture_output=True)
        self.assertEqual((result.returncode, result.stdout), (0, "1\n2\n3\n"))


if __name__ == "__main__":
    unittest.main()
