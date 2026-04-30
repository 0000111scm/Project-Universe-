from _test_utils import make_body, assert_simulation_sane
from simulation import Simulation

sim = Simulation()
s1 = make_body(480, 400, 20, 0, 3.33e8, 30, (255, 210, 50), "Sol A", "plasma")
s2 = make_body(525, 400, -20, 0, 3.33e8, 30, (255, 180, 80), "Sol B", "plasma")
sim.add_body(s1); sim.add_body(s2)

for _ in range(240):
    sim.step(0.016)
    assert_simulation_sane(sim)

bad = [b for b in sim.bodies if getattr(b, "is_fragment", False) and getattr(b, "material", "") not in ("plasma", "blackhole")]
assert not bad, f"estrela gerou fragmento sólido: {[getattr(b, 'material', None) for b in bad[:5]]}"

print("OK: stellar no solid fragments")
