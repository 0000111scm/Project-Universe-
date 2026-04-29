import pygame, math, random, colorsys
from body import Body
from physics.impact_solver import ImpactInput, ImpactType, solve_impact
from physics.material_model import infer_material, material_pair_response, mixed_strength
from physics.angular_momentum import directional_ejecta_vector, merged_angular_velocity, spin_kick_from_impact
from physics.structural_damage import apply_structural_damage, ensure_structure, relax_structure

G                    = 200
MASS_PLANET          = 5e2
MASS_STAR            = 8e5
MASS_BLACK_HOLE      = 5e6

# Ajustes do modelo de colisao intermediario.
# Nao e SPH ainda; e um degrau pragmatico entre "fundir tudo" e hidrodinamica real.
MERGE_SPEED          = 80.0
FRAGMENT_SPEED       = 250.0
ABSORB_RATIO_LIMIT   = 0.08
MAX_FRAGMENTS        = 8
MIN_FRAGMENT_MASS    = 0.5
FRAGMENT_LABEL_TIME  = 1.1
FRAGMENT_TRAIL_LIMIT = 45
BODY_TRAIL_LIMIT     = 300

# Proteções contra cascata de colisões.
MAX_BODIES           = 180
FRAGMENT_LIFETIME    = 12.0
COLLISION_COOLDOWN   = 0.55


def _clamp(value, low, high):
    return max(low, min(high, value))

def _escape_velocity_proxy(body):
    """Proxy estável para velocidade de escape dentro da escala do protótipo."""
    return math.sqrt(max(getattr(body, "mass", 0.0), 0.0) / max(getattr(body, "radius", 1.0), 1.0))


def _estimate_atmospheric_loss(target, impact, projectile_mass=0.0):
    """Perda atmosférica por impacto.

    Não é CFD. É um modelo físico macroscópico:
    - energia específica maior remove mais atmosfera;
    - velocidade de escape maior segura mais atmosfera;
    - impacto mais normal remove mais do que raspão;
    - projétil mais massivo arranca mais envelope.
    """
    atmosphere = getattr(target, "atmosphere", 0.0)
    if atmosphere <= 0.0:
        return 0.0

    # Estrelas, plasma, buracos negros e galáxias não usam atmosfera planetária aqui.
    material = getattr(target, "material", "rock")
    if getattr(target, "mass", 0.0) >= MASS_STAR or material in ("plasma", "blackhole"):
        return 0.0

    q = max(getattr(impact, "specific_energy", 0.0), 0.0)
    q_star = max(getattr(impact, "disruption_threshold", 1.0), 1.0)
    energy_ratio = _clamp(q / q_star, 0.0, 25.0)

    v_rel = max(getattr(impact, "relative_velocity", 0.0), 0.0)
    v_escape = max(_escape_velocity_proxy(target), 1e-6)
    velocity_factor = _clamp(v_rel / (v_escape * 35.0), 0.0, 4.0)

    normality = _clamp(
        getattr(impact, "normal_velocity", 0.0) / max(v_rel, 1e-9),
        0.0,
        1.0,
    )

    mass_ratio = _clamp(projectile_mass / max(getattr(target, "mass", 1.0), 1e-9), 0.0, 1.0)

    loss_fraction = (
        0.015 * energy_ratio +
        0.035 * velocity_factor +
        0.080 * mass_ratio
    ) * (0.35 + 0.65 * normality)

    # Eventos extremos removem envelope de forma forte, mas ainda limitada.
    if getattr(impact, "should_fragment", False):
        loss_fraction += 0.18
    if getattr(impact, "impact_type", None) and getattr(impact.impact_type, "value", "") == "vaporization":
        loss_fraction += 0.35

    loss_fraction = _clamp(loss_fraction, 0.0, 0.85)
    return atmosphere * loss_fraction


def _apply_atmospheric_impact_loss(target, impact, projectile_mass=0.0):
    loss = _estimate_atmospheric_loss(target, impact, projectile_mass)
    if loss <= 0.0:
        return 0.0

    target.atmosphere = max(0.0, getattr(target, "atmosphere", 0.0) - loss)

    # Água/voláteis acompanham parte da atmosfera perdida.
    water_loss = _clamp(loss * 0.08, 0.0, getattr(target, "water", 0.0) * 0.35)
    target.water = max(0.0, getattr(target, "water", 0.0) - water_loss)

    comp = getattr(target, "composition", None)
    if isinstance(comp, dict):
        comp["volatiles"] = max(0.0, comp.get("volatiles", 0.0) - loss * 0.03)
        comp["h2o"] = max(0.0, comp.get("h2o", 0.0) - water_loss * 0.10)

    return loss




