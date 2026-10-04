import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


@unittest.skipUnless(shutil.which('cc') or shutil.which('clang'), 'C compiler required')
class NeuronBenchmarkTests(unittest.TestCase):
    def run_bench(self, *args):
        return subprocess.run([sys.executable, '-m', 'benchmarks.neuron.izhikevich', *args],
                              capture_output=True, text=True)

    def test_correctness_gate_and_metrics_both_precisions(self):
        with tempfile.TemporaryDirectory() as directory:
            result = self.run_bench('--sizes', '17', '--steps', '80', '--repeat', '1',
                                    '--warmup', '0', '--artifacts', directory)
            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(result.stdout)
            self.assertEqual(report['category'], 'neuron_update')
            self.assertEqual(len(report['results']), 2)
            for row in report['results']:
                self.assertTrue(row['validation']['passed'])
                self.assertEqual(row['validation']['max_abs_error'], 0)
                self.assertEqual(row['bytes_per_neuron'], 8 if row['dtype']=='f32' else 16)
                self.assertEqual(row['myrk']['spikes'], row['c']['spikes'])
                self.assertEqual(row['myrk']['state_hash'], row['c']['state_hash'])
                self.assertGreater(row['myrk']['updates_per_second'], 0)
            self.assertTrue(list(Path(directory).glob('*.s')))

    def test_invalid_cli_arguments(self):
        for args in [('--sizes','0'), ('--sizes','2147483648'), ('--steps','0'),
                     ('--repeat','0'), ('--warmup','-1'), ('--max-mib','0')]:
            with self.subTest(args=args):
                self.assertNotEqual(self.run_bench(*args).returncode,0)

    def test_native_gate_rejects_corrupted_model(self):
        from benchmarks.neuron.izhikevich import build_driver, checked
        cc=os.environ.get('CC') or shutil.which('clang') or shutil.which('cc')
        with tempfile.TemporaryDirectory() as directory:
            binary,metadata=build_driver(directory,'f32',cc,'O2')
            generated=Path(directory)/'population-f32.c'
            original=generated.read_text()
            self.assertIn('0.04f',original)
            generated.write_text(original.replace('0.04f','0.05f'))
            checked([cc,*metadata['flags'],Path(directory)/'bench-f32.c','-o',binary])
            with self.assertRaisesRegex(RuntimeError,'state mismatch'):
                checked([binary,'validate','myrk',17,80])

    def test_memory_budget_skips_scale(self):
        result = self.run_bench('--sizes','1000000','--max-mib','1', '--repeat','1')
        self.assertEqual(result.returncode,0,result.stderr)
        report=json.loads(result.stdout)
        self.assertTrue(all(row['status']=='skipped_memory_budget' for row in report['results']))
