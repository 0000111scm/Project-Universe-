# physics_core/common_envelope.py
"""Common Envelope Process.

PATCH 78 — Stellar Collision Replacement FINAL

Este módulo existe para matar o "estrela bateu -> plim fundiu".

Feynman:
- duas estrelas encostam;
- forma-se uma nuvem/envelope de plasma envolvendo os dois núcleos;
- o envelope rouba energia orbital;
- ejeta massa aos poucos;
- só quando energia/instabilidade passam do limite ocorre colapso/fusão.

A entidade CommonEnvelope é persistente e observável.
"""

from dataclasses import dataclass
import math

SOLAR_MASS_INTERNAL = 3.33e8


def clamp(v, a, b):
    return max(a, min(b, v))


def solar_mass(m):
    return max(float(m), 0.0) / SOLAR_MASS_INTERNAL


@dataclass
class CommonEnvelopeProcess:
    key_a: int
    key_b: int
    age: float = 0.0
    total_energy: float = 0.0
    lost_mass: float = 0.0
    instability: float = 0.0
    orbital_decay: float = 0.0
    phase: str = "contact"
    next_eject_time: float = 0.0
    collapse_allowed: bool = False
    visual_body_id: int = 0

    @classmethod
    def from_dict(cls, d, key_a=0, key_b=0):
        return cls(
            key_a=int(d.get("key_a", key_a)),
            key_b=int(d.get("key_b", key_b)),
            age=float(d.get("age", d.get("time", 0.0))),
            total_energy=float(d.get("total_energy", d.get("energy", 0.0))),
            lost_mass=float(d.get("lost_mass", d.get("mass_lost", 0.0))),
            instability=float(d.get("instability", 0.0)),
            orbital_decay=float(d.get("orbital_decay", 0.0)),
            phase=str(d.get("phase", "contact")),
            next_eject_time=float(d.get("next_eject_time", 0.0)),
            collapse_allowed=bool(d.get("collapse_allowed", False)),
            visual_body_id=int(d.get("visual_body_id", 0)),
        )

    def as_dict(self):
        return {
            "key_a": self.key_a,
            "key_b": self.key_b,
            "age": self.age,
            "total_energy": self.total_energy,
            "lost_mass": self.lost_mass,
            "instability": self.instability,
            "orbital_decay": self.orbital_decay,
            "phase": self.phase,
            "next_eject_time": self.next_eject_time,
            "collapse_allowed": self.collapse_allowed,
            "visual_body_id": self.visual_body_id,
        }


def update_common_envelope(proc, m1, m2, r1, r2, rel_speed, overlap_ratio, impact_energy, dt):
    total_mass = max(float(m1 + m2), 1e-9)
    solar = solar_mass(total_mass)

    proc.age += float(dt)
    proc.total_energy += max(float(impact_energy), 0.0)

    binding = max(0.6 * 0.6006 * total_mass * total_mass / max(r1 + r2, 1.0), 1e-9)
    mu = (m1 * m2) / total_mass
    orbital_energy = 0.5 * mu * rel_speed * rel_speed
    energy_ratio = orbital_energy / binding

    proc.instability = max(
        proc.instability,
        energy_ratio * 1.55
        + overlap_ratio * 0.65
        + clamp(solar / 16.0, 0.0, 5.0)
        + proc.age * 0.18
        + proc.lost_mass / total_mass * 0.75,
    )

    if proc.age < 0.65:
        proc.phase = "contact"
    elif proc.instability < 1.6:
        proc.phase = "common_envelope"
    elif proc.instability < 3.2:
        proc.phase = "violent_envelope"
    else:
        proc.phase = "collapse_candidate"

    # Sistemas pequenos: envelope persiste mais.
    # Sistemas muito massivos/muitas estrelas: precisa evoluir para remanescente compacto.
    min_age = 5.0 if solar < 4.0 else (2.4 if solar < 12.0 else 0.95)
    instability_gate = 2.2 if solar < 4.0 else (1.55 if solar < 12.0 else 0.95)

    proc.collapse_allowed = (
        proc.age >= min_age
        and proc.instability >= instability_gate
    ) or (
        solar >= 8.0 and proc.age >= 0.75 and proc.instability >= 1.35
    ) or (
        solar >= 20.0 and proc.age >= 0.45
    )

    damping = clamp(0.035 + proc.instability * 0.018 + overlap_ratio * 0.035, 0.035, 0.33)
    pull = clamp(0.006 + overlap_ratio * 0.014 + proc.age * 0.003, 0.004, 0.065)

    # Ejeção contínua de massa do envelope.
    loss_fraction = 0.00045 + energy_ratio * 0.0013 + overlap_ratio * 0.0007
    if proc.phase == "violent_envelope":
        loss_fraction *= 3.0
    elif proc.phase == "collapse_candidate":
        loss_fraction *= 5.5
    loss_fraction = clamp(loss_fraction, 0.00025, 0.020)

    eject_interval = 0.40
    if proc.phase == "violent_envelope":
        eject_interval = 0.24
    elif proc.phase == "collapse_candidate":
        eject_interval = 0.16

    should_eject = proc.age >= proc.next_eject_time
    if should_eject:
        proc.next_eject_time = proc.age + eject_interval

    return {
        "solar": solar,
        "damping": damping,
        "pull": pull,
        "loss_fraction": loss_fraction,
        "should_eject": should_eject,
        "collapse_allowed": proc.collapse_allowed,
        "phase": proc.phase,
        "instability": proc.instability,
        "envelope_radius_factor": clamp(1.25 + proc.instability * 0.18, 1.25, 2.8),
    }


def classify_final_remnant(total_mass, proc):
    solar = solar_mass(total_mass)
    if solar >= 25.0 or proc.instability >= 4.7:
        return "Buraco Negro", "blackhole", 0.14
    if solar >= 8.0 or proc.instability >= 3.25:
        return "Estrela de Nêutrons", "plasma", 0.17
    if solar >= 3.0 or proc.instability >= 1.85:
        return "Remanescente Estelar", "plasma", 0.52
    return "Estrela Fundida", "plasma", 0.92


def final_mass_and_ejecta(total_mass, proc):
    frac = clamp(0.04 + proc.instability * 0.050 + proc.lost_mass / max(total_mass, 1e-9) * 0.25, 0.04, 0.68)
    ejecta = total_mass * frac
    return max(total_mass - ejecta, 1e-9), ejecta
