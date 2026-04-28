"""Utilidades de painel/UI do Project Universe.

Valores medidos aparecem nas unidades reais usadas no Brasil.
Barras de habitabilidade são fatores de adequação, portanto continuam em porcentagem.
"""
import pygame

FACTOR_LABELS = {
    'temperatura': 'faixa térmica',
    'água líquida': 'água líquida',
    'pressão': 'pressão útil',
    'atmosfera': 'atmosfera',
    'massa': 'massa',
    'gravidade': 'gravidade',
    'estrela': 'fluxo estelar',
    'proteção': 'proteção',
    'química': 'química',
    'risco físico': 'segurança física',
}


def factor_label(label):
    return FACTOR_LABELS.get(str(label), str(label))


def draw_factor_bar(screen, font, x, y, width, label, value):
    """Desenha uma barra de fator de habitabilidade.

    Ex.: "faixa térmica: 98%" significa que a temperatura atual está 98% adequada,
    não que a temperatura seja 98%. A temperatura medida fica no painel em °C.
    """
    value = max(0.0, min(1.0, float(value)))
    if value >= 0.72:
        color = (70, 210, 95)
    elif value >= 0.38:
        color = (210, 170, 70)
    else:
        color = (210, 80, 70)
    pygame.draw.rect(screen, (18, 22, 32), (x, y, width, 7), border_radius=3)
    pygame.draw.rect(screen, color, (x, y, int(width * value), 7), border_radius=3)
    txt = font.render(f"{factor_label(label)}: {int(value * 100)}%", True, (150, 165, 185))
    screen.blit(txt, (x, y - 11))
