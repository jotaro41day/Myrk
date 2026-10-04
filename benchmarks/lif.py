"""LIF time-driven C baseline and Python numerical oracle (not a Myrk claim)."""

import argparse
import json
import os
from pathlib import Path
import platform
import shutil
import tempfile

from .run import benchmark, run_binary, timed


ROOT = Path(__file__).resolve().parent


def python_reference(neurons: int, steps: int) -> tuple[int, float]:
    voltage = [0.0] * neurons
    spikes = 0
    for _ in range(steps):
        for i in range(neurons):
            input_current = 1.2 + (i % 7) * 0.1
            value = voltage[i] + (input_current - voltage[i]) * 0.05
            if value >= 1.0:
                spikes += 1
                value = 0.0
            voltage[i] = value
    return spikes, sum(voltage)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--neurons", type=int, default=50000)
    parser.add_argument("--steps", type=int, default=200)
    parser.add_argument("--repeat", type=int, default=7)
    args = parser.parse_args()
    if min(args.neurons, args.steps, args.repeat) < 1:
        parser.error("all counts must be positive")
    cc = os.environ.get("CC") or shutil.which("clang") or shutil.which("cc")
    if not cc:
        parser.error("C compiler missing")
    with tempfile.TemporaryDirectory(prefix="myrk-lif-bench-") as temp:
        binary = Path(temp) / "lif-reference"
        compile_seconds, result = timed([cc, "-std=c11", "-O2", "-fwrapv",
                                         "-fno-fast-math", "-ffp-contract=off",
                                         str(ROOT / "lif_reference.c"), "-o", str(binary)])
        if result.returncode:
            raise RuntimeError(result.stderr)
        _, small, code, _ = run_binary(binary, (64, 200))
        if code:
            raise RuntimeError("C LIF oracle failed")
        c_spikes, c_sum = small.split()
        py_spikes, py_sum = python_reference(64, 200)
        if int(c_spikes) != py_spikes or abs(float(c_sum) - py_sum) > 1e-8:
            raise RuntimeError(f"C/Python LIF mismatch: {small} vs {(py_spikes, py_sum)}")
        _, checksum, code, _ = run_binary(binary, (args.neurons, args.steps))
        if code:
            raise RuntimeError("C LIF benchmark failed")
        report = benchmark(binary, args.repeat, 2, checksum,
                           args.neurons * args.steps, (args.neurons, args.steps))
        report["neuron_updates_per_second"] = report.pop("iterations_per_second")
        print(json.dumps({"workload": "independent LIF neurons, Euler dt/tau=0.05, f64, SoA",
                          "role": "C baseline only; Python validates a smaller equivalent case",
                          "hardware": {"machine": platform.machine(), "system": platform.platform()},
                          "compiler": cc, "neurons": args.neurons, "steps": args.steps,
                          "checksum": checksum, "compile_ms": round(compile_seconds * 1000, 3),
                          "measurements": report}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
