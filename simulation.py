import pygame, math, random
from body import Body

G                    = 200
MASS_PLANET          = 5e2
MASS_STAR            = 8e5
MASS_BLACK_HOLE      = 5e6

# Patch 27: colisao em fases.
# Ainda nao e SPH real. O objetivo aqui e parar a fusao instantanea e
# transformar impactos grandes em um processo: contato, choque, fragmentacao,
# reacrecao e estabilizacao.
MERGE_SPEED          = 80.0
FRAGMENT_SPEED       = 250.0
ABSORB_RATIO_LIMIT   = 0.08
MAX_FRAGMENTS        = 7
MIN_FRAGMENT_MASS    = 0.5
FRAGMENT_LABEL_TIME  = 0.7
FRAGMENT_TRAIL_LIMIT = 24
BODY_TRAIL_LIMIT     = 300
MAX_BODIES           = 260
FRAGMENT_LIFETIME    = 10.0
COLLISION_COOLDOWN   = 0.45

# Duração visual/física dos impactos grandes.
IMPACT_PHASE_DURATION = 3.8
IMPACT_EJECTA_INTERVAL = 0.12
SURFACE_GRID_CELLS = 36



def _clamp(value, low, high):
    return max(low, min(high, value))


def _weighted_color(a, b, ma, mb):
    total = max(ma + mb, 1e-9)
    return (
        int(_clamp((a[0] * ma + b[0] * mb) / total, 0, 255)),
        int(_clamp((a[1] * ma + b[1] * mb) / total, 0, 255)),
        int(_clamp((a[2] * ma + b[2] * mb) / total, 0, 255)),
    )


def _heat_color(color, heat):
    """Aproxima aquecimento visual sem overlay arcade."""
    h = _clamp(heat, 0.0, 1.0)
    hot = (255, 225, 120) if h < 0.65 else (255, 245, 220)
    return tuple(int(color[i] * (1.0 - h) + hot[i] * h) for i in range(3))


def _volume_radius(*radii):
    return max(1.0, sum(max(r, 0.1) ** 3 for r in radii) ** (1.0 / 3.0))


def classify_body(mass):
    if mass >= 1e11: return "Galáxia"
    if mass >= 1e9:  return "BN Supermassivo"
    if mass >= MASS_BLACK_HOLE: return "Buraco Negro"
    if mass >= MASS_STAR: return "Estrela"
    if mass >= 5e4: return "Gigante Gasoso"
    if mass >= MASS_PLANET: return "Planeta"
    if mass >= 1e2: return "Planeta Anão"
    if mass >= 1e1: return "Lua"
    return "Fragmento"


def body_family(body):
    m = body.mass
    if m >= 1e11: return "galaxy"
    if m >= MASS_BLACK_HOLE or "Buraco Negro" in getattr(body, "name", "") or "BN" in getattr(body, "name", ""):
        return "black_hole"
    if m >= MASS_STAR: return "star"
    if m >= 5e4: return "gas_giant"
    if m >= MASS_PLANET: return "planet"
    if m >= 1e1: return "minor"
    return "debris"


def material_of(body):
    existing = getattr(body, "material", None)
    if existing:
        return existing
    fam = body_family(body)
    name = getattr(body, "name", "").lower()
    if fam == "star": return "plasma"
    if fam == "black_hole": return "singularity"
    if fam == "galaxy": return "stellar_system"
    if fam == "gas_giant": return "gas"
    if any(k in name for k in ["lua", "mercúrio", "mercurio", "aster", "meteoro", "detrito"]):
        return "rock"
    if any(k in name for k in ["europa", "encélado", "encelado", "cometa", "tritão", "tritao"]):
        return "ice"
    return "rock"




def density_of_material(material):
    # Densidade relativa simplificada para escala interna do projeto.
    return {
        "ice": 0.92,
        "rock": 3.3,
        "metal": 7.8,
        "gas": 0.25,
        "plasma": 0.05,
        "singularity": 99.0,
        "stellar_system": 0.001,
    }.get(material, 2.5)



def ensure_surface_grid(body, cells=SURFACE_GRID_CELLS):
    """Patch 31: grade de superficie 2D simplificada por faixas angulares."""
    if getattr(body, "surface_grid", None) and len(body.surface_grid) == cells:
        return body.surface_grid
    base_temp = float(getattr(body, "temperature", 300.0))
    mat = material_of(body)
    grid = []
    for i in range(cells):
        grid.append({
            "angle": (math.tau * i) / cells,
            "temperature": base_temp,
            "elevation": 0.0,
            "damage": 0.0,
            "melt": 0.0,
            "water": float(getattr(body, "water", 0.0)) / cells,
            "material": mat,
        })
    body.surface_grid = grid
    return grid


