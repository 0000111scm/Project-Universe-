from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from simulation import Simulation
from physics_core.bridge import build_state_from_bodies
from body import Body

sim = Simulation()
assert getattr(sim, "core_dimension", 2) == 3
assert getattr(sim, "use_3d_core", False) is True

b = Body(0, 0, 0, 0, 1000, 10, (255,255,255), "B")
sim.add_body(b)
state, _, _ = build_state_from_bodies(sim.bodies)
assert state.pos.shape[1] == 3
assert state.vel.shape[1] == 3

print("OK: 3D core activation")
