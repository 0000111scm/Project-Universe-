# physics_core/gravity.py
"""Gravidade N-body vetorizada FP64."""

try:
    import numpy as np
except Exception:
    np = None


def compute_nbody_acceleration(state, gravitational_constant=0.6006, softening=25.0):
    if np is None:
        raise RuntimeError("NumPy é necessário para gravity.py")

    n = state.n
    acc = np.zeros((state.pos.shape[0], 3), dtype=np.float64)
    if n == 0:
        return acc

    active = state.active[:n]
    pos = state.pos[:n]
    mass = state.mass[:n]

    delta = pos[None, :, :] - pos[:, None, :]
    dist2 = (delta * delta).sum(axis=2) + float(softening)
    np.fill_diagonal(dist2, np.inf)

    inv_dist = 1.0 / np.sqrt(dist2)
    inv_dist3 = inv_dist / dist2

    factor = float(gravitational_constant) * mass[None, :] * inv_dist3
    a = (delta * factor[:, :, None]).sum(axis=1)

    acc[:n] = a
    acc[:n][~active] = 0.0
    return acc


def total_energy(state, gravitational_constant=0.6006, softening=25.0):
    if np is None:
        raise RuntimeError("NumPy é necessário para gravity.py")

    n = state.n
    if n == 0:
        return 0.0

    active = state.active[:n]
    pos = state.pos[:n][active]
    vel = state.vel[:n][active]
    mass = state.mass[:n][active]

    kinetic = 0.5 * (mass * (vel * vel).sum(axis=1)).sum()

    potential = 0.0
    for i in range(len(mass)):
        d = pos[i+1:] - pos[i]
        if d.size == 0:
            continue
        dist = np.sqrt((d * d).sum(axis=1) + float(softening))
        potential -= (float(gravitational_constant) * mass[i] * mass[i+1:] / dist).sum()

    return float(kinetic + potential)
