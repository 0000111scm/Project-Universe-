from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from physics_core.thermodynamics import classify_phase, phase_name, temperature_delta_from_energy

assert phase_name(classify_phase("rock", 300.0)) == "solid"
assert phase_name(classify_phase("rock", 1800.0)) == "liquid"
assert phase_name(classify_phase("rock", 4000.0)) == "vapor"
assert phase_name(classify_phase("rock", 12000.0)) == "plasma"

dt = temperature_delta_from_energy("rock", 900.0, 1.0)
assert abs(dt - 1.0) < 1e-6

print("OK: thermodynamics phase")
