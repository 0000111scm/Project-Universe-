# Contribuindo

## Fluxo recomendado

1. Crie uma branch a partir de `Dev`.
2. Faça uma mudança pequena e testável.
3. Rode o projeto com `python main.py`.
4. Teste pelo menos:
   - criação de corpo;
   - colisão;
   - troca de abas;
   - mover corpo;
   - salvar/carregar.
5. Abra pull request para `Dev`.

## Padrão de código

- Interface e textos em PT-BR.
- Unidades exibidas em padrão brasileiro.
- Fórmulas físicas devem ficar em `physics/` sempre que possível.
- Renderização deve ficar em `visuals/`.
- `main.py` deve perder responsabilidades aos poucos.
