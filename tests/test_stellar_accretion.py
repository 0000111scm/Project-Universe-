from _test_utils import make_body, run_steps
from simulation import Simulation

sim = Simulation()
star = make_body(500, 400, 0, 0, 3.33e8, 30, (255, 210, 50), "Sol", "plasma")
planet = make_body(526, 400, -20, 0, 1e3, 8, (50, 120, 220), "Planeta", "rock")
sim.add_body(star); sim.add_body(planet)

m0 = star.mass
run_steps(sim, 160)

stars = [b for b in sim.bodies if getattr(b, "material", "") == "plasma" and b.mass > 5e7]
assert stars, "estrela sumiu"
largest_star = max(stars, key=lambda b: b.mass)
assert largest_star.mass >= m0, "estrela não acresceu massa"
assert not getattr(largest_star, "has_rings", False), "estrela herdou anel indevido"

print("OK: stellar accretion")
