from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from physics_core.vector3 import Vec3, project_xy

v = Vec3(1.0, 2.0, 3.0)
u = Vec3(2.0, 0.0, -1.0)

assert (v + u).z == 2.0
assert v.dot(u) == -1.0
assert project_xy(v) == (1.0, 2.0)

print("OK: 3D core prep")
