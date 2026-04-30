from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from simulation import Simulation
from body import Body

sim = Simulation()
a = Body(480, 400, 18, 0, 3.33e8, 30, (255, 210, 50), "Sol A")
a.material = "plasma"
b = Body(525, 400, -18, 0, 3.33e8, 30, (255, 180, 80), "Sol B")
b.material = "plasma"

sim.add_body(a)
sim.add_body(b)

# Poucos frames: deve formar envelope, não colapsar instantaneamente.
for _ in range(40):
    sim.step(0.016)

stellar = [x for x in sim.bodies if getattr(x, "material", "") == "plasma" and not getattr(x, "is_fragment", False)]
assert len(stellar) >= 2, f"colapsou/fundiu cedo demais: {len(stellar)} estrelas"
assert any(hasattr(x, "common_envelope_phase") for x in stellar), "envelope comum não registrado"

print("OK: stellar persistent envelope")
