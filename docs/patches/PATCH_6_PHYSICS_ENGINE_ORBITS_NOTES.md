# Patch 6 — Physics sanity, N-body predictive orbits, pause control, SPH base

## Corrigido
- Buracos negros e galáxias não são mais tratados como estrelas só por terem massa alta.
- Colisões agora passam por uma classificação física: galáxia, buraco negro, objeto compacto, estrela, planeta, corpo pequeno.
- Galáxias e buracos negros não devem “sumir” por virarem evento de nova/supernova indevido.
- `selected_type` agora é validado antes de acessar o catálogo, evitando `IndexError` em abas/itens.
- Adicionado softening gravitacional mais coerente para evitar estilingue numérico em massas extremas.
- `dt` do step físico agora é limitado para impedir explosão de integração quando o FPS dá engasgo.

## Colisões por família
- Galáxia + galáxia/corpo: fusão/assimilação galáctica.
- Buraco negro + corpo: acreção/merger compacto, sem fragmentos comuns.
- Estrela + estrela: fusão/nova; pode gerar remanescente compacto se passar de limite.
- Estrela + planeta: absorção/vaporização do planeta.
- Planeta + planeta: fusão lenta, fragmentação em impacto médio/rápido.
- Pequenos corpos: absorção, craterização e detritos.

## Órbitas
- Criado `systems/orbits.py` com predição N-body real usando integração Leapfrog/Velocity-Verlet.
- O desenho de órbitas agora usa cache global por assinatura do estado da simulação.
- Em modo performance, reduz passos/corpos usados na predição.

## SPH
- Criado `physics/sph.py` com estrutura inicial de partículas, kernel Poly6, gradiente Spiky e estimativa de densidade.
- Ainda não substitui a colisão principal. É base limpa para o próximo patch.

## Engine/render
- Criado `engine.py` como primeira camada para separar engine do `main.py` sem quebrar o loop atual.
- A separação total de render/UI ainda precisa de mais um patch dedicado.

## UI
- Botão de pausar tempo adicionado junto aos controles de velocidade.
- Clique em pausa alterna entre pausa e execução; clicar em uma velocidade despausa.

## Próximo passo recomendado
1. Mover `draw_panel()` para `visuals/panel.py`.
2. Mover renderização de corpos para `visuals/body_render.py`.
3. Ligar `physics/sph.py` em colisões planetárias reais.
4. Criar unidades científicas no painel: kg, km/s, K, raio, densidade, energia de impacto.
