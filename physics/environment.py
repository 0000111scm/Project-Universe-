"""Dinâmica ambiental simplificada e coerente para o Project Universe.

Camada física de primeira ordem:
- fluxo radiativo cai com 1/r²;
- temperatura aproxima do equilíbrio aos poucos por inércia térmica;
- proximidade extrema de estrelas vaporiza água e remove atmosfera;
- frio extremo congela água superficial;
- maré forte aquece corpos planetários;
- limite de Roche usa densidade aproximada.
"""
import math

HAB_SCALE = 150.0
SIGMA_TEMP_EARTH = 278.0

def _clamp(v, a, b):
    return max(a, min(b, v))


def stellar_luminosity(body):
    """Luminosidade em unidades solares aproximadas, evitando tratar BN/galáxia como estrela comum."""
    name = getattr(body, "name", "").lower()
    mass = float(getattr(body, "mass", 0.0))
    if any(k in name for k in ("buraco", "bn ", "quasar", "pulsar", "magnetar")):
        return 0.0
    if any(k in name for k in ("galáxia", "galaxia", "via láctea", "andrômeda", "andromeda")):
        return 0.0
    if mass >= 1e8:    return 5e6
    if mass >= 5e7:    return 1e6
    if mass >= 2e7:    return 1e5
    if mass >= 8e6:    return 5e4
    if mass >= 4e6:    return 1e4
    if mass >= 2.5e6:  return 1e3
    if mass >= 1.5e6:  return 50.0
    if mass >= 1.2e6:  return 10.0
    if mass >= 8e5:    return 2.0
    if mass >= 2e5:    return 0.01
    return 0.0


def radiative_flux(body, bodies, hab_scale=HAB_SCALE):
    flux = 0.0
    nearest_star = None
    nearest_dist_px = None
    for star in bodies:
        if star is body:
            continue
        lum = stellar_luminosity(star)
        if lum <= 0:
            continue
        dist_px = max((body.pos - star.pos).length(), 1.0)
        dist_au = dist_px / hab_scale
        flux += lum / max(dist_au * dist_au, 1e-6)
        if nearest_dist_px is None or dist_px < nearest_dist_px:
            nearest_star = star
            nearest_dist_px = dist_px
    return flux, nearest_star, nearest_dist_px


def equilibrium_temperature(body, bodies, hab_scale=HAB_SCALE):
    flux, _, _ = radiative_flux(body, bodies, hab_scale)
    atm = max(0.0, float(getattr(body, "atmosphere", 0.0)))
    co2 = max(0.0, float(getattr(body, "co2", 0.0)))
    albedo = _clamp(float(getattr(body, "albedo", 0.3)), 0.02, 0.95)
    greenhouse = 1.0 + min(1.1, atm * 0.10 + co2 * 0.24)
    if flux <= 0:
        return 3.0 * greenhouse
    absorbed = max(0.01, flux * (1.0 - albedo) / 0.70)
    return _clamp(SIGMA_TEMP_EARTH * (absorbed ** 0.25) * greenhouse, 3.0, 250000.0)


def body_density_proxy(body):
    return float(getattr(body, "mass", 0.0)) / max(float(getattr(body, "radius", 1.0)) ** 3, 1e-9)


def roche_limit(primary, secondary):
    if primary is secondary or primary.mass <= 0 or secondary.mass <= 0:
        return None
    if primary.mass <= secondary.mass:
        return None
    rho_primary = body_density_proxy(primary)
    rho_secondary = body_density_proxy(secondary)
    if rho_primary <= 0 or rho_secondary <= 0:
        return None
    return 2.44 * max(primary.radius, 1.0) * (rho_primary / max(rho_secondary, 1e-9)) ** (1.0 / 3.0)


def tidal_heating(body, bodies):
    heat = 0.0
    for other in bodies:
        if other is body or other.mass <= body.mass:
            continue
        d = max((body.pos - other.pos).length(), other.radius + body.radius + 1.0)
        heat += other.mass * (max(body.radius, 1.0) ** 2) / (d ** 3)
    return heat


