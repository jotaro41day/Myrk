"""Correctness-gated Izhikevich neuron-update lab. No connected SNN claims."""
import argparse
import json
import os
from pathlib import Path
import platform
import shutil
import statistics
import subprocess
import tempfile
import time

from myrk.codegen_c import generate
from myrk.parser import parse
from myrk.semantics import check
from .reference import rounding, step

ROOT = Path(__file__).resolve().parent
SCALES = [1000, 10000, 100000, 1000000, 2000000, 5000000, 10000000]


def source(dtype, n=17):
    params = dict(a=0.02,b=0.2,c=-65.0,d=8.0,dt=0.5,current=10.0)
    fields = ', '.join(f'{k}={v}{dtype}' for k,v in params.items())
    return f'''fn main() -> i32 {{
    population p: Izhikevich<{dtype}>(size={n}, {fields});
    step(p); print(spikes(p)); return 0;
}}'''


def checked(command):
    result = subprocess.run([str(x) for x in command],text=True,capture_output=True)
    if result.returncode:
        raise RuntimeError(f'command failed ({result.returncode}): {result.stderr.strip()}')
    return result.stdout


def build_driver(directory, dtype, cc, opt):
    directory = Path(directory).resolve()
    generated = directory / f'population-{dtype}.c'
    started=time.perf_counter()
    generated.write_text(generate(check(parse(source(dtype)))))
    frontend_ms=(time.perf_counter()-started)*1000
    driver = ROOT.joinpath('driver.c').read_text()
    for token,value in {'GENERATED':generated.name,'REAL':'float' if dtype=='f32' else 'double',
                        'DTYPE':dtype,'LITERAL':'x##f' if dtype=='f32' else 'x',
                        'REFERENCE':'izhikevich_reference.h'}.items():
        driver=driver.replace('@'+token+'@',value)
    c_file=directory/f'bench-{dtype}.c'; c_file.write_text(driver)
    shutil.copyfile(ROOT/'izhikevich_reference.h', directory/'izhikevich_reference.h')
    binary=directory/f'bench-{dtype}'
    flags=['-std=c11',f'-{opt}','-fwrapv','-fno-fast-math','-ffp-contract=off']
    started=time.perf_counter()
    checked([cc,*flags,c_file,'-o',binary])
    compile_ms=(time.perf_counter()-started)*1000
    checked([cc,*flags,'-S',c_file,'-o',directory/f'bench-{dtype}.s'])
    return binary,dict(flags=flags,frontend_ms=frontend_ms,native_compile_ms=compile_ms,
                       binary_bytes=binary.stat().st_size)


def oracle_gate(binary,dtype):
    n,steps=17,80
    rows=checked([binary,'trace','myrk',n,steps]).splitlines()
    if len(rows)!=steps:
        raise RuntimeError('wrong oracle trace length')
    r=rounding(dtype)
    vs=[r(-70.0+i*0.125) for i in range(n)]
    us=[r(r(0.2)*v) for v in vs]
    for t,row in enumerate(rows):
        fields=row.split(); spikes=0
        if len(fields)!=1+2*n:
            raise RuntimeError('wrong oracle trace width')
        for i in range(n):
            vs[i],us[i],fired=step(vs[i],us[i],dtype=dtype)
            spikes+=fired
            if r(float(fields[1+2*i]))!=vs[i] or r(float(fields[2+2*i]))!=us[i]:
                raise RuntimeError(f'Python oracle mismatch dtype={dtype}, step={t}, neuron={i}')
        if int(fields[0])!=spikes:
            raise RuntimeError('Python oracle spike mismatch')
    return dict(neurons=n,steps=steps,passed=True,comparison='every state and per-step spike count')


def precision_comparison(steps):
    """Trajectory error, NOT an assertion that the two precisions are equivalent."""
    n=97; r=rounding('f32')
    v64=[-70.0+i*0.125 for i in range(n)];u64=[0.2*v for v in v64]
    v32=[r(v) for v in v64];u32=[r(r(0.2)*v) for v in v32]
    maximum_v=maximum_u=0.0; mismatches=0; total32=total64=0
    for _ in range(steps):
        for i in range(n):
            v32[i],u32[i],s32=step(v32[i],u32[i],dtype='f32')
            v64[i],u64[i],s64=step(v64[i],u64[i],dtype='f64')
            maximum_v=max(maximum_v,abs(v32[i]-v64[i]))
            maximum_u=max(maximum_u,abs(u32[i]-u64[i]))
            mismatches+=s32!=s64;total32+=s32;total64+=s64
    return dict(neurons=n,steps=steps,max_trajectory_abs_v=maximum_v,
                max_trajectory_abs_u=maximum_u,spike_neuron_step_mismatches=mismatches,
                spikes_f32=total32,spikes_f64=total64,
                note='Precision sensitivity for this case; not solver convergence or scientific validation')


