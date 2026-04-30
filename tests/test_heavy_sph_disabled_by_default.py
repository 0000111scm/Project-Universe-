from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from simulation import Simulation

sim = Simulation()
assert hasattr(sim, "collision_safety")
assert sim.collision_safety.enable_heavy_sph_replacement is False
assert sim.collision_safety.max_fragments_per_frame <= 18

print("OK: heavy SPH disabled by default")
