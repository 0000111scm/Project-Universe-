import random
import pygame


def create_space_layers(width, height, seed=42):
    rng = random.Random(seed)
    layers = []
    configs = [
        (240, (80, 90, 120), 1, 0.12),
        (150, (130, 135, 155), 1, 0.25),
        (70,  (190, 190, 210), 2, 0.45),
    ]
    for count, base, max_r, parallax in configs:
        stars=[]
        for _ in range(count):
            stars.append((rng.randrange(width), rng.randrange(height), rng.randint(1, max_r), base, rng.random()))
        layers.append({"stars": stars, "parallax": parallax})

    dust=[]
    palette=[(25,18,45,18),(18,35,55,14),(50,24,18,12),(18,48,38,10)]
    for _ in range(22):
        dust.append((rng.randrange(width), rng.randrange(height), rng.randrange(120,420), rng.choice(palette)))
    return {"w": width, "h": height, "layers": layers, "dust": dust}


def draw_space_background(screen, data, cam, zoom, sim_w, height, low_quality=False):
    screen.fill((3, 4, 12))
    w, h = data["w"], data["h"]

    if not low_quality:
        dust_surf = pygame.Surface((sim_w, height), pygame.SRCALPHA)
        for x,y,r,color in data.get("dust", []):
            ox = int((x - cam.x * 0.04) % w) - w//3
            oy = int((y - cam.y * 0.04) % h) - h//3
            if -r < ox < sim_w+r and -r < oy < height+r:
                pygame.draw.circle(dust_surf, color, (ox, oy), r)
        screen.blit(dust_surf, (0,0))

    for layer in data["layers"]:
        par = layer["parallax"]
        for x,y,r,base,tw in layer["stars"]:
            ox = int((x - cam.x * par * 0.12) % w) - w//3
            oy = int((y - cam.y * par * 0.12) % h) - h//3
            if 0 <= ox < sim_w and 0 <= oy < height:
                pulse = 0 if low_quality else int(25 * tw)
                c = tuple(min(255, v + pulse) for v in base)
                pygame.draw.circle(screen, c, (ox, oy), r)
