# PATCH 77 — Octree/Barnes-Hut 3D + Stellar Regression Guard

Cronograma:
- Octree 3D foundation
- backend automático no PhysicsCoreSystem

Adicionado:
- teste many_stars travando
- regressão de fusão estelar instantânea

Mudanças:
- physics_core/octree_3d.py
- PhysicsCoreSystem usa octree_3d acima do threshold
- run_tests.py agora tem timeout por teste
- test_many_stars_remnant.py ajustado para processo persistente
- guard: estrela+estrela não colapsa antes de tempo mínimo de envelope
- menos ejeção de plasma por frame para evitar explosão combinatória
- novo teste: test_stellar_no_instant_merge_regression.py
