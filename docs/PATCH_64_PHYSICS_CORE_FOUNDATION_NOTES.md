# PATCH 64 — Physics Core Rewrite Foundation

Este patch para de remendar `simulation.py` e cria a base nova:

physics_core/
- ecs.py
- state.py
- integrators.py
- gravity.py
- floating_origin.py
- bridge.py
- barnes_hut_2d.py

Objetivo:
- ECS/SoA
- arrays contíguos FP64
- integrador Leapfrog independente
- gravidade vetorizada
- floating origin preparado
- bridge Body <-> PhysicsState
- fundação para Barnes-Hut, SPH real, 3D e GPU

Importante:
- ainda não substitui completamente Simulation
- Body continua sendo camada de render/UI
- o core novo será integrado progressivamente nos próximos patches
