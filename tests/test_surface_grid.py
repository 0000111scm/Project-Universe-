from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pygame
from body import Body
from physics_core.surface_grid import ensure_surface_grid, deposit_impact_energy, diffuse_surface_heat, crater_depth

b = Body(0, 0, 0, 0, 1000, 12, (50, 120, 220), "Planeta")
b.material = "rock"
b.temperature = 300

grid = ensure_surface_grid(b, cells=64)
assert grid.cells == 64
before = grid.temperature.max()

deposit_impact_energy(b, pygame.Vector2(12, 0), 1e8, affected_mass=10, spread=3)
after = grid.temperature.max()

assert after > before
assert crater_depth(b) > 0

diffuse_surface_heat(b, 0.1)
assert b.temperature >= 3.0
assert hasattr(b, "phase")

print("OK: surface grid")
