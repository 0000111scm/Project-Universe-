# physics_core/collision_event_queue.py
"""Stable collision event queue.

PATCH 82

Antes:
- check_collisions iterava self.bodies;
- handlers removiam/adicionavam corpos durante o loop;
- resultado: índices quebrados, cascata, detrito absurdo, travamento.

Agora:
1. coleta pares em snapshot;
2. bloqueia corpos duplicados;
3. resolve eventos em orçamento fixo;
4. ignora fragmento-fragmento e eventos recém-criados.
"""

from dataclasses import dataclass


@dataclass
class CollisionPairEvent:
    a: object
    b: object
    distance: float
    priority: float


def collect_collision_events(bodies, is_star_like_func, max_events=8):
    snapshot = list(bodies)
    events = []

    n = len(snapshot)
    for i in range(n):
        a = snapshot[i]
        if getattr(a, "collision_cooldown", 0.0) > 0 and not is_star_like_func(a):
            continue

        for j in range(i + 1, n):
            b = snapshot[j]

            if getattr(a, "is_fragment", False) and getattr(b, "is_fragment", False):
                continue

            # Fragmentos não disparam colisão pesada com planetas neste estágio.
            if getattr(a, "is_fragment", False) or getattr(b, "is_fragment", False):
                if not (is_star_like_func(a) or is_star_like_func(b)):
                    continue

            if getattr(b, "collision_cooldown", 0.0) > 0 and not is_star_like_func(b):
                continue

            delta = a.pos - b.pos
            dist = delta.length()
            contact = a.radius + b.radius

            if dist >= contact:
                continue

            overlap = max(0.0, contact - dist)
            star_bonus = 10.0 if (is_star_like_func(a) or is_star_like_func(b)) else 0.0
            priority = overlap + star_bonus

            events.append(CollisionPairEvent(a=a, b=b, distance=dist, priority=priority))

    events.sort(key=lambda e: e.priority, reverse=True)

    locked = set()
    selected = []
    for ev in events:
        if id(ev.a) in locked or id(ev.b) in locked:
            continue
        selected.append(ev)
        locked.add(id(ev.a))
        locked.add(id(ev.b))
        if len(selected) >= max_events:
            break

    return selected
