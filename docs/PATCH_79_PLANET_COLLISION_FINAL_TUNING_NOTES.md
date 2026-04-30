# PATCH 79 — Planet Collision Replacement FINAL + Ejecta Tuning

Cronograma:
- finalização do pipeline planetário

Adicionado:
- colisões estavam gerando explosões/detritos grandes demais

Correções:
- novo physics_core/ejecta_limits.py
- massa visível de ejecta é limitada por severidade e escape velocity
- fragmentos rochosos têm raio máximo físico/visual
- velocidade de detritos fica limitada por escape velocity
- reduz número de fragmentos por impacto
- reduz ejecta_fraction do planetary_pipeline
- remanescentes não nascem gigantes
- planeta rochoso não ganha anel

Teste:
- test_planetary_ejecta_limits.py
