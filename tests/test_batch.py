import unittest
import os
from unittest.mock import patch
from myrk.parser import parse
from myrk.semantics import check
from myrk.codegen_c import generate
from test_buffers import native, program
from test_population import declaration


class BatchCompilerTests(unittest.TestCase):
    def test_invalid_tile_is_rejected(self):
        for value in ['-1','2147483648','none','7x']:
            with self.subTest(value=value), patch.dict(os.environ,{'MYRK_THREADS':'1','MYRK_TILE':value}):
                result=native(program(declaration()+'for t in 0..2 {step(p);}'))
                self.assertEqual(result.returncode,70)
                self.assertIn('MYRK_TILE',result.stderr)

    def test_tiled_batches_match_untiled_with_repeated_calls(self):
        for dtype in ['f32','f64']:
            source=program(declaration(dtype,n=1031)+'''var total:i32=0;
                for batch in 0..3 {
                    for t in 0..80 {step(p); total=total+spikes(p);}
                    print(spikes(p)); print(voltage(p,1030)); print(recovery(p,0));
                } print(total);''')
            with patch.dict(os.environ,{'MYRK_THREADS':'1','MYRK_TILE':'0'}):
                expected=native(source)
            for threads,tile in [(1,1),(1,7),(4,3),(4,2048)]:
                with self.subTest(dtype=dtype,threads=threads,tile=tile), patch.dict(
                        os.environ,{'MYRK_THREADS':str(threads),'MYRK_TILE':str(tile)}):
                    actual=native(source)
                    self.assertEqual((actual.returncode,actual.stdout),
                                     (expected.returncode,expected.stdout),actual.stderr)

    def test_thread_configuration_is_validated(self):
        for value in ['0','-1','65','four','4x']:
            with self.subTest(value=value), patch.dict(os.environ,{'MYRK_THREADS':value}):
                result=native(program(declaration()+'for t in 0..2 {step(p);}'))
                self.assertEqual(result.returncode,70)
                self.assertIn('MYRK_THREADS',result.stderr)

    def test_parallel_batches_match_single_thread_and_reuse_pool(self):
        for dtype in ['f32','f64']:
            for n in [1,3,17,1031]:
                source=program(declaration(dtype,n=n)+'''var total:i32=0;
                    for batch in 0..3 {
                        for t in 0..80 {step(p); total=total+spikes(p);}
                        print(spikes(p)); print(voltage(p,0));
                    } print(total);''')
                with patch.dict(os.environ,{'MYRK_THREADS':'1'}):
                    baseline=native(source)
                with patch.dict(os.environ,{'MYRK_THREADS':'4'}):
                    parallel=native(source)
                self.assertEqual((parallel.returncode,parallel.stdout),
                                 (baseline.returncode,baseline.stdout),parallel.stderr)

    def test_pure_loop_lowers_to_batch(self):
        source=program(declaration()+'for t in 0..80 { step(p); }')
        self.assertIn('myrk_izh_f32_advance(',generate(check(parse(source))).split('myrk_f_main(void) {')[1])

    def test_observer_prevents_batching(self):
        source=program(declaration()+'for t in 0..2 { step(p); print(spikes(p)); }')
        main=generate(check(parse(source))).split('myrk_f_main(void) {')[1]
        self.assertNotIn('_advance(',main)

    def test_accumulation_and_last_spikes_match_observed_loop(self):
        for dtype in ['f32','f64']:
            start=declaration(dtype,n=19)+'var total: i32 = 2147483640;'
            body='step(p); total = total + spikes(p);'
            suffix='print(total); print(spikes(p)); print(voltage(p,0)); print(recovery(p,18));'
            optimized=native(program(start+'for t in 0..200 {'+body+'}'+suffix))
            # Extra harmless declaration deliberately prevents the strict matching rule.
            oracle=native(program(start+'for t in 0..200 {'+body+'let observed: i32 = spikes(p); }'+suffix))
            self.assertEqual(optimized.returncode,0,optimized.stderr)
            self.assertEqual(optimized.stdout,oracle.stdout)

    def test_empty_ranges_preserve_last_spikes(self):
        for bounds in ['3..3','9..2']:
            result=native(program(declaration(c=0.0,b=0.0,dt=1.0,current=-110.0)+
                'step(p);'+f'for t in {bounds} {{step(p);}} print(spikes(p));'))
            self.assertEqual(result.stdout,'9\n')

    def test_bounds_evaluate_once_left_to_right(self):
        source='fn bound(n:i32) -> i32 { print(n); return n; }'+program(
            declaration(n=0)+'for t in bound(1)..bound(4) {step(p);} print(spikes(p));')
        self.assertEqual(native(source).stdout,'1\n4\n0\n')
