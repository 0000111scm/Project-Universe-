"""Conversões e formatação BR para o Project Universe.

Escala interna atual:
- HAB_SCALE pixels ≈ 1 UA.
- A velocidade visual é convertida assumindo 1 segundo de simulação ≈ 1 ano.
  Isso mantém órbitas tipo Terra perto de dezenas de km/s, sem mentir que o motor usa SI real.
"""
import math

AU_KM = 149_597_870.7
SECONDS_PER_DAY = 86_400.0
SIM_SECOND_DAYS = 365.25
EARTH_MASS_INTERNAL = 1.0e3
SOLAR_MASS_INTERNAL = 1.0e6

def kelvin_to_celsius(k):
    return float(k) - 273.15

def celsius_to_kelvin(c):
    return float(c) + 273.15

def px_to_au(px, hab_scale=150.0):
    return float(px) / max(float(hab_scale), 1e-9)

def px_to_km(px, hab_scale=150.0):
    return px_to_au(px, hab_scale) * AU_KM

def speed_to_km_s(speed_px_per_sim_s, hab_scale=150.0):
    au_per_sim_s = float(speed_px_per_sim_s) / max(float(hab_scale), 1e-9)
    km_per_sim_s = au_per_sim_s * AU_KM
    return km_per_sim_s / (SIM_SECOND_DAYS * SECONDS_PER_DAY)

def acceleration_to_m_s2(acc_px_per_sim_s2, hab_scale=150.0):
    km_per_sim_s2 = (float(acc_px_per_sim_s2) / max(float(hab_scale), 1e-9)) * AU_KM
    real_s = SIM_SECOND_DAYS * SECONDS_PER_DAY
    return (km_per_sim_s2 * 1000.0) / max(real_s * real_s, 1e-9)

def fmt_num_br(value, decimals=1):
    s = f"{float(value):,.{decimals}f}"
    return s.replace(',', 'X').replace('.', ',').replace('X', '.')

def fmt_temp_c(k):
    c = kelvin_to_celsius(k)
    return f"{fmt_num_br(c, 1)} °C"

def fmt_distance_au(px, hab_scale=150.0):
    au = px_to_au(px, hab_scale)
    if au < 0.01:
        km = px_to_km(px, hab_scale)
        return f"{fmt_num_br(km, 0)} km"
    return f"{fmt_num_br(au, 2)} UA"

def fmt_speed(speed_px_per_sim_s, hab_scale=150.0):
    return f"{fmt_num_br(speed_to_km_s(speed_px_per_sim_s, hab_scale), 2)} km/s"

def fmt_acceleration(acc_px_per_sim_s2, hab_scale=150.0):
    return f"{fmt_num_br(acceleration_to_m_s2(acc_px_per_sim_s2, hab_scale), 4)} m/s²"

def fmt_mass(mass):
    mass = float(mass)
    if mass >= SOLAR_MASS_INTERNAL * 0.05:
        return f"{fmt_num_br(mass / SOLAR_MASS_INTERNAL, 3)} M☉"
    if mass >= EARTH_MASS_INTERNAL * 0.001:
        return f"{fmt_num_br(mass / EARTH_MASS_INTERNAL, 3)} M⊕"
    return f"{fmt_num_br(mass, 2)} u.m."
