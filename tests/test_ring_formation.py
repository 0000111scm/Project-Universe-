from _test_utils import make_body, run_steps
from simulation import Simulation

sim = Simulation()
planet = make_body(500, 400, 0, 0, 3e5, 18, (200, 160, 110), "Gigante", "gas")
impactor = make_body(535, 390, -45, 80, 5e2, 6, (150, 140, 130), "Impactador", "rock")
sim.add_body(planet); sim.add_body(impactor)

run_steps(sim, 240)

# Não exige sempre anel, mas se tiver anel não pode ser em estrela/plasma.
for b in sim.bodies:
    if getattr(b, "has_rings", False):
        assert getattr(b, "material", "") not in ("plasma", "blackhole"), "anel em objeto inválido"

print("OK: ring formation sanity")
