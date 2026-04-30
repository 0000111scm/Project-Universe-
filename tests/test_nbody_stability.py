from _test_utils import make_body, total_mass, total_momentum, assert_close_ratio, run_steps
from simulation import Simulation

sim = Simulation()
sun = make_body(500, 400, 0, 0, 3.33e8, 30, (255, 210, 50), "Sol", "plasma")
earth = make_body(650, 400, 0, 1155, 1e3, 8, (50, 120, 220), "Terra", "rock")
mars = make_body(725, 400, 0, 943, 1e2, 6, (200, 80, 50), "Marte", "rock")
sim.add_body(sun); sim.add_body(earth); sim.add_body(mars)

m0 = total_mass(sim)
p0 = total_momentum(sim)
run_steps(sim, 360)
p1 = total_momentum(sim)

assert_close_ratio(m0, total_mass(sim), 0.001, "massa total N-body")
assert abs(p1[0] - p0[0]) < max(1e6, abs(p0[1]) * 0.02)
assert abs(p1[1] - p0[1]) < max(1e6, abs(p0[1]) * 0.05)

print("OK: nbody stability")
