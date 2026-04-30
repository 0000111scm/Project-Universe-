from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from simulation import Simulation
from body import Body

sim = Simulation()
assert getattr(sim, "use_collision_event_queue", False) is True

bodies = [
    Body(470, 400, 160, 0, 1000, 12, (50, 120, 220), "A"),
    Body(530, 400, -160, 0, 1000, 12, (200, 80, 50), "B"),
    Body(500, 455, 0, -160, 900, 11, (80, 200, 120), "C"),
]
for b in bodies:
    b.material = "rock"
    sim.add_body(b)

for _ in range(180):
    sim.step(0.016)
    assert len(sim.bodies) <= sim.max_bodies
    for b in sim.bodies:
        assert b.mass >= 0
        assert b.radius > 0

rock_frags = [b for b in sim.bodies if getattr(b, "is_fragment", False) and getattr(b, "material", "") == "rock"]
assert len(rock_frags) <= 12, f"fragmentos demais: {len(rock_frags)}"

print("OK: collision event queue stability")
