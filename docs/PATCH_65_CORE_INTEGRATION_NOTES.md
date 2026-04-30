# PATCH 65 — Physics Core Integration

Agora o physics_core deixa de ser decorativo:
- adiciona physics_core/system.py
- Simulation inicializa PhysicsCoreSystem
- Simulation.step() usa ECS/SoA FP64 para integração orbital
- colisões e Roche ainda ficam no sistema antigo por enquanto
- fallback antigo continua se o core falhar

Resultado:
- primeiro uso real do novo core no loop físico
- Body segue como render/UI, não como fonte principal da física orbital
