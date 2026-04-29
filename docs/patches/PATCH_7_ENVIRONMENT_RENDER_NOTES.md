# Patch 7 — Ambiente Dinâmico, UI Fix e Separação de Render

## Corrigido
- Texto verde de seleção não sobrepõe mais o bloco AJUSTE.
- Lista lateral ganhou margem segura antes da área fixa inferior.
- Botão de pausa continua junto das velocidades.

## Física/Matemática adicionada
- Temperatura planetária agora muda gradualmente com fluxo radiativo `1/r²`.
- Distância de estrelas altera o estado térmico: perto aquece, longe esfria.
- Atmosfera escapa com alta temperatura e baixa gravidade superficial.
- Água vaporiza/perde massa térmica em mundos muito quentes.
- Gelo aumenta em mundos frios.
- Aquecimento de maré por proxy `M/r³`.
- Stress de Roche marcado em corpos próximos demais de massas dominantes.

## Arquivos novos
- `physics/environment.py`
- `visuals/body_render.py`

## Próximo patch recomendado
- Mover `draw_panel()` inteiro para `visuals/panel.py` com estado explícito.
- Mover renderização completa dos corpos para `visuals/body_render.py`.
- Transformar `UniverseEngine` no dono único de simulação, ambiente e tempo.
