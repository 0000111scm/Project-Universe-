from _test_utils import make_body, run_steps
from simulation import Simulation

sim = Simulation()
bh = make_body(500, 400, 0, 0, 1.0e10, 10, (0, 0, 0), "Buraco Negro", "blackhole")
planet = make_body(525, 400, -20, 0, 1e3, 8, (50, 120, 220), "Planeta", "rock")
sim.add_body(bh); sim.add_body(planet)

m0 = bh.mass
run_steps(sim, 120)

assert any(getattr(b, "material", "") == "blackhole" or "Buraco" in getattr(b, "name", "") for b in sim.bodies), "buraco negro desapareceu"
largest = max(sim.bodies, key=lambda b: b.mass)
assert largest.mass >= m0, "buraco negro não reteve/acresceu massa"
print("OK: blackhole accretion")
