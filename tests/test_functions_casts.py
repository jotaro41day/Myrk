import shutil
import unittest

from myrk.lexer import MyrkError
from myrk.parser import parse
from myrk.semantics import check
from test_buffers import native, program


class FunctionsAndCastsTypes(unittest.TestCase):
    def test_non_callable_type_names_remain_valid_functions(self):
        check(parse('fn bool(n: i32) -> bool { return n > 0; } '
                    'fn unit() -> i32 { return 2; } ' + program('print(bool(unit()));')))

    def test_unit_function_interfaces(self):
        module = check(parse('fn log(n: i32) { print(n); } fn main() -> i32 { log(2); return 0; }'))
        self.assertEqual(module.procedures[0].result, 'unit')
        check(parse('fn noop() -> unit { return; } fn main() -> i32 { noop(); return 0; }'))

    def test_unit_cannot_be_scalar_or_parameter(self):
        for source, error in [
            ('fn f() {} fn main() -> i32 { let x = f(); return 0; }', 'unit'),
            ('fn f() {} fn main() -> i32 { print(f()); return 0; }', 'unit'),
            ('fn f(x: unit) {} fn main() -> i32 { return 0; }', 'unit'),
            ('fn f() { return 1; } fn main() -> i32 { return 0; }', 'unit'),
            ('fn main() -> i32 { return; }', 'i32'),
            ('fn main() {}', 'main'),
        ]:
            with self.subTest(source=source), self.assertRaisesRegex(MyrkError, error):
                check(parse(source))

    def test_casts_remain_explicit_and_numeric(self):
        for body, error in [('print(f32(true));', 'numeric'),
                            ('print(i32());', 'one argument'),
                            ('print(f64(1, 2));', 'one argument'),
                            ('var x = 1f32; x += 2.0;', 'expected f32'),
                            ('let x = 1; x += 1;', 'immutable'),
                            ('var x = true; x += false;', 'numbers'),
                            ('var x = 1f32; x %= 1f32;', 'i32')]:
            with self.subTest(body=body), self.assertRaisesRegex(MyrkError, error):
                check(parse(program(body)))

    def test_cast_function_names_reserved(self):
        with self.assertRaisesRegex(MyrkError, 'reserved'):
            check(parse('fn f32(x: i32) -> i32 { return x; } fn main() -> i32 { return 0; }'))

    def test_len_requires_a_local_buffer_or_population(self):
        for body in ('print(len(1));', 'let x = 1; print(len(x));', 'print(len());'):
            with self.subTest(body=body), self.assertRaisesRegex(MyrkError, 'len'):
                check(parse(program(body)))


@unittest.skipUnless(shutil.which('cc') or shutil.which('clang'), 'C compiler required')
class FunctionsAndCastsNative(unittest.TestCase):
    def test_unit_calls_and_early_cleanup(self):
        result = native('''fn log(n: i32) { print(n); }
        fn bounded(n: i32) -> unit {
            buffer x: f32[3];
            for i in 0..n { buffer y: f64[2]; if i == 1 { log(i); return; } }
            log(9);
        }
        fn echo(n: i32) -> i32 { log(n); return n; }
        fn main() -> i32 { bounded(3); bounded(0); echo(42); return 0; }''')
        self.assertEqual((result.returncode, result.stdout), (0, '1\n9\n42\n'))

    def test_casts_truncate_and_preserve_precision_contract(self):
        result = native(program('''print(i32(3.9)); print(i32(-3.9f32));
            print(i32(2147483647.9)); print(i32(-2147483648.9));
            print(f64(f32(16777217))); print(f64(16777217));
            print(f32(-0.0)); print(f64(2f32)); print(i32(-2147483648f32));
        '''))
        self.assertEqual((result.returncode, result.stdout),
                         (0, '3\n-3\n2147483647\n-2147483648\n16777216\n16777217\n-0\n2\n-2147483648\n'))

    def test_invalid_numeric_casts_trap(self):
        for expr in ('i32(2147483648.0)', 'i32(-2147483649.0)', 'i32(0.0 / 0.0)',
                     'i32(1.0 / 0.0)', 'i32(2147483647f32)', 'f32(1e300)'):
            with self.subTest(expr=expr):
                result = native(program('print(' + expr + ');'))
                self.assertEqual(result.returncode, 70)
                self.assertIn('numeric cast', result.stderr)

    def test_float_narrowing_boundary_and_nonfinite(self):
        result = native(program('''let max = f32(3.4028234663852886e38);
            print(max > 3e38f32);
            let inf = f32(1.0 / 0.0); print(inf > max);
            let nan = f32(0.0 / 0.0); print(nan == nan);
        '''))
        self.assertEqual((result.returncode, result.stdout), (0, 'true\ntrue\nfalse\n'))

    def test_compound_scalar_assignment(self):
        result = native(program('''var n = 2147483647; n += 1; n -= 1;
            print(n); n *= 2; print(n); n /= 2; n %= 7; print(n);
            var x = 1f32; x += 2f32; x *= 0.5f32; print(x);
        '''))
        self.assertEqual((result.returncode, result.stdout), (0, '2147483647\n-2\n-1\n1.5\n'))

    def test_compound_division_traps(self):
        for body in ('var x = 1; x /= 0;', 'var x = -2147483648; x %= -1;'):
            with self.subTest(body=body):
                self.assertEqual(native(program(body)).returncode, 70)

    def test_buffer_compound_index_then_load_then_rhs_once(self):
        result = native('''fn idx() -> i32 { print(1); return 0; }
            fn rhs() -> i32 { print(2); return 3; }
            fn main() -> i32 { buffer x: i32[1]; x[0] = 4;
                x[idx()] += rhs(); print(x[0]); print(len(x)); return 0; }
        ''')
        self.assertEqual((result.returncode, result.stdout), (0, '1\n2\n7\n1\n'))

    def test_compound_buffer_checks_index_before_rhs(self):
        result = native('''fn rhs() -> f32 { print(99); return 1f32; }
            fn main() -> i32 { buffer x: f32[0]; x[0] += rhs(); return 0; }''')
        self.assertEqual((result.returncode, result.stdout), (70, ''))

    def test_integer_and_bool_buffers_and_len(self):
        result = native(program('''buffer x: i32[4]; buffer flags: bool[4];
            for i in 0..len(x) { x[i] = i * 2; flags[i] = x[i] > 2; }
            print(x[3]); print(flags[0]); print(flags[3]);
            population p: Izhikevich<f32>(size=3, a=0.02f32, b=0.2f32,
                c=-65f32, d=8f32, dt=0.5f32, current=10f32);
            print(len(p));
        '''))
        self.assertEqual((result.returncode, result.stdout), (0, '6\nfalse\ntrue\n3\n'))


if __name__ == '__main__':
    unittest.main()
