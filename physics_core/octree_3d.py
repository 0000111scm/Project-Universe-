# physics_core/octree_3d.py
"""Octree / Barnes-Hut 3D foundation.

PATCH 77

Feynman:
- perto: calcula corpo por corpo;
- longe: um grupo de corpos vira um centro de massa;
- em 3D isso usa octree, não quadtree.

Ainda não troca todo render para 3D.
Serve como backend físico 3D para o core.
"""

from dataclasses import dataclass
import math

try:
    import numpy as np
except Exception:
    np = None


@dataclass
class OctreeNode:
    cx: float
    cy: float
    cz: float
    half_size: float
    mass: float = 0.0
    com_x: float = 0.0
    com_y: float = 0.0
    com_z: float = 0.0
    body_index: int = -1
    children: object = None

    def is_leaf(self):
        return self.children is None


def _child_index(node, x, y, z):
    ix = 1 if x >= node.cx else 0
    iy = 1 if y >= node.cy else 0
    iz = 1 if z >= node.cz else 0
    return ix | (iy << 1) | (iz << 2)


def _make_children(node):
    h = node.half_size * 0.5
    node.children = []
    for iz in (0, 1):
        for iy in (0, 1):
            for ix in (0, 1):
                node.children.append(
                    OctreeNode(
                        node.cx + h * (1 if ix else -1),
                        node.cy + h * (1 if iy else -1),
                        node.cz + h * (1 if iz else -1),
                        h,
                    )
                )


def _update_mass(node, x, y, z, m):
    total = node.mass + m
    if total <= 0:
        return
    node.com_x = (node.com_x * node.mass + x * m) / total
    node.com_y = (node.com_y * node.mass + y * m) / total
    node.com_z = (node.com_z * node.mass + z * m) / total
    node.mass = total


def insert_body(node, positions, masses, idx, depth=0, max_depth=32):
    x = float(positions[idx, 0])
    y = float(positions[idx, 1])
    z = float(positions[idx, 2])
    m = float(masses[idx])

    _update_mass(node, x, y, z, m)

    if node.body_index == -1 and node.is_leaf():
        node.body_index = idx
        return

    if node.is_leaf():
        old_idx = node.body_index
        node.body_index = -1
        _make_children(node)
        if old_idx != -1 and depth < max_depth:
            ci = _child_index(node, positions[old_idx, 0], positions[old_idx, 1], positions[old_idx, 2])
            insert_body(node.children[ci], positions, masses, old_idx, depth + 1, max_depth)

    if depth >= max_depth:
        return

    ci = _child_index(node, x, y, z)
    insert_body(node.children[ci], positions, masses, idx, depth + 1, max_depth)


def build_octree(positions, masses, active):
    if np is None:
        raise RuntimeError("NumPy é necessário para octree_3d.")

    n = len(masses)
    active_idx = [i for i in range(n) if bool(active[i])]
    if not active_idx:
        return OctreeNode(0.0, 0.0, 0.0, 1.0)

    pts = positions[active_idx]
    mn = pts.min(axis=0)
    mx = pts.max(axis=0)
    center = (mn + mx) * 0.5
    half = max(float((mx - mn).max()) * 0.55 + 1.0, 1.0)

    root = OctreeNode(float(center[0]), float(center[1]), float(center[2]), half)
    for idx in active_idx:
        insert_body(root, positions, masses, idx)
    return root


def _accumulate(node, positions, target_idx, theta, G, softening):
    if node.mass <= 0:
        return 0.0, 0.0, 0.0

    if node.is_leaf() and node.body_index == target_idx:
        return 0.0, 0.0, 0.0

    tx, ty, tz = positions[target_idx]
    dx = node.com_x - float(tx)
    dy = node.com_y - float(ty)
    dz = node.com_z - float(tz)

    dist2 = dx * dx + dy * dy + dz * dz + softening
    dist = math.sqrt(dist2)
    size = node.half_size * 2.0

    if node.is_leaf() or (size / max(dist, 1e-9)) < theta:
        inv_dist3 = 1.0 / (dist2 * dist)
        factor = G * node.mass * inv_dist3
        return dx * factor, dy * factor, dz * factor

    ax = ay = az = 0.0
    if node.children:
        for child in node.children:
            cx, cy, cz = _accumulate(child, positions, target_idx, theta, G, softening)
            ax += cx
            ay += cy
            az += cz
    return ax, ay, az


def compute_octree_acceleration(state, gravitational_constant=0.6006, theta=0.70, softening=25.0):
    if np is None:
        raise RuntimeError("NumPy é necessário para octree_3d.")

    n = state.n
    acc = np.zeros((state.pos.shape[0], 3), dtype=np.float64)
    if n == 0:
        return acc

    positions = state.pos[:n]
    masses = state.mass[:n]
    active = state.active[:n]
    root = build_octree(positions, masses, active)

    for i in range(n):
        if not active[i]:
            continue
        ax, ay, az = _accumulate(root, positions, i, float(theta), float(gravitational_constant), float(softening))
        acc[i, 0] = ax
        acc[i, 1] = ay
        acc[i, 2] = az

    return acc
