# Project Universe - Visual Upgrade 1

## O que mudou

- Fundo espacial refeito com aparência mais realista.
- Três camadas de parallax para sensação de profundidade.
- Nebulosas mais suaves e menos saturadas.
- Estrelas menos coloridas/arcade e mais próximas de observação astronômica.
- Estrelas brilhantes com glow discreto e spikes raros.
- `main.py` agora usa `create_space_layers()` e `draw_space_background()`.

## Arquivos alterados

- `main.py`
- `visuals/background.py`

## Como testar

Rode:

```bash
python main.py
```

Movimente a câmera e use zoom. O fundo deve deslocar em camadas, criando profundidade.
