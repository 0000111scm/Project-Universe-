# Project Universe - Refatoração Fase 1

Separação feita sem mudar a lógica principal da simulação.

## Arquivos extraídos

- `config.py`
  - constantes globais: resolução, FPS, G, escala habitável, saves, cores de colisão.

- `catalog.py`
  - `BODY_CATALOG`
  - `STELLAR_EVOLUTION`

- `camera.py`
  - `screen_to_world()`
  - `world_to_screen()`

- `visuals/background.py`
  - geração do fundo espacial estilo Hubble.

- `systems/labels.py`
  - controle de rótulos/nomes na tela.

## Por que essa ordem

O `main.py` estava acumulando dados, física, renderização, UI e estado global.
Este primeiro corte remove blocos grandes e de baixo risco sem alterar o comportamento do simulador.

## Próxima etapa recomendada

Separar renderização e UI:

- `visuals/drawing.py`
- `visuals/panel.py`
- `systems/temperature.py`
- `systems/habitability.py`
- `save_load.py`

Atenção: a próxima etapa exige mexer mais nos globais do `main.py`, então deve ser feita com mais cuidado.
