from _test_utils import make_body, assert_simulation_sane
from simulation import Simulation

sim = Simulation()
target = make_body(500, 400, 0, 0, 1e3, 12, (50, 120, 220), "Alvo", "rock")
impactor = make_body(470, 400, 180, 0, 80, 5, (150, 140, 130), "Asteroide", "rock")
sim.add_body(target); sim.add_body(impactor)

for _ in range(180):
    sim.step(0.016)
    assert_simulation_sane(sim)

frags = [b for b in sim.bodies if getattr(b, "is_fragment", False)]
for f in frags:
    assert f.vel.length() < 2500, f"fragmento rápido demais: {f.vel.length():.2f}"

print("OK: fragment speed limits")