def _weighted_color(a, b, ma, mb):
    """Mistura visual conservadora: superfície visível preserva dominante."""
    total = max(ma + mb, 1e-9)
    wa = ma / total
    wb = mb / total
    dominant = a if wa >= wb else b
    sec_w = min(wa, wb)

    if sec_w < 0.18:
        return tuple(int(_clamp(c, 0, 255)) for c in dominant)

    blended = (
        _clamp((a[0] * ma + b[0] * mb) / total, 0, 255),
        _clamp((a[1] * ma + b[1] * mb) / total, 0, 255),
        _clamp((a[2] * ma + b[2] * mb) / total, 0, 255),
    )

    br, bg, bb = [x / 255.0 for x in blended]
    dr, dg, db = [x / 255.0 for x in dominant]
    bh, bs, bv = colorsys.rgb_to_hsv(br, bg, bb)
    dh, ds, dv = colorsys.rgb_to_hsv(dr, dg, db)

    min_sat = max(0.22, ds * 0.62)
    if bs < min_sat:
        bh = dh
        bs = min_sat
        bv = max(bv, dv * (0.72 + sec_w * 0.18))

    r, g, bl = colorsys.hsv_to_rgb(bh, _clamp(bs, 0.0, 1.0), _clamp(bv, 0.0, 1.0))
    return (
        int(_clamp(r * 255, 0, 255)),
        int(_clamp(g * 255, 0, 255)),
        int(_clamp(bl * 255, 0, 255)),
    )


def _thermal_tint(color, energy_scale, material="rock"):
    """Escurece/aquece levemente sem transformar tudo em cinza/amarelo."""
    severity = _clamp(math.log10(max(energy_scale, 1.0)) / 6.0, 0.0, 1.0)
    if severity <= 0:
        return color

    r, g, b = color
    if material in ("gas", "plasma"):
        factor = 1.0 + severity * 0.08
        return (
            int(_clamp(r * factor, 0, 255)),
            int(_clamp(g * factor, 0, 255)),
            int(_clamp(b * factor, 0, 255)),
        )

    heat = min(0.18, severity * 0.14)
    dark = 1.0 - min(0.16, severity * 0.10)
    return (
        int(_clamp(r * dark + 55 * heat, 0, 255)),
        int(_clamp(g * dark + 18 * heat, 0, 255)),
        int(_clamp(b * dark + 8 * heat, 0, 255)),
    )


def _volume_radius(*radii):
    return max(1.0, sum(max(r, 0.1) ** 3 for r in radii) ** (1.0 / 3.0))


def _impact_energy(a, b):
    """Energia de impacto simplificada: E = 1/2 * massa reduzida * v_rel²."""
    rel_speed = (a.vel - b.vel).length()
    reduced_mass = (a.mass * b.mass) / max(a.mass + b.mass, 1e-9)
    return 0.5 * reduced_mass * rel_speed * rel_speed, rel_speed, reduced_mass


def _impact_angle(a, b):
    """0 = frontal; 1 = raspante."""
    rel = a.vel - b.vel
    normal = b.pos - a.pos
    if rel.length_squared() == 0 or normal.length_squared() == 0:
        return 0.0
    rel = rel.normalize()
    normal = normal.normalize()
    return max(0.0, min(1.0, 1.0 - abs(rel.dot(normal))))


def _register_impact_mark(target, impact_pos, energy, angle, material="rock"):
    """Registra dano superficial apenas em corpos sólidos.

    Estrelas, buracos negros, galáxias e gigantes gasosos não devem ganhar
    “crateras” desenhadas. Nesses casos o impacto vira aquecimento/flash
    e alteração termodinâmica, não mancha permanente fake.
    """
    severity = _clamp(math.log10(max(energy, 1.0)) / 8.0, 0.08, 1.0)

    # Nada de cratera nem flash global em estrela, buraco negro, galáxia ou corpo gasoso.
    # Um asteroide pequeno não pode fazer o Sol inteiro piscar.
    # A resposta difusa fica como aquecimento proporcional e atividade local armazenada.
    if target.mass >= MASS_STAR or getattr(target, "material", "rock") in ("gas", "plasma", "blackhole"):
        mass_ratio_proxy = min(1.0, severity * 0.012)
        thermal_kick = severity * (250.0 + 2200.0 * mass_ratio_proxy)
        target.temperature = max(getattr(target, "temperature", 300.0), 300.0 + thermal_kick)
        target.stellar_activity = max(getattr(target, "stellar_activity", 0.0), severity * mass_ratio_proxy)
        return

    if not hasattr(target, "impact_marks"):
        target.impact_marks = []
    direction = impact_pos - target.pos
    theta = math.atan2(direction.y, direction.x) if direction.length_squared() else random.random() * math.tau

    # Marcas existem, mas não viram tatuagem eterna.
    life = 4.0 + severity * 10.0
    if target.mass > 5e4:
        life *= 0.55

    mark = {
        "angle": theta,
        "severity": severity,
        "scrape": angle,
        "age": 0.0,
        "life": life,
        "material": material,
    }
    target.impact_marks.append(mark)
    target.impact_marks = target.impact_marks[-8:]
    target.impact_flash = max(getattr(target, "impact_flash", 0.0), 0.15 + severity * 0.85)
    target.temperature = max(getattr(target, "temperature", 300.0), 300.0 + severity * 3500.0)


