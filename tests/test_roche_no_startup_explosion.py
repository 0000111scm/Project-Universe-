from _test_utils import make_body, assert_simulation_sane, total_mass
from simulation import Simulation

sim = Simulation()
primary = make_body(500, 400, 0, 0, 3.33e8, 30, (255, 210, 50), "Sol", "plasma")
planet = make_body(650, 400, 0, 1155, 1e3, 8, (50, 120, 220), "Terra", "rock")
sim.add_body(primary); sim.add_body(planet)

m0 = total_mass(sim)

for _ in range(180):
    sim.step(0.016)
    assert_simulation_sane(sim)

assert len(sim.bodies) <= 5, f"Roche explodiu corpos no início: {len(sim.bodies)} corpos"
assert total_mass(sim) <= m0 * 1.01

print("OK: roche no startup explosion")
