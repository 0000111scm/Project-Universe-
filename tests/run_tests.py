import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEST_DIR = ROOT / "tests"

tests = [
    "test_imports.py",
    "test_nbody_stability.py",
    "test_energy_conservation_orbit.py",
    "test_long_orbit.py",
    "test_jupiter_does_not_eject_sun.py",
    "test_planet_collision_mass_momentum.py",
    "test_blackhole_accretion.py",
    "test_stellar_accretion.py",
    "test_stellar_no_solid_fragments.py",
    "test_many_stars_remnant.py",
    "test_fragment_speed_limits.py",
    "test_ring_formation.py",
    "test_roche_no_startup_explosion.py",
    "test_performance_benchmark.py",
]

for test in tests:
    print(f"\nRunning {test}...")
    subprocess.run([sys.executable, str(TEST_DIR / test)], cwd=str(ROOT), check=True)

print("\nALL PHYSICS TESTS PASSED")
