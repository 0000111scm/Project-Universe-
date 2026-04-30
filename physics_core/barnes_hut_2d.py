# physics_core/barnes_hut_2d.py
"""Barnes-Hut 2D real para o core físico.

Feynman:
- longe: muitos corpos pequenos puxam como se fossem uma massa só no centro do grupo;
- perto: calcula corpo por corpo;
- resultado: sai de O(N²) para algo perto de O(N log N).

Este é 2D por enquanto, mas a arquitetura prepara octree 3D depois.
"""

from dataclasses import dataclass
import math

try:
    import numpy as np
except Exception:
    np = None


@dataclass
class BHNode:
    cx: float
    cy: float
    half_size: float
    mass: float = 0.0
    com_x: float = 0.0
    com_y: float = 0.0
    body_index: int = -1
    children: object = None

    def is_leaf(self):
        return self.children is None


def _child_index(node, x, y):
    east = x >= node.cx
    south = y >= node.cy
    return (1 if east else 0) + (2 if south else 0)


def _make_children(node):
    h = node.half_size * 0.5
    node.children = [
        BHNode(node.cx - h, node.cy - h, h),
        BHNode(node.cx + h, node.cy - h, h),
        BHNode(node.cx - h, node.cy + h, h),
        BHNode(node.cx + h, node.cy + h, h),
    ]


def _update_mass(node, x, y, m):
    total = node.mass + m
    if total <= 0:
        return
    node.com_x = (node.com_x * node.mass + x * m) / total
    node.com_y = (node.com_y * node.mass + y * m) / total
    node.mass = total


def insert_body(node, positions, masses, idx, depth=0, max_depth=32):
    x = float(positions[idx, 0])
    y = float(positions[idx, 1])
    m = float(masses[idx])

    _update_mass(node, x, y, m)

    if node.body_index == -1 and node.is_leaf():
        node.body_index = idx
        return

    if node.is_leaf():
        old_idx = node.body_index
        node.body_index = -1
        _make_children(node)
        if old_idx != -1 and depth < max_depth:
            old_child = _child_index(node, float(positions[old_idx, 0]), float(positions[old_idx, 1]))
            insert_body(node.children[old_child], positions, masses, old_idx, depth + 1, max_depth)

    if depth >= max_depth:
        return

    child = _child_index(node, x, y)
    insert_body(node.children[child], positions, masses, idx, depth + 1, max_depth)


def build_tree(positions, masses, active):
    n = len(masses)
    if n == 0:
        return BHNode(0.0, 0.0, 1.0)

    active_idx = [i for i in range(n) if bool(active[i])]
    if not active_idx:
        return BHNode(0.0, 0.0, 1.0)

    xs = positions[active_idx, 0]
    ys = positions[active_idx, 1]
    min_x, max_x = float(xs.min()), float(xs.max())
    min_y, max_y = float(ys.min()), float(ys.max())
    cx = (min_x + max_x) * 0.5
    cy = (min_y + max_y) * 0.5
    half = max(max_x - min_x, max_y - min_y, 1.0) * 0.55 + 1.0

    root = BHNode(cx, cy, half)
    for idx in active_idx:
        insert_body(root, positions, masses, idx)
    return root


def _accumulate(node, positions, masses, target_idx, theta, G, softening):
    if node.mass <= 0:
        return 0.0, 0.0

    # não calcula auto-força em folha de si mesmo
    if node.is_leaf() and node.body_index == target_idx:
        return 0.0, 0.0

    tx = float(positions[target_idx, 0])
    ty = float(positions[target_idx, 1])
    dx = node.com_x - tx
    dy = node.com_y - ty
    dist2 = dx * dx + dy * dy + softening
    dist = math.sqrt(dist2)

    size = node.half_size * 2.0

    if node.is_leaf() or (size / max(dist, 1e-9)) < theta:
        inv_dist3 = 1.0 / (dist2 * dist)
        factor = G * node.mass * inv_dist3
        return dx * factor, dy * factor

    ax = ay = 0.0
    if node.children:
        for child in node.children:
            cx, cy = _accumulate(child, positions, masses, target_idx, theta, G, softening)
            ax += cx
            ay += cy
    return ax, ay


def compute_barnes_hut_acceleration(state, gravitational_constant=0.6006, theta=0.65, softening=25.0):
    if np is None:
        raise RuntimeError("NumPy é necessário para Barnes-Hut")

    n = state.n
    acc = np.zeros((state.pos.shape[0], 3), dtype=np.float64)
    if n == 0:
        return acc

    positions = state.pos[:n]
    masses = state.mass[:n]
    active = state.active[:n]
    root = build_tree(positions, masses, active)

    for i in range(n):
        if not active[i]:
            continue
        ax, ay = _accumulate(root, positions, masses, i, float(theta), float(gravitational_constant), float(softening))
        acc[i, 0] = ax
        acc[i, 1] = ay
        acc[i, 2] = 0.0

    return acc
