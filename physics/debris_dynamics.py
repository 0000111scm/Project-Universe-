# physics/debris_dynamics.py
"""Dinâmica mínima de detritos e anéis.

Correção física:
- planeta rochoso tipo Terra não ganha anel só porque houve colisão;
- anel só é permitido quando há massa/gravidade suficiente e detritos orbitais;
- detrito precisa estar fora da superfície e dentro de região orbital plausível;
- fragmento precisa ter velocidade tangencial próxima da orbital, não só "estar perto".
"""

import math


def clamp(v, a, b):
    return max(a, min(b, v))


def can_body_have_persistent_rings(body):
    material = getattr(body, "material", "rock")
    mass = float(getattr(body, "mass", 0.0))
    name = getattr(body, "name", "").lower()

    if material in ("plasma", "blackhole"):
        return False

    # Estrelas, buracos negros, fragmentos e planetas rochosos pequenos não ganham anel estável automático.
    if mass < 5.0e4:
        return False

    # Gigantes gasosos/gelados podem sustentar anéis.
    if material == "gas" or mass >= 5.0e4:
        return True

    return False


def orbital_speed(gravitational_constant, body, distance):
    return math.sqrt(max(gravitational_constant * float(body.mass) / max(distance, 1.0), 0.0))


def is_orbital_debris(body, fragment, gravitational_constant):
    dx = fragment.pos.x - body.pos.x
    dy = fragment.pos.y - body.pos.y
    r = math.sqrt(dx * dx + dy * dy)

    if r <= body.radius * 1.35:
        return False

    # Região simples para anéis: fora da superfície, mas não longe demais.
    if r > body.radius * 7.5:
        return False

    rvx = fragment.vel.x - body.vel.x
    rvy = fragment.vel.y - body.vel.y
    speed = math.sqrt(rvx * rvx + rvy * rvy)
    if speed <= 0:
        return False

    # Tangencialidade: v radial baixa, v tangencial dominante.
    radial_v = abs((rvx * dx + rvy * dy) / max(r, 1e-9))
    tangential_v = math.sqrt(max(0.0, speed * speed - radial_v * radial_v))

    expected = orbital_speed(gravitational_constant, body, r)

    if expected <= 0:
        return False

    speed_ratio = tangential_v / expected

    return (
        tangential_v > radial_v * 1.35
        and 0.35 <= speed_ratio <= 2.40
    )


def should_form_ring(body, fragments, gravitational_constant):
    if not can_body_have_persistent_rings(body):
        return False

    local = [f for f in fragments if is_orbital_debris(body, f, gravitational_constant)]
    if len(local) < 5:
        return False

    local_mass = sum(float(getattr(f, "mass", 0.0)) for f in local)
    if local_mass < body.mass * 0.0008:
        return False

    return True
