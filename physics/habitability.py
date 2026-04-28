"""Habitabilidade estável e explicável para o Project Universe.

A pontuação bruta usa fatores físicos. A pontuação exibida deve ser suavizada por
`update_habitability_state()` para não virar pisca-pisca quando a órbita cruza zonas
de temperatura por poucos frames.
"""
import math
from physics.environment import stellar_luminosity, radiative_flux


def _clamp(v, a, b):
    return max(a, min(b, v))


def _smoothstep(edge0, edge1, x):
    if edge0 == edge1:
        return 0.0
    t = _clamp((x - edge0) / (edge1 - edge0), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def _range_factor(x, low_dead, low_ok, high_ok, high_dead):
    """0 fora da zona morta, 1 dentro da zona boa, transição suave entre elas."""
    if x <= low_dead or x >= high_dead:
        return 0.0
    if low_ok <= x <= high_ok:
        return 1.0
    if x < low_ok:
        return _smoothstep(low_dead, low_ok, x)
    return 1.0 - _smoothstep(high_ok, high_dead, x)


def _class_from_score(score):
    if score >= 78:
        return 'Boa'
    if score >= 48:
        return 'Possível'
    if score >= 16:
        return 'Hostil'
    return 'Improvável'


def raw_habitability_report(body, bodies, hab_scale=150.0):
    """Calcula o alvo físico instantâneo da habitabilidade.

    Não suaviza. Use `habitability_report()` para UI.
    Modelo: temperatura + pressão + água líquida + massa/gravidade + estrela estável + riscos.
    """
    mass = float(getattr(body, 'mass', 0.0))
    radius = max(float(getattr(body, 'radius', 1.0)), 1.0)
    temp_k = float(getattr(body, 'temperature', 3.0))
    temp_c = temp_k - 273.15
    atm = max(0.0, float(getattr(body, 'atmosphere', 0.0)))
    pressure = max(0.0, float(getattr(body, 'surface_pressure', atm)))
    water = _clamp(float(getattr(body, 'water', 0.0)), 0.0, 1.0)
    ice = _clamp(float(getattr(body, 'ice_fraction', 0.0)), 0.0, 1.0)
    vapor = _clamp(float(getattr(body, 'water_vapor', 0.0)), 0.0, 1.0)
    co2 = max(0.0, float(getattr(body, 'co2', 0.0)))
    roche = _clamp(float(getattr(body, 'roche_stress', 0.0)), 0.0, 1.0)
    tidal = max(0.0, float(getattr(body, 'tidal_heat', 0.0)))
    volcanism = _clamp(float(getattr(body, 'volcanism', 0.0)), 0.0, 1.0)

    reasons = []
    factors = {}

    if stellar_luminosity(body) > 0:
        return {'score': 0.0, 'target_score': 0.0, 'class': 'Estrela/objeto luminoso', 'factors': {}, 'reasons': ['corpo luminoso, não habitável']}
    name = getattr(body, 'name', '').lower()
    if any(k in name for k in ('buraco', 'bn ', 'quasar', 'galáxia', 'galaxia', 'pulsar', 'magnetar')):
        return {'score': 0.0, 'target_score': 0.0, 'class': 'Objeto extremo', 'factors': {}, 'reasons': ['objeto extremo, não habitável']}

    # Faixa de massa interna: Terra ~1000. Luas grandes pontuam pouco; gigantes gasosos não são bons alvos.
    if mass < 8.0 or mass > 8.0e4:
        mass_factor = 0.0
        reasons.append('massa fora da faixa habitável')
    elif mass < 80.0:
        mass_factor = 0.25 * _smoothstep(8.0, 80.0, mass)
        reasons.append('gravidade baixa')
    elif mass < 250.0:
        mass_factor = 0.55 + 0.45 * _smoothstep(80.0, 250.0, mass)
    elif mass <= 6000.0:
        mass_factor = 1.0
    elif mass <= 30000.0:
        mass_factor = 1.0 - 0.45 * _smoothstep(6000.0, 30000.0, mass)
        reasons.append('super-Terra pesada')
    else:
        mass_factor = 0.35 * (1.0 - _smoothstep(30000.0, 80000.0, mass))
        reasons.append('muito massivo')

    gravity_proxy = mass / max(radius * radius, 1.0)
    # Terra do projeto: 1000/8² = 15,625.
    gravity_rel = gravity_proxy / 15.625
    gravity_factor = _range_factor(gravity_rel, 0.12, 0.55, 1.9, 4.0)
    if gravity_rel < 0.55:
        reasons.append('gravidade superficial baixa')
    elif gravity_rel > 1.9:
        reasons.append('gravidade superficial alta')

    # Escudo atmosférico/magnético simplificado: planetas leves e atmosfera fina perdem proteção.
    magnetic_factor = _clamp(0.35 + 0.45 * _smoothstep(120.0, 900.0, mass) + 0.20 * _smoothstep(0.25, 1.0, atm), 0.0, 1.0)
    if magnetic_factor < 0.65:
        reasons.append('proteção radiativa baixa')

    # Água líquida: faixa ampla entre 0 e 100 °C; ideal por volta de 15-25 °C.
    temp_survival = _range_factor(temp_c, -55.0, -5.0, 45.0, 105.0)
    temp_comfort = _range_factor(temp_c, -10.0, 8.0, 30.0, 52.0)
    temp_factor = 0.30 * temp_survival + 0.70 * temp_comfort
    if temp_c < -10.0:
        reasons.append('frio reduz água líquida')
    elif temp_c > 45.0:
        reasons.append('calor reduz estabilidade')

    # Pressão útil para água líquida e atmosfera respirável genérica.
    pressure_factor = _range_factor(pressure, 0.08, 0.75, 1.8, 5.5)
    if pressure < 0.70:
        reasons.append('pressão baixa')
    elif pressure > 1.8:
        reasons.append('pressão alta')

    # Atmosfera muito fina ou exagerada entra junto, mas não duplica demais o peso da pressão.
    atm_factor = _range_factor(atm, 0.05, 0.65, 2.2, 7.0)
    if atm < 0.55:
        reasons.append('atmosfera fina')

    liquid_temp = _range_factor(temp_c, -10.0, 2.0, 38.0, 85.0)
    retained_liquid = _clamp(water * (1.0 - 0.65 * ice - 0.75 * vapor), 0.0, 1.0)
    water_factor = retained_liquid * liquid_temp
    if water <= 0.05:
        reasons.append('pouca água')
    elif liquid_temp < 0.55:
        reasons.append('água instável')

    flux, nearest_star, dist_px = radiative_flux(body, bodies, hab_scale)
    star_factor = 1.0 if nearest_star is not None else 0.05
    if nearest_star is None:
        reasons.append('sem estrela próxima')
    else:
        # Penaliza extremos de fluxo; evita pontuação alta por inércia térmica logo após teleporte/criação.
        flux_factor = _range_factor(flux, 0.08, 0.35, 1.8, 7.0)
        star_factor *= flux_factor
        if flux_factor < 0.35:
            reasons.append('fluxo estelar ruim')

    chemistry_factor = 1.0
    if co2 > 0.8:
        chemistry_factor *= max(0.25, 1.0 - (co2 - 0.8) / 3.5)
        reasons.append('CO₂ elevado')

    hazard = 1.0
    if roche > 0.02:
        hazard *= max(0.0, 1.0 - roche * 1.6)
        reasons.append('maré destrutiva')
    if tidal > 3000.0:
        hazard *= 0.35
        reasons.append('aquecimento de maré extremo')
    elif tidal > 500.0:
        hazard *= 0.70
        reasons.append('aquecimento de maré forte')
    if volcanism > 0.75:
        hazard *= 0.78
        reasons.append('vulcanismo intenso')

    factors = {
        'faixa térmica': _clamp(temp_factor, 0.0, 1.0),
        'água líquida': _clamp(water_factor, 0.0, 1.0),
        'pressão': _clamp(pressure_factor, 0.0, 1.0),
        'atmosfera': _clamp(atm_factor, 0.0, 1.0),
        'massa': _clamp(mass_factor, 0.0, 1.0),
        'gravidade': _clamp(gravity_factor, 0.0, 1.0),
        'estrela': _clamp(star_factor, 0.0, 1.0),
        'proteção': _clamp(magnetic_factor, 0.0, 1.0),
        'química': _clamp(chemistry_factor, 0.0, 1.0),
        'risco físico': _clamp(hazard, 0.0, 1.0),
    }

    # Média geométrica ponderada: um fator péssimo derruba, mas sem queda instantânea absurda.
    weights = {
        'faixa térmica': 1.35,
        'água líquida': 1.20,
        'pressão': 1.05,
        'atmosfera': 0.75,
        'massa': 0.80,
        'gravidade': 0.85,
        'estrela': 1.15,
        'proteção': 0.85,
        'química': 0.55,
        'risco físico': 1.25,
    }
    log_sum = 0.0
    w_sum = 0.0
    for key, value in factors.items():
        w = weights[key]
        log_sum += w * math.log(max(0.001, value))
        w_sum += w
    score = 100.0 * math.exp(log_sum / max(w_sum, 1e-9))

    # Tetos por fatores limitantes. Isto impede Marte com pouca atmosfera de virar Éden só por água/temperatura.
    cap = 100.0
    if pressure < 0.25: cap = min(cap, 28.0)
    elif pressure < 0.70: cap = min(cap, 58.0)
    if atm < 0.20: cap = min(cap, 35.0)
    elif atm < 0.55: cap = min(cap, 62.0)
    if water <= 0.05: cap = min(cap, 10.0)
    if temp_c < -25.0 or temp_c > 60.0: cap = min(cap, 42.0)
    if magnetic_factor < 0.55: cap = min(cap, 68.0)
    if star_factor < 0.35: cap = min(cap, 35.0)
    if hazard < 0.70: cap = min(cap, 50.0)
    score = min(score, cap)

    # Pequeno bônus só quando quase tudo está bom; não salva planeta ruim.
    if cap > 90.0 and temp_comfort > 0.8 and pressure_factor > 0.8 and water_factor > 0.7 and hazard > 0.9 and magnetic_factor > 0.75:
        score = min(100.0, score + 4.0)

    score = round(_clamp(score, 0.0, 100.0), 1)
    return {'score': score, 'target_score': score, 'class': _class_from_score(score), 'factors': factors, 'reasons': reasons[:5]}


def update_habitability_state(body, bodies, dt, time_scale=1.0, hab_scale=150.0):
    """Atualiza habitabilidade suavizada no corpo.

    Subida é propositalmente lenta; queda por risco extremo é mais rápida, mas não frame-a-frame.
    """
    raw = raw_habitability_report(body, bodies, hab_scale)
    target = float(raw['score'])
    current = float(getattr(body, 'habitability_score', min(target, 5.0)))

    sim_dt = max(0.0, dt * max(time_scale, 0.0))
    if sim_dt <= 0:
        body.habitability_target = target
        return raw

    hazard = raw.get('factors', {}).get('risco físico', 1.0)
    temp_factor = raw.get('factors', {}).get('faixa térmica', 0.0)
    # Escala temporal: habitabilidade ecológica não muda igual velocímetro.
    if target >= current:
        tau = 180.0  # recuperação/terraformação natural lenta
    else:
        tau = 55.0  # degradação ambiental moderada
    if hazard < 0.35 or temp_factor < 0.12:
        tau = 18.0  # desastre real: cai mais rápido

    alpha = 1.0 - math.exp(-sim_dt / max(tau, 1e-6))
    body.habitability_score = _clamp(current + (target - current) * alpha, 0.0, 100.0)
    body.habitability_target = target
    body.habitability_factors = raw.get('factors', {})
    body.habitability_reasons = raw.get('reasons', [])
    body.habitability_class = _class_from_score(body.habitability_score)
    return raw


def habitability_report(body, bodies, hab_scale=150.0):
    raw = raw_habitability_report(body, bodies, hab_scale)
    target = float(raw['score'])
    score = float(getattr(body, 'habitability_score', target))
    # A UI mostra potencial atual, não memória biológica antiga.
    # Pode subir devagar, mas não deve ficar acima do teto físico atual.
    if score > target:
        score = target
        body.habitability_score = target
    raw['target_score'] = target
    raw['score'] = round(_clamp(score, 0.0, 100.0), 1)
    raw['class'] = _class_from_score(raw['score'])
    raw['factors'] = getattr(body, 'habitability_factors', raw.get('factors', {}))
    raw['reasons'] = getattr(body, 'habitability_reasons', raw.get('reasons', []))
    return raw
