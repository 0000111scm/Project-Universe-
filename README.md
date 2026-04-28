<div align="center">

# Project Universe

### Simulador espacial 2D em Python, com foco em física, visual limpo e evolução futura para 3D.

![Python](https://img.shields.io/badge/Python-3.12+-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Pygame](https://img.shields.io/badge/Pygame-2D-00AA55?style=for-the-badge)
![Status](https://img.shields.io/badge/status-em%20desenvolvimento-FFB000?style=for-the-badge)
![Idioma](https://img.shields.io/badge/idioma-PT--BR-009739?style=for-the-badge)

</div>

---

## Visão geral

**Project Universe** é um simulador espacial em desenvolvimento, atualmente em **2D**, feito em Python.  
A proposta é construir uma base sólida de física, interação e visualização para, no futuro, evoluir para uma engine moderna e possivelmente uma versão 3D.

O projeto prioriza:

- simulação gravitacional em tempo real;
- comportamento físico coerente entre diferentes tipos de astros;
- interface em português brasileiro;
- unidades no padrão usado no Brasil;
- arquitetura modular para crescimento progressivo.

---

## Estado atual

| Área | Implementado |
|---|---|
| Gravidade | N-body em tempo real |
| Colisões | Regras por tipo de corpo |
| Fragmentação | Detritos físicos intermediários |
| Temperatura | Variação por fluxo estelar |
| Atmosfera | Modelo simplificado com gases |
| Habitabilidade | Cálculo por fatores físicos |
| Órbitas | Predição orbital e baricentro |
| Interação | Editor orbital básico |
| Visual | Fundo espacial, brilhos e trilhas |

---

## Recursos principais

### Física e simulação

- Gravidade N-body.
- Colisões entre planetas, estrelas, buracos negros, galáxias e corpos menores.
- Fragmentação intermediária com detritos.
- Conservação básica de massa e momento.
- Temperatura dinâmica por proximidade estelar.
- Atmosfera simplificada com composição básica.
- Habitabilidade com fatores explicáveis.
- Zona habitável, limite de Roche e zonas gravitacionais.

### Interface e interação

- Interface em PT-BR.
- Medidas em °C, km/s, UA, km, bar, m/s², M⊕ e M☉.
- Seleção e inspeção de corpos.
- Editor orbital: mover, zerar velocidade e circularizar.
- Presets de simulação.
- Controle de velocidade do tempo.

---

## Como rodar

### Windows

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

### Linux / macOS

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

---

## Controles básicos

| Ação | Controle |
|---|---|
| Selecionar corpo | Mouse esquerdo |
| Criar corpo | Selecionar no painel e arrastar |
| Mover corpo | Modo mover + mouse ou setas |
| Navegar câmera | Setas |
| Movimento rápido | Shift + setas |
| Pausar tempo | Espaço |
| Zerar velocidade | Botão / comando dedicado |
| Circularizar órbita | Botão dedicado |

---

## Estrutura do projeto

```text
project_universe/
├── main.py
├── simulation.py
├── body.py
├── catalog.py
├── config.py
├── engine.py
├── physics/
│   ├── celestial.py
│   ├── collision_rules.py
│   ├── environment.py
│   ├── habitability.py
│   ├── presets.py
│   ├── sph.py
│   └── units.py
├── systems/
│   ├── labels.py
│   └── orbits.py
├── visuals/
│   ├── background.py
│   ├── body_render.py
│   └── panel.py
└── ui/
    └── panel_helpers.py
```

---

## Roadmap

### Curto prazo

- Refatorar totalmente o painel lateral.
- Reduzir lógica física dentro de `simulation.py`.
- Melhorar estabilidade da predição orbital N-body.
- Refinar colisões por composição e tipo de objeto.
- Melhorar o painel ambiental dos planetas.

### Médio prazo

- Implementar SPH real por fases.
- Melhorar transferência térmica.
- Adicionar clima, nuvens e arrasto atmosférico.
- Expandir evolução estelar.
- Adicionar mais presets científicos.

### Longo prazo

- Preparar migração para uma engine moderna.
- Evoluir o projeto para 3D.
- Usar GPU de forma mais intensa.
- Simular sistemas maiores com mais escala e performance.

---

## Convenção de branches

```text
main      versão estável
dev       integração dos próximos patches
patch-x   alterações isoladas para teste
```

---

## Status

Projeto em desenvolvimento ativo.  
A versão atual é uma base 2D funcional para testar mecânicas, física e interface antes da evolução para uma arquitetura mais robusta.

---

## Licença

Licença ainda a definir.  
Para código aberto e portfólio, a licença MIT é uma boa opção.

---

<div align="center">

**Project Universe**  
Construindo um simulador espacial passo a passo, sem pular a física.

</div>
