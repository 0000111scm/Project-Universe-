# PATCH 81 — 3D Core Real Activation + Star/Planet Accretion

Cronograma:
- 3D core activation
- render 2D continua como projeção XY

Adicionado:
- Terra caindo no Sol estava gerando detritos rochosos absurdos

Correção:
- novo physics_core/stellar_accretion.py
- planeta/lua/asteroide colidindo com estrela vira stellar_accretion
- massa e momento transferidos para a estrela
- planeta é absorvido/vaporizado
- não gera fragmento rochoso
- pequena ejeção permitida só como plasma
