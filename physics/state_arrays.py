# physics/state_arrays.py
"""Data-oriented state arrays para o core físico.

Objetivo:
- manter Body para UI/render por enquanto;
- espelhar propriedades físicas em arrays NumPy fp64;
- calcular N-body com arrays contíguos;
- preparar Barnes-Hut/GPU/3D sem quebrar o projeto atual.

Este é o primeiro passo real para abandonar OOP no core.
"""

from dataclasses import dataclass

try:
    import numpy as np
except Exception:
    np = None


@dataclass
class PhysicsStateArrays:
    pos: object
    vel: object
    acc: object
    mass: object
    radius: object
    alive: object
    index_to_body: list

    @property
    def n(self):
        return len(self.index_to_body)


def build_state_arrays(bodies):
    if np is None:
        return None

    n = len(bodies)
    pos = np.zeros((n, 2), dtype=np.float64)
    vel = np.zeros((n, 2), dtype=np.float64)
    acc = np.zeros((n, 2), dtype=np.float64)
    mass = np.zeros(n, dtype=np.float64)
    radius = np.zeros(n, dtype=np.float64)
    alive = np.ones(n, dtype=np.bool_)

    for i, b in enumerate(bodies):
        pos[i, 0] = float(b.pos.x)
        pos[i, 1] = float(b.pos.y)
        vel[i, 0] = float(b.vel.x)
        vel[i, 1] = float(b.vel.y)
        acc[i, 0] = float(getattr(b, "acc").x)
        acc[i, 1] = float(getattr(b, "acc").y)
        mass[i] = max(float(b.mass), 1.0e-12)
        radius[i] = max(float(b.radius), 1.0e-9)

    return PhysicsStateArrays(
        pos=pos,
        vel=vel,
        acc=acc,
        mass=mass,
        radius=radius,
        alive=alive,
        index_to_body=list(bodies),
    )


def sync_arrays_to_bodies(state):
    if state is None:
        return

    for i, b in enumerate(state.index_to_body):
        b.pos.x = float(state.pos[i, 0])
        b.pos.y = float(state.pos[i, 1])
        b.vel.x = float(state.vel[i, 0])
        b.vel.y = float(state.vel[i, 1])
        b.acc.x = float(state.acc[i, 0])
        b.acc.y = float(state.acc[i, 1])


def compute_gravity_acceleration(state, gravitational_constant, softening=25.0):
    """N-body vetorizado em fp64.

    Retorna aceleração Nx2.
    Convenção:
    dx[i,j] = pos[j] - pos[i]
    a[i] = sum_j G*m[j]*dx/r^3
    """
    if np is None or state is None or state.n == 0:
        return None

    pos = state.pos
    mass = state.mass

    delta = pos[None, :, :] - pos[:, None, :]          # i -> j
    dist2 = (delta * delta).sum(axis=2) + float(softening)
    np.fill_diagonal(dist2, np.inf)

    inv_dist = 1.0 / np.sqrt(dist2)
    inv_dist3 = inv_dist / dist2

    factor = float(gravitational_constant) * mass[None, :] * inv_dist3
    acc = (delta * factor[:, :, None]).sum(axis=1)
    return acc.astype(np.float64, copy=False)


def floating_origin_shift(state, camera_world_pos):
    """Prepara origem flutuante.

    Por enquanto não alteramos Body/render automaticamente.
    A função existe para o próximo passo: simular em coordenadas locais à câmera.
    """
    if np is None or state is None:
        return None
    origin = np.array([float(camera_world_pos[0]), float(camera_world_pos[1])], dtype=np.float64)
    return state.pos - origin[None, :]
