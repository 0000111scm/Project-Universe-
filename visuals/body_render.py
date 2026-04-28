"""Camada de renderização de corpos.

Patch 7 começa a tirar render do main.py. Ainda mantemos funções antigas lá para não
quebrar tudo de uma vez; este módulo guarda helpers reutilizáveis e será expandido.
"""
import pygame


def draw_selection_rings(screen, sx, sy, r, selected=False, followed=False):
    if selected:
        pygame.draw.circle(screen, (255, 255, 70), (sx, sy), r + 5, 1)
    if followed:
        pygame.draw.circle(screen, (50, 170, 255), (sx, sy), r + 8, 1)


def draw_temperature_badge(screen, sx, sy, r, body):
    temp = float(getattr(body, "temperature", 300.0))
    stress = float(getattr(body, "roche_stress", 0.0))
    if temp < 650 and stress <= 0:
        return
    alpha = 45 if temp < 1200 else 80
    color = (255, 120, 40, alpha) if temp >= 650 else (255, 60, 60, 55)
    rr = max(r + 3, int(r * (1.25 + min(temp / 5000.0, 0.8))))
    s = pygame.Surface((rr * 2 + 2, rr * 2 + 2), pygame.SRCALPHA)
    pygame.draw.circle(s, color, (rr + 1, rr + 1), rr, 1 if temp < 1200 else 2)
    screen.blit(s, (sx - rr - 1, sy - rr - 1))
