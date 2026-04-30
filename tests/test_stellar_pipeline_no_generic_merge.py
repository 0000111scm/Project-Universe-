from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from simulation import Simulation
from body import Body

sim = Simulation()
a = Body(490, 400, 8, 0, 3.33e8, 30, (255, 210, 50), "Sol A")
a.material = "plasma"
b = Body(520, 400, -8, 0, 3.33e8, 30, (255, 180, 80), "Sol B")
b.material = "plasma"
sim.add_body(a)
sim.add_body(b)

for _ in range(70):
    sim.step(0.016)

assert any(getattr(x, "is_common_envelope", False) for x in sim.bodies), "sem envelope comum"
assert not any(getattr(x, "name", "") == "Estrela Fundida" and getattr(x, "common_envelope_age", 0) < 2.0 for x in sim.bodies)

print("OK: stellar pipeline no generic merge")