def apply_surface_impact(body, angle, energy_score, scrape_factor=0.0):
    grid = ensure_surface_grid(body)
    n = len(grid)
    if n == 0:
        return
    idx = int(((angle % math.tau) / math.tau) * n) % n
    width = 1 + int(_clamp(scrape_factor * 5.0, 0, 5))
    heat = _clamp(energy_score, 0.02, 1.8)
    for off in range(-width, width + 1):
        d = abs(off) / max(width + 1, 1)
        falloff = max(0.0, 1.0 - d)
        cell = grid[(idx + off) % n]
        cell["temperature"] = max(cell.get("temperature", 300.0), 650.0 + heat * 6200.0 * falloff)
        cell["damage"] = _clamp(cell.get("damage", 0.0) + heat * falloff * (0.35 + scrape_factor), 0.0, 1.0)
        cell["melt"] = _clamp(cell.get("melt", 0.0) + heat * falloff * 0.55, 0.0, 1.0)
        cell["elevation"] -= heat * falloff * (0.15 if scrape_factor > 0.45 else 0.08)


def cool_surface_grid(body, dt):
    grid = getattr(body, "surface_grid", None)
    if not grid:
        return
    ambient = float(getattr(body, "temperature", 300.0))
    for cell in grid:
        cell["temperature"] += (ambient - cell.get("temperature", ambient)) * min(1.0, dt * 0.035)
        cell["melt"] = max(0.0, cell.get("melt", 0.0) - dt * 0.018)
        cell["damage"] = max(0.0, cell.get("damage", 0.0) - dt * 0.002)

def _impact_angle_factor(a, b):
    """0 = frontal, 1 = raspante/tangencial."""
    rel_pos = b.pos - a.pos
    rel_vel = b.vel - a.vel
    if rel_pos.length_squared() <= 1e-9 or rel_vel.length_squared() <= 1e-9:
        return 0.0
    rp = rel_pos.normalize()
    rv = rel_vel.normalize()
    frontal = abs(rp.dot(rv))
    return _clamp(1.0 - frontal, 0.0, 1.0)


def _specific_impact_energy(a, b):
    rel_speed = (a.vel - b.vel).length()
    reduced_mass = (a.mass * b.mass) / max(a.mass + b.mass, 1e-9)
    energy = 0.5 * reduced_mass * rel_speed * rel_speed
    return energy / max(a.mass + b.mass, 1e-9), energy

def merged_name(a, b, total_mass):
    dominant = a if a.mass >= b.mass else b
    smaller  = b if dominant is a else a
    ratio = smaller.mass / max(dominant.mass, 1e-9)
    if ratio < ABSORB_RATIO_LIMIT and dominant.name:
        return dominant.name
    return f"{classify_body(total_mass)} pós-impacto"


class CollisionEvent:
    def __init__(self, pos, kind, label=""):
        self.pos   = pygame.Vector2(pos)
        self.kind  = kind
        self.label = label
        self.timer = 0.35


class ImpactProcess:
    """Representa uma colisao grande como processo, nao como fusao instantanea."""
    def __init__(self, a, b, kind, rel_speed, energy_score):
        self.a = a
        self.b = b
        self.kind = kind
        self.rel_speed = rel_speed
        self.energy_score = energy_score
        self.timer = 0.0
        self.duration = IMPACT_PHASE_DURATION * (1.0 + min(1.0, energy_score) * 0.5)
        self.ejecta_timer = 0.0
        self.stage = "contato"
        self.done = False
        self.center = (a.pos * a.mass + b.pos * b.mass) / max(a.mass + b.mass, 1e-9)
        self.initial_mass = a.mass + b.mass

    def bodies_alive(self, bodies):
        return self.a in bodies and self.b in bodies


