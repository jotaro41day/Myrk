"""Emit the production kernel without libc headers for assembly inspection.

Example: python3 -m benchmarks.neuron.emit_kernel --dtype f32 > /tmp/kernel.c
clang --target=aarch64-linux-android24 -ffreestanding -O3 -fno-fast-math \
    -ffp-contract=off -S /tmp/kernel.c -o /tmp/kernel.s
This is cross compilation only; it does not validate execution on Android.
"""
import argparse
from myrk.neural import kernel


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dtype',choices=['f32','f64'],required=True)
    args=parser.parse_args()
    print('typedef int int32_t;')
    print(kernel(args.dtype).replace('static int32_t myrk_', 'int32_t myrk_'))


if __name__=='__main__':
    main()
