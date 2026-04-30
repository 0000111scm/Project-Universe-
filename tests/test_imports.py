from _test_utils import ROOT
import importlib

for module in ["body", "simulation", "config", "catalog", "camera", "physics.impact_solver", "physics.local_physics"]:
    importlib.import_module(module)

print("OK: imports")
