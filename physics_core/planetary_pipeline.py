# physics_core/planetary_pipeline.py
"""Persistent/physical planetary impact pipeline.

Substitui a ideia arcade:
    planeta tocou planeta -> merge

Por causa/efeito:
    velocidade relativa + massa reduzida -> energia de impacto
    energia / energia de ligação -> severidade
    severidade decide:
      - deformação
      - hit-and-run
      - acreção parcial
      - disrupção parcial
      - disrupção catastrófica
    massa ejetada e remanescente vêm de energia, não if mágico.
"""

from dataclasses import dataclass
import math


def clamp(v, a, b):
    return max(a, min(b, v))


@dataclass
class PlanetaryImpactOutcome:
    mode: str
    severity: float
    bound_fraction: float
    ejecta_fraction: float
    accreted_fraction: float
    heat_fraction: float
    damping: float
    remove_secondary: bool
    create_remnant: bool
    catastrophic: bool


def reduced_mass(m1, m2):
    return (m1 * m2) / max(m1 + m2, 1e-9)


def binding_energy_proxy(mass, radius, G=0.6006):
    return 0.6 * G * float(mass) * float(mass) / max(float(radius), 1.0)


def escape_velocity_proxy(mass, radius, G=0.6006):
    return math.sqrt(max(2.0 * G * float(mass) / max(float(radius), 1.0), 0.0))


def classify_planetary_impact(a, b, impact, G=0.6006):
    m1 = float(a.mass)
    m2 = float(b.mass)
    r1 = float(a.radius)
    r2 = float(b.radius)
    total = max(m1 + m2, 1e-9)
    small = min(m1, m2)
    big = max(m1, m2)
    mass_ratio = small / max(big, 1e-9)

    v = max(float(getattr(impact, "relative_velocity", 0.0)), 0.0)
    vn = max(float(getattr(impact, "normal_velocity", 0.0)), 0.0)
    vt = max(float(getattr(impact, "tangential_velocity", 0.0)), 0.0)
    normal_fraction = vn / max(v, 1e-9)
    graze = vt / max(v, 1e-9)

    mu = reduced_mass(m1, m2)
    impact_energy = 0.5 * mu * v * v
    bind = binding_energy_proxy(total, max(r1 + r2, 1.0), G)
    severity = impact_energy / max(bind, 1e-9)

    vesc = escape_velocity_proxy(total, max(r1 + r2, 1.0), G)
    speed_ratio = v / max(vesc, 1e-9)

    # Baixa energia, frontal, massas comparáveis -> acreção parcial, não fusão mágica total.
    if severity < 0.020 and normal_fraction > 0.55 and speed_ratio < 0.55:
        return PlanetaryImpactOutcome(
            mode="partial_accretion",
            severity=severity,
            bound_fraction=0.92,
            ejecta_fraction=0.002,
            accreted_fraction=0.35,
            heat_fraction=0.28,
            damping=0.55,
            remove_secondary=False,
            create_remnant=False,
            catastrophic=False,
        )

    # Rasante com velocidade alta -> hit-and-run/deformação.
    if graze > 0.62 and speed_ratio > 0.35:
        return PlanetaryImpactOutcome(
            mode="hit_and_run_deformation",
            severity=severity,
            bound_fraction=clamp(0.94 - severity * 0.10, 0.80, 0.94),
            ejecta_fraction=clamp(0.002 + severity * 0.012, 0.002, 0.018),
            accreted_fraction=0.02,
            heat_fraction=0.18 + normal_fraction * 0.22,
            damping=0.30,
            remove_secondary=False,
            create_remnant=False,
            catastrophic=False,
        )

    # Energia moderada -> deformação forte + cratera + ejecta.
    if severity < 0.35:
        return PlanetaryImpactOutcome(
            mode="sph_deformation",
            severity=severity,
            bound_fraction=clamp(0.94 - severity * 0.24, 0.76, 0.94),
            ejecta_fraction=clamp(0.003 + severity * 0.018, 0.003, 0.022),
            accreted_fraction=clamp(0.04 + mass_ratio * 0.08, 0.03, 0.14),
            heat_fraction=clamp(0.28 + normal_fraction * 0.32, 0.22, 0.62),
            damping=clamp(0.42 + severity * 0.65, 0.42, 0.78),
            remove_secondary=False,
            create_remnant=False,
            catastrophic=False,
        )

    # Energia alta -> disrupção parcial. Não vira um corpo só.
    if severity < 1.15:
        return PlanetaryImpactOutcome(
            mode="partial_disruption",
            severity=severity,
            bound_fraction=clamp(0.82 - severity * 0.10, 0.58, 0.82),
            ejecta_fraction=clamp(0.012 + severity * 0.028, 0.012, 0.060),
            accreted_fraction=0.0,
            heat_fraction=clamp(0.45 + normal_fraction * 0.30, 0.42, 0.78),
            damping=0.84,
            remove_secondary=False,
            create_remnant=True,
            catastrophic=False,
        )

    # Energia extrema -> disrupção catastrófica.
    return PlanetaryImpactOutcome(
        mode="catastrophic_disruption",
        severity=severity,
        bound_fraction=clamp(0.64 - min(severity, 4.0) * 0.035, 0.45, 0.64),
        ejecta_fraction=clamp(0.030 + min(severity, 4.0) * 0.030, 0.030, 0.140),
        accreted_fraction=0.0,
        heat_fraction=0.82,
        damping=0.92,
        remove_secondary=True,
        create_remnant=True,
        catastrophic=True,
    )
