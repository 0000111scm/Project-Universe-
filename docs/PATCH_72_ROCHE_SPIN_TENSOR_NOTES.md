# PATCH 72 — Roche + Spin Tensor

Foco físico:
- tensor de inércia proxy 2D
- velocidade angular crítica
- stress centrífugo por rotação
- stress de maré/Roche
- achatamento por spin
- perda de massa progressiva por ruptura estrutural

Novo módulo:
- physics_core/structural_dynamics.py

Este patch começa a fazer astros se romperem por:
- rotação extrema
- maré gravitacional
- limite de Roche

Ainda é 2D/proxy. Depois vira tensor 3D real.
