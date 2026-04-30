from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from body import Body
from physics_core.structural_dynamics import evaluate_structural_state, critical_angular_velocity

b = Body(0, 0, 0, 0, 1000, 10, (100, 100, 100), "Rocha")
b.material = "rock"

crit = critical_angular_velocity(b)
assert crit > 0

b.angular_velocity = crit * 1.5
state = evaluate_structural_state(b)
assert state.spin_stress > 1.0
assert state.should_shed_mass

print("OK: structural dynamics")
