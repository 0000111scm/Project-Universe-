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

for _ in range(90):
    sim.step(0.016)

stellar_main = [x for x in sim.bodies if getattr(x, "material", "") == "plasma" and not getattr(x, "is_fragment", False)]
assert len(stellar_main) >= 2, f"regressão: estrelas fundiram cedo demais ({len(stellar_main)})"
assert any(getattr(x, "common_envelope_phase", None) for x in stellar_main), "sem envelope comum"

print("OK: stellar no instant merge regression")
