# Patch 9 — BR Units, Habitability, Environmental Coherence

## Corrigido/melhorado
- Painel científico agora usa PT-BR e unidades familiares: °C, km/s, UA, bar, m/s², M⊕ e M☉.
- Temperatura não aparece mais como Kelvin negativo/confuso; o motor ainda calcula em K, mas a UI mostra Celsius.
- Habitabilidade agora é composta por fatores: temperatura, massa, atmosfera, água líquida, presença de estrela e riscos físicos.
- O painel mostra pressão superficial estimada, estado da água, gelo, vapor, maré, Roche, distância ao corpo dominante e aceleração.
- Ambiente ganhou inércia térmica melhor, escape atmosférico, pressão superficial e atualização de fase da água.
- Colisões aquecem corpos fundidos com base em energia de impacto simplificada.

## Próximo patch sugerido
1. Extrair `draw_panel()` para `visuals/panel.py`.
2. Criar `physics/collision_rules.py` e tirar regras de colisão de `simulation.py`.
3. Criar presets reais: Sistema Solar, Terra-Lua, binária, colisão planetária, buraco negro.
4. Adicionar autosave e botão de reset limpo.
