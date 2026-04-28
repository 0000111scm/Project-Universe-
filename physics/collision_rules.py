"""Regras de colisão por família de corpos celestes.

Este módulo é a próxima casa das decisões físicas que ainda estão em `simulation.py`.
Por enquanto ele documenta e centraliza os nomes/categorias para evitar mágica espalhada.
"""

COLLISION_KIND_DESCRIPTIONS = {
    "galactic_merge": "Galáxias atravessam e fundem halos de massa; não geram explosão local comum.",
    "blackhole_merge": "Buracos negros/objetos compactos absorvem massa e podem emitir evento visual intenso.",
    "compact_merge": "Estrelas de nêutrons, pulsares e magnetars se fundem como objetos compactos.",
    "stellar_merge": "Estrelas colidem como fusão/nova visual, sem avalanche de fragmentos sólidos.",
    "stellar_absorb": "Estrela engole corpo menor, aquece e pode ejetar pequena quantidade de matéria.",
    "absorb": "Corpo grande absorve corpo pequeno com perda parcial para ejecta.",
    "merge": "Corpos comparáveis em baixa velocidade se fundem conservando momento.",
    "fragment": "Impacto médio gera detritos.",
    "shatter": "Impacto extremo estilhaça o menor e arranca massa do maior.",
}


def describe_collision(kind: str) -> str:
    return COLLISION_KIND_DESCRIPTIONS.get(kind, "Colisão genérica.")
