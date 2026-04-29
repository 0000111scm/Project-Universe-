# physics/structural_damage.py

from dataclasses import dataclass


def clamp(value, low, high):
    return max(low, min(high, value))


@dataclass
class DamageResult:
    impact_damage: float
    thermal_damage: float
    total_damage: float
    integrity: float
    should_shed_mass: bool
    should_break_apart: bool


def ensure_structure(body):
    """Inicializa campos estruturais sem exigir mudança em body.py."""
    if not hasattr(body, "structural_integrity"):
        body.structural_integrity = 1.0
    if not hasattr(body, "damage_accumulated"):
        body.damage_accumulated = 0.0
    if not hasattr(body, "thermal_damage"):
        body.thermal_damage = 0.0
    return body


def apply_structural_damage(body, impact=None, heat_energy=0.0, affected_mass=None, strength=1.0e5):
    """Dano estrutural acumulado.

    Ideia:
    - impacto pequeno não destrói instantaneamente;
    - impactos repetidos enfraquecem o corpo;
    - calor extremo também degrada integridade;
    - ruptura só acontece quando integridade cai muito.
    """
    ensure_structure(body)

    mass = max(affected_mass if affected_mass is not None else getattr(body, "mass", 1.0), 1e-9)
    strength = max(strength, 1e-9)

    q = getattr(impact, "specific_energy", 0.0) if impact is not None else 0.0
    impact_ratio = clamp(q / strength, 0.0, 50.0)

    impact_damage = clamp(impact_ratio * 0.18, 0.0, 0.85)

    temp = getattr(body, "temperature", 300.0)
    material = getattr(body, "material", "rock")

    thermal_limit = {
        "ice": 273.15,
        "rock": 1500.0,
        "metal": 1800.0,
        "gas": 2500.0,
        "plasma": 12000.0,
        "blackhole": 1.0e30,
    }.get(material, 1500.0)

    heat_ratio = clamp(temp / max(thermal_limit, 1.0), 0.0, 10.0)
    direct_heat_ratio = clamp(heat_energy / max(mass * strength, 1e-9), 0.0, 10.0)

    thermal_damage = clamp((heat_ratio - 0.75) * 0.08 + direct_heat_ratio * 0.12, 0.0, 0.55)

    total = clamp(impact_damage + thermal_damage, 0.0, 0.95)

    # Dano não é todo permanente; parte relaxa/redistribui. Mas acumula.
    body.damage_accumulated = clamp(getattr(body, "damage_accumulated", 0.0) + total * 0.45, 0.0, 1.0)
    body.thermal_damage = clamp(getattr(body, "thermal_damage", 0.0) + thermal_damage * 0.35, 0.0, 1.0)

    integrity_loss = total * 0.35 + body.damage_accumulated * 0.08 + body.thermal_damage * 0.05
    body.structural_integrity = clamp(getattr(body, "structural_integrity", 1.0) - integrity_loss, 0.0, 1.0)

    return DamageResult(
        impact_damage=impact_damage,
        thermal_damage=thermal_damage,
        total_damage=total,
        integrity=body.structural_integrity,
        should_shed_mass=body.structural_integrity < 0.55 and total > 0.12,
        should_break_apart=body.structural_integrity < 0.22 and total > 0.25,
    )


def relax_structure(body, dt):
    """Relaxamento lento: corpo não fica eternamente no vermelho após dano leve."""
    ensure_structure(body)

    recovery = dt * 0.006
    body.damage_accumulated = clamp(body.damage_accumulated - recovery, 0.0, 1.0)

    # Integridade volta pouco, nunca cura totalmente rápido.
    if body.damage_accumulated < 0.15 and body.thermal_damage < 0.20:
        body.structural_integrity = clamp(body.structural_integrity + dt * 0.002, 0.0, 1.0)

    # Dano térmico relaxa com resfriamento.
    temp = getattr(body, "temperature", 300.0)
    if temp < 900:
        body.thermal_damage = clamp(body.thermal_damage - dt * 0.004, 0.0, 1.0)
