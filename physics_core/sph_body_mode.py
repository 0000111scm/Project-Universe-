# physics_core/sph_body_mode.py
"""SPH Body Mode — safe scaffold.

PATCH 82

Objetivo real:
um corpo pode ser marcado como "modo SPH ativo", mas o modo pesado não assume o
controle sem gate de segurança. Isso evita o inferno dos patches anteriores.

Feynman:
- Body rígido é barato, mas falso em impacto forte.
- SPH é mais real, mas caro.
- Então o corpo entra em "pending_sph" primeiro.
- Só vira SPH ativo quando o evento está isolado e dentro do orçamento.
"""

from dataclasses import dataclass


@dataclass
class SPHBodyMode:
    active: bool = False
    pending: bool = False
    reason: str = ""
    age: float = 0.0
    particle_budget: int = 0
    stability_score: float = 1.0


def request_sph_mode(body, reason, severity, particle_budget=128):
    mode = getattr(body, "sph_mode", None)
    if mode is None:
        mode = SPHBodyMode()
        body.sph_mode = mode

    mode.pending = True
    mode.reason = str(reason)
    mode.particle_budget = int(max(32, min(particle_budget, 256)))
    mode.stability_score = max(0.0, min(1.0, 1.0 - float(severity) * 0.15))
    return mode


def can_activate_sph_mode(sim, body):
    cfg = getattr(sim, "collision_safety", None)
    if cfg is None:
        return False
    if not getattr(cfg, "enable_heavy_sph_replacement", False):
        return False
    if len(getattr(sim, "bodies", [])) > 20:
        return False
    if getattr(body, "is_fragment", False):
        return False

    mode = getattr(body, "sph_mode", None)
    if mode is None or not mode.pending:
        return False

    return True


def update_sph_body_modes(sim, dt):
    """Atualiza flags sem ativar simulação pesada por padrão."""
    for body in getattr(sim, "bodies", []):
        mode = getattr(body, "sph_mode", None)
        if mode is None:
            continue
        mode.age += float(dt)

        if mode.pending and can_activate_sph_mode(sim, body):
            mode.active = True
            mode.pending = False

        # Se ficou pendente tempo demais, volta para rígido seguro.
        if mode.pending and mode.age > 4.0:
            mode.pending = False
            mode.active = False
