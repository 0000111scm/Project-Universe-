# PATCH 66 — Barnes-Hut 2D

Foco físico/arquitetural:
- Barnes-Hut 2D funcional no physics_core
- Quadtree com centro de massa por nó
- Critério theta: size / distance < theta
- Backend automático:
  - direct_nbody para poucos corpos
  - barnes_hut_2d para muitos corpos

Ainda não é GPU nem 3D.
É o passo correto antes de Octree 3D/compute shader.
