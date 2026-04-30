# PATCH 80 — Physics Regression Gate + Collision Stabilization

- novo physics_core/collision_safety.py
- SPH Body Replacement pesado OFF por padrão
- limita colisões pesadas por frame
- limita fragmentos por colisão/frame
- fragmentos rochosos menores e mais lentos
- fragment-fragment collisions ignoradas no loop pesado
- testes de regressão contra explosão/travamento
