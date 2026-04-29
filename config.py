# Configurações globais do Project Universe

WIDTH, HEIGHT = 1280, 800
PANEL_W = 280
SIM_W = WIDTH - PANEL_W
FPS = 60
G = 0.6006  # escala corrigida: preserva velocidades orbitais com M_SOL realista
M_SOL = 3.33e8  # Terra=1e3; Sol≈333000 Terras
HAB_SCALE = 150.0  # px ≈ 1 UA

BG_W = SIM_W * 3
BG_H = HEIGHT * 3

TIME_SCALES = [0.5, 1.0, 2.0, 5.0]

SAVE_FILE = "universe_save.json"
SAVE_SLOTS = [f"universe_save_slot{i}.json" for i in range(1, 4)]

COLLISION_COLORS = {
    "merge": (200, 180, 100),
    "nova": (255, 200, 50),
    "blackhole": (180, 50, 255),
    "absorb": (255, 120, 50),
}
