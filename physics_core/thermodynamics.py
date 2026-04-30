# physics_core/thermodynamics.py
"""Thermodynamics + phase engine.

Feynman:
- colisão perde energia cinética;
- energia perdida não some;
- ela vira calor local;
- calor + pressão dizem se material fica sólido, magma, vapor ou plasma.

Este módulo não tenta ser química completa ainda.
Ele cria a primeira tabela física coerente para materiais principais.
"""

from dataclasses import dataclass
import math

SIGMA = 5.670374419e-8  # Stefan-Boltzmann SI; usado como escala normalizada
SPACE_TEMPERATURE = 3.0


@dataclass
class PhaseMaterial:
    name: str
    density: float
    heat_capacity: float
    melt_temperature: float
    vapor_temperature: float
    plasma_temperature: float
    latent_heat_melt: float
    latent_heat_vapor: float
    strength: float


MATERIAL_PHASES = {
    "rock": PhaseMaterial("rock", 3300.0, 900.0, 1450.0, 3200.0, 9000.0, 4.0e5, 6.0e6, 8.0e5),
    "metal": PhaseMaterial("metal", 7800.0, 520.0, 1800.0, 3400.0, 10000.0, 2.7e5, 6.3e6, 1.4e6),
    "ice": PhaseMaterial("ice", 920.0, 2100.0, 273.15, 650.0, 4500.0, 3.3e5, 2.8e6, 1.2e5),
    "gas": PhaseMaterial("gas", 1.2, 14000.0, 80.0, 400.0, 3500.0, 0.0, 1.0e5, 1.0e3),
    "plasma": PhaseMaterial("plasma", 0.01, 22000.0, 3000.0, 12000.0, 12000.0, 0.0, 0.0, 1.0),
    "blackhole": PhaseMaterial("blackhole", 1.0e30, 1.0e30, 1.0e30, 1.0e30, 1.0e30, 0.0, 0.0, 1.0e30),
}


PHASE_SOLID = 0
PHASE_LIQUID = 1
PHASE_VAPOR = 2
PHASE_PLASMA = 3


def clamp(v, a, b):
    return max(a, min(b, v))


def material_phase_data(material):
    return MATERIAL_PHASES.get(str(material), MATERIAL_PHASES["rock"])


def pressure_boost_temperature(pressure, gravity=1.0):
    """Pressão aumenta ponto de ebulição/fusão de forma simplificada."""
    p = max(float(pressure), 0.0)
    g = max(float(gravity), 0.0)
    return math.log1p(p * 1.0e-5 + g * 1.0e-3) * 55.0


def classify_phase(material, temperature, pressure=0.0, gravity=1.0):
    data = material_phase_data(material)
    t = float(temperature)
    boost = pressure_boost_temperature(pressure, gravity)

    melt = data.melt_temperature + boost * 0.35
    vapor = data.vapor_temperature + boost
    plasma = data.plasma_temperature + boost * 0.25

    if t >= plasma:
        return PHASE_PLASMA
    if t >= vapor:
        return PHASE_VAPOR
    if t >= melt:
        return PHASE_LIQUID
    return PHASE_SOLID


def phase_name(phase):
    return {
        PHASE_SOLID: "solid",
        PHASE_LIQUID: "liquid",
        PHASE_VAPOR: "vapor",
        PHASE_PLASMA: "plasma",
    }.get(int(phase), "unknown")


def temperature_delta_from_energy(material, energy, affected_mass):
    data = material_phase_data(material)
    mass = max(float(affected_mass), 1.0e-9)
    return float(energy) / max(mass * data.heat_capacity, 1.0e-9)


def impact_heat_partition(impact_energy, normal_fraction=0.5, material="rock"):
    """Quanto da energia de impacto vira calor local.

    Impacto frontal comprime mais -> mais calor.
    Impacto rasante joga mais energia em rotação/ejecta.
    """
    n = clamp(float(normal_fraction), 0.0, 1.0)
    mat = material_phase_data(material)
    strength_factor = clamp(8.0e5 / max(mat.strength, 1.0), 0.25, 2.2)
    heat_fraction = clamp(0.18 + 0.42 * n * strength_factor, 0.08, 0.72)
    return float(impact_energy) * heat_fraction


def radiative_cooling_delta(temperature, radius, mass, dt, emissivity=0.85):
    """Resfriamento radiativo aproximado.

    Usa Stefan-Boltzmann como escala:
    P = área * emissividade * sigma * (T^4 - espaço^4)
    No protótipo a escala é amortecida para não congelar tudo em segundos.
    """
    t = max(float(temperature), SPACE_TEMPERATURE)
    r = max(float(radius), 1.0)
    m = max(float(mass), 1.0e-9)
    area = 4.0 * math.pi * r * r
    power = area * float(emissivity) * SIGMA * max(0.0, t**4 - SPACE_TEMPERATURE**4)

    # escala interna do simulador, para não usar watts reais diretamente
    scaled_power = power * 1.0e-9
    heat_capacity = 1200.0
    return scaled_power * float(dt) / max(m * heat_capacity, 1.0e-9)


def apply_body_thermodynamics(body, dt):
    """Atualiza fase/temperatura agregada do Body."""
    material = getattr(body, "material", "rock")
    temp = float(getattr(body, "temperature", 300.0))

    pressure = float(getattr(body, "atmosphere", 0.0)) * 1.0e5
    gravity = float(getattr(body, "mass", 0.0)) / max(float(getattr(body, "radius", 1.0))**2, 1.0)

    phase = classify_phase(material, temp, pressure=pressure, gravity=gravity)
    body.phase = phase_name(phase)

    # Material muda se extremo.
    if phase == PHASE_PLASMA:
        body.material = "plasma"
    elif phase == PHASE_VAPOR and material in ("ice", "rock"):
        body.vapor_fraction = min(1.0, getattr(body, "vapor_fraction", 0.0) + dt * 0.04)
    elif phase == PHASE_LIQUID and material in ("rock", "ice"):
        body.melt_fraction = min(1.0, getattr(body, "melt_fraction", 0.0) + dt * 0.03)

    # Resfriamento radiativo.
    if material != "blackhole":
        cooling = radiative_cooling_delta(temp, getattr(body, "radius", 1.0), getattr(body, "mass", 1.0), dt)
        body.temperature = max(SPACE_TEMPERATURE, temp - cooling)

    return phase
