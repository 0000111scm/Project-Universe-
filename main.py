import pygame
import math
import random
import json
import os
from body import Body
from simulation import Simulation
from config import *
from catalog import BODY_CATALOG, STELLAR_EVOLUTION
from camera import screen_to_world, world_to_screen
from visuals.background import create_space_layers, draw_space_background
from systems.labels import should_draw_body_label, compact_body_label

pygame.init()
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Project Universe")
clock  = pygame.time.Clock()

sim = Simulation()
sim.time_scale = 0.5

def orbital_velocity(mc, d):
    return math.sqrt(G * mc / d)

cx, cy = SIM_W//2, HEIGHT//2

def _catalog_entry_for_name(name):
    base = str(name).lower().strip()
    parts = base.rsplit(" ", 1)
    if len(parts) == 2 and parts[1].isdigit():
        base = parts[0]
    for tab in BODY_CATALOG.values():
        for entry in tab:
            if str(entry.get("name", "")).lower().strip() == base:
                return entry
    return None


def _apply_catalog_physics(body, entry):
    if not entry:
        return body
    body.has_rings = bool(entry.get("has_rings", False))
    body.base_color = entry.get("color", body.color)
    body.luminosity = float(entry.get("luminosity", 0.0))
    if body.mass >= 1e9:
        body.material = "blackhole"
    elif body.mass >= 5e7:
        body.material = "plasma"
    elif body.mass >= 5e4:
        body.material = "gas"
    elif body.mass < 30 and getattr(body, "water", 0.0) > 0.3:
        body.material = "ice"
    else:
        body.material = getattr(body, "material", "rock")
    return body


def _add_stable(x, y, vx, vy, mass, radius, color, name):
    b = Body(x, y, vx, vy, mass, radius, color, name)
    _apply_catalog_physics(b, _catalog_entry_for_name(name))
    sim.add_body(b)

# Apenas os corpos principais em volta do Sol
_add_stable(cx, cy, 0, 0, M_SOL, 30, (255,210,50), "Sol")
_add_stable(cx+150, cy, 0, orbital_velocity(M_SOL,150), 1e3, 8,  (0,120,255),   "Terra")
_add_stable(cx+225, cy, 0, orbital_velocity(M_SOL,225), 8e2, 6,  (200,80,50),   "Marte")
_add_stable(cx+780, cy, 0, orbital_velocity(M_SOL,780), 3e5, 16, (180,140,80),  "Júpiter")

TABS       = list(BODY_CATALOG.keys())
active_tab = 0

slider_mass_mult = 1.0
slider_rad_mult  = 1.0
slider_vel_mult  = 1.0

show_vectors   = False
show_orbits    = False
show_hab_zone  = False
show_roche     = False
show_minimap   = True
show_graph     = False
show_gravity_zone = False
show_barycenter   = False
performance_mode  = False
show_advanced_options = False
advanced_rect = None
graph_mode     = "temp"  # "temp" | "vel" | "mass"

flares      = []
flare_timers= {}
collision_particles = []
orbit_cache = {}


# ══════════════════════════════════════════
# FUNDO ESTILO HUBBLE — gerado UMA VEZ na inicialização
# ══════════════════════════════════════════
_BG_LAYERS      = create_space_layers(BG_W, BG_H)
twinkle_time    = 0.0

selected_type      = None
selected_body      = None
followed_body      = None
editing_name       = False
edit_text          = ""
last_click_time    = 0
last_click_body    = None
planet_count       = 4
camera_offset      = pygame.Vector2(0,0)
zoom               = 1.0
zoom_target        = 1.0
cam_velocity       = pygame.Vector2(0.0, 0.0)
dragging           = False
drag_start         = pygame.Vector2(0,0)
dragging_body      = None
dragging_body_offset = pygame.Vector2(0,0)
running            = True
paused             = False
placing            = False
place_pos_world    = None
place_start_screen = None
preview_trail      = []
panel_scroll       = 0
dragging_slider    = None
slider_drag_start_x   = 0
slider_drag_start_val = 0.0
body_ages          = {}
graph_history      = {}   # body_id → {temp:[], vel:[], mass:[]}
current_slot       = 0

def get_save_path():
    if current_slot == 0: return SAVE_FILE
    return SAVE_SLOTS[current_slot-1]

font       = pygame.font.SysFont("arial", 13)
font_small = pygame.font.SysFont("arial", 11)
font_title = pygame.font.SysFont("arial", 12, bold=True)
font_big   = pygame.font.SysFont("arial", 14, bold=True)

btn_rects_bodies  = []
btn_rects_time    = []
tab_rects         = []
slider_rects      = {}
toggle_rects      = {}
save_rect         = None
load_rect         = None
pause_rect        = None



# ══════════════════════════════════════════
#  FÍSICA CORRIGIDA
# ══════════════════════════════════════════
def get_luminosity(body):
    """Luminosidade vem do catálogo quando disponível; massa é fallback."""
    lum = getattr(body, "luminosity", None)
    if lum is not None:
        return lum

    m = body.mass
    if m >= 1e12:   return 1e10
    if m >= 1e9:    return 0
    if m >= 5e10:   return 5e6
    if m >= 1e10:   return 1e5
    if m >= 5e7:    return 1.0
    return 0

def body_temperature(body):
    """
    T = 278 * (flux_total)^0.25
    flux = sum(L_estrela / d_UA²)
    d_UA = dist_px / HAB_SCALE
    Terra (150px do Sol, L=2): T = 278*(2/1)^0.25 ≈ 331K ~ OK
    """
    flux = 0.0
    for s in sim.bodies:
        if s is body: continue
        lum = get_luminosity(s)
        if lum <= 0: continue
        dist_px = max((body.pos - s.pos).length(), 1.0)
        dist_ua = dist_px / HAB_SCALE
        flux   += lum / (dist_ua ** 2)
    # efeito estufa da atmosfera
    atm_factor = 1.0 + getattr(body,'atmosphere',0)*0.15
    if flux <= 0:
        return max(3, int(3 * atm_factor))
    temp = 278.0 * (flux ** 0.25) * atm_factor
    return max(3, min(int(temp), 200000))

def body_type_str(body):
    if body.mass >= 1e12:  return "Galáxia / Núcleo Ativo"
    if body.mass >= 1e9 and getattr(body, "material", "") == "blackhole": return "Buraco Negro"
    if body.mass >= 5e7:   return "Estrela"
    if body.mass >= 5e4:   return "Gigante Gasoso"
    if body.mass >= 5e2:   return "Planeta"
    if body.mass >= 1e2:   return "Planeta Anão"
    if body.mass >= 1e1:   return "Lua"
    return "Corpo Menor"

def life_probability(body):
    """
    Condições:
    1. Deve ser planeta (50 ≤ massa ≤ 50000)
    2. Não pode ter luminosidade (não é estrela)
    3. Temperatura entre 200K e 450K
    4. Fator de massa planetária
    5. Precisa haver ao menos uma estrela no sistema
    """
    if body.mass < 50 or body.mass > 5e4: return 0.0
    if get_luminosity(body) > 0:          return 0.0

    temp = body_temperature(body)
    if temp <= 0: return 0.0

    # Curva gaussiana centrada em 288K (Terra), largura 70K
    temp_factor = math.exp(-((temp - 288)**2) / (2 * 70**2))

    # Fator de massa
    if body.mass < 100:
        mass_factor = (body.mass - 50) / 50.0
    elif body.mass <= 8000:
        mass_factor = 1.0
    elif body.mass <= 30000:
        mass_factor = 1.0 - (body.mass - 8000) / 22000.0
    else:
        mass_factor = 0.0

    # Fator atmosférico
    atm = getattr(body, 'atmosphere', 0)
    atm_factor = min(atm, 1.0) if atm > 0 else 0.3

    # Fator água
    water = getattr(body, 'water', 0)
    water_factor = min(water, 1.0) if water > 0 else 0.2

    # Presença de estrela
    has_star = any(get_luminosity(s) > 0 and s is not body for s in sim.bodies)
    star_factor = 1.0 if has_star else 0.05

    prob = temp_factor * mass_factor * atm_factor * water_factor * star_factor * 100.0
    return round(max(0.0, min(prob, 100.0)), 1)

def water_state(temp):
    if temp < 273:  return "Gelo ❄",    (160,210,255)
    if temp <= 373: return "Líquida 💧", (50,150,255)
    return "Vapor 💨",              (200,210,255)

def hab_zone_radii(body):
    lum = get_luminosity(body)
    if lum <= 0: return None, None
    r_inner = math.sqrt(lum / 1.1)  * HAB_SCALE
    r_outer = math.sqrt(lum / 0.53) * HAB_SCALE
    return r_inner, r_outer

def roche_limit(body):
    if body.mass < 1e4: return None
    return body.radius * 2.44 * ((body.mass / max(body.mass*0.001,1))**(1/3)) * 1.2

# ══════════════════════════════════════════
#  ÁGUA DINÂMICA VISUAL
# ══════════════════════════════════════════
def update_body_water_color(body):
    temp = body_temperature(body)
    water = getattr(body, 'water', 0)
    if water <= 0: return
    ws, _ = water_state(temp)
    base  = body.base_color
    if "Gelo" in ws:
        blend = (200,230,255)
    elif "Líquida" in ws:
        blend = (30,100,220)
    else:
        blend = base
    t = min(water, 1.0) * 0.4
    body.color = tuple(int(base[i]*(1-t) + blend[i]*t) for i in range(3))

# ══════════════════════════════════════════
#  ATMOSFERA
# ══════════════════════════════════════════
def estimate_atmosphere(body):
    """Estima atmosfera retida pela gravidade superficial e temperatura."""
    if body.mass < 50: return 0.0
    if get_luminosity(body) > 0: return 0.0
    temp = body_temperature(body)
    # Escape velocity proxy: proporcional a sqrt(mass/radius)
    esc = math.sqrt(body.mass / max(body.radius,1))
    # Quanto mais quente, mais fácil escapar
    retention = max(0.0, min(1.0, esc/50.0 - temp/5000.0))
    return round(retention * 2.0, 2)  # em bar (0–2)

# ══════════════════════════════════════════
#  TERRAFORMAÇÃO
# ══════════════════════════════════════════
terraforming_body  = None
terra_btn_rects    = {}
orbital_btn_rects  = {}


def _dominant_attractor(body):
    """Retorna o corpo que domina a órbita local."""
    candidates = [b for b in sim.bodies if b is not body and b.mass > body.mass]
    if not candidates:
        candidates = [b for b in sim.bodies if b is not body]
    if not candidates:
        return None
    return max(candidates, key=lambda other: other.mass / max((body.pos - other.pos).length_squared(), 1e-6))


def circularize_orbit(body):
    """Ajusta velocidade para órbita circular ao redor do atrator dominante."""
    attractor = _dominant_attractor(body)
    if not attractor:
        return False

    r_vec = body.pos - attractor.pos
    dist = r_vec.length()
    if dist <= max(body.radius + attractor.radius + 2.0, 1.0):
        return False

    tangent = pygame.Vector2(-r_vec.y, r_vec.x)
    if tangent.length_squared() == 0:
        return False
    tangent = tangent.normalize()

    current_rel_vel = body.vel - attractor.vel
    if current_rel_vel.length_squared() > 0 and current_rel_vel.dot(tangent) < 0:
        tangent *= -1

    speed = math.sqrt(G * attractor.mass / max(dist, 1e-6))
    body.vel = attractor.vel + tangent * speed
    body.acc.update(0.0, 0.0)
    body.trail.clear()
    body.collision_cooldown = 0.5
    return True


def preserve_orbit_after_drag(body):
    """Depois de arrastar pausado, recalcula velocidade tangencial estável."""
    attractor = _dominant_attractor(body)
    if not attractor:
        return False
    if body.mass >= attractor.mass * 0.75:
        return False
    return circularize_orbit(body)


def zero_body_velocity(body):
    """Zera velocidade explicitamente. Arrastar não faz mais isso."""
    body.vel.update(0.0, 0.0)
    body.acc.update(0.0, 0.0)
    body.trail.clear()
    body.collision_cooldown = 0.5
    return True


