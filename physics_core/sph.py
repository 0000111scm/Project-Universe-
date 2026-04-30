# physics_core/sph.py
"""SPH Foundation — partículas volumétricas reais.

Feynman:
- cada partícula é um pedacinho de matéria;
- densidade = quantas partículas estão perto;
- pressão = densidade alta empurra para fora;
- viscosidade = material resiste a deformar;
- impacto forte deixa de ser "fundiu" e vira deformação + calor + ejeção.

Este ainda é SPH 2D e pequeno, mas é o núcleo matemático correto para evoluir.
"""

from dataclasses import dataclass
from physics_core.thermodynamics import classify_phase

try:
    import numpy as np
except Exception:
    np = None


def require_numpy():
    if np is None:
        raise RuntimeError("NumPy é necessário para SPH.")


@dataclass
class SPHMaterial:
    rest_density: float
    stiffness: float
    viscosity: float
    heat_capacity: float
    melt_temperature: float
    vapor_temperature: float


MATERIALS = {
    "rock": SPHMaterial(3.3, 220.0, 4.5, 900.0, 1500.0, 3200.0),
    "metal": SPHMaterial(7.8, 350.0, 6.0, 520.0, 1800.0, 3400.0),
    "ice": SPHMaterial(0.92, 85.0, 2.0, 2100.0, 273.15, 650.0),
    "gas": SPHMaterial(0.20, 12.0, 0.35, 14000.0, 90.0, 400.0),
    "plasma": SPHMaterial(0.05, 4.0, 0.08, 22000.0, 3000.0, 12000.0),
}


class SPHParticleSet:
    def __init__(self, capacity=0):
        require_numpy()
        cap = max(int(capacity), 0)
        self.pos = np.zeros((cap, 2), dtype=np.float64)
        self.vel = np.zeros((cap, 2), dtype=np.float64)
        self.force = np.zeros((cap, 2), dtype=np.float64)
        self.mass = np.zeros(cap, dtype=np.float64)
        self.density = np.zeros(cap, dtype=np.float64)
        self.pressure = np.zeros(cap, dtype=np.float64)
        self.temperature = np.zeros(cap, dtype=np.float64)
        self.material_id = np.zeros(cap, dtype=np.int32)
        self.phase_id = np.zeros(cap, dtype=np.int32)  # 0 sólido, 1 líquido/magma, 2 vapor, 3 plasma
        self.owner = np.zeros(cap, dtype=np.int64)
        self.active = np.zeros(cap, dtype=np.bool_)
        self.count = 0

    def ensure_capacity(self, n):
        require_numpy()
        old = self.pos.shape[0]
        if old >= n:
            return
        new_cap = max(n, max(64, old * 2))

        def grow(arr, shape_tail=()):
            new = np.zeros((new_cap,) + shape_tail, dtype=arr.dtype)
            if old:
                new[:old] = arr
            return new

        self.pos = grow(self.pos, (2,))
        self.vel = grow(self.vel, (2,))
        self.force = grow(self.force, (2,))
        self.mass = grow(self.mass)
        self.density = grow(self.density)
        self.pressure = grow(self.pressure)
        self.temperature = grow(self.temperature)
        self.material_id = grow(self.material_id)
        self.phase_id = grow(self.phase_id)
        self.owner = grow(self.owner)
        self.active = grow(self.active)

    def add_particles(self, positions, velocities, masses, temperatures, material_id, owner):
        require_numpy()
        n = len(positions)
        start = self.count
        end = start + n
        self.ensure_capacity(end)

        self.pos[start:end] = positions
        self.vel[start:end] = velocities
        self.mass[start:end] = masses
        self.temperature[start:end] = temperatures
        self.material_id[start:end] = int(material_id)
        self.phase_id[start:end] = 0
        self.owner[start:end] = int(owner)
        self.active[start:end] = True
        self.count = end
        return slice(start, end)

    def compact(self):
        if self.count == 0:
            return
        mask = self.active[:self.count]
        keep = np.nonzero(mask)[0]
        n = len(keep)
        self.pos[:n] = self.pos[keep]
        self.vel[:n] = self.vel[keep]
        self.force[:n] = self.force[keep]
        self.mass[:n] = self.mass[keep]
        self.density[:n] = self.density[keep]
        self.pressure[:n] = self.pressure[keep]
        self.temperature[:n] = self.temperature[keep]
        self.material_id[:n] = self.material_id[keep]
        self.phase_id[:n] = self.phase_id[keep]
        self.owner[:n] = self.owner[keep]
        self.active[:n] = True
        self.active[n:self.count] = False
        self.count = n


MATERIAL_ID = {
    "rock": 1,
    "metal": 2,
    "ice": 3,
    "gas": 4,
    "plasma": 5,
}

ID_MATERIAL = {v: k for k, v in MATERIAL_ID.items()}


def material_id(name):
    return MATERIAL_ID.get(str(name), 1)


def get_material(mid):
    return MATERIALS.get(ID_MATERIAL.get(int(mid), "rock"), MATERIALS["rock"])


