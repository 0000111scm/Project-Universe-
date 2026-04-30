from _test_utils import make_body, assert_simulation_sane
from simulation import Simulation

sim = Simulation()
a = make_body(480, 400, 45, 0, 1e3, 12, (50, 120, 220), "Planeta A", "rock")
b = make_body(505, 400, -45, 0, 8e2, 10, (200, 80, 50), "Planeta B", "rock")
sim.add_body(a)
sim.add_body(b)

for _ in range(120):
    sim.step(0.016)
    assert_simulation_sane(sim)

assert len(sim.bodies) >= 1
print("OK: collisions")
