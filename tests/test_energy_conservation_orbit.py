from _test_utils import make_body, total_energy, run_steps, assert_close_ratio
from simulation import Simulation

sim = Simulation()
sun = make_body(500, 400, 0, 0, 3.33e8, 30, (255, 210, 50), "Sol", "plasma")
earth = make_body(650, 400, 0, 1155, 1e3, 8, (50, 120, 220), "Terra", "rock")
sim.add_body(sun); sim.add_body(earth)

e0 = total_energy(sim)
run_steps(sim, 900)
e1 = total_energy(sim)

# Tolerância alta porque o motor ainda tem softening e escala visual.
assert_close_ratio(e0, e1, 0.18, "energia orbital total")
print("OK: energy conservation orbit")
