# Project Universe

Simulador espacial 2D em Python inspirado no Universe Sandbox, com foco em física, realismo visual e evolução progressiva para uma engine moderna.

> Nome em inglês, projeto em PT-BR. Interface, medidas e documentação principal seguem o padrão brasileiro.

## Estado atual

O projeto já possui:

- Gravidade N-body em tempo real.
- Colisões por tipo de astro: planetas, estrelas, buracos negros, galáxias e pequenos corpos.
- Fragmentação intermediária com detritos, aquecimento e conservação básica de momento.
- Temperatura dinâmica por fluxo estelar.
- Atmosfera simplificada com gases separados: N₂, O₂, CO₂ e CH₄.
- Habitabilidade explicável com fatores físicos.
- Zonas habitáveis, limite de Roche, esfera/zona gravitacional, baricentro e vetores.
- Presets de simulação.
- Editor orbital básico: mover, zerar velocidade e circularizar órbita.
- Interface em PT-BR com °C, km/s, UA, km, bar, m/s², M⊕ e M☉.

## Como rodar

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

No Linux/macOS:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

## Controles principais

- Mouse esquerdo: selecionar/criar/mover conforme o modo ativo.
- Botão `Mover`: reposiciona o corpo selecionado com o mouse ou setas.
- Setas: movem o corpo no modo `Mover`; fora dele, navegam a câmera.
- Shift + setas: movimento mais rápido.
- `Zerar V`: zera a velocidade relativa ao corpo dominante.
- `Circularizar`: ajusta a velocidade para uma órbita circular aproximada.
- Espaço ou botão `Pausar`: pausa o tempo.

## Estrutura

```text
project_universe/
├── main.py                  # loop principal e estado da aplicação
├── simulation.py            # motor físico principal
├── body.py                  # entidade de corpo celeste
├── catalog.py               # catálogo de astros
├── config.py                # constantes globais
├── engine.py                # camada inicial de engine
├── physics/
│   ├── celestial.py         # classificação e regras celestes
│   ├── collision_rules.py   # regras de colisão por família de objeto
│   ├── environment.py       # temperatura, atmosfera, Roche e maré
│   ├── habitability.py      # cálculo de habitabilidade
│   ├── presets.py           # cenários prontos
│   ├── sph.py               # base para SPH
│   └── units.py             # conversões e formatação BR
├── systems/
│   ├── labels.py
│   └── orbits.py            # predição orbital N-body
└── visuals/
    ├── background.py
    ├── body_render.py
    └── panel.py
```

## Roadmap curto

1. Extrair totalmente o painel lateral para `visuals/panel.py`.
2. Completar `physics/collision_rules.py` e reduzir lógica física dentro de `simulation.py`.
3. Implementar SPH real por fases.
4. Melhorar transferência térmica, nuvens, clima e arrasto atmosférico.
5. Preparar migração futura para Unity DOTS/engine moderna quando a física estiver validada.

## Convenção de branches

```text
main        versão estável
Dev         integração dos próximos patches
patch-x     patch isolado para teste
```

Sugestão de commit:

```bash
git add .
git commit -m "Patch 12: orbital editor, BR units cleanup and repo polish"
git push
```

## Licença

Defina uma licença antes de abrir o projeto publicamente. Para portfólio e código aberto, MIT é um bom ponto de partida.
