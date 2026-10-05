"""Correctness-gated single-thread lab for IF/LIF/QIF/AdEx/HH native updates.

Izhikevich retains its existing neuron.izhikevich lab (including multicore).
"""
import argparse
import json
import math
import os
from pathlib import Path
import platform
import shutil
import statistics
import tempfile
import time
from myrk.codegen_c import generate
from myrk.parser import parse
from myrk.semantics import check
from myrk.models import MODELS, prefix, population_type
from .izhikevich import checked
from .model_reference import DEFAULTS, declaration, initialize, step
from .reference import rounding

ROOT=Path(__file__).resolve().parent
NAMES=['IF','LIF','QIF','AdEx','HH']


def build_driver(directory,model,dtype,cc):
    directory=Path(directory).resolve();directory.mkdir(parents=True,exist_ok=True)
    generated=directory/f'{model}-{dtype}.c'
    started=time.perf_counter()
    generated.write_text(generate(check(parse('fn main() -> i32 {'+declaration(model,dtype)+
                                            'step(p); return 0;}'))))
    frontend_ms=(time.perf_counter()-started)*1000
    definition=MODELS[model];states=definition.states
    substitutions={'GENERATED':generated.name,'REAL':'float' if dtype=='f32' else 'double',
        'LITERAL':'x##f' if dtype=='f32' else 'x','EXP':'expf' if dtype=='f32' else 'exp',
        'EXPM1':'expm1f' if dtype=='f32' else 'expm1','MODEL':str(NAMES.index(model)),
        'POPULATION':population_type(model,dtype),'NSTATES':str(len(states)),'PREFIX':prefix(model,dtype),
        'PARAMETERS':' '.join(f'p.{k}=R({v});' for k,v in DEFAULTS[model].items()),
        'ALLOCATIONS':' '.join(f'p.{s}=myrk_alloc(n,sizeof(REAL));' for s in states),
        'BUFFERS':' '.join(f'out[{i}]=p->{s};' for i,s in enumerate(states)),
        'FREES':' '.join(f'free(p->{s});' for s in states),'HETEROGENEOUS_GATES':''}
    if model=='HH':
        substitutions['HETEROGENEOUS_GATES']=f'''REAL am,bm,ah,bh,an,bn;
            {prefix(model,dtype)}_rates(p.v[i],&am,&bm,&ah,&bh,&an,&bn);
            p.m[i]=am/(am+bm);p.h[i]=ah/(ah+bh);p.n[i]=an/(an+bn);'''
    source=ROOT.joinpath('models_driver.c').read_text()
    for token,value in substitutions.items():source=source.replace('@'+token+'@',value)
    c_file=directory/f'bench-{model}-{dtype}.c';c_file.write_text(source)
    shutil.copyfile(ROOT/'reference_models.h',directory/'reference_models.h')
    binary=directory/f'bench-{model}-{dtype}'
    flags=['-std=c11','-O2','-fwrapv','-fno-fast-math','-ffp-contract=off','-pthread']
    started=time.perf_counter();checked([cc,*flags,c_file,'-o',binary,'-lm'])
    compile_ms=(time.perf_counter()-started)*1000
    checked([cc,*flags,'-S',c_file,'-o',directory/f'bench-{model}-{dtype}.s'])
    return binary,dict(flags=flags,link_libraries=['m'],frontend_ms=frontend_ms,
                       native_compile_ms=compile_ms,binary_bytes=binary.stat().st_size)


def oracle_gate(binary,model,dtype):
    n,steps=17,80;r=rounding(dtype);params=DEFAULTS[model]
    states=[initialize(model,{**params,'v_init':r(r(params['v_init'])+r((i%17)*0.125))},dtype)
            for i in range(n)]
    rows=checked([binary,'trace','myrk',n,steps],1).splitlines()
    if len(rows)!=steps:raise RuntimeError('wrong Python oracle trace length')
    maximum=0.0
    for row in rows:
        values=row.split();expected_count=0;offset=1
        if len(values)!=1+n*len(states[0]):raise RuntimeError('wrong Python oracle trace width')
        for i in range(n):
            states[i],fired=step(model,states[i],params,dtype);expected_count+=fired
            for expected in states[i]:
                actual=r(float(values[offset]));offset+=1;error=abs(actual-expected);maximum=max(maximum,error)
                tolerance=0.003 if dtype=='f32' else 1e-9
                if not math.isfinite(actual) or error>tolerance:
                    raise RuntimeError(f'Python oracle state mismatch {model}/{dtype}, neuron {i}')
        if int(values[0])!=expected_count:raise RuntimeError('Python oracle spike mismatch')
    return dict(passed=True,neurons=n,steps=steps,max_abs_error=maximum,
                note='libm rounding tolerance for states; exact per-step spike count')


