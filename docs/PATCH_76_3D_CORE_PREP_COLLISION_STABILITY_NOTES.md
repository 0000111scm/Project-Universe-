# PATCH 76 — 3D Core Prep + Collision Stability

Cronograma original:
- preparar core 3D
- render 2D continua como projeção XY

Adicionado pelo bug reportado:
- travamento com 3 corpos colidindo

Mudanças:
- physics_core/vector3.py
- physics_core/collision_budget.py
- Simulation.core_dimension = 3
- budget de colisões pesadas por frame
- impede mesmo corpo de rodar múltiplas colisões SPH pesadas no mesmo frame
- limita fragmentos por frame
- marca corpos removidos para não serem processados de novo no mesmo loop
- teste multi-impacto com 3 corpos
