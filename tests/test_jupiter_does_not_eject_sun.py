from _test_utils import make_body, run_steps
from simulation import Simulation

sim = Simulation()
sun = make_body(500, 400, 0, 0, 3.33e8, 30, (255, 210, 50), "Sol", "plasma")
jupiter = make_body(920, 400, 0, 690, 3e5, 16, (200, 160, 110), "Júpiter", "gas")
sim.add_body(sun); sim.add_body(jupiter)

sun_start = sun.pos.copy()
run_steps(sim, 360)
sun_shift = (sun.pos - sun_start).length()

assert sun_shift < 80, f"Sol deslocou demais por Júpiter: {sun_shift:.2f}px"
print("OK: jupiter does not eject sun")
