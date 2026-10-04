import shutil
import unittest

from benchmarks.neuron.reference import rounding, step
from myrk.lexer import MyrkError
from myrk.parser import parse
from myrk.semantics import check
from test_buffers import native, program


def declaration(dtype='f32', n=9, **overrides):
    values = dict(a=0.02, b=0.2, c=-65.0, d=8.0, dt=0.5, current=10.0)
    values.update(overrides)
    parameters = ', '.join(f'{name}={value}{dtype}' for name, value in values.items())
    return f'population p: Izhikevich<{dtype}>(size={n}, {parameters});'


class PopulationTypes(unittest.TestCase):
    def test_uniform_parameter_rounding_boundaries(self):
        from decimal import Decimal, localcontext
        with localcontext() as context:
            context.prec=200
            half=Decimal(2)**-150
            above=format(half+Decimal(2)**-220,'f')
            at=format(half,'f')
        # Just above the underflow midpoint must remain a positive f32 dt.
        check(parse(program(declaration().replace('dt=0.5f32','dt='+above+'f32'))))
        with self.assertRaisesRegex(MyrkError,'dt must be positive'):
            check(parse(program(declaration().replace('dt=0.5f32','dt='+at+'f32'))))
        overflow=str(2**128-2**103)+'.0f32'
        with self.assertRaisesRegex(MyrkError,'finite'):
            check(parse(program(declaration().replace('a=0.02f32','a='+overflow))))

    def test_semantic_population_survives_in_ir(self):
        spec = check(parse(program(declaration()))).procedures[0].body[0].data
        self.assertEqual(spec.model, 'Izhikevich')
        self.assertEqual(spec.precision, 'f32')
        self.assertEqual(spec.layout, 'soa')
        self.assertEqual(spec.solver, 'euler_simultaneous')
        self.assertEqual([p.name for p in spec.parameters], ['a', 'b', 'c', 'd', 'dt', 'current'])
        self.assertTrue(all(p.uniformity == 'uniform' for p in spec.parameters))

    def test_invalid_population_diagnostics(self):
        good = declaration()
        cases = [(good.replace('dt=0.5f32', 'dt=0.0f32'), 'dt must be positive'),
                 (good.replace('b=0.2f32', 'b=0.2f64'), 'expected f32'),
                 (good.replace('Izhikevich', 'Unknown'), 'unknown neuron model'),
                 (good.replace('current=10.0f32', 'other=10.0f32'), 'parameters'),
                 (good.replace('size=9', 'size=1.0'), 'expected i32'),
                 (good.replace('a=0.02f32', 'a=0.02f32, a=0.03f32'), 'duplicate'),
                 (good+'print(voltage(p, 0.0));', 'expected i32'),
                 ('step(p);', 'unknown variable'),
                 ('let p: i32 = 1; step(p);', 'not a population')]
        for body, message in cases:
            with self.subTest(body=body), self.assertRaisesRegex(MyrkError, message):
                check(parse(program(body)))


@unittest.skipUnless(shutil.which('cc') or shutil.which('clang'), 'C compiler required')
class PopulationNative(unittest.TestCase):
    def test_full_trajectory_matches_rounded_oracle(self):
        for dtype in ['f32', 'f64']:
            for current in [0.0, 10.0, 40.0]:
                with self.subTest(dtype=dtype, current=current):
                    source = program(declaration(dtype, current=current) + '''
                    for t in 0..80 {
                        step(p); print(spikes(p));
                        for i in 0..9 { print(voltage(p,i)); print(recovery(p,i)); }
                    }''')
                    result = native(source)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    numbers = iter(result.stdout.splitlines())
                    r = rounding(dtype)
                    v, u = r(-65.0), r(r(0.2)*r(-65.0))
                    for _ in range(80):
                        v, u, fired = step(v, u, dtype=dtype, current=current)
                        self.assertEqual(int(next(numbers)), fired*9)
                        for _ in range(9):
                            self.assertEqual(r(float(next(numbers))), v)
                            self.assertEqual(r(float(next(numbers))), u)

    def test_empty_population(self):
        result = native(program(declaration(n=0)+'step(p); print(spikes(p));'))
        self.assertEqual((result.returncode,result.stdout), (0,'0\n'))

    def test_initial_state_and_spikes(self):
        result = native(program(declaration('f64')+'print(spikes(p)); print(voltage(p,0)); print(recovery(p,0));'))
        self.assertEqual(result.stdout, '0\n-65\n-13\n')

    def test_population_literal_has_same_rounding_as_scalar(self):
        literal='1.000000059604644775390625000001f32'
        body=declaration().replace('c=-65.0f32','c='+literal)
        result=native(program(body+f'print(voltage(p,0)); print({literal});'))
        self.assertEqual(result.stdout.splitlines(),['1.00000012','1.00000012'])

    def test_native_exact_threshold_fires(self):
        for dtype in ['f32','f64']:
            body = declaration(dtype,c=0.0,b=0.0,dt=1.0,current=-110.0)
            result = native(program(body+'step(p); print(spikes(p)); print(voltage(p,0)); print(recovery(p,0));'))
            self.assertEqual(result.stdout,'9\n0\n8\n')

    def test_population_bounds(self):
        for query in ['voltage(p,-1)', 'recovery(p,9)']:
            self.assertEqual(native(program(declaration()+f'print({query});')).returncode,70)
        self.assertEqual(native(program(declaration(n=-1))).returncode,70)

    def test_reference_threshold_boundary(self):
        # dt=1, v=0, u=110, I=0 gives exactly v_next=30: must fire.
        v,u,fired = step(0,110,dt=1,current=0)
        self.assertEqual((v,u,fired),(-65.0,115.8,1))
