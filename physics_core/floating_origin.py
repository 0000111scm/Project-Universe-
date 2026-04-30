# physics_core/floating_origin.py
"""Floating origin.

Ideia Feynman:
números muito grandes perdem detalhes pequenos.
Então a simulação mantém o mundo em FP64,
mas o render recebe coordenadas locais perto da câmera.
"""

try:
    import numpy as np
except Exception:
    np = None


class FloatingOrigin:
    def __init__(self):
        self.origin = None

    def set_origin(self, xyz):
        if np is None:
            self.origin = xyz
        else:
            self.origin = np.array(xyz, dtype=np.float64)

    def world_to_local(self, positions):
        if self.origin is None:
            return positions
        return positions - self.origin[None, :]

    def local_point(self, point):
        if self.origin is None:
            return point
        return point - self.origin
