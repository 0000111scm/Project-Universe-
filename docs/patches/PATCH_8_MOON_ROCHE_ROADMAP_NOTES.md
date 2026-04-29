# Patch 8 — Lua, Roche e Roadmap

## Corrigido
- Lua criada com `U` não explode mais imediatamente.
- Corrigido `sim.add_body(_moon)` que ficava fora do bloco correto do atalho `U`.
- Lua agora nasce com cooldown curto de colisão.
- Órbita inicial da lua foi afastada para não nascer dentro do limite de Roche visual.

## Física ajustada
- Limite de Roche agora usa densidade aproximada (`massa / raio³`) em vez de massa bruta.
- Isso é mais coerente com a fórmula física real e evita valores absurdos na escala interna do simulador.
- Corpos recém-criados têm pequena janela de estabilização antes de sofrer fragmentação por Roche.
- `born_timer` agora é salvo/carregado.

## Organização
- Adicionado `ROADMAP_PROJECT_UNIVERSE.md` com a lista de evolução técnica separada por fases.

## Próximo patch recomendado
- Separar `draw_panel()` para `visuals/panel.py`.
- Criar `physics/collision_rules.py` para remover regras de colisão de `simulation.py`.
- Adicionar painel de diagnóstico: FPS, corpos, substeps, temperatura média, partículas e modo performance.
