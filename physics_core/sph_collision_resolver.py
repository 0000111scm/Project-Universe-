# physics_core/sph_collision_resolver.py
"""SPH Planetary Collision Resolver.

Objetivo:
parar de decidir colisão planeta-planeta apenas por regra.

Feynman:
1. dois planetas batem;
2. amostramos matéria deles em partículas;
3. rodamos alguns passos de pressão/viscosidade/calor;
4. partículas com energia suficiente escapam;
5. partículas ligadas reacumulam;
6. o corpo resultante recebe massa, velocidade, temperatura e dano vindos das partículas.

Ainda é híbrido Body + SPH 2D, mas a decisão começa a sair da matéria simulada.
"""

from dataclasses import dataclass

try:
    import numpy as np
except Exception:
    np = None

from physics_core.sph import SPHParticleSet, sample_body_particles, step_sph
from physics_core.thermodynamics import classify_phase, phase_name, temperature_delta_from_energy, impact_heat_partition


@dataclass
class SPHCollisionOutcome:
    bound_mass_a: float
    bound_mass_b: float
    ejecta_mass: float
    mean_temp_a: float
    mean_temp_b: float
    max_phase: int
    damage_a: float
    damage_b: float
    reaccrete: bool
    catastrophic: bool
    merged_core_fraction: float


def _escape_speed_proxy(G, mass, radius):
    return (max(2.0 * G * float(mass) / max(float(radius), 1.0), 0.0)) ** 0.5


def _weighted_mean(values, weights, fallback=0.0):
    s = float(weights.sum())
    if s <= 0:
        return fallback
    return float((values * weights).sum() / s)


def resolve_planetary_sph_collision(a, b, impact, G=0.6006, particle_count=96, micro_steps=8, dt=0.012):
    """Resolve colisão por uma micro-simulação SPH local.

    Retorna outcome com massa ligada/ejetada e dano.
    """
    if np is None:
        raise RuntimeError("NumPy é necessário para SPH collision resolver.")

    total_mass = max(float(a.mass + b.mass), 1e-9)
    count_a = max(24, int(particle_count * (a.mass / total_mass)))
    count_b = max(24, int(particle_count * (b.mass / total_mass)))

    pa, va, ma, ta, mata = sample_body_particles(a, count=count_a)
    pb, vb, mb, tb, matb = sample_body_particles(b, count=count_b)

    normal_fraction = impact.normal_velocity / max(impact.relative_velocity, 1e-9)

    heat_a = impact_heat_partition(
        max(getattr(impact, "impact_energy", 0.0), 0.0) * (a.mass / total_mass),
        normal_fraction=normal_fraction,
        material=getattr(a, "material", "rock"),
    )
    heat_b = impact_heat_partition(
        max(getattr(impact, "impact_energy", 0.0), 0.0) * (b.mass / total_mass),
        normal_fraction=normal_fraction,
        material=getattr(b, "material", "rock"),
    )

    ta += min(35000.0, temperature_delta_from_energy(getattr(a, "material", "rock"), heat_a, max(a.mass * 0.16, 1e-9)))
    tb += min(35000.0, temperature_delta_from_energy(getattr(b, "material", "rock"), heat_b, max(b.mass * 0.16, 1e-9)))

    ps = SPHParticleSet(capacity=count_a + count_b)
    ps.add_particles(pa, va, ma, ta, mata, owner=1)
    ps.add_particles(pb, vb, mb, tb, matb, owner=2)

    # Micro-resolução local: poucas iterações para pressão/viscosidade agirem.
    for _ in range(max(1, int(micro_steps))):
        step_sph(ps, dt, h=max(8.0, min(a.radius, b.radius) * 0.9))

    n = ps.count
    pos = ps.pos[:n]
    vel = ps.vel[:n]
    mass = ps.mass[:n]
    temp = ps.temperature[:n]
    phase = ps.phase_id[:n]
    owner = ps.owner[:n]

    bary_pos = (np.array([a.pos.x, a.pos.y]) * a.mass + np.array([b.pos.x, b.pos.y]) * b.mass) / total_mass
    bary_vel = (np.array([a.vel.x, a.vel.y]) * a.mass + np.array([b.vel.x, b.vel.y]) * b.mass) / total_mass

    rel_pos = pos - bary_pos[None, :]
    rel_vel = vel - bary_vel[None, :]

    dist = np.sqrt((rel_pos * rel_pos).sum(axis=1))
    speed = np.sqrt((rel_vel * rel_vel).sum(axis=1))

    equivalent_radius = max((float(a.radius) ** 3 + float(b.radius) ** 3) ** (1.0 / 3.0), 1.0)
    escape = _escape_speed_proxy(G, total_mass, equivalent_radius)

    # Partícula ligada: não escapou e não está longe demais.
    bound = (speed < escape * 1.35) & (dist < equivalent_radius * 3.2)
    escaping = ~bound

    bound_a = bound & (owner == 1)
    bound_b = bound & (owner == 2)

    bound_mass_a = float(mass[bound_a].sum())
    bound_mass_b = float(mass[bound_b].sum())
    ejecta_mass = float(mass[escaping].sum())

    mean_temp_a = _weighted_mean(temp[owner == 1], mass[owner == 1], fallback=float(getattr(a, "temperature", 300.0)))
    mean_temp_b = _weighted_mean(temp[owner == 2], mass[owner == 2], fallback=float(getattr(b, "temperature", 300.0)))

    max_phase = int(phase.max()) if len(phase) else 0

    pressure_max = float(ps.pressure[:n].max()) if n else 0.0
    hot_fraction = float(mass[temp > 1800.0].sum() / max(mass.sum(), 1e-9))

    damage_base = min(1.0, pressure_max * 0.0015 + hot_fraction * 0.45)
    damage_a = min(1.0, damage_base + (1.0 - bound_mass_a / max(float(a.mass), 1e-9)) * 0.55)
    damage_b = min(1.0, damage_base + (1.0 - bound_mass_b / max(float(b.mass), 1e-9)) * 0.55)

    bound_total = bound_mass_a + bound_mass_b
    # Reacumulação só pode acontecer em impacto realmente suave.
    # Se a velocidade/temperatura gerou muita ejeção ou fase vapor/plasma, não é "plim fundiu".
    rel_speed_global = float(getattr(impact, "relative_velocity", 0.0))
    gentle = rel_speed_global < 55.0 and max_phase <= 1

    reaccrete = gentle and bound_total > total_mass * 0.72 and ejecta_mass < total_mass * 0.18
    catastrophic = ejecta_mass > total_mass * 0.45 or max_phase >= 3

    merged_core_fraction = min(1.0, bound_total / total_mass)

    return SPHCollisionOutcome(
        bound_mass_a=bound_mass_a,
        bound_mass_b=bound_mass_b,
        ejecta_mass=ejecta_mass,
        mean_temp_a=mean_temp_a,
        mean_temp_b=mean_temp_b,
        max_phase=max_phase,
        damage_a=damage_a,
        damage_b=damage_b,
        reaccrete=reaccrete,
        catastrophic=catastrophic,
        merged_core_fraction=merged_core_fraction,
    )
