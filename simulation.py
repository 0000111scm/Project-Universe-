import pygame, math, random
from body import Body
from physics.celestial import (
    MASS_PLANET, MASS_STAR, MASS_BLACK_HOLE, MASS_GALAXY,
    body_class, collision_family, class_label, is_massive_persistent,
)

G                    = 200
# Ajustes do modelo de colisao intermediario.
# Nao e SPH ainda; e um degrau pragmatico entre "fundir tudo" e hidrodinamica real.
MERGE_SPEED          = 80.0
FRAGMENT_SPEED       = 250.0
ABSORB_RATIO_LIMIT   = 0.08
MAX_FRAGMENTS        = 10
MIN_FRAGMENT_MASS    = 0.5
FRAGMENT_LABEL_TIME  = 1.1
FRAGMENT_TRAIL_LIMIT = 45
BODY_TRAIL_LIMIT     = 300

# Proteções contra cascata de colisões.
MAX_BODIES           = 420
FRAGMENT_LIFETIME    = 10.0
COLLISION_COOLDOWN   = 0.35


def _clamp(value, low, high):
    return max(low, min(high, value))


def _weighted_color(a, b, ma, mb):
    total = max(ma + mb, 1e-9)
    return (
        int(_clamp((a[0] * ma + b[0] * mb) / total, 0, 255)),
        int(_clamp((a[1] * ma + b[1] * mb) / total, 0, 255)),
        int(_clamp((a[2] * ma + b[2] * mb) / total, 0, 255)),
    )


def _volume_radius(*radii):
    return max(1.0, sum(max(r, 0.1) ** 3 for r in radii) ** (1.0 / 3.0))


def classify_body(mass):
    return class_label(mass)


def merged_name(a, b, total_mass):
    """Evita nomes infinitos apos colisoes sucessivas."""
    dominant = a if a.mass >= b.mass else b
    smaller  = b if dominant is a else a
    ratio = smaller.mass / max(dominant.mass, 1e-9)

    # Impacto pequeno: o maior continua sendo reconhecivel.
    if ratio < ABSORB_RATIO_LIMIT and dominant.name:
        return dominant.name

    # Impacto entre corpos comparaveis: cria uma classe limpa.
    return f"{classify_body(total_mass)} Fundido"


class CollisionEvent:
    def __init__(self, pos, kind):
        self.pos   = pygame.Vector2(pos)
        self.kind  = kind
        self.timer = 0.4


