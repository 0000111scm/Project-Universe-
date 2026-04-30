# physics_core/surface_grid.py
"""Surface Grid — superfície física por células.

Feynman:
Antes:
    planeta.temperature = 2000
Isso quer dizer que o planeta inteiro aqueceu magicamente.

Agora:
    a energia entra numa célula da superfície;
    essa célula esquenta;
    o calor espalha para células vizinhas;
    dano e cratera ficam onde o impacto ocorreu.

Ainda é grid 1D angular em volta do corpo 2D.
Depois isso vira grid esférico 3D.
"""

from dataclasses import dataclass
import math

try:
    import numpy as np
except Exception:
    np = None

from physics_core.thermodynamics import classify_phase, phase_name, temperature_delta_from_energy


@dataclass
class SurfaceGrid:
    cells: int
    temperature: object
    damage: object
    elevation: object
    melt_fraction: object
    phase_id: object
    material_id: int = 1


MATERIAL_ID = {
    "rock": 1,
    "metal": 2,
    "ice": 3,
    "gas": 4,
    "plasma": 5,
    "blackhole": 6,
}

ID_MATERIAL = {v: k for k, v in MATERIAL_ID.items()}


def require_numpy():
    if np is None:
        raise RuntimeError("NumPy é necessário para SurfaceGrid.")


def create_surface_grid(cells=96, base_temperature=300.0, material="rock"):
    require_numpy()
    cells = max(8, int(cells))
    return SurfaceGrid(
        cells=cells,
        temperature=np.full(cells, float(base_temperature), dtype=np.float64),
        damage=np.zeros(cells, dtype=np.float64),
        elevation=np.zeros(cells, dtype=np.float64),
        melt_fraction=np.zeros(cells, dtype=np.float64),
        phase_id=np.zeros(cells, dtype=np.int32),
        material_id=MATERIAL_ID.get(str(material), 1),
    )


def ensure_surface_grid(body, cells=96):
    grid = getattr(body, "surface_grid", None)
    if grid is not None and hasattr(grid, "temperature"):
        return grid

    grid = create_surface_grid(
        cells=cells,
        base_temperature=float(getattr(body, "temperature", 300.0)),
        material=getattr(body, "material", "rock"),
    )
    body.surface_grid = grid
    return grid


def angle_to_cell(grid, angle):
    tau = math.tau
    a = float(angle) % tau
    return int((a / tau) * grid.cells) % grid.cells


def impact_angle_on_body(body, impact_point):
    dx = float(impact_point.x - body.pos.x)
    dy = float(impact_point.y - body.pos.y)
    return math.atan2(dy, dx)


def deposit_impact_energy(body, impact_point, energy, affected_mass, spread=3):
    """Deposita energia na superfície no ponto de impacto."""
    grid = ensure_surface_grid(body)
    material = ID_MATERIAL.get(grid.material_id, getattr(body, "material", "rock"))

    angle = impact_angle_on_body(body, impact_point)
    center = angle_to_cell(grid, angle)

    spread = max(1, int(spread))
    affected_mass = max(float(affected_mass), 1.0e-9)
    total_weight = 0.0
    weights = []

    for off in range(-spread, spread + 1):
        w = math.exp(-(off * off) / max(spread * spread * 0.55, 1.0))
        weights.append((off, w))
        total_weight += w

    max_delta = 0.0
    for off, w in weights:
        idx = (center + off) % grid.cells
        local_energy = float(energy) * (w / max(total_weight, 1.0e-9))
        local_mass = affected_mass * (w / max(total_weight, 1.0e-9))

        dt = temperature_delta_from_energy(material, local_energy, max(local_mass, 1.0e-9))
        dt = max(0.0, min(dt, 50000.0))
        grid.temperature[idx] += dt
        max_delta = max(max_delta, dt)

        # Dano e cratera: energia local remove elevação.
        damage_delta = min(1.0, dt / 18000.0)
        grid.damage[idx] = min(1.0, grid.damage[idx] + damage_delta)
        grid.elevation[idx] -= damage_delta * max(float(getattr(body, "radius", 1.0)) * 0.10, 0.5)

    update_surface_phases(body)
    body.temperature = max(float(getattr(body, "temperature", 300.0)), float(grid.temperature.max()))
    body.surface_damage = max(float(getattr(body, "surface_damage", 0.0)), float(grid.damage.max()))
    return max_delta


def update_surface_phases(body):
    grid = ensure_surface_grid(body)
    material = ID_MATERIAL.get(grid.material_id, getattr(body, "material", "rock"))

    pressure = float(getattr(body, "atmosphere", 0.0)) * 1.0e5
    gravity = float(getattr(body, "mass", 0.0)) / max(float(getattr(body, "radius", 1.0)) ** 2, 1.0)

    for i in range(grid.cells):
        ph = classify_phase(material, grid.temperature[i], pressure=pressure, gravity=gravity)
        grid.phase_id[i] = ph
        if ph >= 1:
            grid.melt_fraction[i] = min(1.0, grid.melt_fraction[i] + 0.015 * ph)

    # fase global = fase máxima local
    body.phase = phase_name(int(grid.phase_id.max()))


def diffuse_surface_heat(body, dt, conductivity=0.18):
    """Difusão térmica simples entre células vizinhas."""
    grid = ensure_surface_grid(body)
    dt = max(float(dt), 0.0)
    if dt <= 0:
        return

    t = grid.temperature
    left = np.roll(t, 1)
    right = np.roll(t, -1)
    lap = left + right - 2.0 * t

    grid.temperature[:] = np.maximum(3.0, t + lap * float(conductivity) * min(dt, 1.0))

    # recuperação lenta de dano superficial, não da cratera/elevation
    grid.damage[:] = np.maximum(0.0, grid.damage - dt * 0.0004)
    update_surface_phases(body)

    # temperatura representativa: média + peso do hotspot
    mean_t = float(grid.temperature.mean())
    max_t = float(grid.temperature.max())
    body.temperature = max(3.0, mean_t * 0.75 + max_t * 0.25)


def crater_depth(body):
    grid = ensure_surface_grid(body)
    return abs(float(grid.elevation.min()))


def max_surface_temperature(body):
    grid = ensure_surface_grid(body)
    return float(grid.temperature.max())
