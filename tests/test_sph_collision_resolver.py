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
b = Body(506, 400, -120, 0, 900, 11, (200, 80, 50), "Planeta B")
b.material = "rock"

sim.add_body(a)
sim.add_body(b)

for _ in range(180):
    sim.step(0.016)

assert len(sim.bodies) >= 1
for body in sim.bodies:
    assert body.mass > 0
    assert body.radius > 0
    assert body.temperature >= 3.0

# Deve existir alguma consequência material, nem que seja fase/dano/temperatura.
assert any(
    hasattr(body, "phase") or getattr(body, "surface_damage", 0.0) > 0 or body.temperature > 300
    for body in sim.bodies
)

print("OK: SPH collision resolver")
