# physics_core/ejecta_limits.py
"""Ejecta limits.

Corrige o problema:
colisão planetária estava gerando detritos enormes, rápidos e visuais demais.

Feynman:
- nem toda energia vira pedaço sólido voando;
- parte vira calor;
- parte derrete/vaporiza;
- só uma fração pequena vira fragmento visível;
- velocidade do detrito não pode ignorar escape velocity e massa do corpo.
"""

import math


def clamp(v, a, b):
    return max(a, min(b, v))


def escape_velocity_proxy(G, mass, radius):
    return math.sqrt(max(2.0 * float(G) * float(mass) / max(float(radius), 1.0), 0.0))


def bounded_planetary_ejecta_fraction(severity, impact_speed, escape_speed):
    """Fração máxima de massa que pode virar detrito sólido visível."""
    sev = max(float(severity), 0.0)
    speed_ratio = float(impact_speed) / max(float(escape_speed), 1e-9)

    # Para impactos moderados, detrito sólido é baixo.
    base = 0.006 + min(sev, 1.0) * 0.045

    # Se velocidade é extrema, muita massa vira vapor/energia, não bloco sólido gigante.
    if speed_ratio > 2.5:
        base *= 0.45
    elif speed_ratio > 1.5:
        base *= 0.70

    return clamp(base, 0.0005, 0.018)


def bounded_fragment_count(severity, source_radius, performance_mode=False):
    sev = max(float(severity), 0.0)
    count = int(2 + min(sev, 2.0) * 4 + min(float(source_radius), 30.0) * 0.08)
    if performance_mode:
        count = min(count, 6)
    return int(clamp(count, 1, 4))


def bounded_fragment_radius(parent_radius, mass_fraction):
    """Fragmento não pode nascer do tamanho de planeta por causa de escala visual."""
    parent_radius = max(float(parent_radius), 1.0)
    mf = clamp(float(mass_fraction), 0.0, 1.0)

    # Raio físico cúbico, mas com teto visual forte.
    r = parent_radius * (mf ** (1.0 / 3.0)) * 0.55
    return clamp(r, 0.45, max(0.9, parent_radius * 0.14))


def bounded_ejecta_speed(impact_speed, escape_speed, severity):
    sev = max(float(severity), 0.0)
    impact_speed = max(float(impact_speed), 0.0)
    escape_speed = max(float(escape_speed), 1.0)

    # Detritos ficam em escala de escape velocity, não em velocidade arbitrária do impacto.
    low = escape_speed * 0.18
    high = escape_speed * (0.55 + min(sev, 2.0) * 0.25)

    return clamp(high, low, min(max(impact_speed * 0.35, low), escape_speed * 1.15))


def should_render_as_vapor(severity, temperature, material):
    if str(material) in ("plasma", "gas"):
        return True
    if float(temperature) > 3600:
        return True
    if float(severity) > 1.4:
        return True
    return False