class Simulation:
    def __init__(self):
        self.bodies           = []
        self.time_scale       = 0.5
        self.time_elapsed     = 0.0
        self.collision_events = []
        self.max_bodies       = MAX_BODIES
        self.performance_mode = False

    def _trim_for_new_body(self, reserve=1):
        """Remove detritos primeiro para abrir espaco para astros criados pelo usuario."""
        limit = getattr(self, "max_bodies", MAX_BODIES)
        while len(self.bodies) + reserve > limit:
            fragments = [b for b in self.bodies if getattr(b, "is_fragment", False)]
            if not fragments:
                return False
            victim = min(fragments, key=lambda b: (getattr(b, "life_timer", 0.0), b.mass))
            self.bodies.remove(victim)
        return True

    def can_add_body(self, reserve=1):
        if len(self.bodies) + reserve <= getattr(self, "max_bodies", MAX_BODIES):
            return True
        return any(getattr(b, "is_fragment", False) for b in self.bodies)

    def add_body(self, body):
        if not self._trim_for_new_body(1):
            return False
        self.bodies.append(body)
        return True

    def _compute_accelerations(self):
        for b in self.bodies:
            b.acc = pygame.Vector2(0.0, 0.0)
        n = len(self.bodies)
        for i in range(n):
            a = self.bodies[i]
            for j in range(i + 1, n):
                b = self.bodies[j]
                dx = b.pos.x - a.pos.x
                dy = b.pos.y - a.pos.y
                # Softening fisico/visual: evita estilingue numerico quando objetos enormes encostam.
                soft = max(25.0, (getattr(a, "radius", 1.0) + getattr(b, "radius", 1.0)) ** 2 * 0.08)
                ds2 = dx*dx + dy*dy + soft
                ds  = math.sqrt(ds2)
                ax  = G * b.mass * dx / (ds2 * ds)
                ay  = G * b.mass * dy / (ds2 * ds)
                bx  = G * a.mass * dx / (ds2 * ds)
                by  = G * a.mass * dy / (ds2 * ds)
                a.acc.x += ax; a.acc.y += ay
                b.acc.x -= bx; b.acc.y -= by

    def _separate(self, a, b):
        d = b.pos - a.pos
        dist = d.length()
        if dist < 0.001:
            d = pygame.Vector2(random.uniform(-1,1), random.uniform(-1,1))
            if d.length_squared() == 0:
                d = pygame.Vector2(1, 0)
            d = d.normalize()
            dist = 1.0
        overlap = a.radius + b.radius - dist
        if overlap > 0:
            push = d / dist * (overlap * 0.5)
            a.pos -= push
            b.pos += push

    def _collision_kind(self, a, b):
        """Decide colisao por familia fisica, massa e velocidade relativa."""
        relative_speed = (a.vel - b.vel).length()
        mass_ratio = min(a.mass, b.mass) / max(max(a.mass, b.mass), 1e-9)
        fam = collision_family(a, b)

        if fam == "galactic":
            return "galactic_merge"
        if fam == "black_hole":
            return "blackhole_merge"
        if fam == "compact":
            return "compact_merge"
        if fam == "stellar":
            return "stellar_merge"
        if fam == "star_body":
            return "stellar_absorb"

        if mass_ratio < ABSORB_RATIO_LIMIT:
            return "absorb"
        if relative_speed < MERGE_SPEED:
            return "merge"
        if relative_speed < FRAGMENT_SPEED:
            return "fragment"
        return "shatter"

    def _copy_surface_properties(self, target, a, b, ma, mb):
        total = max(ma + mb, 1e-9)
        target.base_color = getattr(target, "base_color", target.color)
        target.temperature = (getattr(a, "temperature", 300.0) * ma + getattr(b, "temperature", 300.0) * mb) / total
        target.atmosphere = (getattr(a, "atmosphere", 0.0) * ma + getattr(b, "atmosphere", 0.0) * mb) / total
        target.water      = (getattr(a, "water", 0.0) * ma + getattr(b, "water", 0.0) * mb) / total
        target.has_life   = getattr(a, "has_life", False) or getattr(b, "has_life", False)
        target.age        = min(getattr(a, "age", 0.0), getattr(b, "age", 0.0))

        # Campos opcionais usados no main.py.
        for attr, default in (("co2", 0.0), ("n2", 0.0), ("o2", 0.0), ("ch4", 0.0), ("surface_pressure", 0.0), ("albedo", 0.3)):
            av = getattr(a, attr, default)
            bv = getattr(b, attr, default)
            setattr(target, attr, (av * ma + bv * mb) / total)

    def _merge_bodies(self, a, b, kind="merge"):
        total_mass = a.mass + b.mass
        new_pos = (a.pos * a.mass + b.pos * b.mass) / total_mass
        new_vel = (a.vel * a.mass + b.vel * b.mass) / total_mass
        new_radius = _volume_radius(a.radius, b.radius)
        new_color = _weighted_color(a.color, b.color, a.mass, b.mass)
        new_name = merged_name(a, b, total_mass)

        old_a_mass, old_b_mass = a.mass, b.mass
        a.pos = new_pos
        a.vel = new_vel
        a.mass = total_mass
        a.radius = new_radius
        a.color = new_color
        a.name = new_name
        a.trail = []
        a.collision_cooldown = COLLISION_COOLDOWN
        self._copy_surface_properties(a, a, b, old_a_mass, old_b_mass)
        impact_energy = 0.5 * min(old_a_mass, old_b_mass) * (getattr(a, "vel", pygame.Vector2()).length_squared())
        a.impact_heat = min(1.0, impact_energy / max(total_mass * 50000.0, 1.0))
        a.temperature = max(getattr(a, "temperature", 300.0), 900.0 + a.impact_heat * 5000.0)
        self.collision_events.append(CollisionEvent(new_pos, kind))

    def _galactic_merge(self, a, b):
        big, small = (a, b) if a.mass >= b.mass else (b, a)
        self._merge_bodies(big, small, "merge")
        big.name = "Galaxia Fundida" if body_class(big) == "galaxy" else big.name
        big.collision_cooldown = COLLISION_COOLDOWN * 2
        return big, small

    def _blackhole_merge(self, a, b):
        big, small = (a, b) if a.mass >= b.mass else (b, a)
        retained = 0.97 if body_class(small) == "black_hole" else 0.92
        absorbed_mass = small.mass * retained
        total_mass = big.mass + absorbed_mass
        big.pos = (big.pos * big.mass + small.pos * absorbed_mass) / max(total_mass, 1e-9)
        big.vel = (big.vel * big.mass + small.vel * absorbed_mass) / max(total_mass, 1e-9)
        big.mass = total_mass
        big.radius = max(big.radius, _volume_radius(big.radius, small.radius * retained ** (1/3)))
        big.color = (35, 0, 70) if big.mass < 1e9 else (18, 0, 45)
        big.name = "BN Supermassivo" if big.mass >= 1e9 else "Buraco Negro"
        big.trail = []
        big.temperature = max(getattr(big, "temperature", 300.0), 5000.0)
        big.collision_cooldown = COLLISION_COOLDOWN * 2
        self.collision_events.append(CollisionEvent(big.pos, "blackhole"))
        return big, small

    def _stellar_absorb(self, a, b):
        star, other = (a, b) if body_class(a) == "star" else (b, a)
        retained = 0.96 if other.mass < star.mass * 0.05 else 0.9
        absorbed_mass = other.mass * retained
        total_mass = star.mass + absorbed_mass
        star.pos = (star.pos * star.mass + other.pos * absorbed_mass) / max(total_mass, 1e-9)
        star.vel = (star.vel * star.mass + other.vel * absorbed_mass) / max(total_mass, 1e-9)
        star.mass = total_mass
        star.radius = _volume_radius(star.radius, other.radius * retained ** (1/3))
        star.color = _weighted_color(star.color, other.color, star.mass, absorbed_mass)
        star.temperature = max(getattr(star, "temperature", 300.0), 3500.0 + (star.vel - other.vel).length() * 2.0)
        star.collision_cooldown = COLLISION_COOLDOWN
        self.collision_events.append(CollisionEvent(star.pos, "absorb"))
        return star, other

    def _absorb_body(self, big, small):
        # O corpo maior absorve parte da massa; parte vira ejecta visual/fisico.
        retained = 0.85
        absorbed_mass = small.mass * retained
        lost_mass = max(small.mass - absorbed_mass, 0.0)
        total_mass = big.mass + absorbed_mass

        new_pos = (big.pos * big.mass + small.pos * absorbed_mass) / total_mass
        new_vel = (big.vel * big.mass + small.vel * absorbed_mass) / total_mass
        old_big_mass = big.mass

        big.pos = new_pos
        big.vel = new_vel
        big.mass = total_mass
        big.radius = _volume_radius(big.radius, small.radius * (retained ** (1.0/3.0)))
        big.color = _weighted_color(big.color, small.color, old_big_mass, absorbed_mass)
        big.name = big.name or classify_body(big.mass)
        big.trail = []
        big.collision_cooldown = COLLISION_COOLDOWN
        self._copy_surface_properties(big, big, small, old_big_mass, absorbed_mass)
        big.temperature = max(getattr(big, "temperature", 300.0), 900.0 + (big.vel - small.vel).length() * 3.0)

        if lost_mass >= MIN_FRAGMENT_MASS:
            self._spawn_fragments(small, big, lost_mass, "crater", count_hint=4)
        self.collision_events.append(CollisionEvent(new_pos, "absorb"))

    def _spawn_fragments(self, source, collider, ejecta_mass, kind, count_hint=None):
        if ejecta_mass < MIN_FRAGMENT_MASS:
            return

        rel = source.vel - collider.vel
        rel_speed = max(rel.length(), 20.0)
        count = count_hint or int(_clamp(ejecta_mass / 5.0, 3, MAX_FRAGMENTS))
        count = int(_clamp(count, 1, MAX_FRAGMENTS))
        if getattr(self, "performance_mode", False):
            count = min(count, 4)
        fragment_mass = ejecta_mass / count
        if fragment_mass < MIN_FRAGMENT_MASS:
            count = max(1, int(ejecta_mass / MIN_FRAGMENT_MASS))
            fragment_mass = ejecta_mass / count

        away = source.pos - collider.pos
        if away.length_squared() == 0:
            away = pygame.Vector2(random.uniform(-1, 1), random.uniform(-1, 1))
        if away.length_squared() == 0:
            away = pygame.Vector2(1, 0)
        away = away.normalize()

        available_slots = max(0, getattr(self, "max_bodies", MAX_BODIES) - len(self.bodies))
        count = min(count, available_slots)
        if count <= 0:
            return

        for idx in range(count):
            angle = random.uniform(-0.9, 0.9)
            direction = away.rotate_rad(angle)
            speed = random.uniform(0.25, 0.85) * rel_speed + random.uniform(10, 45)
            pos = source.pos + direction * random.uniform(source.radius * 0.2, source.radius + 2)
            vel = (source.vel * 0.65 + collider.vel * 0.35) + direction * speed
            radius = max(1.0, source.radius * ((fragment_mass / max(source.mass, 1e-9)) ** (1.0/3.0)))
            frag = Body(pos.x, pos.y, vel.x, vel.y, fragment_mass, radius, source.color, "Fragmento")
            frag.base_color = getattr(source, "base_color", source.color)
            frag.is_fragment = True
            frag.show_label = False
            frag.label_timer = FRAGMENT_LABEL_TIME
            frag.temperature = max(getattr(source, "temperature", 300.0), 900.0 + rel_speed * 3.0)
            frag.atmosphere = 0.0
            frag.water = max(0.0, getattr(source, "water", 0.0) * 0.15)
            frag.has_life = False
            frag.age = 0.0
            frag.life_timer = FRAGMENT_LIFETIME * random.uniform(0.65, 1.35)
            frag.collision_cooldown = COLLISION_COOLDOWN
            self.bodies.append(frag)

        self.collision_events.append(CollisionEvent(source.pos, kind))

    def _fragment_collision(self, a, b, destructive=False):
        # O maior sobrevive; o menor vira detritos. Em impacto extremo, parte do maior tambem perde massa.
        big, small = (a, b) if a.mass >= b.mass else (b, a)
        rel_speed = (a.vel - b.vel).length()

        small_ejecta = small.mass * (0.75 if destructive else 0.45)
        small_absorbed = small.mass - small_ejecta
        damage = 0.04 if not destructive else min(0.18, 0.04 + rel_speed / 3000.0)
        big_ejecta = big.mass * damage if destructive else 0.0

        old_big_mass = big.mass
        big.mass = max(big.mass + small_absorbed - big_ejecta, MIN_FRAGMENT_MASS)
        big.vel = (big.vel * old_big_mass + small.vel * small_absorbed) / max(old_big_mass + small_absorbed, 1e-9)
        big.radius = max(1.0, big.radius * ((big.mass / max(old_big_mass, 1e-9)) ** (1.0/3.0)))
        big.color = _weighted_color(big.color, small.color, old_big_mass, small_absorbed)
        big.name = big.name or classify_body(big.mass)
        big.trail = []
        big.collision_cooldown = COLLISION_COOLDOWN
        big.temperature = max(getattr(big, "temperature", 300.0), 1000.0 + rel_speed * 3.5)

        self._spawn_fragments(small, big, small_ejecta, "shatter" if destructive else "fragment")
        if big_ejecta >= MIN_FRAGMENT_MASS:
            self._spawn_fragments(big, small, big_ejecta, "shatter", count_hint=6)

        self.collision_events.append(CollisionEvent((a.pos + b.pos) * 0.5, "shatter" if destructive else "fragment"))
        return big, small

    def check_collisions(self):
        n = len(self.bodies)
        i = 0
        while i < n:
            j = i + 1
            while j < n:
                a, b = self.bodies[i], self.bodies[j]
                if getattr(a, "collision_cooldown", 0.0) > 0 or getattr(b, "collision_cooldown", 0.0) > 0:
                    j += 1
                    continue

                if (a.pos - b.pos).length() < (a.radius + b.radius):
                    kind = self._collision_kind(a, b)

                    if kind == "galactic_merge":
                        survivor, removed = self._galactic_merge(a, b)
                        self.bodies.remove(removed)
                        n -= 1
                        if i >= n: break
                        if j >= n: continue
                    elif kind == "blackhole_merge":
                        survivor, removed = self._blackhole_merge(a, b)
                        self.bodies.remove(removed)
                        n -= 1
                        if i >= n: break
                        if j >= n: continue
                    elif kind == "compact_merge":
                        self._merge_bodies(a, b, "blackhole")
                        a.name = "Buraco Negro" if a.mass >= MASS_BLACK_HOLE else "Estrela de Neutrons"
                        self.bodies.pop(j)
                        n -= 1
                        continue
                    elif kind == "stellar_merge":
                        self._merge_bodies(a, b, "nova")
                        a.name = "Estrela Fundida" if a.mass < MASS_BLACK_HOLE else "Buraco Negro"
                        if a.mass >= MASS_BLACK_HOLE:
                            a.color = (45, 0, 90)
                            a.radius = max(6, min(a.radius, 16))
                        self.bodies.pop(j)
                        n -= 1
                        continue
                    elif kind == "stellar_absorb":
                        survivor, removed = self._stellar_absorb(a, b)
                        self.bodies.remove(removed)
                        n -= 1
                        if i >= n: break
                        if j >= n: continue
                    elif kind == "absorb":
                        big, small = (a, b) if a.mass >= b.mass else (b, a)
                        self._absorb_body(big, small)
                        self.bodies.remove(small)
                        n -= 1
                        if i >= n: break
                        if j >= n: continue
                    elif kind == "merge":
                        self._merge_bodies(a, b, "merge")
                        self.bodies.pop(j)
                        n -= 1
                        continue
                    elif kind == "fragment":
                        survivor, removed = self._fragment_collision(a, b, destructive=False)
                        self.bodies.remove(removed)
                        n -= 1
                        if i >= n: break
                        if j >= n: continue
                    else:
                        survivor, removed = self._fragment_collision(a, b, destructive=True)
                        self.bodies.remove(removed)
                        n -= 1
                        if i >= n: break
                        if j >= n: continue
                else:
                    j += 1
            i += 1

    def check_roche(self):
        """Fragmentação simplificada por limite de Roche.

        O cálculo fino fica em physics/environment.py, que marca body.roche_stress.
        Aqui só transformamos stress extremo em evento físico controlado.
        """
        for body in self.bodies[:]:
            if getattr(body, "is_fragment", False):
                continue
            if is_massive_persistent(body):
                continue
            stress = float(getattr(body, "roche_stress", 0.0))
            if getattr(body, "born_timer", 999.0) < 4.0:
                continue
            if stress < 0.96 or getattr(body, "collision_cooldown", 0.0) > 0:
                continue
            ejecta = body.mass * min(0.55, 0.20 + stress * 0.25)
            if ejecta < MIN_FRAGMENT_MASS:
                continue
            body.mass = max(MIN_FRAGMENT_MASS, body.mass - ejecta)
            body.radius = max(1.0, body.radius * (body.mass / max(body.mass + ejecta, 1e-9)) ** (1.0 / 3.0))
            body.temperature = max(float(getattr(body, "temperature", 300.0)), 1200.0)
            body.collision_cooldown = COLLISION_COOLDOWN * 2
            self._spawn_fragments(body, body, ejecta, "shatter", count_hint=6)
            self.collision_events.append(CollisionEvent(body.pos, "shatter"))

    def simulate_preview(self, new_body_data, steps=80, step_dt=0.4):
        ghosts = [Body(b.pos.x,b.pos.y,b.vel.x,b.vel.y,b.mass,b.radius,b.color,"") for b in self.bodies]
        nb = Body(new_body_data["pos"].x, new_body_data["pos"].y, new_body_data["vel"].x, new_body_data["vel"].y, new_body_data["mass"], new_body_data["radius"], new_body_data["color"], "")
        ghosts.append(nb)
        trail=[]
        for _ in range(steps):
            for b in ghosts: b.acc = pygame.Vector2(0,0)
            for ii in range(len(ghosts)):
                ga = ghosts[ii]
                for gb in ghosts[ii+1:]:
                    dx = gb.pos.x - ga.pos.x; dy = gb.pos.y - ga.pos.y
                    ds2 = dx*dx + dy*dy + 25.0
                    ds  = math.sqrt(ds2)
                    f   = G * ga.mass * gb.mass / ds2
                    ga.acc.x += f*dx/ds/ga.mass; ga.acc.y += f*dy/ds/ga.mass
                    gb.acc.x -= f*dx/ds/gb.mass; gb.acc.y -= f*dy/ds/gb.mass
            sdt = step_dt * self.time_scale * 0.08
            for b in ghosts:
                b.vel += b.acc * sdt
                b.pos += b.vel * sdt
            trail.append(pygame.Vector2(nb.pos))
        return trail

    def step(self, dt):
        # Protecao contra frame spike: evita que uma travada de FPS arremesse corpos para longe.
        dt = min(dt, 1.0 / 20.0)
        # Substeps adaptativos: mantém estabilidade com poucos corpos e evita queda brutal de FPS com detritos.
        if getattr(self, "performance_mode", False):
            SUB = 1 if len(self.bodies) > 80 else 2
        elif len(self.bodies) > 220:
            SUB = 1
        elif len(self.bodies) > 120:
            SUB = 2
        else:
            SUB = 4
        sdt = dt * self.time_scale * 0.08 / SUB
        self.time_elapsed += dt * self.time_scale * 0.08
        for _ in range(SUB):
            self._compute_accelerations()
            for b in self.bodies:
                b.vel += b.acc * sdt
                b.pos += b.vel * sdt
            self.check_collisions()
        for b in self.bodies[:]:
            b.age = getattr(b, "age", 0.0) + dt * self.time_scale
            b.born_timer = getattr(b, "born_timer", 999.0) + dt
            if getattr(b, "collision_cooldown", 0.0) > 0:
                b.collision_cooldown = max(0.0, b.collision_cooldown - dt)
            if getattr(b, "label_timer", 0.0) > 0:
                b.label_timer = max(0.0, b.label_timer - dt)
            if getattr(b, "is_fragment", False):
                life_speed = 1.8 if getattr(self, "performance_mode", False) else 1.0
                b.life_timer = getattr(b, "life_timer", FRAGMENT_LIFETIME) - dt * life_speed
                if b.life_timer <= 0 and b.mass < MASS_PLANET:
                    self.bodies.remove(b)
                    continue
                b.temperature = max(120.0, getattr(b, "temperature", 300.0) - dt * 45.0)

            b.trail.append((int(b.pos.x), int(b.pos.y)))
            trail_limit = FRAGMENT_TRAIL_LIMIT if getattr(b, "is_fragment", False) else BODY_TRAIL_LIMIT
            if len(b.trail) > trail_limit:
                b.trail = b.trail[-trail_limit:]
        for ev in self.collision_events[:]:
            ev.timer -= dt
            if ev.timer <= 0: self.collision_events.remove(ev)