def draw_orbital_editor_panel(body):
    global orbital_btn_rects
    orbital_btn_rects = {}
    if not body or body not in sim.bodies:
        return

    w = 248
    h = 76
    x0 = SIM_W - w - 10
    y0 = HEIGHT - h - 156

    bg = pygame.Surface((w + 8, h + 8), pygame.SRCALPHA)
    pygame.draw.rect(bg, (8, 12, 26, 225), (0, 0, w + 8, h + 8), border_radius=8)
    pygame.draw.rect(bg, (70, 90, 180, 180), (0, 0, w + 8, h + 8), 1, border_radius=8)
    screen.blit(bg, (x0 - 4, y0 - 4))

    screen.blit(font_title.render("EDITOR ORBITAL", True, (150, 180, 255)), (x0, y0))
    screen.blit(font_small.render(f"Corpo: {body.name}", True, (165, 185, 220)), (x0, y0 + 16))

    y = y0 + 36
    buttons = [
        ("circularize", "Circularizar", (22, 50, 92), (70, 125, 230)),
        ("zero_velocity", "Zerar vel.", (65, 35, 30), (210, 90, 70)),
        ("follow", "Seguir", (24, 60, 42), (75, 180, 100)),
    ]

    bw = (w - 8) // 3
    for i, (key, label, bgc, border) in enumerate(buttons):
        rect = pygame.Rect(x0 + i * (bw + 4), y, bw, 24)
        pygame.draw.rect(screen, bgc, rect, border_radius=4)
        pygame.draw.rect(screen, border, rect, 1, border_radius=4)
        s = font_small.render(label, True, (225, 230, 240))
        screen.blit(s, s.get_rect(center=rect.center))
        orbital_btn_rects[key] = rect


def draw_terraforming_panel(body):
    global terra_btn_rects
    terra_btn_rects = {}
    w   = 248
    atm = getattr(body,'atmosphere',0)
    wtr = getattr(body,'water',0)
    co2 = getattr(body,'co2',0)
    n2  = getattr(body,'n2',0)
    alb = getattr(body,'albedo',0.3)
    temp = body_temperature(body)
    life = life_probability(body)
    params = [
        ("Atmosfera", f"{atm:.2f} bar", "atm",    (100,200,255),(60,80,120),   0.0, 3.0,  0.1),
        ("\xc1gua",   f"{wtr:.2f}",     "water",  (50,130,255), (30,60,160),   0.0, 1.0,  0.1),
        ("CO2",       f"{co2:.2f} bar", "co2",    (200,160,80), (120,80,30),   0.0, 2.0,  0.1),
        ("N2",        f"{n2:.2f} bar",  "n2",     (120,200,120),(60,120,60),   0.0, 2.0,  0.1),
        ("Albedo",    f"{alb:.2f}",     "albedo", (200,200,200),(100,100,100), 0.05,0.95, 0.05),
    ]
    h_panel = 34 + len(params)*22 + 48
    x0 = SIM_W - w - 10
    y0 = HEIGHT - h_panel - 30
    bg = pygame.Surface((w+8, h_panel+8), pygame.SRCALPHA)
    pygame.draw.rect(bg,(8,22,10,230),  (0,0,w+8,h_panel+8),border_radius=8)
    pygame.draw.rect(bg,(40,130,60,210),(0,0,w+8,h_panel+8),1,border_radius=8)
    screen.blit(bg,(x0-4,y0-4))
    screen.blit(font_title.render("TERRAFORMACAO",True,(80,220,100)),(x0,y0))
    screen.blit(font_small.render(f"Corpo: {body.name}",True,(160,220,170)),(x0,y0+16))
    y0+=34
    for label,val_str,key,col_up,col_dn,mn,mx_v,step in params:
        screen.blit(font_small.render(f"{label}: {val_str}",True,(170,220,190)),(x0,y0))
        r_up=pygame.Rect(x0+w-42,y0,18,14)
        r_dn=pygame.Rect(x0+w-20,y0,18,14)
        pygame.draw.rect(screen,col_up,r_up,border_radius=3)
        pygame.draw.rect(screen,col_dn,r_dn,border_radius=3)
        screen.blit(font_small.render("+",True,(255,255,255)),(r_up.x+4,r_up.y+1))
        screen.blit(font_small.render("-",True,(255,255,255)),(r_dn.x+5,r_dn.y+1))
        terra_btn_rects[f"{key}_up"]=(r_up,step,mn,mx_v)
        terra_btn_rects[f"{key}_dn"]=(r_dn,step,mn,mx_v)
        y0+=22
    lc=(80,255,100) if life>10 else (180,180,180)
    screen.blit(font_small.render(f"Temp: ~{temp}K   Vida: {life}%",True,lc),(x0,y0))
    y0+=20
    r_save =pygame.Rect(x0,    y0,100,20)
    r_close=pygame.Rect(x0+108,y0,100,20)
    pygame.draw.rect(screen,(20,60,30), r_save, border_radius=4)
    pygame.draw.rect(screen,(40,160,70),r_save, 1,border_radius=4)
    pygame.draw.rect(screen,(60,20,20), r_close,border_radius=4)
    pygame.draw.rect(screen,(160,50,50),r_close,1,border_radius=4)
    screen.blit(font_small.render("Salvar",True,(100,255,130)),(r_save.x+8, r_save.y+4))
    screen.blit(font_small.render("Fechar",True,(255,150,150)),(r_close.x+8,r_close.y+4))
    terra_btn_rects["save"] =r_save
    terra_btn_rects["close"]=r_close

# ══════════════════════════════════════════
#  GRÁFICOS
# ══════════════════════════════════════════
GRAPH_W, GRAPH_H = 220, 100
graph_modes = ["temp","vel","mass","life"]
graph_labels = {"temp":"Temperatura (K)","vel":"Velocidade (u/s)","mass":"Massa","life":"Habitabilidade (%)"}
graph_colors = {"temp":(255,180,80),"vel":(80,200,255),"mass":(180,100,255),"life":(80,255,120)}

def update_graph(dt):
    for body in sim.bodies:
        bid = id(body)
        if bid not in graph_history:
            graph_history[bid] = {"temp":[],"vel":[],"mass":[],"life":[]}
        h = graph_history[bid]
        for _k in ("temp","vel","mass","life"):
            if _k not in h: h[_k] = []
        h["temp"].append(body_temperature(body))
        h["vel"].append(body.vel.length())
        h["mass"].append(body.mass)
        h["life"].append(life_probability(body))
        for k in h:
            if len(h[k]) > GRAPH_W: h[k].pop(0)

graph_update_timer = 0.0

def draw_graph():
    if not selected_body or selected_body not in sim.bodies: return
    bid = id(selected_body)
    if bid not in graph_history: return
    data = graph_history[bid][graph_mode]
    if len(data) < 2: return

    # posicionar gráfico acima do body_info para não sobrepor
    _info_h = (len([1]*14)*15)+8+30  # altura estimada do body_info
    gx = 10
    gy = HEIGHT - 240 - (_info_h if selected_body and selected_body in sim.bodies else 0)
    bg = pygame.Surface((GRAPH_W+20, GRAPH_H+40), pygame.SRCALPHA)
    pygame.draw.rect(bg,(8,8,20,210),(0,0,GRAPH_W+20,GRAPH_H+40),border_radius=6)
    pygame.draw.rect(bg,(50,50,80,160),(0,0,GRAPH_W+20,GRAPH_H+40),1,border_radius=6)
    screen.blit(bg,(gx-4,gy-4))

    # Tabs do gráfico
    tw = (GRAPH_W+20)//3
    for i,gm in enumerate(graph_modes):
        rx = gx-4+i*tw
        sel = gm==graph_mode
        pygame.draw.rect(screen,(30,30,60) if sel else (15,15,30),(rx,gy-4,tw,14),border_radius=3)
        pygame.draw.rect(screen,graph_colors[gm],(rx,gy-4,tw,14),1,border_radius=3)
        screen.blit(font_small.render(gm,True,graph_colors[gm] if sel else (80,80,100)),(rx+4,gy-3))

    screen.blit(font_small.render(graph_labels[graph_mode],True,(140,140,160)),(gx,gy+8))

    mn = min(data); mx2 = max(data)
    span = max(mx2-mn, 1)
    pts = []
    for i,v in enumerate(data):
        px = gx + int(i * (GRAPH_W / max(len(data)-1,1)))
        py = gy + GRAPH_H + 16 - int((v-mn)/span * (GRAPH_H-4))
        pts.append((px,py))
    if len(pts)>1:
        pygame.draw.lines(screen,graph_colors[graph_mode],False,pts,1)

    screen.blit(font_small.render(f"{mx2:.1f}",True,(160,160,160)),(gx+GRAPH_W+2,gy+16))
    screen.blit(font_small.render(f"{mn:.1f}",True,(160,160,160)),(gx+GRAPH_W+2,gy+GRAPH_H+12))

# ══════════════════════════════════════════
#  SALVAR / CARREGAR
# ══════════════════════════════════════════
def save_simulation():
    data = {"bodies":[]}
    for b in sim.bodies:
        data["bodies"].append({
            "x":b.pos.x,"y":b.pos.y,"vx":b.vel.x,"vy":b.vel.y,
            "mass":b.mass,"radius":b.radius,"color":list(b.color),
            "base_color":list(getattr(b,'base_color',b.color)),
            "name":b.name,"atmosphere":getattr(b,'atmosphere',0),
            "water":getattr(b,'water',0),
            "is_fragment":getattr(b,'is_fragment',False),
            "show_label":getattr(b,'show_label',True)
        })
    with open(SAVE_FILE,"w") as f: json.dump(data,f,indent=2)

def load_simulation():
    global planet_count
    if not os.path.exists(SAVE_FILE): return
    with open(SAVE_FILE,"r") as f: data=json.load(f)
    sim.bodies.clear(); body_ages.clear(); graph_history.clear()
    for bd in data["bodies"]:
        b = Body(bd["x"],bd["y"],bd["vx"],bd["vy"],bd["mass"],bd["radius"],tuple(bd["color"]),bd["name"])
        b.base_color  = tuple(bd.get("base_color",bd["color"]))
        b.atmosphere  = bd.get("atmosphere",0)
        b.water       = bd.get("water",0)
        b.is_fragment = bd.get("is_fragment",False)
        b.show_label  = bd.get("show_label", not b.is_fragment)
        b.label_timer = 0.0
        b.co2         = bd.get("co2",0)
        b.n2          = bd.get("n2",0)
        b.albedo      = bd.get("albedo",0.3)
        b._terra_set  = True
        sim.add_body(b)
    planet_count = len(sim.bodies)

# ══════════════════════════════════════════
#  FLARES
# ══════════════════════════════════════════
def update_flares(dt):
    for body in sim.bodies:
        lum = get_luminosity(body)
        if lum < 1.0: continue
        bid = id(body)
        if bid not in flare_timers:
            flare_timers[bid] = random.uniform(5,20)
        flare_timers[bid] -= dt*sim.time_scale
        if flare_timers[bid] <= 0:
            flare_timers[bid] = random.uniform(8,25)
            angle = random.uniform(0, math.pi*2)
            speed = random.uniform(80,200)
            for _ in range(8):
                ang2 = angle + random.uniform(-0.4,0.4)
                flares.append({
                    "pos":  pygame.Vector2(body.pos),
                    "vel":  pygame.Vector2(math.cos(ang2)*speed, math.sin(ang2)*speed),
                    "timer": random.uniform(0.3,0.7),
                    "max_timer": 0.7,
                    "radius": random.uniform(2,5),
                    "color": body.color,
                })

def spawn_collision_particles(pos,kind,count=30):
    import math as _m
    cfg={"merge":{"sp":(40,120),"li":(0.4,0.9),"sz":(2,5),"cl":[(255,220,100),(255,180,60),(200,140,40)]},
         "nova": {"sp":(80,300),"li":(0.6,1.4),"sz":(2,6),"cl":[(255,255,180),(255,220,80),(255,140,40),(255,80,20)]},
         "blackhole":{"sp":(20,80),"li":(0.5,1.2),"sz":(2,4),"cl":[(180,60,255),(120,20,200),(200,100,255)]},
         "absorb":{"sp":(30,100),"li":(0.3,0.7),"sz":(1,4),"cl":[(255,120,50),(255,80,20),(200,60,10)]},
    }.get(kind,{"sp":(40,120),"li":(0.4,0.9),"sz":(2,5),"cl":[(255,220,100)]})
    for _ in range(count):
        a=random.uniform(0,_m.pi*2); sp=random.uniform(*cfg["sp"])
        _life=random.uniform(*cfg["li"])
        collision_particles.append({
            "pos":pygame.Vector2(pos),
            "vel":pygame.Vector2(_m.cos(a)*sp,_m.sin(a)*sp),
            "timer":_life,
            "max_timer":max(_life,0.001),
            "size":random.uniform(*cfg["sz"]),
            "color":random.choice(cfg["cl"]),
        })

