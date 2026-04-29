# Patch 5 — UI crash fix + N-body orbit preview

## Corrigido
- Crash ao mudar de aba depois de muitas colisões (`IndexError` no painel).
- Seleção antiga do catálogo agora é validada antes de acessar `BODY_CATALOG`.
- Clique em aba não reaproveita mais os botões antigos da lista no mesmo frame.

## Melhorado
- Órbitas preditivas agora usam uma previsão N-body simplificada com cache.
- Em cenas lotadas, o preview pula fragmentos e corpos pequenos para segurar FPS.
- Primeiro corte real de UI: helpers seguros do painel foram movidos para `ui/panel_helpers.py`.

## Ainda fica para o próximo passo
- Extrair `draw_panel()` inteiro do `main.py`.
- Extrair renderização dos corpos para `visuals/body_render.py`.
- Melhorar painel científico com escala física, unidade e filtros de visualização.
