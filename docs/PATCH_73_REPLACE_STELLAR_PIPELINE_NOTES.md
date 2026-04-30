# PATCH 73 — Replace Stellar Collision Pipeline

Mudança real:
- substitui merge estelar instantâneo por processo persistente
- adiciona physics_core/stellar_pipeline.py
- estrelas em colisão ficam em common envelope por vários frames
- ejeção contínua de plasma
- instabilidade acumulada
- colapso/fusão só quando o processo físico exige

O objetivo é quebrar o padrão antigo:
estrela + estrela -> plim -> estrela fundida

Agora:
estrela + estrela -> contato -> envelope comum -> envelope violento -> colapso/fusão/remanescente
