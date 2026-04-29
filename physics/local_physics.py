# physics/local_physics.py
"""Energia local mínima por camadas.

Não é SPH ainda. É o primeiro passo para parar de aquecer o corpo inteiro
quando um impacto atinge só a superfície.
"""

def clamp(v, a, b):
    return max(a, min(b, v))


LAYER_PRESETS = {
    "rock": (
        ("crosta", 0.035, 900.0),
        ("manto", 0.640, 1200.0),
        ("núcleo", 0.325, 850.0),
    ),
    "metal": (
        ("crosta", 0.020, 600.0),
        ("manto", 0.180, 750.0),
        ("núcleo", 0.800, 520.0),
    ),
    "ice": (
        ("crosta", 0.120, 2100.0),
        ("manto", 0.680, 2600.0),
        ("núcleo", 0.200, 900.0),
    ),
    "gas": (
        ("envelope", 0.920, 14000.0),
        ("núcleo", 0.080, 900.0),
    ),
    "plasma": (
        ("envelope", 1.000, 22000.0),
    ),
    "blackhole": (
        ("horizonte", 1.000, 1.0e30),
    ),
}


def material_of(body):
    return getattr(body, "material", "rock")


def ensure_internal_layers(body):
    if hasattr(body, "internal_layers") and isinstance(body.internal_layers, list):
        return body.internal_layers

    material = material_of(body)
    preset = LAYER_PRESETS.get(material, LAYER_PRESETS["rock"])
    temp = float(getattr(body, "temperature", 300.0))
    mass = max(float(getattr(body, "mass", 1.0)), 1e-9)

    layers = []
    for name, fraction, heat_capacity in preset:
        layers.append({
            "name": name,
            "mass_fraction": fraction,
            "temperature": temp,
            "damage": 0.0,
            "heat_capacity": heat_capacity,
        })

    body.internal_layers = layers
    body.surface_damage = float(getattr(body, "surface_damage", 0.0))
    return layers


def deposit_impact_energy(body, heat_energy, affected_mass=None, depth="surface"):
    """Deposita calor localmente.

    - superfície/crosta recebe a maior parte;
    - parte pequena vaza para camadas internas;
    - body.temperature vira temperatura superficial aproximada.
    """
    layers = ensure_internal_layers(body)
    if heat_energy <= 0 or not layers:
        return 0.0

    mass = max(float(getattr(body, "mass", 1.0)), 1e-9)
    affected = max(float(affected_mass if affected_mass is not None else mass * 0.04), 1e-9)
    affected_fraction = clamp(affected / mass, 0.001, 1.0)

    # Estrelas/plasma distribuem no envelope; corpos sólidos concentram na crosta.
    material = material_of(body)
    if material in ("plasma", "gas"):
        shares = [1.0] + [0.0] * (len(layers) - 1)
    else:
        if depth == "deep":
            shares = [0.45, 0.40, 0.15]
        else:
            shares = [0.82, 0.15, 0.03]
        shares = shares[:len(layers)]
        total = sum(shares) or 1.0
        shares = [s / total for s in shares]

    max_delta = 0.0
    for layer, share in zip(layers, shares):
        layer_mass = max(mass * layer["mass_fraction"] * affected_fraction, 1e-9)
        heat_capacity = max(float(layer.get("heat_capacity", 900.0)), 1e-9)
        delta_t = heat_energy * share / (layer_mass * heat_capacity)
        delta_t = clamp(delta_t, 0.0, 35000.0)
        layer["temperature"] = max(float(layer.get("temperature", 300.0)), float(layer.get("temperature", 300.0)) + delta_t)
        layer["damage"] = clamp(float(layer.get("damage", 0.0)) + delta_t / 25000.0 * share, 0.0, 1.0)
        max_delta = max(max_delta, delta_t)

    # Temperatura exibida = camada externa, não média global.
    body.temperature = max(float(getattr(body, "temperature", 300.0)), float(layers[0]["temperature"]))
    body.surface_damage = clamp(float(getattr(body, "surface_damage", 0.0)) + max_delta / 50000.0, 0.0, 1.0)
    return max_delta


def relax_internal_layers(body, dt):
    layers = ensure_internal_layers(body)
    if len(layers) < 2:
        return

    dt = max(float(dt), 0.0)
    if dt <= 0:
        return

    # Difusão simples entre camadas vizinhas.
    k = min(0.08, dt * 0.012)
    for i in range(len(layers) - 1):
        hot = layers[i]
        cold = layers[i + 1]
        diff = (hot["temperature"] - cold["temperature"]) * k
        hot["temperature"] -= diff
        cold["temperature"] += diff * 0.65

    # Resfriamento superficial lento.
    layers[0]["temperature"] = max(3.0, layers[0]["temperature"] - dt * 2.5)
    layers[0]["damage"] = clamp(layers[0].get("damage", 0.0) - dt * 0.0008, 0.0, 1.0)
    body.surface_damage = clamp(float(getattr(body, "surface_damage", 0.0)) - dt * 0.0005, 0.0, 1.0)
    body.temperature = max(3.0, layers[0]["temperature"])
