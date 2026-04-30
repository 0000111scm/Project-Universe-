# physics/stellar_sph.py
from dataclasses import dataclass
import math
import random

def clamp(v, a, b):
    return max(a, min(b, v))

@dataclass
class StellarSPHParticle:
    x: float
    y: float
    vx: float
    vy: float
    mass: float
    temperature: float
    smoothing_length: float
    life: float
    density: float = 0.0
    pressure: float = 0.0

class StellarSPHSystem:
    def __init__(self, max_particles=512):
        self.particles = []
        self.max_particles = max_particles

    def clear_dead(self):
        self.particles = [p for p in self.particles if p.life > 0.0 and p.mass > 0.0]

    def emit_common_envelope(self, pos, bary_vel, mass, rel_vel, radius, strength=1.0, count=None):
        if mass <= 0.0:
            return []
        count = count or int(clamp(6 + strength * 8, 6, 48))
        available = max(0, self.max_particles - len(self.particles))
        count = min(count, available)
        if count <= 0:
            return []
        rel_speed = math.hypot(rel_vel[0], rel_vel[1])
        mass_per = max(mass / count, 1e-9)
        created = []
        for i in range(count):
            ang = math.tau * i / max(count, 1) + random.uniform(-0.22, 0.22)
            dist = random.uniform(radius * 0.25, radius * 1.15)
            speed = clamp(rel_speed * random.uniform(0.035, 0.16) + strength * random.uniform(5.0, 26.0), 2.0, 210.0)
            p = StellarSPHParticle(
                x=pos[0] + math.cos(ang) * dist,
                y=pos[1] + math.sin(ang) * dist,
                vx=bary_vel[0] + math.cos(ang) * speed,
                vy=bary_vel[1] + math.sin(ang) * speed,
                mass=mass_per,
                temperature=8000.0 + strength * 4500.0,
                smoothing_length=max(3.0, radius * 0.20),
                life=random.uniform(2.8, 6.8) * clamp(0.85 + strength * 0.14, 0.85, 1.9),
            )
            self.particles.append(p)
            created.append(p)
        return created

    def step(self, dt):
        if not self.particles:
            return
        dt = max(float(dt), 0.0)
        if dt <= 0:
            return
        n = len(self.particles)
        for i, p in enumerate(self.particles):
            density = p.mass
            h2 = max(p.smoothing_length * p.smoothing_length, 1e-9)
            stride = 1 if n <= 96 else max(1, n // 96)
            for j in range(0, n, stride):
                if i == j:
                    continue
                q = self.particles[j]
                dx = p.x - q.x
                dy = p.y - q.y
                r2 = dx * dx + dy * dy
                if r2 < h2:
                    w = 1.0 - math.sqrt(r2 / h2)
                    density += q.mass * w
            p.density = density
            p.pressure = max(0.0, density * p.temperature * 1.0e-7)
        cx = sum(p.x for p in self.particles) / n
        cy = sum(p.y for p in self.particles) / n
        for p in self.particles:
            dx = p.x - cx
            dy = p.y - cy
            d = math.hypot(dx, dy) or 1.0
            pressure_push = clamp(p.pressure / max(p.mass, 1e-9), 0.0, 35.0)
            p.vx += (dx / d) * pressure_push * dt
            p.vy += (dy / d) * pressure_push * dt
            damp = max(0.0, 1.0 - dt * 0.055)
            p.vx *= damp
            p.vy *= damp
            p.x += p.vx * dt
            p.y += p.vy * dt
            p.temperature = max(3.0, p.temperature - dt * (120.0 + p.temperature * 0.01))
            p.life -= dt
        self.clear_dead()

    def total_mass(self):
        return sum(p.mass for p in self.particles)
