# Patch 28 — UI Input Fix + Arrasto Atmosférico Base

## Corrigido
- Clique em botões/toggles da área VISÃO não seleciona mais corpos escondidos por baixo.
- A lista de corpos só registra clique nas linhas realmente visíveis.
- Removida chamada duplicada de seleção no clique direito.

## Adicionado
- Arrasto atmosférico base para objetos atravessando atmosfera.
- Objetos rápidos perdem velocidade relativa, aquecem e podem sofrer ablação leve.

## Teste
1. Clique nos botões de VISÃO.
2. Nenhum corpo deve ser selecionado junto.
3. Lance um asteroide rápido contra planeta com atmosfera e observe aquecimento/desaceleração.
