from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from simulation import Simulation
from body import Body

sim = Simulation()

b1 = Body(470, 400, 170, 0, 1000, 12, (50, 120, 220), "A")
b1.material = "rock"
b2 = Body(530, 400, -170, 0, 1000, 12, (200, 80, 50), "B")
b2.material = "rock"
b3 = Body(500, 455, 0, -170, 900, 11, (80, 200, 120), "C")
b3.material = "rock"

sim.add_body(b1)
sim.add_body(b2)
sim.add_body(b3)

for _ in range(160):
    sim.step(0.016)
    assert len(sim.bodies) <= sim.max_bodies
    for b in sim.bodies:
        assert b.mass > 0
        assert b.radius > 0

assert hasattr(sim, "collision_budget")
print("OK: multi impact stability")
