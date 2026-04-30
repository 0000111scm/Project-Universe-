# physics_core/system.py
"""Sistema físico ECS usado como backend do Simulation.

Este arquivo começa a tirar a física orbital do modelo Body/OOP.
Fluxo:
1. Body -> PhysicsState fp64
2. Leapfrog no PhysicsState
3. PhysicsState -> Body

Ainda mantém colisões no Simulation antigo por enquanto.
"""

from physics_core.bridge import build_state_from_bodies, sync_state_to_bodies
from physics_core.gravity import compute_nbody_acceleration, total_energy
from physics_core.barnes_hut_2d import compute_barnes_hut_acceleration
from physics_core.octree_3d import compute_octree_acceleration
from physics_core.integrators import leapfrog_step


class PhysicsCoreSystem:
    def __init__(self, gravitational_constant=0.6006):
        self.G = gravitational_constant
        self.last_energy = None
        self.energy_drift = 0.0
        self.enabled = True
        self.use_barnes_hut = True
        self.barnes_hut_threshold = 48
        self.theta = 0.65
        self.last_backend = "none"
        self.use_octree_3d = True
        self.octree_threshold = 96

    def step_bodies(self, bodies, dt):
        if not self.enabled or not bodies:
            return False

        state, _body_to_entity, entity_to_body = build_state_from_bodies(bodies)

        use_octree = self.use_octree_3d and state.n >= self.octree_threshold
        use_bh = (not use_octree) and self.use_barnes_hut and state.n >= self.barnes_hut_threshold

        def acceleration(s):
            if use_octree:
                self.last_backend = "octree_3d"
                return compute_octree_acceleration(
                    s,
                    gravitational_constant=self.G,
                    theta=self.theta,
                    softening=25.0,
                )
            if use_bh:
                self.last_backend = "barnes_hut_2d"
                return compute_barnes_hut_acceleration(
                    s,
                    gravitational_constant=self.G,
                    theta=self.theta,
                    softening=25.0,
                )
            self.last_backend = "direct_nbody"
            return compute_nbody_acceleration(s, self.G, softening=25.0)

        e0 = total_energy(state, self.G)
        leapfrog_step(state, dt, acceleration)
        e1 = total_energy(state, self.G)

        self.last_energy = e1
        if abs(e0) > 1.0e-9:
            self.energy_drift = abs(e1 - e0) / abs(e0)
        else:
            self.energy_drift = 0.0

        sync_state_to_bodies(state, entity_to_body)
        return True
