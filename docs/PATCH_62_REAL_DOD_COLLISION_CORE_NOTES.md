# PATCH 62 REAL — Data-Oriented Physics Core + Planetary Collision

Foco físico/arquitetural, sem UI.

Arquitetura:
- adiciona physics/state_arrays.py
- espelha Body em arrays fp64: pos, vel, acc, mass, radius
- N-body usa arrays contíguos quando NumPy existe
- prepara origem flutuante, Barnes-Hut, GPU e 3D

Colisão planetária:
- adiciona physics/planetary_collision.py
- usa energia de ligação gravitacional proxy
- planeta-planeta não funde instantaneamente por padrão
- contato vira deformação, dano, aquecimento e ejeção parcial
- fusão/acréscimo só em impacto extremamente suave