def _apply_impact_side_effects(target, projectile, energy, rel_speed, absorbed_mass=0.0):
    """Aplica consequências físicas simples no corpo sobrevivente.

    Evita colisão sem efeito: impacto altera atmosfera, água, voláteis,
    composição, temperatura e rotação de forma proporcional à energia.
    """
    severity = _clamp(math.log10(max(energy, 1.0)) / 8.0, 0.0, 1.0)

    if hasattr(target, "composition"):
        comp = target.composition
        h2o_loss = min(comp.get("h2o", 0.0), severity * 0.018 + rel_speed * 0.00002)
        comp["h2o"] = max(0.0, comp.get("h2o", 0.0) - h2o_loss)
        comp["volatiles"] = max(0.0, comp.get("volatiles", 0.0) + h2o_loss * 0.45)

        if hasattr(projectile, "composition") and absorbed_mass > 0:
            mix = _clamp(absorbed_mass / max(target.mass, 1e-9), 0.0, 0.08)
            for k, v in projectile.composition.items():
                comp[k] = comp.get(k, 0.0) * (1.0 - mix) + v * mix

    if target.mass < MASS_STAR:
        # PATCH 43: perda atmosférica principal agora vem de _apply_atmospheric_impact_loss().
        # Mantemos só uma perda residual térmica, bem menor.
        atm_loss = severity * (0.004 + rel_speed * 0.000006)
        target.atmosphere = max(0.0, getattr(target, "atmosphere", 0.0) - atm_loss)

    water_loss = severity * (0.02 + rel_speed * 0.00004)
    target.water = max(0.0, getattr(target, "water", 0.0) - water_loss)
    target.temperature = max(getattr(target, "temperature", 300.0), 300.0 + severity * 4500.0)



def _apply_energy_temperature(body, heat_energy, affected_mass=None):
    """Converte energia térmica em aumento de temperatura aproximado.

    Usa capacidade térmica efetiva por material. Isso evita cor fake substituir física.
    """
    material = getattr(body, "material", "rock")
    heat_capacity = {
        "ice": 2100.0,
        "rock": 900.0,
        "metal": 520.0,
        "gas": 14000.0,
        "plasma": 22000.0,
        "blackhole": 1.0e30,
    }.get(material, 900.0)

    mass = max(affected_mass if affected_mass is not None else getattr(body, "mass", 1.0), 1e-9)
    delta_t = heat_energy / max(mass * heat_capacity, 1e-9)

    # Escala do protótipo: limita salto para não quebrar UI/cores.
    delta_t = _clamp(delta_t, 0.0, 25000.0)
    body.temperature = max(getattr(body, "temperature", 300.0), getattr(body, "temperature", 300.0) + delta_t)
    return delta_t


def _inherit_fragment_surface(fragment, source, thermal_energy_scale):
    """Fragmentos herdam material/composição/cor do corpo de origem."""
    fragment.material = getattr(source, "material", "rock")
    fragment.composition = dict(getattr(source, "composition", {}))
    base = getattr(source, "base_color", getattr(source, "color", (180, 180, 180)))
    fragment.base_color = base
    fragment.color = _thermal_tint(base, thermal_energy_scale, fragment.material)
    fragment.water = max(0.0, getattr(source, "water", 0.0) * 0.10)
    fragment.atmosphere = 0.0
    fragment.has_life = False
    return fragment


def classify_body(mass):
    if mass >= 1e11: return "Galaxia"
    if mass >= 1e9:  return "BN Supermassivo"
    if mass >= MASS_BLACK_HOLE: return "Buraco Negro"
    if mass >= MASS_STAR: return "Estrela"
    if mass >= 5e4: return "Gigante Gasoso"
    if mass >= MASS_PLANET: return "Planeta"
    if mass >= 1e2: return "Planeta Anao"
    if mass >= 1e1: return "Lua"
    return "Fragmento"


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



def _is_gas_giant(body):
    return getattr(body, "material", "") == "gas" or (5.0e4 <= getattr(body, "mass", 0.0) < MASS_STAR)


