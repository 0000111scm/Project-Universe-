# physics_core/collision_safety.py
"""Collision Safety Layer.

PATCH 80 — Physics Regression Gate

Primeiro estabilidade, depois fidelidade:
- SPH pesado desligado por padrão
- limita cascata de colisões
- limita fragmentos
- evita colisão pesada de fragmentos
"""

def clamp(v, a, b):
    return max(a, min(b, v))


class CollisionSafetyConfig:
    def __init__(self):
        self.enable_heavy_sph_replacement = False
        self.enable_planetary_pipeline = True
        self.max_heavy_collisions_per_frame = 1
        self.max_total_collision_events_per_frame = 6
        self.max_fragments_per_collision = 4
        self.max_fragments_per_frame = 18
        self.max_rock_fragment_radius_factor = 0.16
        self.max_visible_ejecta_fraction = 0.035
        self.min_collision_cooldown_after_heavy = 1.2
        self.skip_fragments_as_collision_sources = True


def should_allow_heavy_sph(sim, a, b, severity):
    cfg = getattr(sim, "collision_safety", None)
    if cfg is None:
        return False
    if not cfg.enable_heavy_sph_replacement:
        return False
    if len(getattr(sim, "bodies", [])) > 24:
        return False
    if severity < 0.65:
        return False
    if getattr(a, "is_fragment", False) or getattr(b, "is_fragment", False):
        return False
    return True


def bounded_collision_events(sim):
    cfg = getattr(sim, "collision_safety", None)
    return int(getattr(cfg, "max_total_collision_events_per_frame", 6))


def bounded_fragments_for_collision(sim, requested):
    cfg = getattr(sim, "collision_safety", None)
    limit = int(getattr(cfg, "max_fragments_per_collision", 4))
    return int(clamp(int(requested), 1, limit))
