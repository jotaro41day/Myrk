import math
import unittest
from benchmarks.neuron.model_reference import DEFAULTS, declaration, initialize, step
from benchmarks.neuron.reference import rounding
from myrk.parser import parse
from myrk.semantics import check
from myrk.lexer import MyrkError
from myrk.optimize import batch_populations
from test_buffers import native, program


class ModelTypes(unittest.TestCase):
    def test_basic_models_have_explicit_ir(self):
        for model in ['IF','LIF','QIF']:
            for dtype in ['f32','f64']:
                with self.subTest(model=model,dtype=dtype):
                    spec=check(parse(program(declaration(model,dtype)))).procedures[0].body[0].data
                    self.assertEqual((spec.model,spec.precision,spec.states),(model,dtype,('v',)))
                    self.assertEqual(spec.solver,'euler_simultaneous')

    def test_model_names_are_case_insensitive(self):
        for model in ['IF','LIF','QIF']:
            source=program(declaration(model).replace(': '+model+'<',': '+model.lower()+'<'))
            self.assertEqual(check(parse(source)).procedures[0].body[0].data.model,model)

    def test_parameter_domains_and_missing_parameters(self):
        for model in ['IF','LIF','QIF']:
            for key in ['dt','capacitance']:
                with self.assertRaisesRegex(MyrkError,key+' must be positive'):
                    check(parse(program(declaration(model,**{key:0.0}))))
            with self.assertRaisesRegex(MyrkError,'parameters'):
                check(parse(program(declaration(model).replace('dt=0.1f64, ',''))))
        for model,key in [('LIF','g_leak'),('QIF','k')]:
            with self.assertRaisesRegex(MyrkError,key+' must be positive'):
                check(parse(program(declaration(model,**{key:-1.0}))))

    def test_incompatible_state_query_is_a_type_error(self):
        for model in ['IF','LIF','QIF']:
            with self.assertRaisesRegex(MyrkError,'recovery.*Izhikevich'):
                check(parse(program(declaration(model)+'print(recovery(p,0));')))

    def test_new_models_do_not_inherit_batch_proof(self):
        for model in ['IF','LIF','QIF']:
            module=batch_populations(check(parse(program(declaration(model)+'for t in 0..80 {step(p);}'))))
            self.assertEqual(module.procedures[0].body[1].op,'for')


class ModelNative(unittest.TestCase):
    def test_basic_model_trajectories_every_state_and_step(self):
        for model in ['IF','LIF','QIF']:
            for dtype in ['f32','f64']:
                for current in [0.0,500.0]:
                    with self.subTest(model=model,dtype=dtype,current=current):
                        params={**DEFAULTS[model],'current':current};r=rounding(dtype)
                        source=program(declaration(model,dtype,current=current)+'''for t in 0..80 {
                            step(p); print(spikes(p));
                            for i in 0..9 { print(voltage(p,i)); }
                        }''')
                        result=native(source);self.assertEqual(result.returncode,0,result.stderr)
                        numbers=iter(result.stdout.splitlines());state=initialize(model,params,dtype)
                        for _ in range(80):
                            state,fired=step(model,state,params,dtype)
                            self.assertEqual(int(next(numbers)),9*fired)
                            for _ in range(9):self.assertEqual(r(float(next(numbers))),state[0])

    def test_exact_threshold_and_reset(self):
        for model in ['IF','LIF','QIF']:
            extra={'g_leak':1.0,'v_rest':0.0} if model=='LIF' else (
                {'k':1.0,'v_rest':0.0,'v_critical':0.0} if model=='QIF' else {})
            source=program(declaration(model,'f64',n=19,dt=1.0,current=200.0,
                v_init=0.0,v_reset=0.0,v_threshold=1.0,**extra)+
                'step(p); print(spikes(p)); print(voltage(p,18));')
            self.assertEqual(native(source).stdout,'19\n0\n')

    def test_empty_and_negative_populations(self):
        for model in ['IF','LIF','QIF']:
            self.assertEqual(native(program(declaration(model,n=0)+'step(p); print(spikes(p));')).stdout,'0\n')
            self.assertEqual(native(program(declaration(model,n=-1))).returncode,70)

    def test_lif_subthreshold_matches_discrete_closed_form(self):
        source=program(declaration('LIF',current=10.0)+
            'for t in 0..100 {step(p);} print(voltage(p,0));')
        result=native(source);self.assertEqual(result.returncode,0,result.stderr)
        expected=-64.0+(-65.0+64.0)*(1.0-0.1*10.0/200.0)**100
        self.assertAlmostEqual(float(result.stdout),expected,places=11)
        # Continuous solution differs because the requested solver is Euler.
        continuous=-64.0-math.exp(-0.1*100*10.0/200.0)
        self.assertLess(abs(float(result.stdout)-continuous),0.001)
