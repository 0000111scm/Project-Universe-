# physics/planetary_collision.py
"""Modelos físicos mínimos para colisão planeta-planeta.

Foco:
- parar fusão instantânea;
- estimar energia de ligação gravitacional;
- decidir entre contato inelástico, acreção parcial, fragmentação e disrupção;
- manter tudo como aproximação expandível para SPH.
"""

from dataclasses import dataclass
import math


def clamp(v, a, b):
    return max(a, min(b, v))


@dataclass
class PlanetaryCollisionDecision:
    mode: str
    merge_fraction: float
    ejecta_fraction: float
    damping: float
    should_fragment: bool
    should_merge: bool
    severity: float


def binding_energy_proxy(mass, radius, G=0.6006):
    mass = max(float(mass), 1.0e-9)
    radius = max(float(radius), 1.0)
    return 0.6 * G * mass * mass / radius


def reduced_mass(m1, m2):
    return (m1 * m2) / max(m1 + m2, 1.0e-9)


def decide_planetary_collision(a, b, impact):
    m1 = float(getattr(a, "mass", 0.0))
    m2 = float(getattr(b, "mass", 0.0))
    r1 = float(getattr(a, "radius", 1.0))
    r2 = float(getattr(b, "radius", 1.0))

    total = max(m1 + m2, 1.0e-9)
    small = min(m1, m2)
    big = max(m1, m2)
    mass_ratio = small / max(big, 1.0e-9)

    v = max(float(getattr(impact, "relative_velocity", 0.0)), 0.0)
    normal_v = max(float(getattr(impact, "normal_velocity", 0.0)), 0.0)
    tang_v = max(float(getattr(impact, "tangential_velocity", 0.0)), 0.0)

    mu = reduced_mass(m1, m2)
    kinetic = 0.5 * mu * v * v
    bind = binding_energy_proxy(total, max(r1 + r2, 1.0))
    severity = kinetic / max(bind, 1.0e-9)

    graze = tang_v / max(v, 1.0e-9)
    frontal = normal_v / max(v, 1.0e-9)

    # Regras físicas simples:
    # impacto lento + frontal pode virar acreção, mas ainda com perda/ejecta.
    if severity < 0.015 and frontal > 0.55:
        return PlanetaryCollisionDecision(
            mode="gentle_accretion",
            merge_fraction=0.72,
            ejecta_fraction=0.02 + graze * 0.04,
            damping=0.55,
            should_fragment=False,
            should_merge=True,
            severity=severity,
        )

    # impacto moderado: não funde instantaneamente; vira deformação + ejecta + fragmentação leve.
    if severity < 0.20:
        return PlanetaryCollisionDecision(
            mode="inelastic_deformation",
            merge_fraction=0.15 if mass_ratio > 0.15 else 0.35,
            ejecta_fraction=clamp(0.015 + severity * 0.16 + graze * 0.035, 0.01, 0.10),
            damping=clamp(0.35 + severity * 0.60, 0.35, 0.70),
            should_fragment=True,
            should_merge=False,
            severity=severity,
        )

    # impacto forte: fragmentação/disrupção parcial.
    if severity < 1.0:
        return PlanetaryCollisionDecision(
            mode="partial_disruption",
            merge_fraction=0.05,
            ejecta_fraction=clamp(0.08 + severity * 0.26, 0.08, 0.34),
            damping=0.78,
            should_fragment=True,
            should_merge=False,
            severity=severity,
        )

    # impacto extremo: disrupção catastrófica.
    return PlanetaryCollisionDecision(
        mode="catastrophic_disruption",
        merge_fraction=0.0,
        ejecta_fraction=clamp(0.35 + severity * 0.18, 0.35, 0.80),
        damping=0.88,
        should_fragment=True,
        should_merge=False,
        severity=severity,
    )
