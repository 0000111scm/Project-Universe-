
"""Escala física realista/comprimida para o Project Universe.

A simulação separa:
- physical_mass_kg / physical_radius_km: dados reais aproximados.
- mass / radius: escala numérica/visual comprimida para manter jogabilidade e FPS.

Referências usadas no desenho do modelo: NASA planetary facts, NASA Sun facts,
NASA Milky Way facts e literatura de relação massa-raio/impactos.
"""
from __future__ import annotations
import re, math

EARTH_MASS_KG = 5.97219e24
EARTH_RADIUS_KM = 6371.0
SOLAR_MASS_KG = 1.9885e30
SOLAR_RADIUS_KM = 696000.0
LY_KM = 9.4607e12

REAL = {
    # key: canonical, family, material, mass kg, radius km, density kg/m3, sim mass, display radius
    "mercurio": ("Mercúrio","planet","rock",0.330e24,2439.7,5427,55,4),
    "venus": ("Vênus","planet","rock",4.867e24,6051.8,5243,815,8),
    "terra": ("Terra","planet","rock",EARTH_MASS_KG,EARTH_RADIUS_KM,5514,1000,8),
    "lua": ("Lua","moon","rock",7.34767309e22,1737.4,3344,12.3,3),
    "marte": ("Marte","planet","rock",0.64171e24,3389.5,3933,107,6),
    "jupiter": ("Júpiter","gas_giant","gas",1898.13e24,71492,1326,317800,28),
    "saturno": ("Saturno","gas_giant","gas",568.32e24,60268,687,95200,24),
    "urano": ("Urano","ice_giant","gas",86.811e24,25559,1271,14500,16),
    "netuno": ("Netuno","ice_giant","gas",102.409e24,24764,1638,17100,16),
    "plutao": ("Plutão","dwarf_planet","ice",1.303e22,1188.3,1854,2.2,2),
    "europa": ("Europa","moon","ice",4.80e22,1560.8,3013,8,3),
    "tita": ("Titã","moon","ice",1.3452e23,2574.7,1880,22.5,4),
    "ganimedes": ("Ganímedes","moon","ice",1.4819e23,2634.1,1936,24.8,4),
    "io": ("Io","moon","rock",8.93e22,1821.6,3528,15,3),
    "calisto": ("Calisto","moon","ice",1.076e23,2410.3,1834,18,3),
    "encelado": ("Encélado","moon","ice",1.08e20,252.1,1609,0.018,1.5),
    "tritao": ("Tritão","moon","ice",2.14e22,1353.4,2061,3.6,2.5),
    "sol": ("Sol","star","plasma",SOLAR_MASS_KG,SOLAR_RADIUS_KM,1408,1e6,48),
    "ana amarela": ("Anã Amarela","star","plasma",SOLAR_MASS_KG,SOLAR_RADIUS_KM,1408,1e6,48),
    "ana vermelha": ("Anã Vermelha","star","plasma",0.2*SOLAR_MASS_KG,0.28*SOLAR_RADIUS_KM,5000,2e5,23),
    "ana branca": ("Anã Branca","white_dwarf","plasma",0.8*SOLAR_MASS_KG,9000,1e9,8e5,6),
    "estrela neutrons": ("Estrela de Nêutrons","neutron_star","plasma",1.4*SOLAR_MASS_KG,12,4e17,4e6,4),
    "pulsar": ("Pulsar","neutron_star","plasma",1.4*SOLAR_MASS_KG,12,4e17,4e6,4),
    "magnetar": ("Magnetar","neutron_star","plasma",1.8*SOLAR_MASS_KG,12,4e17,5e6,4),
    "bn estelar": ("Buraco Negro Estelar","blackhole","blackhole",10*SOLAR_MASS_KG,29.5,0,5e6,10),
    "bn intermediario": ("Buraco Negro Intermediário","blackhole","blackhole",1e3*SOLAR_MASS_KG,2950,0,1e8,14),
    "bn supermassivo": ("Buraco Negro Supermassivo","blackhole","blackhole",4e6*SOLAR_MASS_KG,1.18e7,0,1e10,22),
    "via lactea": ("Via Láctea","galaxy","stellar_system",1.5e12*SOLAR_MASS_KG,50000*LY_KM,0,1e12,185),
    "andromeda": ("Andrômeda","galaxy","stellar_system",1.5e12*SOLAR_MASS_KG,76000*LY_KM,0,1.5e12,215),
    "galaxia espiral": ("Galáxia Espiral","galaxy","stellar_system",8e11*SOLAR_MASS_KG,50000*LY_KM,0,8e11,175),
    "galaxia eliptica": ("Galáxia Elíptica","galaxy","stellar_system",5e11*SOLAR_MASS_KG,40000*LY_KM,0,5e11,160),
    "galaxia ana": ("Galáxia Anã","galaxy","stellar_system",1e9*SOLAR_MASS_KG,10000*LY_KM,0,1e9,95),
}
ALIASES = {
    "júpiter":"jupiter","plutão":"plutao","titã":"tita","ganímedes":"ganimedes",
    "encélado":"encelado","tritão":"tritao","anã amarela":"ana amarela",
    "anã vermelha":"ana vermelha","anã branca":"ana branca",
    "estrela nêutrons":"estrela neutrons","buraco negro":"bn estelar",
    "bn intermediário":"bn intermediario","via láctea":"via lactea",
    "andrômeda":"andromeda","galáxia espiral":"galaxia espiral",
    "galáxia elíptica":"galaxia eliptica","galáxia anã":"galaxia ana",
}
def norm(name):
    s=(name or "").lower().strip()
    s=re.sub(r"\s+\d+$","",s)
    for a,b in {"á":"a","à":"a","ã":"a","â":"a","é":"e","ê":"e","í":"i","ó":"o","ô":"o","õ":"o","ú":"u","ç":"c","ü":"u"}.items():
        s=s.replace(a,b)
    return s

