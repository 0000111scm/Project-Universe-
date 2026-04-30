# PATCH 80 HOTFIX — Mass Conservation

Corrige regressão:
- colisão planeta-planeta perdia massa demais
- teste test_planet_collision_mass_momentum falhava
- remanescente catastrófico podia nascer com massa absurda baixa

Mudanças:
- bound_fraction mínimo maior
- ejecta_fraction mais conservador
- floor de massa de remanescente enquanto SPH pesado está desligado
- teste novo: test_planetary_mass_floor_regression.py
