# physics/angular_momentum.py

import math


def clamp(value, low, high):
    return max(low, min(high, value))


def moment_of_inertia_sphere(mass, radius):
    """Momento de inércia aproximado: esfera sólida I = 2/5 M R²."""
    return 0.4 * max(mass, 0.0) * max(radius, 1e-6) ** 2


def orbital_angular_momentum_2d(mass, rel_pos, rel_vel):
    """Momento angular escalar em 2D: Lz = m * (r x v)."""
    return mass * (rel_pos.x * rel_vel.y - rel_pos.y * rel_vel.x)


def merged_angular_velocity(body_a, body_b, merged_pos, merged_vel, merged_mass, merged_radius):
    """Conserva momento angular aproximado ao fundir dois corpos."""
    ia = moment_of_inertia_sphere(body_a.mass, body_a.radius)
    ib = moment_of_inertia_sphere(body_b.mass, body_b.radius)

    spin_l = ia * getattr(body_a, "angular_velocity", 0.0) + ib * getattr(body_b, "angular_velocity", 0.0)

    rel_a = body_a.pos - merged_pos
    rel_b = body_b.pos - merged_pos
    vel_a = body_a.vel - merged_vel
    vel_b = body_b.vel - merged_vel

    orbital_l = (
        orbital_angular_momentum_2d(body_a.mass, rel_a, vel_a) +
        orbital_angular_momentum_2d(body_b.mass, rel_b, vel_b)
    )

    i_new = moment_of_inertia_sphere(merged_mass, merged_radius)
    omega = (spin_l + orbital_l) / max(i_new, 1e-9)

    # Limite para não virar beyblade numérica.
    return clamp(omega, -12.0, 12.0)


def spin_kick_from_impact(target, projectile, impact, sign=1.0):
    """Rotação induzida por impacto tangencial.

    Quanto maior a velocidade tangencial e a massa do projétil, maior o torque.
    Impacto frontal quase não gira.
    """
    target_i = moment_of_inertia_sphere(target.mass, target.radius)
    lever = max(target.radius, 1.0)
    tangential_v = max(getattr(impact, "tangential_velocity", 0.0), 0.0)
    projectile_mass = max(getattr(projectile, "mass", 0.0), 0.0)

    angular_impulse = projectile_mass * tangential_v * lever
    delta_omega = angular_impulse / max(target_i, 1e-9)
    return clamp(sign * delta_omega, -8.0, 8.0)


def directional_ejecta_vector(source, collider, impact):
    """Direção preferencial dos detritos: normal de escape + cauda tangencial."""
    normal = source.pos - collider.pos
    if normal.length_squared() == 0:
        normal.update(1.0, 0.0)
    normal = normal.normalize()

    rel = source.vel - collider.vel
    if rel.length_squared() == 0:
        return normal

    tangent = rel - normal * rel.dot(normal)
    if tangent.length_squared() > 0:
        tangent = tangent.normalize()
    else:
        tangent = normal.rotate(90)

    graze = clamp(getattr(impact, "tangential_velocity", 0.0) / max(getattr(impact, "relative_velocity", 1e-9), 1e-9), 0.0, 1.0)
    direction = normal * (1.0 - 0.55 * graze) + tangent * (0.70 * graze)
    if direction.length_squared() == 0:
        return normal
    return direction.normalize()
