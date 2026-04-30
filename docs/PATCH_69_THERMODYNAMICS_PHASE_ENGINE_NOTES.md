# PATCH 69 — Thermodynamics + Phase Engine

Foco físico:
- energia cinética perdida vira calor local
- materiais têm calor específico, fusão, vaporização e plasma
- fase depende de temperatura + pressão
- SPH usa a engine de fase
- colisão planetária injeta calor por partição física
- corpos passam a ter `phase`: solid/liquid/vapor/plasma
- resfriamento radiativo simplificado por Stefan-Boltzmann

Novo módulo:
- physics_core/thermodynamics.py
