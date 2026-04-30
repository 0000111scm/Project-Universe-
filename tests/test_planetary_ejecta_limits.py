from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from simulation import Simulation
from body import Body

sim = Simulation()
a = Body(480, 400, 170, 0, 1000, 12, (50, 120, 220), "Terra A")
a.material = "rock"
b = Body(505, 400, -170, 0, 1000, 12, (50, 120, 220), "Terra B")
b.material = "rock"

sim.add_body(a)
sim.add_body(b)

for _ in range(160):
    sim.step(0.016)

frags = [x for x in sim.bodies if getattr(x, "is_fragment", False) and getattr(x, "material", "") == "rock"]
for f in frags:
    assert f.radius <= 12 * 0.35, f"fragmento rochoso gigante: {f.radius}"
    assert f.vel.length() < 2500, f"fragmento rápido demais: {f.vel.length()}"

for body in sim.bodies:
    assert not (getattr(body, "has_rings", False) and getattr(body, "material", "") == "rock")

assert len(frags) <= 20, f"detrito visual exagerado: {len(frags)}"

print("OK: planetary ejecta limits")
