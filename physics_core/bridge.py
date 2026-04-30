# physics_core/bridge.py
"""Ponte temporária Body <-> PhysicsState.

O render ainda usa Body.
O core novo usa ECS/arrays.
Esta ponte permite migrar por partes sem quebrar o projeto.
"""

from physics_core.state import create_state, add_entity


def body_material(body):
    return getattr(body, "material", "rock")


def build_state_from_bodies(bodies):
    state = create_state(len(bodies))
    body_to_entity = {}
    entity_to_body = {}

    for i, b in enumerate(bodies):
        eid = i + 1
        body_to_entity[id(b)] = eid
        entity_to_body[eid] = b

        add_entity(
            state,
            eid=eid,
            pos=(float(b.pos.x), float(b.pos.y), 0.0),
            vel=(float(b.vel.x), float(b.vel.y), 0.0),
            mass=float(b.mass),
            radius=float(b.radius),
            temperature=float(getattr(b, "temperature", 300.0)),
            material=body_material(b),
        )

    return state, body_to_entity, entity_to_body


def sync_state_to_bodies(state, entity_to_body):
    for idx, eid in enumerate(state.index_to_entity):
        b = entity_to_body.get(eid)
        if b is None:
            continue
        b.pos.x = float(state.pos[idx, 0])
        b.pos.y = float(state.pos[idx, 1])
        b.vel.x = float(state.vel[idx, 0])
        b.vel.y = float(state.vel[idx, 1])
        b.acc.x = float(state.acc[idx, 0])
        b.acc.y = float(state.acc[idx, 1])
        b.mass = float(state.mass[idx])
        b.radius = float(state.radius[idx])
        b.temperature = float(state.temperature[idx])
