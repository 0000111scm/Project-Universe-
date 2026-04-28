"""Presets científicos para montar cenários comuns do Project Universe."""
import math
import random
import pygame
from body import Body
from config import G, M_SOL, SIM_W, HEIGHT


def orbital_velocity(mass, distance):
    return math.sqrt(G * mass / max(distance, 1.0))


def _body(x, y, vx, vy, mass, radius, color, name, atmosphere=None, water=None):
    b = Body(x, y, vx, vy, mass, radius, color, name)
    b.base_color = color
    if atmosphere is not None:
        b.atmosphere = atmosphere
    if water is not None:
        b.water = water
    b.temperature = getattr(b, "temperature", 288.0)
    b.collision_cooldown = 0.8
    return b


def _reset(sim):
    sim.bodies.clear()
    sim.collision_events.clear()


def preset_sistema_solar(sim):
    _reset(sim)
    cx, cy = SIM_W // 2, HEIGHT // 2
    sun = _body(cx, cy, 0, 0, M_SOL, 30, (255, 210, 50), "Sol", 0, 0)
    sim.add_body(sun)
    data = [
        (58,  3e1, 2,  (180,170,160), "Mercúrio", 0.0, 0.0),
        (108, 8e2, 7,  (220,190,100), "Vênus",    9.0, 0.0),
        (150, 1e3, 8,  (50,120,220),  "Terra",    1.0, 0.71),
        (225, 1e2, 6,  (200,80,50),   "Marte",    0.006, 0.02),
        (420, 3e5, 16, (200,160,110), "Júpiter",  0.0, 0.0),
        (610, 9e4, 14, (210,190,130), "Saturno",  0.0, 0.0),
    ]
    for dist, mass, radius, color, name, atm, water in data:
        v = orbital_velocity(M_SOL, dist)
        sim.add_body(_body(cx + dist, cy, 0, v, mass, radius, color, name, atm, water))


def preset_binaria(sim):
    _reset(sim)
    cx, cy = SIM_W // 2, HEIGHT // 2
    m1, m2 = 1.0e6, 7.0e5
    d = 140
    v = orbital_velocity(m1 + m2, d) * 0.48
    sim.add_body(_body(cx - d*0.45, cy, 0, -v*m2/(m1+m2)*2.0, m1, 30, (255,210,70), "Estrela A", 0, 0))
    sim.add_body(_body(cx + d*0.55, cy, 0,  v*m1/(m1+m2)*2.0, m2, 24, (255,150,80), "Estrela B", 0, 0))
    # planeta circumbinário externo
    dist = 420
    sim.add_body(_body(cx + dist, cy, 0, orbital_velocity(m1+m2, dist), 900, 8, (70,130,230), "Mundo circumbinário", 0.9, 0.5))


def preset_colisao_lua_terra(sim):
    _reset(sim)
    cx, cy = SIM_W // 2, HEIGHT // 2
    sim.add_body(_body(cx, cy, 0, 0, M_SOL, 30, (255,210,50), "Sol", 0, 0))
    dist = 190
    earth_v = orbital_velocity(M_SOL, dist)
    earth = _body(cx + dist, cy, 0, earth_v, 1e3, 8, (50,120,220), "Proto-Terra", 1.0, 0.7)
    sim.add_body(earth)
    # Impactador estilo Theia: aproxima com velocidade oblíqua moderada.
    sim.add_body(_body(cx + dist + 70, cy - 46, -95, earth_v + 55, 160, 5, (190,120,75), "Theia", 0.15, 0.05))


def preset_asteroides(sim):
    _reset(sim)
    cx, cy = SIM_W // 2, HEIGHT // 2
    sim.add_body(_body(cx, cy, 0, 0, M_SOL, 30, (255,210,50), "Sol", 0, 0))
    rng = random.Random(7)
    for i in range(80):
        dist = rng.uniform(230, 560)
        ang = rng.uniform(0, math.pi * 2)
        pos = pygame.Vector2(cx + math.cos(ang)*dist, cy + math.sin(ang)*dist)
        speed = orbital_velocity(M_SOL, dist) * rng.uniform(0.88, 1.12)
        vel = pygame.Vector2(-math.sin(ang)*speed, math.cos(ang)*speed)
        mass = rng.uniform(1.0, 18.0)
        radius = max(1, int(rng.uniform(1.0, 2.5)))
        color = rng.choice([(130,120,100), (150,140,120), (110,105,95)])
        b = _body(pos.x, pos.y, vel.x, vel.y, mass, radius, color, f"Asteroide {i+1}", 0, 0)
        b.show_label = False
        sim.add_body(b)


def apply_preset(sim, preset_name):
    if preset_name == "sistema_solar":
        preset_sistema_solar(sim)
    elif preset_name == "binaria":
        preset_binaria(sim)
    elif preset_name == "colisao_lua_terra":
        preset_colisao_lua_terra(sim)
    elif preset_name == "asteroides":
        preset_asteroides(sim)
    else:
        return False
    return True
