# physics_core/stellar_accretion.py
"""Star/planet accretion model.

Problema corrigido:
Terra caindo no Sol não gera fragmentos rochosos gigantes.
Em termos físicos:
- o planeta entra em plasma estelar;
- material rochoso vaporiza/ioniza;
- massa e momento vão para a estrela;
- pode haver aquecimento local e pequena ejeção de plasma;
- não existe "anel rochoso" nem detrito sólido grande.

Feynman:
estrela é um oceano de plasma quente. Jogar rocha ali não cria pedregulho voando;
a rocha derrete, vaporiza, mistura e transfere energia.
"""

from dataclasses import dataclass
import math


def clamp(v, a, b):
    return max(a, min(b, v))


@dataclass
class StellarAccretionOutcome:
    absorbed_mass: float
    vaporized_mass: float
    plasma_ejecta_mass: float
    heat_energy: float
    momentum_fraction: float
    destroy_projectile: bool


def classify_star_planet_accretion(star, projectile, impact):
    star_mass = max(float(star.mass), 1e-9)
    proj_mass = max(float(projectile.mass), 1e-9)
    total = star_mass + proj_mass

    rel_v = max(float(getattr(impact, "relative_velocity", 0.0)), 0.0)
    impact_energy = max(float(getattr(impact, "impact_energy", 0.0)), 0.0)

    # Quanto menor o projétil em relação à estrela, mais ele simplesmente é absorvido/vaporizado.
    mass_ratio = proj_mass / max(star_mass, 1e-9)

    absorbed_fraction = clamp(0.94 - mass_ratio * 6.0, 0.72, 0.985)
    vaporized_fraction = clamp(0.05 + rel_v / 2500.0, 0.03, 0.22)

    absorbed = proj_mass * absorbed_fraction
    vaporized = min(proj_mass - absorbed, proj_mass * vaporized_fraction)

    # Ejeção visível é plasma, pequena. Não rocha.
    plasma_ejecta = clamp(impact_energy / max(star_mass * 2.5e5, 1e-9), 0.0, proj_mass * 0.018)
    plasma_ejecta = min(plasma_ejecta, proj_mass * 0.025)

    heat = impact_energy * 0.45

    # Momento do planeta altera estrela pouco, proporcional à massa.
    momentum_fraction = clamp(proj_mass / total, 0.0, 0.08)

    return StellarAccretionOutcome(
        absorbed_mass=max(0.0, absorbed),
        vaporized_mass=max(0.0, vaporized),
        plasma_ejecta_mass=max(0.0, plasma_ejecta),
        heat_energy=heat,
        momentum_fraction=momentum_fraction,
        destroy_projectile=True,
    )
