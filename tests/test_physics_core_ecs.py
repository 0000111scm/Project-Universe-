from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from physics_core.state import create_state, add_entity, total_mass, center_of_mass
from physics_core.gravity import compute_nbody_acceleration, total_energy
from physics_core.integrators import leapfrog_step

state = create_state(2)
add_entity(state, 1, (0.0, 0.0, 0.0), (0.0, 0.0, 0.0), 1000.0, 10.0)
add_entity(state, 2, (100.0, 0.0, 0.0), (0.0, 2.0, 0.0), 1.0, 1.0)

assert state.pos.dtype.name == "float64"
assert state.vel.dtype.name == "float64"
assert abs(total_mass(state) - 1001.0) < 1e-9

e0 = total_energy(state)
for _ in range(20):
    leapfrog_step(state, 0.01, compute_nbody_acceleration)
e1 = total_energy(state)

assert abs(e1 - e0) / max(abs(e0), 1.0) < 0.05
com = center_of_mass(state)
assert com.shape == (3,)

print("OK: physics_core ECS fp64")
