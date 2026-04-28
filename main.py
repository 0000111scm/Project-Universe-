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
from systems.orbits import predict_nbody_paths, make_cache_signature
from physics.environment import stellar_luminosity, equilibrium_temperature, update_environment, radiative_flux
from visuals.body_render import draw_selection_rings, draw_temperature_badge
from physics.habitability import habitability_report
from physics.units import fmt_temp_c, fmt_mass, fmt_speed, fmt_distance_au, fmt_acceleration, kelvin_to_celsius, fmt_num_br
from physics.presets import apply_preset
from visuals.panel import draw_factor_bar

pygame.init()
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Project Universe")
clock  = pygame.time.Clock()

sim = Simulation()
sim.time_scale = 0.5

def orbital_velocity(mc, d):
    return math.sqrt(G * mc / d)

cx, cy = SIM_W//2, HEIGHT//2

def _add_stable(x, y, vx, vy, mass, radius, color, name):
    b = Body(x, y, vx, vy, mass, radius, color, name)
    sim.add_body(b)

# Apenas os corpos principais em volta do Sol
_add_stable(cx, cy, 0, 0, M_SOL, 30, (255,210,50), "Sol")
_add_stable(cx+150, cy, 0, orbital_velocity(M_SOL,150), 1e3, 8,  (0,120,255),   "Terra")
_add_stable(cx+225, cy, 0, orbital_velocity(M_SOL,225), 8e2, 6,  (200,80,50),   "Marte")
_add_stable(cx+780, cy, 0, orbital_velocity(M_SOL,780), 5e2, 10, (180,140,80),  "Júpiter")


BODY_CATALOG["Presets"] = [
    {"name":"Sistema Solar", "desc":"preset limpo", "color":(255,210,80), "preset":"sistema_solar", "mass":0, "radius":1, "has_rings":False, "luminosity":0},
    {"name":"Sistema Binário", "desc":"duas estrelas", "color":(255,160,80), "preset":"binaria", "mass":0, "radius":1, "has_rings":False, "luminosity":0},
    {"name":"Colisão Lua-Terra", "desc":"Theia", "color":(130,190,255), "preset":"colisao_lua_terra", "mass":0, "radius":1, "has_rings":False, "luminosity":0},
    {"name":"Campo Asteroides", "desc":"80 corpos", "color":(160,145,110), "preset":"asteroides", "mass":0, "radius":1, "has_rings":False, "luminosity":0},
]

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
graph_mode     = "temp"  # "temp" | "vel" | "mass"

flares      = []
flare_timers= {}
collision_particles = []
orbit_cache = {}
orbit_cache_sig = None


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
moving_body        = None
move_rect          = None

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


def get_catalog_entry(selected):
    """Retorna item do catalogo com protecao contra indice invalido."""
    if selected is None:
        return None
    try:
        tab_i, body_i = selected
        tabs = list(BODY_CATALOG.values())
        if tab_i < 0 or tab_i >= len(tabs):
            return None
        bodies = tabs[tab_i]
        if body_i < 0 or body_i >= len(bodies):
            return None
        return bodies[body_i]
    except Exception:
        return None


def validate_selected_type():
    global selected_type
    if selected_type is not None and get_catalog_entry(selected_type) is None:
        selected_type = None
    return selected_type is not None




# ══════════════════════════════════════════
#  FÍSICA CORRIGIDA
# ══════════════════════════════════════════
def get_luminosity(body):
    """Luminosidade física aproximada; BN/galáxias não aquecem como estrela comum."""
    return stellar_luminosity(body)

def body_temperature(body):
    """Temperatura atual dinâmica. O alvo radiativo vem de physics/environment.py."""
    if hasattr(body, "temperature"):
        return max(3, min(int(body.temperature), 250000))
    return int(equilibrium_temperature(body, sim.bodies, HAB_SCALE))

def body_type_str(body):
    if body.mass >= 1e11:  return "Galáxia"
    if body.mass >= 1e9:   return "BN Supermassivo"
    if body.mass >= 5e6:   return "Buraco Negro"
    if body.mass >= 4e6:   return "Estrela de Nêutrons"
    if body.mass >= 2e7:   return "Hipergigante"
    if body.mass >= 3e6:   return "Gigante/Supergigante"
    if body.mass >= 2e5:   return "Estrela"
    if body.mass >= 5e4:   return "Gigante Gasoso"
    if body.mass >= 5e2:   return "Planeta"
    if body.mass >= 1e2:   return "Planeta Anão"
    if body.mass >= 1e1:   return "Lua"
    return "Corpo Menor"

def life_probability(body):
    """Pontuação de habitabilidade 0-100 baseada em fatores físicos explicáveis."""
    return habitability_report(body, sim.bodies, HAB_SCALE)["score"]

