import math
from _test_utils import make_body, timed_steps
from simulation import Simulation

sim = Simulation()
cx, cy = 500, 400
sim.add_body(make_body(cx, cy, 0, 0, 3.33e8, 30, (255, 210, 50), "Sol", "plasma"))

for i in range(80):
    ang = math.tau * i / 80
    dist = 160 + (i % 20) * 8
    x = cx + math.cos(ang) * dist
    y = cy + math.sin(ang) * dist
    v = 850
    vx = -math.sin(ang) * v
    vy = math.cos(ang) * v
    sim.add_body(make_body(x, y, vx, vy, 10 + (i % 5), 2, (150, 150, 140), f"Ast {i}", "rock"))

elapsed = timed_steps(sim, 240)

# Limite solto para máquina comum; serve para detectar travamento absurdo.
assert elapsed < 12.0, f"benchmark lento demais: {elapsed:.2f}s para 240 frames/81 corpos"

print(f"OK: performance benchmark {elapsed:.2f}s")
