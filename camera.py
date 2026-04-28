import pygame
from config import SIM_W, HEIGHT

def screen_to_world(sx, sy, cam, zoom, cx, cy):
    return pygame.Vector2(
        (sx - SIM_W / 2 + cx * zoom) / zoom - cam.x,
        (sy - HEIGHT / 2 + cy * zoom) / zoom - cam.y,
    )

def world_to_screen(pos, cam, zoom, cx, cy):
    return (
        int((pos.x + cam.x) * zoom + SIM_W / 2 - cx * zoom),
        int((pos.y + cam.y) * zoom + HEIGHT / 2 - cy * zoom),
    )
