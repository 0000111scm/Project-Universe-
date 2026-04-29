# Patch 19+20+21 — colisão guiada por física, limpeza visual e estabilidade

## Objetivo
Remover efeitos visuais artificiais de colisão e fazer o evento aparecer pela própria simulação: calor, detritos, massa e movimento.

## Mudanças principais
- Removidos os círculos/ondas de explosão em colisões.
- Colisões agora geram apenas ejecta discreto, sem overlay arcade.
- Fragmentos reduzidos e com vida/trilha menores para diminuir poluição visual.
- Fragmentos não mostram label por padrão; só aparecem se selecionados/seguidos.
- Aquecimento por impacto baseado em energia cinética simplificada.
- Corpos aquecidos exibem brilho superficial temporário, não anéis artificiais.
- Limite de corpos reduzido para estabilidade visual/performance.
- Temperatura no painel exibida em °C.

## Física aplicada
Ainda não é SPH real, mas agora a colisão usa uma aproximação mais coerente:

- energia cinética relativa;
- massa reduzida do impacto;
- aquecimento específico do corpo sobrevivente/resultante;
- comportamento diferente por material;
- ejecta reduzido para gases/plasma e maior para gelo/rocha.

## Arquivos alterados
- `main.py`
- `simulation.py`
- `body.py`
- `physics/materials.py`

## Próximo passo recomendado
Implementar SPH real por fases: partículas internas, densidade, pressão, ejeção de massa e recomposição gravitacional.
