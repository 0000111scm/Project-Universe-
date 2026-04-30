# physics/stellar_evolution.py
"""Modelo estelar simplificado para colisões reais.

Não é MESA, não é GR completo. É uma camada física macroscópica para deixar
colisões estrela-estrela menos "plim":

- calcula energia de ligação gravitacional;
- calcula energia orbital relativa;
- acompanha envelope comum por estado persistente;
- estima perda de massa por energia disponível;
- classifica remanescente por massa solar aproximada;
- emite feedback físico para SPH/plasma.
"""

from dataclasses import dataclass
import math

SOLAR_MASS_INTERNAL = 3.33e8
G_INTERNAL = 0.6006


def clamp(v, a, b):
    return max(a, min(b, v))


def solar_masses(mass):
    return max(float(mass), 0.0) / SOLAR_MASS_INTERNAL


def binding_energy_proxy(mass, radius):
    """Energia de ligação gravitacional aproximada na escala interna."""
    mass = max(float(mass), 1e-9)
    radius = max(float(radius), 1.0)
    return 0.6 * G_INTERNAL * mass * mass / radius


def reduced_mass(m1, m2):
    return (m1 * m2) / max(m1 + m2, 1e-9)


def orbital_energy_proxy(m1, m2, relative_speed):
    mu = reduced_mass(m1, m2)
    return 0.5 * mu * relative_speed * relative_speed


@dataclass
class StellarContactState:
    time: float = 0.0
    energy: float = 0.0
    mass_lost: float = 0.0
    orbital_energy_lost: float = 0.0
    common_envelope_mass: float = 0.0
    instability: float = 0.0
    phase: str = "contact"
    merge_count: int = 0

    @classmethod
    def from_dict(cls, d):
        return cls(
            time=float(d.get("time", 0.0)),
            energy=float(d.get("energy", 0.0)),
            mass_lost=float(d.get("mass_lost", 0.0)),
            orbital_energy_lost=float(d.get("orbital_energy_lost", 0.0)),
            common_envelope_mass=float(d.get("common_envelope_mass", 0.0)),
            instability=float(d.get("instability", 0.0)),
            phase=str(d.get("phase", "contact")),
            merge_count=int(d.get("merge_count", 0)),
        )

    def as_dict(self):
        return {
            "time": self.time,
            "energy": self.energy,
            "mass_lost": self.mass_lost,
            "orbital_energy_lost": self.orbital_energy_lost,
            "common_envelope_mass": self.common_envelope_mass,
            "instability": self.instability,
            "phase": self.phase,
            "merge_count": self.merge_count,
        }


@dataclass
class StellarCollisionStep:
    phase: str
    damping: float
    pull: float
    mass_loss_fraction: float
    envelope_mass_fraction: float
    merge_ready: bool
    explosion_strength: float
    remnant_kind: str
    remnant_material: str
    remnant_radius_factor: float
    compactness: float
    instability: float


def classify_remnant(total_mass, instability=0.0):
    solar = solar_masses(total_mass)

    # Limites simplificados. No futuro entram metalicidade, rotação, massa expulsa.
    if solar >= 25.0 or instability >= 4.2:
        return "Buraco Negro", "blackhole", 0.16
    if solar >= 8.0 or instability >= 2.8:
        return "Estrela de Nêutrons", "plasma", 0.18
    if solar >= 3.0 or instability >= 1.6:
        return "Remanescente Estelar", "plasma", 0.55
    return "Estrela Fundida", "plasma", 1.00


def evaluate_stellar_contact(
    m1,
    m2,
    r1,
    r2,
    relative_speed,
    overlap_ratio,
    state,
    merge_count=1,
):
    """Retorna parâmetros físicos para um passo de envelope comum."""
    st = StellarContactState.from_dict(state) if isinstance(state, dict) else state

    total_mass = max(m1 + m2, 1e-9)
    total_radius = max(r1 + r2, 1.0)

    binding = binding_energy_proxy(total_mass, max(total_radius * 0.5, 1.0))
    orbital = orbital_energy_proxy(m1, m2, relative_speed)

    energy_ratio = orbital / max(binding, 1e-9)
    solar = solar_masses(total_mass)
    compactness = total_mass / max(total_radius, 1.0)

    # Instabilidade cresce com energia orbital, massa total, overlap e fusões sucessivas.
    instability = (
        energy_ratio * 0.90 +
        clamp(solar / 20.0, 0.0, 3.0) +
        clamp(overlap_ratio, 0.0, 3.0) * 0.35 +
        max(0, merge_count - 1) * 0.22 +
        st.time * 0.10
    )
    st.instability = max(st.instability, instability)

    if st.time < 0.35:
        phase = "contact"
    elif st.instability < 1.15:
        phase = "common_envelope"
    elif st.instability < 2.50:
        phase = "violent_envelope"
    else:
        phase = "collapse_candidate"

    # Damping não é bounce: é remoção de energia orbital por plasma/envelope.
    damping = clamp(0.055 + overlap_ratio * 0.055 + energy_ratio * 0.035 + st.time * 0.018, 0.05, 0.48)
    pull = clamp(0.018 + overlap_ratio * 0.030 + st.time * 0.010, 0.015, 0.16)

    # Massa expulsa aumenta com energia disponível e fase.
    loss_base = 0.00018 + clamp(energy_ratio, 0.0, 4.0) * 0.0012
    if phase == "violent_envelope":
        loss_base *= 2.2
    elif phase == "collapse_candidate":
        loss_base *= 4.0

    loss_base += clamp(relative_speed / 1200.0, 0.0, 0.004)
    mass_loss_fraction = clamp(loss_base, 0.00012, 0.028)

    envelope_mass_fraction = clamp(0.002 + overlap_ratio * 0.006 + energy_ratio * 0.004, 0.001, 0.055)

    # Merge só quando já houve envelope/instabilidade, ou quando o núcleo comum está inevitável.
    merge_ready = (
        st.time > 3.5
        or (st.time > 1.6 and overlap_ratio > 0.85)
        or (st.time > 1.2 and st.instability > 3.0)
        or (st.time > 0.8 and solar >= 25.0 and overlap_ratio > 0.45)
    )

    remnant_name, remnant_material, radius_factor = classify_remnant(total_mass, st.instability)

    explosion_strength = clamp(
        st.instability +
        clamp(solar / 12.0, 0.0, 4.0) +
        max(0, merge_count - 1) * 0.18,
        0.0,
        8.0,
    )

    return StellarCollisionStep(
        phase=phase,
        damping=damping,
        pull=pull,
        mass_loss_fraction=mass_loss_fraction,
        envelope_mass_fraction=envelope_mass_fraction,
        merge_ready=merge_ready,
        explosion_strength=explosion_strength,
        remnant_kind=remnant_name,
        remnant_material=remnant_material,
        remnant_radius_factor=radius_factor,
        compactness=compactness,
        instability=st.instability,
    )


def final_mass_after_stellar_event(raw_mass, state, explosion_strength):
    st = StellarContactState.from_dict(state) if isinstance(state, dict) else state

    # Perda mínima para qualquer envelope; perda forte para colapso/supernova simplificada.
    frac = clamp(0.02 + explosion_strength * 0.035 + st.mass_lost / max(raw_mass, 1e-9) * 0.20, 0.015, 0.55)
    return max(raw_mass * (1.0 - frac), 1e-9), raw_mass * frac
