"""Utilidades de painel/UI do Project Universe.

Valores medidos aparecem nas unidades reais usadas no Brasil.
Barras de habitabilidade são fatores de adequação, portanto continuam em porcentagem.
"""
import pygame

FACTOR_LABELS = {
    'temperatura': 'temp. adequada',
    'faixa térmica': 'temp. adequada',
    'água líquida': 'água líquida',
    'pressão': 'pressão adequada',
    'atmosfera': 'atm. adequada',
    'massa': 'massa adequada',
    'gravidade': 'gravidade adequada',
    'estrela': 'fluxo estelar',
    'proteção': 'proteção',
    'química': 'química',
    'risco físico': 'segurança física',
}


def factor_label(label):
    return FACTOR_LABELS.get(str(label), str(label))


def draw_factor_bar(screen, font, x, y, width, label, value):
    """Desenha uma barra de fator de habitabilidade.

    Ex.: "temp. adequada: 98%" significa adequação da temperatura para vida,
    não uma temperatura percentual. A temperatura real fica no painel em °C.
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
