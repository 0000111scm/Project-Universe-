# physics_core/sph_coupling.py
"""Acoplamento SPH -> corpos rígidos temporários.

Feynman:
- se partículas perto do impacto ficam muito quentes, o corpo aquece;
- se partículas saem rápido demais, isso vira massa ejetada;
- se a pressão fica alta, vira dano estrutural;
- assim a colisão deixa de ser só regra e começa a ser consequência de material.
"""

try:
    import numpy as np
except Exception:
    np = None


def summarize_owner_particles(pset, owner_id):
    if np is None or pset.count == 0:
        return None

    n = pset.count
    mask = (pset.active[:n]) & (pset.owner[:n] == int(owner_id))
    idx = np.nonzero(mask)[0]
    if idx.size == 0:
        return None

    mass = pset.mass[idx]
    total_mass = float(mass.sum())
    if total_mass <= 0:
        return None

    vel = pset.vel[idx]
    temp = pset.temperature[idx]
    density = pset.density[idx]
    pressure = pset.pressure[idx]

    mean_vel = (vel * mass[:, None]).sum(axis=0) / total_mass
    kinetic = float((0.5 * mass * (vel * vel).sum(axis=1)).sum())

    return {
        "count": int(idx.size),
        "mass": total_mass,
        "mean_vx": float(mean_vel[0]),
        "mean_vy": float(mean_vel[1]),
        "mean_temp": float((temp * mass).sum() / total_mass),
        "max_temp": float(temp.max()),
        "mean_density": float(density.mean()),
        "max_pressure": float(pressure.max()),
        "kinetic": kinetic,
    }


def estimate_ejecta_from_particles(pset, body, escape_speed):
    """Retorna massa de partículas do corpo com velocidade acima da escape proxy."""
    if np is None or pset.count == 0:
        return 0.0

    n = pset.count
    owner_id = int(id(body))
    mask = (pset.active[:n]) & (pset.owner[:n] == owner_id)
    idx = np.nonzero(mask)[0]
    if idx.size == 0:
        return 0.0

    rel_v = pset.vel[idx] - np.array([float(body.vel.x), float(body.vel.y)], dtype=np.float64)
    speed = np.sqrt((rel_v * rel_v).sum(axis=1))

    escaping = idx[speed > float(escape_speed)]
    if escaping.size == 0:
        return 0.0

    ejecta_mass = float(pset.mass[escaping].sum())
    pset.active[escaping] = False
    return ejecta_mass


def apply_sph_feedback_to_body(pset, body, heat_scale=0.03, pressure_scale=0.0008):
    """Aplica feedback das partículas no Body.

    Retorna dicionário com métricas usadas pela Simulation.
    """
    summary = summarize_owner_particles(pset, id(body))
    if not summary:
        return {
            "heat_delta": 0.0,
            "damage_delta": 0.0,
            "particle_mass": 0.0,
            "particle_count": 0,
        }

    body_temp = float(getattr(body, "temperature", 300.0))
    particle_temp = summary["mean_temp"]

    heat_delta = max(0.0, particle_temp - body_temp) * float(heat_scale)
    pressure_damage = max(0.0, summary["max_pressure"]) * float(pressure_scale)
    pressure_damage = min(0.20, pressure_damage)

    return {
        "heat_delta": heat_delta,
        "damage_delta": pressure_damage,
        "particle_mass": summary["mass"],
        "particle_count": summary["count"],
        "max_pressure": summary["max_pressure"],
        "max_temp": summary["max_temp"],
    }