def update_collision_particles(dt):
    for p in collision_particles[:]:
        p["pos"]+=p["vel"]*dt  # sem time_scale: partículas são visuais, não físicas
        p["vel"]*=max(0,1-dt*1.5)
        p["timer"]-=dt
        if p["timer"]<=0: collision_particles.remove(p)

def draw_collision_particles():
    for p in collision_particles:
        sx,sy=world_to_screen(p["pos"],camera_offset,zoom,cx,cy)
        if not (0<=sx<=SIM_W and 0<=sy<=HEIGHT): continue
        alpha=max(0,min(255,int(220*(p["timer"]/max(p["max_timer"],0.001)))))
        r=max(1,int(p["size"]*zoom))
        c=p["color"]
        color4=(max(0,min(255,int(c[0]))),max(0,min(255,int(c[1]))),max(0,min(255,int(c[2]))),alpha)
        s=pygame.Surface((r*2+2,r*2+2),pygame.SRCALPHA)
        pygame.draw.circle(s,color4,(r+1,r+1),r)
        screen.blit(s,(sx-r-1,sy-r-1))

def draw_flares():
    for fl in flares:
        sx,sy = world_to_screen(fl["pos"],camera_offset,zoom,cx,cy)
        r     = max(1,int(fl["radius"]*zoom))
        alpha = int(220*(fl["timer"]/fl["max_timer"]))
        if r > 0:
            fs = pygame.Surface((r*2+2,r*2+2),pygame.SRCALPHA)
            pygame.draw.circle(fs,(*fl["color"],alpha),(r+1,r+1),r)
            screen.blit(fs,(sx-r-1,sy-r-1))

# ══════════════════════════════════════════
#  MINIMAPA
# ══════════════════════════════════════════
MINI_W,MINI_H = 160,100
MINI_X = SIM_W - MINI_W - 8
MINI_Y = HEIGHT - MINI_H - 8

def draw_minimap():
    if not sim.bodies: return
    xs=[b.pos.x for b in sim.bodies]; ys=[b.pos.y for b in sim.bodies]
    min_x,max_x=min(xs)-50,max(xs)+50; min_y,max_y=min(ys)-50,max(ys)+50
    span_x=max(max_x-min_x,1); span_y=max(max_y-min_y,1)
    surf=pygame.Surface((MINI_W,MINI_H),pygame.SRCALPHA)
    pygame.draw.rect(surf,(8,8,20,200),(0,0,MINI_W,MINI_H),border_radius=4)
    pygame.draw.rect(surf,(50,50,80,180),(0,0,MINI_W,MINI_H),1,border_radius=4)
    for body in sim.bodies:
        mx2=int((body.pos.x-min_x)/span_x*MINI_W)
        my2=int((body.pos.y-min_y)/span_y*MINI_H)
        mr=max(1,int(body.radius*MINI_W/span_x*2))
        pygame.draw.circle(surf,body.color,(mx2,my2),min(mr,6))
    screen.blit(surf,(MINI_X,MINI_Y))
    screen.blit(font_small.render("MAPA",True,(80,80,120)),(MINI_X+4,MINI_Y+2))

# ══════════════════════════════════════════
#  RENDERIZAÇÃO
# ══════════════════════════════════════════
def draw_hab_zone():
    for body in sim.bodies:
        r_in,r_out=hab_zone_radii(body)
        if r_in is None: continue
        sx,sy=world_to_screen(body.pos,camera_offset,zoom,cx,cy)
        ri,ro=int(r_in*zoom),int(r_out*zoom)
        if ro<3000:
            s=pygame.Surface((ro*2+4,ro*2+4),pygame.SRCALPHA)
            pygame.draw.circle(s,(0,255,100,12),(ro+2,ro+2),ro)
            pygame.draw.circle(s,(0,0,0,0),(ro+2,ro+2),ri)
            screen.blit(s,(sx-ro-2,sy-ro-2))
            pygame.draw.circle(screen,(0,160,60),(sx,sy),ro,1)
            pygame.draw.circle(screen,(0,160,60),(sx,sy),ri,1)

