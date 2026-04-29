# Patch 4 — Performance, Add Body Fix, US-style Background

## Correções
- Corrigido bloqueio que impedia adicionar novos astros depois de colisões grandes.
- O limite antigo no `main.py` era rígido demais; agora usa `sim.can_add_body()`.
- A simulação remove detritos antigos/pequenos primeiro quando precisa abrir espaço para um corpo criado pelo usuário.

## Performance
- Adicionado modo `Perf.` no painel de visão.
- Atalho: `P` ativa/desativa performance mode.
- Performance mode reduz substeps, fragmentos, camada próxima do fundo, densidade visual de trilhas e custo das órbitas.
- Fragmentos somem mais rápido em performance mode.

## Órbitas
- Adicionado cache simples para órbitas analíticas.
- Fragmentos e corpos muito pequenos são ignorados em performance mode.

## Fundo visual
- Fundo refeito com aparência mais sóbria:
  - gradiente escuro sutil;
  - poeira galáctica;
  - veios escuros;
  - estrelas menos saturadas;
  - parallax em camadas.

## Ainda pendente
- Separar render/UI do `main.py` de forma mais profunda.
- Órbita preditiva N-body real, não só aproximação analítica.
- Painel científico completo com unidades melhores.
