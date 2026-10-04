"""Slow independent scalar oracle. Never a performance competitor.

Euler simultaneous, threshold/reset after step. Round EVERY primitive operation
for f32 so differential tests do not silently compare different arithmetic.
"""
import struct


def rounding(dtype):
    if dtype == 'f64':
        return float
    if dtype == 'f32':
        return lambda x: struct.unpack('f', struct.pack('f', x))[0]
    raise ValueError(dtype)


def step(v, u, *, dtype='f64', a=0.02, b=0.2, c=-65.0, d=8.0, dt=0.5, current=10.0):
    r = rounding(dtype)
    v, u, a, b, c, d, dt, current = map(r, (v, u, a, b, c, d, dt, current))
    quadratic = r(r(r(0.04) * v) * v)
    linear = r(r(5.0) * v)
    drive = r(r(r(r(quadratic + linear) + r(140.0)) - u) + current)
    next_v = r(v + r(dt * drive))
    next_u = r(u + r(dt * r(a * r(r(b * v) - u))))
    fired = next_v >= r(30.0)
    return (c if fired else next_v, r(next_u + d) if fired else next_u, int(fired))
