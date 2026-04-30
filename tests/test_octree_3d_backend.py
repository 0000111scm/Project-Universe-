from pathlib import Path
import sys, math
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from simulation import Simulation
from body import Body

sim = Simulation()
sim.physics_core.octree_threshold = 16

cx, cy = 500, 400
sun = Body(cx, cy, 0, 0, 3.33e8, 30, (255, 210, 50), "Sol")
sun.material = "plasma"
sim.add_body(sun)

for i in range(36):
    ang = math.tau * i / 36
    dist = 170 + (i % 9) * 12
    b = Body(cx + math.cos(ang)*dist, cy + math.sin(ang)*dist, -math.sin(ang)*700, math.cos(ang)*700, 5, 2, (160,160,150), f"Ast {i}")
    b.material = "rock"
    sim.add_body(b)

for _ in range(50):
    sim.step(0.016)

assert sim.physics_core.last_backend in ("octree_3d", "barnes_hut_2d", "direct_nbody")
assert sim.physics_core.last_backend == "octree_3d"

print("OK: octree 3d backend")
