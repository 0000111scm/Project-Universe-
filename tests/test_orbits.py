from _test_utils import make_body, assert_simulation_sane
from simulation import Simulation

sim = Simulation()
sun = make_body(500, 400, 0, 0, 3.33e8, 30, (255, 210, 50), "Sol", "plasma")
earth = make_body(650, 400, 0, 1155, 1e3, 8, (50, 120, 220), "Terra", "rock")
sim.add_body(sun)
sim.add_body(earth)

initial_dist = (earth.pos - sun.pos).length()

for _ in range(240):
    sim.step(0.016)
    assert_simulation_sane(sim)

final_dist = (earth.pos - sun.pos).length()
assert final_dist > 20
assert final_dist < initial_dist * 8.0

print("OK: orbit sanity")
