from _test_utils import make_body, run_steps
from simulation import Simulation

sim = Simulation()
sun = make_body(500, 400, 0, 0, 3.33e8, 30, (255, 210, 50), "Sol", "plasma")
earth = make_body(650, 400, 0, 1155, 1e3, 8, (50, 120, 220), "Terra", "rock")
sim.add_body(sun); sim.add_body(earth)

initial = (earth.pos - sun.pos).length()
run_steps(sim, 1800)
final = (earth.pos - sun.pos).length()

assert 20 < final < initial * 10.0, f"órbita longa instável: inicial={initial}, final={final}"
print("OK: long orbit")
