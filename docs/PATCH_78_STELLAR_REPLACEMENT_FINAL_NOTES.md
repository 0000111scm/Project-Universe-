# PATCH 78 — Stellar Collision Replacement FINAL

Mudança grande:
- adiciona physics_core/common_envelope.py
- colisão estelar cria entidade visível/persistente "Envelope Comum"
- estrela+estrela não passa mais por merge/accretion genérico
- colapso só ocorre após idade mínima + instabilidade
- ejeção contínua controlada
- remove regressão do "plim fundiu"

Testes:
- test_common_envelope_entity.py
- test_stellar_pipeline_no_generic_merge.py
