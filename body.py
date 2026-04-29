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
        self.impact_marks = []
        self.impact_flash = 0.0
        self.spin = 0.0
        self.angular_velocity = 0.0
        self.material = "rock" if mass < 5e4 else "gas"
        self.composition = {
            "silicates": 0.55 if mass < 5e4 else 0.05,
            "metals": 0.25 if mass < 5e4 else 0.02,
            "h2o": self.water * 0.10,
            "volatiles": 0.10 if mass < 5e4 else 0.50,
        }