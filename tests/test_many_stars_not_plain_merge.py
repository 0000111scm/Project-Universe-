from pathlib import Path
import sys, math
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from simulation import Simulation
from body import Body

sim = Simulation()
cx, cy = 500, 400
for i in range(12):
    ang = math.tau * i / 12
    b = Body(cx + math.cos(ang)*60, cy + math.sin(ang)*60, -math.cos(ang)*25, -math.sin(ang)*25, 3.33e8, 24, (255, 200, 80), f"Estrela {i}")
    b.material = "plasma"
    sim.add_body(b)

for _ in range(120):
    sim.step(0.016)

names = [getattr(b, "name", "") for b in sim.bodies]
plasma_count = sum(1 for b in sim.bodies if getattr(b, "material", "") == "plasma")
assert plasma_count >= 1
assert any("Plasma ejetado" in n or hasattr(b, "common_envelope_phase") or getattr(b, "explosion_strength", 0) > 0 for b, n in zip(sim.bodies, names)), "sem envelope/ejeção visível"

print("OK: many stars not plain merge")
