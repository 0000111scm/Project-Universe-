# physics/material_model.py

from dataclasses import dataclass


@dataclass(frozen=True)
class MaterialProfile:
    name: str
    density: float                 # kg/m³ aproximado conceitual
    structural_strength: float     # J/kg - energia específica para dano estrutural
    melting_point: float           # K
    vaporization_point: float      # K
    restitution: float             # 0 = inelástico, 1 = elástico
    heat_absorption: float         # fração típica da energia que vira calor
    fragmentation_bias: float      # tendência a fragmentar
    ejecta_bias: float             # tendência a ejetar massa


MATERIALS = {
    "ice": MaterialProfile(
        name="ice",
        density=920.0,
        structural_strength=2.0e4,
        melting_point=273.15,
        vaporization_point=373.15,
        restitution=0.18,
        heat_absorption=0.42,
        fragmentation_bias=0.35,
        ejecta_bias=0.30,
    ),
    "rock": MaterialProfile(
        name="rock",
        density=3300.0,
        structural_strength=1.0e5,
        melting_point=1500.0,
        vaporization_point=3200.0,
        restitution=0.12,
        heat_absorption=0.34,
        fragmentation_bias=0.45,
        ejecta_bias=0.24,
    ),
    "metal": MaterialProfile(
        name="metal",
        density=7800.0,
        structural_strength=3.0e5,
        melting_point=1800.0,
        vaporization_point=3300.0,
        restitution=0.16,
        heat_absorption=0.30,
        fragmentation_bias=0.28,
        ejecta_bias=0.18,
    ),
    "gas": MaterialProfile(
        name="gas",
        density=1.2,
        structural_strength=8.0e3,
        melting_point=90.0,
        vaporization_point=140.0,
        restitution=0.04,
        heat_absorption=0.65,
        fragmentation_bias=0.08,
        ejecta_bias=0.45,
    ),
    "plasma": MaterialProfile(
        name="plasma",
        density=0.1,
        structural_strength=1.0e4,
        melting_point=5000.0,
        vaporization_point=10000.0,
        restitution=0.02,
        heat_absorption=0.78,
        fragmentation_bias=0.02,
        ejecta_bias=0.25,
    ),
    "blackhole": MaterialProfile(
        name="blackhole",
        density=1.0e18,
        structural_strength=1.0e12,
        melting_point=1.0e30,
        vaporization_point=1.0e30,
        restitution=0.0,
        heat_absorption=0.0,
        fragmentation_bias=0.0,
        ejecta_bias=0.0,
    ),
}


def get_material_profile(material: str) -> MaterialProfile:
    return MATERIALS.get(material, MATERIALS["rock"])


def infer_material(body) -> str:
    """Inferência simples para o protótipo.

    PATCH 40 não tenta simular mineralogia completa ainda.
    Ele só elimina o absurdo de tratar rocha, gelo, gás e plasma como se fossem iguais.
    """
    mass = getattr(body, "mass", 0.0)
    explicit = getattr(body, "material", None)

    if mass >= 1.0e9:
        return "blackhole"
    if mass >= 5.0e7:
        return "plasma"
    if mass >= 5.0e4:
        return "gas"

    if explicit in MATERIALS:
        return explicit

    water = getattr(body, "water", 0.0)
    temperature = getattr(body, "temperature", 300.0)

    if water > 0.35 and temperature < 273.15:
        return "ice"

    composition = getattr(body, "composition", {})
    if composition.get("metals", 0.0) > 0.45:
        return "metal"

    return "rock"


def mixed_strength(body_a, body_b) -> float:
    mat_a = get_material_profile(infer_material(body_a))
    mat_b = get_material_profile(infer_material(body_b))

    # O elo mais fraco domina a primeira ruptura.
    return min(mat_a.structural_strength, mat_b.structural_strength)


def material_pair_response(body_a, body_b):
    mat_a = get_material_profile(infer_material(body_a))
    mat_b = get_material_profile(infer_material(body_b))

    total = max(getattr(body_a, "mass", 0.0) + getattr(body_b, "mass", 0.0), 1e-9)
    wa = getattr(body_a, "mass", 0.0) / total
    wb = getattr(body_b, "mass", 0.0) / total

    return {
        "heat_absorption": mat_a.heat_absorption * wa + mat_b.heat_absorption * wb,
        "fragmentation_bias": mat_a.fragmentation_bias * wa + mat_b.fragmentation_bias * wb,
        "ejecta_bias": mat_a.ejecta_bias * wa + mat_b.ejecta_bias * wb,
        "restitution": mat_a.restitution * wa + mat_b.restitution * wb,
        "material_a": mat_a.name,
        "material_b": mat_b.name,
    }
