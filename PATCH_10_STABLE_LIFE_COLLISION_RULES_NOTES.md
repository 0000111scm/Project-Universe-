# Patch 10 — Habitabilidade estável + regras de colisão separadas

## Corrigido/melhorado
- A porcentagem de vida não sobe/desce bruscamente a cada frame.
- Criado modelo de habitabilidade em duas camadas:
  - alvo físico instantâneo;
  - valor exibido suavizado por inércia ambiental.
- Quedas por desastre ainda são mais rápidas, mas não viram pisca-pisca.
- Painel mostra tendência quando o valor real está indo para cima ou para baixo.

## Matemática de vida
Fatores considerados:
- temperatura em °C;
- água líquida provável;
- pressão superficial;
- atmosfera;
- massa;
- gravidade superficial;
- fluxo estelar;
- química/CO₂;
- riscos físicos: Roche, maré e vulcanismo.

A pontuação usa média geométrica ponderada. Isso evita que um planeta com um único fator impossível pareça habitável.

## Arquitetura
- Criado `physics/collision_rules.py`.
- `simulation.py` agora pergunta ao módulo de regras qual colisão deve acontecer.
- Isso prepara o projeto para SPH real sem entupir o loop principal.

## Próximo passo recomendado
Patch 11:
- extrair `draw_panel()` para `visuals/panel.py`;
- adicionar presets científicos: Sistema Solar limpo, colisão Lua-Terra, binária, campo de asteroides;
- melhorar painel ambiental com barras de fatores.
