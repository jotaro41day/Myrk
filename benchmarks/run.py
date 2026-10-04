"""Comparable scalar-loop smoke benchmark; no speed claims from one machine."""

import argparse
import json
import os
from pathlib import Path
import platform
import shutil
import statistics
import subprocess
import sys
import tempfile
import time


ROOT = Path(__file__).resolve().parents[1]
ITERATIONS = 50_000_000
EXPECTED = "149999997"


def timed(command: list[str]) -> tuple[float, subprocess.CompletedProcess[str]]:
    start = time.perf_counter()
    result = subprocess.run(command, capture_output=True, text=True)
    return time.perf_counter() - start, result


def run_binary(binary: Path, arguments: tuple = ()) -> tuple[float, str, int, int | None]:
    """Measure one child. wait4 reports this child's peak RSS on Linux."""
    if not hasattr(os, "wait4"):
        elapsed, result = timed([str(binary), *(str(arg) for arg in arguments)])
        return elapsed, result.stdout.strip(), result.returncode, None
    with tempfile.TemporaryFile(mode="w+t") as stdout, tempfile.TemporaryFile(mode="w+t") as stderr:
        start = time.perf_counter()
        process = subprocess.Popen([str(binary), *(str(arg) for arg in arguments)],
                                   stdout=stdout, stderr=stderr)
        _, status, usage = os.wait4(process.pid, 0)
        elapsed = time.perf_counter() - start
        process.returncode = os.waitstatus_to_exitcode(status)
        stdout.seek(0)
        stderr.seek(0)
        return elapsed, stdout.read().strip(), process.returncode, usage.ru_maxrss


def benchmark(binary: Path, repeat: int, warmup: int, expected: str,
              iterations: int | None = None, arguments: tuple = ()) -> dict:
    for _ in range(warmup):
        _, output, code, _ = run_binary(binary, arguments)
        if code or output != expected:
            raise RuntimeError(f"wrong checksum: {output!r}")
    times = []
    peaks = []
    for _ in range(repeat):
        elapsed, output, code, peak = run_binary(binary, arguments)
        if code or output != expected:
            raise RuntimeError(f"wrong result: {output!r}, exit={code}")
        times.append(elapsed)
        if peak is not None:
            peaks.append(peak)
    median = statistics.median(times)
    result = {"median_ms": round(median * 1000, 3),
            "min_ms": round(min(times) * 1000, 3),
            "max_ms": round(max(times) * 1000, 3),
            "samples_ms": [round(value * 1000, 3) for value in times],
            "peak_rss_kib_median": statistics.median(peaks) if peaks else None,
            "binary_bytes": binary.stat().st_size}
    if iterations is not None:
        result["iterations_per_second"] = round(iterations / median)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repeat", type=int, default=7)
    parser.add_argument("--warmup", type=int, default=2)
    args = parser.parse_args()
    if args.repeat < 1 or args.warmup < 0:
        parser.error("repeat must be positive and warmup cannot be negative")
    cc = os.environ.get("CC") or shutil.which("clang") or shutil.which("cc")
    if not cc:
        parser.error("C compiler missing")
    with tempfile.TemporaryDirectory(prefix="myrk-bench-") as temp:
        temp = Path(temp)
        myrk_binary = temp / "myrk-scalar"
        c_binary = temp / "c-scalar"
        myrk_hello = temp / "myrk-hello"
        c_hello = temp / "c-hello"
        myrk_compile, result = timed([sys.executable, "-m", "myrk", "build",
                                      str(ROOT / "benchmarks/scalar.myrk"), "-o", str(myrk_binary)])
        if result.returncode:
            raise RuntimeError(result.stderr)
        c_compile, result = timed([cc, "-std=c11", "-O2", "-fwrapv", "-fno-fast-math",
                                   "-ffp-contract=off", str(ROOT / "benchmarks/scalar.c"),
                                   "-o", str(c_binary)])
        if result.returncode:
            raise RuntimeError(result.stderr)
        _, result = timed([sys.executable, "-m", "myrk", "build",
                           str(ROOT / "examples/hello.myrk"), "-o", str(myrk_hello)])
        if result.returncode:
            raise RuntimeError(result.stderr)
        hello_source = temp / "hello.c"
        hello_source.write_text('#include <stdio.h>\nint main(void) { puts("42"); return 0; }\n')
        _, result = timed([cc, "-O2", str(hello_source), "-o", str(c_hello)])
        if result.returncode:
            raise RuntimeError(result.stderr)
        output = {"workload": "sum(i % 7), i=0..49999999, i32, stdout checksum 149999997",
                  "hardware": {"machine": platform.machine(), "system": platform.platform(),
                               "processor": platform.processor()},
                  "compiler": cc, "repeat": args.repeat, "warmup": args.warmup,
                  "myrk": {"compile_ms": round(myrk_compile * 1000, 3),
                           **benchmark(myrk_binary, args.repeat, args.warmup, EXPECTED, ITERATIONS)},
                  "c": {"compile_ms": round(c_compile * 1000, 3),
                        **benchmark(c_binary, args.repeat, args.warmup, EXPECTED, ITERATIONS)},
                  "startup_proxy": {"description": "new process printing 42; includes launch and I/O",
                                    "myrk": benchmark(myrk_hello, args.repeat, args.warmup, "42"),
                                    "c": benchmark(c_hello, args.repeat, args.warmup, "42")}}
        print(json.dumps(output, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