def _limit_giant_velocity(body):
    max_speed = 900.0
    if _is_gas_giant(body) and body.vel.length() > max_speed:
        body.vel.scale_to_length(max_speed)


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
            victim = min(fragments, key=lambda b: (getattr(b, "fragment_life", 0.0), b.mass))
            self.bodies.remove(victim)
        return True

    def can_add_body(self, reserve=1):
        if len(self.bodies) + reserve <= getattr(self, "max_bodies", MAX_BODIES):
            return True
        return any(getattr(b, "is_fragment", False) for b in self.bodies)

    def add_body(self, body):
        if not self._trim_for_new_body(1):
            return False
        ensure_structure(body)
        self.bodies.append(body)
        return True

    def _compute_accelerations(self):
        self._compute_accelerations_for(self.bodies)

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

    def _body_strength(self, body):
        # PATCH 40: resistência vem do modelo de material, não de tabela local fake.
        return mixed_strength(body, body)

    def _solve_collision_impact(self, a, b):
        normal = b.pos - a.pos
        response = material_pair_response(a, b)
        strength = mixed_strength(a, b)

        a.material = response["material_a"]
        b.material = response["material_b"]

        return solve_impact(ImpactInput(
            m1=a.mass,
            m2=b.mass,
            r1=a.radius,
            r2=b.radius,
            v1x=a.vel.x,
            v1y=a.vel.y,
            v2x=b.vel.x,
            v2y=b.vel.y,
            normal_x=normal.x,
            normal_y=normal.y,
            structural_strength=strength,
            heat_absorption=response["heat_absorption"],
            fragmentation_bias=response["fragmentation_bias"],
            ejecta_bias=response["ejecta_bias"],
            restitution=response["restitution"],
        ))

    def _collision_kind_from_impact(self, a, b, impact):
        # Buracos negros e galáxias continuam como acreção, mas a energia vem do solver.
        if a.mass >= MASS_BLACK_HOLE or b.mass >= MASS_BLACK_HOLE:
            return "accretion"
        if a.mass >= 1e11 or b.mass >= 1e11:
            return "galactic_accretion"

        # Plasma não recebe cratera. Impacto vira acreção/fusão/disrupção térmica.
        if a.mass >= MASS_STAR or b.mass >= MASS_STAR:
            if a.mass >= MASS_STAR and b.mass >= MASS_STAR:
                if impact.impact_type in (ImpactType.CATASTROPHIC_DISRUPTION, ImpactType.VAPORIZATION):
                    return "stellar_disruption"
                return "stellar_merge"
            return "plasma_accretion"

        # Gigantes gasosos não devem virar nuvem de rochas cinzas.
        # Colisão gasosa lenta/média vira fusão/acréscimo fluido; só impacto extremo arranca massa.
        if _is_gas_giant(a) or _is_gas_giant(b):
            if impact.impact_type in (ImpactType.HIT_AND_RUN, ImpactType.GRAZE):
                return "hit_and_run"
            if impact.specific_energy < impact.disruption_threshold * 2.8:
                mass_ratio = min(a.mass, b.mass) / max(max(a.mass, b.mass), 1e-9)
                return "merge" if mass_ratio >= 0.08 else "absorb"
            return "fragment"

        if impact.impact_type in (ImpactType.HIT_AND_RUN, ImpactType.GRAZE):
            return "hit_and_run"
        if impact.impact_type == ImpactType.CRATERING:
            return "crater"
        if impact.impact_type in (ImpactType.ACCRETION, ImpactType.MERGE):
            mass_ratio = min(a.mass, b.mass) / max(max(a.mass, b.mass), 1e-9)
            if mass_ratio < ABSORB_RATIO_LIMIT:
                return "absorb"
            return "merge"
        if impact.impact_type == ImpactType.PARTIAL_DISRUPTION:
            return "fragment"
        return "shatter"

    def _collision_kind(self, a, b):
        energy, relative_speed, reduced_mass = _impact_energy(a, b)
        mass_ratio = min(a.mass, b.mass) / max(max(a.mass, b.mass), 1e-9)
        energy_scale = energy / max(min(a.mass, b.mass), 1e-9)

        if a.mass >= MASS_BLACK_HOLE or b.mass >= MASS_BLACK_HOLE:
            return "accretion"

        if a.mass >= 1e11 or b.mass >= 1e11:
            return "galactic_accretion"

        if a.mass >= MASS_STAR and b.mass >= MASS_STAR:
            if energy_scale > 4.0e4:
                return "stellar_disruption"
            return "stellar_merge"

        # Planeta/estrela: planeta vaporiza/acresce; não é colisão comum.
        if a.mass >= MASS_STAR or b.mass >= MASS_STAR:
            return "plasma_accretion"

        # Corpo minúsculo contra planeta: cratera/meteoro, não fusão total.
        if mass_ratio < 0.02:
            if relative_speed > 120:
                return "crater"
            return "absorb"

        # Corpos comparáveis: só funde direto se o impacto for extremamente lento.
        if relative_speed < 28 and energy_scale < 1.5e3:
            return "merge"

        if energy_scale < 8.0e3:
            return "crater"
        if energy_scale < 5.0e4:
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
        target.structural_integrity = (
            getattr(a, "structural_integrity", 1.0) * ma +
            getattr(b, "structural_integrity", 1.0) * mb
        ) / total
        target.damage_accumulated = (
            getattr(a, "damage_accumulated", 0.0) * ma +
            getattr(b, "damage_accumulated", 0.0) * mb
        ) / total
        target.thermal_damage = (
            getattr(a, "thermal_damage", 0.0) * ma +
            getattr(b, "thermal_damage", 0.0) * mb
        ) / total

        # Campos opcionais usados no main.py.
        for attr, default in (("co2", 0.0), ("n2", 0.0), ("albedo", 0.3)):
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
        new_omega = merged_angular_velocity(a, b, new_pos, new_vel, total_mass, new_radius)
        impact_energy, rel_speed, _mu = _impact_energy(a, b)

        a.pos = new_pos
        a.vel = new_vel
        a.mass = total_mass
        a.radius = new_radius
        a.color = _thermal_tint(new_color, impact_energy / max(total_mass, 1e-9), getattr(a, "material", "rock"))
        a.has_rings = getattr(a, "has_rings", False) or getattr(b, "has_rings", False)
        a.name = new_name
        a.trail = []
        a.collision_cooldown = COLLISION_COOLDOWN
        self._copy_surface_properties(a, a, b, old_a_mass, old_b_mass)
        a.material = infer_material(a)
        a.angular_velocity = new_omega
        _apply_impact_side_effects(a, b, impact_energy, rel_speed, old_b_mass)
        _apply_energy_temperature(a, impact_energy * 0.25, affected_mass=max(total_mass, 1e-9))
        apply_structural_damage(a, impact=None, heat_energy=impact_energy * 0.25, affected_mass=max(total_mass, 1e-9), strength=1.0e5)
        self.collision_events.append(CollisionEvent(new_pos, kind))

    def _absorb_body(self, big, small):
        energy, rel_speed, _mu = _impact_energy(big, small)
        angle = _impact_angle(big, small)
        mass_ratio = small.mass / max(big.mass, 1e-9)

        _register_impact_mark(big, small.pos, energy, angle, getattr(small, "material", "rock"))

        retained = 0.72 if rel_speed > 80 else 0.88
        if mass_ratio > 0.005:
            retained = min(retained, 0.65)
        absorbed_mass = small.mass * retained
        lost_mass = max(small.mass - absorbed_mass, 0.0)
        total_mass = big.mass + absorbed_mass

        new_pos = (big.pos * big.mass + small.pos * absorbed_mass) / total_mass
        new_vel = (big.vel * big.mass + small.vel * absorbed_mass) / total_mass
        old_big_mass = big.mass

        # Momento angular: impacto pequeno e rasante gira o corpo maior.
        class _ImpactProxy:
            tangential_velocity = angle * rel_speed
            relative_velocity = rel_speed
        big.angular_velocity = getattr(big, "angular_velocity", 0.0) + spin_kick_from_impact(big, small, _ImpactProxy(), sign=1.0)

        big.pos = new_pos
        big.vel = new_vel
        big.mass = total_mass
        big.radius = _volume_radius(big.radius, small.radius * (retained ** (1.0/3.0)))
        energy_scale = energy / max(small.mass, 1e-9)
        big.color = _thermal_tint(
            _weighted_color(big.color, small.color, old_big_mass, absorbed_mass),
            energy_scale,
            getattr(big, "material", "rock"),
        )
        big.has_rings = getattr(big, "has_rings", False) or getattr(small, "has_rings", False)
        big.name = big.name or classify_body(big.mass)
        big.trail = []
        big.collision_cooldown = COLLISION_COOLDOWN
        self._copy_surface_properties(big, big, small, old_big_mass, absorbed_mass)
        big.material = infer_material(big)
        _apply_impact_side_effects(big, small, energy, rel_speed, absorbed_mass)
        _apply_energy_temperature(big, energy * 0.30, affected_mass=max(absorbed_mass, MIN_FRAGMENT_MASS))
        apply_structural_damage(big, impact=None, heat_energy=energy * 0.30, affected_mass=max(absorbed_mass, MIN_FRAGMENT_MASS), strength=1.0e5)

        if lost_mass >= MIN_FRAGMENT_MASS:
            self._spawn_fragments(small, big, lost_mass, "ejecta", count_hint=3 if mass_ratio < 0.005 else 6)
        self.collision_events.append(CollisionEvent(new_pos, "impact"))

    def _spawn_fragments(self, source, collider, ejecta_mass, kind, count_hint=None, impact=None):
        """Fragmentação direcional com conservação aproximada de massa e energia."""
        if ejecta_mass < MIN_FRAGMENT_MASS:
            return

        rel = source.vel - collider.vel
        rel_speed = max(rel.length(), 20.0)

        if impact is not None:
            energy_budget = max(
                getattr(impact.energy, "fragmentation", 0.0) +
                getattr(impact.energy, "ejecta", 0.0),
                0.0
            )
            count = count_hint or int(_clamp(ejecta_mass / max(source.mass * 0.04, 2.0), 2, MAX_FRAGMENTS))
            away = directional_ejecta_vector(source, collider, impact)
        else:
            energy_budget = 0.5 * max(ejecta_mass, MIN_FRAGMENT_MASS) * rel_speed * rel_speed
            count = count_hint or int(_clamp(ejecta_mass / 8.0, 2, MAX_FRAGMENTS))
            away = source.pos - collider.pos
            if away.length_squared() == 0:
                away = pygame.Vector2(random.uniform(-1, 1), random.uniform(-1, 1))
            if away.length_squared() == 0:
                away = pygame.Vector2(1, 0)
            away = away.normalize()

        count = int(_clamp(count, 1, MAX_FRAGMENTS))
        if getattr(self, "performance_mode", False) or len(self.bodies) > 120:
            count = min(count, 4)

        available_slots = max(0, getattr(self, "max_bodies", MAX_BODIES) - len(self.bodies))
        count = min(count, available_slots)
        if count <= 0:
            return

        fragment_mass = ejecta_mass / count
        if fragment_mass < MIN_FRAGMENT_MASS:
            count = max(1, min(count, int(ejecta_mass / MIN_FRAGMENT_MASS)))
            fragment_mass = ejecta_mass / count

        specific_fragment_energy = energy_budget / max(ejecta_mass, 1e-9)
        eject_speed_base = math.sqrt(max(0.0, 2.0 * specific_fragment_energy))
        eject_speed_base = _clamp(eject_speed_base, 15.0, max(60.0, rel_speed * 1.35))

        # Base comum mantém conservação de momento visualmente plausível.
        center_velocity = (source.vel * source.mass + collider.vel * collider.mass) / max(source.mass + collider.mass, 1e-9)

        for idx in range(count):
            # Distribuição em cone, não explosão circular.
            spread = 0.28 if impact is not None else 0.55
            angle = random.uniform(-spread, spread)
            direction = away.rotate_rad(angle)
            speed = random.uniform(0.55, 1.05) * eject_speed_base

            pos = source.pos + direction * random.uniform(source.radius * 0.35, source.radius + 3)
            vel = center_velocity + direction * speed
            radius = max(1.0, source.radius * ((fragment_mass / max(source.mass, 1e-9)) ** (1.0/3.0)))

            frag = Body(pos.x, pos.y, vel.x, vel.y, fragment_mass, radius, getattr(source, "base_color", source.color), "Fragmento")
            _inherit_fragment_surface(frag, source, specific_fragment_energy)

            frag.is_fragment = True
            frag.show_label = False
            frag.has_rings = False
            frag.spin = random.uniform(0, math.tau)
            frag.angular_velocity = random.uniform(-1.0, 1.0) + (speed / max(radius, 1.0)) * random.uniform(-0.18, 0.18)
            frag.label_timer = FRAGMENT_LABEL_TIME
            frag.temperature = max(getattr(source, "temperature", 300.0), 300.0)
            _apply_energy_temperature(frag, energy_budget / max(count, 1), affected_mass=fragment_mass)
            frag.age = 0.0
            frag.life_timer = FRAGMENT_LIFETIME * random.uniform(0.65, 1.25)
            frag.collision_cooldown = COLLISION_COOLDOWN * 1.4
            self.bodies.append(frag)

        self.collision_events.append(CollisionEvent(source.pos, kind))

    def _fragment_collision(self, a, b, destructive=False, impact=None):
        big, small = (a, b) if a.mass >= b.mass else (b, a)
        energy, rel_speed, _mu = _impact_energy(a, b)
        angle = _impact_angle(a, b)
        energy_scale = energy / max(min(a.mass, b.mass), 1e-9)

        _register_impact_mark(big, small.pos, energy, angle, getattr(small, "material", "rock"))

        # Raspante: arranca material, preserva parte do projétil e adiciona rotação.
        scrape_boost = 0.45 + angle * 0.55
        small_ejecta = small.mass * (0.35 + min(0.45, energy_scale / 90000.0)) * scrape_boost
        small_ejecta = min(small.mass * 0.90, small_ejecta)
        small_absorbed = small.mass - small_ejecta

        damage = min(0.22 if destructive else 0.10, (energy_scale / 250000.0) * (1.0 + angle))
        big_ejecta = big.mass * damage

        old_big_mass = big.mass
        big.mass = max(big.mass + small_absorbed - big_ejecta, MIN_FRAGMENT_MASS)
        big.vel = (big.vel * old_big_mass + small.vel * small_absorbed) / max(old_big_mass + small_absorbed, 1e-9)
        big.radius = max(1.0, big.radius * ((big.mass / max(old_big_mass, 1e-9)) ** (1.0/3.0)))
        big.color = _thermal_tint(
            _weighted_color(big.color, small.color, old_big_mass, max(small_absorbed, 0.0)),
            energy_scale,
            getattr(big, "material", "rock"),
        )
        big.has_rings = getattr(big, "has_rings", False) or getattr(small, "has_rings", False)
        big.name = big.name or classify_body(big.mass)
        big.trail = []
        big.collision_cooldown = COLLISION_COOLDOWN
        _apply_impact_side_effects(big, small, energy, rel_speed, small_absorbed)
        big.temperature = max(getattr(big, "temperature", 300.0), 800.0 + min(9000.0, energy_scale * 0.05))
        if impact is not None:
            big.angular_velocity = getattr(big, "angular_velocity", 0.0) + spin_kick_from_impact(big, small, impact, sign=1.0)
            _apply_energy_temperature(big, getattr(impact.energy, "heat", 0.0) * 0.45, affected_mass=max(big.mass * 0.12, small.mass))
            damage_result = apply_structural_damage(
                big,
                impact=impact,
                heat_energy=getattr(impact.energy, "heat", 0.0) * 0.45,
                affected_mass=max(big.mass * 0.12, small.mass),
                strength=getattr(impact, "disruption_threshold", 1.0e5),
            )
            if damage_result.should_shed_mass and big.mass > MIN_FRAGMENT_MASS * 4:
                shed_mass = min(big.mass * 0.06, big.mass - MIN_FRAGMENT_MASS)
                big.mass -= shed_mass
                self._spawn_fragments(big, small, shed_mass, "spall", count_hint=2, impact=impact)
        else:
            big.angular_velocity = getattr(big, "angular_velocity", 0.0) + angle * rel_speed * (small.mass / max(big.mass,1e-9)) * 0.04

        self._spawn_fragments(small, big, small_ejecta, "ejecta", count_hint=3 + int(angle * 4), impact=impact)
        if big_ejecta >= MIN_FRAGMENT_MASS:
            self._spawn_fragments(big, small, big_ejecta, "spall", count_hint=2 + int(damage * 12), impact=impact)

        self.collision_events.append(CollisionEvent((a.pos + b.pos) * 0.5, "scrape" if angle > 0.55 else "impact"))
        return big, small

    def _hit_and_run_collision(self, a, b, impact):
        # Colisão tangencial: não funde, não apaga o projétil.
        # Separa os corpos e aplica impulso normal simples com conservação de momento.
        normal = b.pos - a.pos
        if normal.length_squared() == 0:
            normal = pygame.Vector2(random.uniform(-1, 1), random.uniform(-1, 1))
        if normal.length_squared() == 0:
            normal = pygame.Vector2(1, 0)
        n = normal.normalize()

        rel_vel = b.vel - a.vel
        closing_speed = rel_vel.dot(n)
        restitution = 0.35 if impact.specific_energy < impact.disruption_threshold else 0.12

        if closing_speed < 0:
            impulse_mag = -(1.0 + restitution) * closing_speed / max((1.0 / a.mass) + (1.0 / b.mass), 1e-9)
            impulse = n * impulse_mag
            a.vel -= impulse / a.mass
            b.vel += impulse / b.mass

        self._separate(a, b)

        energy = impact.impact_energy
        rel_speed = impact.relative_velocity
        angle = impact.tangential_velocity / max(impact.relative_velocity, 1e-9)
        if a.mass >= b.mass:
            _register_impact_mark(a, b.pos, energy, angle, getattr(b, "material", "rock"))
            _apply_impact_side_effects(a, b, energy, rel_speed, 0.0)
        else:
            _register_impact_mark(b, a.pos, energy, angle, getattr(a, "material", "rock"))
            _apply_impact_side_effects(b, a, energy, rel_speed, 0.0)

        a.angular_velocity = getattr(a, "angular_velocity", 0.0) - spin_kick_from_impact(a, b, impact, sign=1.0)
        b.angular_velocity = getattr(b, "angular_velocity", 0.0) + spin_kick_from_impact(b, a, impact, sign=1.0)
        _apply_energy_temperature(a, getattr(impact.energy, "heat", 0.0) * 0.20, affected_mass=max(a.mass * 0.08, b.mass * 0.25))
        _apply_energy_temperature(b, getattr(impact.energy, "heat", 0.0) * 0.20, affected_mass=max(b.mass * 0.08, a.mass * 0.25))
        apply_structural_damage(a, impact=impact, heat_energy=getattr(impact.energy, "heat", 0.0) * 0.20, affected_mass=max(a.mass * 0.08, b.mass * 0.25), strength=getattr(impact, "disruption_threshold", 1.0e5))
        apply_structural_damage(b, impact=impact, heat_energy=getattr(impact.energy, "heat", 0.0) * 0.20, affected_mass=max(b.mass * 0.08, a.mass * 0.25), strength=getattr(impact, "disruption_threshold", 1.0e5))
        a.collision_cooldown = COLLISION_COOLDOWN
        b.collision_cooldown = COLLISION_COOLDOWN
        self.collision_events.append(CollisionEvent((a.pos + b.pos) * 0.5, "scrape"))

    def check_collisions(self):
        n = len(self.bodies)
        handled = 0
        max_handled = 10 if n < 80 else 5
        i = 0
        while i < n:
            j = i + 1
            while j < n:
                a, b = self.bodies[i], self.bodies[j]
                if getattr(a, "collision_cooldown", 0.0) > 0 or getattr(b, "collision_cooldown", 0.0) > 0:
                    j += 1
                    continue

                if (a.pos - b.pos).length() < (a.radius + b.radius):
                    handled += 1
                    if handled > max_handled:
                        return
                    impact = self._solve_collision_impact(a, b)

                    # PATCH 43 — perda atmosférica por impacto.
                    # Aplica nos dois corpos antes da decisão final, proporcional ao projétil.
                    _apply_atmospheric_impact_loss(a, impact, projectile_mass=b.mass)
                    _apply_atmospheric_impact_loss(b, impact, projectile_mass=a.mass)

                    kind = self._collision_kind_from_impact(a, b, impact)

                    if kind == "hit_and_run":
                        self._hit_and_run_collision(a, b, impact)
                        j += 1
                        continue
                    elif kind in ("stellar_merge", "stellar_disruption"):
                        self._merge_bodies(a, b, "stellar")
                        self.bodies.pop(j)
                        n -= 1
                        continue
                    elif kind in ("accretion", "galactic_accretion", "plasma_accretion", "absorb"):
                        big, small = (a, b) if a.mass >= b.mass else (b, a)
                        self._absorb_body(big, small)
                        self.bodies.remove(small)
                        n -= 1
                        if i >= n: break
                        if j >= n: continue
                    elif kind == "crater":
                        survivor, removed = self._fragment_collision(a, b, destructive=False, impact=impact)
                        self.bodies.remove(removed)
                        n -= 1
                        if i >= n: break
                        if j >= n: continue
                    elif kind == "merge":
                        self._merge_bodies(a, b, "merge")
                        self.bodies.pop(j)
                        n -= 1
                        continue
                    elif kind == "fragment":
                        survivor, removed = self._fragment_collision(a, b, destructive=False, impact=impact)
                        self.bodies.remove(removed)
                        n -= 1
                        if i >= n: break
                        if j >= n: continue
                    else:
                        survivor, removed = self._fragment_collision(a, b, destructive=True, impact=impact)
                        self.bodies.remove(removed)
                        n -= 1
                        if i >= n: break
                        if j >= n: continue
                else:
                    j += 1
            i += 1

    def check_roche(self):
        pass

    def _compute_accelerations_for(self, bodies):
        for b in bodies:
            b.acc = pygame.Vector2(0.0, 0.0)
        n = len(bodies)
        for i in range(n):
            a = bodies[i]
            for j in range(i + 1, n):
                b = bodies[j]
                dx = b.pos.x - a.pos.x
                dy = b.pos.y - a.pos.y
                ds2 = dx * dx + dy * dy + 25.0
                ds = math.sqrt(ds2)
                f = G * a.mass * b.mass / ds2
                fx = f * dx / ds
                fy = f * dy / ds
                a.acc.x += fx / a.mass
                a.acc.y += fy / a.mass
                b.acc.x -= fx / b.mass
                b.acc.y -= fy / b.mass

    def simulate_preview(self, new_body_data, steps=80, step_dt=0.4):
        ghosts = [Body(b.pos.x,b.pos.y,b.vel.x,b.vel.y,b.mass,b.radius,b.color,"") for b in self.bodies]
        nb = Body(new_body_data["pos"].x, new_body_data["pos"].y, new_body_data["vel"].x, new_body_data["vel"].y, new_body_data["mass"], new_body_data["radius"], new_body_data["color"], "")
        ghosts.append(nb)
        trail=[]
        sdt = step_dt * self.time_scale * 0.08
        for _ in range(steps):
            self._compute_accelerations_for(ghosts)
            half_dt = 0.5 * sdt
            for b in ghosts:
                b.vel += b.acc * half_dt
                b.pos += b.vel * sdt
            self._compute_accelerations_for(ghosts)
            for b in ghosts:
                b.vel += b.acc * half_dt
            trail.append(pygame.Vector2(nb.pos))
        return trail

    def step(self, dt):
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
            half_dt = 0.5 * sdt
            for b in self.bodies:
                b.vel += b.acc * half_dt
                _limit_giant_velocity(b)
                b.pos += b.vel * sdt
            self._compute_accelerations()
            for b in self.bodies:
                b.vel += b.acc * half_dt
                _limit_giant_velocity(b)
            self.check_collisions()
        for b in self.bodies[:]:
            ensure_structure(b)
            relax_structure(b, dt * self.time_scale)
            b.age = getattr(b, "age", 0.0) + dt * self.time_scale
            if getattr(b, "collision_cooldown", 0.0) > 0:
                b.collision_cooldown = max(0.0, b.collision_cooldown - dt)
            if getattr(b, "label_timer", 0.0) > 0:
                b.label_timer = max(0.0, b.label_timer - dt)
            if hasattr(b, "impact_marks"):
                for mark in b.impact_marks[:]:
                    mark["age"] = mark.get("age", 0.0) + dt
                    if mark["age"] >= mark.get("life", 8.0):
                        b.impact_marks.remove(mark)
            if getattr(b, "impact_flash", 0.0) > 0:
                b.impact_flash = max(0.0, b.impact_flash - dt * 1.8)
            b.spin = getattr(b, "spin", 0.0) + getattr(b, "angular_velocity", 0.0) * dt
            if abs(getattr(b, "angular_velocity", 0.0)) > 0.001:
                b.angular_velocity *= max(0.0, 1.0 - dt * 0.02)

            # Patch 35: oceanos/voláteis simples ligados à temperatura.
            temp = getattr(b, "temperature", 300.0)
            if hasattr(b, "composition"):
                h2o = b.composition.get("h2o", getattr(b, "water", 0.0) * 0.1)
                if temp > 650 and h2o > 0:
                    vapor_loss = min(h2o, dt * 0.002 * (temp - 650) / 350.0)
                    b.composition["h2o"] = max(0.0, h2o - vapor_loss)
                    b.composition["volatiles"] = b.composition.get("volatiles", 0.0) + vapor_loss * 0.6
                    b.water = max(0.0, getattr(b, "water", 0.0) - vapor_loss * 2.0)
                elif 273 < temp < 373 and h2o > 0:
                    b.water = min(1.0, getattr(b, "water", 0.0) + dt * 0.0005)

            if getattr(b, "is_fragment", False):
                life_speed = 1.8 if getattr(self, "performance_mode", False) else 1.0
                b.life_timer = getattr(b, "life_timer", FRAGMENT_LIFETIME) - dt * life_speed
                if b.life_timer <= 0 and b.mass < MASS_PLANET:
                    self.bodies.remove(b)
                    continue
                b.temperature = max(120.0, getattr(b, "temperature", 300.0) - dt * 45.0)

            # PATCH 46 — ruptura progressiva por dano acumulado.
            if (
                not getattr(b, "is_fragment", False)
                and getattr(b, "structural_integrity", 1.0) < 0.18
                and b.mass > MIN_FRAGMENT_MASS * 8
                and len(self.bodies) < self.max_bodies - 2
            ):
                shed_mass = min(b.mass * 0.10, b.mass - MIN_FRAGMENT_MASS)
                b.mass -= shed_mass
                b.radius = max(1.0, b.radius * ((b.mass / max(b.mass + shed_mass, 1e-9)) ** (1.0/3.0)))
                self._spawn_fragments(b, b, shed_mass, "breakup", count_hint=3)
                b.structural_integrity = max(0.22, getattr(b, "structural_integrity", 0.0))

            b.trail.append((int(b.pos.x), int(b.pos.y)))
            trail_limit = FRAGMENT_TRAIL_LIMIT if getattr(b, "is_fragment", False) else BODY_TRAIL_LIMIT
            if len(b.trail) > trail_limit:
                b.trail = b.trail[-trail_limit:]
        for ev in self.collision_events[:]:
            ev.timer -= dt
            if ev.timer <= 0: self.collision_events.remove(ev)
