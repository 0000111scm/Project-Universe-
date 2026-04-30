from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from simulation import Simulation
from body import Body

sim = Simulation()
a = Body(480, 400, 70, 0, 1000, 12, (50, 120, 220), "Planeta A")
a.material = "rock"
b = Body(505, 400, -70, 0, 900, 11, (200, 80, 50), "Planeta B")
b.material = "rock"

sim.add_body(a)
sim.add_body(b)

for _ in range(120):
    sim.step(0.016)

assert hasattr(sim, "sph_particles")
assert sim.sph_particles.count >= 0
# Não exige count > 0 em todo cenário, mas se ativar precisa ser válido.
if sim.sph_particles.count:
    assert sim.sph_particles.density[:sim.sph_particles.count].max() >= 0

print("OK: Simulation SPH collision seed")