def water_state(temp_k):
    if temp_k < 273.15:  return "Gelo",    (160,210,255)
    if temp_k <= 373.15: return "Líquida", (50,150,255)
    return "Vapor",              (200,210,255)

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

def draw_terraforming_panel(body):
    global terra_btn_rects
    terra_btn_rects = {}
    w   = 248
    atm = getattr(body,'atmosphere',0)
    wtr = getattr(body,'water',0)
    co2 = getattr(body,'co2',0)
    n2  = getattr(body,'n2',0)
    o2  = getattr(body,'o2',0)
    ch4 = getattr(body,'ch4',0)
    alb = getattr(body,'albedo',0.3)
    temp = body_temperature(body)
    life = life_probability(body)
    params = [
        ("Atmosfera", f"{atm:.2f} bar", "atm",    (100,200,255),(60,80,120),   0.0, 3.0,  0.1),
        ("\xc1gua",   f"{wtr:.2f}",     "water",  (50,130,255), (30,60,160),   0.0, 1.0,  0.1),
        ("CO2",       f"{co2:.2f} bar", "co2",    (200,160,80), (120,80,30),   0.0, 2.0,  0.1),
        ("N2",        f"{n2:.2f} bar",  "n2",     (120,200,120),(60,120,60),   0.0, 3.0,  0.1),
        ("O2",        f"{o2:.2f} bar",  "o2",     (120,220,255),(50,110,150),  0.0, 1.5,  0.05),
        ("CH4",       f"{ch4:.2f} bar", "ch4",    (180,140,220),(90,60,130),   0.0, 1.0,  0.05),
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
    screen.blit(font_small.render(f"Temp: {fmt_temp_c(temp)}   Vida: {life}%",True,lc),(x0,y0))
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
graph_labels = {"temp":"Temperatura (°C)","vel":"Velocidade (km/s)","mass":"Massa","life":"Habitabilidade (%)"}
graph_colors = {"temp":(255,180,80),"vel":(80,200,255),"mass":(180,100,255),"life":(80,255,120)}

def update_graph(dt):
    for body in sim.bodies:
        bid = id(body)
        if bid not in graph_history:
            graph_history[bid] = {"temp":[],"vel":[],"mass":[],"life":[]}
        h = graph_history[bid]
        for _k in ("temp","vel","mass","life"):
            if _k not in h: h[_k] = []
        h["temp"].append(kelvin_to_celsius(body_temperature(body)))
        h["vel"].append(float(fmt_speed(body.vel.length(), HAB_SCALE).split()[0].replace(".", "").replace(",", ".")))
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
            "show_label":getattr(b,'show_label',True),
            "born_timer":getattr(b,'born_timer',999.0),
            "temperature":getattr(b,'temperature',300.0),
            "co2":getattr(b,'co2',0.0),
            "n2":getattr(b,'n2',0.0),
            "o2":getattr(b,'o2',0.0),
            "ch4":getattr(b,'ch4',0.0),
            "surface_pressure":getattr(b,'surface_pressure',getattr(b,'atmosphere',0.0)),
            "albedo":getattr(b,'albedo',0.3)
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
        b.born_timer = bd.get("born_timer", 999.0)
        b.temperature = bd.get("temperature", 300.0)
        b.co2         = bd.get("co2",0)
        b.n2          = bd.get("n2",0)
        b.o2          = bd.get("o2",0)
        b.ch4         = bd.get("ch4",0)
        b.surface_pressure = bd.get("surface_pressure", b.atmosphere)
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

def _get_orbit_paths():
    """Cache global de predicao orbital N-body real."""
    global orbit_cache, orbit_cache_sig
    quality = 0 if performance_mode else 1
    sig = make_cache_signature(sim.bodies, quality_bucket=quality)
    if sig != orbit_cache_sig:
        steps = 90 if performance_mode else 180
        stride = 4 if performance_mode else 3
        max_bodies = 45 if performance_mode else 80
        orbit_cache = predict_nbody_paths(sim.bodies, steps=steps, dt=0.018, stride=stride, max_bodies=max_bodies)
        orbit_cache_sig = sig
    return orbit_cache


def draw_orbit_prediction(body):
    """Predicao visual N-body: integra todos os corpos importantes, nao so 1 atrator."""
    if not sim.bodies:
        return
    if performance_mode and getattr(body, "is_fragment", False):
        return
    if len(sim.bodies) > 140 and body.mass < 50:
        return

    world_pts = _get_orbit_paths().get(id(body))
    if not world_pts or len(world_pts) < 2:
        return

    pts=[]
    for point in world_pts:
        sx2,sy2=world_to_screen(point,camera_offset,zoom,cx,cy)
        if -3000<=sx2<=SIM_W+3000 and -3000<=sy2<=HEIGHT+3000:
            pts.append((sx2,sy2))
    if len(pts)>2:
        s=pygame.Surface((SIM_W,HEIGHT),pygame.SRCALPHA)
        alpha = 28 if performance_mode else 48
        pygame.draw.lines(s,(*body.color[:3],alpha),False,pts,1)
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
    ckey = (id(body), r, body.color)
    if ckey not in _texture_cache:
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

        mask=pygame.Surface((r*2+2,r*2+2),pygame.SRCALPHA)
        pygame.draw.circle(mask,(255,255,255,255),(r+1,r+1),r)
        s.blit(mask,(0,0),special_flags=pygame.BLEND_RGBA_MULT)
        _texture_cache[ckey]=s
    screen.blit(_texture_cache[ckey],(sx-r-1,sy-r-1))

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

    for tab in BODY_CATALOG.values():
        for bt in tab:
            if bt["name"]==body.name and bt.get("has_rings"):
                draw_rings(body,sx,sy,r); break

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
    # limpar spawned de eventos que já foram removidos
    active_ids={id(ev) for ev in sim.collision_events}
    for eid in list(_spawned_events):
        if eid not in active_ids: _spawned_events.discard(eid)
    for ev in sim.collision_events:
        eid=id(ev)
        if eid not in _spawned_events:
            # Reduz partículas quando há muitos corpos para evitar queda forte de FPS.
            if len(sim.bodies) > 180:
                _pc = 12
            elif ev.kind in ("nova", "blackhole"):
                _pc = 36
            else:
                _pc = 22
            spawn_collision_particles(ev.pos, ev.kind, _pc)
            _spawned_events.add(eid)
        sx,sy=world_to_screen(ev.pos,camera_offset,zoom,cx,cy)
        color=COLLISION_COLORS.get(ev.kind,(255,255,255))
        progress=1.0-(ev.timer/0.4); radius=int(40*progress); fade=int(255*(1.0-progress))
        if radius>0:
            if ev.kind=="nova":
                # onda de choque externa
                pygame.draw.circle(screen,(255,200,80),(sx,sy),radius,2)
                pygame.draw.circle(screen,(255,120,40),(sx,sy),max(1,int(radius*0.65)),1)
                # núcleo brilhante
                if radius>6:
                    ns=pygame.Surface((radius,radius),pygame.SRCALPHA)
                    _na=max(0,min(255,int(80*(1-progress))))
                    pygame.draw.circle(ns,(255,255,200,_na),(radius//2,radius//2),max(1,radius//2))
                    screen.blit(ns,(sx-radius//2,sy-radius//2))
                # nebulosa residual (anel externo esmaecendo)
                if progress>0.5:
                    nr=int(radius*1.6)
                    nt=pygame.Surface((nr*2+4,nr*2+4),pygame.SRCALPHA)
                    _na1=max(0,min(255,int(30*(1-progress))))
                    _na2=max(0,min(255,int(60*(1-progress))))
                    pygame.draw.circle(nt,(180,80,200,_na1),(nr+2,nr+2),nr)
                    pygame.draw.circle(nt,(200,100,255,_na2),(nr+2,nr+2),nr,2)
                    screen.blit(nt,(sx-nr-2,sy-nr-2))
            elif ev.kind=="blackhole":
                pygame.draw.circle(screen,(100,0,160),(sx,sy),radius,2)
                pygame.draw.circle(screen,(180,60,255),(sx,sy),max(1,radius//3),1)
                if radius>4:
                    bs=pygame.Surface((radius*2,radius*2),pygame.SRCALPHA)
                    _ba=max(0,min(255,int(60*(1-progress))))
                    pygame.draw.circle(bs,(60,0,120,_ba),(radius,radius),radius)
                    screen.blit(bs,(sx-radius,sy-radius))
            else:
                pygame.draw.circle(screen,color,(sx,sy),radius,1)
        lm={"merge":"FUSÃO","nova":"SUPERNOVA!","blackhole":"BURACO NEGRO!","absorb":"ABSORVIDO"}
        surf=font_small.render(lm.get(ev.kind,""),True,color)
        surf.set_alpha(fade)
        screen.blit(surf,(sx-surf.get_width()//2,sy-radius-14))

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
                2 + ZONE_SAVLOAD_H + ZONE_SEP +
                2 + ZONE_TIME_H)

LIST_TOP    = ZONE_TITLE_H + ZONE_TABS_H   # 44px
LIST_BOTTOM = HEIGHT - FIXED_BOTTOM - 18   # margem para dica sem sobrepor AJUSTE

def draw_slider(label,val,mn,mx_v,x,y,w,key):
    slider_rects[key]=pygame.Rect(x,y,w,10)
    pygame.draw.rect(screen,(22,22,42),(x,y,w,10),border_radius=5)
    t=(val-mn)/(mx_v-mn); kx=int(x+t*w)
    pygame.draw.rect(screen,(50,85,165),(x,y,int(t*w),10),border_radius=5)
    pygame.draw.circle(screen,(140,170,245),(kx,y+5),7)
    screen.blit(font_small.render(f"{label}: {val:.1f}x",True,(140,155,185)),(x,y-13))

def draw_panel():
    global btn_rects_bodies,btn_rects_time,tab_rects,save_rect,load_rect,toggle_rects

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

    # Toggles em grade 2x2 fixos
    hw=(PANEL_W-12)//2
    toggle_rects={}
    toggle_defs=[
        ("Vetores","show_vectors",show_vectors),
        ("Órbitas","show_orbits",show_orbits),
        ("Z.Habit.","show_hab_zone",show_hab_zone),
        ("Roche","show_roche",show_roche),
        ("Gráfico","show_graph",show_graph),
        ("Grav.","show_gravity_zone",show_gravity_zone),
        ("Baric.","show_barycenter",show_barycenter),
        ("Perf.","performance_mode",performance_mode),
    ]
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
    fy+=ZONE_TOGGLE_H+ZONE_SEP

    # Separador + Salvar/Carregar
    pygame.draw.line(screen,(35,35,70),(SIM_W+4,fy),(SIM_W+PANEL_W-4,fy),1)
    fy+=2
    sw=(PANEL_W-12)//2
    save_rect=pygame.Rect(SIM_W+4,   fy,sw,ZONE_SAVLOAD_H-2)
    load_rect=pygame.Rect(SIM_W+6+sw,fy,sw,ZONE_SAVLOAD_H-2)
    for rect,lbl,bg,bdr,tc in [
        (save_rect,"💾 Salvar",(20,55,35),(45,160,75),(160,235,180)),
        (load_rect,"📂 Carregar",(20,35,65),(45,90,180),(160,190,235)),
    ]:
        pygame.draw.rect(screen,bg,rect,border_radius=4)
        pygame.draw.rect(screen,bdr,rect,1,border_radius=4)
        s=font_small.render(lbl,True,tc)
        screen.blit(s,s.get_rect(center=rect.center))
    fy+=ZONE_SAVLOAD_H+ZONE_SEP

    # Velocidade do tempo
    pygame.draw.line(screen,(35,35,70),(SIM_W+4,fy),(SIM_W+PANEL_W-4,fy),1)
    fy+=2
    btn_rects_time.clear()
    time_items = ["pause"] + list(TIME_SCALES)
    bw2=(PANEL_W-12)//len(time_items)
    for i,item in enumerate(time_items):
        rx=SIM_W+4+i*(bw2+2)
        rect=pygame.Rect(rx,fy,bw2,ZONE_TIME_H-2)
        btn_rects_time.append((item, rect))
        if item == "pause":
            sel = paused
            lbl = "▶" if paused else "⏸"
        else:
            sel=abs(sim.time_scale-item)<0.01 and not paused
            lbl=f"{item}x"
        pygame.draw.rect(screen,(16,52,28) if sel else (14,14,26),rect,border_radius=3)
        pygame.draw.rect(screen,(42,165,65) if sel else (32,32,55),rect,1,border_radius=3)
        tsurf=font_small.render(lbl,True,(85,230,105) if sel else (95,95,115))
        screen.blit(tsurf,tsurf.get_rect(center=rect.center))

    # Dica no rodapé
    entry = get_catalog_entry(selected_type)
    if entry is not None:
        bname=entry["name"]
        screen.blit(font_small.render(f"[ {bname} ] Arraste →",True,(70,240,105)),(SIM_W+6,LIST_BOTTOM+2))
    elif followed_body and followed_body in sim.bodies:
        screen.blit(font_small.render(f"◎ {followed_body.name}",True,(70,185,245)),(SIM_W+6,LIST_BOTTOM+2))

# ══════════════════════════════════════════
#  EDITOR ORBITAL
# ══════════════════════════════════════════
def nearest_massive_host(body):
    candidates = [o for o in sim.bodies if o is not body and o.mass > body.mass]
    if not candidates:
        return None
    return max(candidates, key=lambda o: o.mass / max((o.pos - body.pos).length_squared(), 25.0))


def circularize_body_orbit(body):
    host = nearest_massive_host(body)
    if not host:
        return False
    radial = body.pos - host.pos
    dist = max(radial.length(), host.radius + body.radius + 1.0)
    if dist <= 1e-6:
        return False
    tangent = pygame.Vector2(-radial.y, radial.x)
    if tangent.length_squared() == 0:
        tangent = pygame.Vector2(0, 1)
    tangent = tangent.normalize()
    current_rel = body.vel - host.vel
    if current_rel.dot(tangent) < 0:
        tangent *= -1
    speed = math.sqrt(G * host.mass / dist)
    body.vel = host.vel + tangent * speed
    body.trail = []
    body.collision_cooldown = 0.8
    return True


def zero_body_velocity(body):
    host = nearest_massive_host(body)
    body.vel = pygame.Vector2(host.vel) if host else pygame.Vector2(0, 0)
    body.trail = []
    body.collision_cooldown = 0.8
    return True

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
    temp_k = body_temperature(b)
    report = habitability_report(b, sim.bodies, HAB_SCALE)
    life = report["score"]
    bts  = body_type_str(b)
    spd  = b.vel.length()
    lum  = get_luminosity(b)
    ws,wc= water_state(temp_k)
    r_in,r_out=hab_zone_radii(b)
    rl   = roche_limit(b)
    atm  = getattr(b,'atmosphere',0)
    wtr  = getattr(b,'water',0)
    pressure = getattr(b, 'surface_pressure', atm)
    dom_body, dom_acc = dominant_gravity_source(b)

    temp_c = kelvin_to_celsius(temp_k)
    if temp_c < -80:      tc=(120,160,255)
    elif temp_c < 0:      tc=(100,190,255)
    elif temp_c < 60:     tc=(90,230,120)
    elif temp_c < 500:    tc=(255,190,80)
    elif temp_c < 3000:   tc=(255,120,60)
    else:                 tc=(220,180,255)

    lines=[
        (f"  {b.name}",                     (255,215,80),  True),
        (f"Tipo: {bts}",                    (185,185,210), False),
        (f"Massa: {fmt_mass(b.mass)}",      (185,185,195), False),
        (f"Raio: {fmt_num_br(b.radius,1)} un", (185,185,195), False),
        (f"Veloc.: {fmt_speed(spd, HAB_SCALE)}", (185,185,195), False),
        (f"Temp.: {fmt_temp_c(temp_k)}",     tc,            False),
        (f"Água: {ws}  {fmt_num_br(wtr*100,0)}%", wc,       False),
        (f"Atm.: {fmt_num_br(atm,2)} bar",  (140,180,220), False),
        (f"Pressão: {fmt_num_br(pressure,2)} bar", (140,180,220), False),
    ]
    if dom_body:
        dist = (b.pos - dom_body.pos).length()
        lines.append((f"Grav.dom: {dom_body.name[:13]}", (150,170,240), False))
        lines.append((f"Dist.: {fmt_distance_au(dist, HAB_SCALE)}", (150,170,240), False))
        lines.append((f"Acel.g: {fmt_acceleration(dom_acc, HAB_SCALE)}", (120,140,210), False))
    if getattr(b, "tidal_heat", 0.0) > 1.0:
        lines.append((f"Aquec. maré: {fmt_num_br(getattr(b,'tidal_heat',0.0),1)}", (230,120,80), False))
    if getattr(b, "roche_stress", 0.0) > 0.01:
        lines.append((f"Stress Roche: {fmt_num_br(getattr(b,'roche_stress',0.0)*100,0)}%", (255,85,85), False))
    if getattr(b, "ice_fraction", 0.0) > 0.05:
        lines.append((f"Gelo sup.: {fmt_num_br(getattr(b,'ice_fraction',0.0)*100,0)}%", (150,210,255), False))
    if getattr(b, "water_vapor", 0.0) > 0.05:
        lines.append((f"Vapor água: {fmt_num_br(getattr(b,'water_vapor',0.0)*100,0)}%", (190,210,255), False))
    if lum>0:
        lines.append((f"Luminos.: {fmt_num_br(lum,2)} L☉",(255,225,95),False))
    if r_in:
        lines.append((f"Zona habit.: {fmt_distance_au(r_in,HAB_SCALE)}-{fmt_distance_au(r_out,HAB_SCALE)}",(70,240,105),False))
    if rl:
        lines.append((f"Roche: {fmt_distance_au(rl,HAB_SCALE)}",(240,85,85),False))

    life_color = (70,240,105) if life >= 35 else (220,180,80) if life >= 8 else (120,120,140)
    lines.append((f"Vida: {fmt_num_br(life,1)}% ({report['class']})", life_color, False))
    factor_items = list(report.get('factors', {}).items())
    if report.get('reasons'):
        lines.append(("Obs: " + ", ".join(report['reasons'])[:30], (190,150,90), False))
    lines.append((f"Pos: ({int(b.pos.x)}, {int(b.pos.y)})",(110,110,130),False))

    h_box=len(lines)*15+62 + min(6, len(factor_items))*16
    x0=10; y0_box=HEIGHT-h_box-30
    bg=pygame.Surface((252,h_box+8),pygame.SRCALPHA)
    pygame.draw.rect(bg,(5,8,22,230),(0,0,252,h_box+8),border_radius=10)
    pygame.draw.rect(bg,(60,80,160,180),(0,0,252,h_box+8),1,border_radius=8)
    screen.blit(bg,(x0-4,y0_box-4))

    y0=y0_box
    for i,(line,color,bold) in enumerate(lines):
        f=font_title if bold else font_small
        screen.blit(f.render(line,True,color),(x0,y0))
        y0+=15

    if life>0:
        pygame.draw.rect(screen,(18,38,22),(x0,y0-2,110,5),border_radius=2)
        pygame.draw.rect(screen,(55,205,75),(x0,y0-2,int(life/100*110),5),border_radius=2)

    y0 += 12
    for key, val in factor_items[:6]:
        draw_factor_bar(screen, font_small, x0, y0, 135, key, val)
        y0 += 16

    y0+=6
    is_f=followed_body==b
    fr=pygame.Rect(x0,y0,76,18)
    er=pygame.Rect(x0+80,y0,80,18)
    mr=pygame.Rect(x0+164,y0,76,18)
    zv=pygame.Rect(x0,y0+22,76,18)
    cv=pygame.Rect(x0+80,y0+22,92,18)
    tr=pygame.Rect(x0,y0+44,108,18)
    pygame.draw.rect(screen,(16,46,65) if is_f else (14,14,28),fr,border_radius=4)
    pygame.draw.rect(screen,(50,145,205) if is_f else (36,36,60),fr,1,border_radius=4)
    screen.blit(font_small.render("Seguindo" if is_f else "Seguir",True,(70,190,245) if is_f else (95,95,115)),(x0+5,y0+3))
    pygame.draw.rect(screen,(36,26,16) if editing_name else (14,14,28),er,border_radius=4)
    pygame.draw.rect(screen,(165,125,50) if editing_name else (36,36,60),er,1,border_radius=4)
    screen.blit(font_small.render("Renomear",True,(210,170,70) if editing_name else (95,95,115)),(x0+85,y0+3))
    pygame.draw.rect(screen,(18,44,46) if moving_body is b else (14,14,28),mr,border_radius=4)
    pygame.draw.rect(screen,(60,185,190) if moving_body is b else (36,36,60),mr,1,border_radius=4)
    screen.blit(font_small.render("Mover",True,(90,220,220) if moving_body is b else (95,95,115)),(mr.x+8,y0+3))
    pygame.draw.rect(screen,(42,20,20),zv,border_radius=4)
    pygame.draw.rect(screen,(145,70,70),zv,1,border_radius=4)
    screen.blit(font_small.render("Zerar V",True,(225,145,145)),(zv.x+5,zv.y+3))
    pygame.draw.rect(screen,(22,32,54),cv,border_radius=4)
    pygame.draw.rect(screen,(75,105,190),cv,1,border_radius=4)
    screen.blit(font_small.render("Circularizar",True,(135,165,240)),(cv.x+5,cv.y+3))
    pygame.draw.rect(screen,(16,40,22),tr,border_radius=4)
    pygame.draw.rect(screen,(40,140,60),tr,1,border_radius=4)
    screen.blit(font_small.render("Terraformar",True,(70,200,90)),(x0+3,y0+47))
    return fr, er, tr, mr, zv, cv

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
info_fr=info_er=info_tr=info_mr=info_zv=info_cv=None

while running:
    validate_selected_type()
    dt=clock.tick(FPS)/1000.0
    twinkle_time+=dt
    sim.performance_mode = performance_mode

    if abs(zoom_target - zoom) > 0.0005:
        zoom += (zoom_target - zoom) * min(1.0, dt * 10.0)

    if followed_body and followed_body in sim.bodies:
        target_offset = pygame.Vector2(
            SIM_W/2/zoom-followed_body.pos.x,
            HEIGHT/2/zoom-followed_body.pos.y
        )
        camera_offset += (target_offset - camera_offset) * min(1.0, dt * 6.5)

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
                if zoom>0.1:
                    zoom=zoom_target=0.04; camera_offset=pygame.Vector2(0,0)
                else:
                    zoom=zoom_target=1.0
            if event.key==pygame.K_F5:     save_simulation()
            if event.key==pygame.K_F9:     load_simulation()
            if event.key==pygame.K_r:
                camera_offset=pygame.Vector2(0,0); zoom=zoom_target=1.0; followed_body=None
            if event.key==pygame.K_u:
                if selected_body and selected_body in sim.bodies and selected_body.mass>=5e2:
                    # Órbita inicial fora do Roche visual. A distância antiga era curta demais e a lua nascia triturada.
                    _orb_r=max(selected_body.radius*8.0, selected_body.radius+18.0)
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
                    _moon.collision_cooldown=0.6
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
                    moving_body=None
            # Setas: movem o corpo selecionado quando o modo Mover está ativo.
            # Fora dele, setas navegam pela câmera na direção intuitiva.
            if event.key in (pygame.K_UP, pygame.K_DOWN, pygame.K_LEFT, pygame.K_RIGHT):
                step = (90.0 if (pygame.key.get_mods() & pygame.KMOD_SHIFT) else 25.0) / zoom
                if moving_body and moving_body in sim.bodies:
                    if event.key == pygame.K_UP:    moving_body.pos.y -= step
                    if event.key == pygame.K_DOWN:  moving_body.pos.y += step
                    if event.key == pygame.K_LEFT:  moving_body.pos.x -= step
                    if event.key == pygame.K_RIGHT: moving_body.pos.x += step
                    moving_body.trail = []
                    moving_body.collision_cooldown = 0.8
                    selected_body = moving_body
                    followed_body = None
                else:
                    if event.key == pygame.K_UP:    camera_offset.y += step
                    if event.key == pygame.K_DOWN:  camera_offset.y -= step
                    if event.key == pygame.K_LEFT:  camera_offset.x += step
                    if event.key == pygame.K_RIGHT: camera_offset.x -= step
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
                _add_stable(cx+780, cy, 0, orbital_velocity(M_SOL,780), 5e2, 10, (180,140,80),  "Júpiter")
                planet_count = 4

        if event.type==pygame.MOUSEWHEEL:
            mx,my=pygame.mouse.get_pos()
            if mx<SIM_W:
                before = screen_to_world(mx, my, camera_offset, zoom, cx, cy)
                factor = 1.16 ** event.y
                zoom = max(0.04, min(zoom * factor, 28.0))
                zoom_target = zoom
                after = screen_to_world(mx, my, camera_offset, zoom, cx, cy)
                camera_offset += (after - before)
            else:
                panel_scroll=max(0,panel_scroll-event.y*20)

        if event.type==pygame.MOUSEBUTTONDOWN:
            mx,my=pygame.mouse.get_pos(); now=pygame.time.get_ticks()

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
                            _key_map={"atm":"atmosphere","water":"water","co2":"co2","n2":"n2","o2":"o2","ch4":"ch4","albedo":"albedo"}
                            attr=_key_map.get(key.replace("_up","").replace("_dn",""),key.replace("_up","").replace("_dn",""))
                            _defaults={"atmosphere":0.0,"water":0.0,"co2":0.0,"n2":0.0,"o2":0.0,"ch4":0.0,"albedo":0.3}
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
                # Toggles
                for var,trect in toggle_rects.items():
                    if trect.collidepoint(mx,my):
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

                if save_rect and save_rect.collidepoint(mx,my): save_simulation()
                if load_rect and load_rect.collidepoint(mx,my): load_simulation()

                for i,rect in enumerate(tab_rects):
                    if rect.collidepoint(mx,my): active_tab=i; selected_type=None; panel_scroll=0

                for rect,i in btn_rects_bodies:
                    if rect.collidepoint(mx,my):
                        key=(active_tab,i)
                        entry=get_catalog_entry(key)
                        if entry and entry.get("preset"):
                            if apply_preset(sim, entry["preset"]):
                                selected_type=None; selected_body=None; followed_body=None; moving_body=None
                                body_ages.clear(); flare_timers.clear(); graph_history.clear(); orbit_cache.clear(); preview_trail=[]
                                planet_count=len(sim.bodies)
                                paused=False
                        else:
                            selected_type=key if selected_type!=key else None
                            selected_body=None; preview_trail=[]

                for item, rect in btn_rects_time:
                    if rect.collidepoint(mx,my):
                        if item == "pause":
                            paused = not paused
                        else:
                            sim.time_scale = item
                            paused = False
                        orbit_cache.clear()

            elif mx<SIM_W:
                # Cliques nos botões do info HUD
                if info_fr and info_fr.collidepoint(mx,my):
                    followed_body=None if followed_body==selected_body else selected_body
                elif info_er and info_er.collidepoint(mx,my):
                    editing_name=True; edit_text=selected_body.name if selected_body else ""
                elif info_mr and info_mr.collidepoint(mx,my):
                    moving_body = None if moving_body is selected_body else selected_body
                    if moving_body:
                        followed_body = None
                        paused = True
                elif info_zv and info_zv.collidepoint(mx,my):
                    if selected_body and selected_body in sim.bodies:
                        zero_body_velocity(selected_body)
                elif info_cv and info_cv.collidepoint(mx,my):
                    if selected_body and selected_body in sim.bodies:
                        circularize_body_orbit(selected_body)
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
                    if moving_body and moving_body in sim.bodies:
                        new_pos = screen_to_world(mx, my, camera_offset, zoom, cx, cy)
                        moving_body.pos = pygame.Vector2(new_pos)
                        moving_body.trail = []
                        moving_body.collision_cooldown = 0.8
                        selected_body = moving_body
                    elif get_catalog_entry(selected_type) is not None and sim.can_add_body():
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
                            if hit: hit.atmosphere=estimate_atmosphere(hit)
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
                if placing:
                    placing=False; mx,my=pygame.mouse.get_pos()
                    if get_catalog_entry(selected_type) is not None and place_pos_world is not None:
                        btype=get_catalog_entry(selected_type)
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
                        if not hasattr(nb,'_terra_set'):
                            nb.atmosphere = estimate_atmosphere(nb)
                            nb.water      = 1.0 if nb.mass>=500 else 0.0
                        sim.add_body(nb)

                    preview_trail=[]
            if event.button==3: dragging=False; cam_velocity.update(0,0)

        if event.type==pygame.MOUSEMOTION:
            mx,my=pygame.mouse.get_pos()
            if dragging_slider:
                limits={"mass":(0.1,10.0),"rad":(0.1,10.0),"vel":(0.1,5.0)}
                mn,mxv=limits[dragging_slider]
                dv=(mx-slider_drag_start_x)/(PANEL_W-22)*(mxv-mn)
                nv=max(mn,min(slider_drag_start_val+dv,mxv))
                if dragging_slider=="mass":  slider_mass_mult=nv
                elif dragging_slider=="rad": slider_rad_mult=nv
                elif dragging_slider=="vel": slider_vel_mult=nv
            if moving_body and moving_body in sim.bodies and mx < SIM_W and pygame.mouse.get_pressed()[0]:
                new_pos = screen_to_world(mx, my, camera_offset, zoom, cx, cy)
                moving_body.pos = pygame.Vector2(new_pos)
                moving_body.trail = []
                moving_body.collision_cooldown = 0.8
                selected_body = moving_body
            if dragging and not dragging_slider:
                mp=pygame.Vector2(mx,my)
                delta=(mp-drag_start)/zoom
                camera_offset+=delta
                cam_velocity=delta*FPS
                drag_start=mp; followed_body=None
            if placing and place_pos_world is not None and get_catalog_entry(selected_type) is not None:
                drag_vec=pygame.Vector2(mx,my)-place_start_screen
                launch_vel=-drag_vec*(3.0/zoom)*slider_vel_mult
                btype=get_catalog_entry(selected_type)
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
    if not paused:
        sim.step(dt)  # colisões já são verificadas internamente com sub-steps
        update_environment(sim.bodies, dt, sim.time_scale, HAB_SCALE)
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
    if preview_trail and len(preview_trail)>1 and get_catalog_entry(selected_type) is not None:
        color_p=get_catalog_entry(selected_type)["color"]
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
            draw_selection_rings(screen, sx, sy, r, body==selected_body, body==followed_body)
            draw_temperature_badge(screen, sx, sy, r, body)
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
        if mx<SIM_W and get_catalog_entry(selected_type) is not None:
            btype=get_catalog_entry(selected_type)
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
    if result: info_fr, info_er, info_tr, info_mr, info_zv, info_cv = result

    if show_graph: draw_graph()
    if terraforming_body and terraforming_body in sim.bodies:
        draw_terraforming_panel(terraforming_body)

    # HUD topo esquerdo
    if paused:
        hud_bg=pygame.Surface((120,22),pygame.SRCALPHA)
        pygame.draw.rect(hud_bg,(6,6,18,185),(0,0,120,22),border_radius=5)
        screen.blit(hud_bg,(6,6))
        screen.blit(font.render("⏸ PAUSADO",True,(145,190,255)),(12,10))

    # Status discreto, sem poluir com lista de atalhos.
    status = f"Corpos: {len(sim.bodies)} | Tempo: {'pausado' if paused else str(sim.time_scale)+'x'}"
    if moving_body and moving_body in sim.bodies:
        status += f" | Movendo: {moving_body.name} | setas movem | Shift+setas rápido"
    screen.blit(font_small.render(status, True, (55,55,80)), (10, HEIGHT-12))

    draw_panel()
    pygame.display.flip()

pygame.quit()
                    
