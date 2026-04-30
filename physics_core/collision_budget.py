# physics_core/collision_budget.py
"""Collision budget / multi-impact guard.

Corrige travamento quando vários corpos colidem no mesmo frame.

Feynman:
se A, B e C se chocam no mesmo instante, não podemos rodar SPH pesado para:
A-B, A-C, B-C, e ainda processar fragmentos recém-criados no mesmo frame.

A solução profissional:
- orçamento de colisões pesadas por frame;
- corpo processado entra em bloqueio;
- corpos removidos não voltam ao loop;
- fragmentos criados no frame não entram em SPH pesado no mesmo frame.
"""

class CollisionBudget:
    def __init__(self, max_heavy_impacts=2, max_fragment_spawns=48):
        self.max_heavy_impacts = int(max_heavy_impacts)
        self.max_fragment_spawns = int(max_fragment_spawns)
        self.heavy_impacts = 0
        self.fragment_spawns = 0
        self.locked_ids = set()
        self.removed_ids = set()

    def reset(self):
        self.heavy_impacts = 0
        self.fragment_spawns = 0
        self.locked_ids.clear()
        self.removed_ids.clear()

    def can_process_pair(self, a, b):
        if id(a) in self.removed_ids or id(b) in self.removed_ids:
            return False
        if id(a) in self.locked_ids or id(b) in self.locked_ids:
            return False
        return True

    def can_run_heavy(self, a, b):
        if not self.can_process_pair(a, b):
            return False
        return self.heavy_impacts < self.max_heavy_impacts

    def consume_heavy(self, a, b):
        self.heavy_impacts += 1
        self.locked_ids.add(id(a))
        self.locked_ids.add(id(b))

    def mark_removed(self, body):
        self.removed_ids.add(id(body))
        self.locked_ids.add(id(body))

    def can_spawn_fragments(self, count):
        return self.fragment_spawns + int(count) <= self.max_fragment_spawns

    def consume_fragments(self, count):
        self.fragment_spawns += int(count)
