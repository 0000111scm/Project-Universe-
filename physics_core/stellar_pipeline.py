# physics_core/stellar_pipeline.py
"""Persistent Stellar Collision Pipeline.

Este módulo substitui o comportamento "estrela tocou -> fundiu".

Feynman:
- estrelas são plasma autogravitante;
- ao colidir, elas não viram uma bola instantaneamente;
- primeiro formam envelope comum;
- energia orbital é dissipada;
- massa escapa como plasma;
- a instabilidade cresce;
- só depois há fusão, supernova simplificada ou colapso.

O objeto visível Body ainda existe, mas a decisão física vira processo persistente.
"""

from dataclasses import dataclass
import math

SOLAR_MASS_INTERNAL = 3.33e8


def clamp(v, a, b):
    return max(a, min(b, v))


def solar_mass(m):
    return max(float(m), 0.0) / SOLAR_MASS_INTERNAL


@dataclass
class StellarProcess:
    time: float = 0.0
    energy: float = 0.0
    mass_lost: float = 0.0
    instability: float = 0.0
    phase: str = "contact"
    merge_count: int = 1
    last_eject_time: float = 0.0
    collapse_ready: bool = False

    @classmethod
    def from_dict(cls, d):
        return cls(
            time=float(d.get("time", 0.0)),
            energy=float(d.get("energy", 0.0)),
            mass_lost=float(d.get("mass_lost", 0.0)),
            instability=float(d.get("instability", 0.0)),
            phase=str(d.get("phase", "contact")),
            merge_count=int(d.get("merge_count", 1)),
            last_eject_time=float(d.get("last_eject_time", 0.0)),
            collapse_ready=bool(d.get("collapse_ready", False)),
        )

    def as_dict(self):
        return {
            "time": self.time,
            "energy": self.energy,
            "mass_lost": self.mass_lost,
            "instability": self.instability,
            "phase": self.phase,
            "merge_count": self.merge_count,
            "last_eject_time": self.last_eject_time,
            "collapse_ready": self.collapse_ready,
        }


def evaluate_process(m1, m2, r1, r2, rel_speed, overlap_ratio, process, dt):
    total = max(m1 + m2, 1e-9)
    solar = solar_mass(total)

    process.time += float(dt)

    # Energia orbital relativa normalizada por uma ligação gravitacional proxy.
    binding_proxy = max(0.6 * 0.6006 * total * total / max(r1 + r2, 1.0), 1e-9)
    orbital_proxy = 0.5 * (m1 * m2 / total) * rel_speed * rel_speed
    energy_ratio = orbital_proxy / binding_proxy

    process.instability = max(
        process.instability,
        energy_ratio * 1.4
        + overlap_ratio * 0.55
        + clamp(solar / 18.0, 0.0, 4.0)
        + process.time * 0.16
        + max(0, process.merge_count - 1) * 0.25,
    )

    if process.time < 0.55:
        process.phase = "contact"
    elif process.instability < 1.4:
        process.phase = "common_envelope"
    elif process.instability < 3.0:
        process.phase = "violent_envelope"
    else:
        process.phase = "collapse_candidate"

    # O segredo: não merge imediato. A fase deve persistir tempo suficiente.
    min_time = 5.0 if solar < 4 else (3.2 if solar < 12 else 1.65)
    core_overlap = overlap_ratio > (1.15 if solar < 8 else 0.65)
    slow_core = rel_speed < max(12.0, 30.0 / max(solar, 1.0))

    process.collapse_ready = (
        process.time >= min_time
        or (process.time > 2.4 and core_overlap and slow_core)
        or (process.instability > 4.8 and process.time > 1.8)
        or (solar > 25 and process.time > 0.9 and overlap_ratio > 0.45)
    )

    damping = clamp(0.045 + overlap_ratio * 0.045 + process.instability * 0.012, 0.04, 0.34)
    pull = clamp(0.010 + overlap_ratio * 0.018 + process.time * 0.004, 0.008, 0.085)

    # perda contínua; em fase violenta sobe bastante
    loss_fraction = 0.00035 + energy_ratio * 0.0014 + overlap_ratio * 0.0008
    if process.phase == "violent_envelope":
        loss_fraction *= 3.0
    elif process.phase == "collapse_candidate":
        loss_fraction *= 5.0
    loss_fraction = clamp(loss_fraction, 0.0002, 0.018)

    eject_interval = 0.18 if process.phase in ("violent_envelope", "collapse_candidate") else 0.32
    should_eject = (process.time - process.last_eject_time) >= eject_interval

    return {
        "solar": solar,
        "damping": damping,
        "pull": pull,
        "loss_fraction": loss_fraction,
        "should_eject": should_eject,
        "eject_interval": eject_interval,
        "collapse_ready": process.collapse_ready,
        "phase": process.phase,
        "instability": process.instability,
    }


def remnant_from_process(final_mass, process):
    solar = solar_mass(final_mass)
    instability = process.instability

    if solar >= 25 or instability >= 4.4:
        return "Buraco Negro", "blackhole", 0.16
    if solar >= 8 or instability >= 3.0:
        return "Estrela de Nêutrons", "plasma", 0.18
    if solar >= 3 or instability >= 1.7:
        return "Remanescente Estelar", "plasma", 0.58
    return "Estrela Fundida", "plasma", 1.00


def final_mass_and_ejecta(raw_mass, process):
    # Não soma tudo magicamente: evento final expulsa massa.
    frac = clamp(0.035 + process.instability * 0.045 + process.mass_lost / max(raw_mass, 1e-9) * 0.22, 0.03, 0.62)
    ejecta = raw_mass * frac
    return max(raw_mass - ejecta, 1e-9), ejecta
