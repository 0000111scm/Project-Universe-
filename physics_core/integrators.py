# physics_core/integrators.py
"""Integradores físicos.

Feynman:
- velocidade diz para onde o corpo vai;
- gravidade muda a velocidade;
- Leapfrog faz isso em meio-passo para não vazar energia orbital.
"""

def leapfrog_step(state, dt, acceleration_func):
    """Velocity Verlet / Leapfrog em arrays.

    1. calcula aceleração atual
    2. velocidade anda meio passo
    3. posição anda passo inteiro
    4. recalcula aceleração
    5. velocidade completa o segundo meio passo
    """
    n = state.n
    if n == 0:
        return

    active = state.active[:n]
    half = 0.5 * float(dt)

    state.acc[:n] = acceleration_func(state)
    state.vel[:n][active] += state.acc[:n][active] * half
    state.pos[:n][active] += state.vel[:n][active] * float(dt)

    state.acc[:n] = acceleration_func(state)
    state.vel[:n][active] += state.acc[:n][active] * half
