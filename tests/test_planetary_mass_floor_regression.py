from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from simulation import Simulation
from body import Body

sim = Simulation()
a = Body(480, 400, 120, 0, 1000, 12, (50, 120, 220), "A")
a.material = "rock"
b = Body(505, 400, -120, 0, 800, 11, (200, 80, 50), "B")
b.material = "rock"
sim.add_body(a)
sim.add_body(b)

m0 = sum(x.mass for x in sim.bodies)
for _ in range(120):
    sim.step(0.016)

m1 = sum(x.mass for x in sim.bodies)
assert m1 >= m0 * 0.45, f"massa perdida demais: antes={m0}, depois={m1}"
assert len(sim.bodies) <= sim.max_bodies

print("OK: planetary mass floor regression")
