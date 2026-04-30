from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from simulation import Simulation
from body import Body

sim = Simulation()
assert hasattr(sim, "physics_core")
assert getattr(sim, "use_physics_core", False) is True

sun = Body(500, 400, 0, 0, 3.33e8, 30, (255, 210, 50), "Sol")
sun.material = "plasma"
earth = Body(650, 400, 0, 1155, 1e3, 8, (50, 120, 220), "Terra")
earth.material = "rock"

sim.add_body(sun)
sim.add_body(earth)

for _ in range(120):
    sim.step(0.016)

assert sim.physics_core.last_energy is not None
assert sim.physics_core.energy_drift < 1.0

print("OK: Simulation uses physics_core")
