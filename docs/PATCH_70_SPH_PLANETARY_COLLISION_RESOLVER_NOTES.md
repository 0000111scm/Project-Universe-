# PATCH 70 — SPH Planetary Collision Resolver

Este patch muda o papel do SPH:
- antes: SPH era feedback auxiliar
- agora: SPH resolve colisões planetárias relevantes

Novo módulo:
- physics_core/sph_collision_resolver.py

Lógica:
1. amostra os dois corpos em partículas
2. injeta calor pelo impacto
3. roda micro-passos SPH
4. calcula massa ligada/ejetada
5. define reacumulação, deformação ou disrupção
6. aplica dano, temperatura, fase, perda de massa e ejecta

Isso ainda é 2D/híbrido, mas reduz a dependência de regra manual.
