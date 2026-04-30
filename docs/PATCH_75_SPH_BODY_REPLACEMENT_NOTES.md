# PATCH 75 — SPH Body Replacement Prototype

Grande mudança:
- impacto planetário forte não fica mais preso em Body rígido
- os corpos são removidos e substituídos por:
  - Remanescente SPH, se a nuvem ficou ligada
  - detritos/ejecta, se dispersou
  - vapor/disrupção, se energia foi extrema

Novo módulo:
- physics_core/sph_body_replacement.py

Também corrige:
- test_many_stars_remnant.py travando/esperando remanescente rápido
- após PATCH 73, colisão estelar é processo persistente, então o teste agora valida envelope/ejeção/estabilidade
- reduz contagem de plasma estelar para evitar explosão de corpos em testes
