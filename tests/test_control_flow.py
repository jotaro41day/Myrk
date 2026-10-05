import os
import shutil
import unittest
from unittest.mock import patch

from myrk.lexer import MyrkError
from myrk.parser import parse
from myrk.semantics import check
from myrk.optimize import batch_populations
from test_buffers import native, program


IZH = '''population p: Izhikevich<f32>(size=17,
    a=0.02f32, b=0.2f32, c=-65f32, d=8f32, dt=0.5f32, current=10f32);'''


class ControlTypes(unittest.TestCase):
    def test_conditions_and_logic_require_bool(self):
        for body in ('if 1 { print(0); }', 'while 1f32 { break; }',
                     'print(1 && 2);', 'print(true || 1);'):
            with self.subTest(body=body), self.assertRaisesRegex(MyrkError, 'bool'):
                check(parse(program(body)))

    def test_loop_exits_outside_loop(self):
        for body in ('break;', 'continue;', 'if true { break; }'):
            with self.subTest(body=body), self.assertRaisesRegex(MyrkError, 'inside a loop'):
                check(parse(program(body)))

    def test_branch_and_loop_locals_do_not_escape(self):
        for body in ('if true { let x = 1; } print(x);',
                     'if true { let x = 1; } else { print(x); }',
                     'while false { let x = 1; } print(x);'):
            with self.subTest(body=body), self.assertRaisesRegex(MyrkError, 'unknown variable'):
                check(parse(program(body)))

    def test_every_scalar_path_returns(self):
        check(parse('fn main() -> i32 { if true { return 0; } else { return 1; } }'))
        for body in ('if true { return 0; }', 'while true { return 0; }',
                     'if true { return 0; } else { print(1); }'):
            with self.subTest(body=body), self.assertRaisesRegex(MyrkError, 'return'):
                check(parse('fn main() -> i32 { ' + body + ' }'))

    def test_control_flow_preserves_conservative_neural_batching(self):
        source = program(IZH + '''
            if true { for t in 0..200 { step(p); } }
            while false { for t in 0..200 { step(p); } break; }
            for t in 0..200 { step(p); if t == 1 { break; } }
        ''')
        body = batch_populations(check(parse(source))).procedures[0].body
        self.assertEqual(body[1].args[1][0].op, 'advance')
        self.assertEqual(body[2].args[1][0].op, 'advance')
        self.assertEqual(body[3].op, 'for')


@unittest.skipUnless(shutil.which('cc') or shutil.which('clang'), 'C compiler required')
class ControlNative(unittest.TestCase):
    def test_else_if_all_path_returns_and_recursion(self):
        result = native('''fn sign(x: i32) -> i32 {
            if x < 0 { return -1; } else if x == 0 { return 0; } else { return 1; }
        }
        fn fib(x: i32) -> i32 {
            if x < 2 { return x; }
            return fib(x - 1) + fib(x - 2);
        }
        fn main() -> i32 { print(sign(-2)); print(sign(0)); print(sign(3)); print(fib(10)); return 0; }''')
        self.assertEqual((result.returncode, result.stdout), (0, '-1\n0\n1\n55\n'))

    def test_while_condition_is_recomputed_after_continue(self):
        result = native('''fn below(n: i32) -> bool { print(n); return n < 3; }
        fn main() -> i32 {
            var n = 0;
            while below(n) { n = n + 1; continue; }
            print(n); return 0;
        }''')
        self.assertEqual((result.returncode, result.stdout), (0, '0\n1\n2\n3\n3\n'))

    def test_short_circuit_skips_effects_and_traps(self):
        result = native('''fn yes(n: i32) -> bool { print(n); return true; }
        fn main() -> i32 {
            buffer x: f32[0];
            print(false && (1 / 0 == 0));
            print(true || (x[0] == 0f32));
            print(true && yes(1));
            print(false || yes(2));
            print(false && yes(3));
            print(true || yes(4));
            print(!false && 1 < 2 == true || false);
            return 0;
        }''')
        self.assertEqual((result.returncode, result.stdout),
                         (0, 'false\ntrue\n1\ntrue\n2\ntrue\nfalse\ntrue\ntrue\n'))

    def test_nested_break_continue_preserve_outer_buffers(self):
        result = native(program('''
            buffer outer: f64[1]; outer[0] = 7.0;
            var count = 0;
            for i in 0..3 {
                buffer a: f32[8]; a[0] = 1f32;
                var j = 0;
                while j < 4 {
                    buffer b: f32[8]; b[0] = a[0];
                    j = j + 1;
                    if j == 2 { buffer c: f64[8]; continue; }
                    if j == 3 { break; }
                    count = count + 1;
                }
                if i == 1 { continue; }
                count = count + 10;
            }
            print(count); print(outer[0]);
        '''))
        self.assertEqual((result.returncode, result.stdout), (0, '23\n7\n'))

    def test_model_declaration_and_batch_inside_control_flow(self):
        result = native(program('''var n = 0;
            while n < 2 {
                if n == 0 { ''' + IZH + '''
                    for t in 0..200 { step(p); }
                    print(spikes(p)); print(voltage(p,0));
                } else {
                    population p: IF<f32>(size=17, dt=0.1f32, current=500f32,
                        capacitance=200f32, v_init=-65f32, v_reset=-65f32, v_threshold=-50f32);
                    for t in 0..400 { step(p); }
                    print(voltage(p,0));
                }
                n = n + 1;
            }
        '''))
        self.assertEqual((result.returncode, result.stdout), (0, '0\n-68.0648041\n-55\n'))

    def test_batch_inside_branch_with_multicore(self):
        with patch.dict(os.environ, {'MYRK_THREADS': '2', 'MYRK_TILE': '7'}):
            result = native(program(IZH + '''var count = 0;
                if true { for t in 0..200 { step(p); count = count + spikes(p); } }
                print(count); print(voltage(p,0));
            '''))
        self.assertEqual((result.returncode, result.stdout), (0, '51\n-68.0648041\n'))


if __name__ == '__main__':
    unittest.main()
