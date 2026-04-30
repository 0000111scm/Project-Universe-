from _test_utils import make_body, assert_simulation_sane
from simulation import Simulation

sim = Simulation()
primary = make_body(500, 400, 0, 0, 3.33e8, 30, (255, 210, 50), "Sol", "plasma")
moon = make_body(545, 400, 0, 0, 100, 5, (180, 180, 180), "Lua", "rock")
sim.add_body(primary)
sim.add_body(moon)

for _ in range(120):
    sim.step(0.016)
    assert_simulation_sane(sim)

print("OK: roche sanity")
