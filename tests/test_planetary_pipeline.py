from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from simulation import Simulation
from body import Body

sim = Simulation()
a = Body(480, 400, 130, 0, 1000, 12, (50, 120, 220), "Terra A")
a.material = "rock"
b = Body(505, 400, -130, 0, 1000, 12, (50, 120, 220), "Terra B")
b.material = "rock"

sim.add_body(a)
sim.add_body(b)

for _ in range(180):
    sim.step(0.016)

assert len(sim.bodies) >= 1
for body in sim.bodies:
    assert body.mass > 0
    assert body.radius > 0
    assert not (getattr(body, "has_rings", False) and getattr(body, "material", "") == "rock")

assert any(
    "Remanescente" in getattr(body, "name", "")
    or getattr(body, "surface_damage", 0.0) > 0
    or getattr(body, "damage_accumulated", 0.0) > 0
    for body in sim.bodies
)

print("OK: planetary pipeline")
