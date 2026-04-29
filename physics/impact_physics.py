
"""Análise de impacto: resultado baseado em energia, massa física, família e material."""
from dataclasses import dataclass
try:
    from physics.real_scale import physical_mass_for_collision, physical_radius_for_collision
except Exception:
    from real_scale import physical_mass_for_collision, physical_radius_for_collision

@dataclass
class ImpactAnalysis:
    outcome: str
    dominant: object
    secondary: object
    mass_ratio: float
    relative_speed: float
    impact_energy: float
    specific_energy: float
    binding_proxy: float
    severity: float
    retention: float
    ejecta_fraction: float
    result_name: str

def fam(body):
    return getattr(body,"family",None) or getattr(body,"material",None) or "small_body"

def classify_by_mass_and_family(body):
    f=fam(body)
    if f and f!="fragment": return f
    m=getattr(body,"mass",0)
    if m>=1e11: return "galaxy"
    if m>=5e6: return "blackhole"
    if m>=2e5: return "star"
    if m>=5e4: return "gas_giant"
    if m>=5e2: return "planet"
    if m>=1e1: return "moon"
    return "small_body"

def label(body):
    return {
        "galaxy":"Galáxia","blackhole":"Buraco Negro","star":"Estrela","white_dwarf":"Anã Branca",
        "neutron_star":"Estrela de Nêutrons","gas_giant":"Gigante Gasoso","ice_giant":"Gigante Gelado",
        "planet":"Planeta","dwarf_planet":"Planeta Anão","moon":"Lua","small_body":"Corpo Menor",
        "fragment":"Fragmento"
    }.get(classify_by_mass_and_family(body),"Corpo")

def impact_analysis(a,b):
    rel=(a.vel-b.vel).length()
    ma,mb=physical_mass_for_collision(a),physical_mass_for_collision(b)
    dominant, secondary=(a,b) if ma>=mb else (b,a)
    md,ms=max(ma,mb),min(ma,mb)
    ratio=ms/max(md,1e-30)
    mu=ma*mb/max(ma+mb,1e-30)
    energy=0.5*mu*rel*rel
    specific=energy/max(ms,1e-30)
    binding=max(6.67430e-11*ms/max(physical_radius_for_collision(secondary)*1000,1),1e-12)
    severity=specific/binding
    fa,fb=classify_by_mass_and_family(a),classify_by_mass_and_family(b)

    if "blackhole" in (fa,fb):
        bh=a if fa=="blackhole" else b
        other=b if bh is a else a
        return ImpactAnalysis("blackhole_accretion",bh,other,ratio,rel,energy,specific,binding,severity,.995,0,"Buraco Negro")

    if "galaxy" in (fa,fb):
        if fa==fb=="galaxy":
            return ImpactAnalysis("galaxy_merger",dominant,secondary,ratio,rel,energy,specific,binding,severity,.98,.01,"Galáxia Fundida")
        gal=a if fa=="galaxy" else b
        other=b if gal is a else a
        return ImpactAnalysis("galactic_accretion",gal,other,ratio,rel,energy,specific,binding,severity,.999,0,getattr(gal,"name","Galáxia"))

    stellar=("star","white_dwarf","neutron_star")
    if fa in stellar or fb in stellar:
        if not (fa in stellar and fb in stellar):
            star=a if fa in stellar else b
            other=b if star is a else a
            return ImpactAnalysis("stellar_accretion",star,other,ratio,rel,energy,specific,binding,severity,.985,.01,getattr(star,"name","Estrela"))
        total_solar=(ma+mb)/1.9885e30
        if total_solar>=25:
            return ImpactAnalysis("stellar_collapse_blackhole",dominant,secondary,ratio,rel,energy,specific,binding,severity,.55,.20,"Buraco Negro")
        if total_solar>=8:
            return ImpactAnalysis("stellar_collapse_neutron",dominant,secondary,ratio,rel,energy,specific,binding,severity,.65,.18,"Estrela de Nêutrons")
        return ImpactAnalysis("stellar_merger",dominant,secondary,ratio,rel,energy,specific,binding,severity,.94,.03,"Estrela Fundida")

    if ratio<0.02 and severity<0.35:
        outcome,ret,eject="cratering",.97,.03
        name=getattr(dominant,"name",label(dominant))
    elif ratio<0.12 and severity<1.0:
        outcome,ret,eject="partial_disruption",.88,.12
        name=getattr(dominant,"name",label(dominant))
    elif severity<0.35 and ratio>=0.12:
        outcome,ret,eject="gentle_merge",.96,.02
        name=f"{label(dominant)} Fundido"
    elif severity<2.5:
        outcome,ret,eject="giant_impact",.76,.18
        name=f"{label(dominant)} Fundido"
    else:
        outcome,ret,eject="catastrophic_disruption",.48,.42
        name="Campo de Detritos" if ratio>.45 else f"{label(dominant)} Impactado"

    mat=getattr(secondary,"material","rock")
    if mat=="ice": eject*=1.25
    elif mat=="gas": eject*=.45
    elif mat=="metal": eject*=.75
    eject=max(0,min(.65,eject))
    return ImpactAnalysis(outcome,dominant,secondary,ratio,rel,energy,specific,binding,severity,ret,eject,name)
