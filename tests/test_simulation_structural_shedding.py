from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from simulation import Simulation
from body import Body
from physics_core.structural_dynamics import critical_angular_velocity

sim = Simulation()
b = Body(500, 400, 0, 0, 1000, 14, (120, 120, 120), "Asteroide Rotativo")
b.material = "rock"
b.angular_velocity = critical_angular_velocity(b) * 2.0
sim.add_body(b)

for _ in range(80):
    sim.step(0.016)

assert any(hasattr(body, "structural_failure") for body in sim.bodies)
for body in sim.bodies:
    assert body.mass > 0
    assert body.radius > 0

print("OK: simulation structural shedding")
