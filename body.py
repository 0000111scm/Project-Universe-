import pygame

class Body:
    def __init__(self, x, y, vx, vy, mass, radius, color, name=""):
        self.pos         = pygame.Vector2(x, y)
        self.vel         = pygame.Vector2(vx, vy)
        self.acc         = pygame.Vector2(0, 0)
        self.mass        = mass
        self.radius      = radius
        self.color       = color
        self.base_color  = color  # cor original para água visual
        self.name        = name
        self.trail       = []
        self.temperature = 300.0
        self.alive       = True
        # Propriedades físicas simuladas
        self.atmosphere  = 1.0 if mass >= 100 else 0.0   # 0–2 bar estimado
        self.water       = 1.0 if mass >= 500 else 0.0   # 0–1 cobertura
        self.has_life    = False
        self.age         = 0.0   # segundos de simulação
        self.show_label  = True
        self.label_timer = 0.0
        self.is_fragment = False
        # Estado ambiental dinâmico
        self.co2         = 0.0
        self.n2          = 0.0
        self.albedo      = 0.3
        self.water_vapor = 0.0
        self.ice_fraction= 0.0
        self.tidal_heat  = 0.0
        self.volcanism   = 0.0
        self.roche_stress= 0.0
        self.born_timer  = 0.0