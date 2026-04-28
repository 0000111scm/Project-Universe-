"""Predicao orbital N-body real para visualizacao.

Nao usa orbita Kepleriana fake. Clona estado atual, integra todas as gravidades
mutuas e retorna pontos futuros por corpo. Otimizado para ser chamado com cache.
"""
import math
import pygame

G = 200

def _clone_state(bodies, max_bodies=80):
    # Fragmentos pequenos custam muito e quase nao ajudam na predicao visual.
    important = [b for b in bodies if not getattr(b, "is_fragment", False) or getattr(b, "mass", 0) >= 50]
    important = sorted(important, key=lambda b: getattr(b, "mass", 0), reverse=True)[:max_bodies]
    state = []
    for b in important:
        state.append({
            "src": b,
            "pos": pygame.Vector2(b.pos),
            "vel": pygame.Vector2(b.vel),
            "mass": float(b.mass),
        })
    return state


def _accelerations(state):
    acc = [pygame.Vector2(0, 0) for _ in state]
    n = len(state)
    for i in range(n):
        a = state[i]
        for j in range(i + 1, n):
            b = state[j]
            d = b["pos"] - a["pos"]
            # softening proporcional evita singularidade visual em passagens proximas
            ds2 = d.length_squared() + 64.0
            ds = math.sqrt(ds2)
            if ds <= 0:
                continue
            direction = d / ds
            acc_i = direction * (G * b["mass"] / ds2)
            acc_j = -direction * (G * a["mass"] / ds2)
            acc[i] += acc_i
            acc[j] += acc_j
    return acc


def predict_nbody_paths(bodies, steps=180, dt=0.018, stride=3, max_bodies=80):
    state = _clone_state(bodies, max_bodies=max_bodies)
    if len(state) < 2:
        return {}
    paths = {id(s["src"]): [] for s in state}

    # Leapfrog/Velocity-Verlet: mais estavel que Euler simples para orbita.
    acc = _accelerations(state)
    for _ in range(steps):
        for i, s in enumerate(state):
            s["vel"] += acc[i] * (dt * 0.5)
            s["pos"] += s["vel"] * dt
        acc = _accelerations(state)
        for i, s in enumerate(state):
            s["vel"] += acc[i] * (dt * 0.5)
        if _ % stride == 0:
            for s in state:
                paths[id(s["src"])].append(pygame.Vector2(s["pos"]))
    return paths


def make_cache_signature(bodies, quality_bucket=1):
    sig = [len(bodies), quality_bucket]
    for b in sorted(bodies, key=lambda x: id(x))[:90]:
        sig.extend((
            id(b),
            int(b.pos.x // 12), int(b.pos.y // 12),
            int(b.vel.x // 8), int(b.vel.y // 8),
            int(float(b.mass) // 100),
        ))
    return tuple(sig)
