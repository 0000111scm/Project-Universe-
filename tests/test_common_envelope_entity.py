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

for _ in range(120):
    sim.step(0.016)

main_stars = [x for x in sim.bodies if getattr(x, "material", "") == "plasma" and not getattr(x, "is_fragment", False)]
envelopes = [x for x in sim.bodies if getattr(x, "is_common_envelope", False)]

assert len(main_stars) >= 2, "estrela fundiu cedo demais"
assert envelopes, "CommonEnvelope visível não foi criado"
assert any(getattr(x, "common_envelope_phase", None) for x in main_stars), "fase de envelope não registrada"

print("OK: common envelope entity")
