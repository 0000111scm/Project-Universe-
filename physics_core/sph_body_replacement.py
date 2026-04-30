# physics_core/sph_body_replacement.py
"""SPH Body Replacement Prototype.

Feynman:
Antes:
    planeta é um círculo rígido.
    colisão decide "merge / fragmenta" por regra.

Agora:
    em impacto forte, o planeta vira uma nuvem temporária de matéria.
    essa nuvem carrega massa, calor, fase e velocidade.
    depois ela decide se:
      - reacumula;
      - vira remanescente;
      - dispersa;
      - vaporiza parte do material.

É híbrido ainda, mas já troca "evento instantâneo" por "processo físico".
"""

from dataclasses import dataclass
import math

try:
    import numpy as np
except Exception:
    np = None

from physics_core.sph import SPHParticleSet, sample_body_particles, step_sph
from physics_core.thermodynamics import impact_heat_partition, temperature_delta_from_energy


@dataclass
class ReplacementOutcome:
    status: str
    bound_mass: float
    ejecta_mass: float
    vapor_mass: float
    mean_temperature: float
    max_temperature: float
    remnant_radius_factor: float
    remnant_phase_id: int
    particle_count: int


def _require_numpy():
    if np is None:
        raise RuntimeError("NumPy é necessário para SPH body replacement.")


def _weighted_mean(values, weights, fallback=0.0):
    total = float(weights.sum())
    if total <= 0:
        return fallback
    return float((values * weights).sum() / total)


def _escape_speed(g, mass, radius):
    return math.sqrt(max(2.0 * float(g) * float(mass) / max(float(radius), 1.0), 0.0))


def should_replace_body_with_sph(a, b, impact, severity):
    """Decide quando abandonar corpo rígido e usar nuvem SPH temporária."""
    rel = float(getattr(impact, "relative_velocity", 0.0))
    if severity >= 0.18:
        return True
    if rel >= 95.0 and min(a.mass, b.mass) >= 80.0:
        return True
    if getattr(impact, "impact_energy", 0.0) > (a.mass + b.mass) * 5000.0:
        return True
    return False


def run_replacement_cloud(a, b, impact, g=0.6006, severity=0.0, particle_count=192, steps=18, dt=0.010):
    """Roda uma micro-nuvem SPH dos dois corpos e retorna o resultado físico."""
    _require_numpy()

    total_mass = max(float(a.mass + b.mass), 1e-9)
    particle_count = int(max(64, min(particle_count, 260)))

    ca = max(24, int(particle_count * (a.mass / total_mass)))
    cb = max(24, particle_count - ca)

    pa, va, ma, ta, mata = sample_body_particles(a, count=ca)
    pb, vb, mb, tb, matb = sample_body_particles(b, count=cb)

    normal_fraction = impact.normal_velocity / max(impact.relative_velocity, 1e-9)
    heat_total = max(getattr(impact, "impact_energy", 0.0), 0.0)

    heat_a = impact_heat_partition(heat_total * (a.mass / total_mass), normal_fraction, getattr(a, "material", "rock"))
    heat_b = impact_heat_partition(heat_total * (b.mass / total_mass), normal_fraction, getattr(b, "material", "rock"))

    ta += min(60000.0, temperature_delta_from_energy(getattr(a, "material", "rock"), heat_a, max(a.mass * 0.10, 1e-9)))
    tb += min(60000.0, temperature_delta_from_energy(getattr(b, "material", "rock"), heat_b, max(b.mass * 0.10, 1e-9)))

    ps = SPHParticleSet(capacity=ca + cb)
    ps.add_particles(pa, va, ma, ta, mata, owner=1)
    ps.add_particles(pb, vb, mb, tb, matb, owner=2)

    h = max(7.0, min(float(a.radius), float(b.radius)) * 0.85)
    for _ in range(max(2, int(steps))):
        step_sph(ps, dt, h=h)

    n = ps.count
    pos = ps.pos[:n]
    vel = ps.vel[:n]
    mass = ps.mass[:n]
    temp = ps.temperature[:n]
    phase = ps.phase_id[:n]

    bary_pos = (np.array([a.pos.x, a.pos.y]) * a.mass + np.array([b.pos.x, b.pos.y]) * b.mass) / total_mass
    bary_vel = (np.array([a.vel.x, a.vel.y]) * a.mass + np.array([b.vel.x, b.vel.y]) * b.mass) / total_mass

    rel_pos = pos - bary_pos[None, :]
    rel_vel = vel - bary_vel[None, :]
    dist = np.sqrt((rel_pos * rel_pos).sum(axis=1))
    speed = np.sqrt((rel_vel * rel_vel).sum(axis=1))

    equivalent_radius = max((float(a.radius) ** 3 + float(b.radius) ** 3) ** (1.0 / 3.0), 1.0)
    vesc = _escape_speed(g, total_mass, equivalent_radius)

    vapor = phase >= 2
    plasma = phase >= 3
    bound = (speed < vesc * 1.20) & (dist < equivalent_radius * 3.0) & (~plasma)

    bound_mass = float(mass[bound].sum())
    vapor_mass = float(mass[vapor].sum())
    ejecta_mass = float(mass[~bound].sum())

    mean_temp = _weighted_mean(temp, mass, fallback=max(float(getattr(a, "temperature", 300.0)), float(getattr(b, "temperature", 300.0))))
    max_temp = float(temp.max()) if len(temp) else mean_temp
    max_phase = int(phase.max()) if len(phase) else 0

    bound_fraction = bound_mass / total_mass

    if bound_fraction >= 0.62 and max_phase < 3:
        status = "reaccumulated_remnant"
    elif bound_fraction >= 0.28:
        status = "partial_remnant"
    else:
        status = "dispersed_cloud"

    # Se muito material vapor/plasma, não pode fingir planeta normal.
    if vapor_mass > total_mass * 0.42:
        status = "vaporized_disruption"

    return ReplacementOutcome(
        status=status,
        bound_mass=max(bound_mass, 0.0),
        ejecta_mass=max(ejecta_mass, 0.0),
        vapor_mass=max(vapor_mass, 0.0),
        mean_temperature=mean_temp,
        max_temperature=max_temp,
        remnant_radius_factor=max(0.18, min(1.0, (bound_mass / total_mass) ** (1.0 / 3.0))) if total_mass > 0 else 0.25,
        remnant_phase_id=max_phase,
        particle_count=n,
    )