def get_fact(name):
    n=norm(name)
    if n in REAL: return pack(REAL[n])
    if n in ALIASES: return pack(REAL[ALIASES[n]])
    for k in sorted(REAL, key=len, reverse=True):
        if k in n or n in k:
            return pack(REAL[k])
    return None

def pack(t):
    c,f,m,kg,rad,dens,sim,disp=t
    return {"canonical":c,"family":f,"material":m,"mass_kg":kg,"radius_km":rad,"density":dens,"sim_mass":sim,"display_radius":disp}

def fallback_family(name,mass):
    n=norm(name)
    if "galax" in n or mass>=1e11: return "galaxy"
    if "buraco" in n or n.startswith("bn") or mass>=5e6: return "blackhole"
    if "estrela" in n or "sol" in n or "ana" in n or mass>=2e5: return "star"
    if mass>=5e4: return "gas_giant"
    if mass>=5e2: return "planet"
    if mass>=1e1: return "moon"
    return "small_body"

def family_material(family,name=""):
    if family=="blackhole": return "blackhole"
    if family in ("star","white_dwarf","neutron_star"): return "plasma"
    if family=="galaxy": return "stellar_system"
    if family in ("gas_giant","ice_giant"): return "gas"
    if "cometa" in norm(name) or family=="dwarf_planet": return "ice"
    return "rock"

def composition(material):
    return {
        "rock":{"silicato":.55,"ferro":.30,"gelo":.05,"volateis":.10},
        "ice":{"gelo":.60,"silicato":.25,"ferro":.05,"volateis":.10},
        "gas":{"hidrogenio_helio":.82,"gelo":.10,"rocha_metal":.08},
        "plasma":{"hidrogenio_helio_plasma":.98,"metais":.02},
        "blackhole":{"singularidade":1.0},
        "stellar_system":{"estrelas":.10,"gas_poeira":.05,"materia_escura":.85},
    }.get(material,{"silicato":.55,"ferro":.30,"gelo":.05,"volateis":.10}).copy()

def configure_body_physics(body, catalog_entry=None):
    fact=None
    if catalog_entry:
        fact=(catalog_entry.get("real") or get_fact(catalog_entry.get("name","")))
    if not fact:
        fact=get_fact(getattr(body,"name",""))
    if fact:
        body.family=fact["family"]; body.material=fact["material"]
        body.physical_mass_kg=fact["mass_kg"]; body.physical_radius_km=fact["radius_km"]; body.density_kg_m3=fact["density"]
        body.mass=float(fact["sim_mass"]); body.radius=float(fact["display_radius"]); body.display_radius=body.radius
        body.composition=composition(body.material)
        if body.material=="blackhole":
            body.color=(0,0,0); body.base_color=(0,0,0)
        return body
    fam=fallback_family(getattr(body,"name",""),getattr(body,"mass",0))
    mat=family_material(fam,getattr(body,"name",""))
    body.family=getattr(body,"family",fam) or fam
    body.material=getattr(body,"material",mat) or mat
    body.physical_mass_kg=getattr(body,"physical_mass_kg",None)
    body.physical_radius_km=getattr(body,"physical_radius_km",None)
    body.density_kg_m3=getattr(body,"density_kg_m3",None)
    body.display_radius=getattr(body,"display_radius",getattr(body,"radius",1))
    if not getattr(body,"composition",None): body.composition=composition(body.material)
    return body

def physical_radius_for_collision(body):
    real = getattr(body, "physical_radius_km", 0)
    if real:
        return float(real)
    # Inverte aproximadamente a escala visual de corpos rochosos:
    # Terra = raio visual 8 -> 6371 km. Assim, um asteroide visualmente maior
    # que a Terra também passa a ser fisicamente maior na colisão.
    rvis = max(float(getattr(body, "radius", 1.0)), 0.2)
    return float(EARTH_RADIUS_KM * ((rvis / 8.0) ** (1.0 / 0.55)))

def physical_mass_for_collision(body):
    real = getattr(body, "physical_mass_kg", 0)
    if real:
        return float(real)
    # Estima massa por volume e densidade quando o corpo foi escalado manualmente.
    mat = getattr(body, "material", "rock")
    density = getattr(body, "density_kg_m3", None)
    if not density:
        density = {"rock":3300, "ice":1600, "metal":7800, "gas":1200, "plasma":1400, "stellar_system":1e-20}.get(mat, 3000)
    r_m = physical_radius_for_collision(body) * 1000.0
    volume = 4.0/3.0 * math.pi * r_m**3
    by_radius = volume * density
    by_slider = max(getattr(body, "mass", 1), 1) * 1e21
    return float(max(by_radius, by_slider))

def update_catalog_with_real_scales(catalog):
    for group in catalog.values():
        for e in group:
            fact=get_fact(e.get("name",""))
            if not fact: continue
            e["real"]=fact
            e["mass"]=fact["sim_mass"]
            e["radius"]=int(round(fact["display_radius"]))
            e["material"]=fact["material"]; e["family"]=fact["family"]
            fam=fact["family"]
            if fam in ("planet","gas_giant","ice_giant","dwarf_planet","moon"):
                e["desc"]=f"{fact['mass_kg']/EARTH_MASS_KG:.3g} M⊕"
            elif fam in ("star","white_dwarf","neutron_star","blackhole"):
                e["desc"]=f"{fact['mass_kg']/SOLAR_MASS_KG:.3g} M☉"
            elif fam=="galaxy":
                e["desc"]="escala galáctica"
    return catalog
