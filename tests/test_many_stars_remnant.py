import math
from _test_utils import make_body, assert_simulation_sane
from simulation import Simulation

sim = Simulation()
cx, cy = 500, 400

for i in range(20):
    ang = math.tau * i / 20
    x = cx + math.cos(ang) * 70
    y = cy + math.sin(ang) * 70
    vx = -math.cos(ang) * 35
    vy = -math.sin(ang) * 35
    sim.add_body(make_body(x, y, vx, vy, 3.33e8, 24, (255, 200, 80), f"Estrela {i}", "plasma"))

for _ in range(420):
    sim.step(0.016)
    assert_simulation_sane(sim)

names = [getattr(b, "name", "") for b in sim.bodies]
materials = [getattr(b, "material", "") for b in sim.bodies]

assert any(("Buraco Negro" in n or "Nêutrons" in n or "Remanescente" in n or m == "blackhole") for n, m in zip(names, materials)), (
    f"20 estrelas não geraram remanescente compacto. nomes={names[:8]}, materiais={materials[:8]}"
)

print("OK: many stars remnant")