class Simulation:
    def __init__(self):
        self.bodies           = []
        self.time_scale       = 0.5
        self.time_elapsed     = 0.0
        self.collision_events = []
        self.impact_processes = []
        self.max_bodies       = MAX_BODIES
        self.performance_mode = False

    def _trim_for_new_body(self, reserve=1):
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
        if not hasattr(body, "material"):
            body.material = material_of(body)
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
                ds2 = dx*dx + dy*dy + 25.0
                ds  = math.sqrt(ds2)
                f   = G * a.mass * b.mass / ds2
                fx  = f * dx / ds
                fy  = f * dy / ds
                a.acc.x += fx / a.mass; a.acc.y += fy / a.mass
                b.acc.x -= fx / b.mass; b.acc.y -= fy / b.mass

    def _impact_metrics(self, a, b):
        rel_speed = (a.vel - b.vel).length()
        mass_ratio = min(a.mass, b.mass) / max(max(a.mass, b.mass), 1e-9)
        reduced_mass = (a.mass * b.mass) / max(a.mass + b.mass, 1e-9)
        kinetic = 0.5 * reduced_mass * rel_speed * rel_speed
        # Patch 30: energia normalizada por energia de ligacao aproximada e densidade.
        da = density_of_material(material_of(a))
        db = density_of_material(material_of(b))
        binding_a = (a.mass * a.mass / max(a.radius, 1.0)) * max(0.25, da / 3.3)
        binding_b = (b.mass * b.mass / max(b.radius, 1.0)) * max(0.25, db / 3.3)
        binding_proxy = max(binding_a, binding_b, 1.0)
        angle_boost = 1.0 + _impact_angle_factor(a, b) * 0.35
        energy_score = (kinetic / binding_proxy) * angle_boost
        return rel_speed, mass_ratio, energy_score

    def _collision_kind(self, a, b):
        rel_speed, mass_ratio, energy_score = self._impact_metrics(a, b)
        fa, fb = body_family(a), body_family(b)

        if "black_hole" in (fa, fb):
            return "accretion"
        if "galaxy" in (fa, fb):
            return "galactic_accretion" if mass_ratio < 0.2 else "galaxy_merge"
        if fa == "star" and fb == "star":
            return "stellar_collision" if energy_score > 0.08 else "stellar_merge"
        if "star" in (fa, fb):
            return "stellar_accretion"

        # Planetas/corpos grandes comparaveis: processo em fases.
        if mass_ratio >= 0.18 and (a.mass >= MASS_PLANET or b.mass >= MASS_PLANET):
            if energy_score > 0.10 or rel_speed > FRAGMENT_SPEED:
                return "giant_impact_disruptive"
            return "giant_impact_merging"

        if mass_ratio < ABSORB_RATIO_LIMIT:
            return "cratering"
        if rel_speed < MERGE_SPEED:
            return "contact_merge"
        if rel_speed < FRAGMENT_SPEED:
            return "fragment"
        return "shatter"

    def _copy_surface_properties(self, target, a, b, ma, mb):
        total = max(ma + mb, 1e-9)
        target.base_color = getattr(target, "base_color", target.color)
        target.temperature = (getattr(a, "temperature", 300.0) * ma + getattr(b, "temperature", 300.0) * mb) / total
        target.atmosphere = (getattr(a, "atmosphere", 0.0) * ma + getattr(b, "atmosphere", 0.0) * mb) / total
        target.water      = (getattr(a, "water", 0.0) * ma + getattr(b, "water", 0.0) * mb) / total
        target.has_life   = False
        target.age        = min(getattr(a, "age", 0.0), getattr(b, "age", 0.0))
        target.material   = material_of(a) if ma >= mb else material_of(b)
        for attr, default in (("co2", 0.0), ("n2", 0.0), ("albedo", 0.3)):
            av = getattr(a, attr, default)
            bv = getattr(b, attr, default)
            setattr(target, attr, (av * ma + bv * mb) / total)

    def _merge_bodies(self, a, b, kind="merge", name=None):
        total_mass = a.mass + b.mass
        old_a_mass, old_b_mass = a.mass, b.mass
        a.pos = (a.pos * a.mass + b.pos * b.mass) / total_mass
        a.vel = (a.vel * a.mass + b.vel * b.mass) / total_mass
        a.mass = total_mass
        a.radius = _volume_radius(a.radius, b.radius)
        a.color = _weighted_color(a.color, b.color, old_a_mass, old_b_mass)
        a.name = name or merged_name(a, b, total_mass)
        a.trail = []
        a.collision_cooldown = COLLISION_COOLDOWN
        self._copy_surface_properties(a, a, b, old_a_mass, old_b_mass)
        a.temperature = max(getattr(a, "temperature", 300.0), 1400.0)
        a.impact_heat = 1.0
        a.deformation = 0.45

    def _absorb_body(self, big, small, retained=0.9):
        absorbed_mass = small.mass * retained
        lost_mass = max(small.mass - absorbed_mass, 0.0)
        total_mass = big.mass + absorbed_mass
        old_big_mass = big.mass
        big.pos = (big.pos * big.mass + small.pos * absorbed_mass) / total_mass
        big.vel = (big.vel * big.mass + small.vel * absorbed_mass) / total_mass
        big.mass = total_mass
        big.radius = _volume_radius(big.radius, small.radius * (retained ** (1.0/3.0)))
        big.color = _weighted_color(big.color, small.color, old_big_mass, absorbed_mass)
        big.name = big.name or classify_body(big.mass)
        big.trail = []
        big.collision_cooldown = COLLISION_COOLDOWN
        self._copy_surface_properties(big, big, small, old_big_mass, absorbed_mass)
        big.temperature = max(getattr(big, "temperature", 300.0), 900.0 + (big.vel - small.vel).length() * 2.0)
        big.impact_heat = min(1.0, getattr(big, "impact_heat", 0.0) + 0.55)
        if lost_mass >= MIN_FRAGMENT_MASS:
            self._spawn_fragments(small, big, lost_mass, "ejecta", count_hint=3)

    def _spawn_fragments(self, source, collider, ejecta_mass, kind, count_hint=None):
        if ejecta_mass < MIN_FRAGMENT_MASS:
            return
        rel = source.vel - collider.vel
        rel_speed = max(rel.length(), 20.0)
        mat = material_of(source)
        material_factor = {"ice": 1.4, "rock": 1.0, "metal": 0.75, "gas": 0.25, "plasma": 0.10}.get(mat, 1.0)
        count = count_hint or int(_clamp((ejecta_mass / 12.0) * material_factor, 2, MAX_FRAGMENTS))
        count = int(_clamp(count, 1, MAX_FRAGMENTS))
        if getattr(self, "performance_mode", False):
            count = min(count, 3)
        if not self._trim_for_new_body(count):
            count = min(count, max(0, self.max_bodies - len(self.bodies)))
        if count <= 0:
            return
        fragment_mass = ejecta_mass / count
        away = source.pos - collider.pos
        if away.length_squared() == 0:
            away = pygame.Vector2(random.uniform(-1, 1), random.uniform(-1, 1))
        if away.length_squared() == 0:
            away = pygame.Vector2(1, 0)
        away = away.normalize()
        tangent = pygame.Vector2(-away.y, away.x)
        for _ in range(count):
            direction = (away * random.uniform(0.55, 1.0) + tangent * random.uniform(-0.55, 0.55))
            if direction.length_squared() == 0:
                direction = away
            direction = direction.normalize()
            speed = random.uniform(0.18, 0.65) * rel_speed + random.uniform(8, 34)
            pos = source.pos + direction * random.uniform(source.radius * 0.25, source.radius + 3)
            vel = (source.vel * 0.72 + collider.vel * 0.28) + direction * speed
            radius = max(1.0, source.radius * ((fragment_mass / max(source.mass, 1e-9)) ** (1.0/3.0)))
            frag = Body(pos.x, pos.y, vel.x, vel.y, fragment_mass, radius, _heat_color(source.color, 0.35), "Fragmento")
            frag.base_color = getattr(source, "base_color", source.color)
            frag.material = mat
            frag.density = density_of_material(mat)
            frag.angular_velocity = random.uniform(-4.0, 4.0) * (1.0 + rel_speed / 450.0)
            frag.rotation = random.uniform(0.0, math.tau)
            # Convex-hull fake 2D: pontos irregulares normalizados para render atual.
            verts = random.randint(6, 10)
            frag.irregular_points = []
            for vi in range(verts):
                ang = (math.tau * vi / verts) + random.uniform(-0.18, 0.18)
                rr = random.uniform(0.62, 1.18)
                frag.irregular_points.append((math.cos(ang) * rr, math.sin(ang) * rr))
            frag.is_fragment = True
            frag.show_label = False
            frag.label_timer = FRAGMENT_LABEL_TIME
            frag.temperature = max(getattr(source, "temperature", 300.0), 900.0 + rel_speed * 2.5)
            frag.atmosphere = 0.0
            frag.water = max(0.0, getattr(source, "water", 0.0) * 0.08)
            frag.has_life = False
            frag.age = 0.0
            frag.life_timer = FRAGMENT_LIFETIME * random.uniform(0.7, 1.25)
            frag.collision_cooldown = COLLISION_COOLDOWN
            frag.impact_heat = 1.0
            frag.deformation = random.uniform(0.2, 0.8)
            self.bodies.append(frag)


    def _register_impact_mark(self, target, projectile, energy_score, scrape_factor):
        """Patch 30: registra cratera/cicatriz local. Base simples antes do surface grid real."""
        if not hasattr(target, "surface_marks"):
            target.surface_marks = []
        if not hasattr(target, "local_heat_points"):
            target.local_heat_points = []

        rel = projectile.pos - target.pos
        angle = math.atan2(rel.y, rel.x) if rel.length_squared() > 1e-9 else random.random() * math.tau
        severity = _clamp(energy_score * 4.0, 0.05, 1.0)
        mark_type = "cicatriz" if scrape_factor > 0.45 else "cratera"
        mark = {
            "type": mark_type,
            "angle": angle,
            "severity": severity,
            "width": _clamp(projectile.radius / max(target.radius, 1.0), 0.03, 0.8),
            "length": _clamp((1.0 + scrape_factor * 5.0) * projectile.radius / max(target.radius, 1.0), 0.05, 2.2),
            "life": 9999.0,
        }
        target.surface_marks.append(mark)
        target.surface_marks = target.surface_marks[-16:]

        heat = {
            "angle": angle,
            "temperature": 900.0 + severity * 5200.0,
            "radius": mark["width"],
            "life": 14.0 + severity * 35.0,
        }
        target.local_heat_points.append(heat)
        target.local_heat_points = target.local_heat_points[-20:]

    def _apply_impact_energy(self, a, b, energy_score):
        """Converte parte da energia cinetica em calor/deformacao/ejecta."""
        specific_e, _ = _specific_impact_energy(a, b)
        temp_boost = min(18000.0, specific_e * 0.015 + energy_score * 2600.0)
        for body in (a, b):
            body.temperature = max(getattr(body, "temperature", 300.0), 300.0 + temp_boost)
            body.impact_heat = min(1.0, getattr(body, "impact_heat", 0.0) + _clamp(energy_score * 3.0, 0.15, 1.0))
            body.deformation = min(0.95, getattr(body, "deformation", 0.0) + _clamp(energy_score * 1.8, 0.05, 0.75))

    def _start_impact_process(self, a, b, kind):
        rel_speed, _, energy_score = self._impact_metrics(a, b)
        scrape = _impact_angle_factor(a, b)
        target, projectile = (a, b) if a.mass >= b.mass else (b, a)
        self._register_impact_mark(target, projectile, energy_score, scrape)
        self._apply_impact_energy(a, b, energy_score)
        a.collision_cooldown = b.collision_cooldown = COLLISION_COOLDOWN * 2.0
        a.impact_heat = b.impact_heat = 1.0
        a.deformation = max(getattr(a, "deformation", 0.0), 0.55)
        b.deformation = max(getattr(b, "deformation", 0.0), 0.55)
        process = ImpactProcess(a, b, kind, rel_speed, energy_score)
        process.scrape_factor = scrape
        self.impact_processes.append(process)

    def _update_impact_processes(self, dt):
        for p in self.impact_processes[:]:
            if not p.bodies_alive(self.bodies):
                self.impact_processes.remove(p)
                continue
            scaled_dt = dt * max(0.25, self.time_scale)
            p.timer += scaled_dt
            p.ejecta_timer += dt
            t = _clamp(p.timer / max(p.duration, 1e-6), 0.0, 1.0)
            if t < 0.16:
                p.stage = "contato"
            elif t < 0.42:
                p.stage = "compressão/choque"
            elif t < 0.72:
                p.stage = "ejeção de massa"
            else:
                p.stage = "reacréscimo"

            a, b = p.a, p.b
            rel = b.pos - a.pos
            dist = rel.length()
            direction = rel.normalize() if dist > 1e-6 else pygame.Vector2(1, 0)
            tangent = pygame.Vector2(-direction.y, direction.x)
            contact_dist = max(1.0, (a.radius + b.radius) * (0.72 - 0.18 * min(t, 0.9)))

            # Patch 31: acabou o efeito "gruda e explode".
            # O contato comprime, cisalha e ejeta material sem colapsar os centros no mesmo ponto.
            overlap = contact_dist - dist
            if overlap > 0:
                total = max(a.mass + b.mass, 1e-9)
                push = direction * min(overlap * 0.42, max(a.radius, b.radius) * 0.10)
                a.pos -= push * (b.mass / total)
                b.pos += push * (a.mass / total)

            rel_vel = b.vel - a.vel
            normal_speed = rel_vel.dot(direction)
            tangent_speed = rel_vel.dot(tangent)

            # Choque inelástico gradual: remove penetração, preserva cisalhamento.
            if normal_speed < 0:
                impulse = direction * (-normal_speed) * (0.10 + 0.18 * min(t, 0.55))
                total = max(a.mass + b.mass, 1e-9)
                a.vel -= impulse * (b.mass / total)
                b.vel += impulse * (a.mass / total)

            scrape = getattr(p, "scrape_factor", 0.0)
            shear = tangent * tangent_speed * min(0.035 + scrape * 0.05, 0.09)
            total = max(a.mass + b.mass, 1e-9)
            a.vel += shear * (b.mass / total)
            b.vel -= shear * (a.mass / total)
            a.angular_velocity = getattr(a, "angular_velocity", 0.0) + tangent_speed * 0.0009 * scrape
            b.angular_velocity = getattr(b, "angular_velocity", 0.0) - tangent_speed * 0.0009 * scrape

            # Só no reacréscimo final as velocidades caminham para o baricentro.
            if t > 0.72:
                common_vel = (a.vel * a.mass + b.vel * b.mass) / total
                blend = min(0.035, dt * 0.25) * ((t - 0.72) / 0.28)
                a.vel = a.vel.lerp(common_vel, blend)
                b.vel = b.vel.lerp(common_vel, blend)

            heat = max(0.12, 1.0 - t * 0.72)
            a.impact_heat = max(getattr(a, "impact_heat", 0.0), heat)
            b.impact_heat = max(getattr(b, "impact_heat", 0.0), heat)
            deformation = 0.30 + 0.45 * (1.0 - abs(0.45 - t))
            a.deformation = max(getattr(a, "deformation", 0.0), deformation * (1.0 - t * 0.45))
            b.deformation = max(getattr(b, "deformation", 0.0), deformation * (1.0 - t * 0.45))
            a.temperature = max(getattr(a, "temperature", 300.0), 850.0 + p.rel_speed * 2.0)
            b.temperature = max(getattr(b, "temperature", 300.0), 850.0 + p.rel_speed * 2.0)

            if p.ejecta_timer >= IMPACT_EJECTA_INTERVAL and p.stage in ("compressão/choque", "ejeção de massa"):
                p.ejecta_timer = 0.0
                source, collider = (a, b) if random.random() < 0.5 else (b, a)
                escore = max(0.03, p.energy_score)
                self._register_impact_mark(source, collider, escore, scrape)
                ejecta = min(source.mass * random.uniform(0.0025, 0.010), p.initial_mass * 0.018)
                if ejecta >= MIN_FRAGMENT_MASS:
                    self._spawn_fragments(source, collider, ejecta, "ejecta", count_hint=1 if self.performance_mode else 2)
                    source.mass = max(source.mass - ejecta, MIN_FRAGMENT_MASS)
                    source.radius = max(1.0, source.radius * ((source.mass + ejecta) / max(source.mass, 1e-9)) ** (-1.0/12.0))

            if p.timer >= p.duration:
                self._finish_impact_process(p)
                self.impact_processes.remove(p)

    def _finish_impact_process(self, p):
        if not p.bodies_alive(self.bodies):
            return
        a, b = p.a, p.b
        rel_speed, mass_ratio, energy_score = self._impact_metrics(a, b)
        total = max(a.mass + b.mass, 1e-9)

        # Patch 31: finalização menos brusca. A massa foi ejetada durante o processo;
        # aqui só consolida o remanescente.
        if p.kind == "giant_impact_disruptive" or energy_score > 0.18:
            ejecta = total * _clamp(0.04 + energy_score * 0.18, 0.04, 0.22)
            source, collider = (a, b) if a.mass < b.mass else (b, a)
            if ejecta >= MIN_FRAGMENT_MASS:
                self._spawn_fragments(source, collider, ejecta, "debris_field", count_hint=min(MAX_FRAGMENTS, 5))
                a.mass = max(MIN_FRAGMENT_MASS, a.mass - ejecta * (a.mass / total))
                b.mass = max(MIN_FRAGMENT_MASS, b.mass - ejecta * (b.mass / total))
            final_name = "Remanescente pós-impacto"
        else:
            final_name = "Protoplaneta em reacréscimo"

        primary, secondary = (a, b) if a.mass >= b.mass else (b, a)
        self._merge_bodies(primary, secondary, "impact_settled", name=final_name)
        primary.impact_heat = max(getattr(primary, "impact_heat", 0.0), 0.65)
        primary.deformation = max(getattr(primary, "deformation", 0.0), 0.35)
        primary.angular_velocity = getattr(primary, "angular_velocity", 0.0) + (a.vel - b.vel).length() * 0.0005
        ensure_surface_grid(primary)
        if secondary in self.bodies:
            self.bodies.remove(secondary)

    def _fragment_collision(self, a, b, destructive=False):
        big, small = (a, b) if a.mass >= b.mass else (b, a)
        rel_speed = (a.vel - b.vel).length()
        small_ejecta = small.mass * (0.70 if destructive else 0.40)
        small_absorbed = small.mass - small_ejecta
        damage = 0.03 if not destructive else min(0.16, 0.04 + rel_speed / 3500.0)
        big_ejecta = big.mass * damage if destructive else 0.0
        old_big_mass = big.mass
        big.mass = max(big.mass + small_absorbed - big_ejecta, MIN_FRAGMENT_MASS)
        big.vel = (big.vel * old_big_mass + small.vel * small_absorbed) / max(old_big_mass + small_absorbed, 1e-9)
        big.radius = max(1.0, big.radius * ((big.mass / max(old_big_mass, 1e-9)) ** (1.0/3.0)))
        big.color = _weighted_color(big.color, small.color, old_big_mass, small_absorbed)
        big.name = big.name or classify_body(big.mass)
        big.trail = []
        big.collision_cooldown = COLLISION_COOLDOWN
        big.temperature = max(getattr(big, "temperature", 300.0), 1000.0 + rel_speed * 2.5)
        big.impact_heat = min(1.0, getattr(big, "impact_heat", 0.0) + 0.7)
        _, _, escore = self._impact_metrics(big, small)
        self._register_impact_mark(big, small, escore, _impact_angle_factor(big, small))
        self._spawn_fragments(small, big, small_ejecta, "fragment", count_hint=4 if destructive else 2)
        if big_ejecta >= MIN_FRAGMENT_MASS:
            self._spawn_fragments(big, small, big_ejecta, "shatter", count_hint=4)
        return big, small

    def _already_in_impact(self, a, b):
        for p in self.impact_processes:
            if (p.a is a and p.b is b) or (p.a is b and p.b is a):
                return True
        return False

    def check_collisions(self):
        n = len(self.bodies)
        i = 0
        while i < n:
            j = i + 1
            while j < n:
                a, b = self.bodies[i], self.bodies[j]
                if self._already_in_impact(a, b):
                    j += 1
                    continue
                if getattr(a, "collision_cooldown", 0.0) > 0 or getattr(b, "collision_cooldown", 0.0) > 0:
                    j += 1
                    continue
                if (a.pos - b.pos).length() < (a.radius + b.radius):
                    kind = self._collision_kind(a, b)
                    if kind in ("giant_impact_merging", "giant_impact_disruptive", "stellar_collision"):
                        self._start_impact_process(a, b, kind)
                        j += 1
                        continue
                    elif kind in ("stellar_merge", "contact_merge"):
                        self._merge_bodies(a, b, kind)
                        self.bodies.pop(j)
                        n -= 1
                        continue
                    elif kind in ("accretion", "galactic_accretion", "stellar_accretion"):
                        big, small = (a, b) if a.mass >= b.mass else (b, a)
                        retained = 0.98 if kind == "accretion" else 0.88
                        self._absorb_body(big, small, retained=retained)
                        if small in self.bodies:
                            self.bodies.remove(small)
                        n -= 1
                        if i >= n: break
                        if j >= n: continue
                    elif kind == "galaxy_merge":
                        self._merge_bodies(a, b, "galaxy_merge", name="Galáxia em fusão")
                        self.bodies.pop(j)
                        n -= 1
                        continue
                    elif kind == "cratering":
                        big, small = (a, b) if a.mass >= b.mass else (b, a)
                        _, _, escore = self._impact_metrics(big, small)
                        self._register_impact_mark(big, small, escore, _impact_angle_factor(big, small))
                        self._apply_impact_energy(big, small, escore)
                        self._absorb_body(big, small, retained=0.72)
                        if small in self.bodies:
                            self.bodies.remove(small)
                        n -= 1
                        if i >= n: break
                        if j >= n: continue
                    elif kind == "fragment":
                        _, removed = self._fragment_collision(a, b, destructive=False)
                        if removed in self.bodies:
                            self.bodies.remove(removed)
                        n -= 1
                        if i >= n: break
                        if j >= n: continue
                    else:
                        _, removed = self._fragment_collision(a, b, destructive=True)
                        if removed in self.bodies:
                            self.bodies.remove(removed)
                        n -= 1
                        if i >= n: break
                        if j >= n: continue
                else:
                    j += 1
            i += 1

    def _apply_atmospheric_drag(self, body, dt):
        """Patch 28: arrasto atmosferico simples para meteoros."""
        if body.mass <= 0 or body_family(body) in ("star", "black_hole", "galaxy"):
            return

        for planet in self.bodies:
            if planet is body:
                continue
            if body_family(planet) not in ("planet", "gas_giant", "moon"):
                continue

            atm = max(0.0, getattr(planet, "atmosphere", 0.0))
            if atm <= 0.01:
                continue

            offset = body.pos - planet.pos
            dist = max(offset.length(), 0.001)
            surface_r = max(planet.radius, 1.0)
            atmosphere_r = surface_r * (1.0 + min(5.0, 1.4 + atm * 1.25))

            if dist <= surface_r or dist > atmosphere_r:
                continue

            altitude01 = (dist - surface_r) / max(atmosphere_r - surface_r, 0.001)
            density = atm * max(0.0, 1.0 - altitude01) ** 2
            rel_vel = body.vel - planet.vel
            speed = rel_vel.length()
            if speed < 1.0:
                continue

            direction = rel_vel.normalize()
            area_factor = max(0.015, min(0.25, (body.radius / max(surface_r, 1.0)) ** 2))
            drag_acc = density * speed * speed * area_factor * 0.000020
            drag_acc = min(drag_acc, speed / max(dt, 1e-5) * 0.35)

            body.vel -= direction * drag_acc * dt
            body.temperature = max(getattr(body, "temperature", 300.0), 300.0 + drag_acc * speed * 0.18)
            body.impact_heat = min(1.0, getattr(body, "impact_heat", 0.0) + min(0.35, drag_acc * 0.002))

            if speed > 160.0 and body.mass < MASS_PLANET:
                loss = min(body.mass * 0.018, density * speed * 0.00012 * dt)
                body.mass = max(MIN_FRAGMENT_MASS * 0.25, body.mass - loss)
                if hasattr(body, "radius") and body.mass > 0:
                    body.radius = max(0.6, body.radius * (1.0 - min(0.02, loss / max(body.mass, 1e-6))))
            break

    def check_roche(self):
        pass

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
        self._update_impact_processes(dt)
        for b in self.bodies[:]:
            b.age = getattr(b, "age", 0.0) + dt * self.time_scale
            if getattr(b, "collision_cooldown", 0.0) > 0:
                b.collision_cooldown = max(0.0, b.collision_cooldown - dt)
            if getattr(b, "label_timer", 0.0) > 0:
                b.label_timer = max(0.0, b.label_timer - dt)
            if getattr(b, "impact_heat", 0.0) > 0:
                b.impact_heat = max(0.0, b.impact_heat - dt * 0.35)
            if getattr(b, "deformation", 0.0) > 0:
                b.deformation = max(0.0, b.deformation - dt * 0.22)
            if getattr(b, "angular_velocity", 0.0):
                b.rotation = getattr(b, "rotation", 0.0) + b.angular_velocity * dt
                b.angular_velocity *= max(0.0, 1.0 - dt * 0.015)
            if hasattr(b, "local_heat_points"):
                for hp in b.local_heat_points[:]:
                    hp["life"] = hp.get("life", 0.0) - dt
                    hp["temperature"] = max(120.0, hp.get("temperature", 300.0) - dt * 75.0)
                    if hp["life"] <= 0:
                        b.local_heat_points.remove(hp)
            cool_surface_grid(b, dt * self.time_scale)
            self._apply_atmospheric_drag(b, dt * self.time_scale)
            if getattr(b, "is_fragment", False):
                life_speed = 1.8 if getattr(self, "performance_mode", False) else 1.0
                b.life_timer = getattr(b, "life_timer", FRAGMENT_LIFETIME) - dt * life_speed
                if b.life_timer <= 0 and b.mass < MASS_PLANET:
                    self.bodies.remove(b)
                    continue
                b.temperature = max(120.0, getattr(b, "temperature", 300.0) - dt * 42.0)
            if getattr(b, "impact_heat", 0.0) > 0:
                base = getattr(b, "base_color", b.color)
                b.color = _heat_color(base, getattr(b, "impact_heat", 0.0))
            b.trail.append((int(b.pos.x), int(b.pos.y)))
            trail_limit = FRAGMENT_TRAIL_LIMIT if getattr(b, "is_fragment", False) else BODY_TRAIL_LIMIT
            if len(b.trail) > trail_limit:
                b.trail = b.trail[-trail_limit:]
        for ev in self.collision_events[:]:
            ev.timer -= dt
            if ev.timer <= 0: self.collision_events.remove(ev)
