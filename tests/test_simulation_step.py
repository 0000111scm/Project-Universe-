from _test_utils import make_body, assert_simulation_sane
from simulation import Simulation

sim = Simulation()
sim.add_body(make_body(500, 400, 0, 0, 3.33e8, 30, (255, 210, 50), "Sol", "plasma"))
sim.add_body(make_body(650, 400, 0, 1150, 1e3, 8, (50, 120, 220), "Terra", "rock"))

for _ in range(180):
    sim.step(0.016)
    assert_simulation_sane(sim)

print("OK: simulation step")
