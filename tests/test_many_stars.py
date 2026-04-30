import math
from _test_utils import make_body, assert_simulation_sane
from simulation import Simulation

sim = Simulation()
cx, cy = 500, 400

for i in range(12):
    ang = math.tau * i / 12
    x = cx + math.cos(ang) * 80
    y = cy + math.sin(ang) * 80
    vx = -math.cos(ang) * 20
    vy = -math.sin(ang) * 20
    sim.add_body(make_body(x, y, vx, vy, 3.33e8, 24, (255, 200, 80), f"Estrela {i}", "plasma"))

for _ in range(180):
    sim.step(0.016)
    assert_simulation_sane(sim)

assert len(sim.bodies) <= sim.max_bodies
print("OK: many stars sanity")
