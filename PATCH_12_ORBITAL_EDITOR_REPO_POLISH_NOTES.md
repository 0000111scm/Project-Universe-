# Patch 12 — Editor Orbital, Unidades BR e Repositório

## Correções

- As barras de habitabilidade não aparecem mais como `temperatura: 100%`.
- Agora o painel mostra a temperatura medida em °C e a barra virou `faixa térmica`, que é apenas o fator de adequação térmica.
- Habitabilidade exibida agora respeita o teto físico atual. Se pressão/atmosfera caem, a vida não fica presa artificialmente em 100%.
- Movimento por teclado saiu do WASD e foi para as setas.
- Direção das setas foi ajustada para comportamento intuitivo.

## Adicionado

- Editor orbital básico:
  - Mover corpo selecionado;
  - Zerar velocidade relativa ao corpo dominante;
  - Circularizar órbita aproximada.
- Atmosfera com gases separados:
  - N₂;
  - O₂;
  - CO₂;
  - CH₄.
- Save/load preserva gases e pressão superficial.
- README profissional para GitHub.
- CONTRIBUTING.md.
- .gitignore limpo.

## Próximos passos

1. Extrair totalmente o painel lateral para `visuals/panel.py`.
2. Completar `physics/collision_rules.py` e remover regras físicas restantes de `simulation.py`.
3. Criar painel orbital com periastro, apoastro, excentricidade e período estimado.
4. Implementar arrasto atmosférico em corpos atravessando atmosfera.
5. Começar SPH real em pequena escala.
