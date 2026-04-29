# Patch 27 — Colisão em fases

## Objetivo
Parar a fusão instantânea em colisões grandes. Agora impacto entre corpos comparáveis vira processo físico em etapas.

## Mudanças principais
- Adicionado `ImpactProcess`.
- Colisões grandes passam por fases:
  - contato;
  - onda de choque;
  - fragmentação;
  - reacréscimo;
  - estabilização.
- Terra + Vênus não vira mais apenas `Planeta Fundido` no mesmo frame.
- Durante o impacto:
  - corpos aquecem;
  - sofrem deformação visual registrada em atributo;
  - perdem massa para detritos;
  - velocidades relativas são amortecidas;
  - massa final é recalculada depois do processo.
- Fragmentos nascem com:
  - material;
  - temperatura alta;
  - vida útil;
  - rastro menor;
  - label oculto por padrão.
- Removidos círculos/ondas arcade em `draw_collision_events()`.
- Adicionado rótulo discreto do estágio físico: `impacto: contato`, `impacto: onda de choque`, etc.

## Arquivos alterados
- `simulation.py`
- `main.py`

## Limitação honesta
Ainda não é SPH real. Este patch cria a estrutura de processo físico. O SPH de verdade entra depois, usando pressão, densidade e vizinhança de partículas.

## Testes recomendados
1. Terra + Vênus em baixa velocidade.
2. Terra + Vênus em alta velocidade.
3. Asteroide pequeno contra Terra.
4. Asteroide grande contra Terra.
5. Estrela + planeta.

Resultado esperado:
- impactos grandes duram alguns segundos;
- há ejeção gradual de massa;
- fusão final ocorre depois do processo;
- menos poluição visual;
- sem anéis/círculos de explosão.
