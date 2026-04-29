"""Composicao fisica simplificada para colisoes por material."""
MATERIAL_FRAGMENT_FACTOR={"rock":1.0,"metal":0.65,"ice":1.35,"gas":0.25,"plasma":0.1,"blackhole":0.0,"stellar_system":0.0}
MATERIAL_COLORS={"rock":(145,125,105),"metal":(165,165,175),"ice":(190,225,255),"gas":(180,160,120),"plasma":(255,210,90),"blackhole":(0,0,0),"stellar_system":(190,190,220)}
def dominant_material(body):
    if getattr(body,"material",None): return body.material
    comp=getattr(body,"composition",None) or {}
    return max(comp.items(),key=lambda kv:kv[1])[0] if comp else "rock"
def mix_composition(a,b,ma,mb):
    total=max(ma+mb,1e-9); out={}
    for src,m in ((a,ma),(b,mb)):
        for k,v in (getattr(src,"composition",None) or {}).items(): out[k]=out.get(k,0)+v*m/total
    s=sum(out.values()) or 1
    return {k:v/s for k,v in out.items()}
def classify_result_material(a,b,total_mass):
    ma,mb=dominant_material(a),dominant_material(b)
    if "blackhole" in (ma,mb): return "blackhole"
    if "stellar_system" in (ma,mb): return "stellar_system"
    if ma==mb=="plasma" or ("plasma" in (ma,mb) and total_mass>=8e5): return "plasma"
    comp=mix_composition(a,b,getattr(a,"mass",1),getattr(b,"mass",1))
    return max(comp.items(),key=lambda kv:kv[1])[0] if comp else "rock"
def fragment_factor(body): return MATERIAL_FRAGMENT_FACTOR.get(dominant_material(body),1.0)
def material_color(material): return MATERIAL_COLORS.get(material,MATERIAL_COLORS["rock"])
