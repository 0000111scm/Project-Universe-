import pygame, math, random, colorsys
try:
    import numpy as np
except Exception:
    np = None
from body import Body
from physics.impact_solver import ImpactInput, ImpactType, solve_impact
from physics.material_model import infer_material, material_pair_response, mixed_strength
from physics.angular_momentum import directional_ejecta_vector, merged_angular_velocity, spin_kick_from_impact
from physics.structural_damage import apply_structural_damage, ensure_structure, relax_structure
from physics.local_physics import ensure_internal_layers, deposit_impact_energy, relax_internal_layers
from physics.stellar_sph import StellarSPHSystem
from physics.stellar_evolution import StellarContactState, evaluate_stellar_contact, final_mass_after_stellar_event
from physics.state_arrays import build_state_arrays, sync_arrays_to_bodies, compute_gravity_acceleration
from physics.planetary_collision import decide_planetary_collision
from physics.debris_dynamics import should_form_ring
from physics_core.system import PhysicsCoreSystem
from physics_core.sph import SPHParticleSet, sample_body_particles, step_sph
from physics_core.sph_coupling import apply_sph_feedback_to_body, estimate_ejecta_from_particles
from physics_core.thermodynamics import apply_body_thermodynamics, impact_heat_partition, temperature_delta_from_energy, classify_phase, phase_name
from physics_core.sph_collision_resolver import resolve_planetary_sph_collision
from physics_core.surface_grid import ensure_surface_grid, deposit_impact_energy as deposit_surface_impact_energy, diffuse_surface_heat, crater_depth
from physics_core.stellar_pipeline import StellarProcess, evaluate_process, remnant_from_process, final_mass_and_ejecta
from physics_core.common_envelope import CommonEnvelopeProcess, update_common_envelope, classify_final_remnant, final_mass_and_ejecta as common_envelope_final_mass
from physics_core.planetary_pipeline import classify_planetary_impact
from physics_core.sph_body_replacement import should_replace_body_with_sph, run_replacement_cloud
from physics_core.ejecta_limits import bounded_planetary_ejecta_fraction, bounded_fragment_count, bounded_fragment_radius, bounded_ejecta_speed, escape_velocity_proxy as ejecta_escape_velocity
from physics_core.collision_safety import CollisionSafetyConfig, should_allow_heavy_sph, bounded_collision_events, bounded_fragments_for_collision
from physics_core.stellar_accretion import classify_star_planet_accretion
from physics_core.collision_event_queue import collect_collision_events
from physics_core.sph_body_mode import request_sph_mode, update_sph_body_modes
from physics_core.collision_budget import CollisionBudget

G                    = 0.6006
MASS_PLANET          = 5e2
MASS_STAR            = 5e7
MASS_BLACK_HOLE      = 1e9
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
    """Converte energia térmica em aquecimento local.

    PATCH 55:
    - corpos sólidos aquecem crosta/superfície primeiro;
    - estrelas/plasma aquecem envelope;
    - body.temperature representa a camada externa, não o corpo inteiro.
    """
    if heat_energy <= 0:
        return 0.0

    try:
        ensure_internal_layers(body)
        return deposit_impact_energy(body, heat_energy, affected_mass=affected_mass, depth="surface")
    except Exception:
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

def _is_star_like(body):
    return getattr(body, "mass", 0.0) >= MASS_STAR or getattr(body, "material", "") == "plasma"


def _can_inherit_rings(target, donor):
    # Estrela/plasma/buraco negro nunca herda anel de planeta.
    if _is_star_like(target) or getattr(target, "material", "") == "blackhole":
        return False
    if getattr(donor, "mass", 0.0) >= MASS_STAR:
        return False
    return bool(getattr(target, "has_rings", False) or getattr(donor, "has_rings", False))


def _contact_key(a, b):
    return tuple(sorted((id(a), id(b))))



def _cap_vector(vec, max_len):
    if vec.length() > max_len:
        vec = pygame.Vector2(vec)
        vec.scale_to_length(max_len)
    return vec


def _body_can_fragment(body):
    if _is_star_like(body):
        return False
    if getattr(body, "material", "") in ("plasma", "blackhole"):
        return False
    return True



def _stellar_mass_solar_units(mass):
    return max(float(mass), 0.0) / 3.33e8


def _stellar_merge_remnant_name(total_mass):
    solar = _stellar_mass_solar_units(total_mass)
    if solar >= 25.0:
        return "Buraco Negro"
    if solar >= 8.0:
        return "Estrela de Nêutrons"
    if solar >= 3.0:
        return "Remanescente Estelar"
    return "Estrela Fundida"


def _stellar_merge_material(total_mass):
    solar = _stellar_mass_solar_units(total_mass)
    if solar >= 25.0:
        return "blackhole"
    return "plasma"


def _stellar_remnant_radius(total_mass, raw_radius):
    solar = _stellar_mass_solar_units(total_mass)
    if solar >= 25.0:
        return max(6.0, min(16.0, raw_radius * 0.16))
    if solar >= 8.0:
        return max(5.0, min(12.0, raw_radius * 0.18))
    if solar >= 3.0:
        return max(10.0, raw_radius * 0.55)
    return raw_radius


def _stellar_explosion_strength(total_mass, merge_count=1):
    solar = _stellar_mass_solar_units(total_mass)
    return _clamp((solar / 8.0) + (merge_count - 1) * 0.20, 0.0, 8.0)


def _event_intensity(energy, mass_scale=1.0):
    """Normaliza energia de evento para feedback físico/visual."""
    return _clamp(math.log10(max(float(energy) / max(float(mass_scale), 1e-9), 1.0)) / 7.0, 0.0, 1.0)


