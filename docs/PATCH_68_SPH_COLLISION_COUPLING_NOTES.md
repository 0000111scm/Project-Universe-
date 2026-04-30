# PATCH 68 — SPH Collision Coupling

Agora o SPH começa a afetar o resultado físico:
- partículas têm fase: sólido/magma/vapor/plasma
- pressão das partículas aumenta dano
- temperatura das partículas aquece o corpo
- partículas acima da velocidade de escape geram perda de massa
- massa SPH pode virar detrito rígido leve

Ainda é híbrido:
- Body continua existindo
- SPH modela impacto local e material ejetado
- próximo passo: substituir colisão planetária por resolução SPH mais direta
