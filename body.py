import pygame

class Body:
    def __init__(self, x, y, vx, vy, mass, radius, color, name=""):
        self.pos         = pygame.Vector2(x, y)
        self.vel         = pygame.Vector2(vx, vy)
        self.acc         = pygame.Vector2(0, 0)
        self.mass        = mass
        self.radius      = radius
        self.color       = color
        self.base_color  = color
        self.name        = name
        self.trail       = []
        self.temperature = 300.0
        self.alive       = True
        self.atmosphere  = 1.0 if mass >= 100 else 0.0
        self.water       = 1.0 if mass >= 500 else 0.0
        self.has_life    = False
        self.age         = 0.0
        self.show_label  = True
        self.label_timer = 0.0
        self.is_fragment = False

        # Patch 29/30: base para fragmentos irregulares e impactos locais.
        self.material     = None
        self.density      = 1.0
        self.angular_velocity = 0.0
        self.rotation     = 0.0
        self.irregular_points = []
        self.surface_marks = []      # crateras/cicatrizes simples em 2D
        self.local_heat_points = []  # pontos quentes de impacto, base do grid futuro
        self.surface_grid = []       # Patch 31: grade local de superficie 2D
        self.impact_heat  = 0.0
        self.deformation  = 0.0
