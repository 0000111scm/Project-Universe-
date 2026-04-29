# physics/real_scale.py

EARTH_MASS_UNIT = 1.0e3
SOLAR_MASS_UNIT = 3.33e8

MASS_BY_NAME = {
    "Sol": SOLAR_MASS_UNIT,
    "Anã Amarela": SOLAR_MASS_UNIT,
    "Alfa Centauri A": 1.10 * SOLAR_MASS_UNIT,
    "Alfa Centauri B": 0.90 * SOLAR_MASS_UNIT,
    "Proxima Centauri": 0.12 * SOLAR_MASS_UNIT,
    "Anã Vermelha": 0.20 * SOLAR_MASS_UNIT,
    "Anã Branca": 0.80 * SOLAR_MASS_UNIT,
    "Sirius A": 2.00 * SOLAR_MASS_UNIT,
    "Sirius B": 0.80 * SOLAR_MASS_UNIT,
    "Anã Azul": 1.20 * SOLAR_MASS_UNIT,
    "Subgigante": 3.00 * SOLAR_MASS_UNIT,
    "Gigante Amarela": 5.00 * SOLAR_MASS_UNIT,
    "Gigante Laranja": 4.00 * SOLAR_MASS_UNIT,
    "Gigante Vermelha": 10.00 * SOLAR_MASS_UNIT,
    "Supergigante Az.": 20.00 * SOLAR_MASS_UNIT,
    "Supergigante Vm.": 25.00 * SOLAR_MASS_UNIT,
    "Hipergigante": 100.00 * SOLAR_MASS_UNIT,
    "Betelgeuse": 20.00 * SOLAR_MASS_UNIT,
    "Eta Carinae": 150.00 * SOLAR_MASS_UNIT,
    "Rigel": 18.00 * SOLAR_MASS_UNIT,
    "Canopus": 9.00 * SOLAR_MASS_UNIT,
    "Arcturus": 3.00 * SOLAR_MASS_UNIT,
    "Vega": 2.10 * SOLAR_MASS_UNIT,
    "Pollux": 2.00 * SOLAR_MASS_UNIT,
    "VY Canis Maj.": 30.00 * SOLAR_MASS_UNIT,
    "R136a1": 315.00 * SOLAR_MASS_UNIT,
    "BN Estelar": 10.00 * SOLAR_MASS_UNIT,
    "BN Intermediário": 1000.00 * SOLAR_MASS_UNIT,
    "BN Supermassivo": 1.0e6 * SOLAR_MASS_UNIT,
    "Estrela Nêutrons": 1.40 * SOLAR_MASS_UNIT,
    "Pulsar": 1.40 * SOLAR_MASS_UNIT,
    "Magnetar": 1.60 * SOLAR_MASS_UNIT,
    "Quasar": 1.0e6 * SOLAR_MASS_UNIT,
    "Estrela Zombie": 0.70 * SOLAR_MASS_UNIT,
    "Estrela Wolf-Rayet": 20.00 * SOLAR_MASS_UNIT,
    "Estrela T Tauri": 0.80 * SOLAR_MASS_UNIT,
    "Estrela Carbono": 3.00 * SOLAR_MASS_UNIT,
    "Binária Contato": 2.00 * SOLAR_MASS_UNIT,
    "Nova": 0.80 * SOLAR_MASS_UNIT,
}

def update_catalog_with_real_scales(catalog):
    for entries in catalog.values():
        for entry in entries:
            name = entry.get("name")
            if name in MASS_BY_NAME:
                entry["mass"] = float(MASS_BY_NAME[name])
    return catalog
