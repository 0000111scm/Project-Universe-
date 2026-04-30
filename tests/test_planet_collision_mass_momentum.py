from _test_utils import make_body, total_mass, total_momentum, momentum_mag, assert_simulation_sane
from simulation import Simulation

sim = Simulation()
a = make_body(480, 400, 55, 0, 1e3, 12, (50, 120, 220), "Planeta A", "rock")
b = make_body(505, 400, -55, 0, 8e2, 10, (200, 80, 50), "Planeta B", "rock")
sim.add_body(a); sim.add_body(b)

m0 = total_mass(sim)
p0 = total_momentum(sim)

for _ in range(180):
    sim.step(0.016)
    assert_simulation_sane(sim)

m1 = total_mass(sim)
p1 = total_momentum(sim)

assert m1 <= m0 * 1.02, f"massa criada: antes={m0}, depois={m1}"
assert m1 >= m0 * 0.45, f"massa perdida demais: antes={m0}, depois={m1}"
assert momentum_mag(p1) < max(momentum_mag(p0) * 3.0, 2e5), f"momentum explodiu: antes={p0}, depois={p1}"

print("OK: planet collision mass/momentum")