def draw_roche_limit():
    for body in sim.bodies:
        rl=roche_limit(body)
        if rl is None: continue
        sx,sy=world_to_screen(body.pos,camera_offset,zoom,cx,cy)
        r=int(rl*zoom)
        if r>=3000: continue
        # anel de Roche pulsante
        pulse=0.96+0.04*math.sin(twinkle_time*3)
        rp=int(r*pulse)
        s=pygame.Surface((rp*2+4,rp*2+4),pygame.SRCALPHA)
        pygame.draw.circle(s,(200,50,50,60),(rp+2,rp+2),rp,0)
        pygame.draw.circle(s,(200,50,50,160),(rp+2,rp+2),rp,1)
        screen.blit(s,(sx-rp-2,sy-rp-2))
        # verificar corpos dentro do limite e mostrar deformação
        for small in sim.bodies:
            if small is body or small.mass > body.mass: continue
            dist=(small.pos-body.pos).length()
            if dist<rl:
                ratio=max(0,1.0-(dist/rl))
                ssx,ssy=world_to_screen(small.pos,camera_offset,zoom,cx,cy)
                sr=max(2,int(small.radius*zoom))
                # elipse deformada apontando para o corpo massivo
                angle=math.atan2(body.pos.y-small.pos.y,body.pos.x-small.pos.x)
                stretch=1.0+ratio*0.6
                squeeze=1.0-ratio*0.3
                de=pygame.Surface((int(sr*stretch*2+4),int(sr*squeeze*2+4)),pygame.SRCALPHA)
                pygame.draw.ellipse(de,(*small.color,120),(0,0,int(sr*stretch*2),int(sr*squeeze*2)))
                rs=pygame.transform.rotate(de,-math.degrees(angle))
                screen.blit(rs,(ssx-rs.get_width()//2,ssy-rs.get_height()//2))

def draw_orbit_prediction(body):
    """Orbita analitica com cache simples para reduzir custo quando ha muitos corpos."""
    if not sim.bodies: return
    if performance_mode and getattr(body, "is_fragment", False): return
    if len(sim.bodies) > 120 and body.mass < 10: return

    others=[b for b in sim.bodies if b is not body]
    if not others: return
    attractor=max(others,key=lambda b:b.mass)

    cache_key = (
        id(body), id(attractor),
        int(body.pos.x//4), int(body.pos.y//4),
        int(body.vel.x//2), int(body.vel.y//2),
        int(attractor.pos.x//4), int(attractor.pos.y//4),
        int(attractor.mass//1000)
    )
    world_pts = orbit_cache.get(cache_key)
    if world_pts is None:
        delta=body.pos-attractor.pos
        dist=delta.length()
        if dist<1: return
        speed=body.vel.length()
        if speed<0.01: return
        mu=G*attractor.mass
        try:
            energy=0.5*speed**2-mu/dist
            if energy>=0: return
            a=-mu/(2*energy)
            if a <= 0 or a > 20000: return
            h=abs(delta.x*body.vel.y-delta.y*body.vel.x)
            p=h**2/mu
            ecc=math.sqrt(max(0,1-p/a))
            if ecc>=1: return
            b_axis=a*math.sqrt(1-ecc**2)
            angle=math.atan2(delta.y,delta.x)
            cx_orb=attractor.pos.x-ecc*a*math.cos(angle)
            cy_orb=attractor.pos.y-ecc*a*math.sin(angle)
        except Exception:
            return
        step_deg = 8 if performance_mode else 4
        world_pts=[]
        for deg in range(0,360,step_deg):
            t=math.radians(deg)
            ex=cx_orb+a*math.cos(t)*math.cos(angle)-b_axis*math.sin(t)*math.sin(angle)
            ey=cy_orb+a*math.cos(t)*math.sin(angle)+b_axis*math.sin(t)*math.cos(angle)
            world_pts.append((ex,ey))
        if len(orbit_cache) > 180:
            orbit_cache.clear()
        orbit_cache[cache_key] = world_pts

    pts=[]
    for ex,ey in world_pts:
        sx2,sy2=world_to_screen(pygame.Vector2(ex,ey),camera_offset,zoom,cx,cy)
        if -3000<=sx2<=SIM_W+3000 and -3000<=sy2<=HEIGHT+3000:
            pts.append((sx2,sy2))
    if len(pts)>2:
        s=pygame.Surface((SIM_W,HEIGHT),pygame.SRCALPHA)
        alpha = 28 if performance_mode else 42
        pygame.draw.lines(s,(*body.color[:3],alpha),True,pts,1)
        screen.blit(s,(0,0))

def get_body_at(mx,my):
    for body in sim.bodies:
        sx,sy=world_to_screen(body.pos,camera_offset,zoom,cx,cy)
        if math.hypot(mx-sx,my-sy)<=max(body.radius*zoom,6): return body
    return None


random.seed(42)
_neb_palette = [
    (15, 8, 55),
    (8, 25, 55),
    (50, 8, 35),
    (8, 45, 35),
    (55, 28, 8),
    (30, 8, 50),
]
NEBULAS = []
for _ in range(12):
    NEBULAS.append((
        random.randint(0,SIM_W), random.randint(0,HEIGHT),
        random.randint(180,480), random.randint(120,320),
        random.choice(_neb_palette)
    ))

def draw_stars():
    """Fundo espacial em camadas com paralaxe, menos arcade e mais realista."""
    draw_space_background(screen, _BG_LAYERS, camera_offset, zoom, SIM_W, HEIGHT, low_quality=performance_mode)


def draw_rings(body,sx,sy,r):
    rw=int(r*2.2); rh=int(r*0.35)
    if rw<4 or rh<2: return
    surf=pygame.Surface((rw*2+4,rh*2+4),pygame.SRCALPHA)
    bc=tuple(min(c+40,255) for c in body.color)
    for i,(rwo,alpha) in enumerate([(0,80),(rw//6,50),(rw//3,30)]):
        rw2=rw-rwo; rh2=max(1,rh-rwo//4)
        pygame.draw.ellipse(surf,(*bc,alpha),(rw+2-rw2,rh+2-rh2,rw2*2,rh2*2),max(1,i+1))
    screen.blit(surf,(sx-rw-2,sy-rh-2))


_texture_cache = {}

def draw_planet_texture(body, sx, sy, r):
    if r < 2: return
    import hashlib
    impact_dynamic = bool(getattr(body, "impact_marks", [])) or getattr(body, "impact_flash", 0.0) > 0
    ckey = (id(body), r, body.color)
    if (not impact_dynamic) and ckey in _texture_cache:
        screen.blit(_texture_cache[ckey], (sx-r-1, sy-r-1))
        return
    if True:
        rng = random.Random(int(hashlib.md5(body.name.encode()).hexdigest()[:8], 16))
        s   = pygame.Surface((r*2+2, r*2+2), pygame.SRCALPHA)
        bc  = body.color
        nm  = body.name.lower()

        def band(surface, n_bands, alpha):
            for i in range(n_bands):
                fc2 = (min(255,bc[0]+rng.randint(-30,30)),
                       min(255,bc[1]+rng.randint(-20,20)),
                       max(0,  bc[2]+rng.randint(-20,20)))
                by2 = r+1-r + int(i*r*2/n_bands)
                bh3 = max(2, r*2//n_bands+1)
                ss2 = pygame.Surface((r*2+2,bh3),pygame.SRCALPHA)
                pygame.draw.rect(ss2,(*fc2,alpha),(0,0,r*2+2,bh3))
                surface.blit(ss2,(0,by2))

        if any(x in nm for x in ["terra","earth"]):
            pygame.draw.circle(s,bc,(r+1,r+1),r)
            oc=(max(0,bc[0]-50),min(255,bc[1]+10),min(255,bc[2]+60))
            for _ in range(5):
                ox2,oy2=rng.randint(-r//2,r//2),rng.randint(-r//2,r//2)
                rr2=rng.randint(r//3,r//2+1)
                ss2=pygame.Surface((rr2*2,rr2*2),pygame.SRCALPHA)
                pygame.draw.ellipse(ss2,(*oc,130),(0,0,rr2*2,rr2*2))
                s.blit(ss2,(r+1+ox2-rr2,r+1+oy2-rr2))
            cc2=(min(255,bc[0]+30),min(255,bc[1]+40),max(0,bc[2]-40))
            for _ in range(3):
                ox2,oy2=rng.randint(-r//2,r//2),rng.randint(-r//2,r//2)
                rw2,rh2=rng.randint(r//4,r//2),rng.randint(r//5,r//3)
                ss2=pygame.Surface((rw2*2,rh2*2),pygame.SRCALPHA)
                pygame.draw.ellipse(ss2,(*cc2,170),(0,0,rw2*2,rh2*2))
                s.blit(ss2,(r+1+ox2-rw2,r+1+oy2-rh2))
            pygame.draw.ellipse(s,(230,245,255,150),(r+1-r//3,2,max(1,int(r/1.5)),max(1,r//3)))
        elif any(x in nm for x in ["júpiter","jupiter"]):
            pygame.draw.circle(s,bc,(r+1,r+1),r)
            band(s,8,110)
            mw,mh=max(1,r//2+1),max(1,r//3+1)
            ms2=pygame.Surface((mw,mh),pygame.SRCALPHA)
            pygame.draw.ellipse(ms2,(200,70,40,180),(0,0,mw,mh))
            s.blit(ms2,(r+1+r//5,r+1+r//8))
        elif any(x in nm for x in ["saturno","saturn"]):
            pygame.draw.circle(s,bc,(r+1,r+1),r)
            band(s,6,90)
        elif any(x in nm for x in ["lua","moon","calisto","ganimedes","titã","encélado","tritão","io","europa"]):
            pygame.draw.circle(s,bc,(r+1,r+1),r)
            cb2=tuple(max(0,c-45) for c in bc)
            cl2=tuple(min(255,c+25) for c in bc)
            for _ in range(max(3,r//2)):
                cx3=rng.randint(r//4,3*r//2+1); cy3=rng.randint(r//4,3*r//2+1)
                cr2=rng.randint(max(1,r//8),max(2,r//4))
                if math.hypot(cx3-(r+1),cy3-(r+1))+cr2>r: continue
                pygame.draw.circle(s,cb2,(cx3,cy3),cr2)
                pygame.draw.circle(s,cl2,(cx3,cy3),cr2,1)
        elif any(x in nm for x in ["marte","mars","mercúrio","mercurio"]):
            pygame.draw.circle(s,bc,(r+1,r+1),r)
            if "marte" in nm: pygame.draw.ellipse(s,(240,248,255,140),(r+1-r//4,2,max(1,r//2),max(1,r//4)))
            for _ in range(max(2,r//3)):
                cx3=rng.randint(r//3,3*r//2); cy3=rng.randint(r//3,3*r//2)
                cr2=rng.randint(max(1,r//10),max(2,r//5))
                if math.hypot(cx3-(r+1),cy3-(r+1))+cr2>r: continue
                pygame.draw.circle(s,tuple(max(0,c-30) for c in bc),(cx3,cy3),cr2)
        elif any(x in nm for x in ["vênus","venus"]):
            pygame.draw.circle(s,bc,(r+1,r+1),r)
            band(s,5,80)
        elif any(x in nm for x in ["sol","sun","sirius","alfa","rigel","betelgeuse","vega","canopus",
                                    "estrela","anã","gigante","supergigante","hipergigante"]):
            for i in range(r,0,-2):
                t=i/r
                sc2=(min(255,int(bc[0]*t+255*(1-t))),min(255,int(bc[1]*t+220*(1-t))),max(0,int(bc[2]*t+50*(1-t))))
                pygame.draw.circle(s,sc2,(r+1,r+1),i)
        elif any(x in nm for x in ["buraco","bn ","pulsar","magnetar","quasar"]):
            pygame.draw.circle(s,(0,0,0),(r+1,r+1),r)
            disc=pygame.Surface((r*2+2,r*2+2),pygame.SRCALPHA)
            for i in range(r+r//3,max(1,r-r//4),-1):
                t=(i-(r-r//4))/max(r//3*2,1)
                ac=(min(255,int(220*t)),min(255,int(90*t)),0,max(0,int(70*t)))
                pygame.draw.circle(disc,ac,(r+1,r+1),i,1)
            s.blit(disc,(0,0))
        else:
            pygame.draw.circle(s,bc,(r+1,r+1),r)
            hi=pygame.Surface((r*2+2,r*2+2),pygame.SRCALPHA)
            pygame.draw.circle(hi,(255,255,255,20),(r+1-r//4,r+1-r//4),max(1,r//2))
            s.blit(hi,(0,0))

        # Patch 35: marcas locais de impacto/cratera/raspão presas ao corpo.
        for mk in getattr(body, "impact_marks", [])[-8:]:
            age = mk.get("age", 0.0)
            life = max(mk.get("life", 8.0), 0.1)
            alpha = int(180 * max(0.0, 1.0 - age / life))
            sev = mk.get("severity", 0.2)
            scrape = mk.get("scrape", 0.0)
            theta = mk.get("angle", 0.0) + getattr(body, "spin", 0.0)
            dist = r * 0.58
            mx = int(r + 1 + math.cos(theta) * dist)
            my = int(r + 1 + math.sin(theta) * dist)
            mw = max(2, int(r * (0.18 + sev * 0.42) * (1.0 + scrape * 1.8)))
            mh = max(2, int(r * (0.12 + sev * 0.25) * (1.0 - scrape * 0.35)))
            mark_s = pygame.Surface((mw*2+4, mh*2+4), pygame.SRCALPHA)
            pygame.draw.ellipse(mark_s, (45, 22, 10, alpha), (2,2,mw*2,mh*2))
            pygame.draw.ellipse(mark_s, (230, 95, 35, alpha//3), (mw//2+2,mh//2+2,max(2,mw),max(2,mh)))
            mark_s = pygame.transform.rotate(mark_s, -math.degrees(theta))
            s.blit(mark_s, (mx - mark_s.get_width()//2, my - mark_s.get_height()//2))

        flash = getattr(body, "impact_flash", 0.0)
        if flash > 0:
            fl_alpha = int(90 * min(1.0, flash))
            pygame.draw.circle(s, (255, 210, 120, fl_alpha), (r+1, r+1), r)

        mask=pygame.Surface((r*2+2,r*2+2),pygame.SRCALPHA)
        pygame.draw.circle(mask,(255,255,255,255),(r+1,r+1),r)
        s.blit(mask,(0,0),special_flags=pygame.BLEND_RGBA_MULT)
        if not impact_dynamic:
            _texture_cache[ckey]=s
    screen.blit(s,(sx-r-1,sy-r-1))

def draw_body_effects(body,sx,sy,r):
    btype="small"
    if body.mass>=5e6:    btype="blackhole"
    elif body.mass>=2e5:  btype="star"
    elif body.mass>=5e2:  btype="planet"
    if "Cometa" in body.name: btype="comet"
    if body.mass>=1e11:   btype="galaxy"

    if btype=="star":
        lum=get_luminosity(body)
        hi=min(math.log10(max(lum,0.001)+1)/6.0,1.0)
        for hr_m,ba in [(r*5,7),(r*3,16),(r*1.8,38)]:
            hr=int(hr_m)
            if hr>0:
                a=int(ba*(0.4+0.6*hi))
                hs=pygame.Surface((hr*2+2,hr*2+2),pygame.SRCALPHA)
                pygame.draw.circle(hs,(*body.color,a),(hr+1,hr+1),hr)
                screen.blit(hs,(sx-hr-1,sy-hr-1))
    elif btype=="blackhole":
        angle=twinkle_time*80
        for i in range(16):
            a=math.radians(angle+i*22.5)
            dr=r+5+int(4*math.sin(twinkle_time*4+i))
            ex=int(sx+dr*math.cos(a)); ey=int(sy+dr*0.3*math.sin(a))
            pygame.draw.circle(screen,(200,80,255) if i%2==0 else (100,20,180),(ex,ey),2)
        hs=pygame.Surface((r*8,r*8),pygame.SRCALPHA)
        pygame.draw.circle(hs,(100,0,160,18),(r*4,r*4),r*4)
        pygame.draw.circle(hs,(0,0,0,255),(r*4,r*4),r)
        screen.blit(hs,(sx-r*4,sy-r*4))
    elif btype=="comet":
        if body.vel.length()>0:
            td=-body.vel.normalize()
            for i in range(1,14):
                tx=int(sx+td.x*i*5); ty=int(sy+td.y*i*5)
                a=max(0,200-i*15); sz=max(1,r-i//4)
                ts=pygame.Surface((sz*2+2,sz*2+2),pygame.SRCALPHA)
                pygame.draw.circle(ts,(*body.color,a),(sz+1,sz+1),sz)
                screen.blit(ts,(tx-sz-1,ty-sz-1))
    elif btype=="galaxy":
        for arm in range(2):
            for i in range(1,30):
                ang2=math.radians(arm*180+i*15+twinkle_time*5)
                d2=i*r*0.15
                gx2=int(sx+d2*math.cos(ang2)); gy2=int(sy+d2*0.5*math.sin(ang2))
                a=max(0,160-i*5)
                pygame.draw.circle(screen,(*body.color[:3],a),(gx2,gy2),max(1,2-i//15))
    elif btype=="planet":
        # indica água visualmente
        water=getattr(body,'water',0)
        if water>0.3:
            wtemp=body_temperature(body)
            ws,wc=water_state(wtemp)
            if "Líquida" in ws:
                hs=pygame.Surface((r*3,r*3),pygame.SRCALPHA)
                pygame.draw.circle(hs,(*wc,40),(r*3//2,r*3//2),r*3//2)
                screen.blit(hs,(sx-r*3//2,sy-r*3//2))

    if getattr(body, "has_rings", False):
        draw_rings(body, sx, sy, r)
    else:
        entry = _catalog_entry_for_name(body.name)
        if entry and entry.get("has_rings"):
            body.has_rings = True
            draw_rings(body, sx, sy, r)

def draw_velocity_vector(body,sx,sy,r):
    speed=body.vel.length()
    if speed<0.1: return
    scale=min(speed*0.15,70)
    norm=body.vel.normalize()
    ex=int(sx+norm.x*(r+scale)); ey=int(sy+norm.y*(r+scale))
    pygame.draw.line(screen,(80,255,80),(sx,sy),(ex,ey),1)
    ang=math.atan2(norm.y,norm.x)
    for da in [0.5,-0.5]:
        pygame.draw.line(screen,(80,255,80),(ex,ey),(int(ex-8*math.cos(ang+da)),int(ey-8*math.sin(ang+da))),1)

def draw_acceleration_vector(body, sx, sy, r):
    if body.acc.length() < 0.0001:
        return
    norm = body.acc.normalize()
    scale = min(body.acc.length() * 140.0, 55)
    ex = int(sx + norm.x * (r + scale))
    ey = int(sy + norm.y * (r + scale))
    pygame.draw.line(screen, (90, 160, 255), (sx, sy), (ex, ey), 1)

def hill_radius(body):
    if body.mass <= 0 or len(sim.bodies) < 2:
        return None
    hosts = [b for b in sim.bodies if b is not body and b.mass > body.mass]
    if not hosts:
        return None
    host = max(hosts, key=lambda h: h.mass / max((h.pos - body.pos).length_squared(), 25.0))
    dist = (body.pos - host.pos).length()
    if dist <= 1:
        return None
    return dist * (body.mass / (3.0 * host.mass)) ** (1.0 / 3.0)

def draw_gravity_zones():
    if len(sim.bodies) < 2:
        return
    surf = pygame.Surface((SIM_W, HEIGHT), pygame.SRCALPHA)
    for body in sim.bodies:
        if getattr(body, 'is_fragment', False) or body.mass < 10:
            continue
        hr = hill_radius(body)
        if not hr:
            continue
        sx, sy = world_to_screen(body.pos, camera_offset, zoom, cx, cy)
        rr = int(hr * zoom)
        if rr < 8 or rr > max(SIM_W, HEIGHT) * 3:
            continue
        color = (90, 140, 255, 34) if body.mass < 2e5 else (255, 190, 80, 26)
        pygame.draw.circle(surf, color, (sx, sy), rr, 1)
        if selected_body is body or followed_body is body:
            pygame.draw.circle(surf, (110, 180, 255, 72), (sx, sy), rr, 2)
    screen.blit(surf, (0, 0))

def system_barycenter():
    total = sum(max(0.0, b.mass) for b in sim.bodies)
    if total <= 0:
        return None
    p = pygame.Vector2(0, 0)
    v = pygame.Vector2(0, 0)
    for b in sim.bodies:
        p += b.pos * b.mass
        v += b.vel * b.mass
    return p / total, v / total

def draw_barycenter():
    bc = system_barycenter()
    if not bc:
        return
    pos, vel = bc
    sx, sy = world_to_screen(pos, camera_offset, zoom, cx, cy)
    if not (-80 <= sx <= SIM_W + 80 and -80 <= sy <= HEIGHT + 80):
        return
    pulse = 7 + int(2 * math.sin(twinkle_time * 4))
    pygame.draw.circle(screen, (255, 220, 90), (sx, sy), pulse, 1)
    pygame.draw.line(screen, (255, 220, 90), (sx - 10, sy), (sx + 10, sy), 1)
    pygame.draw.line(screen, (255, 220, 90), (sx, sy - 10), (sx, sy + 10), 1)
    if vel.length() > 0.01:
        n = vel.normalize()
        pygame.draw.line(screen, (255, 180, 80), (sx, sy), (int(sx + n.x * 30), int(sy + n.y * 30)), 1)
    screen.blit(font_small.render('Baricentro', True, (255, 220, 120)), (sx + 12, sy - 8))

_spawned_events=set()
def draw_collision_events():
    """Patch 35: eventos de colisão sem círculos arcade.
    Mostra só flash térmico curto + texto discreto; detritos físicos fazem o resto."""
    active_ids={id(ev) for ev in sim.collision_events}
    for eid in list(_spawned_events):
        if eid not in active_ids:
            _spawned_events.discard(eid)
    for ev in sim.collision_events:
        eid=id(ev)
        if eid not in _spawned_events:
            _pc = 6 if len(sim.bodies) > 180 else (14 if ev.kind in ("stellar","impact","scrape") else 8)
            spawn_collision_particles(ev.pos, ev.kind, _pc)
            _spawned_events.add(eid)

        sx, sy = world_to_screen(ev.pos, camera_offset, zoom, cx, cy)
        if not (-50 <= sx <= SIM_W + 50 and -50 <= sy <= HEIGHT + 50):
            continue

        progress = 1.0 - (ev.timer / 0.4)
        fade = max(0, min(255, int(170 * (1.0 - progress))))
        heat = pygame.Surface((42, 42), pygame.SRCALPHA)
        pygame.draw.circle(heat, (255, 230, 150, fade // 3), (21, 21), 20)
        pygame.draw.circle(heat, (255, 150, 60, fade // 2), (21, 21), 8)
        screen.blit(heat, (sx - 21, sy - 21))

        label_map = {
            "impact": "impacto",
            "scrape": "raspão",
            "ejecta": "ejecta",
            "spall": "estilhaços",
            "stellar": "fusão estelar",
            "absorb": "acréscimo",
        }
        label = label_map.get(ev.kind, "")
        if label and fade > 35:
            surf = font_small.render(label, True, (220, 150, 90))
            surf.set_alpha(fade)
            screen.blit(surf, (sx + 8, sy - 10))

# ══════════════════════════════════════════
#  PAINEL LATERAL — LAYOUT FIXO POR ZONAS
# ══════════════════════════════════════════
# Zonas fixas (de baixo pra cima):
ZONE_TIME_H    = 22   # velocidade do tempo
ZONE_SAVLOAD_H = 26   # salvar/carregar
ZONE_SEP       = 4    # separadores
ZONE_TOGGLE_H  = 112  # toggles em grade, 2 colunas
ZONE_SLIDER_H  = 112  # 3 sliders
ZONE_HEADER_H  = 16   # título de seção
ZONE_TABS_H    = 22   # abas
ZONE_TITLE_H   = 22   # título projeto

FIXED_BOTTOM = (2 + ZONE_HEADER_H +
                ZONE_SLIDER_H + ZONE_SEP +
                2 + ZONE_HEADER_H + ZONE_SEP +
                ZONE_TOGGLE_H + ZONE_SEP +
                2 + ZONE_TIME_H)

LIST_TOP    = ZONE_TITLE_H + ZONE_TABS_H   # 44px
LIST_BOTTOM = HEIGHT - FIXED_BOTTOM        # espaço disponível para lista

def draw_slider(label,val,mn,mx_v,x,y,w,key):
    slider_rects[key]=pygame.Rect(x,y,w,10)
    pygame.draw.rect(screen,(22,22,42),(x,y,w,10),border_radius=5)
    t=(val-mn)/(mx_v-mn); kx=int(x+t*w)
    pygame.draw.rect(screen,(50,85,165),(x,y,int(t*w),10),border_radius=5)
    pygame.draw.circle(screen,(140,170,245),(kx,y+5),7)
    screen.blit(font_small.render(f"{label}: {val:.1f}x",True,(140,155,185)),(x,y-13))

def draw_panel():
    global btn_rects_bodies,btn_rects_time,tab_rects,save_rect,load_rect,toggle_rects,advanced_rect,pause_rect

    # Fundo
    for i in range(PANEL_W):
        pygame.draw.line(screen,(10+i//50,10,20),(SIM_W+i,0),(SIM_W+i,HEIGHT))
    pygame.draw.line(screen,(50,50,90),(SIM_W,0),(SIM_W,HEIGHT),1)

    # ── TÍTULO (topo fixo) ──
    ts=font_big.render("⬡ PROJECT UNIVERSE",True,(120,140,235))
    screen.blit(ts,(SIM_W+PANEL_W//2-ts.get_width()//2,4))
    pygame.draw.line(screen,(30,30,70),(SIM_W+4,ZONE_TITLE_H),(SIM_W+PANEL_W-4,ZONE_TITLE_H),1)

    # ── ABAS (topo fixo) ──
    tab_rects=[]
    tw=PANEL_W//len(TABS)
    for i,tab in enumerate(TABS):
        tx=SIM_W+i*tw
        rect=pygame.Rect(tx,ZONE_TITLE_H,tw,ZONE_TABS_H)
        tab_rects.append(rect)
        sel=active_tab==i
        pygame.draw.rect(screen,(35,35,72) if sel else (14,14,28),rect)
        pygame.draw.rect(screen,(90,90,180) if sel else (30,30,55),rect,1)
        short=tab[:4] if len(tab)>5 else tab
        lbl=font_small.render(short,True,(210,210,255) if sel else (90,90,130))
        screen.blit(lbl,lbl.get_rect(center=rect.center))

    # ── LISTA DE CORPOS (zona scrollável) ──
    bodies_list=list(BODY_CATALOG.values())[active_tab]
    y=LIST_TOP+2-panel_scroll
    btn_rects_bodies=[]
    for i,btype in enumerate(bodies_list):
        bx=SIM_W+4; bw=PANEL_W-8; bh=30
        rect=pygame.Rect(bx,y,bw,bh)
        btn_rects_bodies.append((rect,i))
        if LIST_TOP<=y<=LIST_BOTTOM-bh:
            sel=selected_type==(active_tab,i)
            pygame.draw.rect(screen,(36,36,82) if sel else (16,16,36),rect,border_radius=4)
            pygame.draw.rect(screen,(100,100,215) if sel else (32,32,58),rect,1,border_radius=4)
            pygame.draw.circle(screen,btype["color"],(bx+11,y+bh//2),5)
            if sel:
                gs=pygame.Surface((18,18),pygame.SRCALPHA)
                pygame.draw.circle(gs,(*btype["color"],45),(9,9),9)
                screen.blit(gs,(bx+2,y+bh//2-9))
            screen.blit(font.render(btype["name"],True,(210,210,210) if sel else (165,165,165)),(bx+22,y+3))
            screen.blit(font_small.render(btype["desc"],True,(80,80,110)),(bx+22,y+17))
        y+=bh+2

    # Clip da lista (mascara overflow)
    mask=pygame.Surface((PANEL_W,FIXED_BOTTOM),pygame.SRCALPHA)
    pygame.draw.rect(mask,(10,10,20,255),(0,0,PANEL_W,FIXED_BOTTOM))
    screen.blit(mask,(SIM_W,HEIGHT-FIXED_BOTTOM))

    # ── ZONA FIXA INFERIOR ──
    fy = HEIGHT - FIXED_BOTTOM  # y inicial da zona fixa

    # Separador + título Ajuste
    pygame.draw.line(screen,(35,35,70),(SIM_W+4,fy),(SIM_W+PANEL_W-4,fy),1)
    fy+=2
    screen.blit(font_title.render("✦ AJUSTE",True,(120,140,225)),(SIM_W+8,fy))
    fy+=ZONE_HEADER_H

    # Sliders
    draw_slider("Massa",slider_mass_mult,0.1,10.0,SIM_W+10,fy+14,PANEL_W-22,"mass")
    draw_slider("Raio", slider_rad_mult, 0.1,10.0,SIM_W+10,fy+48,PANEL_W-22,"rad")
    draw_slider("Veloc",slider_vel_mult, 0.1, 5.0,SIM_W+10,fy+82,PANEL_W-22,"vel")
    fy+=ZONE_SLIDER_H+ZONE_SEP

    # Separador + título Visão
    pygame.draw.line(screen,(35,35,70),(SIM_W+4,fy),(SIM_W+PANEL_W-4,fy),1)
    fy+=2
    screen.blit(font_title.render("✦ VISÃO",True,(120,140,225)),(SIM_W+8,fy))
    fy+=ZONE_HEADER_H

    # Toggles limpos: principais sempre visíveis; avançados só quando aberto.
    hw=(PANEL_W-12)//2
    toggle_rects={}
    primary_defs=[
        ("Vetores","show_vectors",show_vectors),
        ("Órbitas","show_orbits",show_orbits),
        ("Z.Habit.","show_hab_zone",show_hab_zone),
        ("Roche","show_roche",show_roche),
    ]
    advanced_defs=[
        ("Gráfico","show_graph",show_graph),
        ("Grav.","show_gravity_zone",show_gravity_zone),
        ("Baric.","show_barycenter",show_barycenter),
        ("Perf.","performance_mode",performance_mode),
    ]
    toggle_defs = primary_defs + (advanced_defs if show_advanced_options else [])

    for i,(lbl,key,state) in enumerate(toggle_defs):
        col=i%2; row=i//2
        tx=SIM_W+4+col*(hw+4)
        ty=fy+row*20
        rect=pygame.Rect(tx,ty,hw,18)
        toggle_rects[key]=rect
        bg=(16,48,26) if state else (14,14,28)
        bdr=(40,160,65) if state else (35,35,58)
        tc=(75,225,95) if state else (95,95,115)
        pygame.draw.rect(screen,bg,rect,border_radius=3)
        pygame.draw.rect(screen,bdr,rect,1,border_radius=3)
        pygame.draw.circle(screen,(60,200,80) if state else (45,45,65),(tx+9,ty+9),4)
        screen.blit(font_small.render(lbl,True,tc),(tx+18,ty+3))

    adv_y = fy + ((len(toggle_defs)+1)//2)*20 + 4
    advanced_rect = pygame.Rect(SIM_W+4, adv_y, PANEL_W-8, 18)
    adv_bg=(32,26,16) if show_advanced_options else (14,14,28)
    adv_bd=(170,130,55) if show_advanced_options else (35,35,58)
    pygame.draw.rect(screen,adv_bg,advanced_rect,border_radius=3)
    pygame.draw.rect(screen,adv_bd,advanced_rect,1,border_radius=3)
    adv_label = "Avançado ▲" if show_advanced_options else "Avançado ▼"
    screen.blit(font_small.render(adv_label,True,(220,180,90)),(advanced_rect.x+8,advanced_rect.y+3))
    fy+=ZONE_TOGGLE_H+ZONE_SEP

    save_rect = None
    load_rect = None

    # Velocidade do tempo
    pygame.draw.line(screen,(35,35,70),(SIM_W+4,fy),(SIM_W+PANEL_W-4,fy),1)
    fy+=2
    btn_rects_time.clear()

    # Pausa/play junto dos controles de tempo, usando símbolo universal.
    bw2=(PANEL_W-16)//5

    pause_rect = pygame.Rect(SIM_W+4, fy, bw2, ZONE_TIME_H-2)
    pbg = (18,52,30) if paused else (42,24,24)
    pbd = (60,180,90) if paused else (190,80,70)
    pygame.draw.rect(screen, pbg, pause_rect, border_radius=3)
    pygame.draw.rect(screen, pbd, pause_rect, 1, border_radius=3)

    cx_btn, cy_btn = pause_rect.center
    if paused:
        # ▶ play
        pts = [
            (cx_btn - 4, cy_btn - 6),
            (cx_btn - 4, cy_btn + 6),
            (cx_btn + 7, cy_btn),
        ]
        pygame.draw.polygon(screen, (220,235,225), pts)
    else:
        # ❚❚ pause
        pygame.draw.rect(screen, (220,235,225), (cx_btn - 7, cy_btn - 6, 4, 12), border_radius=1)
        pygame.draw.rect(screen, (220,235,225), (cx_btn + 3, cy_btn - 6, 4, 12), border_radius=1)

    for i,ts in enumerate(TIME_SCALES):
        rx=SIM_W+4+(i+1)*(bw2+2)
        rect=pygame.Rect(rx,fy,bw2,ZONE_TIME_H-2)
        btn_rects_time.append(rect)
        sel=abs(sim.time_scale-ts)<0.01 and not paused
        pygame.draw.rect(screen,(16,52,28) if sel else (14,14,26),rect,border_radius=3)
        pygame.draw.rect(screen,(42,165,65) if sel else (32,32,55),rect,1,border_radius=3)
        s=font_small.render(f"{ts}x",True,(85,230,105) if sel else (95,95,115))
        screen.blit(s,s.get_rect(center=rect.center))

    # Dica no rodapé
    if selected_type is not None:
        tab_i,body_i=selected_type
        bname=list(BODY_CATALOG.values())[tab_i][body_i]["name"]
        screen.blit(font_small.render(f"[ {bname} ] Arraste →",True,(70,240,105)),(SIM_W+6,LIST_BOTTOM+2))
    elif followed_body and followed_body in sim.bodies:
        screen.blit(font_small.render(f"◎ {followed_body.name}",True,(70,185,245)),(SIM_W+6,LIST_BOTTOM+2))

# ══════════════════════════════════════════
#  INFO HUD (lado esquerdo)
# ══════════════════════════════════════════
def dominant_gravity_source(body):
    best = None
    best_acc = 0.0
    for other in sim.bodies:
        if other is body:
            continue
        d2 = max((other.pos - body.pos).length_squared(), 25.0)
        acc = G * other.mass / d2
        if acc > best_acc:
            best_acc = acc
            best = other
    return best, best_acc


def draw_body_info():
    if not selected_body or selected_body not in sim.bodies: return
    b    = selected_body
    temp = body_temperature(b)
    life = life_probability(b)
    bts  = body_type_str(b)
    spd  = b.vel.length()
    lum  = get_luminosity(b)
    ws,wc= water_state(temp)
    r_in,r_out=hab_zone_radii(b)
    rl   = roche_limit(b)
    atm  = getattr(b,'atmosphere',0)
    wtr  = getattr(b,'water',0)
    dom_body, dom_acc = dominant_gravity_source(b)

    if temp<500:      tc=(100,120,220)
    elif temp<2000:   tc=(200,120,60)
    elif temp<6000:   tc=(255,220,100)
    elif temp<20000:  tc=(180,210,255)
    else:             tc=(220,180,255)

    lines=[
        (f"  {b.name}",                     (255,215,80),  True),
        (f"Tipo:   {bts}",                  (185,185,210), False),
        (f"Massa:  {b.mass:.2e}",           (185,185,195), False),
        (f"Vel:    {spd:.1f} u/s",          (185,185,195), False),
        (f"Temp:   ~{temp} K",              tc,            False),
        (f"Água:   {ws}",                   wc,            False),
        (f"Atm:    {atm:.2f} bar",          (140,180,220), False),
    ]
    if dom_body:
        lines.append((f"Grav.dom: {dom_body.name[:14]}", (150,170,240), False))
        lines.append((f"Acel.g: {dom_acc:.2e}", (120,140,210), False))
    if lum>0:
        lines.append((f"Lumin.: {lum:.2e} L☉",(255,225,95),False))
    if r_in:
        lines.append((f"Z.Hab:  {int(r_in)}-{int(r_out)} u",(70,240,105),False))
    if rl:
        lines.append((f"Roche:  {int(rl)} u",(240,85,85),False))
    if life>0:
        lines.append((f"🌱 Vida: {life}%",(70,240,105),False))
    else:
        lines.append(("Vida: improvável",(85,85,105),False))
    lines.append((f"Pos: ({int(b.pos.x)}, {int(b.pos.y)})",(110,110,130),False))

    h_box=len(lines)*15+36
    x0=10; y0_box=HEIGHT-h_box-30
    bg=pygame.Surface((235,h_box+8),pygame.SRCALPHA)
    pygame.draw.rect(bg,(5,8,22,230),(0,0,235,h_box+8),border_radius=10)
    pygame.draw.rect(bg,(60,80,160,180),(0,0,235,h_box+8),1,border_radius=8)
    screen.blit(bg,(x0-4,y0_box-4))

    y0=y0_box
    for i,(line,color,bold) in enumerate(lines):
        f=font_title if bold else font_small
        screen.blit(f.render(line,True,color),(x0,y0))
        y0+=15

    # Barra de vida
    if life>0:
        pygame.draw.rect(screen,(18,38,22),(x0,y0-2,90,5),border_radius=2)
        pygame.draw.rect(screen,(55,205,75),(x0,y0-2,int(life/100*90),5),border_radius=2)

    y0+=6
    is_f=followed_body==b
    fr=pygame.Rect(x0,y0,108,18)
    er=pygame.Rect(x0+112,y0,108,18)
    tr=pygame.Rect(x0,y0+22,108,18)
    pygame.draw.rect(screen,(16,46,65) if is_f else (14,14,28),fr,border_radius=4)
    pygame.draw.rect(screen,(50,145,205) if is_f else (36,36,60),fr,1,border_radius=4)
    screen.blit(font_small.render("◎ Seguindo" if is_f else "◎ Seguir",True,(70,190,245) if is_f else (95,95,115)),(x0+5,y0+3))
    pygame.draw.rect(screen,(36,26,16) if editing_name else (14,14,28),er,border_radius=4)
    pygame.draw.rect(screen,(165,125,50) if editing_name else (36,36,60),er,1,border_radius=4)
    screen.blit(font_small.render("✎ Renomear",True,(210,170,70) if editing_name else (95,95,115)),(x0+117,y0+3))
    # Botão Terraformar
    pygame.draw.rect(screen,(16,40,22),tr,border_radius=4)
    pygame.draw.rect(screen,(40,140,60),tr,1,border_radius=4)
    screen.blit(font_small.render("🌿 Terraformar",True,(70,200,90)),(x0+3,y0+25))

    # Clique área botões info
    return fr, er, tr

# ══════════════════════════════════════════
#  EVOLUÇÃO ESTELAR
# ══════════════════════════════════════════
def update_stellar_evolution(dt):
    from simulation import CollisionEvent
    for body in sim.bodies:
        bid=id(body)
        if bid not in body_ages: body_ages[bid]=0
        body_ages[bid]+=dt*sim.time_scale
        # inchaço estelar visual gradual
        for _en,_ed in STELLAR_EVOLUTION.items():
            if _en==body.name and _ed["age_limit"]<9999999:
                _ar=min(1.0,body_ages[bid]/_ed["age_limit"])
                if _ar>0.7 and get_luminosity(body)>0:
                    if not hasattr(body,"_base_radius"): body._base_radius=body.radius
                    body.radius=max(body._base_radius,int(body._base_radius*(1.0+(_ar-0.7)*0.5)))
        for evo_name,evo_data in STELLAR_EVOLUTION.items():
            if evo_name==body.name:
                if body_ages[bid]>=evo_data["age_limit"]:
                    body_ages[bid]=0
                    next_stage=evo_data["next"]
                    if next_stage=="supernova":
                        sim.collision_events.append(CollisionEvent(body.pos,"nova"))
                        body.mass*=0.1; body.radius=6
                        body.color=(80,0,120); body.name="Buraco Negro"
                    elif next_stage:
                        for tab in BODY_CATALOG.values():
                            for bt in tab:
                                if bt["name"]==next_stage:
                                    body.mass=bt["mass"]; body.radius=bt["radius"]
                                    body.color=bt["color"]; body.name=bt["name"]
                                    sim.collision_events.append(CollisionEvent(body.pos,"nova"))
                                    break

# ══════════════════════════════════════════
# FÍSICA ATMOSFÉRICA
# ══════════════════════════════════════════
_atm_timer = 0.0
def update_atmosphere_loss(dt):
    """Planetas quentes perdem atmosfera; frios/massivos retêm."""
    global _atm_timer
    _atm_timer += dt
    if _atm_timer < 1.0: return  # só atualiza a cada ~1s real
    _atm_timer = 0.0
    for body in sim.bodies:
        if get_luminosity(body) > 0: continue       # estrelas não
        if body.mass < 10: continue                  # corpos minúsculos ignorados
        temp = body_temperature(body)
        atm  = getattr(body, 'atmosphere', 0.0)
        if atm <= 0: continue
        # perda por temperatura alta
        if temp > 600:
            loss = (temp - 600) / 80000.0
            body.atmosphere = max(0.0, round(atm - loss, 4))
        # perda por massa baixa (sem gravidade suficiente)
        if body.mass < 80:
            loss = 0.001
            body.atmosphere = max(0.0, round(getattr(body,'atmosphere',0) - loss, 4))
        # recuperação lenta se temp ideal e massa ok
        if 200 < temp < 450 and body.mass >= 200:
            gain = 0.0001
            body.atmosphere = min(3.0, round(getattr(body,'atmosphere',0) + gain, 4))


_frame_count = 0
# ══════════════════════════════════════════
#  LOOP PRINCIPAL
# ══════════════════════════════════════════
graph_update_timer = 0.0
info_fr=info_er=info_tr=None

while running:
    dt=clock.tick(FPS)/1000.0
    twinkle_time+=dt
    sim.performance_mode = performance_mode

    if abs(zoom_target - zoom) > 0.0005:
        zoom += (zoom_target - zoom) * min(1.0, dt * 10.0)

    if followed_body and followed_body in sim.bodies:
        # world_to_screen: (pos + cam) * zoom + centro - (cx,cy)*zoom.
        # Para centralizar em qualquer zoom: cam = (cx, cy) - pos.
        camera_offset = pygame.Vector2(cx - followed_body.pos.x, cy - followed_body.pos.y)

    for event in pygame.event.get():
        if event.type==pygame.QUIT: running=False

        if editing_name:
            if event.type==pygame.KEYDOWN:
                if event.key==pygame.K_RETURN:
                    if selected_body and edit_text.strip(): selected_body.name=edit_text.strip()
                    editing_name=False
                elif event.key==pygame.K_ESCAPE: editing_name=False
                elif event.key==pygame.K_BACKSPACE: edit_text=edit_text[:-1]
                else:
                    if len(edit_text)<28: edit_text+=event.unicode
            continue

        if event.type==pygame.KEYDOWN:
            if event.key==pygame.K_SPACE:  paused=not paused
            if event.key==pygame.K_v:      show_vectors=not show_vectors
            if event.key==pygame.K_o:      show_orbits=not show_orbits
            if event.key==pygame.K_h:      show_hab_zone=not show_hab_zone
            if event.key==pygame.K_l:      show_roche=not show_roche
            if event.key==pygame.K_m:      show_minimap=not show_minimap
            if event.key==pygame.K_g:      show_graph=not show_graph
            if event.key==pygame.K_j:      show_gravity_zone=not show_gravity_zone
            if event.key==pygame.K_b:      show_barycenter=not show_barycenter
            if event.key==pygame.K_p:
                performance_mode = not performance_mode
                sim.performance_mode = performance_mode
                orbit_cache.clear()
            if event.key==pygame.K_x:
                if zoom>0.02:
                    zoom=zoom_target=0.008; camera_offset=pygame.Vector2(0,0)
                else:
                    zoom=zoom_target=1.0
            if event.key==pygame.K_F5:     save_simulation()
            if event.key==pygame.K_F9:     load_simulation()
            if event.key==pygame.K_r:
                camera_offset=pygame.Vector2(0,0); zoom=zoom_target=1.0; followed_body=None
            if event.key==pygame.K_u:
                if selected_body and selected_body in sim.bodies and selected_body.mass>=5e2:
                    _orb_r=selected_body.radius*3.5
                    _angle=random.uniform(0,math.pi*2)
                    _lx=selected_body.pos.x+math.cos(_angle)*_orb_r
                    _ly=selected_body.pos.y+math.sin(_angle)*_orb_r
                    _ov=math.sqrt(G*selected_body.mass/max(_orb_r,1))
                    _vx=-math.sin(_angle)*_ov+selected_body.vel.x
                    _vy= math.cos(_angle)*_ov+selected_body.vel.y
                    from body import Body as _B
                    _moon=_B(_lx,_ly,_vx,_vy,selected_body.mass*0.012,
                             max(2,int(selected_body.radius*0.27)),
                             (200,200,190),f"Lua de {selected_body.name}")
                    _moon.atmosphere=0.0; _moon.water=0.0
                    _moon.born_timer=0.0
                    sim.add_body(_moon)
            if event.key==pygame.K_ESCAPE:
                if terraforming_body:
                    terraforming_body=None
                elif editing_name:
                    editing_name=False
                elif placing:
                    placing=False; preview_trail=[]
                else:
                    selected_type=None
                    selected_body=None
                    followed_body=None
            pan_step = 40 / zoom
            if event.key==pygame.K_w: camera_offset.y += pan_step
            if event.key==pygame.K_s: camera_offset.y -= pan_step
            if event.key==pygame.K_a: camera_offset.x += pan_step
            if event.key==pygame.K_d: camera_offset.x -= pan_step
            # trocar modo gráfico
            if event.key==pygame.K_TAB and show_graph:
                gi=graph_modes.index(graph_mode)
                graph_mode=graph_modes[(gi+1)%len(graph_modes)]

            if event.key == pygame.K_DELETE:
                if selected_body and selected_body in sim.bodies:
                    body_ages.pop(id(selected_body), None)
                    flare_timers.pop(id(selected_body), None)
                    graph_history.pop(id(selected_body), None)
                    sim.bodies.remove(selected_body)
                    if followed_body == selected_body: followed_body = None
                    selected_body = None

            if event.key == pygame.K_d and pygame.key.get_mods() & pygame.KMOD_CTRL:
                if selected_body and selected_body in sim.bodies:
                    new_body = Body(selected_body.pos.x + 50, selected_body.pos.y + 50, selected_body.vel.x, selected_body.vel.y, selected_body.mass, selected_body.radius, selected_body.color, selected_body.name + " copy")
                    new_body.base_color = getattr(selected_body, 'base_color', selected_body.color)
                    new_body.atmosphere = getattr(selected_body, 'atmosphere', 0)
                    new_body.water = getattr(selected_body, 'water', 0)
                    new_body.has_rings = getattr(selected_body, 'has_rings', False)
                    new_body.material = getattr(selected_body, 'material', 'rock')
                    new_body.composition = dict(getattr(selected_body, 'composition', {}))
                    sim.add_body(new_body)

            if event.key == pygame.K_r and pygame.key.get_mods() & pygame.KMOD_CTRL:
                sim.bodies.clear()
                body_ages.clear()
                flare_timers.clear()
                graph_history.clear()
                selected_body = None
                followed_body = None
                planet_count = 0
                # Re-add initial solar system
                _add_stable(cx, cy, 0, 0, M_SOL, 30, (255,210,50), "Sol")
                _add_stable(cx+150, cy, 0, orbital_velocity(M_SOL,150), 1e3, 8,  (0,120,255),   "Terra")
                _add_stable(cx+225, cy, 0, orbital_velocity(M_SOL,225), 8e2, 6,  (200,80,50),   "Marte")
                _add_stable(cx+780, cy, 0, orbital_velocity(M_SOL,780), 3e5, 16, (180,140,80),  "Júpiter")
                planet_count = 4

        if event.type==pygame.MOUSEWHEEL:
            mx,my=pygame.mouse.get_pos()
            if mx<SIM_W:
                before = screen_to_world(mx, my, camera_offset, zoom, cx, cy)
                factor = 1.25 ** event.y
                zoom = max(0.005, min(zoom * factor, 60.0))
                zoom_target = zoom
                after = screen_to_world(mx, my, camera_offset, zoom, cx, cy)
                if followed_body and followed_body in sim.bodies:
                    camera_offset = pygame.Vector2(cx - followed_body.pos.x, cy - followed_body.pos.y)
                else:
                    camera_offset += (after - before)
            else:
                panel_scroll=max(0,panel_scroll-event.y*20)


        if event.type==pygame.KEYDOWN and selected_body and selected_body in sim.bodies and not editing_name:
            if event.key==pygame.K_c:
                circularize_orbit(selected_body)
                paused = True
                continue
            if event.key==pygame.K_z:
                zero_body_velocity(selected_body)
                paused = True
                continue
            if event.key==pygame.K_f:
                followed_body = selected_body
                continue

        if event.type==pygame.MOUSEBUTTONDOWN:
            mx,my=pygame.mouse.get_pos(); now=pygame.time.get_ticks()
            # Pygame antigo pode transformar scroll em botão 4/5.
            # Isso nunca deve selecionar astros nem toggles.
            if event.button not in (1, 3):
                continue

            # Terraformação
            _terra_click_consumed = False
            if terraforming_body and terra_btn_rects:
                for key,val in terra_btn_rects.items():
                    if key in ("save","close"):
                        if val.collidepoint(mx,my):
                            if key=="save":
                                terraforming_body._terra_set=True
                                save_simulation()
                            else:
                                terraforming_body=None
                            _terra_click_consumed=True
                            break
                    else:
                        rect,step,mn,mx_v=val
                        if rect.collidepoint(mx,my):
                            _key_map={"atm":"atmosphere","water":"water","co2":"co2","n2":"n2","albedo":"albedo"}
                            attr=_key_map.get(key.replace("_up","").replace("_dn",""),key.replace("_up","").replace("_dn",""))
                            _defaults={"atmosphere":0.0,"water":0.0,"co2":0.0,"n2":0.0,"albedo":0.3}
                            if not hasattr(terraforming_body,attr):
                                setattr(terraforming_body,attr,_defaults.get(attr,0.0))
                            cur=getattr(terraforming_body,attr,_defaults.get(attr,0.0))
                            if key.endswith("_up"):
                                setattr(terraforming_body,attr,round(min(cur+step,mx_v),3))
                            else:
                                setattr(terraforming_body,attr,round(max(cur-step,mn),3))
                            terraforming_body._terra_set=True
                            for _a,_d in _defaults.items():
                                if not hasattr(terraforming_body,_a):
                                    setattr(terraforming_body,_a,_d)
                            save_simulation()
                            _terra_click_consumed=True
                            break

            if _terra_click_consumed:
                continue
            # Sliders
            for key,srect in slider_rects.items():
                if srect.collidepoint(mx,my):
                    dragging_slider=key; slider_drag_start_x=mx
                    slider_drag_start_val={"mass":slider_mass_mult,"rad":slider_rad_mult,"vel":slider_vel_mult}[key]

            if mx>=SIM_W and dragging_slider is None:
                ui_consumed = False

                if selected_body and selected_body in sim.bodies:
                    for key, rect in orbital_btn_rects.items():
                        if rect.collidepoint(mx, my):
                            if key == "circularize":
                                circularize_orbit(selected_body)
                                paused = True
                            elif key == "zero_velocity":
                                zero_body_velocity(selected_body)
                                paused = True
                            elif key == "follow":
                                followed_body = selected_body
                            ui_consumed = True
                            break

                if pause_rect and pause_rect.collidepoint(mx,my):
                    paused = not paused
                    ui_consumed = True

                # Botões de velocidade precisam ter prioridade sobre lista/tabs do painel.
                if not ui_consumed:
                    for i,rect in enumerate(btn_rects_time):
                        if rect.collidepoint(mx,my):
                            sim.time_scale = TIME_SCALES[i]
                            paused = False
                            ui_consumed = True
                            break

                if not ui_consumed and advanced_rect and advanced_rect.collidepoint(mx,my):
                    show_advanced_options = not show_advanced_options
                    ui_consumed = True

                if not ui_consumed:
                    for var,trect in toggle_rects.items():
                        if trect.collidepoint(mx,my):
                            ui_consumed = True
                            if   var=="show_vectors":    show_vectors=not show_vectors
                            elif var=="show_orbits":     show_orbits=not show_orbits
                            elif var=="show_hab_zone":   show_hab_zone=not show_hab_zone
                            elif var=="show_roche":      show_roche=not show_roche
                            elif var=="show_minimap":    show_minimap=not show_minimap
                            elif var=="show_graph":      show_graph=not show_graph
                            elif var=="show_gravity_zone": show_gravity_zone=not show_gravity_zone
                            elif var=="show_barycenter":   show_barycenter=not show_barycenter
                            elif var=="performance_mode":
                                performance_mode=not performance_mode
                                sim.performance_mode=performance_mode
                                orbit_cache.clear()
                            break

                if not ui_consumed:
                    for i,rect in enumerate(tab_rects):
                        if rect.collidepoint(mx,my):
                            active_tab=i; selected_type=None; panel_scroll=0; ui_consumed=True; break

                if not ui_consumed:
                    for rect,i in btn_rects_bodies:
                        if rect.collidepoint(mx,my):
                            key=(active_tab,i)
                            selected_type=key if selected_type!=key else None
                            selected_body=None; preview_trail=[]
                            ui_consumed=True
                            break

                if not ui_consumed:
                    for i,rect in enumerate(btn_rects_time):
                        if rect.collidepoint(mx,my):
                            sim.time_scale=TIME_SCALES[i]
                            paused=False
                            ui_consumed=True
                            break

                if ui_consumed:
                    continue

            elif mx<SIM_W:
                # Cliques nos botões do info HUD
                if info_fr and info_fr.collidepoint(mx,my):
                    followed_body=None if followed_body==selected_body else selected_body
                elif info_er and info_er.collidepoint(mx,my):
                    editing_name=True; edit_text=selected_body.name if selected_body else ""
                elif info_tr and info_tr.collidepoint(mx,my):
                    terraforming_body=selected_body

                # Gráfico — trocar modo clicando nas abas
                elif show_graph and selected_body and selected_body in sim.bodies:
                    GRAPH_W2=GRAPH_W+20; tw2=GRAPH_W2//3
                    gy_graph=HEIGHT-240
                    for i,gm in enumerate(graph_modes):
                        gr=pygame.Rect(10-4+i*tw2,gy_graph-4,tw2,14)
                        if gr.collidepoint(mx,my):
                            globals()["graph_mode"]=gm; break

                elif event.button==1:
                    if selected_type is not None and sim.can_add_body():
                        placing=True
                        place_start_screen=pygame.Vector2(mx,my)
                        place_pos_world=screen_to_world(mx,my,camera_offset,zoom,cx,cy)
                        preview_trail=[]
                    else:
                        hit=get_body_at(mx,my)
                        if hit and hit==last_click_body and (now-last_click_time)<400:
                            followed_body=hit
                        else:
                            selected_body=hit; editing_name=False
                            if hit:
                                hit.atmosphere=estimate_atmosphere(hit)
                            elif followed_body is not None and mx < SIM_W:
                                followed_body = None

                        # PATCH 43:
                        # Pausado = editor orbital seguro.
                        # Arrastar muda a POSIÇÃO, mas preserva a velocidade orbital.
                        # Antes zerava vel/acc e o corpo caía direto no Sol. Buraco negro de UX.
                        if paused and hit:
                            dragging_body = hit
                            followed_body = None
                            world_mouse = screen_to_world(mx,my,camera_offset,zoom,cx,cy)
                            dragging_body_offset = hit.pos - world_mouse
                            hit.collision_cooldown = 0.5

                        last_click_body=hit; last_click_time=now
                elif event.button==3:
                    hit=get_body_at(mx,my)
                    if hit:
                        if followed_body==hit: followed_body=None
                        body_ages.pop(id(hit),None)
                        flare_timers.pop(id(hit),None)
                        graph_history.pop(id(hit),None)
                        sim.bodies.remove(hit)
                        if selected_body==hit: selected_body=None
                        if terraforming_body==hit: terraforming_body=None
                    else:
                        dragging=True; drag_start=pygame.Vector2(mx,my)

        if event.type==pygame.MOUSEBUTTONUP:
            if event.button==1:
                if dragging_slider: dragging_slider=None
                if dragging_body:
                    preserve_orbit_after_drag(dragging_body)
                    dragging_body = None
                if placing:
                    placing=False; mx,my=pygame.mouse.get_pos()
                    if selected_type is not None and place_pos_world is not None:
                        tab_i,body_i=selected_type
                        btype=list(BODY_CATALOG.values())[tab_i][body_i]
                        drag_vec=pygame.Vector2(mx,my)-place_start_screen
                        launch_vel=-drag_vec*(3.0/zoom)*slider_vel_mult
                        planet_count+=1
                        nb=Body(
                            place_pos_world.x,place_pos_world.y,
                            launch_vel.x,launch_vel.y,
                            btype["mass"]*slider_mass_mult,
                            max(1,int(btype["radius"]*slider_rad_mult)),
                            btype["color"],f"{btype['name']} {planet_count}"
                        )
                        nb.base_color   = btype["color"]
                        nb.has_rings    = bool(btype.get("has_rings", False))
                        _apply_catalog_physics(nb, btype)
                        if not hasattr(nb,'_terra_set'):
                            nb.atmosphere = estimate_atmosphere(nb)
                            nb.water      = 1.0 if nb.mass>=500 else 0.0
                        sim.add_body(nb)

                    preview_trail=[]
            if event.button==3: dragging=False; cam_velocity.update(0,0)

        if event.type==pygame.MOUSEMOTION:
            mx,my=pygame.mouse.get_pos()

            if paused and dragging_body and dragging_body in sim.bodies:
                world_mouse = screen_to_world(mx,my,camera_offset,zoom,cx,cy)
                dragging_body.pos = world_mouse + dragging_body_offset

                # Preserva velocidade orbital. Só limpa aceleração momentânea
                # para evitar impulso acumulado do frame anterior.
                dragging_body.acc.update(0.0, 0.0)
                dragging_body.trail.clear()
                dragging_body.collision_cooldown = 0.5
                followed_body = None

            if dragging_slider:
                limits={"mass":(0.1,10.0),"rad":(0.1,10.0),"vel":(0.1,5.0)}
                mn,mxv=limits[dragging_slider]
                dv=(mx-slider_drag_start_x)/(PANEL_W-22)*(mxv-mn)
                nv=max(mn,min(slider_drag_start_val+dv,mxv))
                if dragging_slider=="mass":  slider_mass_mult=nv
                elif dragging_slider=="rad": slider_rad_mult=nv
                elif dragging_slider=="vel": slider_vel_mult=nv
            if dragging and not dragging_slider and not dragging_body:
                mp=pygame.Vector2(mx,my)
                delta=(mp-drag_start)/zoom
                camera_offset+=delta
                cam_velocity=delta*FPS
                drag_start=mp; followed_body=None
            if placing and place_pos_world is not None and selected_type is not None:
                drag_vec=pygame.Vector2(mx,my)-place_start_screen
                launch_vel=-drag_vec*(3.0/zoom)*slider_vel_mult
                tab_i,body_i=selected_type
                btype=list(BODY_CATALOG.values())[tab_i][body_i]
                if performance_mode and len(sim.bodies) > 90:
                    preview_trail=[]
                else:
                    preview_trail=sim.simulate_preview({
                    "pos":place_pos_world,"vel":launch_vel,
                    "mass":btype["mass"]*slider_mass_mult,
                    "radius":max(1,int(btype["radius"]*slider_rad_mult)),
                    "color":btype["color"],
                })

    # ── ATUALIZAÇÃO ──
    if dragging_body and not paused:
        dragging_body = None

    if not paused:
        sim.step(dt)  # colisões já são verificadas internamente com sub-steps
        sim.check_roche()
        update_stellar_evolution(dt)
        update_atmosphere_loss(dt)
        update_flares(dt)
        for fl in flares[:]:
            fl["pos"] += fl["vel"] * dt
            fl["timer"] -= dt
            if fl["timer"] <= 0: flares.remove(fl)
        for body in sim.bodies:
            update_body_water_color(body)
        graph_update_timer += dt
        if graph_update_timer >= 0.5:
            graph_update_timer = 0.0
            update_graph(dt)

    # ── RENDERIZAÇÃO ──
    screen.fill((4,4,12))
    draw_stars()
    if show_hab_zone:  draw_hab_zone()
    if show_roche:     draw_roche_limit()
    if show_gravity_zone: draw_gravity_zones()
    if show_barycenter:   draw_barycenter()
    if show_orbits:
        for body in sim.bodies: draw_orbit_prediction(body)

    # Trilhas
    for body in sim.bodies:
        # rastro: linha contínua com fade suave
        _tpts=[]
        for _tp in body.trail:
            _tsx=int((_tp[0]+camera_offset.x)*zoom+SIM_W/2-cx*zoom)
            _tsy=int((_tp[1]+camera_offset.y)*zoom+HEIGHT/2-cy*zoom)
            _tpts.append((_tsx,_tsy))
        _ttotal=len(_tpts)
        if _ttotal>1:
            _step=max(1,_ttotal//(36 if performance_mode else 80))
            _br,_bg2,_bb=body.color[0],body.color[1],body.color[2]
            for _ti in range(0,_ttotal-_step,_step):
                _a=max(0,min(255,int(200*_ti/max(_ttotal,1))))
                _tc=(_br*_a//255,_bg2*_a//255,_bb*_a//255)
                pygame.draw.line(screen,_tc,_tpts[_ti],_tpts[min(_ti+_step,_ttotal-1)],1)

    # Preview de trajetória
    if preview_trail and len(preview_trail)>1 and selected_type is not None:
        tab_i,body_i=selected_type
        color_p=list(BODY_CATALOG.values())[tab_i][body_i]["color"]
        points=[]
        for point in preview_trail:
            sx=int((point.x+camera_offset.x)*zoom+SIM_W/2-cx*zoom)
            sy=int((point.y+camera_offset.y)*zoom+HEIGHT/2-cy*zoom)
            if 0<=sx<=SIM_W and 0<=sy<=HEIGHT: points.append((sx,sy))
        if len(points)>1:
            for k in range(len(points)-1):
                alpha=int(220*(1-k/len(points)))
                pygame.draw.line(screen,tuple(min(v,alpha) for v in color_p),points[k],points[k+1],1)

    # Corpos
    for body in sim.bodies:
        sx,sy=world_to_screen(body.pos,camera_offset,zoom,cx,cy)
        r=max(2,int(body.radius*zoom))
        if -r*6<=sx<=SIM_W+r*6 and -r*6<=sy<=HEIGHT+r*6:
            draw_body_effects(body,sx,sy,r)
            if show_vectors:
                draw_velocity_vector(body,sx,sy,r)
                draw_acceleration_vector(body,sx,sy,r)
            if body==selected_body:
                pygame.draw.circle(screen,(255,255,70),(sx,sy),r+5,1)
            if body==followed_body:
                pygame.draw.circle(screen,(50,170,255),(sx,sy),r+8,1)
            # glow estrelar — discreto e proporcional
            _lum=get_luminosity(body)
            if _lum>0 and r>=3:
                _ga=min(55,max(12,int(math.log10(_lum+1)*14)))
                for _gr,_ga2 in [(r*3,_ga//3),(r*2,_ga//2),(r+2,_ga)]:
                    _gs=pygame.Surface((_gr*2+2,_gr*2+2),pygame.SRCALPHA)
                    pygame.draw.circle(_gs,(*body.color,_ga2),(_gr+1,_gr+1),_gr)
                    screen.blit(_gs,(sx-_gr-1,sy-_gr-1))
            # corpo principal
            draw_planet_texture(body,sx,sy,r)
            # sombra 3D (semicírculo escuro no lado oposto à estrela mais próxima)
            if r>=4 and _lum==0:
                _dark=pygame.Surface((r*2,r*2),pygame.SRCALPHA)
                pygame.draw.circle(_dark,(0,0,0,90),(r,r),r)
                _off=max(2,r//3)
                pygame.draw.circle(_dark,(0,0,0,0),(r-_off,r-_off),r-1)
                screen.blit(_dark,(sx-r,sy-r))
            # textura procedural
            if r>=5:
                _btype="star" if body.mass>=8e5 else "planet" if body.mass>=5e2 else "small"
                if _btype=="planet":
                    for _band in range(1,3):
                        _by=sy-r+int(r*_band*0.6)
                        _bw=int(math.sqrt(max(0,r**2-(_by-sy)**2))*2)
                        if _bw>2:
                            _bs=pygame.Surface((_bw,2),pygame.SRCALPHA)
                            _bc=tuple(min(255,int(c*0.65)) for c in body.color)
                            pygame.draw.rect(_bs,(*_bc,45),(0,0,_bw,2))
                            screen.blit(_bs,(sx-_bw//2,_by))
                    _ps=pygame.Surface((r,r//2+1),pygame.SRCALPHA)
                    pygame.draw.ellipse(_ps,(255,255,255,20),(0,0,r,r//2))
                    screen.blit(_ps,(sx-r//2,sy-r))
                elif _btype=="star" and r>=8:
                    _seed=int(body.mass)%999
                    random.seed(_seed)
                    for _ in range(2):
                        _mx=sx+random.randint(-r//2,r//2)
                        _my=sy+random.randint(-r//3,r//3)
                        _mr=max(1,random.randint(1,max(1,r//4)))
                        _ms=pygame.Surface((_mr*2,_mr*2),pygame.SRCALPHA)
                        pygame.draw.ellipse(_ms,(0,0,0,55),(0,0,_mr*2,_mr*2))
                        screen.blit(_ms,(_mx-_mr,_my-_mr))
                    random.seed(int(pygame.time.get_ticks()//200))
            if should_draw_body_label(body, selected_body, followed_body, zoom):
                label = compact_body_label(body)
                color = (190,190,190)
                if getattr(body, "is_fragment", False):
                    alpha_factor = min(1.0, max(0.0, getattr(body, "label_timer", 0.0) / 1.1))
                    color = tuple(int(c * alpha_factor) for c in color)
                screen.blit(font_small.render(label, True, color), (sx+r+3, sy-7))

    # Seta de lançamento
    if placing and place_start_screen is not None:
        mx,my=pygame.mouse.get_pos()
        if mx<SIM_W:
            tab_i,body_i=selected_type
            btype=list(BODY_CATALOG.values())[tab_i][body_i]
            psx=int((place_pos_world.x+camera_offset.x)*zoom+SIM_W/2-cx*zoom)
            psy=int((place_pos_world.y+camera_offset.y)*zoom+HEIGHT/2-cy*zoom)
            pygame.draw.circle(screen,btype["color"],(psx,psy),max(2,int(btype["radius"]*slider_rad_mult*zoom)),1)
            pygame.draw.line(screen,(255,255,70),(psx,psy),(mx,my),1)
            dx,dy=psx-mx,psy-my; ang=math.atan2(dy,dx)
            for da in [0.4,-0.4]:
                pygame.draw.line(screen,(255,255,70),(psx,psy),(int(psx-18*math.cos(ang+da)),int(psy-18*math.sin(ang+da))),1)

    draw_flares()
    update_collision_particles(dt)
    draw_collision_particles()
    draw_collision_events()

    # HUD esquerdo
    result = draw_body_info()
    if result: info_fr, info_er, info_tr = result

    if show_graph: draw_graph()
    if terraforming_body and terraforming_body in sim.bodies:
        draw_terraforming_panel(terraforming_body)

    # HUD topo esquerdo — estado sempre visível
    hud_label = "⏸ PAUSADO" if paused else "▶ RODANDO"
    hud_color = (145,190,255) if paused else (120,210,145)
    hud_bg=pygame.Surface((126,22),pygame.SRCALPHA)
    pygame.draw.rect(hud_bg,(6,6,18,185),(0,0,126,22),border_radius=5)
    screen.blit(hud_bg,(6,6))
    screen.blit(font.render(hud_label,True,hud_color),(12,10))

    # Barra de teclas
    screen.blit(font_small.render(
        "ESPAÇO pausa | V vetores | O órbitas | H hab. | L Roche | J grav. | B baric. | G gráfico | U lua | X galáxia | F5 salvar | F9 carregar | R resetar câmera | DEL deletar | CTRL+D duplicar | CTRL+R reset sim",
        True,(55,55,80)),(10,HEIGHT-12))

    draw_panel()
    pygame.display.flip()

pygame.quit()
                    
