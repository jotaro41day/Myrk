import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


class OfficialModelBenchmarkTests(unittest.TestCase):
    def test_all_new_models_both_precisions_are_correctness_gated(self):
        result=subprocess.run([sys.executable,'-m','benchmarks.neuron.models','--sizes','17',
            '--steps','40','--repeat','1','--warmup','0'],text=True,capture_output=True)
        self.assertEqual(result.returncode,0,result.stderr)
        report=json.loads(result.stdout)
        self.assertEqual(len(report['results']),10)
        self.assertEqual({r['model'] for r in report['results']},{'IF','LIF','QIF','AdEx','HH'})
        for row in report['results']:
            self.assertTrue(row['validation']['passed'])
            self.assertTrue(row['python_oracle']['passed'])
            self.assertEqual(row['validation']['max_abs_error'],0)
            self.assertEqual(row['myrk']['state_hash'],row['c']['state_hash'])
            self.assertEqual(row['myrk']['spikes'],row['c']['spikes'])
            self.assertEqual(row['myrk']['threads'],1)
            self.assertGreater(row['myrk']['updates_per_second'],0)
            self.assertGreater(row['myrk']['kernel_median_ms'],0)

    def test_native_reference_rejects_wrong_hh_voltage_update(self):
        from benchmarks.neuron.models import build_driver,checked
        from myrk.model_kernels import kernel
        def broken(model,dtype):
            return kernel(model,dtype).replace('next_v=old_v+dt*','next_v=old_v+2.0*dt*')
        cc=os.environ.get('CC') or 'cc'
        with tempfile.TemporaryDirectory() as directory,patch('myrk.codegen_c.model_kernel',broken):
            binary,_=build_driver(Path(directory),'HH','f64',cc)
            with self.assertRaisesRegex(RuntimeError,'state mismatch'):
                checked([binary,'validate','myrk','17','40'])

    def test_memory_budget_skips_and_cli_rejects_invalid_inputs(self):
        result=subprocess.run([sys.executable,'-m','benchmarks.neuron.models','--models','HH',
            '--dtype','f64','--sizes','1000000','--max-mib','1','--repeat','1','--steps','1'],
            text=True,capture_output=True)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(json.loads(result.stdout)['results'][0]['status'],'skipped_memory_budget')
        for args in [['--sizes','0'],['--steps','0'],['--repeat','0'],['--models','Unknown']]:
            result=subprocess.run([sys.executable,'-m','benchmarks.neuron.models',*args],text=True,capture_output=True)
            self.assertEqual(result.returncode,2,result.stderr)

    def test_reference_has_same_hh_finite_state_failure_contract(self):
        from benchmarks.neuron.models import build_driver,checked,DEFAULTS
        with tempfile.TemporaryDirectory() as directory,patch.dict(DEFAULTS['HH'],{'dt':1000.0}):
            binary,_=build_driver(Path(directory),'HH','f64',os.environ.get('CC') or 'cc')
            for backend in ['myrk','c']:
                with self.subTest(backend=backend), self.assertRaisesRegex(
                        RuntimeError,r'command failed \(70\).*nonfinite HH state'):
                    checked([binary,'run',backend,'1','5'])
