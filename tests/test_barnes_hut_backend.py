from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import math
from simulation import Simulation
from body import Body

sim = Simulation()
sim.physics_core.barnes_hut_threshold = 16

cx, cy = 500, 400
sun = Body(cx, cy, 0, 0, 3.33e8, 30, (255, 210, 50), "Sol")
sun.material = "plasma"
sim.add_body(sun)

for i in range(40):
    ang = math.tau * i / 40
    dist = 180 + (i % 10) * 12
    x = cx + math.cos(ang) * dist
    y = cy + math.sin(ang) * dist
    vx = -math.sin(ang) * 750
    vy = math.cos(ang) * 750
    b = Body(x, y, vx, vy, 5.0, 2, (160, 160, 150), f"Ast {i}")
    b.material = "rock"
    sim.add_body(b)

for _ in range(60):
    sim.step(0.016)

assert sim.physics_core.last_backend == "barnes_hut_2d"
assert len(sim.bodies) <= sim.max_bodies
for b in sim.bodies:
    assert b.mass > 0
    assert math.isfinite(b.pos.x)
    assert math.isfinite(b.pos.y)

print("OK: Barnes-Hut backend")
