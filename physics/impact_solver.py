# physics/impact_solver.py

from dataclasses import dataclass
from enum import Enum
import math


class ImpactType(Enum):
    ACCRETION = "accretion"
    MERGE = "merge"
    HIT_AND_RUN = "hit_and_run"
    GRAZE = "graze"
    CRATERING = "cratering"
    PARTIAL_DISRUPTION = "partial_disruption"
    CATASTROPHIC_DISRUPTION = "catastrophic_disruption"
    VAPORIZATION = "vaporization"


@dataclass
class ImpactInput:
    m1: float
    m2: float
    r1: float
    r2: float
    v1x: float
    v1y: float
    v2x: float
    v2y: float
    normal_x: float
    normal_y: float
    structural_strength: float

    # PATCH 40: resposta material média do par em colisão.
    heat_absorption: float = 0.35
    fragmentation_bias: float = 0.35
    ejecta_bias: float = 0.25
    restitution: float = 0.10


@dataclass
class EnergyPartition:
    heat: float
    deformation: float
    ejecta: float
    fragmentation: float


@dataclass
class ImpactResult:
    impact_type: ImpactType
    relative_velocity: float
    normal_velocity: float
    tangential_velocity: float
    reduced_mass: float
    impact_energy: float
    specific_energy: float
    disruption_threshold: float
    energy: EnergyPartition
    ejected_mass: float
    merged_mass: float
    should_merge: bool
    should_fragment: bool
    should_create_crater: bool


def _clamp(value, low, high):
    return max(low, min(high, value))


def normalize(x, y):
    length = math.sqrt(x * x + y * y)
    if length == 0:
        return 1.0, 0.0
    return x / length, y / length


def classify_impact(specific_energy, q_star, normal_v, tangential_v, v_rel):
    angle_factor = tangential_v / max(v_rel, 1e-9)

    if specific_energy > q_star * 20.0:
        return ImpactType.VAPORIZATION
    if specific_energy > q_star * 5.0:
        return ImpactType.CATASTROPHIC_DISRUPTION
    if specific_energy > q_star:
        return ImpactType.PARTIAL_DISRUPTION

    # Impactos rasantes não devem virar fusão mágica.
    if angle_factor > 0.78:
        return ImpactType.HIT_AND_RUN
    if angle_factor > 0.58:
        return ImpactType.GRAZE

    if specific_energy > q_star * 0.10:
        return ImpactType.CRATERING

    if normal_v > tangential_v:
        return ImpactType.MERGE

    return ImpactType.ACCRETION


def partition_energy(impact_energy, data: ImpactInput, impact_type: ImpactType):
    heat_fraction = _clamp(data.heat_absorption, 0.05, 0.85)
    frag_fraction = _clamp(0.10 + data.fragmentation_bias * 0.35, 0.02, 0.45)
    ejecta_fraction = _clamp(0.10 + data.ejecta_bias * 0.30, 0.02, 0.40)

    if impact_type in (ImpactType.HIT_AND_RUN, ImpactType.GRAZE):
        deformation_fraction = 0.18
        ejecta_fraction *= 0.55
        frag_fraction *= 0.45
    elif impact_type == ImpactType.CRATERING:
        deformation_fraction = 0.22
        ejecta_fraction *= 1.15
    elif impact_type in (ImpactType.CATASTROPHIC_DISRUPTION, ImpactType.VAPORIZATION):
        deformation_fraction = 0.08
        frag_fraction *= 1.35
        heat_fraction *= 1.15
    else:
        deformation_fraction = 0.25

    total = heat_fraction + deformation_fraction + ejecta_fraction + frag_fraction
    if total <= 0:
        return EnergyPartition(impact_energy, 0.0, 0.0, 0.0)

    scale = impact_energy / total
    return EnergyPartition(
        heat=heat_fraction * scale,
        deformation=deformation_fraction * scale,
        ejecta=ejecta_fraction * scale,
        fragmentation=frag_fraction * scale,
    )


def estimate_ejected_mass(total_mass, specific_energy, q_star, impact_type, data: ImpactInput):
    ratio = _clamp(specific_energy / max(q_star, 1e-9), 0.0, 50.0)
    ejecta_bias = _clamp(data.ejecta_bias, 0.02, 0.80)

    if impact_type == ImpactType.CRATERING:
        return total_mass * _clamp(0.002 + ratio * 0.015 * ejecta_bias, 0.001, 0.05)

    if impact_type == ImpactType.PARTIAL_DISRUPTION:
        return total_mass * _clamp(0.05 + ratio * 0.12 * ejecta_bias, 0.03, 0.35)

    if impact_type == ImpactType.CATASTROPHIC_DISRUPTION:
        return total_mass * _clamp(0.35 + ratio * 0.04 * ejecta_bias, 0.30, 0.75)

    if impact_type == ImpactType.VAPORIZATION:
        return total_mass * _clamp(0.65 + ratio * 0.01, 0.60, 0.95)

    return 0.0


def solve_impact(data: ImpactInput) -> ImpactResult:
    total_mass = data.m1 + data.m2
    if total_mass <= 0:
        raise ValueError("Massa total inválida no impacto.")

    reduced_mass = (data.m1 * data.m2) / total_mass

    rvx = data.v2x - data.v1x
    rvy = data.v2y - data.v1y
    v_rel = math.sqrt(rvx * rvx + rvy * rvy)

    nx, ny = normalize(data.normal_x, data.normal_y)

    normal_v = abs(rvx * nx + rvy * ny)
    tangential_v = math.sqrt(max(0.0, v_rel * v_rel - normal_v * normal_v))

    impact_energy = 0.5 * reduced_mass * v_rel * v_rel
    specific_energy = impact_energy / total_mass

    q_star = max(data.structural_strength, 1e-9)

    impact_type = classify_impact(
        specific_energy=specific_energy,
        q_star=q_star,
        normal_v=normal_v,
        tangential_v=tangential_v,
        v_rel=v_rel,
    )

    energy = partition_energy(impact_energy, data, impact_type)

    ejected_mass = estimate_ejected_mass(
        total_mass=total_mass,
        specific_energy=specific_energy,
        q_star=q_star,
        impact_type=impact_type,
        data=data,
    )

    merged_mass = max(0.0, total_mass - ejected_mass)

    return ImpactResult(
        impact_type=impact_type,
        relative_velocity=v_rel,
        normal_velocity=normal_v,
        tangential_velocity=tangential_v,
        reduced_mass=reduced_mass,
        impact_energy=impact_energy,
        specific_energy=specific_energy,
        disruption_threshold=q_star,
        energy=energy,
        ejected_mass=ejected_mass,
        merged_mass=merged_mass,
        should_merge=impact_type in (ImpactType.ACCRETION, ImpactType.MERGE),
        should_fragment=impact_type in (
            ImpactType.PARTIAL_DISRUPTION,
            ImpactType.CATASTROPHIC_DISRUPTION,
            ImpactType.VAPORIZATION,
        ),
        should_create_crater=impact_type == ImpactType.CRATERING,
    )
