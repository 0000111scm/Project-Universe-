from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from simulation import Simulation
from body import Body
from physics_core.sph_body_mode import request_sph_mode, update_sph_body_modes

sim = Simulation()
b = Body(0, 0, 0, 0, 1000, 10, (255,255,255), "B")
b.material = "rock"
sim.add_body(b)

mode = request_sph_mode(b, "test", 0.5)
assert mode.pending is True
update_sph_body_modes(sim, 1.0)

# Pesado fica off por padrão.
assert getattr(b, "sph_mode").active is False

print("OK: SPH body mode safe")
