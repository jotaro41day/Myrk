import math
import shutil
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

    def test_lif_matches_original_c_and_python_baselines(self):
        import os
        import subprocess
        import tempfile
        from pathlib import Path
        from benchmarks.lif import python_reference
        neurons,steps=64,200
        groups=[];declarations=[];body=[];queries=[]
        for i in range(7):
            count=(neurons-1-i)//7+1
            pop=f'p{i}';groups.append(count)
            declarations.append(declaration('LIF',n=count,dt=0.05,current=1.2+i*0.1,
                capacitance=1.0,g_leak=1.0,v_rest=0.0,v_init=0.0,v_reset=0.0,v_threshold=1.0).replace(' p:',' '+pop+':'))
            body.append(f'step({pop}); total=total+spikes({pop});')
            queries.append(f'for i in 0..{count} {{print(voltage({pop},i));}}')
        result=native(program(' '.join(declarations)+'var total:i32=0;'+
            f'for t in 0..{steps} {{'+''.join(body)+'} print(total);'+''.join(queries)))
        self.assertEqual(result.returncode,0,result.stderr)
        values=result.stdout.splitlines();actual=int(values[0]),sum(map(float,values[1:]))
        expected=python_reference(neurons,steps)
        self.assertEqual(len(values)-1,sum(groups))
        self.assertEqual(actual[0],expected[0]);self.assertAlmostEqual(actual[1],expected[1],places=8)
        with tempfile.TemporaryDirectory() as directory:
            binary=Path(directory)/'lif-reference'
            cc=os.environ.get('CC') or shutil.which('clang') or shutil.which('cc')
            subprocess.run([cc,'-std=c11','-O2','-fno-fast-math',
                '-ffp-contract=off',str(Path(__file__).resolve().parents[1]/'benchmarks/lif_reference.c'),
                '-o',str(binary)],check=True,capture_output=True,text=True)
            spikes,checksum=subprocess.check_output([str(binary),str(neurons),str(steps)],text=True).split()
        self.assertEqual(actual[0],int(spikes));self.assertAlmostEqual(actual[1],float(checksum),places=8)


class AdvancedModelTypes(unittest.TestCase):
    def test_models_states_and_solver(self):
        for model,states,solver in [('AdEx',('v','w'),'euler_simultaneous'),
                                   ('HH',('v','m','h','n'),'euler_voltage_rush_larsen_gates')]:
            spec=check(parse(program(declaration(model)))).procedures[0].body[0].data
            self.assertEqual((spec.model,spec.states,spec.solver),(model,states,solver))

    def test_advanced_parameter_domains_and_queries(self):
        for model,key in [('AdEx','delta_t'),('AdEx','tau_w'),('HH','capacitance')]:
            with self.assertRaisesRegex(MyrkError,key+' must be positive'):
                check(parse(program(declaration(model,**{key:0.0}))))
        for model,key in [('AdEx','a'),('AdEx','b'),('HH','g_na'),('HH','g_k'),('HH','g_leak')]:
            with self.assertRaisesRegex(MyrkError,key+' must be nonnegative'):
                check(parse(program(declaration(model,**{key:-1.0}))))
        for model,query in [('IF','adaptation'),('AdEx','gate_m'),('HH','recovery')]:
            with self.assertRaisesRegex(MyrkError,query+' requires'):
                check(parse(program(declaration(model)+f'print({query}(p,0));')))


class AdvancedModelNative(unittest.TestCase):
    def test_advanced_trajectories_every_state_and_step(self):
        from benchmarks.neuron.model_reference import initialize,step
        for model,queries in [('AdEx',['voltage','adaptation']),('HH',['voltage','gate_m','gate_h','gate_n'])]:
            for dtype in ['f32','f64']:
                with self.subTest(model=model,dtype=dtype):
                    body=' '.join(f'print({q}(p,i));' for q in queries)
                    source=program(declaration(model,dtype,n=3)+f'''for t in 0..400 {{
                        step(p); print(spikes(p)); for i in 0..3 {{ {body} }}
                    }}''')
                    result=native(source);self.assertEqual(result.returncode,0,result.stderr)
                    values=iter(result.stdout.splitlines());params=DEFAULTS[model];state=initialize(model,params,dtype)
                    for _ in range(400):
                        state,fired=step(model,state,params,dtype)
                        self.assertEqual(int(next(values)),fired*3)
                        for _ in range(3):
                            for expected in state:
                                actual=float(next(values))
                                self.assertTrue(math.isfinite(actual))
                                self.assertAlmostEqual(actual,expected,delta=0.003 if dtype=='f32' else 1e-9)

    def test_hh_singular_rates_initialize_finite_gates(self):
        from benchmarks.neuron.model_reference import initialize
        for voltage in [-40.0,-55.0,-65.0]:
            for dtype in ['f32','f64']:
                result=native(program(declaration('HH',dtype,v_init=voltage)+
                    'print(gate_m(p,0)); print(gate_h(p,0)); print(gate_n(p,0));'))
                self.assertEqual(result.returncode,0,result.stderr)
                expected=initialize('HH',{**DEFAULTS['HH'],'v_init':voltage},dtype)[1:]
                for actual,gate in zip(map(float,result.stdout.splitlines()),expected):
                    self.assertTrue(0<=actual<=1)
                    self.assertAlmostEqual(actual,gate,delta=1e-7 if dtype=='f32' else 1e-14)

    def test_hh_crossing_has_no_reset_or_repeated_spike(self):
        source=program(declaration('HH',dt=0.1,current=10.0,g_na=0.0,g_k=0.0,g_leak=0.0,
                                   v_init=-0.5,v_threshold=0.0)+
            'step(p); print(spikes(p)); print(voltage(p,0)); step(p); print(spikes(p)); print(voltage(p,0));')
        self.assertEqual(native(source).stdout,'9\n0.5\n0\n1.5\n')

    def test_hh_gates_remain_bounded_and_rest_is_near_equilibrium(self):
        result=native(program(declaration('HH',current=0.0)+
            'for t in 0..1000 {step(p);} print(voltage(p,0)); print(gate_m(p,0)); print(gate_h(p,0)); print(gate_n(p,0));'))
        self.assertEqual(result.returncode,0,result.stderr)
        voltage,*gates=map(float,result.stdout.splitlines())
        self.assertLess(abs(voltage+65.0),0.02)
        self.assertTrue(all(0<gate<1 for gate in gates))

    def test_advanced_empty_population_and_checked_queries(self):
        for model,query in [('AdEx','adaptation'),('HH','gate_n')]:
            self.assertEqual(native(program(declaration(model,n=0)+'step(p); print(spikes(p));')).stdout,'0\n')
            self.assertEqual(native(program(declaration(model,n=9)+f'print({query}(p,9));')).returncode,70)

    def test_empty_hh_does_not_compute_unused_initial_gates(self):
        result=native(program(declaration('HH',n=0,v_init=-1000000.0)+'step(p); print(spikes(p));'))
        self.assertEqual((result.returncode,result.stdout),(0,'0\n'),result.stderr)

    def test_unstable_hh_fails_instead_of_storing_nonfinite_state(self):
        result=native(program(declaration('HH',dt=1000.0)+'for t in 0..5 {step(p);}'))
        self.assertEqual(result.returncode,70)
        self.assertIn('nonfinite HH state',result.stderr)
