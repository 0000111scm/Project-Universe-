# physics_core/ecs.py
"""ECS mínimo.

Entidade = ID inteiro.
Componentes físicos ficam em arrays no PhysicsState.
Nada de objeto por corpo no core.
"""

class EntityManager:
    def __init__(self):
        self._next_id = 1
        self.alive = set()

    def create(self):
        eid = self._next_id
        self._next_id += 1
        self.alive.add(eid)
        return eid

    def destroy(self, eid):
        self.alive.discard(eid)

    def is_alive(self, eid):
        return eid in self.alive
