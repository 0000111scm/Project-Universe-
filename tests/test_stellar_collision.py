from _test_utils import make_body, assert_simulation_sane
from simulation import Simulation

sim = Simulation()
s1 = make_body(480, 400, 15, 0, 3.33e8, 30, (255, 210, 50), "Sol A", "plasma")
s2 = make_body(525, 400, -15, 0, 3.33e8, 30, (255, 180, 80), "Sol B", "plasma")
sim.add_body(s1)
sim.add_body(s2)

for _ in range(240):
    sim.step(0.016)
    assert_simulation_sane(sim)

assert len(sim.bodies) >= 1
assert not any(getattr(b, "material", "") == "rock" and getattr(b, "mass", 0) > 5e7 for b in sim.bodies)

print("OK: stellar collision sanity")