def update_environment(bodies, dt, time_scale=1.0, hab_scale=HAB_SCALE):
    sim_dt = max(0.0, dt * max(time_scale, 0.0))
    if sim_dt <= 0:
        return

    for body in list(bodies):
        body.born_timer = float(getattr(body, "born_timer", 999.0)) + dt

        lum_self = stellar_luminosity(body)
        name = getattr(body, "name", "").lower()
        compact_or_galaxy = any(k in name for k in ("buraco", "bn ", "galáxia", "galaxia", "quasar", "pulsar", "magnetar"))
        if compact_or_galaxy or lum_self > 0:
            if lum_self > 0:
                body.temperature = max(float(getattr(body, "temperature", 300.0)), 3500.0)
            else:
                body.temperature = max(3.0, float(getattr(body, "temperature", 50.0)))
            continue

        eq = equilibrium_temperature(body, bodies, hab_scale)
        current = float(getattr(body, "temperature", 300.0))
        # Corpos maiores mudam de temperatura mais devagar.
        inertia = _clamp(math.sqrt(max(body.mass, 1.0)) * 0.16 + max(body.radius, 1.0) * 0.25, 5.0, 160.0)
        body.temperature = current + (eq - current) * min(1.0, sim_dt / inertia)

        flux, nearest_star, dist_px = radiative_flux(body, bodies, hab_scale)
        heat = tidal_heating(body, bodies)
        body.tidal_heat = heat
        if heat > 30.0:
            body.temperature += min(2500.0, heat * 0.012) * min(1.0, sim_dt)
            body.volcanism = min(1.0, heat / 6000.0)
        else:
            body.volcanism = max(0.0, float(getattr(body, "volcanism", 0.0)) - sim_dt * 0.01)

        temp = float(getattr(body, "temperature", 300.0))
        water = _clamp(float(getattr(body, "water", 0.0)), 0.0, 1.0)
        atm = max(0.0, float(getattr(body, "atmosphere", 0.0)))

        # Fases da água.
        if temp > 373.15:
            body.water_vapor = min(1.0, float(getattr(body, "water_vapor", 0.0)) + sim_dt * min(0.05, (temp - 373.15) / 50000.0))
        else:
            body.water_vapor = max(0.0, float(getattr(body, "water_vapor", 0.0)) - sim_dt * 0.01)
        if temp > 700.0:
            loss = sim_dt * min(0.2, (temp - 700.0) / 25000.0)
            body.water = max(0.0, water - loss)
        elif temp < 250.0:
            body.ice_fraction = min(1.0, float(getattr(body, "ice_fraction", 0.0)) + sim_dt * 0.01)
        else:
            body.ice_fraction = max(0.0, float(getattr(body, "ice_fraction", 0.0)) - sim_dt * 0.015)

        # Escape atmosférico: calor + baixa velocidade de escape proxy.
        esc_proxy = math.sqrt(max(body.mass, 1.0) / max(body.radius, 1.0))
        if temp > 600.0 or esc_proxy < 8.0:
            escape = sim_dt * max(0.0, (temp - 550.0) / 90000.0 + (8.0 - esc_proxy) / 8000.0)
            body.atmosphere = max(0.0, atm - escape)
        elif 180.0 < temp < 330.0 and body.mass >= 200:
            body.atmosphere = min(3.0, atm + sim_dt * 0.00008)

        # Composição atmosférica simples em bar equivalentes. Compatível com saves antigos.
        # atmosphere continua sendo a reserva total; pressão usa gravidade superficial.
        if not getattr(body, '_gas_initialized', False):
            total_atm = max(0.0, float(getattr(body, 'atmosphere', 0.0)))
            lname = getattr(body, 'name', '').lower()
            has_earthlike_bio = ('terra' in lname or 'earth' in lname or bool(getattr(body, 'has_life', False)))
            if not hasattr(body, 'n2'):
                body.n2 = total_atm * (0.78 if has_earthlike_bio else 0.90)
            if not hasattr(body, 'o2'):
                body.o2 = total_atm * (0.21 if has_earthlike_bio else 0.02)
            if not hasattr(body, 'co2'):
                body.co2 = total_atm * (0.01 if has_earthlike_bio else 0.08)
            if not hasattr(body, 'ch4'):
                body.ch4 = 0.0
            body._gas_initialized = True

        gas_total = max(0.0, float(getattr(body, 'n2', 0.0)) + float(getattr(body, 'o2', 0.0)) + float(getattr(body, 'co2', 0.0)) + float(getattr(body, 'ch4', 0.0)))
        if gas_total > 0:
            body.atmosphere = gas_total

        # Pressão superficial estimada, separada da atmosfera bruta.
        gravity_proxy = max(body.mass, 1.0) / max(body.radius * body.radius, 1.0)
        body.surface_gravity_proxy = gravity_proxy
        body.surface_pressure = max(0.0, gas_total if gas_total > 0 else getattr(body, 'atmosphere', 0.0)) * _clamp(gravity_proxy / 15.625, 0.15, 4.0)

        body.roche_stress = 0.0
        if float(getattr(body, "born_timer", 999.0)) < 3.0:
            continue
        if nearest_star is not None and dist_px is not None:
            rl = roche_limit(nearest_star, body)
            if rl and dist_px < rl:
                body.roche_stress = min(1.0, 1.0 - dist_px / max(rl, 1.0))
                body.temperature += body.roche_stress * 250.0 * min(1.0, sim_dt)
