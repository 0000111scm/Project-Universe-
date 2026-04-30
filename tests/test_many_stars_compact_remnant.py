from pathlib import Path
import sys, math
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from simulation import Simulation
from body import Body

sim = Simulation()
cx, cy = 500, 400

for i in range(20):
    ang = math.tau * i / 20
    b = Body(
        cx + math.cos(ang) * 70,
        cy + math.sin(ang) * 70,
        -math.cos(ang) * 30,
        -math.sin(ang) * 30,
        3.33e8,
        22,
        (255, 200, 80),
        f"Estrela {i}",
    )
    b.material = "plasma"
    sim.add_body(b)

for _ in range(220):
    sim.step(0.016)

names = [getattr(b, "name", "") for b in sim.bodies]
materials = [getattr(b, "material", "") for b in sim.bodies]

assert any(("Buraco Negro" in n or "Nêutrons" in n or "Remanescente" in n or m == "blackhole") for n, m in zip(names, materials)), (
    f"20 estrelas não geraram remanescente compacto. nomes={names}, materiais={materials}"
)

print("OK: many stars compact remnant")
