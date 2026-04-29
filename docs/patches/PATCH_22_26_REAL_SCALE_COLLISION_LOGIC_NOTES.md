# Patch 22–26 — Escala física, colisão por energia e base SPH

## Foco
Prioridade total em lógica, matemática e coerência física.

## Implementado
- Separação entre propriedades físicas reais e escala visual comprimida:
  - `physical_mass_kg`
  - `physical_radius_km`
  - `density_kg_m3`
  - `family`
  - `material`
  - `composition`
- Catálogo ajustado automaticamente com dados físicos aproximados para planetas, luas, estrelas, buracos negros e galáxias.
- Escala visual logarítmica/comprimida:
  - Terra continua legível.
  - Sol fica maior que planetas.
  - Galáxias ficam muito maiores que planetas.
- Colisão agora usa:
  - massa física;
  - raio físico;
  - velocidade relativa;
  - energia de impacto;
  - energia específica;
  - razão de massa;
  - família do corpo;
  - material dominante.
- Asteroide visual/fisicamente maior que a Terra não é mais tratado como corpo pequeno absorvido pela Terra.
- Galáxias usam acreção/fusão galáctica, não colisão planetária comum.
- Buracos negros usam acreção.
- Estrelas podem fundir, acrecionar planetas ou colapsar para remanescente.
- Fragmentos carregam material, composição e massa física estimada.
- Base SPH criada em `physics/sph.py`.

## Ainda não é SPH completo
Este patch cria a ponte física para SPH. O solver hidrodinâmico real, com pressão/densidade/vizinhança, fica para a próxima fase.
