from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from simulation import Simulation
from body import Body

sim = Simulation()
a = Body(480, 400, 90, 0, 1000, 12, (50, 120, 220), "Planeta A")
a.material = "rock"
b = Body(505, 400, -90, 0, 900, 11, (200, 80, 50), "Planeta B")
b.material = "rock"
sim.add_body(a)
sim.add_body(b)

for _ in range(180):
    sim.step(0.016)

assert hasattr(sim, "sph_particles")
if sim.sph_particles.count:
    assert sim.sph_particles.temperature[:sim.sph_particles.count].max() >= 3.0
    assert sim.sph_particles.phase_id[:sim.sph_particles.count].max() >= 0

for body in sim.bodies:
    assert body.mass > 0
    assert body.radius > 0

print("OK: SPH coupling")
