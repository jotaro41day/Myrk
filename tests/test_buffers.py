import shutil
import os
import subprocess
import tempfile
from pathlib import Path
import unittest

from myrk.cli import build
from myrk.codegen_c import generate
from myrk.lexer import MyrkError
from myrk.parser import parse
from myrk.semantics import check


def native(source):
    with tempfile.TemporaryDirectory() as directory:
        binary = Path(directory) / 'test'
        build(generate(check(parse(source))), binary,
              os.environ.get('CC') or shutil.which('clang') or shutil.which('cc'))
        return subprocess.run([str(binary)], capture_output=True, text=True)


def program(body):
    return 'fn main() -> i32 { ' + body + ' return 0; }'


class BufferTypes(unittest.TestCase):
    def test_buffer_ir(self):
        module = check(parse(program('buffer x: f32[4]; x[0] = 1.0f32; print(x[0]);')))
        self.assertEqual(module.procedures[0].body[0].op, 'buffer')
        self.assertEqual(module.procedures[0].body[2].args[0].dtype, 'f32')

    def test_bad_buffer_uses(self):
        for body, error in [
            ('buffer x: bool[4];', 'buffer element'),
            ('buffer x: f32[1.0];', 'expected i32'),
            ('buffer x: f32[4]; x[0] = 1.0;', 'expected f32'),
            ('buffer x: f32[4]; print(x[0.0]);', 'expected i32'),
            ('let x: i32 = 1; print(x[0]);', 'not a buffer'),
            ('buffer x: f32[4]; print(x);', 'scalar'),
            ('buffer x: f32[4]; x = x;', 'buffer'),
        ]:
            with self.subTest(body=body), self.assertRaisesRegex(MyrkError, error):
                check(parse(program(body)))


@unittest.skipUnless(shutil.which('cc') or shutil.which('clang'), 'C compiler required')
class BufferNative(unittest.TestCase):
    def test_zero_initialize_and_store(self):
        result = native(program('buffer x: f32[4]; print(x[3]); x[2] = 2.5f32; print(x[2]);'))
        self.assertEqual((result.returncode, result.stdout), (0, '0\n2.5\n'))

    def test_zero_length(self):
        self.assertEqual(native(program('buffer x: f64[0];')).returncode, 0)

    def test_bad_sizes_and_bounds(self):
        for body in ['buffer x: f32[-1];', 'buffer x: f64[0]; print(x[0]);',
                     'buffer x: f32[4]; x[-1] = 0.0f32;',
                     'buffer x: f64[4]; print(x[4]);']:
            with self.subTest(body=body):
                self.assertEqual(native(program(body)).returncode, 70)

    def test_nested_scope_and_early_return(self):
        result = native('''fn f() -> f64 {
            buffer x: f64[2]; x[0] = 3.5;
            for i in 0..2 { buffer y: f64[3]; y[i] = x[0]; return y[i]; }
            return 0.0;
        }
        fn main() -> i32 { print(f()); return 0; }''')
        self.assertEqual((result.returncode, result.stdout), (0, '3.5\n'))

    def test_index_and_rhs_evaluation_order(self):
        result = native('''fn index() -> i32 { print(1); return 0; }
        fn value() -> f32 { print(2); return 3.0f32; }
        fn main() -> i32 { buffer x: f32[1]; x[index()] = value(); print(x[0]); return 0; }''')
        self.assertEqual(result.stdout, '1\n2\n3\n')
