# Patch 11 — Presets, mover corpos, habitabilidade mais realista

## Corrigido
- Habitabilidade não dá mais 100% para planetas com atmosfera/pressão fracas.
- Marte-like com água e temperatura boas agora ainda é limitado por pressão, atmosfera fina e proteção radiativa.
- A pontuação de vida ficou mais lenta e mais conservadora.

## Adicionado
- Aba `Presets` no catálogo:
  - Sistema Solar
  - Sistema Binário
  - Colisão Lua-Terra
  - Campo de Asteroides
- Botão `Mover` no painel do corpo selecionado.
  - Clique em `Mover`, depois clique/arraste no espaço para reposicionar o corpo.
  - A simulação pausa automaticamente durante o reposicionamento.
- Painel ambiental com barras dos fatores de vida.
- Rodapé limpo: remove lista enorme de atalhos e mostra só status.

## Refatoração
- Criado `physics/presets.py`.
- Criado `visuals/panel.py` com helper de barras.
- Começo da extração real do painel, sem quebrar o loop principal.

## Próximo passo recomendado
- Extrair `draw_panel()` inteiro para `visuals/panel.py` com objeto de estado.
- Criar editor orbital: mover corpo com opção de preservar velocidade, zerar velocidade ou circularizar órbita.
- Melhorar composição atmosférica: O2, N2, CO2, CH4 e pressão parcial.
