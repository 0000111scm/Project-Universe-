from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from simulation import Simulation
from body import Body

sim = Simulation()

sun = Body(500, 400, 0, 0, 3.33e8, 30, (255, 210, 50), "Sol")
sun.material = "plasma"
earth = Body(526, 400, -90, 0, 1000, 8, (50, 120, 220), "Terra")
earth.material = "rock"

sim.add_body(sun)
sim.add_body(earth)

for _ in range(100):
    sim.step(0.016)

names = [getattr(b, "name", "") for b in sim.bodies]
assert "Terra" not in names, "planeta deveria ter sido absorvido/vaporizado pela estrela"

rock_frags = [b for b in sim.bodies if getattr(b, "is_fragment", False) and getattr(b, "material", "") == "rock"]
assert len(rock_frags) == 0, f"estrela gerou detrito rochoso falso: {len(rock_frags)}"

stars = [b for b in sim.bodies if getattr(b, "material", "") == "plasma" and not getattr(b, "is_fragment", False)]
assert stars, "estrela sumiu"
assert stars[0].mass > 3.33e8, "estrela não absorveu massa"

print("OK: star planet accretion")
