# PATCH 74 — Replace Planetary Collision Pipeline

Mudança grande:
- adiciona physics_core/planetary_pipeline.py
- colisão planeta-planeta deixa de usar reacumulação rápida
- classifica impacto por energia de ligação, velocidade de escape, ângulo e massa
- aplica:
  - deformação
  - dano
  - heat local
  - ejecta
  - remanescente de impacto
  - disrupção parcial/catastrófica

Correção:
- SPH resolver não reacumula em impacto quente/rápido
- planeta rochoso não ganha anel por colisão
