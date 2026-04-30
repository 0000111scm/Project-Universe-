# physics_core/state.py
"""PhysicsState SoA FP64.

SoA = Structure of Arrays:
- pos_x[] pos_y[] pos_z[]
- vel_x[] vel_y[] vel_z[]
- mass[]
- radius[]
- temperature[]

Isso é o oposto de OOP clássico:
em vez de cada corpo carregar tudo dentro de um objeto,
cada propriedade vive em um bloco contíguo de memória.
"""

from dataclasses import dataclass
try:
    import numpy as np
except Exception:
    np = None


@dataclass
class PhysicsState:
    entity: object
    pos: object
    vel: object
    acc: object
    mass: object
    radius: object
    temperature: object
    material_id: object
    active: object
    entity_to_index: dict
    index_to_entity: list

    @property
    def n(self):
        return len(self.index_to_entity)


MATERIAL_IDS = {
    "rock": 1,
    "metal": 2,
    "ice": 3,
    "gas": 4,
    "plasma": 5,
    "blackhole": 6,
}


def require_numpy():
    if np is None:
        raise RuntimeError("NumPy é necessário para physics_core.")


def create_state(capacity=0):
    require_numpy()
    cap = max(int(capacity), 0)
    return PhysicsState(
        entity=np.zeros(cap, dtype=np.int64),
        pos=np.zeros((cap, 3), dtype=np.float64),
        vel=np.zeros((cap, 3), dtype=np.float64),
        acc=np.zeros((cap, 3), dtype=np.float64),
        mass=np.zeros(cap, dtype=np.float64),
        radius=np.zeros(cap, dtype=np.float64),
        temperature=np.zeros(cap, dtype=np.float64),
        material_id=np.zeros(cap, dtype=np.int32),
        active=np.zeros(cap, dtype=np.bool_),
        entity_to_index={},
        index_to_entity=[],
    )


def _grow(state, min_capacity):
    old = state.entity.shape[0]
    if old >= min_capacity:
        return state

    new_cap = max(min_capacity, max(8, old * 2))

    def grow_array(arr, shape_tail=()):
        new = np.zeros((new_cap,) + shape_tail, dtype=arr.dtype)
        if old:
            new[:old] = arr
        return new

    state.entity = grow_array(state.entity)
    state.pos = grow_array(state.pos, (3,))
    state.vel = grow_array(state.vel, (3,))
    state.acc = grow_array(state.acc, (3,))
    state.mass = grow_array(state.mass)
    state.radius = grow_array(state.radius)
    state.temperature = grow_array(state.temperature)
    state.material_id = grow_array(state.material_id)
    state.active = grow_array(state.active)
    return state


def add_entity(state, eid, pos, vel, mass, radius, temperature=300.0, material="rock"):
    require_numpy()
    idx = len(state.index_to_entity)
    _grow(state, idx + 1)

    state.entity[idx] = int(eid)
    state.pos[idx, :] = pos
    state.vel[idx, :] = vel
    state.acc[idx, :] = 0.0
    state.mass[idx] = max(float(mass), 1.0e-12)
    state.radius[idx] = max(float(radius), 1.0e-9)
    state.temperature[idx] = float(temperature)
    state.material_id[idx] = MATERIAL_IDS.get(str(material), 1)
    state.active[idx] = True

    state.entity_to_index[int(eid)] = idx
    state.index_to_entity.append(int(eid))
    return idx


def compact_state(state):
    """Remove entidades inativas mantendo arrays contíguos."""
    require_numpy()
    if state.n == 0:
        return state

    mask = state.active[:state.n]
    keep = np.nonzero(mask)[0]

    state.entity[:len(keep)] = state.entity[keep]
    state.pos[:len(keep)] = state.pos[keep]
    state.vel[:len(keep)] = state.vel[keep]
    state.acc[:len(keep)] = state.acc[keep]
    state.mass[:len(keep)] = state.mass[keep]
    state.radius[:len(keep)] = state.radius[keep]
    state.temperature[:len(keep)] = state.temperature[keep]
    state.material_id[:len(keep)] = state.material_id[keep]
    state.active[:len(keep)] = True
    state.active[len(keep):state.n] = False

    state.index_to_entity = [int(x) for x in state.entity[:len(keep)]]
    state.entity_to_index = {eid: i for i, eid in enumerate(state.index_to_entity)}
    return state


def total_mass(state):
    if state.n == 0:
        return 0.0
    return float(state.mass[:state.n][state.active[:state.n]].sum())


def center_of_mass(state):
    require_numpy()
    if state.n == 0:
        return np.zeros(3, dtype=np.float64)
    mask = state.active[:state.n]
    m = state.mass[:state.n][mask]
    if m.size == 0 or m.sum() <= 0:
        return np.zeros(3, dtype=np.float64)
    p = state.pos[:state.n][mask]
    return (p * m[:, None]).sum(axis=0) / m.sum()
