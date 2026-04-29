# Patch 31 — Grade de superfície 2D + colisão sem “grudar e explodir”

## Corrigido
- Colisões grandes não puxam mais os dois corpos para o mesmo ponto antes de ejetar massa.
- O impacto agora separa compressão, cisalhamento, ejeção de massa e reacréscimo.
- Impactos tangenciais preservam deslizamento e rotação em vez de virarem fusão seca.

## Adicionado
- Grade de superfície 2D simplificada por faixas angulares.
- Cada célula guarda temperatura, dano, derretimento, elevação e material.
- Crateras e cicatrizes agora também alteram células locais da superfície.
- Render discreto de dano/calor local no corpo.

## Limite atual
Ainda não é SPH real nem terreno completo. É a base para Patch 32: temperatura local mais física.
