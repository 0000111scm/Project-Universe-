"""Base inicial para SPH.

Ainda nao substitui o sistema de colisao principal. Serve como fundacao limpa:
- particulas de material
- kernel de suavizacao
- estimativa de densidade/pressao
O proximo patch pode ligar isso nas colisoes planetarias reais.
"""
from dataclasses import dataclass
import math
import pygame

@dataclass
class SPHParticle:
    pos: pygame.Vector2
    vel: pygame.Vector2
    mass: float
    density: float = 0.0
    pressure: float = 0.0
    temperature: float = 300.0
    material: str = "silicate"


def poly6_kernel(r: float, h: float) -> float:
    if r < 0 or r > h or h <= 0:
        return 0.0
    return 315.0 / (64.0 * math.pi * h**9) * (h*h - r*r) ** 3


def spiky_gradient_mag(r: float, h: float) -> float:
    if r <= 0 or r > h or h <= 0:
        return 0.0
    return -45.0 / (math.pi * h**6) * (h - r) ** 2


def estimate_density(particles, h=12.0):
    for p in particles:
        rho = 0.0
        for q in particles:
            rho += q.mass * poly6_kernel((p.pos - q.pos).length(), h)
        p.density = max(rho, 1e-6)
    return particles
