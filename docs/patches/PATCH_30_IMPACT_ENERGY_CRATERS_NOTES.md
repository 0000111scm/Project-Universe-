# Patch 30 — Energia de impacto + crateras/cicatrizes

## Objetivo
Corrigir a lógica de colisão para deixar de tratar impactos como fusão simples e iniciar uma base física mais coerente.

## Incluído
- Botão **Avançado** restaurado no painel Visão.
- Colisão usando energia de impacto normalizada.
- Ângulo de impacto:
  - frontal gera cratera circular;
  - tangencial gera cicatriz alongada.
- Aquecimento local no ponto de impacto.
- Corpo impactado guarda marcas em `surface_marks`.
- Base para o futuro `surface grid` em `local_heat_points`.
- Fragmentos mantêm:
  - material;
  - densidade;
  - massa;
  - temperatura;
  - rotação;
  - forma irregular 2D.
- Renderização simples de fragmentos irregulares.

## Limitação conhecida
Ainda não é SPH real. O Patch 30 melhora a lógica de impacto, mas a deformação física contínua e a propagação de onda de choque por célula vêm depois do grid de superfície e SPH.

## Próximo patch oficial
Patch 31 — Grade de superfície 2D.
