from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from simulation import Simulation
from body import Body

sim = Simulation()
a = Body(480, 400, 120, 0, 1000, 12, (50, 120, 220), "Planeta A")
a.material = "rock"
b = Body(505, 400, -120, 0, 900, 11, (200, 80, 50), "Planeta B")
b.material = "rock"

sim.add_body(a)
sim.add_body(b)

for _ in range(180):
    sim.step(0.016)

assert any(hasattr(body, "surface_grid") for body in sim.bodies)
for body in sim.bodies:
    if hasattr(body, "surface_grid"):
        assert body.surface_grid.temperature.max() >= 3.0

print("OK: collision surface grid")
