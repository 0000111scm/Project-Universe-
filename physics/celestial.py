"""Classificacao e regras fisicas de alto nivel para corpos celestes.

Este modulo evita o bug classico: tudo muito massivo virar "estrela".
A ordem importa: galaxia > buraco negro > remanescente compacto > estrela > planeta.
"""

MASS_PLANET = 5e2
MASS_STAR = 8e5
MASS_NEUTRON_STAR = 4e6
MASS_BLACK_HOLE = 5e6
MASS_GALAXY = 1e11

BLACK_HOLE_KEYS = ("buraco", "bn ", "bn estelar", "bn super", "quasar")
GALAXY_KEYS = ("galáxia", "galaxia", "via láctea", "andromeda", "andrômeda", "nuvem magal")
NEUTRON_KEYS = ("nêutrons", "neutrons", "pulsar", "magnetar")
STAR_KEYS = (
    "sol", "estrela", "anã", "ana ", "gigante", "supergigante", "hipergigante",
    "sirius", "alfa", "centauri", "betelgeuse", "rigel", "vega", "canopus",
    "arcturus", "pollux", "eta carinae", "wolf-rayet", "t tauri", "carbono", "nova"
)

def _name(body):
    return getattr(body, "name", "").lower()

def body_class(body):
    """Retorna uma classe fisica estavel usada pela simulacao."""
    name = _name(body)
    mass = float(getattr(body, "mass", 0.0))

    if any(k in name for k in GALAXY_KEYS) or mass >= MASS_GALAXY:
        return "galaxy"
    if any(k in name for k in BLACK_HOLE_KEYS) or (mass >= MASS_BLACK_HOLE and "estrela" not in name and "gigante" not in name):
        return "black_hole"
    if any(k in name for k in NEUTRON_KEYS):
        return "neutron_star"
    if any(k in name for k in STAR_KEYS) or mass >= MASS_STAR:
        return "star"
    if mass >= 5e4:
        return "gas_giant"
    if mass >= MASS_PLANET:
        return "planet"
    if mass >= 1e2:
        return "dwarf_planet"
    if mass >= 1e1:
        return "moon"
    return "small_body"

def class_label(body_or_mass):
    if not hasattr(body_or_mass, "mass"):
        mass = float(body_or_mass)
        if mass >= MASS_GALAXY: return "Galaxia"
        if mass >= MASS_BLACK_HOLE: return "Buraco Negro"
        if mass >= MASS_STAR: return "Estrela"
        if mass >= 5e4: return "Gigante Gasoso"
        if mass >= MASS_PLANET: return "Planeta"
        if mass >= 1e2: return "Planeta Anao"
        if mass >= 1e1: return "Lua"
        return "Fragmento"
    cls = body_class(body_or_mass)
    return {
        "galaxy": "Galaxia",
        "black_hole": "Buraco Negro",
        "neutron_star": "Estrela de Neutrons",
        "star": "Estrela",
        "gas_giant": "Gigante Gasoso",
        "planet": "Planeta",
        "dwarf_planet": "Planeta Anao",
        "moon": "Lua",
        "small_body": "Fragmento",
    }[cls]

def collision_family(a, b):
    ca, cb = body_class(a), body_class(b)
    families = {ca, cb}
    if "galaxy" in families:
        return "galactic"
    if "black_hole" in families:
        return "black_hole"
    if "neutron_star" in families:
        return "compact"
    if ca == "star" and cb == "star":
        return "stellar"
    if "star" in families:
        return "star_body"
    if ca in ("planet", "gas_giant", "dwarf_planet") and cb in ("planet", "gas_giant", "dwarf_planet"):
        return "planetary"
    return "small"

def is_massive_persistent(body):
    return body_class(body) in {"galaxy", "black_hole", "neutron_star", "star"}
