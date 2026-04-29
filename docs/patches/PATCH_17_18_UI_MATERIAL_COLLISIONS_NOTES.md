# Patch 17+18 — UI de visualização + colisões por material

## Patch 17 — Painel de visão mais limpo

- Mantidos no painel principal:
  - Vetores
  - Órbitas
  - Zona habitável
  - Roche
  - Gravidade
- Criado botão `Avançado`.
- Movidos para o modo avançado:
  - Baricentro
  - Gráfico
  - Desempenho
- `Grav.` virou `Gravidade`, porque para o usuário faz mais sentido.
  - Internamente ainda usa a esfera de Hill/zona de dominância gravitacional aproximada.

## Patch 18 — Colisões por material

- Adicionado `physics/materials.py`.
- `Body` agora possui:
  - `material`
  - `composition`
- Materiais iniciais:
  - rock
  - ice
  - gas
  - plasma
  - blackhole
- Colisões passam a preservar/misturar composição.
- Fragmentos herdam material/composição do corpo original.
- Buracos negros mantêm cor preta e nome coerente.
- Gases fragmentam menos; gelo fragmenta mais; plasma quase não gera fragmento comum.

## Observação

Ainda não é SPH real. É uma camada intermediária para preparar colisões mais físicas antes da implementação SPH.