def measure(binary,n,steps,repeat,warmup,expected,dt_ms):
    samples={'myrk':[],'c':[]}
    for run in range(warmup+repeat):
        for backend in (['myrk','c'] if run%2==0 else ['c','myrk']):
            started=time.perf_counter();row=json.loads(checked([binary,'run',backend,n,steps],1))
            row['process_ms']=(time.perf_counter()-started)*1000
            for key in ('spikes','last_spikes','state_hash','sums'):
                if row[key]!=expected[key]:raise RuntimeError(f'{backend} wrong {key}; timing discarded')
            if row['seconds']<=0:raise RuntimeError('invalid native clock interval')
            if run>=warmup:samples[backend].append(row)
    result={}
    for backend,rows in samples.items():
        durations=[row['seconds'] for row in rows];median=statistics.median(durations)
        rss=[row['peak_rss_kib'] for row in rows if row['peak_rss_kib']>=0]
        result[backend]=dict(kernel_median_ms=median*1000,samples_ms=[d*1000 for d in durations],
            ms_per_timestep=median*1000/steps,updates_per_second=n*steps/median,
            realtime_factor=steps*dt_ms*.001/median,threads=1,
            peak_rss_kib_median=statistics.median(rss) if rss else None,
            process_median_ms=statistics.median(r['process_ms'] for r in rows),
            spikes=rows[0]['spikes'],last_spikes=rows[0]['last_spikes'],
            state_hash=rows[0]['state_hash'],sums=rows[0]['sums'])
    return result


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--models',nargs='+',choices=NAMES,default=NAMES)
    parser.add_argument('--sizes',nargs='+',type=int,default=[1000,10000])
    parser.add_argument('--dtype',choices=['f32','f64','both'],default='both')
    parser.add_argument('--steps',type=int,default=200)
    parser.add_argument('--repeat',type=int,default=5)
    parser.add_argument('--warmup',type=int,default=2)
    parser.add_argument('--max-mib',type=int,default=512)
    parser.add_argument('--artifacts',type=Path)
    parser.add_argument('--output',type=Path)
    parser.add_argument('--summary',action='store_true')
    args=parser.parse_args(argv)
    if any(not 1<=n<=2147483647 for n in args.sizes) or not 1<=args.steps<=2147483647:
        parser.error('sizes and steps must be in [1,2147483647]')
    if args.repeat<1 or args.warmup<0 or args.max_mib<1:
        parser.error('repeat/max-mib must be positive and warmup nonnegative')
    cc=os.environ.get('CC') or shutil.which('clang') or shutil.which('cc')
    if not cc:parser.error('install clang or set CC')
    try:
        report=dict(category='neuron_update',mode='strict; no FMA contraction',threads=1,
            compiler=checked([cc,'--version']).splitlines()[0],steps=args.steps,
            repeat=args.repeat,warmup=args.warmup,
            initialization='v_init+(i%17)*0.125; HH gates at equilibrium of varied initial v',
            hardware=dict(machine=platform.machine(),system=platform.platform()),results=[])
        with tempfile.TemporaryDirectory(prefix='myrk-models-') as temp:
            directory=args.artifacts or Path(temp)
            for model in args.models:
                for dtype in (['f32','f64'] if args.dtype=='both' else [args.dtype]):
                    binary,compilation=build_driver(directory,model,dtype,cc)
                    oracle=oracle_gate(binary,model,dtype)
                    definition=MODELS[model];width=4 if dtype=='f32' else 8
                    for n in args.sizes:
                        row=dict(model=model,solver=definition.solver,dtype=dtype,neurons=n,
                            dt_ms=DEFAULTS[model]['dt'],parameters=DEFAULTS[model],states=definition.states,
                            bytes_per_neuron=len(definition.states)*width,state_bytes=n*len(definition.states)*width)
                        row['validation_payload_bytes']=row['state_bytes']*2
                        if row['validation_payload_bytes']>args.max_mib*1024*1024:
                            row['status']='skipped_memory_budget';report['results'].append(row);continue
                        validation=json.loads(checked([binary,'validate','myrk',n,args.steps],1))
                        row.update(status='measured',compilation=compilation,python_oracle=oracle,
                            validation={k:validation[k] for k in ('passed','max_abs_error')},
                            **measure(binary,n,args.steps,args.repeat,args.warmup,validation,DEFAULTS[model]['dt']))
                        report['results'].append(row)
        serialized=json.dumps(report,indent=2)
        if args.output:args.output.write_text(serialized+'\n')
        if args.summary:
            print('Native single-thread neuron updates; independent C gate; no synapses')
            print('model dtype N Myrk_ms C_ms M_updates/s realtime')
            for row in report['results']:
                if row['status']!='measured':print(row['model'],row['dtype'],row['neurons'],row['status']);continue
                m=row['myrk'];print(f'{row["model"]} {row["dtype"]} {row["neurons"]} '
                    f'{m["kernel_median_ms"]:.3f} {row["c"]["kernel_median_ms"]:.3f} '
                    f'{m["updates_per_second"]/1e6:.1f} {m["realtime_factor"]:.3f}')
            if args.output:print(f'Full JSON: {args.output}')
        else:print(serialized)
    except (RuntimeError,OSError,ValueError) as error:
        parser.exit(1,f'benchmark failed; no performance report: {error}\n')
    return 0


if __name__=='__main__':raise SystemExit(main())
