# physics_core/vector3.py
"""Vector3 FP64 helpers.

PATCH 76 — 3D Core Prep

A simulação ainda renderiza em 2D, mas o core passa a ter estruturas 3D.
Render 2D = projeção temporária de x/y.
"""

from dataclasses import dataclass
import math


@dataclass
class Vec3:
    x: float
    y: float
    z: float = 0.0

    def __add__(self, other):
        return Vec3(self.x + other.x, self.y + other.y, self.z + other.z)

    def __sub__(self, other):
        return Vec3(self.x - other.x, self.y - other.y, self.z - other.z)

    def __mul__(self, scalar):
        return Vec3(self.x * scalar, self.y * scalar, self.z * scalar)

    def dot(self, other):
        return self.x * other.x + self.y * other.y + self.z * other.z

    def length_squared(self):
        return self.dot(self)

    def length(self):
        return math.sqrt(self.length_squared())

    def normalized(self):
        l = self.length()
        if l <= 1e-12:
            return Vec3(0.0, 0.0, 0.0)
        return Vec3(self.x / l, self.y / l, self.z / l)


def vec2_to_vec3(v):
    return Vec3(float(v.x), float(v.y), 0.0)


def project_xy(v):
    return float(v.x), float(v.y)