def measure(binary,n,steps,repeat,warmup,expected):
    samples={k:[] for k in ('myrk','c')}
    # Alternate order to reduce fixed ordering bias; each process starts from identical state.
    for run in range(warmup+repeat):
        order=('myrk','c') if run%2==0 else ('c','myrk')
        for backend in order:
            started=time.perf_counter()
            row=json.loads(checked([binary,'run',backend,n,steps]))
            row['process_seconds']=time.perf_counter()-started
            for key in ('spikes','state_hash','sum_v','sum_u'):
                if row[key]!=expected[key]:
                    raise RuntimeError(f'{backend} wrong {key}; timing discarded')
            if row['seconds']<=0:
                raise RuntimeError('invalid native clock interval')
            if run>=warmup:
                samples[backend].append(row)
    result={}
    for backend,rows in samples.items():
        seconds=[r['seconds'] for r in rows];median=statistics.median(seconds)
        rss=[r['peak_rss_kib'] for r in rows if r['peak_rss_kib']>=0]
        result[backend]=dict(kernel_median_ms=median*1000,samples_ms=[s*1000 for s in seconds],
            ms_per_timestep=median*1000/steps,updates_per_second=n*steps/median,
            realtime_factor=steps*0.0005/median,
            peak_rss_kib_median=statistics.median(rss) if rss else None,
            process_median_ms=statistics.median(r['process_seconds'] for r in rows)*1000,
            spikes=rows[0]['spikes'],sum_v=rows[0]['sum_v'],sum_u=rows[0]['sum_u'],
            state_hash=rows[0]['state_hash'])
    return result


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sizes',nargs='+',type=int,default=[1000,10000,100000,1000000])
    parser.add_argument('--all-scales',action='store_true')
    parser.add_argument('--dtype',choices=['f32','f64','both'],default='both')
    parser.add_argument('--steps',type=int,default=200)
    parser.add_argument('--repeat',type=int,default=5)
    parser.add_argument('--warmup',type=int,default=2)
    parser.add_argument('--max-mib',type=int,default=512,
                        help='maximum validation array payload (two complete populations), not total RSS')
    parser.add_argument('--opt',choices=['O2','O3'],default='O2')
    parser.add_argument('--artifacts',type=Path,help='keep generated C, native binaries and assembly here')
    args=parser.parse_args(argv)
    if args.all_scales: args.sizes=SCALES
    if any(n<1 or n>2147483647 for n in args.sizes) or not 1<=args.steps<=2147483647:
        parser.error('sizes and steps must be in [1,2147483647]')
    if args.repeat<1 or args.warmup<0 or args.max_mib<1:
        parser.error('repeat/max-mib must be positive; warmup must be nonnegative')
    cc=os.environ.get('CC') or shutil.which('clang') or shutil.which('cc')
    if not cc: parser.error('install clang or set CC')
    try:
        report=dict(category='neuron_update',model='Izhikevich',solver='euler_simultaneous',
            threshold='after integration >=30; reset v=c, u=u_next+d',dt_ms=0.5,
            current=10.0,threads=1,mode='strict; no FMA contraction',
            hardware=dict(machine=platform.machine(),system=platform.platform(),
                          cpu_count=os.cpu_count()),compiler=checked([cc,'--version']).splitlines()[0],
            repeat=args.repeat,warmup=args.warmup,steps=args.steps,
            precision_comparison=precision_comparison(min(args.steps,200)),results=[])
        with tempfile.TemporaryDirectory(prefix='myrk-izh-') as temporary:
            directory=args.artifacts or Path(temporary)
            directory.mkdir(parents=True,exist_ok=True)
            for dtype in (['f32','f64'] if args.dtype=='both' else [args.dtype]):
                binary,compilation=build_driver(directory,dtype,cc,args.opt)
                oracle=oracle_gate(binary,dtype)
                width=4 if dtype=='f32' else 8
                for n in args.sizes:
                    row=dict(neurons=n,dtype=dtype,bytes_per_neuron=2*width,
                             state_bytes=n*2*width,validation_payload_bytes=n*4*width)
                    if n*4*width>args.max_mib*1024*1024:
                        row['status']='skipped_memory_budget';report['results'].append(row);continue
                    validation=json.loads(checked([binary,'validate','myrk',n,args.steps]))
                    row.update(status='measured',compilation=compilation,python_oracle=oracle,
                               validation={k:validation[k] for k in ('passed','max_abs_error')},
                               **measure(binary,n,args.steps,args.repeat,args.warmup,validation))
                    row['myrk']['effective_state_gb_s']=n*4*width*args.steps/(row['myrk']['kernel_median_ms']/1000)/1e9
                    report['results'].append(row)
            print(json.dumps(report,indent=2))
    except (RuntimeError,OSError,ValueError) as error:
        parser.exit(1,f'benchmark failed; no performance report: {error}\n')
    return 0


if __name__=='__main__':
    raise SystemExit(main())
