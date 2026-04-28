# Patch 13 — Movimento direto, painel mais claro e preparação de UI

## Corrigido

- Corpo selecionado agora pode ser movido com clique e arrasto direto:
  1. clique uma vez no astro para abrir as informações;
  2. clique e segure no próprio astro;
  3. arraste para reposicionar.
- O modo `Mover` ainda existe, mas não é mais obrigatório para arrastar um corpo selecionado.
- Durante o arrasto, o tempo pausa automaticamente para evitar colisões acidentais enquanto o usuário reposiciona o astro.
- O rastro do corpo é limpo ao mover, evitando linhas falsas atravessando o mapa.

## Painel de informações

- `faixa térmica` virou `temp. adequada`, deixando claro que a barra é uma adequação para vida, não uma temperatura em porcentagem.
- Temperatura real continua em °C no painel principal.
- Labels foram ajustados para ficarem mais claros:
  - `Raio` → `Raio visual`;
  - `Atm.` → `Atmosfera`;
  - `Grav.dom` → `Gravidade dom.`;
  - `Vida` → `Vida estimada`;
  - `Obs` → `Limites`.
- Adicionado título `Adequação para vida` acima das barras ambientais.

## Arquitetura

- Mantida compatibilidade com o painel atual.
- Próximo passo ainda recomendado: extrair o painel lateral inteiro para `visuals/panel.py`, reduzindo o tamanho do `main.py`.

## Observação

Este patch foca em UX e clareza científica antes da extração pesada de UI.
