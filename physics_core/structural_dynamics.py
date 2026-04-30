# physics_core/structural_dynamics.py
"""Structural Dynamics — spin, inertia tensor, Roche stress.

Feynman:
- massa girando quer sair pela tangente;
- gravidade/material tentam segurar;
- outro astro perto puxa um lado mais que o outro;
- se a soma dessas tensões passa a ligação interna, o corpo começa a se romper.

Ainda é 2D, mas usa relações físicas diretas:
- tensor de inércia proxy
- velocidade angular crítica
- tensão centrífuga
- tensão de maré/Roche
- decisão de ruptura progressiva
"""

from dataclasses import dataclass
import math


@dataclass
class StructuralState:
    inertia_xx: float
    inertia_yy: float
    inertia_xy: float
    spin_stress: float
    tidal_stress: float
    roche_ratio: float
    flattening: float
    failure: float
    should_shed_mass: bool
    should_disrupt: bool


MATERIAL_STRENGTH = {
    "ice": 0.35,
    "rock": 1.00,
    "metal": 1.80,
    "gas": 0.08,
    "plasma": 0.01,
    "blackhole": 1.0e12,
}


def clamp(v, a, b):
    return max(a, min(b, v))


def material_strength(body):
    return MATERIAL_STRENGTH.get(str(getattr(body, "material", "rock")), 1.0)


def inertia_tensor_2d(body):
    """Tensor de inércia proxy para disco/corpo circular 2D.

    Para um disco uniforme:
    Izz = 1/2 M R².
    Aqui guardamos componentes 2D equivalentes para preparar tensor real 3D depois.
    """
    m = max(float(getattr(body, "mass", 0.0)), 1e-9)
    r = max(float(getattr(body, "radius", 1.0)), 1.0)
    i = 0.25 * m * r * r
    return i, i, 0.0


def critical_angular_velocity(body, G=0.6006):
    """ω crítico quando centrífuga ~ gravidade superficial."""
    m = max(float(getattr(body, "mass", 0.0)), 1e-9)
    r = max(float(getattr(body, "radius", 1.0)), 1.0)
    return math.sqrt(max(G * m / (r ** 3), 0.0))


def spin_flattening(body, G=0.6006):
    omega = abs(float(getattr(body, "angular_velocity", 0.0)))
    omega_crit = max(critical_angular_velocity(body, G), 1e-9)
    q = (omega / omega_crit) ** 2
    return clamp(q * 0.35, 0.0, 0.85)


def spin_stress(body, G=0.6006):
    omega = abs(float(getattr(body, "angular_velocity", 0.0)))
    omega_crit = max(critical_angular_velocity(body, G), 1e-9)
    strength = material_strength(body)
    return (omega / omega_crit) ** 2 / max(strength, 1e-9)


def roche_limit(primary, secondary):
    """Limite de Roche proxy usando densidade massa/r³."""
    rp = max(float(primary.radius), 1.0)
    rho_p = float(primary.mass) / max(rp ** 3, 1e-9)
    rho_s = float(secondary.mass) / max(float(secondary.radius) ** 3, 1e-9)
    return 2.44 * rp * (rho_p / max(rho_s, 1e-9)) ** (1.0 / 3.0)


def tidal_stress(primary, secondary, distance, G=0.6006):
    """Tensão de maré normalizada.

    Gradiente ~ 2GM R / d³.
    Gravidade própria ~ GM/R².
    ratio ~ (M_primary/M_secondary)*(R_secondary/d)^3
    """
    d = max(float(distance), 1.0)
    ratio = (
        float(primary.mass) / max(float(secondary.mass), 1e-9)
        * (float(secondary.radius) / d) ** 3
    )
    strength = material_strength(secondary)
    return ratio / max(strength, 1e-9)


def evaluate_structural_state(body, primary=None, distance=None, G=0.6006):
    ixx, iyy, ixy = inertia_tensor_2d(body)
    s_stress = spin_stress(body, G)
    flat = spin_flattening(body, G)

    roche_ratio = 0.0
    t_stress = 0.0
    if primary is not None and distance is not None:
        roche = roche_limit(primary, body)
        roche_ratio = max(0.0, roche / max(float(distance), 1.0))
        t_stress = tidal_stress(primary, body, distance, G)

    failure = clamp(max(s_stress, t_stress, roche_ratio - 0.75), 0.0, 5.0)

    return StructuralState(
        inertia_xx=ixx,
        inertia_yy=iyy,
        inertia_xy=ixy,
        spin_stress=s_stress,
        tidal_stress=t_stress,
        roche_ratio=roche_ratio,
        flattening=flat,
        failure=failure,
        should_shed_mass=failure > 0.85,
        should_disrupt=failure > 1.65,
    )


def mass_shedding_fraction(state):
    if not state.should_shed_mass:
        return 0.0
    if state.should_disrupt:
        return clamp(0.04 + state.failure * 0.045, 0.04, 0.25)
    return clamp(0.006 + state.failure * 0.018, 0.006, 0.06)
