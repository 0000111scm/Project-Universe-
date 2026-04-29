"""Base SPH leve: estimativa de partículas para ejeção de impacto.
Solver SPH real fica para a próxima fase; este módulo organiza a ponte física.
"""
def estimate_particle_count(ejecta_mass, body_mass, severity, max_particles=24):
    if ejecta_mass <= 0 or body_mass <= 0:
        return 0
    frac = ejecta_mass / body_mass
    return int(max(1, min(max_particles, frac*80 + severity*2)))
