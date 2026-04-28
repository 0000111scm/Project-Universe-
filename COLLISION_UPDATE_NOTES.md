# Project Universe - Collision Update

## O que foi alterado

Arquivo principal alterado:
- `simulation.py`

## Melhorias implementadas

### 1. Nomes de colisao corrigidos
Antes:
```text
Terra-Lua-Marte-Asteroide-Detritos
```

Agora:
```text
Terra
Planeta Fundido
Estrela Fundido
Fragmento 1
```

O corpo dominante preserva o nome quando absorve um corpo muito menor.

### 2. Tipos de colisao
O sistema agora separa colisao por velocidade relativa e razao de massa:

- `absorb`: corpo grande absorve corpo pequeno
- `merge`: corpos comparaveis se fundem em baixa velocidade
- `fragment`: impacto medio gera detritos
- `shatter`: impacto extremo estilhaca o corpo menor e arranca massa do maior

### 3. Conservacao basica
Ainda conserva massa/momento nos casos principais, mas agora permite perda parcial para fragmentos.

### 4. Fragmentos fisicos
Fragmentos sao novos objetos `Body`, com:
- massa propria
- raio proprio
- velocidade de ejeção
- temperatura elevada
- sem atmosfera
- pouca ou nenhuma agua

## Importante

Isto ainda nao e SPH real. E uma fase intermediaria correta para o projeto agora.
SPH deve vir depois que esse sistema estiver estavel.

## Teste recomendado

1. Rode `main.py`
2. Lance asteroides pequenos contra planetas grandes
3. Teste impactos lentos e rapidos
4. Observe se:
   - nomes nao crescem infinitamente
   - impactos pequenos preservam o corpo maior
   - impactos rapidos geram fragmentos
   - o FPS continua aceitavel

