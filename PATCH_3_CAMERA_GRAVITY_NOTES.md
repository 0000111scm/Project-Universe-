# Project Universe - Patch 3: Camera, Gravity Zones & Performance

## Corrigido
- Zoom do mouse voltou a funcionar.
- Zoom agora ancora no ponto do cursor, então aproximar não joga o astro para fora da tela.
- Seguimento de corpo ficou suavizado, com câmera menos seca.

## Adicionado
- Toggle `Grav.` no painel VISÃO: desenha zona gravitacional aproximada usando esfera de Hill em 2D.
- Toggle `Baric.` no painel VISÃO: mostra o baricentro do sistema.
- Atalhos:
  - `J`: zona gravitacional
  - `B`: baricentro
- Vetores agora exibem velocidade e aceleração quando `Vetores` está ativo.

## Performance
- Limite de corpos reduzido para controlar avalanche de detritos.
- Fragmentos vivem menos tempo.
- Substeps físicos agora são adaptativos: menos corpos = mais estabilidade; muitos corpos = menos travamento.
- Partículas visuais de colisão são reduzidas quando há muitos corpos.

## Próximo passo recomendado
- Separar de verdade o render/UI do `main.py` em módulos dedicados.
- Melhorar órbitas preditivas com cache e atualização intervalada.
- Criar modo performance/qualidade no painel.