def _cooldown_for_event(base, intensity):
    return base * _clamp(0.75 + float(intensity) * 0.9, 0.75, 1.65)



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
        self.stellar_contacts  = {}
        self.use_numpy_gravity = True
        self.stellar_sph = StellarSPHSystem(max_particles=512)
        self.physics_state = None
        self.use_state_arrays = True
        self.physics_core = PhysicsCoreSystem(G)
        self.sph_particles = SPHParticleSet(capacity=0)
        self.use_sph_collision = True
        self.collision_budget = CollisionBudget(max_heavy_impacts=1, max_fragment_spawns=12)
        self.collision_safety = CollisionSafetyConfig()
        self.use_collision_event_queue = True
        self.physics_frame_index = 0
        self.collision_check_stride = 1
        self.thermal_update_stride = 1
        self.use_physics_core = True
        self.core_dimension = 3  # render ainda projeta XY
        self.render_projection = 'xy'
        self.use_3d_core = True

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
        ensure_internal_layers(body)
        ensure_surface_grid(body)
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
        # PATCH82 star-planet absolute route:
        if (_is_star_like(a) and not _is_star_like(b)) or (_is_star_like(b) and not _is_star_like(a)):
            return "stellar_accretion"

        # PATCH81 star-planet hard-route:
        # planeta/lua/asteroide colidindo com estrela vira acreção/vaporização,
        # nunca pipeline planetário nem fragmentação rochosa.
        if (_is_star_like(a) and not _is_star_like(b)) or (_is_star_like(b) and not _is_star_like(a)):
            return "stellar_accretion"

        # PATCH 78 stellar hard-route:
        # estrela+estrela nunca passa pelo merge/accretion genérico.
        if _is_star_like(a) and _is_star_like(b):
            return "stellar_merge"

        # Buracos negros e galáxias continuam como acreção, mas a energia vem do solver.
        if a.mass >= MASS_BLACK_HOLE or b.mass >= MASS_BLACK_HOLE:
            return "accretion"
        if a.mass >= 1e11 or b.mass >= 1e11:
            return "galactic_accretion"

        # Plasma não recebe cratera. Impacto vira acreção/fusão/disrupção térmica.
        if a.mass >= MASS_STAR or b.mass >= MASS_STAR:
            if a.mass >= MASS_STAR and b.mass >= MASS_STAR:
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

            # PATCH 62 REAL:
            # planeta-planeta não deve virar "plim fundiu" automaticamente.
            # Quase tudo passa por contato planetário inelástico/fragmentação.
            if a.mass >= MASS_PLANET and b.mass >= MASS_PLANET:
                rel = (a.vel - b.vel).length()
                if rel < 8.0 and mass_ratio > 0.35:
                    return "merge"
                return "planetary_contact"

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
        a.has_rings = _can_inherit_rings(a, b)
        a.name = new_name
        a.trail = []
        intensity = _event_intensity(impact_energy, max(total_mass, 1.0))
        a.collision_cooldown = _cooldown_for_event(COLLISION_COOLDOWN, intensity)
        a.impact_flash = max(getattr(a, "impact_flash", 0.0), intensity * 0.55)
        self._copy_surface_properties(a, a, b, old_a_mass, old_b_mass)
        a.material = infer_material(a)
        if _is_star_like(a):
            a.has_rings = False
        a.angular_velocity = new_omega
        _apply_impact_side_effects(a, b, impact_energy, rel_speed, old_b_mass)
        _apply_energy_temperature(a, impact_energy * 0.25, affected_mass=max(total_mass, 1e-9))
        apply_structural_damage(a, impact=None, heat_energy=impact_energy * 0.25, affected_mass=max(total_mass, 1e-9), strength=1.0e5)
        self.collision_events.append(CollisionEvent(new_pos, kind))

    def _get_or_create_common_envelope_body(self, key, a, b, proc, bary_pos, bary_vel, radius):
        """Cria/atualiza entidade visual/física de envelope comum.

        Não é estrela nova. É o envelope de plasma persistente.
        """
        existing = None
        visual_id = int(getattr(proc, "visual_body_id", 0))
        for body in self.bodies:
            if id(body) == visual_id and getattr(body, "is_common_envelope", False):
                existing = body
                break

        if existing is None:
            if len(self.bodies) >= self.max_bodies - 1:
                return None

            env = Body(
                bary_pos.x,
                bary_pos.y,
                bary_vel.x,
                bary_vel.y,
                max(MIN_FRAGMENT_MASS, (a.mass + b.mass) * 0.002),
                max(radius, 4.0),
                (255, 160, 90),
                "Envelope Comum",
            )
            env.material = "plasma"
            env.phase = "plasma"
            env.is_fragment = True
            env.is_common_envelope = True
            env.show_label = True
            env.has_rings = False
            env.temperature = max(getattr(a, "temperature", 6000.0), getattr(b, "temperature", 6000.0), 9000.0)
            env.life_timer = FRAGMENT_LIFETIME * 2.0
            env.collision_cooldown = COLLISION_COOLDOWN * 4.0
            self.bodies.append(env)
            proc.visual_body_id = id(env)
            return env

        existing.pos = bary_pos
        existing.vel = bary_vel
        existing.radius = max(existing.radius * 0.94 + radius * 0.06, radius)
        existing.mass = max(MIN_FRAGMENT_MASS, min((a.mass + b.mass) * 0.010, existing.mass * 1.02 + proc.lost_mass * 0.02))
        existing.temperature = max(existing.temperature, 9000.0 + proc.instability * 3500.0)
        existing.life_timer = FRAGMENT_LIFETIME * 2.0
        existing.common_envelope_phase = proc.phase
        existing.instability = proc.instability
        return existing

    def _remove_common_envelope_body(self, proc):
        visual_id = int(getattr(proc, "visual_body_id", 0))
        for body in self.bodies[:]:
            if id(body) == visual_id and getattr(body, "is_common_envelope", False):
                if hasattr(self, "collision_budget"):
                    self.collision_budget.mark_removed(body)
                if body in self.bodies:
                    self.bodies.remove(body)

    def _stellar_guard_minimum_envelope_time(self, a, b):
        """Bloqueia regressão: estrela+estrela não vira fusão instantânea."""
        age_a = getattr(a, "common_envelope_age", 0.0)
        age_b = getattr(b, "common_envelope_age", 0.0)
        return max(age_a, age_b) >= 2.0

    def _stellar_contact_collision(self, a, b, impact, dt_contact=0.08):
        """PATCH 78 FINAL — colisão estelar substituída por CommonEnvelope real.

        Não existe mais caminho de fusão estelar imediata aqui.
        """
        key = _contact_key(a, b)

        dist = max((a.pos - b.pos).length(), 1e-6)
        overlap = (a.radius + b.radius) - dist
        overlap_ratio = _clamp(overlap / max(min(a.radius, b.radius), 1.0), 0.0, 6.0)

        proc = CommonEnvelopeProcess.from_dict(self.stellar_contacts.get(key, {}), key_a=key[0], key_b=key[1])

        total_mass = max(a.mass + b.mass, 1e-9)
        bary_pos = (a.pos * a.mass + b.pos * b.mass) / total_mass
        bary_vel = (a.vel * a.mass + b.vel * b.mass) / total_mass
        rel_vel = b.vel - a.vel
        rel_speed = rel_vel.length()

        ev = update_common_envelope(
            proc,
            a.mass,
            b.mass,
            a.radius,
            b.radius,
            rel_speed,
            overlap_ratio,
            getattr(impact, "impact_energy", 0.0),
            dt_contact,
        )

        # Dissipação orbital: plasma rouba energia, sem bounce elástico.
        a.vel = a.vel.lerp(bary_vel, ev["damping"] * (b.mass / total_mass))
        b.vel = b.vel.lerp(bary_vel, ev["damping"] * (a.mass / total_mass))

        # Núcleos se aproximam devagar, mas permanecem entidades até colapso físico.
        a.pos = a.pos.lerp(bary_pos, ev["pull"] * (b.mass / total_mass))
        b.pos = b.pos.lerp(bary_pos, ev["pull"] * (a.mass / total_mass))

        a.material = "plasma"
        b.material = "plasma"
        a.has_rings = False
        b.has_rings = False

        a.common_envelope_phase = proc.phase
        b.common_envelope_phase = proc.phase
        a.common_envelope_age = proc.age
        b.common_envelope_age = proc.age
        a.instability = max(getattr(a, "instability", 0.0), proc.instability)
        b.instability = max(getattr(b, "instability", 0.0), proc.instability)
        a.stellar_activity = max(getattr(a, "stellar_activity", 0.0), _clamp(0.45 + proc.instability * 0.16, 0.45, 1.0))
        b.stellar_activity = max(getattr(b, "stellar_activity", 0.0), _clamp(0.45 + proc.instability * 0.16, 0.45, 1.0))

        # Entidade de envelope comum visível/persistente.
        env_radius = _volume_radius(a.radius, b.radius) * ev["envelope_radius_factor"]
        self._get_or_create_common_envelope_body(key, a, b, proc, bary_pos, bary_vel, env_radius)

        # Aquecimento local: energia orbital -> calor.
        heat = max(getattr(impact.energy, "heat", 0.0), 0.0) * (1.0 + proc.instability * 0.35)
        _apply_energy_temperature(a, heat * (a.mass / total_mass), affected_mass=max(a.mass * 0.18, 1.0))
        _apply_energy_temperature(b, heat * (b.mass / total_mass), affected_mass=max(b.mass * 0.18, 1.0))

        # Ejeção contínua do envelope.
        if ev["should_eject"]:
            eject_mass = min(total_mass * ev["loss_fraction"], total_mass * 0.040)
            if eject_mass >= MIN_FRAGMENT_MASS:
                a_loss = min(a.mass * 0.035, eject_mass * (a.mass / total_mass))
                b_loss = min(b.mass * 0.035, eject_mass * (b.mass / total_mass))
                a.mass = max(MIN_FRAGMENT_MASS, a.mass - a_loss)
                b.mass = max(MIN_FRAGMENT_MASS, b.mass - b_loss)
                proc.lost_mass += a_loss + b_loss

                strength = _clamp(proc.instability, 0.9, 9.0)
                self._spawn_stellar_explosion(
                    pos=bary_pos,
                    bary_vel=bary_vel,
                    mass=a_loss + b_loss,
                    strength=strength,
                    source_a=a,
                    source_b=b,
                )

                if hasattr(self, "stellar_sph"):
                    self.stellar_sph.emit_common_envelope(
                        pos=(bary_pos.x, bary_pos.y),
                        bary_vel=(bary_vel.x, bary_vel.y),
                        mass=(a_loss + b_loss) * 0.75,
                        rel_vel=(rel_vel.x, rel_vel.y),
                        radius=max(a.radius, b.radius),
                        strength=strength,
                        count=int(_clamp(8 + strength * 8, 8, 72)),
                    )

        self.stellar_contacts[key] = proc.as_dict()

        a.collision_cooldown = 0.0
        b.collision_cooldown = 0.0

        if ev["collapse_allowed"]:
            self._collapse_common_envelope(a, b, proc)
            self.stellar_contacts.pop(key, None)
            return "collapsed"

        self.collision_events.append(CollisionEvent(bary_pos, proc.phase))
        return "contact"

    def _spawn_stellar_plasma(self, pos, bary_vel, mass, rel_vel, a, b):
        self._spawn_stellar_explosion(pos, bary_vel, mass, _clamp(rel_vel.length() / 60.0, 0.7, 3.0), a, b)

    def _spawn_stellar_explosion(self, pos, bary_vel, mass, strength, source_a, source_b):
        """Ejeção de plasma. Nunca gera fragmento sólido."""
        if mass <= MIN_FRAGMENT_MASS or len(self.bodies) >= self.max_bodies - 12:
            return

        count = int(_clamp(2 + strength * 2, 2, 10))
        available = max(0, self.max_bodies - len(self.bodies))
        count = min(count, available)
        if count <= 0:
            return

        mass_per = max(MIN_FRAGMENT_MASS, mass / count)
        speed_base = _clamp(28.0 + strength * 55.0, 28.0, 520.0)

        for i in range(count):
            ang = (math.tau * i / max(count, 1)) + random.uniform(-0.28, 0.28)
            direction = pygame.Vector2(math.cos(ang), math.sin(ang))
            speed = speed_base * random.uniform(0.55, 1.35)

            plasma = Body(
                pos.x + direction.x * random.uniform(4.0, 22.0),
                pos.y + direction.y * random.uniform(4.0, 22.0),
                bary_vel.x + direction.x * speed,
                bary_vel.y + direction.y * speed,
                mass_per,
                max(1.0, min(7.0, (mass_per / max(MASS_PLANET, 1.0)) ** (1.0 / 3.0) * 2.5)),
                (255, 220, 110),
                "Plasma ejetado",
            )
            plasma.material = "plasma"
            plasma.is_fragment = True
            plasma.show_label = False
            plasma.has_rings = False
            plasma.atmosphere = 0.0
            plasma.water = 0.0
            plasma.temperature = 10000.0 + strength * 5500.0
            plasma.phase = "plasma"
            plasma.life_timer = FRAGMENT_LIFETIME * _clamp(0.8 + strength * 0.12, 0.8, 2.2)
            plasma.collision_cooldown = COLLISION_COOLDOWN * 2.5
            self.bodies.append(plasma)

    def _collapse_common_envelope(self, a, b, proc):
        """Colapso/fusão final somente após envelope comum físico."""
        raw_mass = max(a.mass + b.mass, 1e-9)
        final_mass, ejecta_mass = common_envelope_final_mass(raw_mass, proc)
        remnant_name, remnant_material, radius_factor = classify_final_remnant(final_mass, proc)

        new_pos = (a.pos * a.mass + b.pos * b.mass) / max(a.mass + b.mass, 1e-9)
        new_vel = (a.vel * a.mass + b.vel * b.mass) / max(a.mass + b.mass, 1e-9)
        raw_radius = _volume_radius(a.radius, b.radius)

        if ejecta_mass >= MIN_FRAGMENT_MASS:
            self._spawn_stellar_explosion(
                pos=new_pos,
                bary_vel=new_vel,
                mass=ejecta_mass,
                strength=_clamp(proc.instability + _stellar_mass_solar_units(raw_mass) / 8.0, 1.0, 10.0),
                source_a=a,
                source_b=b,
            )

        self._remove_common_envelope_body(proc)

        old_a_mass, old_b_mass = a.mass, b.mass

        a.pos = new_pos
        a.vel = new_vel
        a.mass = final_mass
        a.radius = max(4.0, raw_radius * radius_factor)
        a.material = remnant_material
        a.name = remnant_name
        a.has_rings = False
        a.trail = []
        a.collision_cooldown = COLLISION_COOLDOWN * 4.0

        self._copy_surface_properties(a, a, b, old_a_mass, old_b_mass)
        a.material = remnant_material
        a.has_rings = False
        a.stellar_activity = 1.0
        a.stellar_merge_count = int(getattr(a, "stellar_merge_count", 0)) + int(getattr(b, "stellar_merge_count", 0)) + 1
        a.common_envelope_age = proc.age
        a.common_envelope_phase = "collapsed" if remnant_material == "blackhole" else "merged_after_envelope"
        a.explosion_strength = max(getattr(a, "explosion_strength", 0.0), proc.instability)
        a.instability = proc.instability

        if remnant_material == "blackhole":
            a.color = (0, 0, 0)
            a.temperature = max(getattr(a, "temperature", 300.0), 1.0e6)
            a.phase = "blackhole"
            a.luminosity = 0.0
        elif remnant_name == "Estrela de Nêutrons":
            a.color = (180, 210, 255)
            a.temperature = max(getattr(a, "temperature", 300.0), 2.5e5)
            a.phase = "plasma"
            a.luminosity = max(getattr(a, "luminosity", 0.0), 80.0)
        else:
            a.temperature = max(getattr(a, "temperature", 300.0), 9000.0 + proc.instability * 4000.0)
            a.phase = "plasma"
            a.luminosity = max(getattr(a, "luminosity", 0.0), 1.5 + proc.instability * 0.8)

        _apply_energy_temperature(a, proc.total_energy * 0.40, affected_mass=max(final_mass * 0.25, 1.0))
        self.collision_events.append(CollisionEvent(new_pos, "stellar_collapse" if remnant_material == "blackhole" else "stellar_explosion"))

    def _merge_stars_progressive(self, a, b, state):
        """Compatibilidade; não deve ser usado como fusão imediata."""
        proc = CommonEnvelopeProcess.from_dict(state, key_a=id(a), key_b=id(b))
        if proc.age < 2.0:
            return
        self._collapse_common_envelope(a, b, proc)

    def _stellar_accretion(self, star, body):
        """Acreção estrela + corpo menor.

        Sem anel, sem fragmentação sólida orbital e sem flash global.
        Conserva momento com massa absorvida e converte impacto em aquecimento/atividade.
        """
        energy, rel_speed, _mu = _impact_energy(star, body)

        retained = 0.995
        absorbed_mass = body.mass * retained
        total_mass = star.mass + absorbed_mass

        star.pos = (star.pos * star.mass + body.pos * absorbed_mass) / total_mass
        star.vel = (star.vel * star.mass + body.vel * absorbed_mass) / total_mass
        star.mass = total_mass

        # Estrela cresce pouco visualmente no protótipo.
        star.radius = max(star.radius, _volume_radius(star.radius, body.radius * 0.20))
        star.has_rings = False
        star.material = "plasma"
        star.trail = []
        star.collision_cooldown = COLLISION_COOLDOWN

        _apply_impact_side_effects(star, body, energy, rel_speed, absorbed_mass)
        _apply_energy_temperature(star, energy * 0.35, affected_mass=max(absorbed_mass, MIN_FRAGMENT_MASS))

        activity = min(1.0, 0.08 + body.mass / max(star.mass, 1e-9) * 120.0)
        star.stellar_activity = max(getattr(star, "stellar_activity", 0.0), activity)
        star.impact_flash = max(getattr(star, "impact_flash", 0.0), activity * 0.10)
        star.accretion_glow = max(getattr(star, "accretion_glow", 0.0), activity)

        # Planeta não "some": vira energia/plasma/acréscimo estelar no evento.
        self.collision_events.append(CollisionEvent(body.pos, "stellar_accretion"))
        self.collision_events.append(CollisionEvent(star.pos, "plasma_flare"))

    def _absorb_body(self, big, small):
        if _is_star_like(big) and not _is_star_like(small):
            self._stellar_accretion(big, small)
            return

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
        big.has_rings = _can_inherit_rings(big, small)
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
        if hasattr(self, "collision_budget"):
            count_budget = bounded_fragments_for_collision(self, int(max(1, count_hint if count_hint is not None else 4)))
            if not self.collision_budget.can_spawn_fragments(count_budget):
                return []
            self.collision_budget.consume_fragments(count_budget)

        """PATCH 56 — fragmentação mais conservativa.

        Regras:
        - estrelas/plasma não viram pedras;
        - massa e momento são tratados de forma aproximada;
        - detritos saem em cone coerente com o impacto;
        - recoil no corpo fonte compensa momentum dos fragmentos;
        - ejeção é limitada para evitar explosões numéricas.
        """
        if ejecta_mass < MIN_FRAGMENT_MASS:
            return
        if not _body_can_fragment(source):
            return

        rel = source.vel - collider.vel
        rel_speed = max(rel.length(), 10.0)

        if impact is not None:
            energy_budget = max(
                getattr(impact.energy, "fragmentation", 0.0)
                + getattr(impact.energy, "ejecta", 0.0),
                0.0,
            )
            away = directional_ejecta_vector(source, collider, impact)
            graze = _clamp(
                getattr(impact, "tangential_velocity", 0.0)
                / max(getattr(impact, "relative_velocity", 1e-9), 1e-9),
                0.0,
                1.0,
            )
        else:
            energy_budget = 0.5 * max(ejecta_mass, MIN_FRAGMENT_MASS) * rel_speed * rel_speed
            away = source.pos - collider.pos
            if away.length_squared() == 0:
                away = pygame.Vector2(random.uniform(-1, 1), random.uniform(-1, 1))
            if away.length_squared() == 0:
                away = pygame.Vector2(1, 0)
            away = away.normalize()
            graze = _impact_angle(source, collider)

        # Quantidade limitada e proporcional à massa e severidade.
        severity = _clamp(energy_budget / max(ejecta_mass * 1.0e5, 1e-9), 0.0, 1.0)
        base_count = count_hint or int(_clamp(2 + severity * 6 + graze * 3, 2, MAX_FRAGMENTS))
        count = int(_clamp(base_count, 1, MAX_FRAGMENTS))

        if getattr(self, "performance_mode", False) or len(self.bodies) > 120:
            count = min(count, 4)

        available_slots = max(0, getattr(self, "max_bodies", MAX_BODIES) - len(self.bodies))
        count = min(count, available_slots)
        if count <= 0:
            return

        ejecta_mass = min(ejecta_mass, max(source.mass - MIN_FRAGMENT_MASS, 0.0))
        if ejecta_mass < MIN_FRAGMENT_MASS:
            return

        fragment_mass = ejecta_mass / count
        if fragment_mass < MIN_FRAGMENT_MASS:
            count = max(1, min(count, int(ejecta_mass / MIN_FRAGMENT_MASS)))
            fragment_mass = ejecta_mass / count

        specific_fragment_energy = energy_budget / max(ejecta_mass, 1e-9)
        eject_speed_base = math.sqrt(max(0.0, 2.0 * specific_fragment_energy))
        eject_speed_base = _clamp(eject_speed_base, 3.0, max(18.0, rel_speed * 0.38))

        center_velocity = (
            source.vel * source.mass + collider.vel * collider.mass
        ) / max(source.mass + collider.mass, 1e-9)

        total_fragment_momentum = pygame.Vector2(0.0, 0.0)
        created_mass = 0.0
        source_vel_before = pygame.Vector2(source.vel)

        # Cone: frontal = mais aberto; rasante = cauda estreita.
        cone = 0.55 - 0.32 * graze
        cone = _clamp(cone, 0.16, 0.58)

        for idx in range(count):
            # Distribuição determinística+ruído baixo: evita explosão circular randômica.
            t = 0.0 if count == 1 else (idx / (count - 1) - 0.5)
            angle = t * cone + random.uniform(-cone * 0.18, cone * 0.18)
            direction = away.rotate_rad(angle)
            speed = eject_speed_base * random.uniform(0.55, 0.95)

            pos = source.pos + direction * random.uniform(source.radius * 0.35, source.radius + 2.0)
            vel = center_velocity + direction * speed
            radius = max(1.0, source.radius * ((fragment_mass / max(source.mass, 1e-9)) ** (1.0 / 3.0)))

            frag = Body(
                pos.x,
                pos.y,
                vel.x,
                vel.y,
                fragment_mass,
                radius,
                getattr(source, "base_color", source.color),
                "Fragmento",
            )
            _inherit_fragment_surface(frag, source, specific_fragment_energy)

            frag.is_fragment = True
            frag.show_label = False
            frag.has_rings = False
            frag.spin = random.uniform(0, math.tau)
            frag.angular_velocity = random.uniform(-0.45, 0.45)
            frag.label_timer = FRAGMENT_LABEL_TIME
            frag.temperature = max(getattr(source, "temperature", 300.0), 300.0)
            _apply_energy_temperature(frag, energy_budget / max(count, 1), affected_mass=fragment_mass)
            frag.age = 0.0
            frag.life_timer = FRAGMENT_LIFETIME * random.uniform(0.85, 1.35)
            frag.collision_cooldown = COLLISION_COOLDOWN * 1.6

            self.bodies.append(frag)

            total_fragment_momentum += frag.vel * frag.mass
            created_mass += frag.mass

        # Recoil conservativo aproximado.
        if source in self.bodies and source.mass > MIN_FRAGMENT_MASS and created_mass > 0:
            expected_fragment_momentum = source_vel_before * created_mass
            excess = total_fragment_momentum - expected_fragment_momentum
            recoil = excess / max(source.mass, 1e-9)
            recoil = _cap_vector(recoil, max(2.0, rel_speed * 0.18))
            source.vel -= recoil

        # PATCH 63 — anéis só se formam por detritos orbitais plausíveis.
        # Terra/planetas rochosos não ganham anel automaticamente após impacto.
        if source in self.bodies and created_mass >= MIN_FRAGMENT_MASS * 5:
            local_fragments = [
                b for b in self.bodies
                if getattr(b, "is_fragment", False)
                and (b.pos - source.pos).length() < max(source.radius * 8.0, source.radius + 30.0)
            ]

            if should_form_ring(source, local_fragments, G):
                source.has_rings = True

        self.collision_events.append(CollisionEvent(source.pos, kind))

    def _fragment_collision(self, a, b, destructive=False, impact=None):
        big, small = (a, b) if a.mass >= b.mass else (b, a)
        energy, rel_speed, _mu = _impact_energy(a, b)
        angle = _impact_angle(a, b)
        energy_scale = energy / max(min(a.mass, b.mass), 1e-9)

        _register_impact_mark(big, small.pos, energy, angle, getattr(small, "material", "rock"))

        # Raspante: arranca material, preserva parte do projétil e adiciona rotação.
        scrape_boost = 0.45 + angle * 0.55
        small_ejecta = small.mass * (0.18 + min(0.26, energy_scale / 180000.0)) * scrape_boost
        small_ejecta = min(small.mass * 0.62, small_ejecta)
        small_absorbed = small.mass - small_ejecta

        damage = min(0.11 if destructive else 0.050, (energy_scale / 460000.0) * (1.0 + angle))
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
        big.has_rings = _can_inherit_rings(big, small)
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

    def _seed_sph_from_collision(self, a, b, impact, severity):
        """Cria partículas SPH para colisões planetárias fortes.

        Primeiro passo real:
        - não substitui o planeta inteiro por SPH ainda;
        - amostra parte do material no ponto de colisão;
        - permite densidade/pressão/temperatura começarem a existir como partículas.
        """
        if not getattr(self, "use_sph_collision", False):
            return
        if not hasattr(self, "sph_particles"):
            return

        # Só ativa SPH para colisões com energia relevante.
        if severity < 0.035:
            return

        try:
            count_a = int(_clamp(16 + severity * 48, 16, 80))
            count_b = int(_clamp(16 + severity * 48, 16, 80))

            pa, va, ma, ta, mata = sample_body_particles(a, count=count_a)
            pb, vb, mb, tb, matb = sample_body_particles(b, count=count_b)

            # Energia cinética perdida vira temperatura inicial via termodinâmica.
            normal_fraction = impact.normal_velocity / max(impact.relative_velocity, 1e-9)
            heat_a = impact_heat_partition(
                max(getattr(impact, "impact_energy", 0.0), 0.0) * (a.mass / max(a.mass + b.mass, 1e-9)),
                normal_fraction=normal_fraction,
                material=getattr(a, "material", "rock"),
            )
            heat_b = impact_heat_partition(
                max(getattr(impact, "impact_energy", 0.0), 0.0) * (b.mass / max(a.mass + b.mass, 1e-9)),
                normal_fraction=normal_fraction,
                material=getattr(b, "material", "rock"),
            )

            delta_t_a = _clamp(temperature_delta_from_energy(getattr(a, "material", "rock"), heat_a, max(a.mass * 0.12, 1e-9)), 0.0, 25000.0)
            delta_t_b = _clamp(temperature_delta_from_energy(getattr(b, "material", "rock"), heat_b, max(b.mass * 0.12, 1e-9)), 0.0, 25000.0)

            ta[:] = ta + delta_t_a
            tb[:] = tb + delta_t_b

            self.sph_particles.add_particles(pa, va, ma, ta, mata, owner=id(a))
            self.sph_particles.add_particles(pb, vb, mb, tb, matb, owner=id(b))

            # Limite simples para não crescer sem controle.
            if self.sph_particles.count > 1200:
                self.sph_particles.active[: self.sph_particles.count - 900] = False
                self.sph_particles.compact()
        except Exception:
            return

    def _apply_sph_collision_feedback(self, body):
        """Aplica efeitos das partículas SPH no corpo dono."""
        if not hasattr(self, "sph_particles"):
            return

        feedback = apply_sph_feedback_to_body(self.sph_particles, body)
        heat_delta = feedback.get("heat_delta", 0.0)
        damage_delta = feedback.get("damage_delta", 0.0)

        if heat_delta > 0.0:
            body.temperature = max(getattr(body, "temperature", 300.0), getattr(body, "temperature", 300.0) + heat_delta)

        if damage_delta > 0.0:
            body.surface_damage = min(1.0, getattr(body, "surface_damage", 0.0) + damage_delta)
            body.damage_accumulated = min(1.0, getattr(body, "damage_accumulated", 0.0) + damage_delta * 0.35)

        # Escape proxy: se partícula SPH recebeu velocidade suficiente, vira massa perdida.
        escape_speed = max(5.0, _escape_velocity_proxy(body) * 14.0)
        ejecta = estimate_ejecta_from_particles(self.sph_particles, body, escape_speed)
        if ejecta > MIN_FRAGMENT_MASS and body.mass > ejecta + MIN_FRAGMENT_MASS:
            body.mass -= ejecta
            body.radius = max(1.0, body.radius * ((body.mass / max(body.mass + ejecta, 1e-9)) ** (1.0 / 3.0)))
            # A massa que escapou pode formar detritos rígidos leves.
            self._spawn_fragments(body, body, min(ejecta, body.mass * 0.08), "sph_ejecta", count_hint=2)

    def _resolve_planetary_sph_outcome(self, a, b, impact, decision):
        """Usa SPH como fonte primária da colisão planetária quando energia é relevante."""
        if not getattr(self, "use_sph_collision", False):
            return None

        # Colisões muito suaves continuam no caminho barato.
        if decision.severity < 0.025:
            return None

        try:
            particle_count = int(_clamp(72 + decision.severity * 90, 72, 192))
            micro_steps = int(_clamp(5 + decision.severity * 8, 5, 18))
            return resolve_planetary_sph_collision(
                a,
                b,
                impact,
                G=G,
                particle_count=particle_count,
                micro_steps=micro_steps,
                dt=0.010,
            )
        except Exception:
            return None

    def _apply_planetary_sph_outcome(self, a, b, impact, outcome):
        """Aplica resultado SPH ao par planetário.

        Retorna:
        - None se ambos sobrevivem
        - (survivor, removed) se um corpo deve ser removido
        """
        big, small = (a, b) if a.mass >= b.mass else (b, a)

        total_before = max(a.mass + b.mass, 1e-9)
        bary_vel = (a.vel * a.mass + b.vel * b.mass) / total_before
        bary_pos = (a.pos * a.mass + b.pos * b.mass) / total_before

        # Temperatura/fase vêm da microfísica.
        a.temperature = max(getattr(a, "temperature", 300.0), outcome.mean_temp_a)
        b.temperature = max(getattr(b, "temperature", 300.0), outcome.mean_temp_b)

        # SPH gerou temperatura: isso precisa virar hotspot local no Surface Grid.
        contact_point = (a.pos + b.pos) * 0.5
        try:
            heat_a = max(0.0, (outcome.mean_temp_a - 300.0) * max(a.mass * 0.04, 1.0) * 900.0)
            heat_b = max(0.0, (outcome.mean_temp_b - 300.0) * max(b.mass * 0.04, 1.0) * 900.0)
            deposit_surface_impact_energy(a, contact_point, heat_a, affected_mass=max(a.mass * 0.04, 1.0), spread=int(_clamp(a.radius * 0.18, 2, 9)))
            deposit_surface_impact_energy(b, contact_point, heat_b, affected_mass=max(b.mass * 0.04, 1.0), spread=int(_clamp(b.radius * 0.18, 2, 9)))
            a.crater_depth = crater_depth(a)
            b.crater_depth = crater_depth(b)
        except Exception:
            pass

        a.phase = phase_name(outcome.max_phase)
        b.phase = phase_name(outcome.max_phase)

        a.surface_damage = min(1.0, getattr(a, "surface_damage", 0.0) + outcome.damage_a)
        b.surface_damage = min(1.0, getattr(b, "surface_damage", 0.0) + outcome.damage_b)
        a.damage_accumulated = min(1.0, getattr(a, "damage_accumulated", 0.0) + outcome.damage_a * 0.45)
        b.damage_accumulated = min(1.0, getattr(b, "damage_accumulated", 0.0) + outcome.damage_b * 0.45)

        # Massa ejetada vem das partículas.
        ejecta_mass = min(outcome.ejecta_mass, total_before * 0.65)
        if ejecta_mass >= MIN_FRAGMENT_MASS:
            ejecta_source = small if small.mass <= big.mass else big
            self._spawn_fragments(
                ejecta_source,
                big,
                min(ejecta_mass, max(ejecta_source.mass - MIN_FRAGMENT_MASS, 0.0)),
                "sph_resolved_ejecta",
                count_hint=int(_clamp(2 + ejecta_mass / max(total_before * 0.03, 1e-9), 2, MAX_FRAGMENTS)),
                impact=impact,
            )

        # Caso 1: reacumulação física. Não é "plim": só se a nuvem SPH ficou ligada.
        if outcome.reaccrete:
            survivor = big
            removed = small

            final_mass = max(total_before - ejecta_mass, MIN_FRAGMENT_MASS)
            survivor.mass = final_mass
            survivor.vel = bary_vel
            survivor.pos = bary_pos
            survivor.radius = max(1.0, _volume_radius(a.radius, b.radius) * (final_mass / total_before) ** (1.0 / 3.0))
            survivor.temperature = max(a.temperature, b.temperature)
            survivor.phase = phase_name(outcome.max_phase)
            survivor.has_rings = False
            survivor.collision_cooldown = COLLISION_COOLDOWN * 1.8
            survivor.name = "Corpo Reacumulado" if outcome.catastrophic else survivor.name

            self.collision_events.append(CollisionEvent(bary_pos, "sph_reaccretion"))
            return survivor, removed

        # Caso 2: ambos sobrevivem deformados/perderam massa.
        if total_before > ejecta_mass:
            loss_a = min(a.mass - MIN_FRAGMENT_MASS, ejecta_mass * (a.mass / total_before))
            loss_b = min(b.mass - MIN_FRAGMENT_MASS, ejecta_mass * (b.mass / total_before))
            if loss_a > 0:
                a.mass -= loss_a
                a.radius = max(1.0, a.radius * (a.mass / max(a.mass + loss_a, 1e-9)) ** (1.0 / 3.0))
            if loss_b > 0:
                b.mass -= loss_b
                b.radius = max(1.0, b.radius * (b.mass / max(b.mass + loss_b, 1e-9)) ** (1.0 / 3.0))

        # Remove parte da energia relativa por deformação real.
        damping = 0.55 if not outcome.catastrophic else 0.82
        a.vel = a.vel.lerp(bary_vel, damping * (b.mass / max(a.mass + b.mass, 1e-9)))
        b.vel = b.vel.lerp(bary_vel, damping * (a.mass / max(a.mass + b.mass, 1e-9)))

        a.collision_cooldown = COLLISION_COOLDOWN * 1.5
        b.collision_cooldown = COLLISION_COOLDOWN * 1.5
        self.collision_events.append(CollisionEvent((a.pos + b.pos) * 0.5, "sph_deformation"))
        return None

    def _deposit_collision_to_surface_grid(self, a, b, impact, heat_a, heat_b):
        """Deposita energia real no Surface Grid no ponto de impacto."""
        contact_point = (a.pos + b.pos) * 0.5

        try:
            deposit_surface_impact_energy(
                a,
                contact_point,
                heat_a,
                affected_mass=max(a.mass * 0.04, min(a.mass, b.mass) * 0.10),
                spread=int(_clamp(a.radius * 0.18, 2, 9)),
            )
            deposit_surface_impact_energy(
                b,
                contact_point,
                heat_b,
                affected_mass=max(b.mass * 0.04, min(a.mass, b.mass) * 0.10),
                spread=int(_clamp(b.radius * 0.18, 2, 9)),
            )

            a.crater_depth = crater_depth(a)
            b.crater_depth = crater_depth(b)
        except Exception:
            return

    def _clear_invalid_rocky_rings(self, *bodies):
        for body in bodies:
            if body is not None and getattr(body, "material", "") == "rock":
                body.has_rings = False

    def _spawn_bounded_planetary_ejecta(self, source, target, ejecta_mass, mode, impact, severity):
        """Cria detritos planetários fisicamente limitados.

        Substitui a ejeção absurda de pedaços gigantes.
        """
        # PATCH81_NO_PLANETARY_EJECTA_FOR_STARS:
        # colisão envolvendo estrela não gera detrito rochoso planetário.
        if _is_star_like(source) or _is_star_like(target):
            return []

        if ejecta_mass <= MIN_FRAGMENT_MASS or len(self.bodies) >= self.max_bodies - 1:
            return []

        total_mass = max(source.mass + getattr(target, "mass", 0.0), source.mass)
        escape = ejecta_escape_velocity(G, total_mass, max(source.radius + getattr(target, "radius", 0.0), 1.0))
        impact_speed = max(getattr(impact, "relative_velocity", 0.0), 0.0)

        allowed_fraction = bounded_planetary_ejecta_fraction(severity, impact_speed, escape)
        max_visible_mass = max(MIN_FRAGMENT_MASS, source.mass * min(allowed_fraction, getattr(self.collision_safety, "max_visible_ejecta_fraction", allowed_fraction) if hasattr(self, "collision_safety") else allowed_fraction))
        visible_mass = min(ejecta_mass, max_visible_mass, max(source.mass - MIN_FRAGMENT_MASS, 0.0))

        if visible_mass <= MIN_FRAGMENT_MASS:
            return []

        count = bounded_fragments_for_collision(self, bounded_fragment_count(severity, source.radius, getattr(self, "performance_mode", False)))
        count = min(count, max(1, self.max_bodies - len(self.bodies)))
        if count <= 0:
            return []

        created = []
        mass_per = max(MIN_FRAGMENT_MASS, visible_mass / count)
        speed = bounded_ejecta_speed(impact_speed, escape, severity)

        direction_base = source.pos - target.pos
        if direction_base.length_squared() == 0:
            direction_base = pygame.Vector2(1, 0)
        direction_base = direction_base.normalize()

        for i in range(count):
            angle = random.uniform(-42.0, 42.0)
            direction = direction_base.rotate(angle)
            radius = min(bounded_fragment_radius(source.radius, mass_per / max(source.mass, 1e-9)), source.radius * (getattr(self.collision_safety, "max_rock_fragment_radius_factor", 0.16) if hasattr(self, "collision_safety") else 0.16))

            frag = Body(
                source.pos.x + direction.x * (source.radius + radius + random.uniform(0.5, 3.0)),
                source.pos.y + direction.y * (source.radius + radius + random.uniform(0.5, 3.0)),
                source.vel.x + direction.x * speed * random.uniform(0.45, 1.0),
                source.vel.y + direction.y * speed * random.uniform(0.45, 1.0),
                mass_per,
                radius,
                getattr(source, "color", (150, 140, 130)),
                "Detrito de Impacto",
            )

            frag.material = getattr(source, "material", "rock")
            frag.is_fragment = True
            frag.show_label = False
            frag.has_rings = False
            frag.temperature = max(getattr(source, "temperature", 300.0), 700.0 + severity * 1400.0)
            frag.phase = getattr(source, "phase", "solid")
            frag.collision_cooldown = COLLISION_COOLDOWN * 2.0
            frag.life_timer = FRAGMENT_LIFETIME * _clamp(0.45 + severity * 0.10, 0.45, 0.95)
            frag.trail = []
            self.bodies.append(frag)
            created.append(frag)

        return created

    def _apply_planetary_pipeline_outcome(self, a, b, impact, outcome):
        """Aplica pipeline físico planetário.

        A colisão deixa de ser decisão binária. O resultado altera:
        - massa
        - velocidade
        - dano
        - calor local
        - ejecta
        - remanescente
        """
        total_mass = max(a.mass + b.mass, 1e-9)
        big, small = (a, b) if a.mass >= b.mass else (b, a)

        bary_pos = (a.pos * a.mass + b.pos * b.mass) / total_mass
        bary_vel = (a.vel * a.mass + b.vel * b.mass) / total_mass

        ejecta_mass = min(total_mass * outcome.ejecta_fraction, total_mass - MIN_FRAGMENT_MASS)
        heat_energy = getattr(impact, "impact_energy", 0.0) * outcome.heat_fraction

        # Calor e cratera locais.
        normal_fraction = impact.normal_velocity / max(impact.relative_velocity, 1e-9)
        heat_a = heat_energy * (a.mass / total_mass)
        heat_b = heat_energy * (b.mass / total_mass)

        _apply_energy_temperature(a, heat_a, affected_mass=max(a.mass * 0.08, 1.0))
        _apply_energy_temperature(b, heat_b, affected_mass=max(b.mass * 0.08, 1.0))

        try:
            self._deposit_collision_to_surface_grid(a, b, impact, heat_a, heat_b)
        except Exception:
            pass

        # Dano estrutural proporcional à severidade.
        sev = outcome.severity
        a.surface_damage = min(1.0, getattr(a, "surface_damage", 0.0) + min(0.55, sev * 0.42))
        b.surface_damage = min(1.0, getattr(b, "surface_damage", 0.0) + min(0.55, sev * 0.42))
        a.damage_accumulated = min(1.0, getattr(a, "damage_accumulated", 0.0) + min(0.35, sev * 0.25))
        b.damage_accumulated = min(1.0, getattr(b, "damage_accumulated", 0.0) + min(0.35, sev * 0.25))

        # Ejecta vem da energia. Não cria anel automaticamente.
        if ejecta_mass >= MIN_FRAGMENT_MASS:
            source = small
            available = max(source.mass - MIN_FRAGMENT_MASS, 0.0)
            source_ejecta = min(ejecta_mass, available)
            if source_ejecta > MIN_FRAGMENT_MASS:
                self._spawn_bounded_planetary_ejecta(
                    source,
                    big,
                    source_ejecta,
                    outcome.mode,
                    impact,
                    outcome.severity,
                )
                source.mass = max(MIN_FRAGMENT_MASS, source.mass - source_ejecta)
                source.radius = max(1.0, source.radius * ((source.mass / max(source.mass + source_ejecta, 1e-9)) ** (1.0 / 3.0)))

        # Acreção parcial só em impacto suave. Nunca soma tudo.
        if outcome.accreted_fraction > 0.0 and not outcome.catastrophic:
            accreted = min(small.mass - MIN_FRAGMENT_MASS, small.mass * outcome.accreted_fraction)
            if accreted > MIN_FRAGMENT_MASS:
                old_big_mass = big.mass
                big.mass += accreted
                small.mass -= accreted
                big.vel = (big.vel * old_big_mass + small.vel * accreted) / max(big.mass, 1e-9)
                big.radius = max(1.0, big.radius * ((big.mass / max(old_big_mass, 1e-9)) ** (1.0 / 3.0)))

        # Velocidade: dissipação física, não bounce.
        a.vel = a.vel.lerp(bary_vel, outcome.damping * (b.mass / max(a.mass + b.mass, 1e-9)))
        b.vel = b.vel.lerp(bary_vel, outcome.damping * (a.mass / max(a.mass + b.mass, 1e-9)))

        # Remanescente em disrupção forte: cria corpo central ligado, não "fusão arcade".
        if outcome.create_remnant:
            bound_mass = max(MIN_FRAGMENT_MASS, total_mass * outcome.bound_fraction)
            # PATCH80_HOTFIX_MASS_FLOOR:
            # enquanto o SPH pesado está desligado, não podemos destruir massa demais por regra.
            bound_mass = max(bound_mass, total_mass * 0.58)
            remnant_radius = max(2.0, min(_volume_radius(a.radius, b.radius) * (bound_mass / total_mass) ** (1.0 / 3.0), max(a.radius, b.radius) * 1.15))

            remnant = Body(
                bary_pos.x,
                bary_pos.y,
                bary_vel.x,
                bary_vel.y,
                bound_mass,
                remnant_radius,
                big.color,
                "Remanescente de Impacto",
            )
            remnant.material = getattr(big, "material", "rock")
            remnant.temperature = max(getattr(a, "temperature", 300.0), getattr(b, "temperature", 300.0))
            remnant.phase = getattr(big, "phase", "solid")
            remnant.surface_damage = min(1.0, 0.45 + outcome.severity * 0.25)
            remnant.damage_accumulated = remnant.surface_damage
            remnant.has_rings = False
            remnant.collision_cooldown = COLLISION_COOLDOWN * 2.5
            ensure_structure(remnant)
            ensure_internal_layers(remnant)
            try:
                ensure_surface_grid(remnant)
            except Exception:
                pass
            self.bodies.append(remnant)

            # Remove os originais no caso catastrófico; no parcial, mantém se ainda têm massa.
            if outcome.catastrophic:
                self.collision_events.append(CollisionEvent(bary_pos, outcome.mode))
                return remnant, a, b

        cooldown = max(COLLISION_COOLDOWN * 1.8, getattr(self.collision_safety, "min_collision_cooldown_after_heavy", 1.2) if hasattr(self, "collision_safety") else 1.2)
        a.collision_cooldown = cooldown
        b.collision_cooldown = cooldown
        self._clear_invalid_rocky_rings(a, b)
        a.has_rings = False
        b.has_rings = False
        self.collision_events.append(CollisionEvent(bary_pos, outcome.mode))
        return None

    def _replace_planetary_bodies_with_sph(self, a, b, impact, outcome):
        """PATCH 75 — impacto forte vira nuvem SPH temporária.

        Retorna True se consumiu a colisão e removeu/substituiu os corpos.
        """
        if not should_replace_body_with_sph(a, b, impact, outcome.severity):
            return False

        # PATCH 80: SPH replacement pesado fica bloqueado por gate de segurança.
        if not should_allow_heavy_sph(self, a, b, outcome.severity):
            return False

        if hasattr(self, "collision_budget"):
            if not self.collision_budget.can_run_heavy(a, b):
                return False
            self.collision_budget.consume_heavy(a, b)

        try:
            cloud = run_replacement_cloud(
                a,
                b,
                impact,
                g=G,
                severity=outcome.severity,
                particle_count=int(_clamp(64 + outcome.severity * 80, 64, 160)),
                steps=int(_clamp(4 + outcome.severity * 5, 4, 10)),
                dt=0.010,
            )
        except Exception:
            return False

        total_mass = max(a.mass + b.mass, 1e-9)
        bary_pos = (a.pos * a.mass + b.pos * b.mass) / total_mass
        bary_vel = (a.vel * a.mass + b.vel * b.mass) / total_mass
        big = a if a.mass >= b.mass else b

        # Ejecta/vapor derivados da nuvem SPH.
        ejecta_mass = min(cloud.ejecta_mass, total_mass * 0.75)
        if ejecta_mass > MIN_FRAGMENT_MASS:
            self._spawn_bounded_planetary_ejecta(
                big,
                a if big is b else b,
                min(ejecta_mass, max(total_mass - MIN_FRAGMENT_MASS, 0.0)),
                "sph_body_cloud_ejecta",
                impact,
                outcome.severity,
            )

        if cloud.status in ("reaccumulated_remnant", "partial_remnant"):
            remnant_mass = max(MIN_FRAGMENT_MASS, cloud.bound_mass, total_mass * 0.58)
            remnant_radius = max(2.0, min(_volume_radius(a.radius, b.radius) * cloud.remnant_radius_factor, max(a.radius, b.radius) * 1.18))

            remnant = Body(
                bary_pos.x,
                bary_pos.y,
                bary_vel.x,
                bary_vel.y,
                remnant_mass,
                remnant_radius,
                big.color,
                "Remanescente SPH",
            )
            remnant.material = getattr(big, "material", "rock")
            remnant.temperature = max(cloud.mean_temperature, getattr(big, "temperature", 300.0))
            remnant.phase = phase_name(cloud.remnant_phase_id)
            remnant.has_rings = False
            remnant.surface_damage = min(1.0, 0.35 + outcome.severity * 0.35)
            remnant.damage_accumulated = remnant.surface_damage
            remnant.collision_cooldown = COLLISION_COOLDOWN * 3.0
            ensure_structure(remnant)
            ensure_internal_layers(remnant)
            try:
                ensure_surface_grid(remnant)
                contact = bary_pos
                heat = max(0.0, (cloud.mean_temperature - 300.0) * max(remnant.mass * 0.08, 1.0) * 900.0)
                deposit_surface_impact_energy(remnant, contact, heat, affected_mass=max(remnant.mass * 0.12, 1.0), spread=int(_clamp(remnant.radius * 0.25, 3, 12)))
                remnant.crater_depth = crater_depth(remnant)
            except Exception:
                pass

            self.bodies.append(remnant)

        # Se dispersou/vaporizou, não cria remanescente central limpo.
        # Remove corpos originais: o estado físico agora é detritos + eventual remanescente.
        for doomed in (a, b):
            if doomed in self.bodies:
                if hasattr(self, "collision_budget"):
                    self.collision_budget.mark_removed(doomed)
                self.bodies.remove(doomed)

        self.collision_events.append(CollisionEvent(bary_pos, cloud.status))
        return True

    def _planetary_contact_collision(self, a, b, impact):
        """PATCH 62 REAL — colisão planeta-planeta baseada em energia de ligação.

        Não é SPH real ainda, mas elimina o erro principal:
        planeta + planeta não vira fusão instantânea por padrão.
        """
        decision = decide_planetary_collision(a, b, impact)
        self._seed_sph_from_collision(a, b, impact, decision.severity)

        # PATCH 74:
        # Pipeline físico assume colisão planeta-planeta.
        # SPH continua alimentando calor/dano, mas não pode reacumular tudo magicamente.
        outcome = classify_planetary_impact(a, b, impact, G=G)

        # PATCH 75:
        # Em impacto forte, Body rígido sai de cena e vira nuvem SPH temporária.
        if self._replace_planetary_bodies_with_sph(a, b, impact, outcome):
            return None

        pipeline_result = self._apply_planetary_pipeline_outcome(a, b, impact, outcome)
        if pipeline_result is not None:
            # Caso catastrófico: retorna remanescente + dois removidos.
            if isinstance(pipeline_result, tuple) and len(pipeline_result) == 3:
                remnant, ra, rb = pipeline_result
                for doomed in (ra, rb):
                    if doomed in self.bodies:
                        if hasattr(self, "collision_budget"):
                            self.collision_budget.mark_removed(doomed)
                        self.bodies.remove(doomed)
                return None
            return pipeline_result
        return None

        big, small = (a, b) if a.mass >= b.mass else (b, a)

        total_mass = max(a.mass + b.mass, 1e-9)
        bary_vel = (a.vel * a.mass + b.vel * b.mass) / total_mass

        rel = b.vel - a.vel

        # Dissipação inelástica: remove energia relativa, conserva baricentro.
        a.vel = a.vel.lerp(bary_vel, decision.damping * (b.mass / total_mass))
        b.vel = b.vel.lerp(bary_vel, decision.damping * (a.mass / total_mass))

        # Nada de bounce elástico. Separação geométrica mínima só para evitar stuck infinito.
        normal = b.pos - a.pos
        if normal.length_squared() == 0:
            normal = pygame.Vector2(1, 0)
        n = normal.normalize()
        overlap = a.radius + b.radius - normal.length()
        if overlap > 0:
            # Separação fraca, proporcional inversa à massa.
            a.pos -= n * overlap * (b.mass / total_mass) * 0.20
            b.pos += n * overlap * (a.mass / total_mass) * 0.20

        normal_fraction = impact.normal_velocity / max(impact.relative_velocity, 1e-9)
        heat_a = impact_heat_partition(
            getattr(impact, "impact_energy", 0.0) * (a.mass / max(a.mass + b.mass, 1e-9)),
            normal_fraction=normal_fraction,
            material=getattr(a, "material", "rock"),
        )
        heat_b = impact_heat_partition(
            getattr(impact, "impact_energy", 0.0) * (b.mass / max(a.mass + b.mass, 1e-9)),
            normal_fraction=normal_fraction,
            material=getattr(b, "material", "rock"),
        )

        _apply_energy_temperature(a, heat_a, affected_mass=max(a.mass * 0.10, small.mass * 0.20))
        _apply_energy_temperature(b, heat_b, affected_mass=max(b.mass * 0.10, small.mass * 0.20))
        self._deposit_collision_to_surface_grid(a, b, impact, heat_a, heat_b)

        a.phase = phase_name(classify_phase(getattr(a, "material", "rock"), getattr(a, "temperature", 300.0), pressure=getattr(a, "atmosphere", 0.0) * 1e5))
        b.phase = phase_name(classify_phase(getattr(b, "material", "rock"), getattr(b, "temperature", 300.0), pressure=getattr(b, "atmosphere", 0.0) * 1e5))

        heat = heat_a + heat_b

        apply_structural_damage(
            a,
            impact=impact,
            heat_energy=heat * 0.35,
            affected_mass=max(a.mass * 0.08, small.mass * 0.15),
            strength=getattr(impact, "disruption_threshold", 1.0e5),
        )
        apply_structural_damage(
            b,
            impact=impact,
            heat_energy=heat * 0.35,
            affected_mass=max(b.mass * 0.08, small.mass * 0.15),
            strength=getattr(impact, "disruption_threshold", 1.0e5),
        )

        _register_impact_mark(
            big,
            small.pos,
            impact.impact_energy,
            impact.tangential_velocity / max(impact.relative_velocity, 1e-9),
            getattr(small, "material", "rock"),
        )

        # Ejecta físico aproximado, sem apagar o planeta por mágica.
        ejecta_mass = min(
            small.mass * decision.ejecta_fraction,
            max(small.mass - MIN_FRAGMENT_MASS, 0.0),
        )

        if decision.should_fragment and ejecta_mass >= MIN_FRAGMENT_MASS:
            self._spawn_fragments(
                small,
                big,
                ejecta_mass,
                decision.mode,
                count_hint=2 + int(decision.severity * 10),
                impact=impact,
            )
            small.mass = max(MIN_FRAGMENT_MASS, small.mass - ejecta_mass)
            small.radius = max(1.0, small.radius * ((small.mass / max(small.mass + ejecta_mass, 1e-9)) ** (1.0 / 3.0)))

        # Só acreta parte do menor em colisão extremamente suave.
        if decision.should_merge:
            absorbed = small.mass * decision.merge_fraction
            if absorbed > MIN_FRAGMENT_MASS:
                old_big_mass = big.mass
                big.mass += absorbed
                small.mass -= absorbed
                big.vel = (big.vel * old_big_mass + small.vel * absorbed) / max(big.mass, 1e-9)
                big.radius = _volume_radius(big.radius, small.radius * (absorbed / max(absorbed + small.mass, 1e-9)) ** (1.0 / 3.0))
                _apply_impact_side_effects(big, small, impact.impact_energy, impact.relative_velocity, absorbed)

            if small.mass <= MIN_FRAGMENT_MASS * 2:
                self.collision_events.append(CollisionEvent((a.pos + b.pos) * 0.5, decision.mode))
                return big, small

        a.angular_velocity = getattr(a, "angular_velocity", 0.0) - spin_kick_from_impact(a, b, impact, sign=1.0) * 0.6
        b.angular_velocity = getattr(b, "angular_velocity", 0.0) + spin_kick_from_impact(b, a, impact, sign=1.0) * 0.6

        a.collision_cooldown = COLLISION_COOLDOWN * 1.25
        b.collision_cooldown = COLLISION_COOLDOWN * 1.25

        self._apply_sph_collision_feedback(a)
        self._apply_sph_collision_feedback(b)

        self.collision_events.append(CollisionEvent((a.pos + b.pos) * 0.5, decision.mode))
        return None

    def _hit_and_run_collision(self, a, b, impact):
        if a.mass >= MASS_PLANET and b.mass >= MASS_PLANET and not (_is_star_like(a) or _is_star_like(b)):
            return self._planetary_contact_collision(a, b, impact)

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
        restitution = 0.02 if impact.specific_energy < impact.disruption_threshold else 0.005

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

    def _star_planet_accretion_collision(self, star, projectile, impact):
        """Colisão planeta/estrela realista.

        Planeta não fragmenta como rocha ao bater no Sol.
        Ele vaporiza/é absorvido e transfere massa, energia e momento.
        """
        outcome = classify_star_planet_accretion(star, projectile, impact)

        old_star_mass = max(star.mass, 1e-9)
        absorbed = min(outcome.absorbed_mass, max(projectile.mass, 0.0))
        star.mass += absorbed

        # Conservação aproximada de momento: planeta muda pouco a estrela.
        star.vel = star.vel.lerp(
            (star.vel * old_star_mass + projectile.vel * absorbed) / max(star.mass, 1e-9),
            0.85,
        )

        # Raio de estrela muda pouco com planeta.
        star.radius = max(star.radius, star.radius * (star.mass / old_star_mass) ** (1.0 / 9.0))

        star.material = "plasma"
        star.has_rings = False
        star.temperature = max(getattr(star, "temperature", 6000.0), getattr(star, "temperature", 6000.0) + outcome.heat_energy / max(star.mass * 5000.0, 1e-9))
        star.stellar_activity = min(1.0, max(getattr(star, "stellar_activity", 0.0), 0.45 + min(0.45, impact.relative_velocity / 1600.0)))
        star.accretion_flash = max(getattr(star, "accretion_flash", 0.0), 1.0)

        # Pequena ejeção de plasma, não detrito sólido.
        if outcome.plasma_ejecta_mass > MIN_FRAGMENT_MASS and len(self.bodies) < self.max_bodies - 4:
            try:
                self._spawn_stellar_explosion(
                    pos=projectile.pos,
                    bary_vel=star.vel,
                    mass=outcome.plasma_ejecta_mass,
                    strength=_clamp(impact.relative_velocity / 350.0, 0.8, 3.0),
                    source_a=star,
                    source_b=projectile,
                )
            except Exception:
                pass

        # Remove qualquer anel/fragmento rochoso falso.
        projectile.has_rings = False
        projectile.mass = max(0.0, projectile.mass - absorbed - outcome.vaporized_mass)

        self.collision_events.append(CollisionEvent(projectile.pos, "stellar_accretion"))
        return star, projectile

    def _check_massive_stellar_cluster_collapse(self):
        """Colapso de cluster estelar compacto.

        Se muitas estrelas/plasma ficam concentradas, forma remanescente compacto.
        Evita ficar com várias estrelas atravessadas sem resultado físico.
        """
        stars = [
            b for b in self.bodies
            if _is_star_like(b)
            and not getattr(b, "is_fragment", False)
            and not getattr(b, "is_common_envelope", False)
        ]

        if len(stars) < 6:
            return False

        total_mass = sum(max(b.mass, 0.0) for b in stars)
        if total_mass <= 0:
            return False

        bary_pos = pygame.Vector2(0, 0)
        bary_vel = pygame.Vector2(0, 0)
        for b in stars:
            bary_pos += b.pos * b.mass
            bary_vel += b.vel * b.mass
        bary_pos /= total_mass
        bary_vel /= total_mass

        max_r = max((b.pos - bary_pos).length() for b in stars)
        avg_radius = sum(b.radius for b in stars) / max(len(stars), 1)

        if max_r > max(avg_radius * 5.0, 180.0):
            return False

        solar_mass_units = _stellar_mass_solar_units(total_mass)
        if len(stars) < 10 and solar_mass_units < 8.0:
            return False

        if solar_mass_units >= 25.0:
            name = "Buraco Negro"
            material = "blackhole"
            radius = max(5.0, avg_radius * 0.45)
            color = (0, 0, 0)
            temperature = 1.0e6
            phase = "blackhole"
        elif solar_mass_units >= 8.0:
            name = "Estrela de Nêutrons"
            material = "plasma"
            radius = max(5.0, avg_radius * 0.55)
            color = (180, 210, 255)
            temperature = 2.5e5
            phase = "plasma"
        else:
            name = "Remanescente Estelar"
            material = "plasma"
            radius = max(8.0, avg_radius * 0.85)
            color = (255, 210, 120)
            temperature = 60000.0
            phase = "plasma"

        ejecta_mass = total_mass * (0.08 if material != "blackhole" else 0.16)
        remnant_mass = max(MIN_FRAGMENT_MASS, total_mass - ejecta_mass)

        remnant = stars[0]
        remnant.name = name
        remnant.material = material
        remnant.pos = bary_pos
        remnant.vel = bary_vel
        remnant.mass = remnant_mass
        remnant.radius = radius
        remnant.color = color
        remnant.temperature = temperature
        remnant.phase = phase
        remnant.has_rings = False
        remnant.common_envelope_phase = "cluster_collapse"
        remnant.common_envelope_age = max(getattr(remnant, "common_envelope_age", 0.0), 1.0)
        remnant.explosion_strength = max(getattr(remnant, "explosion_strength", 0.0), 2.0)
        remnant.collision_cooldown = COLLISION_COOLDOWN * 5.0

        if ejecta_mass > MIN_FRAGMENT_MASS:
            try:
                self._spawn_stellar_explosion(
                    pos=bary_pos,
                    bary_vel=bary_vel,
                    mass=ejecta_mass,
                    strength=3.0 if material != "blackhole" else 5.0,
                    source_a=remnant,
                    source_b=remnant,
                )
            except Exception:
                pass

        for b in stars[1:]:
            if b in self.bodies:
                if hasattr(self, "collision_budget"):
                    self.collision_budget.mark_removed(b)
                self.bodies.remove(b)

        for b in self.bodies[:]:
            if getattr(b, "is_common_envelope", False):
                if (b.pos - bary_pos).length() < max_r * 1.5 + 80:
                    self.bodies.remove(b)

        self.collision_events.append(CollisionEvent(bary_pos, "stellar_cluster_collapse"))
        return True

    def check_collisions(self):
        """PATCH 82 — colisão por fila de eventos estável.

        Não processa mais colisão mutando self.bodies no meio da varredura.
        Primeiro coleta pares em snapshot; depois resolve com orçamento fixo.
        """
        if not self.bodies:
            return

        max_events = min(bounded_collision_events(self), 4)
        events = collect_collision_events(self.bodies, _is_star_like, max_events=max_events)

        if not events:
            return

        def _safe_remove(body):
            if body in self.bodies:
                if hasattr(self, "collision_budget"):
                    self.collision_budget.mark_removed(body)
                self.bodies.remove(body)
                return True
            return False

        for ev in events:
            a, b = ev.a, ev.b

            # O evento foi coletado em snapshot; antes de resolver, valida existência.
            if a not in self.bodies or b not in self.bodies:
                continue

            if hasattr(self, "collision_budget") and not self.collision_budget.can_process_pair(a, b):
                continue

            # Fragmentos comuns não entram em colisão pesada.
            if getattr(a, "is_fragment", False) and getattr(b, "is_fragment", False):
                continue
            if (getattr(a, "is_fragment", False) or getattr(b, "is_fragment", False)) and not (_is_star_like(a) or _is_star_like(b)):
                continue

            impact = self._solve_collision_impact(a, b)

            # Atmosfera só se ambos ainda existem e não é estrela/fragmento.
            if not (_is_star_like(a) or _is_star_like(b)):
                _apply_atmospheric_impact_loss(a, impact, projectile_mass=b.mass)
                _apply_atmospheric_impact_loss(b, impact, projectile_mass=a.mass)

            kind = self._collision_kind_from_impact(a, b, impact)

            if kind == "stellar_accretion":
                star, projectile = (a, b) if _is_star_like(a) else (b, a)
                _survivor, removed = self._star_planet_accretion_collision(star, projectile, impact)
                _safe_remove(removed)
                continue

            if kind in ("stellar_merge", "stellar_disruption"):
                result = self._stellar_contact_collision(a, b, impact)
                if result == "collapsed":
                    _safe_remove(b)
                continue

            if kind == "planetary_contact":
                # SPH mode é pedido, mas pesado só ativa se gate permitir.
                try:
                    severity = getattr(self._solve_collision_impact(a, b), "impact_energy", 0.0) / max((a.mass + b.mass) * 1.0e4, 1.0)
                    request_sph_mode(a, "planetary_contact", severity)
                    request_sph_mode(b, "planetary_contact", severity)
                except Exception:
                    pass

                result = self._planetary_contact_collision(a, b, impact)
                if isinstance(result, tuple) and len(result) == 2:
                    _survivor, removed = result
                    _safe_remove(removed)
                continue

            if kind == "hit_and_run":
                self._hit_and_run_collision(a, b, impact)
                continue

            if kind in ("accretion", "galactic_accretion", "plasma_accretion", "absorb"):
                big, small = (a, b) if a.mass >= b.mass else (b, a)
                if kind == "plasma_accretion":
                    big, small = (a, b) if _is_star_like(a) else (b, a)
                self._absorb_body(big, small)
                _safe_remove(small)
                continue

            if kind == "merge":
                # Safety: planeta-planeta não deve cair aqui.
                if not (_is_star_like(a) or _is_star_like(b)) and a.mass >= MASS_PLANET and b.mass >= MASS_PLANET:
                    result = self._planetary_contact_collision(a, b, impact)
                    if isinstance(result, tuple) and len(result) == 2:
                        _survivor, removed = result
                        _safe_remove(removed)
                    continue

                self._merge_bodies(a, b, "merge")
                _safe_remove(b)
                continue

            if kind in ("crater", "fragment"):
                survivor, removed = self._fragment_collision(a, b, destructive=False, impact=impact)
                _safe_remove(removed)
                continue

            survivor, removed = self._fragment_collision(a, b, destructive=True, impact=impact)
            _safe_remove(removed)

    def check_roche(self):
        """Roche conservador.

        Hotfix: não despedaça sistema inicial.
        Só atua quando há aproximação realmente extrema e corpo já existe há tempo mínimo.
        """
        if len(self.bodies) < 2:
            return

        events = 0
        for body in self.bodies[:]:
            if getattr(body, "is_fragment", False):
                continue
            if getattr(body, "age", 0.0) < 1.5:
                continue
            if body.mass <= MIN_FRAGMENT_MASS * 20:
                continue
            if _is_star_like(body) or getattr(body, "material", "") in ("plasma", "blackhole"):
                continue

            primary = None
            best = 0.0
            for other in self.bodies:
                if other is body:
                    continue
                if other.mass <= body.mass * 5.0:
                    continue
                if getattr(other, "is_fragment", False):
                    continue

                d2 = max((body.pos - other.pos).length_squared(), 1e-6)
                influence = other.mass / d2
                if influence > best:
                    best = influence
                    primary = other

            if primary is None:
                body.roche_stress = max(0.0, getattr(body, "roche_stress", 0.0) * 0.96)
                continue

            dist = max((body.pos - primary.pos).length(), 1.0)

            # Só começa perto mesmo. Evita destruir planetas em órbita normal.
            contact_safe = primary.radius + body.radius * 2.4
            if dist > contact_safe:
                body.roche_stress = max(0.0, getattr(body, "roche_stress", 0.0) * 0.96)
                continue

            stress = _clamp((contact_safe - dist) / max(contact_safe, 1e-9), 0.0, 1.0)
            body.roche_stress = max(getattr(body, "roche_stress", 0.0) * 0.90, stress)

            if stress <= 0.18 or events >= 2:
                continue

            apply_structural_damage(
                body,
                impact=None,
                heat_energy=body.mass * stress * 80.0,
                affected_mass=max(body.mass * 0.03, MIN_FRAGMENT_MASS),
                strength=max(self._body_strength(body), 1.0),
            )

            if stress > 0.42 and len(self.bodies) < self.max_bodies - 2:
                shed_fraction = _clamp(stress * 0.015, 0.003, 0.035)
                shed_mass = min(body.mass - MIN_FRAGMENT_MASS, body.mass * shed_fraction)
                if shed_mass >= MIN_FRAGMENT_MASS:
                    body.mass -= shed_mass
                    body.radius = max(1.0, body.radius * ((body.mass / max(body.mass + shed_mass, 1e-9)) ** (1.0/3.0)))
                    self._spawn_fragments(body, primary, shed_mass, "roche", count_hint=1)
                    events += 1

    def _compute_accelerations_for(self, bodies):
        """Calcula acelerações N-body.

        PATCH 62 REAL:
        - core data-oriented via arrays fp64;
        - Body continua existindo só como camada de UI/render;
        - aceleração calculada por arrays contíguos quando NumPy existe.
        """
        n = len(bodies)
        if n == 0:
            return

        if np is not None and getattr(self, "use_state_arrays", True) and n >= 4:
            state = build_state_arrays(bodies)
            acc = compute_gravity_acceleration(state, G, softening=25.0)
            if acc is not None:
                state.acc[:, :] = acc
                for i, b in enumerate(bodies):
                    b.acc = pygame.Vector2(float(acc[i, 0]), float(acc[i, 1]))
                return

        for b in bodies:
            b.acc = pygame.Vector2(0.0, 0.0)

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
        ghosts = [
            Body(b.pos.x, b.pos.y, b.vel.x, b.vel.y, b.mass, b.radius, b.color, "")
            for b in self.bodies
        ]

        nb = Body(
            new_body_data["pos"].x,
            new_body_data["pos"].y,
            new_body_data["vel"].x,
            new_body_data["vel"].y,
            new_body_data["mass"],
            new_body_data["radius"],
            new_body_data["color"],
            "",
        )

        ghosts.append(nb)
        trail = []

        sdt = step_dt * self.time_scale * 0.08
        half_dt = 0.5 * sdt

        for _ in range(steps):
            # Velocity Verlet / Leapfrog:
            # kick meio passo -> drift completo -> recalcula força -> kick meio passo.
            self._compute_accelerations_for(ghosts)

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
        self.physics_frame_index = getattr(self, "physics_frame_index", 0) + 1

        # PATCH80 HOTFIX PERFORMANCE:
        # Para muitos corpos, checar Roche/colisão/termo todo substep custa caro.
        # Gravidade continua todo substep; eventos lentos entram por cadência.
        body_count = len(self.bodies)
        self.collision_check_stride = 3 if body_count > 70 else (2 if body_count > 40 else 1)
        self.thermal_update_stride = 4 if body_count > 70 else (2 if body_count > 40 else 1)

        if hasattr(self, 'collision_budget'):
            self.collision_budget.reset()

        for sub_i in range(SUB):
            # PATCH 65:
            # Física orbital roda no PhysicsCore ECS/SoA FP64 quando disponível.
            # Colisões/Roche ainda usam o sistema antigo após o drift físico.
            used_core = False
            if getattr(self, "use_physics_core", False) and hasattr(self, "physics_core"):
                try:
                    used_core = self.physics_core.step_bodies(self.bodies, sdt)
                except Exception:
                    used_core = False

            if not used_core:
                half_dt = 0.5 * sdt

                # Velocity Verlet / Leapfrog fallback antigo.
                self._compute_accelerations()

                for b in self.bodies:
                    b.vel += b.acc * half_dt
                    _limit_giant_velocity(b)
                    b.pos += b.vel * sdt

                self._compute_accelerations()

                for b in self.bodies:
                    b.vel += b.acc * half_dt
                    _limit_giant_velocity(b)

            if (self.physics_frame_index + sub_i) % self.collision_check_stride == 0:
                self.check_roche()
                self.check_collisions()
                self._check_massive_stellar_cluster_collapse()
        if hasattr(self, 'stellar_sph') and (len(self.bodies) <= 70 or self.physics_frame_index % 2 == 0):
            self.stellar_sph.step(dt * self.time_scale * 0.08 * (2 if len(self.bodies) > 70 else 1))
        if getattr(self, 'use_sph_collision', False) and hasattr(self, 'sph_particles') and (len(self.bodies) <= 70 or self.physics_frame_index % 3 == 0):
            step_sph(self.sph_particles, dt * self.time_scale * 0.08 * (3 if len(self.bodies) > 70 else 1), h=12.0)

        for b in self.bodies[:]:
            ensure_structure(b)
            relax_structure(b, dt * self.time_scale)
            relax_internal_layers(b, dt * self.time_scale)

            if self.physics_frame_index % self.thermal_update_stride == 0:
                apply_body_thermodynamics(b, dt * self.time_scale * 0.08 * self.thermal_update_stride)
                diffuse_surface_heat(b, dt * self.time_scale * 0.08 * self.thermal_update_stride)

            # Anéis persistentes só em corpos capazes de sustentá-los.
            if getattr(b, "has_rings", False):
                try:
                    from physics.debris_dynamics import can_body_have_persistent_rings
                    if not can_body_have_persistent_rings(b):
                        b.has_rings = False
                except Exception:
                    pass

            b.age = getattr(b, "age", 0.0) + dt * self.time_scale
            if getattr(b, "collision_cooldown", 0.0) > 0:
                b.collision_cooldown = max(0.0, b.collision_cooldown - dt)

            if getattr(self, "use_sph_collision", False) and hasattr(self, "sph_particles") and getattr(b, "collision_cooldown", 0.0) > 0:
                self._apply_sph_collision_feedback(b)
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
        valid_ids = {id(b) for b in self.bodies}
        for key in list(getattr(self, "stellar_contacts", {}).keys()):
            if key[0] not in valid_ids or key[1] not in valid_ids:
                self.stellar_contacts.pop(key, None)

        update_sph_body_modes(self, dt * self.time_scale * 0.08)

        for ev in self.collision_events[:]:
            ev.timer -= dt
            if ev.timer <= 0: self.collision_events.remove(ev)
