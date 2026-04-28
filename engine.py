"""Camada inicial de engine para tirar o peso do main.py.

Ainda e fina de proposito: primeiro estabiliza API, depois movemos update/render
sem quebrar o app. O main deve falar com Engine em vez de manipular Simulation direto
nos proximos patches.
"""
from simulation import Simulation

class UniverseEngine:
    def __init__(self):
        self.sim = Simulation()
        self.paused = False

    @property
    def bodies(self):
        return self.sim.bodies

    def add_body(self, body):
        return self.sim.add_body(body)

    def can_add_body(self, reserve=1):
        return self.sim.can_add_body(reserve)

    def set_time_scale(self, scale):
        self.sim.time_scale = scale
        self.paused = False

    def toggle_pause(self):
        self.paused = not self.paused
        return self.paused

    def step(self, dt):
        if not self.paused:
            self.sim.step(dt)
