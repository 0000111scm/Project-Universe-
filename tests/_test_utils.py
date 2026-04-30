import math
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def assert_close_ratio(before, after, tolerance, label):
    before = float(before)
    after = float(after)
    if abs(before) < 1e-9:
        assert abs(after) < tolerance, f"{label}: esperado ~0, veio {after}"
        return
    diff = abs(after - before) / abs(before)
    assert diff <= tolerance, f"{label}: variação {diff:.3f} > limite {tolerance:.3f}. antes={before}, depois={after}"


def finite(v):
    return math.isfinite(float(v))


def assert_finite_body(body):
    vals = [body.pos.x, body.pos.y, body.vel.x, body.vel.y, body.acc.x, body.acc.y, body.mass, body.radius]
    for v in vals:
        assert finite(v), f"valor inválido em {getattr(body, 'name', 'body')}: {v}"
    assert body.mass > 0, f"massa inválida em {getattr(body, 'name', 'body')}"
    assert body.radius > 0, f"raio inválido em {getattr(body, 'name', 'body')}"


def assert_simulation_sane(sim):
    assert len(sim.bodies) <= getattr(sim, "max_bodies", 9999), "excedeu MAX_BODIES"
    for b in sim.bodies:
        assert_finite_body(b)


def make_body(x, y, vx, vy, mass, radius, color=(200, 200, 200), name="Corpo", material=None):
    from body import Body
    b = Body(x, y, vx, vy, mass, radius, color, name)
    if material:
        b.material = material
    return b


def total_mass(sim):
    return sum(float(b.mass) for b in sim.bodies)


def total_momentum(sim):
    px = sum(float(b.mass) * float(b.vel.x) for b in sim.bodies)
    py = sum(float(b.mass) * float(b.vel.y) for b in sim.bodies)
    return px, py


def momentum_mag(p):
    return math.sqrt(p[0] * p[0] + p[1] * p[1])


def kinetic_energy(sim):
    return sum(0.5 * float(b.mass) * float(b.vel.length_squared()) for b in sim.bodies)


def potential_energy(sim, G=0.6006, softening=25.0):
    e = 0.0
    bodies = sim.bodies
    for i, a in enumerate(bodies):
        for b in bodies[i+1:]:
            d2 = (a.pos - b.pos).length_squared() + softening
            e -= G * a.mass * b.mass / math.sqrt(d2)
    return e


def total_energy(sim):
    return kinetic_energy(sim) + potential_energy(sim)


def run_steps(sim, frames=120, dt=0.016):
    for _ in range(frames):
        sim.step(dt)
        assert_simulation_sane(sim)


def timed_steps(sim, frames=240, dt=0.016):
    t0 = time.perf_counter()
    run_steps(sim, frames, dt)
    return time.perf_counter() - t0