def poly6_kernel(r2, h):
    if r2 >= h * h:
        return 0.0
    x = h * h - r2
    # 2D normalization approximation.
    return 4.0 / (np.pi * h ** 8) * x ** 3


def spiky_grad(r_vec, r, h):
    if r <= 1e-12 or r >= h:
        return np.zeros(2, dtype=np.float64)
    c = -30.0 / (np.pi * h ** 5) * (h - r) ** 2
    return c * (r_vec / r)


def viscosity_laplacian(r, h):
    if r >= h:
        return 0.0
    return 20.0 / (3.0 * np.pi * h ** 5) * (h - r)


def compute_density_pressure(pset, h=12.0):
    require_numpy()
    n = pset.count
    if n == 0:
        return

    pos = pset.pos[:n]
    mass = pset.mass[:n]
    active = pset.active[:n]

    pset.density[:n] = 0.0
    for i in range(n):
        if not active[i]:
            continue
        rho = 0.0
        for j in range(n):
            if not active[j]:
                continue
            r = pos[i] - pos[j]
            rho += mass[j] * poly6_kernel(float(r.dot(r)), h)
        pset.density[i] = max(rho, 1e-9)

        mat = get_material(pset.material_id[i])
        pset.pressure[i] = mat.stiffness * max(0.0, pset.density[i] - mat.rest_density)


def compute_sph_forces(pset, h=12.0):
    require_numpy()
    n = pset.count
    if n == 0:
        return

    compute_density_pressure(pset, h=h)

    pset.force[:n] = 0.0
    pos = pset.pos[:n]
    vel = pset.vel[:n]
    mass = pset.mass[:n]
    rho = pset.density[:n]
    pressure = pset.pressure[:n]
    active = pset.active[:n]

    for i in range(n):
        if not active[i]:
            continue

        f_pressure = np.zeros(2, dtype=np.float64)
        f_visc = np.zeros(2, dtype=np.float64)

        mat_i = get_material(pset.material_id[i])

        for j in range(n):
            if i == j or not active[j]:
                continue

            rij = pos[i] - pos[j]
            r = float(np.sqrt(rij.dot(rij)))
            if r >= h or r <= 1e-12:
                continue

            grad = spiky_grad(rij, r, h)
            p_term = (pressure[i] + pressure[j]) / (2.0 * max(rho[j], 1e-9))
            f_pressure += -mass[j] * p_term * grad

            mat_j = get_material(pset.material_id[j])
            visc = 0.5 * (mat_i.viscosity + mat_j.viscosity)
            f_visc += visc * mass[j] * (vel[j] - vel[i]) / max(rho[j], 1e-9) * viscosity_laplacian(r, h)

        pset.force[i] = f_pressure + f_visc


def step_sph(pset, dt, h=12.0):
    require_numpy()
    n = pset.count
    if n == 0:
        return

    compute_sph_forces(pset, h=h)

    active = pset.active[:n]
    acc = np.zeros((n, 2), dtype=np.float64)
    acc[active] = pset.force[:n][active] / pset.mass[:n][active, None]

    pset.vel[:n][active] += acc[active] * float(dt)
    pset.pos[:n][active] += pset.vel[:n][active] * float(dt)

    # Resfriamento simples por radiação/ambiente.
    pset.temperature[:n][active] = np.maximum(3.0, pset.temperature[:n][active] - float(dt) * 8.0)

    # Fase por temperatura/pressão usando engine termodinâmica.
    for i in range(n):
        if not active[i]:
            continue
        mat_name = ID_MATERIAL.get(int(pset.material_id[i]), "rock")
        pset.phase_id[i] = classify_phase(
            mat_name,
            pset.temperature[i],
            pressure=pset.pressure[i],
            gravity=0.0,
        )


def sample_body_particles(body, count=48):
    """Cria nuvem SPH 2D dentro do disco do corpo.

    Usado como primeira aproximação para colisões fortes.
    """
    require_numpy()
    count = max(1, int(count))

    radius = max(float(getattr(body, "radius", 1.0)), 1.0)
    mass = max(float(getattr(body, "mass", 1.0)), 1e-9)
    temp = float(getattr(body, "temperature", 300.0))
    mat = material_id(getattr(body, "material", "rock"))

    # distribuição em espiral para preencher disco sem randômico excessivo
    pos = np.zeros((count, 2), dtype=np.float64)
    vel = np.zeros((count, 2), dtype=np.float64)
    masses = np.full(count, mass / count, dtype=np.float64)
    temps = np.full(count, temp, dtype=np.float64)

    golden = np.pi * (3.0 - np.sqrt(5.0))
    for i in range(count):
        r = radius * np.sqrt((i + 0.5) / count)
        a = i * golden
        pos[i, 0] = float(body.pos.x) + np.cos(a) * r
        pos[i, 1] = float(body.pos.y) + np.sin(a) * r
        vel[i, 0] = float(body.vel.x)
        vel[i, 1] = float(body.vel.y)

    return pos, vel, masses, temps, mat
