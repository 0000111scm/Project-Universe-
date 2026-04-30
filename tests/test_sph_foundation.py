from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from physics_core.sph import SPHParticleSet, sample_body_particles, step_sph
from body import Body

b = Body(0, 0, 10, 0, 1000, 12, (50, 120, 220), "Teste")
b.material = "rock"
b.temperature = 300

pos, vel, mass, temp, mat = sample_body_particles(b, count=32)
assert pos.shape == (32, 2)
assert vel.shape == (32, 2)
assert abs(mass.sum() - b.mass) < 1e-6

ps = SPHParticleSet()
ps.add_particles(pos, vel, mass, temp, mat, owner=1)
step_sph(ps, 0.01)

assert ps.count == 32
assert ps.density[:ps.count].max() > 0
assert ps.temperature[:ps.count].min() >= 3.0

print("OK: SPH foundation")
